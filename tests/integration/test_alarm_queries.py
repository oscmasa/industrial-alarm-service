from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from alarm_service.api.dependencies import get_alarm_query_store, get_overview_store
from alarm_service.config import Settings
from alarm_service.infrastructure.database.alarm_query import PostgresAlarmQuery
from alarm_service.infrastructure.database.models import AlarmModel, ImportModel
from alarm_service.infrastructure.database.overview import PostgresOverview
from alarm_service.infrastructure.database.seed import seed_catalog
from alarm_service.main import create_app


@pytest.fixture
def alarm_client(database):
    engine, _ = database
    with engine.begin() as connection:
        seed_catalog(connection)
        import_id = connection.execute(
            insert(ImportModel)
            .values(source_system="SCADA_01", file_name="test.csv", file_sha256="a" * 64)
            .returning(ImportModel.id)
        ).scalar_one()
        rows = [
            (1, 0, "PUMP_01_FLOW", "LOW_FLOW", "HIGH"),
            (2, 0, "PUMP_01_FLOW", "LOW_FLOW", "LOW"),
            (3, 1, "PUMP_01_FLOW", "LOW_FLOW", "HIGH"),
            (4, 1, "TANK_IN_01_LEVEL", "LOW_LEVEL", "HIGH"),
            (5, 2, "PUMP_01_FLOW", "LOW_FLOW", "HIGH"),
        ]
        connection.execute(
            insert(AlarmModel),
            [
                dict(
                    source_system="SCADA_01",
                    import_id=import_id,
                    event_id=f"EVT-{number:08d}",
                    occurred_at=datetime(2026, 9, 15, hour, tzinfo=UTC),
                    tag_id=tag,
                    alarm_code=code,
                    severity=severity,
                    value="12.5",
                    message=None,
                    warnings=[],
                )
                for number, hour, tag, code, severity in rows
            ],
        )
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_alarm_query_store] = lambda: PostgresAlarmQuery(engine)
    app.dependency_overrides[get_overview_store] = lambda: PostgresOverview(engine)
    with TestClient(app) as client:
        yield client


def test_combined_filters_and_time_boundaries(alarm_client):
    response = alarm_client.get(
        "/api/alarms",
        params={
            "start_time": "2026-09-14T19:00:00-05:00",
            "end_time": "2026-09-15T02:00:00Z",
            "severity": "HIGH",
            "tag": "PUMP_01_FLOW",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 2
    assert [row["event_id"] for row in body["items"]] == ["EVT-00000003", "EVT-00000001"]
    assert all(row["unit"] == "L/min" for row in body["items"])
    assert all(row["value"] == "12.500000" for row in body["items"])


def test_pagination_has_stable_tie_breaking(alarm_client):
    pages = [
        alarm_client.get("/api/alarms", params={"page": page, "page_size": 2}).json()
        for page in (1, 2, 3, 4)
    ]
    events = [row["event_id"] for page in pages for row in page["items"]]
    assert events == [
        "EVT-00000005",
        "EVT-00000004",
        "EVT-00000003",
        "EVT-00000002",
        "EVT-00000001",
    ]
    assert all(page["pagination"]["total"] == 5 for page in pages)
    assert pages[3]["items"] == [] and pages[3]["pagination"]["total_pages"] == 3


def test_no_matches_returns_empty_page(alarm_client):
    body = alarm_client.get("/api/alarms", params={"tag": "UNKNOWN_TAG"}).json()
    assert body["items"] == [] and body["pagination"]["total"] == 0
    assert body["pagination"]["total_pages"] == 0


def test_single_filters(alarm_client):
    for params, expected in (
        ({"severity": "LOW"}, 1),
        ({"tag": "TANK_IN_01_LEVEL"}, 1),
        ({"start_time": "2026-09-15T01:00:00Z"}, 3),
        ({"end_time": "2026-09-15T01:00:00Z"}, 2),
    ):
        assert (
            alarm_client.get("/api/alarms", params=params).json()["pagination"]["total"] == expected
        )


def test_tag_catalog_units_are_exposed_without_changing_values(alarm_client):
    items = alarm_client.get("/api/alarms").json()["items"]
    assert {row["tag"]: row["unit"] for row in items} == {
        "PUMP_01_FLOW": "L/min",
        "TANK_IN_01_LEVEL": "%",
    }
    assert all(row["value"] == "12.500000" for row in items)


def test_overview_groups_by_bogota_day_and_filters_severity(alarm_client):
    params = {"start_time": "2026-09-14T05:00:00Z",
              "end_time": "2026-09-16T05:00:00Z"}
    body = alarm_client.get("/api/metrics/overview", params=params).json()
    assert body["total_events"] == 5
    assert [row["event_count"] for row in body["daily"]] == [5, 0]
    assert body["severity_counts"]["HIGH"] == 4
    filtered = alarm_client.get("/api/metrics/overview", params={**params, "severity": "LOW"})
    assert filtered.json()["total_events"] == 1
    assert filtered.json()["daily"][0]["date"] == "2026-09-14"
    dates = alarm_client.get("/api/metrics/available-dates").json()
    assert dates["first_event"] == "2026-09-15T00:00:00Z"
    assert dates["last_event"] == "2026-09-15T02:00:00Z"
    next_day = alarm_client.get("/api/metrics/overview", params={
        "start_time": "2026-09-15T05:00:00Z",
        "end_time": "2026-09-16T05:00:00Z",
    }).json()
    assert next_day["total_events"] == 0
    assert next_day["daily"][0]["moving_average_7_days"] is None


def test_overview_empty_database(database):
    engine, _ = database
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_overview_store] = lambda: PostgresOverview(engine)
    with TestClient(app) as client:
        dates = client.get("/api/metrics/available-dates").json()
        assert dates["first_event"] is None and dates["last_event"] is None
        result = client.get("/api/metrics/overview", params={
            "start_time": "2026-09-01T05:00:00Z",
            "end_time": "2026-10-01T05:00:00Z",
        })
        assert result.status_code == 200
        body = result.json()
        assert body["total_events"] == 0 and len(body["daily"]) == 30
        assert body["comparison"]["event_count"] is None


def test_overview_tag_and_condition_filters(alarm_client):
    params = {"start_time": "2026-09-14T05:00:00Z",
              "end_time": "2026-09-16T05:00:00Z", "tag": "PUMP_01_FLOW",
              "alarm_code": "LOW_FLOW", "severity": "HIGH"}
    result = alarm_client.get("/api/metrics/overview", params=params).json()
    assert result["total_events"] == 3
    assert result["daily"][0]["event_count"] == 3
    incompatible = alarm_client.get("/api/metrics/overview", params={
        **params, "alarm_code": "LOW_LEVEL",
    }).json()
    assert incompatible["total_events"] == 0
    assert all(row["event_count"] == 0 for row in incompatible["daily"])
