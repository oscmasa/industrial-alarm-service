from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from alarm_service.api.dependencies import get_alarm_query_store
from alarm_service.config import Settings
from alarm_service.infrastructure.database.alarm_query import PostgresAlarmQuery
from alarm_service.infrastructure.database.models import AlarmModel, ImportModel
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
            alarm_client.get("/api/alarms", params=params).json()["pagination"]["total"]
            == expected
        )
