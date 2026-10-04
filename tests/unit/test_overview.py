from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from alarm_service.api.dependencies import get_overview_store
from alarm_service.application.ports.overview import (
    DailySeverityCount,
    EventDates,
    OverviewQuery,
    OverviewSnapshot,
)
from alarm_service.application.use_cases.overview import build_overview
from alarm_service.config import Settings
from alarm_service.domain.alarm import Severity
from alarm_service.main import create_app

START = datetime(2026, 9, 15, 5, tzinfo=UTC)
QUERY = OverviewQuery(START, START + timedelta(days=2))


def snapshot(rows=(), first=datetime(2026, 9, 1, 5, tzinfo=UTC)):
    return OverviewSnapshot(EventDates(first, datetime(2026, 9, 30, 20, tzinfo=UTC)), list(rows))


def test_daily_zero_fill_severity_and_previous_equal_duration():
    result = build_overview(
        QUERY,
        snapshot(
            [
                DailySeverityCount(date(2026, 9, 13), "HIGH", 4),
                DailySeverityCount(date(2026, 9, 15), "HIGH", 3),
                DailySeverityCount(date(2026, 9, 15), "CRITICAL", 1),
                DailySeverityCount(date(2026, 9, 16), "LOW", 2),
            ]
        ),
    )
    assert result["total_events"] == 6
    assert result["severity_counts"] == {"LOW": 2, "MEDIUM": 0, "HIGH": 3, "CRITICAL": 1}
    assert result["comparison"]["event_count"] == 4
    assert result["comparison"]["change_percent"] == Decimal("50.00")
    assert result["comparison"]["start_time"] == START - timedelta(days=2)
    assert result["daily"][0]["moving_average_7_days"] == Decimal("1.14")


def test_missing_prior_dates_does_not_fabricate_comparison_or_average():
    result = build_overview(QUERY, snapshot(first=START))
    assert result["comparison"]["unavailable_reason"] == "outside_observed_dates"
    assert result["comparison"]["event_count"] is None
    assert all(day["moving_average_7_days"] is None for day in result["daily"])
    assert [day["event_count"] for day in result["daily"]] == [0, 0]


def test_zero_baseline_and_empty_database():
    result = build_overview(QUERY, snapshot())
    assert result["comparison"]["unavailable_reason"] == "zero_baseline"
    assert result["comparison"]["change_percent"] is None
    empty = build_overview(QUERY, OverviewSnapshot(EventDates(None, None), []))
    assert empty["total_events"] == 0
    assert all(row["moving_average_7_days"] is None for row in empty["daily"])


def test_average_uses_six_days_before_selected_period():
    rows = [
        DailySeverityCount(date(2026, 9, 9) + timedelta(days=i), "HIGH", i + 1) for i in range(7)
    ]
    result = build_overview(QUERY, snapshot(rows))
    assert result["daily"][0]["event_count"] == 7
    assert result["daily"][0]["moving_average_7_days"] == Decimal("4.00")


class FakeOverview:
    def __init__(self):
        self.queries = []

    def available_dates(self):
        return EventDates(None, None)

    def overview(self, query):
        self.queries.append(query)
        return snapshot()


@pytest.fixture
def overview_api():
    app = create_app(Settings(_env_file=None))
    store = FakeOverview()
    app.dependency_overrides[get_overview_store] = lambda: store
    with TestClient(app) as client:
        yield client, store


