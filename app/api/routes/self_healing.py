"""Feedback endpoint for deterministic self-correction."""

from fastapi import APIRouter, HTTPException

from app.schemas.telemetry import ComfortFeedback, SelfHealingStatus
from app.services.self_healing import self_healing_loop
from app.services.control_gateway import apply_safe_setpoints
from app.simulation.state import building_state

router = APIRouter(prefix="/self-healing", tags=["self-healing"])


@router.post("/evaluate", response_model=SelfHealingStatus)
def evaluate_comfort(feedback: ComfortFeedback) -> SelfHealingStatus:
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        raise HTTPException(status_code=409, detail="Telemetry is required before self-healing evaluation")
    current = building_state.get_setpoints()
    result = self_healing_loop.evaluate(feedback, current, telemetry)
    if result.automatically_corrected:
        gateway_result = apply_safe_setpoints(building_state, result.active_setpoints, emergency=True)
        if not gateway_result.accepted:
            result.automatically_corrected = False
            result.message = "Policy failure stored; automatic correction was blocked by the Safety Sentinel."
    return result
