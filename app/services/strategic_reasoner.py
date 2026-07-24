"""Slow-loop goal translation and explainable strategic planning."""

from __future__ import annotations

from app.schemas.telemetry import BuildingTelemetry, GoalType, OperatingPolicy, StrategicGoal, StrategicPlan
from app.services.adaptive_policy import AdaptivePolicyEvolutionEngine
from app.services.automation_memory import AutomationMemory, automation_memory
from app.services.decision_engine import POLICY_SETPOINTS, DecisionEngine, decision_engine


class StrategicReasoner:
    """Transforms goals into policies; it never applies actuator commands."""

    def __init__(self, memory: AutomationMemory | None = None, engine: DecisionEngine | None = None) -> None:
        self._memory = memory or automation_memory
        self._engine = engine or decision_engine

    def create_plan(self, goal: StrategicGoal, telemetry: BuildingTelemetry) -> StrategicPlan:
        decision = self._engine.decide(telemetry, goal.carbon_intensity_gco2_kwh)
        goal_policy = {
            GoalType.ENERGY_REDUCTION: OperatingPolicy.ENERGY_SAVER,
            GoalType.COMFORT: OperatingPolicy.COMFORT_FIRST,
            GoalType.CARBON_REDUCTION: OperatingPolicy.CARBON_AWARE,
        }[goal.objective]
        performance = self._memory.policy_performance()
        decision_adjustment = AdaptivePolicyEvolutionEngine.adjustment(decision.selected_policy, performance)
        goal_adjustment = AdaptivePolicyEvolutionEngine.adjustment(goal_policy, performance)

        # A clear requested goal starts with a small priority advantage. Learned
        # outcomes may break a close decision, but cannot overrule safety.
        selected_policy = goal_policy
        if decision.selected_policy != goal_policy and decision.confidence + decision_adjustment > 0.8 + goal_adjustment:
            selected_policy = decision.selected_policy

        confidence = decision.confidence if selected_policy == decision.selected_policy else 0.8
        explanation = [
            f"Translated {goal.objective.value.replace('_', ' ')} goal ({goal.target_percent:.0f}% target) into {selected_policy.value.replace('_', ' ')} policy.",
            *decision.rationale,
            "This is a supervisory recommendation; Phase 3 Safety Sentinel validation is required before any setpoint change.",
        ]
        observed = next(item for item in performance if item.policy == selected_policy)
        if observed.observations:
            explanation.append(
                f"Automation memory: {observed.observations} prior episodes average reward {observed.average_reward:.2f}."
            )

        return StrategicPlan(
            goal=goal,
            selected_policy=selected_policy,
            confidence=round(confidence, 2),
            proposed_setpoints=POLICY_SETPOINTS[selected_policy].model_copy(),
            explanation=explanation,
            policy_performance=performance,
        )


strategic_reasoner = StrategicReasoner()
