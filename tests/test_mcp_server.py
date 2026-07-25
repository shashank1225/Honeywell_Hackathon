import json

from app.mcp.server import (
    adjust_lighting,
    adjust_ventilation,
    current_setpoints,
    current_telemetry,
    get_building_context,
    inspect_building_runtime,
    inspect_generated_model,
    queue_policy_recommendation,
    read_energyplus_runtime_errors,
    set_hvac_temperature,
)
from app.services.policy_handoff import policy_handoff_queue
from app.simulation.energyplus_runner import EnergyPlusRunner
from app.simulation.state import BuildingState
from tests.fakes import FakeEnergyPlusBackend


def test_mcp_resources_and_tools_use_shared_state(monkeypatch):
    state = BuildingState()
    runner = EnergyPlusRunner(state=state, interval_seconds=0.1, backend=FakeEnergyPlusBackend())
    runner.tick_once()

    monkeypatch.setattr("app.mcp.server.building_state", state)

    telemetry_payload = json.loads(current_telemetry())
    assert telemetry_payload["temperature_c"] is not None

    setpoints_payload = json.loads(current_setpoints())
    assert setpoints_payload["hvac_temperature_c"] == 22.0

    tool_result = json.loads(set_hvac_temperature("main", 20.0))
    assert tool_result["status"] == "accepted"
    assert tool_result["setpoints"]["hvac_temperature_c"] == 20.0

    ventilation_result = json.loads(adjust_ventilation("main", 75.0))
    assert ventilation_result["status"] == "accepted"
    assert ventilation_result["setpoints"]["ventilation_rate_pct"] == 75.0

    lighting_result = json.loads(adjust_lighting("main", 75.0))
    assert lighting_result["status"] == "accepted"
    assert lighting_result["setpoints"]["lighting_level_pct"] == 75.0


def test_mcp_tool_rejects_invalid_temperature(monkeypatch):
    state = BuildingState()
    monkeypatch.setattr("app.mcp.server.building_state", state)

    result = json.loads(set_hvac_temperature("main", 35.0))
    assert result["status"] == "rejected"


def test_mcp_reasoning_tools_inspect_context_model_errors_and_queue_safe_policy(monkeypatch):
    state = BuildingState()
    runner = EnergyPlusRunner(state=state, interval_seconds=0.1, backend=FakeEnergyPlusBackend())
    runner.tick_once()
    monkeypatch.setattr("app.mcp.server.building_state", state)

    context = json.loads(get_building_context())
    model = json.loads(inspect_generated_model())
    errors = json.loads(read_energyplus_runtime_errors(200))
    runtime = json.loads(inspect_building_runtime())
    queued = json.loads(queue_policy_recommendation("energy_saver", "MCP evidence supports an energy policy."))

    assert context["telemetry"]["power_kw"] > 0
    assert model["status"] in {"available", "missing"}
    assert errors["status"] in {"available", "not_available"}
    assert runtime["building_context"]["telemetry"]["power_kw"] > 0
    assert queued["status"] == "queued"
    assert policy_handoff_queue.consume() is not None
