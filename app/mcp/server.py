"""
AABOS MCP Server.

Exposes building telemetry as MCP resources and HVAC setpoint changes as MCP tools.
The LLM strategic layer (Phase 4) reads these resources but never issues actuator
commands directly — setpoint tools update targets only; the Safety Sentinel (Phase 3)
will validate downstream actuator commands before they reach EnergyPlus.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.schemas.telemetry import OperatingPolicy, Setpoints
from app.services.control_gateway import apply_safe_setpoints
from app.services.policy_handoff import PolicyHandoff, policy_handoff_queue
from app.simulation.state import building_state

settings = get_settings()

mcp = FastMCP(
    "AABOS Building MCP Server",
    host=settings.mcp_host,
    port=settings.mcp_port,
)


@mcp.resource("building://telemetry/current")
def current_telemetry() -> str:
    """Latest zone telemetry: temperature, humidity, occupancy, and power."""
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        return json.dumps({"status": "waiting", "message": "No telemetry published yet"})
    return telemetry.model_dump_json()


@mcp.resource("building://setpoints/current")
def current_setpoints() -> str:
    """Active HVAC temperature and ventilation setpoints."""
    return building_state.get_setpoints().model_dump_json()


@mcp.tool()
def get_building_context() -> str:
    """Read live telemetry and active setpoints through the MCP context contract."""
    return json.dumps(
        {
            "telemetry": json.loads(current_telemetry()),
            "setpoints": json.loads(current_setpoints()),
            "source": "AABOS MCP building resources",
        }
    )


@mcp.tool()
def inspect_generated_model() -> str:
    """Inspect the runtime-generated EnergyPlus IDF header without modifying it."""
    model_path = Path(settings.energyplus_generated_idf_path)
    if not model_path.exists():
        return json.dumps({"status": "missing", "path": str(model_path)})
    try:
        header = model_path.read_text(encoding="utf-8", errors="replace").splitlines()[:4]
    except OSError as exc:
        return json.dumps({"status": "unavailable", "path": str(model_path), "error": str(exc)})
    return json.dumps(
        {
            "status": "available",
            "path": str(model_path.resolve()),
            "bytes": model_path.stat().st_size,
            "header": header,
        }
    )


@mcp.tool()
def read_energyplus_runtime_errors(max_characters: int = 1600) -> str:
    """Read a bounded tail of the current EnergyPlus error log for diagnosis."""
    limit = min(4000, max(200, int(max_characters)))
    output_dir = Path(settings.energyplus_output_dir)
    candidates = [output_dir / "eplusout.err", output_dir / "var" / "energyplus" / "eplusout.err"]
    error_path = next((path for path in candidates if path.exists()), None)
    if error_path is None:
        return json.dumps({"status": "not_available", "message": "No EnergyPlus error log has been generated yet."})
    try:
        content = error_path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError as exc:
        return json.dumps({"status": "unavailable", "path": str(error_path), "error": str(exc)})
    return json.dumps({"status": "available", "path": str(error_path.resolve()), "tail": content})


@mcp.tool()
def inspect_building_runtime() -> str:
    """Collect bounded MCP evidence for LLM reasoning in one tool call.

    The result includes live building context, the generated IDF inspection,
    and the EnergyPlus error-log tail. It is read-only and does not modify the
    simulator or actuator targets.
    """
    return json.dumps(
        {
            "building_context": json.loads(get_building_context()),
            "generated_model": json.loads(inspect_generated_model()),
            "runtime_errors": json.loads(read_energyplus_runtime_errors(600)),
        }
    )


@mcp.tool()
def queue_policy_recommendation(policy: str, rationale: str) -> str:
    """Queue a high-level policy for next-cycle Safety Sentinel validation.

    This never changes an actuator directly. The autonomous control loop reads
    the recommendation on the next cycle and validates its setpoints before
    writing the EnergyPlus runtime model.
    """
    try:
        selected_policy = OperatingPolicy(policy)
    except ValueError:
        return json.dumps({"status": "rejected", "reason": f"Unknown operating policy: {policy}"})
    clean_rationale = rationale.strip()[:500]
    if not clean_rationale:
        return json.dumps({"status": "rejected", "reason": "A policy rationale is required."})
    policy_handoff_queue.publish(
        PolicyHandoff(policy=selected_policy, rationale=clean_rationale, source="mcp-llm-tool")
    )
    return json.dumps(
        {
            "status": "queued",
            "policy": selected_policy.value,
            "message": "Queued for next-cycle Safety Sentinel validation; no actuator changed directly.",
        }
    )


@mcp.tool()
def set_hvac_temperature(zone: str, temperature_c: float) -> str:
    """
    Set the HVAC cooling/heating target temperature for a building zone.

    Args:
        zone: Building zone identifier (e.g. 'main', 'north-wing').
        temperature_c: Target air temperature in Celsius (16-30).
    """
    if not 16.0 <= temperature_c <= 30.0:
        return json.dumps(
            {
                "status": "rejected",
                "reason": "temperature_c must be between 16 and 30",
            }
        )

    current = building_state.get_setpoints()
    result = apply_safe_setpoints(building_state, current.model_copy(update={"hvac_temperature_c": temperature_c}))
    if not result.accepted or result.safe_setpoints is None:
        return json.dumps({"status": "rejected", "reason": result.reasons})
    updated = result.safe_setpoints
    return json.dumps(
        {
            "status": "accepted",
            "zone": zone,
            "setpoints": updated.model_dump(),
        }
    )


@mcp.tool()
def adjust_ventilation(zone: str, ventilation_rate_pct: float) -> str:
    """
    Adjust mechanical ventilation rate for a building zone.

    Args:
        zone: Building zone identifier.
        ventilation_rate_pct: Ventilation intensity from 0 (off) to 100 (max).
    """
    if not 0.0 <= ventilation_rate_pct <= 100.0:
        return json.dumps(
            {
                "status": "rejected",
                "reason": "ventilation_rate_pct must be between 0 and 100",
            }
        )

    current = building_state.get_setpoints()
    result = apply_safe_setpoints(building_state, current.model_copy(update={"ventilation_rate_pct": ventilation_rate_pct}))
    if not result.accepted or result.safe_setpoints is None:
        return json.dumps({"status": "rejected", "reason": result.reasons})
    updated = result.safe_setpoints
    return json.dumps(
        {
            "status": "accepted",
            "zone": zone,
            "setpoints": updated.model_dump(),
        }
    )


@mcp.tool()
def adjust_lighting(zone: str, lighting_level_pct: float) -> str:
    """Adjust interior-lighting schedule intensity from 0 to 100 percent."""
    if not 0.0 <= lighting_level_pct <= 100.0:
        return json.dumps({"status": "rejected", "reason": "lighting_level_pct must be between 0 and 100"})
    current = building_state.get_setpoints()
    result = apply_safe_setpoints(building_state, current.model_copy(update={"lighting_level_pct": lighting_level_pct}))
    if not result.accepted or result.safe_setpoints is None:
        return json.dumps({"status": "rejected", "reason": result.reasons})
    return json.dumps({"status": "accepted", "zone": zone, "setpoints": result.safe_setpoints.model_dump()})


def main() -> None:
    """Run the MCP server over SSE for local development."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
