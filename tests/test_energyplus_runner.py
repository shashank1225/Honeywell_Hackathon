import asyncio

import pytest

from app.schemas.telemetry import Setpoints
from app.simulation.energyplus_runner import EnergyPlusRunner, EnergyPlusSubprocessBackend
from app.simulation.state import BuildingState
from tests.fakes import FakeEnergyPlusBackend


@pytest.fixture
def isolated_state():
    return BuildingState()


@pytest.fixture
def runner(isolated_state):
    return EnergyPlusRunner(state=isolated_state, interval_seconds=0.1, backend=FakeEnergyPlusBackend())


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


def test_runner_recovers_after_a_transient_energyplus_failure(isolated_state):
    class FlakyBackend(FakeEnergyPlusBackend):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def wait_for_telemetry(self, timeout_seconds: float | None = None):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("temporary EnergyPlus output lock")
            return super().wait_for_telemetry(timeout_seconds)

    async def run_test() -> None:
        backend = FlakyBackend()
        retrying_runner = EnergyPlusRunner(
            state=isolated_state,
            interval_seconds=0.01,
            backend=backend,
        )
        await retrying_runner.start()
        await asyncio.sleep(0.05)
        await retrying_runner.stop()

        assert backend.attempts >= 2
        assert isolated_state.get_latest_telemetry() is not None

    asyncio.run(run_test())


def test_load_frames_from_eso_and_meter_files(tmp_path):
    eso_path = tmp_path / "eplusout.eso"
    meter_path = tmp_path / "eplusout.mtr"
    eso_path.write_text(
        """Program Version,EnergyPlus, Version 26.1.0, YMD=2026.07.25 01:44
62,1,ZONE ONE,Zone Mean Air Temperature [C] !Hourly
63,1,ZONE ONE,Zone Air Relative Humidity [%] !Hourly
64,1,ZONE ONE,Zone People Occupant Count [] !Hourly
End of Data Dictionary
2,1,7,21,0,1,0.00,60.00,SummerDesignDay
62,21.5
63,10.0
64,20.0
2,1,7,21,0,2,0.00,60.00,SummerDesignDay
62,22.1
63,11.0
64,21.0
""",
        encoding="utf-8",
    )
    meter_path.write_text(
        """Program Version,EnergyPlus, Version 26.1.0, YMD=2026.07.25 01:44
24,1,ExteriorLights:Electricity [J] !Hourly
End of Data Dictionary
2,1,7,21,0,1,0.00,60.00,SummerDesignDay
24,1800000.0
2,1,7,21,0,2,0.00,60.00,SummerDesignDay
24,3600000.0
""",
        encoding="utf-8",
    )

    backend = EnergyPlusSubprocessBackend(zone="main")
    frames = list(backend._load_frames_from_eso(eso_path, meter_path))

    assert len(frames) == 2
    assert frames[0].temperature_c == pytest.approx(21.5)
    assert frames[0].humidity_pct == pytest.approx(10.0)
    assert frames[0].occupancy_pct == pytest.approx(20.0)
    assert frames[0].power_kw == pytest.approx(0.5)
