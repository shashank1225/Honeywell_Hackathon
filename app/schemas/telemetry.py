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
