from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from alarm_service.api.dependencies import get_alarm_metrics_store
from alarm_service.config import Settings
from alarm_service.infrastructure.database.alarm_metrics import PostgresAlarmMetrics
from alarm_service.infrastructure.database.models import AlarmModel, ImportModel
from alarm_service.infrastructure.database.seed import seed_catalog
from alarm_service.main import create_app


@pytest.fixture
def metrics_client(database):
    engine, _ = database
    with engine.begin() as connection:
        seed_catalog(connection)
        import_id = connection.execute(
            insert(ImportModel)
            .values(source_system="SCADA_01", file_name="test.csv", file_sha256="b" * 64)
            .returning(ImportModel.id)
        ).scalar_one()
        examples = [
            (0, "PUMP_01_FLOW", "LOW_FLOW", "HIGH"),
            (1, "PUMP_01_FLOW", "LOW_FLOW", "HIGH"),
            (1, "TANK_IN_01_LEVEL", "LOW_LEVEL", "HIGH"),
            (2, "TANK_IN_01_LEVEL", "LOW_LEVEL", "LOW"),
            (2, "COMPRESSOR_01_PRESSURE", "LOW_PRESSURE", "HIGH"),
            (3, "COMPRESSOR_01_PRESSURE", "LOW_PRESSURE", "HIGH"),
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
                    value=None,
                    message=None,
                    warnings=[],
                )
                for number, (hour, tag, code, severity) in enumerate(examples, 1)
            ],
        )
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_alarm_metrics_store] = lambda: PostgresAlarmMetrics(engine)
    with TestClient(app) as client:
        yield client


def test_counts_and_alphabetic_tie_order(metrics_client):
    response = metrics_client.get("/api/metrics/top-tags")
    assert response.status_code == 200
    assert response.json()["items"] == [
        {"tag": "COMPRESSOR_01_PRESSURE", "event_count": 2},
        {"tag": "PUMP_01_FLOW", "event_count": 2},
        {"tag": "TANK_IN_01_LEVEL", "event_count": 2},
    ]


def test_metrics_time_boundaries(metrics_client):
    body = metrics_client.get(
        "/api/metrics/top-tags",
        params={"start_time": "2026-09-14T20:00:00-05:00", "end_time": "2026-09-15T03:00:00Z"},
    ).json()
    assert body["items"] == [
        {"tag": "TANK_IN_01_LEVEL", "event_count": 2},
        {"tag": "COMPRESSOR_01_PRESSURE", "event_count": 1},
        {"tag": "PUMP_01_FLOW", "event_count": 1},
    ]


def test_severity_and_limit(metrics_client):
    body = metrics_client.get(
        "/api/metrics/top-tags", params={"severity": "HIGH", "limit": 1}
    ).json()
    assert body == {"items": [{"tag": "COMPRESSOR_01_PRESSURE", "event_count": 2}], "limit": 1}


def test_empty_metrics(metrics_client):
    response = metrics_client.get("/api/metrics/top-tags", params={"severity": "CRITICAL"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "limit": 10}


def test_top_tags_respects_tag_and_condition(metrics_client):
    params = {"tag": "PUMP_01_FLOW", "alarm_code": "LOW_FLOW", "severity": "HIGH"}
    response = metrics_client.get("/api/metrics/top-tags", params=params)
    assert response.json()["items"] == [{"tag": "PUMP_01_FLOW", "event_count": 2}]
    incompatible = metrics_client.get("/api/metrics/top-tags", params={
        **params, "alarm_code": "LOW_PRESSURE",
    })
    assert incompatible.json()["items"] == []
