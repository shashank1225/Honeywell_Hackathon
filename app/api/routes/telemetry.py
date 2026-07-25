import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.schemas.telemetry import BuildingTelemetry
from app.schemas.telemetry import TelemetryWindowSummary
from app.services.telemetry_aggregation import telemetry_window_aggregator
from app.simulation.state import building_state

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/latest", response_model=BuildingTelemetry)
def get_latest_telemetry() -> BuildingTelemetry:
    telemetry = building_state.get_latest_telemetry()
    if telemetry is None:
        raise HTTPException(status_code=404, detail="No telemetry available yet")
    return telemetry


@router.get("/summary", response_model=TelemetryWindowSummary)
def get_telemetry_summary() -> TelemetryWindowSummary:
    """Compact sliding-window aggregates for strategic/LLM context."""
    return telemetry_window_aggregator.summary()


@router.websocket("/stream")
async def telemetry_stream(websocket: WebSocket) -> None:
    """Push real-time telemetry snapshots to dashboard clients."""
    await websocket.accept()
    queue = building_state.subscribe()
    try:
        latest = building_state.get_latest_telemetry()
        if latest is not None:
            await websocket.send_text(latest.model_dump_json())

        while True:
            telemetry = await queue.get()
            await websocket.send_text(telemetry.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        building_state.unsubscribe(queue)
