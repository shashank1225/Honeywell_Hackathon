"""Deterministic validation gateway for all supervisory setpoint proposals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.telemetry import SafetyValidationResult, Setpoints


class SafetySentinel:
    """Enforces hard HVAC limits and prevents rapid control oscillation."""

    max_temperature_step_c = 2.0
    max_ventilation_step_pct = 25.0
    max_lighting_step_pct = 30.0
    min_change_interval = timedelta(minutes=5)

    def __init__(self) -> None:
        self._last_accepted_at: datetime | None = None
        self._last_temperature_delta = 0.0
        self._last_ventilation_delta = 0.0
        self._last_lighting_delta = 0.0

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
        lighting_step = abs(proposed.lighting_level_pct - current.lighting_level_pct)
        if temperature_step > self.max_temperature_step_c:
            reasons.append(f"HVAC temperature change {temperature_step:.1f}°C exceeds {self.max_temperature_step_c:.1f}°C limit.")
        if ventilation_step > self.max_ventilation_step_pct:
            reasons.append(f"Ventilation change {ventilation_step:.1f}% exceeds {self.max_ventilation_step_pct:.1f}% limit.")
        if lighting_step > self.max_lighting_step_pct:
            reasons.append(f"Lighting change {lighting_step:.1f}% exceeds {self.max_lighting_step_pct:.1f}% limit.")
        temperature_delta = proposed.hvac_temperature_c - current.hvac_temperature_c
        ventilation_delta = proposed.ventilation_rate_pct - current.ventilation_rate_pct
        lighting_delta = proposed.lighting_level_pct - current.lighting_level_pct
        reverses_a_recent_change = self._reverses_recent_change(temperature_delta, ventilation_delta, lighting_delta)
        if (
            self._last_accepted_at is not None
            and proposed != current
            and now - self._last_accepted_at < self.min_change_interval
            and not emergency
            and reverses_a_recent_change
        ):
            reasons.append("Setpoint change rejected to prevent control oscillation.")
        if reasons:
            return SafetyValidationResult(accepted=False, reasons=reasons)

        if proposed != current:
            self._last_accepted_at = now
            self._last_temperature_delta = temperature_delta
            self._last_ventilation_delta = ventilation_delta
            self._last_lighting_delta = lighting_delta
        return SafetyValidationResult(accepted=True, safe_setpoints=proposed.model_copy())

    def _reverses_recent_change(self, temperature_delta: float, ventilation_delta: float, lighting_delta: float) -> bool:
        temperature_reversal = temperature_delta * self._last_temperature_delta < 0
        ventilation_reversal = ventilation_delta * self._last_ventilation_delta < 0
        lighting_reversal = lighting_delta * self._last_lighting_delta < 0
        return temperature_reversal or ventilation_reversal or lighting_reversal


safety_sentinel = SafetySentinel()
