from datetime import UTC, datetime

from app.schemas.telemetry import BuildingTelemetry, ComfortFeedback, OperatingPolicy, Setpoints
from app.services.automation_memory import AutomationMemory
from app.services.safety_sentinel import SafetySentinel
from app.services.self_healing import SelfHealingLoop


def telemetry() -> BuildingTelemetry:
    return BuildingTelemetry(timestamp=datetime.now(UTC), temperature_c=24, humidity_pct=50, occupancy_pct=60, power_kw=5)


def test_self_healing_records_failure_and_activates_comfort_fallback():
    memory = AutomationMemory()
    loop = SelfHealingLoop(memory=memory, sentinel=SafetySentinel())
    loop.register_applied_policy(OperatingPolicy.ENERGY_SAVER, Setpoints())

    result = loop.evaluate(ComfortFeedback(expected_comfort=95, actual_comfort=89), Setpoints(hvac_temperature_c=24, ventilation_rate_pct=35), telemetry())

    assert result.policy_failed
    assert result.automatically_corrected
    assert result.fallback_policy == OperatingPolicy.COMFORT_FIRST
    assert result.active_setpoints.hvac_temperature_c == 22.0
    assert memory.recent()[0].policy == OperatingPolicy.ENERGY_SAVER
