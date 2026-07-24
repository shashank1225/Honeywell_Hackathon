from datetime import datetime

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
