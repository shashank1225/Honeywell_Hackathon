from fastapi import APIRouter, HTTPException

from app.schemas.telemetry import Setpoints
from app.services.control_gateway import apply_safe_setpoints
from app.simulation.state import building_state

router = APIRouter(prefix="/setpoints", tags=["setpoints"])


@router.get("", response_model=Setpoints)
def get_setpoints() -> Setpoints:
    return building_state.get_setpoints()


@router.put("/hvac", response_model=Setpoints)
def set_hvac_temperature(temperature_c: float) -> Setpoints:
    if not 16.0 <= temperature_c <= 30.0:
        raise HTTPException(
            status_code=400,
            detail="HVAC temperature must be between 16°C and 30°C",
        )
    current = building_state.get_setpoints()
    result = apply_safe_setpoints(building_state, current.model_copy(update={"hvac_temperature_c": temperature_c}))
    if not result.accepted or result.safe_setpoints is None:
        raise HTTPException(status_code=409, detail=result.reasons)
    return result.safe_setpoints


@router.put("/ventilation", response_model=Setpoints)
def adjust_ventilation(ventilation_rate_pct: float) -> Setpoints:
    if not 0.0 <= ventilation_rate_pct <= 100.0:
        raise HTTPException(
            status_code=400,
            detail="Ventilation rate must be between 0% and 100%",
        )
    current = building_state.get_setpoints()
    result = apply_safe_setpoints(building_state, current.model_copy(update={"ventilation_rate_pct": ventilation_rate_pct}))
    if not result.accepted or result.safe_setpoints is None:
        raise HTTPException(status_code=409, detail=result.reasons)
    return result.safe_setpoints


@router.put("/lighting", response_model=Setpoints)
def adjust_lighting(lighting_level_pct: float) -> Setpoints:
    if not 0.0 <= lighting_level_pct <= 100.0:
        raise HTTPException(
            status_code=400,
            detail="Lighting level must be between 0% and 100%",
        )
    current = building_state.get_setpoints()
    result = apply_safe_setpoints(
        building_state,
        current.model_copy(update={"lighting_level_pct": lighting_level_pct}),
    )
    if not result.accepted or result.safe_setpoints is None:
        raise HTTPException(status_code=409, detail=result.reasons)
    return result.safe_setpoints
