import asyncio
import threading
from collections.abc import AsyncIterator
from datetime import datetime

from app.schemas.telemetry import BuildingTelemetry, Setpoints

DEFAULT_SETPOINTS = Setpoints()


class BuildingState:
    """Thread-safe in-memory store shared by the simulator, API, and MCP server."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._setpoints = DEFAULT_SETPOINTS.model_copy()
        self._latest_telemetry: BuildingTelemetry | None = None
        self._subscribers: list[asyncio.Queue[BuildingTelemetry]] = []

    def get_setpoints(self) -> Setpoints:
        with self._lock:
            return self._setpoints.model_copy()

    def update_setpoints(self, **kwargs: float) -> Setpoints:
        with self._lock:
            self._setpoints = self._setpoints.model_copy(update=kwargs)
            return self._setpoints.model_copy()

    def get_latest_telemetry(self) -> BuildingTelemetry | None:
        with self._lock:
            if self._latest_telemetry is None:
                return None
            return self._latest_telemetry.model_copy()

    def publish_telemetry(self, telemetry: BuildingTelemetry) -> None:
        with self._lock:
            self._latest_telemetry = telemetry
            subscribers = list(self._subscribers)

        for queue in subscribers:
            try:
                queue.put_nowait(telemetry)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue[BuildingTelemetry]:
        queue: asyncio.Queue[BuildingTelemetry] = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[BuildingTelemetry]) -> None:
        with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    async def telemetry_stream(self) -> AsyncIterator[BuildingTelemetry]:
        queue = self.subscribe()
        try:
            latest = self.get_latest_telemetry()
            if latest is not None:
                yield latest
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(queue)


building_state = BuildingState()
