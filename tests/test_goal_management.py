from datetime import UTC, datetime

from app.schemas.telemetry import BuildingTelemetry, GoalRequest, GoalSource, GoalStatus, GoalType
from app.services.goal_management import AutonomousGoalManagementSystem


def telemetry(power_kw: float = 8.0) -> BuildingTelemetry:
    return BuildingTelemetry(timestamp=datetime.now(UTC), temperature_c=22, humidity_pct=45, occupancy_pct=50, power_kw=power_kw)


def test_goal_negotiation_marks_feasible_energy_goal_accepted():
    system = AutonomousGoalManagementSystem()
    goal = system.create(GoalRequest(objective=GoalType.ENERGY_REDUCTION, target_percent=15, priority=80), telemetry())

    assert goal.source == GoalSource.HUMAN
    assert goal.status == GoalStatus.ACCEPTED
    assert goal.assessment.expected_reduction_percent == 15


def test_goal_negotiation_marks_unrealistic_goal_for_negotiation():
    goal = AutonomousGoalManagementSystem().create(GoalRequest(objective=GoalType.ENERGY_REDUCTION, target_percent=50), telemetry(power_kw=2))

    assert goal.status == GoalStatus.NEGOTIATING
    assert not goal.assessment.feasible


def test_proactive_goal_responds_to_high_energy_demand():
    goal = AutonomousGoalManagementSystem().generate_proactive(telemetry(power_kw=9))

    assert goal is not None
    assert goal.source == GoalSource.AUTONOMOUS
    assert goal.request.objective == GoalType.ENERGY_REDUCTION
