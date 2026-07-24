import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.schemas.telemetry import BuildingTelemetry
from app.simulation.state import BuildingState


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SIMULATION_ENABLED", "false")
    get_settings.cache_clear()
    state = BuildingState()
    state.publish_telemetry(
        BuildingTelemetry(
            timestamp="2026-07-25T00:00:00Z",
            temperature_c=22.0,
            humidity_pct=45.0,
            occupancy_pct=50.0,
            power_kw=9.0,
        )
    )
    monkeypatch.setattr("app.api.routes.decisions.building_state", state)
    with TestClient(create_app()) as test_client:
        yield test_client, state
    get_settings.cache_clear()


def test_recommend_and_apply_policy(client):
    test_client, state = client

    recommended = test_client.post("/decisions/recommend")
    applied = test_client.post("/decisions/apply")

    assert recommended.status_code == 200
    assert recommended.json()["selected_policy"] == "energy_saver"
    assert applied.status_code == 200
    assert applied.json()["accepted"] is True
    assert state.get_setpoints().hvac_temperature_c == 24.0


def test_recommend_requires_telemetry(monkeypatch):
    state = BuildingState()
    monkeypatch.setattr("app.api.routes.decisions.building_state", state)
    client = TestClient(create_app())

    response = client.post("/decisions/recommend")

    assert response.status_code == 409
