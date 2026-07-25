"""Deterministic validation gateway for all supervisory setpoint proposals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.telemetry import SafetyValidationResult, Setpoints


class SafetySentinel:
    """Enforces hard HVAC limits and prevents rapid control oscillation."""

    max_temperature_step_c = 2.0
    max_ventilation_step_pct = 25.0
    min_change_interval = timedelta(minutes=5)

    def __init__(self) -> None:
        self._last_accepted_at: datetime | None = None

    def validate(
        self,
        current: Setpoints,
        proposed: Setpoints,
        *,
        now: datetime | None = None,
        emergency: bool = False,
    ) -> SafetyValidationResult:
        now = now or datetime.now(UTC)
        reasons: list[str] = []
        temperature_step = abs(proposed.hvac_temperature_c - current.hvac_temperature_c)
        ventilation_step = abs(proposed.ventilation_rate_pct - current.ventilation_rate_pct)
        if temperature_step > self.max_temperature_step_c:
            reasons.append(f"HVAC temperature change {temperature_step:.1f}°C exceeds {self.max_temperature_step_c:.1f}°C limit.")
        if ventilation_step > self.max_ventilation_step_pct:
            reasons.append(f"Ventilation change {ventilation_step:.1f}% exceeds {self.max_ventilation_step_pct:.1f}% limit.")
        if (
            self._last_accepted_at is not None
            and proposed != current
            and now - self._last_accepted_at < self.min_change_interval
            and not emergency
        ):
            reasons.append("Setpoint change rejected to prevent control oscillation.")
        if reasons:
            return SafetyValidationResult(accepted=False, reasons=reasons)

        if proposed != current:
            self._last_accepted_at = now
        return SafetyValidationResult(accepted=True, safe_setpoints=proposed.model_copy())


safety_sentinel = SafetySentinel()
