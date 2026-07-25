"""Minimal closed-loop autonomous controller for real EnergyPlus cycles."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.config import get_settings
from app.schemas.telemetry import BuildingTelemetry, ComfortFeedback, OperatingPolicy, Setpoints
from app.services.control_gateway import apply_safe_setpoints
from app.services.decision_engine import POLICY_SETPOINTS
from app.services.self_healing import self_healing_loop
from app.services.policy_handoff import PolicyHandoffQueue, policy_handoff_queue
from app.simulation.state import BuildingState, building_state


@dataclass(slots=True)
class AutonomousControlStatus:
    cycles: int = 0
    active_policy: OperatingPolicy = OperatingPolicy.BALANCED
    comfort_pct: float = 100.0
    fallback_activated: bool = False
    last_action: str = "Waiting for telemetry"


class AutonomousControlLoop:
    """Telemetry → decision → safety gateway → next EnergyPlus cycle."""

    def __init__(self, state: BuildingState | None = None, handoffs: PolicyHandoffQueue | None = None) -> None:
        self._state = state or building_state
        self._handoffs = handoffs or policy_handoff_queue
        self._status = AutonomousControlStatus()
        self._lock = threading.RLock()

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
            policy = handoff.policy if handoff else (
                OperatingPolicy.ENERGY_SAVER if telemetry.power_kw >= settings.autonomous_power_threshold_kw else OperatingPolicy.BALANCED
            )
            proposal = POLICY_SETPOINTS[policy]
            result = apply_safe_setpoints(self._state, proposal, policy=policy)
            if result.accepted:
                self_healing_loop.register_applied_policy(policy, current)
                self._status.active_policy = policy
                self._status.fallback_activated = False
                self._status.last_action = (
                    f"LLM recommendation accepted by Safety Sentinel: {policy.value}. {handoff.rationale}"
                    if handoff else f"Autonomously selected {policy.value} from measured power {telemetry.power_kw:.2f} kW"
                )
            else:
                self._status.last_action = f"Safety Sentinel rejected {policy.value}: {'; '.join(result.reasons)}"
            return self.status()

    def status(self) -> AutonomousControlStatus:
        with self._lock:
            return AutonomousControlStatus(
                cycles=self._status.cycles,
                active_policy=self._status.active_policy,
                comfort_pct=self._status.comfort_pct,
                fallback_activated=self._status.fallback_activated,
                last_action=self._status.last_action,
            )


autonomous_control_loop = AutonomousControlLoop()
