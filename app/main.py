from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import api_router
from app.config import get_settings
from app.kafka.telemetry_consumer import TelemetryKafkaConsumer
from app.services.energy_efficiency import energy_efficiency_tracker
from app.services.strategic_worker import strategic_work_queue
from app.services.telemetry_aggregation import telemetry_window_aggregator
from app.services.autonomous_control import autonomous_control_loop
from app.services.automation_memory import automation_memory
from app.simulation.energyplus_runner import get_energyplus_runner
from app.simulation.state import building_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    settings = get_settings()
    runner = None
    def process_telemetry_event(telemetry):
        building_state.publish_telemetry(telemetry)
        energy_efficiency_tracker.record(telemetry, settings.simulation_interval_seconds)
        telemetry_window_aggregator.add(telemetry)

    consumer = TelemetryKafkaConsumer(process_telemetry_event)
    consumer.start()
    automation_memory.start()
    if settings.strategic_worker_enabled:
        strategic_work_queue.start()
    if settings.simulation_enabled:
        runner = get_energyplus_runner()
        runner.set_telemetry_handler(autonomous_control_loop.process)
        await runner.start()
    yield
    if runner is not None:
        await runner.stop()
    consumer.stop()
    strategic_work_queue.stop()
    automation_memory.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Autonomous Adaptive Building Operating System — "
            "safely optimizes comfort, energy, and carbon through hierarchical AI."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
