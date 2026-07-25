"""Measured energy-baseline and realized-savings endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.telemetry import EnergySavingsReport
from app.services.energy_efficiency import energy_efficiency_tracker
from app.simulation.state import building_state

router = APIRouter(prefix="/energy", tags=["energy"])


@router.post("/baseline", response_model=EnergySavingsReport)
def capture_baseline() -> EnergySavingsReport:
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        raise HTTPException(status_code=409, detail="Telemetry is required to capture an energy baseline")
    return energy_efficiency_tracker.capture_baseline(telemetry)


@router.get("/savings", response_model=EnergySavingsReport)
def realized_savings() -> EnergySavingsReport:
    return energy_efficiency_tracker.report()
