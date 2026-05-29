from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_version_and_env():
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert "version" in payload
    assert "env" in payload
    assert payload["version"] == "0.0.1"
