from fastapi.testclient import TestClient

from alarm_service.config import Settings
from alarm_service.main import create_app


def test_status_returns_ok():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_exposes_status_endpoint():
    with TestClient(create_app(Settings(_env_file=None, docs_enabled=True))) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/status" in response.json()["paths"]


def test_documentation_can_be_disabled():
    with TestClient(create_app(Settings(_env_file=None, docs_enabled=False))) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/status").status_code == 200
