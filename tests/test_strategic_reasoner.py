from datetime import UTC, datetime

from app.schemas.telemetry import AutomationEpisode, BuildingTelemetry, GoalType, OperatingPolicy, StrategicGoal
from app.services.automation_memory import AutomationMemory
from app.services.strategic_reasoner import StrategicReasoner


def telemetry() -> BuildingTelemetry:
    return BuildingTelemetry(
        timestamp=datetime.now(UTC), temperature_c=22.0, humidity_pct=45.0,
        occupancy_pct=45.0, power_kw=4.0,
    )


def test_strategic_goal_translates_to_non_actuating_policy():
    plan = StrategicReasoner(memory=AutomationMemory()).create_plan(
        StrategicGoal(objective=GoalType.ENERGY_REDUCTION, target_percent=15), telemetry()
    )

    assert plan.selected_policy == OperatingPolicy.ENERGY_SAVER
    assert plan.proposed_setpoints.hvac_temperature_c == 24.0
    assert "Safety Sentinel" in plan.explanation[-1]


def test_automation_memory_aggregates_policy_rewards():
    memory = AutomationMemory()
    memory.record(AutomationEpisode(
        timestamp=datetime.now(UTC), policy=OperatingPolicy.CARBON_AWARE,
        reward=0.8, energy_kwh=20, comfort_score=0.9, carbon_kg=4, confidence=0.8,
    ))
    memory.record(AutomationEpisode(
        timestamp=datetime.now(UTC), policy=OperatingPolicy.CARBON_AWARE,
        reward=0.4, energy_kwh=18, comfort_score=0.8, carbon_kg=3, confidence=0.7,
    ))

    performance = memory.policy_performance()

    assert performance[0].policy == OperatingPolicy.CARBON_AWARE
    assert performance[0].average_reward == 0.6
    assert performance[0].observations == 2
