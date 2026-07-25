"""Observable status for the autonomous EnergyPlus closed loop."""

from fastapi import APIRouter
from dataclasses import asdict

from app.services.autonomous_control import autonomous_control_loop

router = APIRouter(prefix="/autonomy", tags=["autonomy"])


@router.get("/status")
def autonomous_status() -> dict:
    return asdict(autonomous_control_loop.status())
