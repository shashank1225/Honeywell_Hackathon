from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routes import api_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    yield


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
    app.include_router(api_router)
    return app


app = create_app()
