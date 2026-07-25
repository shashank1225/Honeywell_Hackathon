"""Bounded rolling telemetry aggregation for Kafka and strategic context."""

from __future__ import annotations

import threading
from collections import deque

from app.config import get_settings
from app.schemas.telemetry import BuildingTelemetry, TelemetryWindowSummary


class TelemetryWindowAggregator:
    """Maintains a fixed-size sliding window instead of retaining raw logs."""

    def __init__(self, max_samples: int | None = None) -> None:
        self._max_samples = max_samples or get_settings().telemetry_window_samples
        self._samples: deque[BuildingTelemetry] = deque(maxlen=self._max_samples)
        self._lock = threading.RLock()

    def add(self, telemetry: BuildingTelemetry) -> None:
        with self._lock:
            self._samples.append(telemetry.model_copy())

    def summary(self, interval_seconds: float | None = None) -> TelemetryWindowSummary:
        with self._lock:
            samples = list(self._samples)
        if not samples:
            return TelemetryWindowSummary(
                samples=0, average_temperature_c=0, min_temperature_c=0, max_temperature_c=0,
                average_humidity_pct=0, average_occupancy_pct=0, average_power_kw=0,
                peak_power_kw=0, estimated_energy_kwh=0,
            )
        count = len(samples)
        interval_hours = (interval_seconds or get_settings().simulation_interval_seconds) / 3600.0
        return TelemetryWindowSummary(
            samples=count,
            window_start=samples[0].timestamp,
            window_end=samples[-1].timestamp,
            average_temperature_c=round(sum(item.temperature_c for item in samples) / count, 2),
            min_temperature_c=min(item.temperature_c for item in samples),
            max_temperature_c=max(item.temperature_c for item in samples),
            average_humidity_pct=round(sum(item.humidity_pct for item in samples) / count, 2),
            average_occupancy_pct=round(sum(item.occupancy_pct for item in samples) / count, 2),
            average_power_kw=round(sum(item.power_kw for item in samples) / count, 3),
            peak_power_kw=max(item.power_kw for item in samples),
            estimated_energy_kwh=round(sum(item.power_kw for item in samples) * interval_hours, 5),
        )


telemetry_window_aggregator = TelemetryWindowAggregator()
