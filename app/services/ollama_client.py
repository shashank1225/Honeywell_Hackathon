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

Select one operating policy: balanced, energy_saver, comfort_first, carbon_aware.
Constraints: HVAC stays within 16-30 C; ventilation stays within 0-100%; the deterministic Safety Sentinel validates every downstream change.
If comfort degrades, prefer comfort_first. Return JSON only: {{"policy":"...","rationale":"..."}}.

Goal: {goal}, target: {target_percent}%
Sliding-window telemetry: average_temperature_c={average_temperature_c}, min_temperature_c={min_temperature_c}, max_temperature_c={max_temperature_c}, average_humidity_pct={average_humidity_pct}, average_occupancy_pct={average_occupancy_pct}, average_power_kw={average_power_kw}, peak_power_kw={peak_power_kw}, estimated_energy_kwh={estimated_energy_kwh}.
"""


class OllamaUnavailable(RuntimeError):
    """Raised when the local model cannot provide a valid bounded response."""


@dataclass(frozen=True, slots=True)
class LLMPolicyRecommendation:
    policy: OperatingPolicy
    rationale: str


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
        request = Request(
            f"{settings.llm_base_url.rstrip('/')}/api/generate",
            data=json.dumps(
                {
                    "model": settings.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "keep_alive": settings.llm_keep_alive,
                    "options": {
                        "temperature": 0,
                        "num_predict": settings.llm_max_tokens,
                        "num_ctx": settings.llm_context_tokens,
                    },
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.llm_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaUnavailable(f"Ollama unavailable: {exc}") from exc
        try:
            answer = json.loads(payload["response"])
            policy = OperatingPolicy(answer["policy"])
            rationale = str(answer["rationale"]).strip()
            if not rationale:
                raise ValueError("empty rationale")
            return LLMPolicyRecommendation(policy=policy, rationale=rationale)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OllamaUnavailable("Ollama returned invalid policy JSON") from exc
