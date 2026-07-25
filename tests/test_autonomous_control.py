from datetime import UTC, datetime

from app.schemas.telemetry import BuildingTelemetry, OperatingPolicy
from app.services.autonomous_control import AutonomousControlLoop
from app.services.goal_management import AutonomousGoalManagementSystem
from app.services.policy_handoff import PolicyHandoff, PolicyHandoffQueue
from app.simulation.state import BuildingState


def telemetry(power_kw: float, temperature_c: float = 22.0) -> BuildingTelemetry:
    return BuildingTelemetry(
        timestamp=datetime.now(UTC), temperature_c=temperature_c, humidity_pct=45,
        occupancy_pct=50, power_kw=power_kw,
    )


def test_autonomous_loop_selects_energy_policy_and_changes_next_cycle_setpoints():
    state = BuildingState()
    loop = AutonomousControlLoop(state=state)

    status = loop.process(telemetry(power_kw=6.0))

    assert status.active_policy == OperatingPolicy.ENERGY_SAVER
    assert state.get_setpoints().hvac_temperature_c == 24.0
    assert state.get_setpoints().ventilation_rate_pct == 35.0
    assert len(status.agent_recommendations) == 4
    assert status.decision_confidence > 0


def test_autonomous_loop_activates_fallback_after_measured_comfort_shortfall():
    state = BuildingState()
    loop = AutonomousControlLoop(state=state)
    loop.process(telemetry(power_kw=6.0))

    status = loop.process(telemetry(power_kw=6.0, temperature_c=29.0))

    assert status.fallback_activated
    assert status.active_policy == OperatingPolicy.COMFORT_FIRST


def test_llm_policy_handoff_is_safety_validated_on_next_control_cycle():
    state = BuildingState()
    handoffs = PolicyHandoffQueue()
    handoffs.publish(PolicyHandoff(policy=OperatingPolicy.ENERGY_SAVER, rationale="LLM saw a high-energy trend."))
    loop = AutonomousControlLoop(state=state, handoffs=handoffs)

    status = loop.process(telemetry(power_kw=1.0))

    assert status.active_policy == OperatingPolicy.ENERGY_SAVER
    assert state.get_setpoints().hvac_temperature_c == 24.0
    assert "LLM recommendation accepted by Safety Sentinel" in status.last_action


def test_rejected_llm_policy_activates_safe_balanced_fallback():
    state = BuildingState()
    state.update_setpoints(hvac_temperature_c=24.0, ventilation_rate_pct=35.0)
    handoffs = PolicyHandoffQueue()
    handoffs.publish(PolicyHandoff(policy=OperatingPolicy.COMFORT_FIRST, rationale="Prioritize comfort."))
    loop = AutonomousControlLoop(state=state, handoffs=handoffs)

    status = loop.process(telemetry(power_kw=1.0))

    assert status.active_policy == OperatingPolicy.BALANCED
    assert status.fallback_activated
    assert state.get_setpoints().hvac_temperature_c == 22.0
    assert state.get_setpoints().ventilation_rate_pct == 50.0
    assert "safe balanced fallback activated" in status.last_action


def test_major_telemetry_transition_creates_one_proactive_goal_and_queues_slow_reasoning():
    class RecordingStrategicQueue:
        def __init__(self) -> None:
            self.goals = []

        def submit(self, goal):
            self.goals.append(goal)

    queue = RecordingStrategicQueue()
    loop = AutonomousControlLoop(
        state=BuildingState(),
        goals=AutonomousGoalManagementSystem(),
        strategic_queue=queue,
    )

    status = loop.process(telemetry(power_kw=8.0))
    loop.process(telemetry(power_kw=8.0))

    assert status.active_goal is not None
    assert "Major telemetry transition" in status.strategic_update
    assert len(queue.goals) == 1