def test_http_response_and_timezone_conversion(overview_api):
    client, store = overview_api
    response = client.get(
        "/api/metrics/overview",
        params={
            "start_time": "2026-09-15T00:00:00-05:00",
            "end_time": "2026-09-17T05:00:00Z",
            "severity": "HIGH",
        },
    )
    assert response.status_code == 200
    assert store.queries[0] == OverviewQuery(QUERY.start_time, QUERY.end_time, Severity.HIGH)
    body = response.json()
    assert body["daily"][0]["date"] == "2026-09-15"
    assert body["daily"][0]["moving_average_7_days"] == "0.00"
    assert body["timezone"] == "America/Bogota"
    assert client.get("/api/metrics/available-dates").json() == {
        "timezone": "America/Bogota",
        "first_event": None,
        "last_event": None,
    }


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start_time": "2026-09-15T05:00:00Z"},
        {"start_time": "2026-09-15", "end_time": "2026-09-17T05:00:00Z"},
        {"start_time": "2026-09-15T00:00:00", "end_time": "2026-09-17T05:00:00Z"},
        {"start_time": "2026-09-15T00:00:00Z", "end_time": "2026-09-17T05:00:00Z"},
        {"start_time": "2026-09-17T05:00:00Z", "end_time": "2026-09-15T05:00:00Z"},
        {"start_time": "2026-09-15T05:00:00Z", "end_time": "2026-09-15T05:00:00Z"},
        {"start_time": "2025-01-01T05:00:00Z", "end_time": "2026-09-15T05:00:00Z"},
        {"start_time": "2026-09-15T05:00:00Z", "end_time": "2026-09-17T05:00:00Z", "unknown": "X"},
    ],
)
def test_invalid_ranges_never_query_database(overview_api, params):
    client, store = overview_api
    assert client.get("/api/metrics/overview", params=params).status_code == 422
    assert store.queries == []


def test_overview_database_failure_is_safe(overview_api):
    client, store = overview_api

    def fail(query):
        raise OperationalError("private SQL", {}, RuntimeError("secret"))

    store.overview = fail
    response = client.get(
        "/api/metrics/overview",
        params={
            "start_time": "2026-09-15T05:00:00Z",
            "end_time": "2026-09-17T05:00:00Z",
        },
    )
    assert response.status_code == 503
    assert "secret" not in response.text


def test_overview_normalizes_tag_and_alarm_code(overview_api):
    client, store = overview_api
    response = client.get(
        "/api/metrics/overview",
        params={
            "start_time": "2026-09-15T05:00:00Z",
            "end_time": "2026-09-17T05:00:00Z",
            "tag": " pump_01_flow ",
            "alarm_code": " low_flow ",
            "severity": "MEDIUM",
        },
    )
    assert response.status_code == 200
    assert store.queries[0].tag == "PUMP_01_FLOW"
    assert store.queries[0].alarm_code == "LOW_FLOW"
    assert store.queries[0].severity == Severity.MEDIUM
    assert response.json()["alarm_code"] == "LOW_FLOW"


@pytest.mark.parametrize(
    "field,value",
    [
        ("tag", ""),
        ("tag", "PUMP FLOW"),
        ("tag", "A" * 65),
        ("alarm_code", ""),
        ("alarm_code", "X'; DROP TABLE alarms"),
        ("alarm_code", "A" * 65),
    ],
)
def test_invalid_identifiers_never_query_database(overview_api, field, value):
    client, store = overview_api
    response = client.get(
        "/api/metrics/overview",
        params={
            "start_time": "2026-09-15T05:00:00Z",
            "end_time": "2026-09-17T05:00:00Z",
            field: value,
        },
    )
    assert response.status_code == 422
    assert store.queries == []


def test_catalog_exposes_configured_relationships(overview_api):
    client, _ = overview_api
    response = client.get("/api/catalog/tags")
    assert response.status_code == 200
    items = {item["tag"]: item for item in response.json()["items"]}
    assert len(items) == 12
    assert items["PUMP_01_FLOW"]["alarm_types"] == ["LOW_FLOW"]
    assert items["PUMP_01_FLOW"]["unit"] == "L/min"
    assert items["TANK_IN_01_LEVEL"]["alarm_types"] == ["HIGH_LEVEL", "LOW_LEVEL"]
    assert "HIGH_FLOW" not in {code for item in items.values() for code in item["alarm_types"]}
