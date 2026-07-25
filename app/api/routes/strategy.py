"""Phase 4 strategic planning and adaptive policy-memory endpoints."""

from fastapi import APIRouter, HTTPException, Query
from uuid import UUID

from app.schemas.telemetry import AutomationEpisode, PolicyPerformance, StrategicGoal, StrategicJob, StrategicPlan
from app.services.automation_memory import automation_memory
from app.services.strategic_reasoner import strategic_reasoner
from app.services.strategic_worker import strategic_work_queue
from app.simulation.state import building_state

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.post("/plan", response_model=StrategicPlan)
def create_strategic_plan(goal: StrategicGoal) -> StrategicPlan:
    """Create an explainable, non-actuating slow-loop plan for a goal."""
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        raise HTTPException(status_code=409, detail="Telemetry is required before strategic planning")
    return strategic_reasoner.create_plan(goal, telemetry)


@router.post("/jobs", response_model=StrategicJob, status_code=202)
def enqueue_strategic_plan(goal: StrategicGoal) -> StrategicJob:
    """Queue slow strategic work so prompt latency cannot block control."""
    if building_state.get_latest_telemetry() is None:
        raise HTTPException(status_code=409, detail="Telemetry is required before strategic planning")
    return strategic_work_queue.submit(goal)


@router.get("/jobs/{job_id}", response_model=StrategicJob)
def get_strategic_job(job_id: UUID) -> StrategicJob:
    job = strategic_work_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Strategic job not found")
    return job


@router.post("/episodes", response_model=AutomationEpisode, status_code=201)
def record_episode(episode: AutomationEpisode) -> AutomationEpisode:
    """Record an observed outcome for adaptive policy evolution."""
    return automation_memory.record(episode)


@router.get("/episodes", response_model=list[AutomationEpisode])
def list_episodes(limit: int = Query(default=50, ge=1, le=500)) -> list[AutomationEpisode]:
    return automation_memory.recent(limit)


@router.get("/policies", response_model=list[PolicyPerformance])
def policy_performance() -> list[PolicyPerformance]:
    return automation_memory.policy_performance()
