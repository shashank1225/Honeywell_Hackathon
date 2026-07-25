"""Policy arbitration for AABOS Phase 3."""

from __future__ import annotations

from app.agents.specialized import CarbonAgent, ComfortAgent, EnergyAgent, OccupancyAgent
from app.agents.mcp_context import MCPBuildingContext
from app.schemas.telemetry import (
    BuildingTelemetry,
    DecisionResult,
    OperatingPolicy,
    PolicyPerformance,
    Setpoints,
)
from app.services.adaptive_policy import AdaptivePolicyEvolutionEngine


POLICY_SETPOINTS: dict[OperatingPolicy, Setpoints] = {
    OperatingPolicy.BALANCED: Setpoints(hvac_temperature_c=22.0, ventilation_rate_pct=50.0, lighting_level_pct=100.0),
    OperatingPolicy.ENERGY_SAVER: Setpoints(hvac_temperature_c=24.0, ventilation_rate_pct=35.0, lighting_level_pct=70.0),
    OperatingPolicy.COMFORT_FIRST: Setpoints(hvac_temperature_c=22.0, ventilation_rate_pct=65.0, lighting_level_pct=100.0),
    OperatingPolicy.CARBON_AWARE: Setpoints(hvac_temperature_c=23.5, ventilation_rate_pct=40.0, lighting_level_pct=75.0),
}


class DecisionEngine:
    """Combines specialized recommendations into one explainable operating policy."""

    def __init__(self) -> None:
        self._comfort = ComfortAgent()
        self._energy = EnergyAgent()
        self._occupancy = OccupancyAgent()
        self._carbon = CarbonAgent()

    def decide(
        self,
        telemetry: BuildingTelemetry,
        carbon_intensity_gco2_kwh: float | None = None,
        policy_performance: list[PolicyPerformance] | None = None,
    ) -> DecisionResult:
        recommendations = [
            self._comfort.recommend(telemetry),
            self._energy.recommend(telemetry),
            self._occupancy.recommend(telemetry),
            self._carbon.recommend(telemetry, carbon_intensity_gco2_kwh),
        ]
        totals = {policy: 0.0 for policy in OperatingPolicy}
        for recommendation in recommendations:
            # "Balanced" is a fallback vote, not a competing optimization goal.
            # A material comfort, energy, or carbon concern must be able to
            # override several weak fallback recommendations.
            weight = 0.25 if recommendation.policy == OperatingPolicy.BALANCED else 1.0
            totals[recommendation.policy] += recommendation.score * weight
        for policy in OperatingPolicy:
            # Learning is deliberately bounded and only breaks close votes;
            # agent evidence and the Safety Sentinel remain authoritative.
            totals[policy] += AdaptivePolicyEvolutionEngine.adjustment(policy, policy_performance or [])

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

    def decide_from_mcp(
        self,
        context: MCPBuildingContext,
        carbon_intensity_gco2_kwh: float | None = None,
        policy_performance: list[PolicyPerformance] | None = None,
    ) -> DecisionResult:
        """Run the specialized agents from MCP-provided building context."""
        return self.decide(context.read_telemetry(), carbon_intensity_gco2_kwh, policy_performance)


decision_engine = DecisionEngine()
