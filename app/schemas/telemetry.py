from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

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
    lighting_level_pct: float = Field(default=100.0, ge=0.0, le=100.0)


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
    baseline_energy_kwh: float = Field(default=0.0, ge=0.0)
    energy_savings_pct: float = Field(default=0.0)
    temperature_c: float | None = None
    humidity_pct: float | None = None
    occupancy_pct: float | None = None
    counterfactual: "CounterfactualEvaluation | None" = None


class PolicyPerformance(BaseModel):
    """Explainable learned preference for a named operating policy."""

    policy: OperatingPolicy
    average_reward: float
    observations: int
    baseline_energy_kwh: float = 0.0
    actual_energy_kwh: float = 0.0
    energy_savings_pct: float = 0.0


class EnergySavingsReport(BaseModel):
    """Measured energy result compared with a captured balanced baseline."""

    baseline_power_kw: float | None = None
    baseline_energy_kwh: float = 0.0
    actual_energy_kwh: float = 0.0
    energy_savings_kwh: float = 0.0
    energy_savings_pct: float = 0.0
    samples: int = 0


class CounterfactualOutcome(BaseModel):
    """A non-actuating projected outcome for one operating policy."""

    policy: OperatingPolicy
    projected_power_kw: float = Field(ge=0.0)
    projected_comfort_pct: float = Field(ge=0.0, le=100.0)
    energy_delta_pct: float
    comfort_delta_pct: float
    rationale: str


class CounterfactualEvaluation(BaseModel):
    """Transparent policy comparison derived from the current telemetry state."""

    timestamp: datetime
    selected_policy: OperatingPolicy
    selected_outcome: CounterfactualOutcome
    alternatives: list[CounterfactualOutcome]
    rationale: str


class TelemetryWindowSummary(BaseModel):
    """Compact sliding-window context safe to pass to strategic reasoning."""

    samples: int
    window_start: datetime | None = None
    window_end: datetime | None = None
    average_temperature_c: float
    min_temperature_c: float
    max_temperature_c: float
    average_humidity_pct: float
    average_occupancy_pct: float
    average_power_kw: float
    peak_power_kw: float
    estimated_energy_kwh: float


class StrategicJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StrategicPlan(BaseModel):
    """A slow-loop recommendation which must still pass the Safety Sentinel."""

    goal: StrategicGoal
    selected_policy: OperatingPolicy
    confidence: float = Field(ge=0.0, le=1.0)
    proposed_setpoints: Setpoints
    explanation: list[str]
    policy_performance: list[PolicyPerformance]


class StrategicJob(BaseModel):
    """Asynchronous slow-loop job, isolated from real-time telemetry handling."""

    id: UUID = Field(default_factory=uuid4)
    goal: StrategicGoal
    status: StrategicJobStatus = StrategicJobStatus.QUEUED
    submitted_at: datetime
    completed_at: datetime | None = None
    plan: StrategicPlan | None = None
    error: str | None = None
    llm_used: bool = False
    llm_model: str | None = None
    deterministic_fallback_used: bool = False


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


class GoalSource(StrEnum):
    HUMAN = "human"
    AUTONOMOUS = "autonomous"


class GoalStatus(StrEnum):
    ACCEPTED = "accepted"
    NEGOTIATING = "negotiating"
    REJECTED = "rejected"


class GoalRequest(BaseModel):
    """Goal submitted by an operator or generated from operating conditions."""

    objective: GoalType
    target_percent: float = Field(default=10.0, ge=1.0, le=50.0)
    priority: int = Field(default=50, ge=1, le=100)
    carbon_intensity_gco2_kwh: float | None = Field(default=None, ge=0.0)


class GoalAssessment(BaseModel):
    """Feasibility and tradeoff evidence produced by goal negotiation."""

    feasible: bool
    expected_reduction_percent: float
    comfort_impact_percent: float
    carbon_impact_percent: float
    rationale: str


class ManagedGoal(BaseModel):
    """Prioritized goal held by the Autonomous Goal Management System."""

    id: UUID = Field(default_factory=uuid4)
    source: GoalSource
    status: GoalStatus
    request: GoalRequest
    assessment: GoalAssessment
    created_at: datetime
