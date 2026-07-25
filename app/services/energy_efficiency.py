"""Measured baseline-versus-actual energy accounting for APEE."""

from __future__ import annotations

import threading

from app.schemas.telemetry import BuildingTelemetry, EnergySavingsReport


class EnergyEfficiencyTracker:
    """Captures a balanced baseline then calculates realized policy savings."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._baseline_power_kw: float | None = None
        self._baseline_energy_kwh = 0.0
        self._actual_energy_kwh = 0.0
        self._samples = 0

    def capture_baseline(self, telemetry: BuildingTelemetry) -> EnergySavingsReport:
        with self._lock:
            self._baseline_power_kw = telemetry.power_kw
            self._baseline_energy_kwh = 0.0
            self._actual_energy_kwh = 0.0
            self._samples = 0
            return self.report()

    def record(self, telemetry: BuildingTelemetry, interval_seconds: float) -> EnergySavingsReport:
        with self._lock:
            if self._baseline_power_kw is None:
                self._baseline_power_kw = telemetry.power_kw
            interval_hours = max(interval_seconds, 0.0) / 3600.0
            self._baseline_energy_kwh += self._baseline_power_kw * interval_hours
            self._actual_energy_kwh += telemetry.power_kw * interval_hours
            self._samples += 1
            return self.report()

    def report(self) -> EnergySavingsReport:
        baseline = self._baseline_energy_kwh
        actual = self._actual_energy_kwh
        savings = baseline - actual
        return EnergySavingsReport(
            baseline_power_kw=self._baseline_power_kw,
            baseline_energy_kwh=round(baseline, 5),
            actual_energy_kwh=round(actual, 5),
            energy_savings_kwh=round(savings, 5),
            energy_savings_pct=round((savings / baseline * 100.0) if baseline else 0.0, 2),
            samples=self._samples,
        )


energy_efficiency_tracker = EnergyEfficiencyTracker()
