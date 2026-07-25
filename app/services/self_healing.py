"""Feedback loop that rolls back failed policies and learns from the outcome."""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.telemetry import (
    AutomationEpisode,
    BuildingTelemetry,
    ComfortFeedback,
    OperatingPolicy,
    SelfHealingStatus,
    Setpoints,
)
from app.services.automation_memory import AutomationMemory, automation_memory
from app.services.safety_sentinel import SafetySentinel, safety_sentinel


class SelfHealingLoop:
    """Detects comfort prediction error and safely moves to a comfort fallback."""

    error_threshold = 5.0

    def __init__(self, memory: AutomationMemory | None = None, sentinel: SafetySentinel | None = None) -> None:
        self._memory = memory or automation_memory
        self._sentinel = sentinel or safety_sentinel
        self._active_policy = OperatingPolicy.BALANCED
        self._previous_setpoints = Setpoints()

    def register_applied_policy(self, policy: OperatingPolicy, previous_setpoints: Setpoints) -> None:
        self._active_policy = policy
        self._previous_setpoints = previous_setpoints.model_copy()

    def evaluate(
        self,
        feedback: ComfortFeedback,
        current_setpoints: Setpoints,
        telemetry: BuildingTelemetry,
    ) -> SelfHealingStatus:
        prediction_error = round(feedback.expected_comfort - feedback.actual_comfort, 2)
        if prediction_error <= self.error_threshold:
            return SelfHealingStatus(
                policy_failed=False,
                automatically_corrected=False,
                prediction_error=prediction_error,
                message="Comfort outcome is within the accepted prediction-error threshold.",
                active_setpoints=current_setpoints,
            )

        failed_policy = self._active_policy
        self._memory.record(AutomationEpisode(
            timestamp=datetime.now(UTC),
            policy=failed_policy,
            reward=max(-1.0, -prediction_error / 100.0),
            energy_kwh=telemetry.power_kw,
            comfort_score=feedback.actual_comfort / 100.0,
            carbon_kg=telemetry.power_kw * feedback.carbon_intensity_gco2_kwh / 1000.0,
            confidence=0.0,
        ))
        # Move toward the previous safe state while maintaining a comfort-first
        # correction. The bounded change is always checked by the sentinel.
        fallback = Setpoints(
            hvac_temperature_c=min(22.0, max(16.0, current_setpoints.hvac_temperature_c - 2.0)),
            ventilation_rate_pct=min(100.0, current_setpoints.ventilation_rate_pct + 25.0),
        )
        validation = self._sentinel.validate(current_setpoints, fallback, emergency=True)
        if validation.accepted and validation.safe_setpoints is not None:
            self._previous_setpoints = current_setpoints.model_copy()
            self._active_policy = OperatingPolicy.COMFORT_FIRST
            return SelfHealingStatus(
                policy_failed=True,
                automatically_corrected=True,
                fallback_policy=OperatingPolicy.COMFORT_FIRST,
                prediction_error=prediction_error,
                message="Policy failed: automatically corrected; comfort-first fallback activated and failure stored.",
                active_setpoints=validation.safe_setpoints,
            )

        return SelfHealingStatus(
            policy_failed=True,
            automatically_corrected=False,
            prediction_error=prediction_error,
            message="Policy failure stored; automatic correction was blocked by the Safety Sentinel.",
            active_setpoints=current_setpoints,
        )


self_healing_loop = SelfHealingLoop()
