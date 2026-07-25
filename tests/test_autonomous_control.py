from datetime import UTC, datetime

from app.schemas.telemetry import BuildingTelemetry, OperatingPolicy
from app.services.autonomous_control import AutonomousControlLoop
from app.simulation.state import BuildingState


def telemetry(power_kw: float, temperature_c: float = 22.0) -> BuildingTelemetry:
    return BuildingTelemetry(
        timestamp=datetime.now(UTC), temperature_c=temperature_c, humidity_pct=45,
        occupancy_pct=50, power_kw=power_kw,
    )


def test_autonomous_loop_selects_energy_policy_and_changes_next_cycle_setpoints():
    state = BuildingState()
    loop = AutonomousControlLoop(state=state)

    status = loop.process(telemetry(power_kw=6.0))

    assert status.active_policy == OperatingPolicy.ENERGY_SAVER
    assert state.get_setpoints().hvac_temperature_c == 24.0
    assert state.get_setpoints().ventilation_rate_pct == 35.0


def test_autonomous_loop_activates_fallback_after_measured_comfort_shortfall():
    state = BuildingState()
    loop = AutonomousControlLoop(state=state)
    loop.process(telemetry(power_kw=6.0))

    status = loop.process(telemetry(power_kw=6.0, temperature_c=29.0))

    assert status.fallback_activated
    assert status.active_policy == OperatingPolicy.COMFORT_FIRST
