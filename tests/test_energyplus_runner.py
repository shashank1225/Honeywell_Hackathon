import pytest

from app.schemas.telemetry import Setpoints
from app.simulation.energyplus_runner import EnergyPlusRunner
from app.simulation.state import BuildingState


@pytest.fixture
def isolated_state():
    return BuildingState()


@pytest.fixture
def runner(isolated_state):
    return EnergyPlusRunner(state=isolated_state, interval_seconds=0.1)


def test_tick_once_generates_expected_fields(runner, isolated_state):
    telemetry = runner.tick_once()

    assert telemetry.zone == "main"
    assert 10.0 <= telemetry.temperature_c <= 35.0
    assert 0.0 <= telemetry.humidity_pct <= 100.0
    assert 0.0 <= telemetry.occupancy_pct <= 100.0
    assert telemetry.power_kw > 0.0
    assert isolated_state.get_latest_telemetry() == telemetry


def test_setpoints_influence_simulation(isolated_state, runner):
    isolated_state.update_setpoints(hvac_temperature_c=18.0, ventilation_rate_pct=80.0)

    first = runner.tick_once()
    for _ in range(10):
        latest = runner.tick_once()

    assert latest.temperature_c <= first.temperature_c
    assert latest.power_kw >= 5.0


def test_invalid_setpoint_range_rejected_by_schema():
    with pytest.raises(ValueError):
        Setpoints(hvac_temperature_c=10.0)
