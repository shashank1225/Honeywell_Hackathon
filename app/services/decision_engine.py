"""Policy arbitration for AABOS Phase 3."""

from __future__ import annotations

from app.agents.specialized import CarbonAgent, ComfortAgent, EnergyAgent
from app.schemas.telemetry import (
    BuildingTelemetry,
    DecisionResult,
    OperatingPolicy,
    Setpoints,
)


POLICY_SETPOINTS: dict[OperatingPolicy, Setpoints] = {
    OperatingPolicy.BALANCED: Setpoints(hvac_temperature_c=22.0, ventilation_rate_pct=50.0),
    OperatingPolicy.ENERGY_SAVER: Setpoints(hvac_temperature_c=24.0, ventilation_rate_pct=35.0),
    OperatingPolicy.COMFORT_FIRST: Setpoints(hvac_temperature_c=22.0, ventilation_rate_pct=65.0),
    OperatingPolicy.CARBON_AWARE: Setpoints(hvac_temperature_c=23.5, ventilation_rate_pct=40.0),
}


class DecisionEngine:
    """Combines specialized recommendations into one explainable operating policy."""

    def __init__(self) -> None:
        self._comfort = ComfortAgent()
        self._energy = EnergyAgent()
        self._carbon = CarbonAgent()

    def decide(
        self,
        telemetry: BuildingTelemetry,
        carbon_intensity_gco2_kwh: float | None = None,
    ) -> DecisionResult:
        recommendations = [
            self._comfort.recommend(telemetry),
            self._energy.recommend(telemetry),
            self._carbon.recommend(telemetry, carbon_intensity_gco2_kwh),
        ]
        totals = {policy: 0.0 for policy in OperatingPolicy}
        for recommendation in recommendations:
            # "Balanced" is a fallback vote, not a competing optimization goal.
            # A material comfort, energy, or carbon concern must be able to
            # override several weak fallback recommendations.
            weight = 0.25 if recommendation.policy == OperatingPolicy.BALANCED else 1.0
            totals[recommendation.policy] += recommendation.score * weight

        selected_policy = max(totals, key=totals.__getitem__)
        winning_score = totals[selected_policy]
        confidence = min(1.0, 0.5 + winning_score / len(recommendations) / 2)
        rationale = [
            recommendation.rationale
            for recommendation in recommendations
            if recommendation.policy == selected_policy
        ]
        if not rationale:
            rationale = ["No condition dominates; retaining a balanced operating policy."]

        return DecisionResult(
            selected_policy=selected_policy,
            confidence=round(confidence, 2),
            rationale=rationale,
            recommendations=recommendations,
            proposed_setpoints=POLICY_SETPOINTS[selected_policy].model_copy(),
        )


decision_engine = DecisionEngine()
