"""Asynchronous slow-loop worker for latency-isolated strategic reasoning."""

from __future__ import annotations

import queue
import threading
from datetime import UTC, datetime
from uuid import UUID

from app.config import get_settings
from app.schemas.telemetry import StrategicGoal, StrategicJob, StrategicJobStatus
from app.services.strategic_reasoner import strategic_reasoner
from app.services.ollama_client import OllamaStrategicClient, OllamaUnavailable
from app.services.policy_handoff import PolicyHandoff, policy_handoff_queue
from app.services.telemetry_aggregation import TelemetryWindowAggregator, telemetry_window_aggregator


class StrategicWorkQueue:
    """Runs strategic planning outside the real-time control event loop."""

    def __init__(self, aggregator: TelemetryWindowAggregator | None = None, llm_client: OllamaStrategicClient | None = None) -> None:
        self._aggregator = aggregator or telemetry_window_aggregator
        self._llm_client = llm_client or OllamaStrategicClient()
        self._jobs: dict[UUID, StrategicJob] = {}
        self._queue: queue.Queue[UUID] = queue.Queue()
        self._lock = threading.RLock()
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="aabos-strategic-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self._queue.put(None)  # type: ignore[arg-type]
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def submit(self, goal: StrategicGoal) -> StrategicJob:
        # Startup normally launches this worker in the FastAPI lifespan, but
        # submissions must remain self-healing if that worker was stopped or
        # a local reload raced the lifecycle hook.
        self.start()
        job = StrategicJob(goal=goal, submitted_at=datetime.now(UTC))
        with self._lock:
            self._jobs[job.id] = job
        self._queue.put(job.id)
        return job.model_copy()

    def get(self, job_id: UUID) -> StrategicJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy() if job else None

    def _run(self) -> None:
        while self._running.is_set():
            job_id = self._queue.get()
            if job_id is None:
                continue
            with self._lock:
                job = self._jobs[job_id]
                job.status = StrategicJobStatus.RUNNING
            try:
                summary = self._aggregator.summary()
                if summary.samples == 0:
                    raise RuntimeError("No aggregated telemetry is available")
                try:
                    recommendation = self._llm_client.recommend(job.goal, summary)
                    plan = strategic_reasoner.create_plan_from_summary(
                        job.goal, summary, llm_policy=recommendation.policy, llm_rationale=recommendation.rationale
                    )
                    llm_used = True
                    fallback_used = False
                    policy_handoff_queue.publish(PolicyHandoff(policy=recommendation.policy, rationale=recommendation.rationale))
                except OllamaUnavailable:
                    plan = strategic_reasoner.create_plan_from_summary(job.goal, summary)
                    llm_used = False
                    fallback_used = True
                with self._lock:
                    job.plan = plan
                    job.llm_used = llm_used
                    job.llm_model = get_settings().llm_model if llm_used else None
                    job.deterministic_fallback_used = fallback_used
                    job.status = StrategicJobStatus.COMPLETED
                    job.completed_at = datetime.now(UTC)
            except Exception as exc:
                with self._lock:
                    job.status = StrategicJobStatus.FAILED
                    job.error = str(exc)
                    job.completed_at = datetime.now(UTC)


strategic_work_queue = StrategicWorkQueue()
