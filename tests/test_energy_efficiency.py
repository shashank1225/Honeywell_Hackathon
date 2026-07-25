from datetime import UTC, datetime

from app.schemas.telemetry import BuildingTelemetry
from app.services.energy_efficiency import EnergyEfficiencyTracker


def sample(power_kw: float) -> BuildingTelemetry:
    return BuildingTelemetry(timestamp=datetime.now(UTC), temperature_c=22, humidity_pct=45, occupancy_pct=50, power_kw=power_kw)


def test_realized_savings_are_calculated_against_captured_baseline():
    tracker = EnergyEfficiencyTracker()
    tracker.capture_baseline(sample(10))
    tracker.record(sample(8), interval_seconds=3600)

    report = tracker.report()

    assert report.baseline_energy_kwh == 10
    assert report.actual_energy_kwh == 8
    assert report.energy_savings_kwh == 2
    assert report.energy_savings_pct == 20
