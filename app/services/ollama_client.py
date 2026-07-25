"""Strict, local Ollama client for AABOS strategic policy selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import get_settings
from app.schemas.telemetry import OperatingPolicy, StrategicGoal, TelemetryWindowSummary


PROMPT_TEMPLATE = """You are the Strategic Reasoning Layer of AABOS, an autonomous building operating system.

Your role is supervisory only. You never issue actuator commands, bypass safety rules, or modify an EnergyPlus model directly.
You receive compact rolling-window telemetry from an EnergyPlus digital twin, not raw simulation logs.

Before you recommend a policy, you MUST call the inspect_building_runtime MCP tool. It reads the current building context, inspects the runtime-generated EnergyPlus model, and checks the bounded runtime error log. Use the returned tool evidence in your rationale.

Select one operating policy: balanced, energy_saver, comfort_first, carbon_aware.
Constraints: HVAC stays within 16-30 C; ventilation stays within 0-100%; the deterministic Safety Sentinel validates every downstream change.
If comfort degrades, prefer comfort_first. Return JSON only: {{"policy":"...","rationale":"..."}}. Keep rationale to one sentence of at most 24 words.

Goal: {goal}, target: {target_percent}%
Sliding-window telemetry: average_temperature_c={average_temperature_c}, min_temperature_c={min_temperature_c}, max_temperature_c={max_temperature_c}, average_humidity_pct={average_humidity_pct}, average_occupancy_pct={average_occupancy_pct}, average_power_kw={average_power_kw}, peak_power_kw={peak_power_kw}, estimated_energy_kwh={estimated_energy_kwh}.
"""


class OllamaUnavailable(RuntimeError):
    """Raised when the local model cannot provide a valid bounded response."""


@dataclass(frozen=True, slots=True)
class LLMPolicyRecommendation:
    policy: OperatingPolicy
    rationale: str
    mcp_tools_used: tuple[str, ...] = ()


MCP_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_building_runtime",
            "description": "Read MCP building context, inspect generated EnergyPlus model, and extract bounded runtime errors in one read-only tool call.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
REQUIRED_MCP_TOOLS = {tool["function"]["name"] for tool in MCP_TOOL_DEFINITIONS}
POLICY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "policy": {"type": "string", "enum": [policy.value for policy in OperatingPolicy]},
        "rationale": {"type": "string"},
    },
    "required": ["policy", "rationale"],
    "additionalProperties": False,
}


class OllamaStrategicClient:
    """Calls a local open-source model with a bounded JSON-only prompt."""

    def warm(self) -> None:
        """Load the local model in the background so the first operator request is fast."""
        settings = get_settings()
        if not settings.llm_enabled:
            return
        request = Request(
            f"{settings.llm_base_url.rstrip('/')}/api/generate",
            data=json.dumps(
                {
                    "model": settings.llm_model,
                    "prompt": "Respond with {}.",
                    "stream": False,
                    "format": "json",
                    "keep_alive": settings.llm_keep_alive,
                    "options": {"temperature": 0, "num_predict": 4, "num_ctx": settings.llm_context_tokens},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.llm_timeout_seconds):
                pass
        except (URLError, TimeoutError, OSError):
            # A local model is optional for startup. The strategic worker will
            # retain its deterministic fallback if Ollama is unavailable.
            return

    def recommend(self, goal: StrategicGoal, summary: TelemetryWindowSummary) -> LLMPolicyRecommendation:
        settings = get_settings()
        if not settings.llm_enabled:
            raise OllamaUnavailable("LLM integration is disabled")
        prompt = PROMPT_TEMPLATE.format(goal=goal.objective.value, target_percent=goal.target_percent, **summary.model_dump())
        messages: list[dict] = [
            {
                "role": "system",
                "content": (
                    "Use MCP tools before policy reasoning. You can only recommend a named policy; "
                    "the AABOS Decision Engine and Safety Sentinel execute all downstream work."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        used_tools: list[str] = []
        final_content = ""
        try:
            for _ in range(6):
                payload = self._chat(
                    settings,
                    messages,
                    require_json=REQUIRED_MCP_TOOLS.issubset(used_tools),
                )
                message = payload.get("message", {})
                if not isinstance(message, dict):
                    raise OllamaUnavailable("Ollama returned an invalid chat message")
                tool_calls = message.get("tool_calls") or []
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.get("content", ""),
                        "tool_calls": tool_calls,
                    }
                )
                if not tool_calls:
                    missing_tools = REQUIRED_MCP_TOOLS.difference(used_tools)
                    if missing_tools:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Before a final policy, call each remaining required MCP tool: "
                                    f"{', '.join(sorted(missing_tools))}."
                                ),
                            }
                        )
                        continue
                    final_content = str(message.get("content", ""))
                    break
                for call in tool_calls:
                    name = str(call.get("function", {}).get("name", ""))
                    arguments = call.get("function", {}).get("arguments", {})
                    result = self._execute_mcp_tool(name, arguments if isinstance(arguments, dict) else {})
                    used_tools.append(name)
                    messages.append({"role": "tool", "tool_name": name, "content": result})
        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaUnavailable(f"Ollama unavailable: {exc}") from exc

        missing_tools = REQUIRED_MCP_TOOLS.difference(used_tools)
        if missing_tools:
            raise OllamaUnavailable(f"Ollama did not invoke required MCP tools: {', '.join(sorted(missing_tools))}")
        try:
            answer = json.loads(final_content.removeprefix("```json").removesuffix("```").strip())
            policy = OperatingPolicy(answer["policy"])
            rationale = str(answer["rationale"]).strip()
            if not rationale:
                raise ValueError("empty rationale")
            return LLMPolicyRecommendation(policy=policy, rationale=rationale, mcp_tools_used=tuple(dict.fromkeys(used_tools)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OllamaUnavailable("Ollama returned invalid policy JSON") from exc

    @staticmethod
    def _execute_mcp_tool(name: str, arguments: dict) -> str:
        """Execute the same registered MCP tools exposed to external clients."""
        from app.mcp.server import inspect_building_runtime

        tools = {
            "inspect_building_runtime": inspect_building_runtime,
        }
        tool = tools.get(name)
        if tool is None:
            return json.dumps({"status": "rejected", "reason": f"Unknown MCP tool: {name}"})
        try:
            return tool(**arguments)
        except Exception as exc:
            return json.dumps({"status": "unavailable", "tool": name, "error": str(exc)})

    @staticmethod
    def _chat(settings, messages: list[dict], *, require_json: bool) -> dict:
        body = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": False,
            "tools": MCP_TOOL_DEFINITIONS,
            "keep_alive": settings.llm_keep_alive,
            "options": {
                "temperature": 0,
                "num_predict": settings.llm_max_tokens,
                "num_ctx": settings.llm_context_tokens,
            },
        }
        if require_json:
            body["format"] = POLICY_RESPONSE_SCHEMA
        request = Request(
            f"{settings.llm_base_url.rstrip('/')}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
