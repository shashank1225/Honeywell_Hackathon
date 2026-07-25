"""
AABOS MCP Server.

Exposes building telemetry as MCP resources and HVAC setpoint changes as MCP tools.
The LLM strategic layer (Phase 4) reads these resources but never issues actuator
commands directly — setpoint tools update targets only; the Safety Sentinel (Phase 3)
will validate downstream actuator commands before they reach EnergyPlus.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.schemas.telemetry import Setpoints
from app.services.control_gateway import apply_safe_setpoints
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


def main() -> None:
    """Run the MCP server over SSE for local development."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
