"""Thread-safe handoff from slow LLM reasoning to the fast safety control loop."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.schemas.telemetry import OperatingPolicy


@dataclass(frozen=True, slots=True)
class PolicyHandoff:
    policy: OperatingPolicy
    rationale: str
    source: str = "ollama"


class PolicyHandoffQueue:
    """Retains only the newest supervisory recommendation for the next cycle."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pending: PolicyHandoff | None = None

    def publish(self, handoff: PolicyHandoff) -> None:
        with self._lock:
            self._pending = handoff

    def consume(self) -> PolicyHandoff | None:
        with self._lock:
            handoff = self._pending
            self._pending = None
            return handoff


policy_handoff_queue = PolicyHandoffQueue()
