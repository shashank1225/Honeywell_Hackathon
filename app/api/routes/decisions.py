"""Phase 3 policy decision and safety-validated application endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.telemetry import DecisionRequest, DecisionResult, SafetyValidationResult
from app.services.decision_engine import decision_engine
from app.services.control_gateway import apply_safe_setpoints
from app.services.self_healing import self_healing_loop
from app.agents.mcp_context import MCPBuildingContext
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


@router.post("/mcp-recommend", response_model=DecisionResult)
def recommend_policy_from_mcp(request: DecisionRequest = DecisionRequest()) -> DecisionResult:
    """Use MCP telemetry resources as the specialized-agents context interface."""
    try:
        return decision_engine.decide_from_mcp(MCPBuildingContext(), request.carbon_intensity_gco2_kwh)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="MCP telemetry is required before a policy can be selected") from exc


@router.post("/apply", response_model=SafetyValidationResult)
def apply_recommended_policy(request: DecisionRequest = DecisionRequest()) -> SafetyValidationResult:
    """Apply a selected policy only after deterministic safety validation."""
    decision = _decision(request)
    current = building_state.get_setpoints()
    result = apply_safe_setpoints(building_state, decision.proposed_setpoints, policy=decision.selected_policy)
    if result.accepted and result.safe_setpoints is not None:
        self_healing_loop.register_applied_policy(decision.selected_policy, current)
    return result
