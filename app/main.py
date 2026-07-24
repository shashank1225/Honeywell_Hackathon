from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import api_router
from app.config import get_settings
from app.simulation.energyplus_runner import get_energyplus_runner


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    settings = get_settings()
    runner = get_energyplus_runner()
    if settings.simulation_enabled:
        await runner.start()
    yield
    if settings.simulation_enabled:
        await runner.stop()


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
