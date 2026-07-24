from fastapi.testclient import TestClient

from app.main import create_app


def test_health_check_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "AABOS"
    assert payload["version"] == "0.1.0"


def test_readiness_check_returns_dependency_status():
    client = TestClient(create_app())
    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "postgres" in payload["dependencies"]
    assert "kafka" in payload["dependencies"]
