from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.schemas.telemetry import BuildingTelemetry
from app.services.goal_management import AutonomousGoalManagementSystem
from app.simulation.state import BuildingState


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SIMULATION_ENABLED", "false")
    get_settings.cache_clear()
    state = BuildingState()
    state.publish_telemetry(BuildingTelemetry(timestamp=datetime.now(UTC), temperature_c=22, humidity_pct=45, occupancy_pct=50, power_kw=8))
    system = AutonomousGoalManagementSystem()
    monkeypatch.setattr("app.api.routes.goals.building_state", state)
    monkeypatch.setattr("app.api.routes.goals.goal_management_system", system)
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_create_and_list_goal(client):
    created = client.post("/goals", json={"objective": "energy_reduction", "target_percent": 15, "priority": 80})
    goals = client.get("/goals")

    assert created.status_code == 201
    assert created.json()["status"] == "accepted"
    assert len(goals.json()) == 1
