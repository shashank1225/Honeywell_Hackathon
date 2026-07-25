"""In-process automation memory and reward aggregation for Phase 4.

The service presents a small repository boundary so it can be backed by the
Phase 1 PostgreSQL store without changing strategic-reasoning callers.
"""

from __future__ import annotations

import logging
import queue
import threading

from sqlalchemy import select

from app.database import Base, get_engine, get_session_factory
from app.models.automation_episode import AutomationEpisodeRecord
from app.schemas.telemetry import AutomationEpisode, OperatingPolicy, PolicyPerformance

logger = logging.getLogger(__name__)


class AutomationMemory:
    """Thread-safe experience store with asynchronous durable persistence."""

    def __init__(self, max_episodes: int = 500, persist_to_database: bool = False) -> None:
        self._max_episodes = max_episodes
        self._episodes: list[AutomationEpisode] = []
        self._lock = threading.RLock()
        self._persist_to_database = persist_to_database
        self._persistence_queue: queue.Queue[AutomationEpisode | None] = queue.Queue()
        self._persistence_running = threading.Event()
        self._persistence_thread: threading.Thread | None = None
        self._database_available = False

    def start(self) -> None:
        """Initialize PostgreSQL once and persist future writes off the control path."""
        if not self._persist_to_database or self._persistence_thread is not None:
            return
        try:
            Base.metadata.create_all(bind=get_engine(), tables=[AutomationEpisodeRecord.__table__])
            self._hydrate_from_database()
            self._database_available = True
        except Exception as exc:
            # Local development and safe control must still work without a DB.
            logger.warning("Automation Memory persistence unavailable; using in-memory history: %s", exc)
            self._database_available = False
            return
        self._persistence_running.set()
        self._persistence_thread = threading.Thread(
            target=self._persist_loop,
            name="aabos-automation-memory",
            daemon=True,
        )
        self._persistence_thread.start()

    def stop(self) -> None:
        self._persistence_running.clear()
        self._persistence_queue.put(None)
        if self._persistence_thread is not None:
            self._persistence_thread.join(timeout=2)
            self._persistence_thread = None

    def _hydrate_from_database(self) -> None:
        session = get_session_factory()()
        try:
            records = session.scalars(
                select(AutomationEpisodeRecord)
                .order_by(AutomationEpisodeRecord.id.desc())
                .limit(self._max_episodes)
            ).all()
            restored = [AutomationEpisode.model_validate(record.payload) for record in reversed(records)]
            with self._lock:
                self._episodes = restored
        finally:
            session.close()

    def _persist_loop(self) -> None:
        while self._persistence_running.is_set():
            episode = self._persistence_queue.get()
            if episode is None:
                continue
            session = get_session_factory()()
            try:
                session.add(
                    AutomationEpisodeRecord(
                        timestamp=episode.timestamp,
                        policy=episode.policy.value,
                        reward=episode.reward,
                        energy_kwh=episode.energy_kwh,
                        comfort_score=episode.comfort_score,
                        confidence=episode.confidence,
                        payload=episode.model_dump(mode="json"),
                    )
                )
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.warning("Unable to persist Automation Memory episode: %s", exc)
            finally:
                session.close()

    def record(self, episode: AutomationEpisode) -> AutomationEpisode:
        with self._lock:
            self._episodes.append(episode.model_copy())
            if len(self._episodes) > self._max_episodes:
                self._episodes.pop(0)
        if self._database_available:
            self._persistence_queue.put(episode.model_copy())
        return episode

    def recent(self, limit: int = 50) -> list[AutomationEpisode]:
        with self._lock:
            return [episode.model_copy() for episode in self._episodes[-limit:]][::-1]

    def policy_performance(self) -> list[PolicyPerformance]:
        with self._lock:
            episodes = list(self._episodes)
        performance: list[PolicyPerformance] = []
        for policy in OperatingPolicy:
            policy_episodes = [episode for episode in episodes if episode.policy == policy]
            rewards = [episode.reward for episode in policy_episodes]
            baseline_energy = sum(episode.baseline_energy_kwh for episode in policy_episodes)
            actual_energy = sum(episode.energy_kwh for episode in policy_episodes)
            savings_pct = ((baseline_energy - actual_energy) / baseline_energy * 100.0) if baseline_energy else 0.0
            performance.append(
                PolicyPerformance(
                    policy=policy,
                    average_reward=round(sum(rewards) / len(rewards), 3) if rewards else 0.0,
                    observations=len(rewards),
                    baseline_energy_kwh=round(baseline_energy, 5),
                    actual_energy_kwh=round(actual_energy, 5),
                    energy_savings_pct=round(savings_pct, 2),
                )
            )
        return sorted(performance, key=lambda item: (item.average_reward, item.observations), reverse=True)


automation_memory = AutomationMemory(persist_to_database=True)
