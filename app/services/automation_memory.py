"""In-process automation memory and reward aggregation for Phase 4.

The service presents a small repository boundary so it can be backed by the
Phase 1 PostgreSQL store without changing strategic-reasoning callers.
"""

from __future__ import annotations

import threading

from app.schemas.telemetry import AutomationEpisode, OperatingPolicy, PolicyPerformance


class AutomationMemory:
    """Thread-safe experience store used by the adaptive policy engine."""

    def __init__(self, max_episodes: int = 500) -> None:
        self._max_episodes = max_episodes
        self._episodes: list[AutomationEpisode] = []
        self._lock = threading.RLock()

    def record(self, episode: AutomationEpisode) -> AutomationEpisode:
        with self._lock:
            self._episodes.append(episode.model_copy())
            if len(self._episodes) > self._max_episodes:
                self._episodes.pop(0)
        return episode

    def recent(self, limit: int = 50) -> list[AutomationEpisode]:
        with self._lock:
            return [episode.model_copy() for episode in self._episodes[-limit:]][::-1]

    def policy_performance(self) -> list[PolicyPerformance]:
        with self._lock:
            episodes = list(self._episodes)
        performance: list[PolicyPerformance] = []
        for policy in OperatingPolicy:
            rewards = [episode.reward for episode in episodes if episode.policy == policy]
            performance.append(
                PolicyPerformance(
                    policy=policy,
                    average_reward=round(sum(rewards) / len(rewards), 3) if rewards else 0.0,
                    observations=len(rewards),
                )
            )
        return sorted(performance, key=lambda item: (item.average_reward, item.observations), reverse=True)


automation_memory = AutomationMemory()
