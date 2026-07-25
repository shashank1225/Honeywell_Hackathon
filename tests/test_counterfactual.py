from datetime import UTC, datetime

from app.schemas.telemetry import BuildingTelemetry, OperatingPolicy
from app.services.automation_memory import AutomationMemory
from app.services.autonomous_control import AutonomousControlLoop
from app.services.counterfactual import CounterfactualAutomation
from app.services.energy_efficiency import EnergyEfficiencyTracker
from app.services.goal_management import AutonomousGoalManagementSystem
from app.simulation.state import BuildingState


def sample() -> BuildingTelemetry:
    return BuildingTelemetry(
        timestamp=datetime.now(UTC),
        temperature_c=22.0,
        humidity_pct=45.0,
        occupancy_pct=50.0,
        power_kw=6.0,
    )


def test_counterfactual_compares_all_non_selected_policies_without_actuating():
    evaluation = CounterfactualAutomation().evaluate(sample(), OperatingPolicy.ENERGY_SAVER)

    assert evaluation.selected_policy == OperatingPolicy.ENERGY_SAVER
    assert len(evaluation.alternatives) == 3
    assert {outcome.policy for outcome in evaluation.alternatives} == {
        OperatingPolicy.BALANCED,
        OperatingPolicy.COMFORT_FIRST,
        OperatingPolicy.CARBON_AWARE,
    }
    assert evaluation.selected_outcome.projected_power_kw > 0


def test_autonomous_loop_records_observed_policy_episode_with_counterfactual():
    class NoopStrategicQueue:
        def submit(self, goal):
            return goal

    memory = AutomationMemory()
    loop = AutonomousControlLoop(
        state=BuildingState(),
        goals=AutonomousGoalManagementSystem(),
        strategic_queue=NoopStrategicQueue(),
        memory=memory,
        energy_tracker=EnergyEfficiencyTracker(),
    )

    loop.process(sample())

    episode = memory.recent(1)[0]
    assert episode.counterfactual is not None
    assert episode.temperature_c == 22.0
    assert episode.occupancy_pct == 50.0
