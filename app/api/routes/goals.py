"""Phase 5 goal creation, negotiation, and proactive-goal endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.telemetry import GoalRequest, GoalSource, ManagedGoal
from app.services.goal_management import goal_management_system
from app.simulation.state import building_state

router = APIRouter(prefix="/goals", tags=["goals"])


def _telemetry_or_409():
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        raise HTTPException(status_code=409, detail="Telemetry is required for goal negotiation")
    return telemetry


@router.post("", response_model=ManagedGoal, status_code=201)
def create_goal(request: GoalRequest) -> ManagedGoal:
    return goal_management_system.create(request, _telemetry_or_409(), source=GoalSource.HUMAN)


@router.post("/proactive", response_model=ManagedGoal | None)
def generate_proactive_goal() -> ManagedGoal | None:
    return goal_management_system.generate_proactive(_telemetry_or_409())


@router.get("", response_model=list[ManagedGoal])
def list_goals() -> list[ManagedGoal]:
    return goal_management_system.list()
