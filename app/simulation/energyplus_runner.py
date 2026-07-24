"""
EnergyPlus simulation wrapper.

Phase 2 uses a deterministic mock loop that mimics EnergyPlus telemetry output.
When a real EnergyPlus IDF is available, replace `_simulate_tick` with EP API calls
while keeping the same `BuildingTelemetry` contract and Kafka publishing path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime, timezone

from app.config import get_settings
from app.kafka.client import get_kafka_producer
from app.schemas.telemetry import BuildingTelemetry, Setpoints
from app.simulation.state import BuildingState, building_state

logger = logging.getLogger(__name__)


class EnergyPlusRunner:
    """Mock EnergyPlus runner that emits building telemetry on a fixed interval."""

    def __init__(
        self,
        state: BuildingState | None = None,
        interval_seconds: float | None = None,
        zone: str = "main",
    ) -> None:
        settings = get_settings()
        self._state = state or building_state
        self._interval_seconds = interval_seconds or settings.simulation_interval_seconds
        self._zone = zone
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._tick = 0
        self._temperature_c = 22.0
        self._humidity_pct = 45.0

    @property
    def is_running(self) -> bool:
        return self._running

    def _occupancy_profile(self, hour: float) -> float:
        """Simple weekday occupancy curve peaking during business hours."""
        return max(0.0, min(100.0, 20.0 + 80.0 * math.exp(-0.5 * ((hour - 14.0) / 4.0) ** 2)))

    def _simulate_tick(self, setpoints: Setpoints) -> BuildingTelemetry:
        """Deterministic mock physics — drifts zone state toward active setpoints."""
        now = datetime.now(timezone.utc)
        hour = now.hour + now.minute / 60.0
        self._tick += 1

        temp_delta = (setpoints.hvac_temperature_c - self._temperature_c) * 0.15
        self._temperature_c += temp_delta

        target_humidity = 55.0 - (setpoints.ventilation_rate_pct * 0.15)
        self._humidity_pct += (target_humidity - self._humidity_pct) * 0.1

        occupancy_pct = self._occupancy_profile(hour)
        hvac_load_kw = abs(self._temperature_c - setpoints.hvac_temperature_c) * 2.5
        ventilation_load_kw = setpoints.ventilation_rate_pct * 0.03
        occupancy_load_kw = occupancy_pct * 0.02
        power_kw = 5.0 + hvac_load_kw + ventilation_load_kw + occupancy_load_kw

        return BuildingTelemetry(
            timestamp=now,
            zone=self._zone,
            temperature_c=round(self._temperature_c, 2),
            humidity_pct=round(self._humidity_pct, 2),
            occupancy_pct=round(occupancy_pct, 2),
            power_kw=round(power_kw, 2),
        )

    def tick_once(self) -> BuildingTelemetry:
        """Generate one telemetry sample and publish it to shared state and Kafka."""
        setpoints = self._state.get_setpoints()
        telemetry = self._simulate_tick(setpoints)
        self._state.publish_telemetry(telemetry)
        self._publish_to_kafka(telemetry)
        return telemetry

    def _publish_to_kafka(self, telemetry: BuildingTelemetry) -> None:
        settings = get_settings()
        producer = get_kafka_producer()
        if producer is None:
            return

        payload = json.dumps(telemetry.model_dump(mode="json"))
        producer.send(settings.kafka_telemetry_topic, payload)
        producer.flush(timeout=1)

    async def run_loop(self) -> None:
        """Background loop used by FastAPI lifespan startup."""
        self._running = True
        logger.info(
            "EnergyPlus mock simulation started (interval=%ss, zone=%s)",
            self._interval_seconds,
            self._zone,
        )
        try:
            while self._running:
                self.tick_once()
                await asyncio.sleep(self._interval_seconds)
        finally:
            logger.info("EnergyPlus mock simulation stopped")

    async def start(self) -> None:
        if self._running:
            return
        self._task = asyncio.create_task(self.run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            await self._task
            self._task = None


_runner: EnergyPlusRunner | None = None


def get_energyplus_runner() -> EnergyPlusRunner:
    global _runner
    if _runner is None:
        _runner = EnergyPlusRunner()
    return _runner
