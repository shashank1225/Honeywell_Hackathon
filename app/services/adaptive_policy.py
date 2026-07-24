"""RL-inspired supervisory policy preference evolution."""

from __future__ import annotations

from app.schemas.telemetry import OperatingPolicy, PolicyPerformance


class AdaptivePolicyEvolutionEngine:
    """Applies learned episode rewards as a bounded tie-breaker for policies."""

    max_learning_adjustment = 0.15

    @classmethod
    def adjustment(cls, policy: OperatingPolicy, performance: list[PolicyPerformance]) -> float:
        observed = next((item for item in performance if item.policy == policy), None)
        if observed is None or observed.observations == 0:
            return 0.0
        # More samples increase trust; rewards remain bounded so safety and
        # real-time telemetry always dominate learned preference.
        sample_weight = min(1.0, observed.observations / 20.0)
        return round(observed.average_reward * sample_weight * cls.max_learning_adjustment, 3)
