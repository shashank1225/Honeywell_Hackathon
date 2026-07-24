from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.database import check_database_connection
from app.kafka.client import check_kafka_connection

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    """Basic liveness probe — confirms the API process is running."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": __version__,
    }


@router.get("/health/ready")
def readiness_check() -> dict:
    """Readiness probe — verifies downstream infrastructure connectivity."""
    database_ok = check_database_connection()
    kafka_ok = check_kafka_connection()

    status = "ok" if database_ok and kafka_ok else "degraded"
    return {
        "status": status,
        "dependencies": {
            "postgres": "ok" if database_ok else "unavailable",
            "kafka": "ok" if kafka_ok else "unavailable",
        },
    }
