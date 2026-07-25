"""Deterministic, non-actuating policy comparisons for AABOS explainability."""

from __future__ import annotations

from app.schemas.telemetry import (
    BuildingTelemetry,
    CounterfactualEvaluation,
    CounterfactualOutcome,
    OperatingPolicy,
)
from app.services.decision_engine import POLICY_SETPOINTS


class CounterfactualAutomation:
    """Project policy trade-offs from live telemetry without changing controls.

    These are transparent supervisory estimates, not simulated EnergyPlus
    results. The measured baseline-versus-controlled report remains the source
    of truth for realized savings.
    """

    _power_factors = {
        OperatingPolicy.BALANCED: 1.00,
        OperatingPolicy.ENERGY_SAVER: 0.86,
        OperatingPolicy.COMFORT_FIRST: 1.14,
        OperatingPolicy.CARBON_AWARE: 0.92,
    }

    @staticmethod
    def _comfort_score(temperature_c: float, humidity_pct: float) -> float:
        return max(0.0, min(100.0, 100.0 - abs(temperature_c - 22.0) * 10.0 - max(0.0, humidity_pct - 60.0)))

    def _outcome(
        self,
        telemetry: BuildingTelemetry,
        policy: OperatingPolicy,
        selected_power_kw: float,
        selected_comfort_pct: float,
    ) -> CounterfactualOutcome:
        setpoints = POLICY_SETPOINTS[policy]
        projected_temperature = telemetry.temperature_c + (setpoints.hvac_temperature_c - telemetry.temperature_c) * 0.35
        projected_humidity = max(0.0, telemetry.humidity_pct - (setpoints.ventilation_rate_pct - 50.0) * 0.08)
        projected_power = max(0.05, telemetry.power_kw * self._power_factors[policy])
        projected_comfort = self._comfort_score(projected_temperature, projected_humidity)
        energy_delta = (projected_power - selected_power_kw) / selected_power_kw * 100.0 if selected_power_kw else 0.0
        comfort_delta = projected_comfort - selected_comfort_pct
        return CounterfactualOutcome(
            policy=policy,
            projected_power_kw=round(projected_power, 2),
            projected_comfort_pct=round(projected_comfort, 1),
            energy_delta_pct=round(energy_delta, 1),
            comfort_delta_pct=round(comfort_delta, 1),
            rationale=(
                f"Projected from current {telemetry.power_kw:.2f} kW demand and "
                f"{telemetry.occupancy_pct:.0f}% occupancy; no control action was issued."
            ),
        )

    def evaluate(self, telemetry: BuildingTelemetry, selected_policy: OperatingPolicy) -> CounterfactualEvaluation:
        selected_setpoints = POLICY_SETPOINTS[selected_policy]
        selected_temperature = telemetry.temperature_c + (selected_setpoints.hvac_temperature_c - telemetry.temperature_c) * 0.35
        selected_humidity = max(0.0, telemetry.humidity_pct - (selected_setpoints.ventilation_rate_pct - 50.0) * 0.08)
        selected_power = max(0.05, telemetry.power_kw * self._power_factors[selected_policy])
        selected_comfort = self._comfort_score(selected_temperature, selected_humidity)
        selected = self._outcome(telemetry, selected_policy, selected_power, selected_comfort)
        alternatives = [
            self._outcome(telemetry, policy, selected_power, selected_comfort)
            for policy in OperatingPolicy
            if policy != selected_policy
        ]
        return CounterfactualEvaluation(
            timestamp=telemetry.timestamp,
            selected_policy=selected_policy,
            selected_outcome=selected,
            alternatives=alternatives,
            rationale="Counterfactual comparison is advisory only; the selected policy still requires Safety Sentinel validation.",
        )


counterfactual_automation = CounterfactualAutomation()
