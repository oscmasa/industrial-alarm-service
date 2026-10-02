from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from alarm_service.api.dependencies import get_alarm_metrics_store
from alarm_service.application.ports.alarm_metrics import TagCount
from alarm_service.config import Settings
from alarm_service.main import create_app


class FakeMetrics:
    def __init__(self):
        self.queries = []

    def top_tags(self, query):
        self.queries.append(query)
        return [TagCount("PUMP_01_FLOW", 12), TagCount("TANK_IN_01_LEVEL", 5)][: query.limit]


@pytest.fixture
def api():
    app = create_app(Settings(_env_file=None))
    store = FakeMetrics()
    app.dependency_overrides[get_alarm_metrics_store] = lambda: store
    with TestClient(app) as client:
        yield client, store


def test_default_response(api):
    client, store = api
    response = client.get("/api/metrics/top-tags")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"tag": "PUMP_01_FLOW", "event_count": 12},
            {"tag": "TANK_IN_01_LEVEL", "event_count": 5},
        ],
        "limit": 10,
    }
    assert len(store.queries) == 1


def test_combined_filters(api):
    client, store = api
    response = client.get(
        "/api/metrics/top-tags",
        params={
            "start_time": "2026-09-14T19:00:00-05:00",
            "end_time": "2026-09-16T00:00:00Z",
            "severity": "HIGH",
            "limit": 1,
        },
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert store.queries[0].start_time == datetime(2026, 9, 15, tzinfo=UTC)
    assert store.queries[0].severity == "HIGH"


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": "abc"},
        {"severity": "URGENT"},
        {"start_time": "2026-09-15T12:00:00"},
        {"start_time": "2026-09-15T24:00:00Z"},
        {"start_time": "2026-09-16T00:00:00Z", "end_time": "2026-09-15T00:00:00Z"},
        {"start_time": "2026-09-15T00:00:00Z", "end_time": "2026-09-15T00:00:00Z"},
        {"page": 2},
        {"tag": "PUMP_01_FLOW"},
    ],
)
def test_invalid_metrics_parameters(api, params):
    client, store = api
    assert client.get("/api/metrics/top-tags", params=params).status_code == 422
    assert not store.queries


def test_database_error_is_safe(api):
    client, store = api

    def fail(query):
        raise OperationalError("private SQL", {}, RuntimeError("credentials"))

    store.top_tags = fail
    response = client.get("/api/metrics/top-tags")
    assert response.status_code == 503
    assert "credentials" not in response.text


def test_metrics_openapi_parameters(api):
    client, _ = api
    operation = client.get("/openapi.json").json()["paths"]["/api/metrics/top-tags"]["get"]
    assert {param["name"] for param in operation["parameters"]} == {
        "start_time",
        "end_time",
        "severity",
        "limit",
    }
