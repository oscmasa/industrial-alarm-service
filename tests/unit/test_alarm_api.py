import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from alarm_service.api.dependencies import get_alarm_query_store
from alarm_service.application.ports.alarm_query import AlarmPage, AlarmRecord
from alarm_service.config import Settings
from alarm_service.domain.alarm import Alarm, Severity
from alarm_service.main import create_app


class FakeStore:
    def __init__(self):
        self.queries = []

    def list_alarms(self, query):
        self.queries.append(query)
        alarm = Alarm(
            "EVT-00000001",
            datetime(2026, 9, 15, 19, tzinfo=UTC),
            "PUMP_01_FLOW",
            "LOW_FLOW",
            Severity.HIGH,
            None,
            Decimal("12.500001"),
            ("VALUE_TRIGGER_MISMATCH",),
        )
        return AlarmPage(
            [AlarmRecord(1, "SCADA_01", uuid.UUID(int=1), alarm, unit="L/min")],
            123,
            query.page,
            query.page_size,
        )


@pytest.fixture
def api():
    app = create_app(Settings(_env_file=None))
    store = FakeStore()
    app.dependency_overrides[get_alarm_query_store] = lambda: store
    with TestClient(app) as client:
        yield client, store


def test_response_precision_and_pagination(api):
    client, store = api
    response = client.get("/api/alarms")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"page": 1, "page_size": 50, "total": 123, "total_pages": 3}
    assert body["items"][0]["value"] == "12.500001"
    assert body["items"][0]["unit"] == "L/min"
    assert body["items"][0]["occurred_at"].endswith("Z")
    assert body["items"][0]["warnings"] == ["VALUE_TRIGGER_MISMATCH"]
    assert len(store.queries) == 1


def test_filters_are_normalized_before_query(api):
    client, store = api
    response = client.get(
        "/api/alarms",
        params={
            "start_time": "2026-09-15T14:00:00-05:00",
            "end_time": "2026-09-16T00:00:00Z",
            "severity": "HIGH",
            "tag": " pump_01_flow ",
            "page": 2,
            "page_size": 10,
        },
    )
    assert response.status_code == 200
    query = store.queries[0]
    assert query.start_time == datetime(2026, 9, 15, 19, tzinfo=UTC)
    assert query.tag == "PUMP_01_FLOW" and query.severity == Severity.HIGH
    assert query.page == 2 and query.page_size == 10


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page": 100001},
        {"page": "abc"},
        {"page_size": 0},
        {"page_size": 101},
        {"severity": "Alta"},
        {"tag": ""},
        {"tag": "x';DROP TABLE alarms;--"},
        {"start_time": "2026-09-15"},
        {"start_time": "2026-09-15T12:00:00"},
        {"start_time": "1726400000"},
        {"start_time": "2026-09-15T24:00:00Z"},
        {"end_time": "2026-02-30T12:00:00Z"},
        {"start_time": "2026-09-16T00:00:00Z", "end_time": "2026-09-15T00:00:00Z"},
        {"start_time": "2026-09-15T00:00:00Z", "end_time": "2026-09-15T00:00:00Z"},
        {"unexpected": "value"},
    ],
)
def test_invalid_parameters_do_not_query_database(api, params):
    client, store = api
    assert client.get("/api/alarms", params=params).status_code == 422
    assert not store.queries


def test_database_errors_return_safe_service_unavailable(api):
    client, store = api

    def fail(query):
        raise OperationalError("private SQL", {}, RuntimeError("private credentials"))

    store.list_alarms = fail
    response = client.get("/api/alarms")
    assert response.status_code == 503
    assert "private" not in response.text


def test_openapi_documents_filters(api):
    client, _ = api
    operation = client.get("/openapi.json").json()["paths"]["/api/alarms"]["get"]
    assert {p["name"] for p in operation["parameters"]} == {
        "start_time",
        "end_time",
        "severity",
        "tag",
        "page",
        "page_size",
    }
