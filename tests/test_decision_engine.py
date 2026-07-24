from datetime import UTC, datetime, timedelta

from app.schemas.telemetry import BuildingTelemetry, OperatingPolicy, Setpoints
from app.services.decision_engine import DecisionEngine
from app.services.safety_sentinel import SafetySentinel


def telemetry(**changes: float) -> BuildingTelemetry:
    values = {
        "timestamp": datetime.now(UTC),
        "temperature_c": 22.0,
        "humidity_pct": 45.0,
        "occupancy_pct": 50.0,
        "power_kw": 4.0,
    }
    values.update(changes)
    return BuildingTelemetry(**values)


def test_decision_engine_prefers_energy_saver_for_high_demand():
    result = DecisionEngine().decide(telemetry(power_kw=9.0))

    assert result.selected_policy == OperatingPolicy.ENERGY_SAVER
    assert result.proposed_setpoints.hvac_temperature_c == 24.0
    assert result.recommendations[1].agent == "energy"


def test_decision_engine_prefers_carbon_aware_for_dirty_grid():
    result = DecisionEngine().decide(telemetry(), carbon_intensity_gco2_kwh=650.0)

    assert result.selected_policy == OperatingPolicy.CARBON_AWARE


def test_safety_sentinel_rejects_large_step_and_oscillation():
    sentinel = SafetySentinel()
    current = Setpoints()
    now = datetime.now(UTC)

    rejected = sentinel.validate(current, Setpoints(hvac_temperature_c=25.0), now=now)
    accepted = sentinel.validate(current, Setpoints(hvac_temperature_c=23.0), now=now)
    oscillation = sentinel.validate(Setpoints(hvac_temperature_c=23.0), current, now=now + timedelta(minutes=1))

    assert not rejected.accepted
    assert accepted.accepted
    assert not oscillation.accepted
    assert "oscillation" in oscillation.reasons[0]
