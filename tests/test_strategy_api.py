from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.schemas.telemetry import BuildingTelemetry
from app.services.automation_memory import AutomationMemory
from app.services.strategic_reasoner import StrategicReasoner
from app.simulation.state import BuildingState


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SIMULATION_ENABLED", "false")
    get_settings.cache_clear()
    state = BuildingState()
    state.publish_telemetry(BuildingTelemetry(
        timestamp=datetime.now(UTC), temperature_c=22, humidity_pct=45, occupancy_pct=50, power_kw=4,
    ))
    memory = AutomationMemory()
    monkeypatch.setattr("app.api.routes.strategy.building_state", state)
    monkeypatch.setattr("app.api.routes.strategy.automation_memory", memory)
    monkeypatch.setattr("app.api.routes.strategy.strategic_reasoner", StrategicReasoner(memory=memory))
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_strategy_plan_and_episode_memory(client):
    plan = client.post("/strategy/plan", json={"objective": "carbon_reduction", "target_percent": 12, "carbon_intensity_gco2_kwh": 650})
    episode = client.post("/strategy/episodes", json={
        "timestamp": "2026-07-25T00:00:00Z", "policy": "carbon_aware", "reward": 0.7,
        "energy_kwh": 10, "comfort_score": 0.9, "carbon_kg": 2, "confidence": 0.8,
    })
    policies = client.get("/strategy/policies")

    assert plan.status_code == 200
    assert plan.json()["selected_policy"] == "carbon_aware"
    assert episode.status_code == 201
    assert policies.json()[0]["policy"] == "carbon_aware"
