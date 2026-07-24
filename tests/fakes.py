from __future__ import annotations

import math
from datetime import datetime, timezone

from app.schemas.telemetry import BuildingTelemetry, Setpoints


class FakeEnergyPlusBackend:
    def __init__(self) -> None:
        self._setpoints = Setpoints()
        self._tick = 0
        self._latest: BuildingTelemetry | None = None

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def publish_setpoints(self, setpoints: Setpoints) -> None:
        self._setpoints = setpoints

    def wait_for_telemetry(self, timeout_seconds: float | None = None) -> BuildingTelemetry | None:
        _ = timeout_seconds
        self._tick += 1
        now = datetime.now(timezone.utc)
        occupancy_pct = max(0.0, min(100.0, 25.0 + 35.0 * math.sin(self._tick / 4.0)))
        temperature_c = 23.0 - (self._setpoints.hvac_temperature_c - 22.0) * 0.6 - self._tick * 0.08
        humidity_pct = max(0.0, min(100.0, 50.0 - self._setpoints.ventilation_rate_pct * 0.12 + self._tick * 0.04))
        power_kw = 4.5 + abs(temperature_c - self._setpoints.hvac_temperature_c) * 2.2 + self._setpoints.ventilation_rate_pct * 0.03
        self._latest = BuildingTelemetry(
            timestamp=now,
            zone="main",
            temperature_c=round(temperature_c, 2),
            humidity_pct=round(humidity_pct, 2),
            occupancy_pct=round(occupancy_pct, 2),
            power_kw=round(power_kw, 2),
        )
        return self._latest

    def latest_telemetry(self) -> BuildingTelemetry | None:
        return self._latest