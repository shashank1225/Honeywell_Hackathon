import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.simulation.energyplus_runner import EnergyPlusRunner
from app.simulation.state import BuildingState
from tests.fakes import FakeEnergyPlusBackend


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SIMULATION_ENABLED", "false")
    get_settings.cache_clear()

    state = BuildingState()
    runner = EnergyPlusRunner(state=state, interval_seconds=0.1, backend=FakeEnergyPlusBackend())
    runner.tick_once()

    monkeypatch.setattr("app.api.routes.telemetry.building_state", state)
    monkeypatch.setattr("app.api.routes.setpoints.building_state", state)

    with TestClient(create_app()) as test_client:
        yield test_client, state

    get_settings.cache_clear()


def test_get_latest_telemetry(client):
    test_client, _ = client
    response = test_client.get("/telemetry/latest")

    assert response.status_code == 200
    payload = response.json()
    assert "temperature_c" in payload
    assert "power_kw" in payload


def test_update_setpoints(client):
    test_client, state = client

    hvac_response = test_client.put("/setpoints/hvac?temperature_c=21.5")
    vent_response = test_client.put("/setpoints/ventilation?ventilation_rate_pct=65")
    lighting_response = test_client.put("/setpoints/lighting?lighting_level_pct=75")

    assert hvac_response.status_code == 200
    assert vent_response.status_code == 200
    assert lighting_response.status_code == 200
    assert state.get_setpoints().hvac_temperature_c == 21.5
    assert state.get_setpoints().ventilation_rate_pct == 65.0
    assert state.get_setpoints().lighting_level_pct == 75.0


def test_reject_out_of_range_hvac(client):
    test_client, _ = client
    response = test_client.put("/setpoints/hvac?temperature_c=40")
    assert response.status_code == 400
