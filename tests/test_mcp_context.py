from datetime import UTC, datetime

from app.agents.mcp_context import MCPBuildingContext
from app.schemas.telemetry import BuildingTelemetry, Setpoints
from app.services.decision_engine import DecisionEngine


def test_decision_engine_reads_agent_context_through_mcp_resources():
    telemetry = BuildingTelemetry(timestamp=datetime.now(UTC), temperature_c=22, humidity_pct=45, occupancy_pct=50, power_kw=9)
    context = MCPBuildingContext(
        telemetry_resource=lambda: telemetry.model_dump_json(),
        setpoints_resource=lambda: Setpoints().model_dump_json(),
    )

    decision = DecisionEngine().decide_from_mcp(context)

    assert decision.selected_policy.value == "energy_saver"
