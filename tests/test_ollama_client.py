import json
from datetime import UTC, datetime

from app.config import get_settings
from app.schemas.telemetry import GoalType, StrategicGoal, TelemetryWindowSummary
from app.services.ollama_client import OllamaStrategicClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def summary() -> TelemetryWindowSummary:
    now = datetime.now(UTC)
    return TelemetryWindowSummary(
        samples=4,
        window_start=now,
        window_end=now,
        average_temperature_c=22.0,
        min_temperature_c=21.5,
        max_temperature_c=22.5,
        average_humidity_pct=45.0,
        average_occupancy_pct=40.0,
        average_power_kw=6.0,
        peak_power_kw=7.0,
        estimated_energy_kwh=0.02,
    )


def test_ollama_request_is_short_bounded_json_and_kept_warm(monkeypatch):
    observed = {}

    def fake_urlopen(request, timeout):
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        observed["timeout"] = timeout
        return FakeResponse({"response": json.dumps({"policy": "energy_saver", "rationale": "Demand is elevated."})})

    monkeypatch.setattr("app.services.ollama_client.urlopen", fake_urlopen)
    get_settings.cache_clear()
    try:
        recommendation = OllamaStrategicClient().recommend(
            StrategicGoal(objective=GoalType.ENERGY_REDUCTION, target_percent=10),
            summary(),
        )
    finally:
        get_settings.cache_clear()

    assert recommendation.policy.value == "energy_saver"
    assert observed["payload"]["format"] == "json"
    assert observed["payload"]["keep_alive"] == "30m"
    assert observed["payload"]["options"]["num_predict"] == 80
    assert observed["payload"]["options"]["num_ctx"] == 2048
