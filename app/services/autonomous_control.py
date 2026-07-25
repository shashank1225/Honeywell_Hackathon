"""Minimal closed-loop autonomous controller for real EnergyPlus cycles."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.schemas.telemetry import AgentRecommendation, AutomationEpisode, BuildingTelemetry, ComfortFeedback, GoalType, OperatingPolicy, Setpoints, StrategicGoal
from app.services.control_gateway import apply_safe_setpoints
from app.services.counterfactual import CounterfactualAutomation, counterfactual_automation
from app.services.decision_engine import POLICY_SETPOINTS, DecisionEngine, decision_engine
from app.services.energy_efficiency import EnergyEfficiencyTracker, energy_efficiency_tracker
from app.services.goal_management import AutonomousGoalManagementSystem, goal_management_system
from app.services.self_healing import self_healing_loop
from app.services.automation_memory import AutomationMemory, automation_memory
from app.services.policy_handoff import PolicyHandoffQueue, policy_handoff_queue
from app.services.strategic_worker import StrategicWorkQueue, strategic_work_queue
from app.simulation.state import BuildingState, building_state


@dataclass(slots=True)
class AutonomousControlStatus:
    cycles: int = 0
    active_policy: OperatingPolicy = OperatingPolicy.BALANCED
    comfort_pct: float = 100.0
    fallback_activated: bool = False
    last_action: str = "Waiting for telemetry"
    decision_confidence: float = 0.0
    agent_recommendations: list[AgentRecommendation] = field(default_factory=list)
    active_goal: GoalType | None = None
    strategic_update: str = "No strategic goal is queued"


class AutonomousControlLoop:
    """Telemetry → decision → safety gateway → next EnergyPlus cycle."""

    def __init__(
        self,
        state: BuildingState | None = None,
        handoffs: PolicyHandoffQueue | None = None,
        engine: DecisionEngine | None = None,
        goals: AutonomousGoalManagementSystem | None = None,
        strategic_queue: StrategicWorkQueue | None = None,
        memory: AutomationMemory | None = None,
        energy_tracker: EnergyEfficiencyTracker | None = None,
        counterfactuals: CounterfactualAutomation | None = None,
    ) -> None:
        self._state = state or building_state
        self._handoffs = handoffs or policy_handoff_queue
        self._engine = engine or decision_engine
        self._goals = goals or goal_management_system
        self._strategic_queue = strategic_queue or strategic_work_queue
        self._memory = memory or automation_memory
        self._energy_tracker = energy_tracker or energy_efficiency_tracker
        self._counterfactuals = counterfactuals or counterfactual_automation
        self._status = AutonomousControlStatus()
        self._lock = threading.RLock()
        self._last_strategic_submission: datetime | None = None

    @staticmethod
    def comfort_score(telemetry: BuildingTelemetry) -> float:
        return round(max(0.0, 100.0 - abs(telemetry.temperature_c - 22.0) * 10.0 - max(0.0, telemetry.humidity_pct - 60.0)), 1)

    def process(self, telemetry: BuildingTelemetry) -> AutonomousControlStatus:
        settings = get_settings()
        if not settings.autonomous_control_enabled:
            return self.status()
        with self._lock:
            self._status.cycles += 1
            self._status.comfort_pct = self.comfort_score(telemetry)
            current = self._state.get_setpoints()
            self._record_observed_episode(telemetry, settings)
            self._queue_strategic_reasoning(telemetry, settings)
            if self._status.active_policy != OperatingPolicy.BALANCED and self._status.comfort_pct < settings.autonomous_min_comfort_pct:
                healing = self_healing_loop.evaluate(
                    ComfortFeedback(expected_comfort=95, actual_comfort=self._status.comfort_pct), current, telemetry
                )
                if healing.automatically_corrected:
                    result = apply_safe_setpoints(self._state, healing.active_setpoints, emergency=True)
                    if result.accepted:
                        self._status.active_policy = OperatingPolicy.COMFORT_FIRST
                        self._status.fallback_activated = True
                        self._status.last_action = "Comfort fallback activated after measured shortfall"
                        return self.status()

            handoff = self._handoffs.consume()
            decision = self._engine.decide(telemetry, policy_performance=self._memory.policy_performance())
            self._status.decision_confidence = decision.confidence
            self._status.agent_recommendations = [item.model_copy() for item in decision.recommendations]
            policy = handoff.policy if handoff else decision.selected_policy
            proposal = POLICY_SETPOINTS[policy]
            result = apply_safe_setpoints(self._state, proposal, policy=policy)
            if result.accepted:
                self_healing_loop.register_applied_policy(policy, current)
                self._status.active_policy = policy
                self._status.fallback_activated = False
                self._status.last_action = (
                    f"LLM recommendation accepted by Safety Sentinel: {policy.value}. {handoff.rationale}"
                    if handoff else (
                        f"Autonomously selected {policy.value} from Comfort, Energy, Occupancy, and Carbon agent arbitration."
                    )
                )
            else:
                if handoff and policy != OperatingPolicy.BALANCED:
                    fallback = apply_safe_setpoints(
                        self._state,
                        POLICY_SETPOINTS[OperatingPolicy.BALANCED],
                        policy=OperatingPolicy.BALANCED,
                    )
                    if fallback.accepted:
                        self._status.active_policy = OperatingPolicy.BALANCED
                        self._status.fallback_activated = True
                        self._status.last_action = (
                            f"Safety Sentinel rejected LLM policy {policy.value}; "
                            "safe balanced fallback activated."
                        )
                        return self.status()
                self._status.last_action = (
                    f"Safety Sentinel rejected {policy.value}; retaining last known safe setpoints. "
                    f"Reasons: {'; '.join(result.reasons)}"
                )
            return self.status()

    def _queue_strategic_reasoning(self, telemetry: BuildingTelemetry, settings) -> None:
        """Submit slow reasoning only for an active goal or a major transition.

        This path only queues work; agents and the Safety Sentinel still make
        the immediate telemetry-cycle decision locally and deterministically.
        """
        proactive = self._goals.generate_proactive(telemetry)
        goal = proactive or self._goals.active_goal()
        if goal is None:
            return
        self._status.active_goal = goal.request.objective
        now = datetime.now(UTC)
        interval_elapsed = self._last_strategic_submission is None or (
            now - self._last_strategic_submission >= timedelta(minutes=settings.strategic_interval_minutes)
        )
        if proactive is None and not interval_elapsed:
            return
        self._strategic_queue.submit(
            StrategicGoal(
                objective=goal.request.objective,
                target_percent=goal.request.target_percent,
                carbon_intensity_gco2_kwh=goal.request.carbon_intensity_gco2_kwh,
            )
        )
        self._last_strategic_submission = now
        origin = "Major telemetry transition generated" if proactive is not None else "Scheduled review queued for"
        self._status.strategic_update = f"{origin} {goal.request.objective.value.replace('_', ' ')} strategic goal."

    def _record_observed_episode(self, telemetry: BuildingTelemetry, settings) -> None:
        """Retain the measured outcome of the policy that was active this cycle."""
        report = self._energy_tracker.report()
        interval_hours = max(settings.simulation_interval_seconds, 0.0) / 3600.0
        baseline_power = report.baseline_power_kw or telemetry.power_kw
        baseline_energy = baseline_power * interval_hours
        actual_energy = telemetry.power_kw * interval_hours
        energy_component = max(-1.0, min(1.0, report.energy_savings_pct / 100.0))
        comfort_component = self._status.comfort_pct / 100.0
        reward = round(max(-1.0, min(1.0, 0.65 * comfort_component + 0.35 * energy_component)), 3)
        self._memory.record(
            AutomationEpisode(
                timestamp=telemetry.timestamp,
                policy=self._status.active_policy,
                reward=reward,
                energy_kwh=actual_energy,
                comfort_score=comfort_component,
                carbon_kg=actual_energy * 0.4,
                confidence=self._status.decision_confidence,
                baseline_energy_kwh=baseline_energy,
                energy_savings_pct=report.energy_savings_pct,
                temperature_c=telemetry.temperature_c,
                humidity_pct=telemetry.humidity_pct,
                occupancy_pct=telemetry.occupancy_pct,
                counterfactual=self._counterfactuals.evaluate(telemetry, self._status.active_policy),
            )
        )

    def status(self) -> AutonomousControlStatus:
        with self._lock:
            return AutonomousControlStatus(
                cycles=self._status.cycles,
                active_policy=self._status.active_policy,
                comfort_pct=self._status.comfort_pct,
                fallback_activated=self._status.fallback_activated,
                last_action=self._status.last_action,
                decision_confidence=self._status.decision_confidence,
                agent_recommendations=[item.model_copy() for item in self._status.agent_recommendations],
                active_goal=self._status.active_goal,
                strategic_update=self._status.strategic_update,
            )


autonomous_control_loop = AutonomousControlLoop()
