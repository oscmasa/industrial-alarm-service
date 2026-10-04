from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from alarm_service.api.dependencies import get_data_quality_store
from alarm_service.application.ports.data_quality import ImportSummary, QualityPage, RejectedRecord
from alarm_service.config import Settings
from alarm_service.main import create_app

IMPORT_ID = UUID("26ee9e17-19ec-4dd8-8f68-78bb0c0cf867")
NOW = datetime(2026, 10, 1, tzinfo=UTC)


class FakeQuality:
    def __init__(self):
        self.calls = []
        self.failure = False

    def list_imports(self, page, page_size):
        self.calls.append((page, page_size))
        if self.failure:
            raise OperationalError("private SQL", {}, Exception("private password"))
        return QualityPage(
            [
                ImportSummary(
                    IMPORT_ID,
                    "SCADA_01",
                    "alarms.csv",
                    "a" * 64,
                    "COMPLETED",
                    NOW,
                    NOW,
                    10000,
                    9500,
                    300,
                    200,
                    167,
                )
            ],
            1,
        )

    def list_rejections(self, import_id, page, page_size, error_code):
        self.calls.append((import_id, page, page_size, error_code))
        if import_id != IMPORT_ID:
            return None
        if error_code == "UNKNOWN_CODE":
            return QualityPage([], 0)
        return QualityPage(
            [
                RejectedRecord(
                    1,
                    IMPORT_ID,
                    12,
                    {"value": "  bad value ", "occurred_at": "invalid"},
                    [{"field": "value", "code": "INVALID_NUMBER", "message": "Invalid number."}],
                    NOW,
                )
            ],
            1,
        )


@pytest.fixture
def api():
    app = create_app(Settings(_env_file=None))
    store = FakeQuality()
    app.dependency_overrides[get_data_quality_store] = lambda: store
    with TestClient(app) as client:
        yield client, store


def test_import_counters_and_default_pagination(api):
    client, store = api
    body = client.get("/api/imports").json()
    item = body["items"][0]
    assert item["accepted"] + item["rejected"] + item["duplicates"] == item["records_read"]
    assert item["accepted_with_warnings"] == 167
    assert "error_message" not in item
    assert body["pagination"] == {"page": 1, "page_size": 20, "total": 1, "total_pages": 1}
    assert store.calls == [(1, 20)]


def test_preserves_raw_values_and_normalizes_error_filter(api):
    client, store = api
    response = client.get(
        f"/api/imports/{IMPORT_ID}/rejections",
        params={
            "error_code": " invalid_number ",
            "page": 2,
            "page_size": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["original_data"]["value"] == "  bad value "
    assert body["import_id"] == str(IMPORT_ID)
    assert store.calls[-1] == (IMPORT_ID, 2, 1, "INVALID_NUMBER")


def test_unknown_import_differs_from_no_matching_rejections(api):
    client, _ = api
    assert client.get(f"/api/imports/{UUID(int=0)}/rejections").status_code == 404
    response = client.get(f"/api/imports/{IMPORT_ID}/rejections?error_code=UNKNOWN_CODE")
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.parametrize(
    "path,params",
    [
        ("/api/imports", {"page": 0}),
        ("/api/imports", {"page": 100001}),
        ("/api/imports", {"page_size": 101}),
        ("/api/imports", {"page_size": 0}),
        ("/api/imports", {"page": "bad"}),
        ("/api/imports", {"unexpected": "bad"}),
        (f"/api/imports/{IMPORT_ID}/rejections", {"error_code": ""}),
        (f"/api/imports/{IMPORT_ID}/rejections", {"error_code": "BAD CODE"}),
        (f"/api/imports/{IMPORT_ID}/rejections", {"error_code": "A" * 65}),
        (f"/api/imports/{IMPORT_ID}/rejections", {"page_size": 101}),
        ("/api/imports/not-a-uuid/rejections", {}),
    ],
)
def test_invalid_requests_do_not_query_store(api, path, params):
    client, store = api
    response = client.get(path, params=params)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert not store.calls


def test_database_failure_is_safe(api):
    client, store = api
    store.failure = True
    response = client.get("/api/imports")
    assert response.status_code == 503
    assert "private" not in response.text and "password" not in response.text
