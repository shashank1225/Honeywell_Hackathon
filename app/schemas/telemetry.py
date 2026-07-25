from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class BuildingTelemetry(BaseModel):
    """Snapshot of simulated building sensor readings."""

    timestamp: datetime
    zone: str = "main"
    temperature_c: float = Field(description="Zone air temperature in Celsius")
    humidity_pct: float = Field(description="Relative humidity percentage")
    occupancy_pct: float = Field(description="Estimated zone occupancy percentage")
    power_kw: float = Field(description="Total HVAC and plug load in kilowatts")


class Setpoints(BaseModel):
    """Operator or MCP-requested HVAC control targets."""

    hvac_temperature_c: float = Field(default=22.0, ge=16.0, le=30.0)
    ventilation_rate_pct: float = Field(default=50.0, ge=0.0, le=100.0)


class OperatingPolicy(StrEnum):
    """High-level operating modes selected by the Phase 3 decision engine."""

    BALANCED = "balanced"
    ENERGY_SAVER = "energy_saver"
    COMFORT_FIRST = "comfort_first"
    CARBON_AWARE = "carbon_aware"


class AgentRecommendation(BaseModel):
    """A policy preference supplied by one specialized supervisory agent."""

    agent: str
    policy: OperatingPolicy
    score: float = Field(ge=0.0, le=1.0)
    rationale: str


class DecisionRequest(BaseModel):
    """Optional context for a policy recommendation."""

    carbon_intensity_gco2_kwh: float | None = Field(default=None, ge=0.0)


class DecisionResult(BaseModel):
    """A transparent policy decision and its safe proposed setpoints."""

    selected_policy: OperatingPolicy
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: list[str]
    recommendations: list[AgentRecommendation]
    proposed_setpoints: Setpoints


class SafetyValidationResult(BaseModel):
    """The deterministic outcome of validating a requested setpoint change."""

    accepted: bool
    reasons: list[str] = []
    safe_setpoints: Setpoints | None = None


class GoalType(StrEnum):
    """Strategic objectives that can be translated into operating policies."""

    ENERGY_REDUCTION = "energy_reduction"
    COMFORT = "comfort"
    CARBON_REDUCTION = "carbon_reduction"


class StrategicGoal(BaseModel):
    """A human or autonomous objective for the slow strategic loop."""

    objective: GoalType
    target_percent: float = Field(default=10.0, ge=1.0, le=50.0)
    carbon_intensity_gco2_kwh: float | None = Field(default=None, ge=0.0)


class AutomationEpisode(BaseModel):
    """Observed outcome retained as experience for future policy selection."""

    timestamp: datetime
    policy: OperatingPolicy
    reward: float = Field(ge=-1.0, le=1.0)
    energy_kwh: float = Field(ge=0.0)
    comfort_score: float = Field(ge=0.0, le=1.0)
    carbon_kg: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)


class PolicyPerformance(BaseModel):
    """Explainable learned preference for a named operating policy."""

    policy: OperatingPolicy
    average_reward: float
    observations: int


class StrategicPlan(BaseModel):
    """A slow-loop recommendation which must still pass the Safety Sentinel."""

    goal: StrategicGoal
    selected_policy: OperatingPolicy
    confidence: float = Field(ge=0.0, le=1.0)
    proposed_setpoints: Setpoints
    explanation: list[str]
    policy_performance: list[PolicyPerformance]


class ComfortFeedback(BaseModel):
    """Expected versus observed comfort supplied to the self-healing loop."""

    expected_comfort: float = Field(ge=0.0, le=100.0)
    actual_comfort: float = Field(ge=0.0, le=100.0)
    carbon_intensity_gco2_kwh: float = Field(default=400.0, ge=0.0)


class SelfHealingStatus(BaseModel):
    """Explainable outcome of a feedback-driven automatic correction."""

    policy_failed: bool
    automatically_corrected: bool
    fallback_policy: OperatingPolicy | None = None
    prediction_error: float
    message: str
    active_setpoints: Setpoints
