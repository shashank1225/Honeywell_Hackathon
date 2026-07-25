from datetime import UTC, datetime, timedelta

from app.schemas.telemetry import BuildingTelemetry
from app.services.telemetry_aggregation import TelemetryWindowAggregator


def reading(power_kw: float, temperature_c: float, second: int) -> BuildingTelemetry:
    return BuildingTelemetry(
        timestamp=datetime.now(UTC) + timedelta(seconds=second), temperature_c=temperature_c,
        humidity_pct=45, occupancy_pct=50, power_kw=power_kw,
    )


def test_sliding_window_retains_only_recent_aggregated_telemetry():
    aggregator = TelemetryWindowAggregator(max_samples=2)
    aggregator.add(reading(10, 20, 0))
    aggregator.add(reading(8, 22, 1))
    aggregator.add(reading(6, 24, 2))

    summary = aggregator.summary(interval_seconds=3600)

    assert summary.samples == 2
    assert summary.average_power_kw == 7
    assert summary.min_temperature_c == 22
    assert summary.max_temperature_c == 24
    assert summary.estimated_energy_kwh == 14
