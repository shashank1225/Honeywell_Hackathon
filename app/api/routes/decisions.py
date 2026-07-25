"""Phase 3 policy decision and safety-validated application endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.telemetry import DecisionRequest, DecisionResult, SafetyValidationResult
from app.services.decision_engine import decision_engine
from app.services.safety_sentinel import safety_sentinel
from app.services.self_healing import self_healing_loop
from app.simulation.state import building_state

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _decision(request: DecisionRequest) -> DecisionResult:
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        raise HTTPException(status_code=409, detail="Telemetry is required before a policy can be selected")
    return decision_engine.decide(telemetry, request.carbon_intensity_gco2_kwh)


@router.post("/recommend", response_model=DecisionResult)
def recommend_policy(request: DecisionRequest = DecisionRequest()) -> DecisionResult:
    """Select a supervisory policy; this endpoint never changes setpoints."""
    return _decision(request)


@router.post("/apply", response_model=SafetyValidationResult)
def apply_recommended_policy(request: DecisionRequest = DecisionRequest()) -> SafetyValidationResult:
    """Apply a selected policy only after deterministic safety validation."""
    decision = _decision(request)
    current = building_state.get_setpoints()
    result = safety_sentinel.validate(current, decision.proposed_setpoints)
    if result.accepted and result.safe_setpoints is not None:
        building_state.update_setpoints(**result.safe_setpoints.model_dump())
        self_healing_loop.register_applied_policy(decision.selected_policy, current)
    return result
