"""MCP resource client used by supervisory agents for building context."""

from __future__ import annotations

from collections.abc import Callable

from app.mcp.server import current_setpoints, current_telemetry
from app.schemas.telemetry import BuildingTelemetry, Setpoints


class MCPBuildingContext:
    """Reads the same MCP resources exposed to external strategic agents."""

    def __init__(
        self,
        telemetry_resource: Callable[[], str] = current_telemetry,
        setpoints_resource: Callable[[], str] = current_setpoints,
    ) -> None:
        self._telemetry_resource = telemetry_resource
        self._setpoints_resource = setpoints_resource

    def read_telemetry(self) -> BuildingTelemetry:
        payload = self._telemetry_resource()
        return BuildingTelemetry.model_validate_json(payload)

    def read_setpoints(self) -> Setpoints:
        return Setpoints.model_validate_json(self._setpoints_resource())
