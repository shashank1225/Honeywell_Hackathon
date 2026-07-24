from fastapi import APIRouter, HTTPException

from app.schemas.telemetry import Setpoints
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
    return building_state.update_setpoints(hvac_temperature_c=temperature_c)


@router.put("/ventilation", response_model=Setpoints)
def adjust_ventilation(ventilation_rate_pct: float) -> Setpoints:
    if not 0.0 <= ventilation_rate_pct <= 100.0:
        raise HTTPException(
            status_code=400,
            detail="Ventilation rate must be between 0% and 100%",
        )
    return building_state.update_setpoints(ventilation_rate_pct=ventilation_rate_pct)
