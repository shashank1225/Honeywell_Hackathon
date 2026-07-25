"""Read-only counterfactual evidence for the active autonomous policy."""

from fastapi import APIRouter, HTTPException

from app.services.autonomous_control import autonomous_control_loop
from app.services.counterfactual import counterfactual_automation
from app.simulation.state import building_state

router = APIRouter(prefix="/counterfactuals", tags=["counterfactuals"])


@router.get("/current")
def current_counterfactual():
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        raise HTTPException(status_code=409, detail="Telemetry is required for counterfactual evaluation")
    policy = autonomous_control_loop.status().active_policy
    return counterfactual_automation.evaluate(telemetry, policy)
