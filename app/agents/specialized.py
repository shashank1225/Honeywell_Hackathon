"""Deterministic specialized agents used by the Phase 3 decision engine.

These agents are deliberately supervisory: they choose among named policies and
never issue actuator commands. The Safety Sentinel remains the sole gateway for
setpoint changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.telemetry import AgentRecommendation, BuildingTelemetry, OperatingPolicy


@dataclass(frozen=True, slots=True)
class ComfortAgent:
    name: str = "comfort"

    def recommend(self, telemetry: BuildingTelemetry) -> AgentRecommendation:
        temperature_error = abs(telemetry.temperature_c - 22.0)
        humidity_error = max(0.0, telemetry.humidity_pct - 60.0) / 40.0
        score = min(1.0, 0.45 + temperature_error / 4.0 + humidity_error)
        policy = OperatingPolicy.COMFORT_FIRST if score >= 0.65 else OperatingPolicy.BALANCED
        return AgentRecommendation(
            agent=self.name,
            policy=policy,
            score=round(score, 2),
            rationale=(
                f"Zone temperature is {telemetry.temperature_c:.1f}°C and humidity is "
                f"{telemetry.humidity_pct:.0f}%."
            ),
        )


@dataclass(frozen=True, slots=True)
class EnergyAgent:
    name: str = "energy"

    def recommend(self, telemetry: BuildingTelemetry) -> AgentRecommendation:
        score = min(1.0, max(0.0, telemetry.power_kw / 7.0))
        policy = OperatingPolicy.ENERGY_SAVER if telemetry.power_kw >= 3.5 else OperatingPolicy.BALANCED
        return AgentRecommendation(
            agent=self.name,
            policy=policy,
            score=round(score, 2),
            rationale=f"Current building demand is {telemetry.power_kw:.1f} kW.",
        )


@dataclass(frozen=True, slots=True)
class OccupancyAgent:
    """Matches operating intensity to the live occupancy signal."""

    name: str = "occupancy"

    def recommend(self, telemetry: BuildingTelemetry) -> AgentRecommendation:
        low_occupancy = telemetry.occupancy_pct <= 20.0
        score = min(1.0, max(0.0, (35.0 - telemetry.occupancy_pct) / 35.0))
        policy = OperatingPolicy.ENERGY_SAVER if low_occupancy else OperatingPolicy.BALANCED
        return AgentRecommendation(
            agent=self.name,
            policy=policy,
            score=round(score, 2),
            rationale=(
                f"Estimated occupancy is {telemetry.occupancy_pct:.0f}% "
                f"({'low demand supports setback' if low_occupancy else 'normal occupancy requires balanced service'})."
            ),
        )


@dataclass(frozen=True, slots=True)
class CarbonAgent:
    name: str = "carbon"

    def recommend(self, telemetry: BuildingTelemetry, carbon_intensity_gco2_kwh: float | None) -> AgentRecommendation:
        intensity = carbon_intensity_gco2_kwh if carbon_intensity_gco2_kwh is not None else 400.0
        score = min(1.0, max(0.0, intensity / 700.0))
        policy = OperatingPolicy.CARBON_AWARE if score >= 0.65 else OperatingPolicy.BALANCED
        source = "default grid estimate" if carbon_intensity_gco2_kwh is None else "provided grid signal"
        return AgentRecommendation(
            agent=self.name,
            policy=policy,
            score=round(score, 2),
            rationale=f"Carbon intensity is {intensity:.0f} gCO₂/kWh ({source}).",
        )
