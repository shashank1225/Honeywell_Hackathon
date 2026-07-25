"""Autonomous Goal Management and goal-negotiation services for Phase 5."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from app.schemas.telemetry import (
    BuildingTelemetry,
    GoalAssessment,
    GoalRequest,
    GoalSource,
    GoalStatus,
    GoalType,
    ManagedGoal,
)


class GoalNegotiationEngine:
    """Estimates whether a requested objective is safe and achievable."""

    def assess(self, request: GoalRequest, telemetry: BuildingTelemetry) -> GoalAssessment:
        if request.objective == GoalType.ENERGY_REDUCTION:
            achievable = min(30.0, 8.0 + telemetry.power_kw * 3.0)
            comfort_impact = -min(8.0, max(0.0, request.target_percent - 10.0) * 0.35)
            carbon_impact = min(30.0, achievable * 0.9)
        elif request.objective == GoalType.CARBON_REDUCTION:
            achievable = min(28.0, 10.0 + telemetry.power_kw * 2.5)
            comfort_impact = -min(5.0, max(0.0, request.target_percent - 12.0) * 0.2)
            carbon_impact = achievable
        else:
            # Comfort goals target the portion of the discomfort gap that can
            # be corrected without leaving Phase 3 safety envelopes.
            discomfort = abs(telemetry.temperature_c - 22.0) * 12 + max(0.0, telemetry.humidity_pct - 60.0) * 0.5
            achievable = min(35.0, max(10.0, discomfort))
            comfort_impact = min(20.0, achievable * 0.6)
            carbon_impact = -min(10.0, achievable * 0.25)

        feasible = request.target_percent <= achievable
        rationale = (
            f"Requested {request.target_percent:.0f}% {request.objective.value.replace('_', ' ')}; "
            f"current telemetry supports approximately {achievable:.0f}% under active safety limits."
        )
        return GoalAssessment(
            feasible=feasible,
            expected_reduction_percent=round(min(request.target_percent, achievable), 1),
            comfort_impact_percent=round(comfort_impact, 1),
            carbon_impact_percent=round(carbon_impact, 1),
            rationale=rationale,
        )


class AutonomousGoalManagementSystem:
    """Creates, prioritizes, and retains negotiated operational goals."""

    def __init__(self, negotiator: GoalNegotiationEngine | None = None) -> None:
        self._negotiator = negotiator or GoalNegotiationEngine()
        self._goals: list[ManagedGoal] = []
        self._lock = threading.RLock()

    def create(self, request: GoalRequest, telemetry: BuildingTelemetry, source: GoalSource = GoalSource.HUMAN) -> ManagedGoal:
        assessment = self._negotiator.assess(request, telemetry)
        status = GoalStatus.ACCEPTED if assessment.feasible else GoalStatus.NEGOTIATING
        with self._lock:
            higher_priority = next(
                (
                    existing
                    for existing in self._goals
                    if existing.status == GoalStatus.ACCEPTED
                    and existing.request.objective != request.objective
                    and existing.request.priority > request.priority
                ),
                None,
            )
            if higher_priority is not None:
                status = GoalStatus.NEGOTIATING
                assessment = assessment.model_copy(
                    update={
                        "rationale": (
                            f"{assessment.rationale} Deferred behind higher-priority "
                            f"{higher_priority.request.objective.value.replace('_', ' ')} goal."
                        )
                    }
                )
            goal = ManagedGoal(source=source, status=status, request=request, assessment=assessment, created_at=datetime.now(UTC))
            self._goals.append(goal)
        return goal

    def generate_proactive(self, telemetry: BuildingTelemetry) -> ManagedGoal | None:
        if telemetry.power_kw >= 7.0:
            request = GoalRequest(objective=GoalType.ENERGY_REDUCTION, target_percent=15, priority=75)
        elif abs(telemetry.temperature_c - 22.0) >= 1.5 or telemetry.humidity_pct >= 65.0:
            request = GoalRequest(objective=GoalType.COMFORT, target_percent=12, priority=85)
        else:
            return None
        with self._lock:
            duplicate = next(
                (
                    goal
                    for goal in reversed(self._goals)
                    if goal.source == GoalSource.AUTONOMOUS
                    and goal.status == GoalStatus.ACCEPTED
                    and goal.request.objective == request.objective
                    and datetime.now(UTC) - goal.created_at < timedelta(minutes=30)
                ),
                None,
            )
        if duplicate is not None:
            return None
        return self.create(request, telemetry, source=GoalSource.AUTONOMOUS)

    def active_goal(self) -> ManagedGoal | None:
        """Return the highest-priority feasible goal for slow-loop reasoning."""
        with self._lock:
            accepted = [goal.model_copy() for goal in self._goals if goal.status == GoalStatus.ACCEPTED]
        if not accepted:
            return None
        return max(accepted, key=lambda goal: (goal.request.priority, goal.created_at))

    def list(self) -> list[ManagedGoal]:
        with self._lock:
            return sorted(
                (goal.model_copy() for goal in self._goals),
                key=lambda goal: (goal.request.priority, goal.created_at),
                reverse=True,
            )


goal_management_system = AutonomousGoalManagementSystem()
