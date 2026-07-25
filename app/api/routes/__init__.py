from fastapi import APIRouter

from app.api.routes.decisions import router as decisions_router
from app.api.routes.autonomy import router as autonomy_router
from app.api.routes.counterfactuals import router as counterfactuals_router
from app.api.routes.energy import router as energy_router
from app.api.routes.health import router as health_router
from app.api.routes.goals import router as goals_router
from app.api.routes.setpoints import router as setpoints_router
from app.api.routes.self_healing import router as self_healing_router
from app.api.routes.strategy import router as strategy_router
from app.api.routes.telemetry import router as telemetry_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(telemetry_router)
api_router.include_router(setpoints_router)
api_router.include_router(decisions_router)
api_router.include_router(strategy_router)
api_router.include_router(self_healing_router)
api_router.include_router(goals_router)
api_router.include_router(energy_router)
api_router.include_router(autonomy_router)
api_router.include_router(counterfactuals_router)
