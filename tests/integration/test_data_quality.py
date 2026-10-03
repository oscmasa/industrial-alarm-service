from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert

from alarm_service.infrastructure.database.data_quality import PostgresDataQuality
from alarm_service.infrastructure.database.models import ImportModel, RejectedRecordModel


def test_order_pagination_and_import_isolation(database):
    engine, _ = database
    first, second = uuid4(), uuid4()
    with engine.begin() as conn:
        conn.execute(insert(ImportModel), [
            dict(id=identifier, source_system="SCADA_01", file_name="same.csv",
                 file_sha256="a" * 64, started_at=datetime(2026, 9, day, tzinfo=UTC))
            for identifier, day in [(first, 1), (second, 2)]
        ])
        conn.execute(insert(RejectedRecordModel), [
            dict(import_id=identifier, record_number=number, original_data={"value": " bad "},
                 errors=[{"field": "value", "code": code, "message": "Invalid."}])
            for identifier, number, code in [
                (first, 3, "INVALID_NUMBER"), (first, 1, "INVALID_DATE"),
                (second, 1, "INVALID_NUMBER"),
            ]
        ])
    store = PostgresDataQuality(engine)
    assert store.list_imports(1, 1).items[0].id == second
    assert store.list_imports(2, 1).items[0].id == first
    assert store.list_imports(3, 1).items == []
    assert store.list_imports(3, 1).total == 2
    result = store.list_rejections(first, 1, 1, None)
    assert result.total == 2 and result.items[0].record_number == 1
    assert store.list_rejections(first, 2, 1, None).items[0].record_number == 3
    result = store.list_rejections(first, 1, 20, "INVALID_NUMBER")
    assert result.total == 1
    assert result.items[0].original_data == {"value": " bad "}
    assert store.list_rejections(first, 1, 20, "UNKNOWN_CODE").total == 0
    assert store.list_rejections(uuid4(), 1, 20, None) is None


def test_empty_history_and_import_without_rejections(database):
    engine, _ = database
    store = PostgresDataQuality(engine)
    assert store.list_imports(1, 20).total == 0
    with engine.begin() as conn:
        identifier = conn.execute(insert(ImportModel).values(
            source_system="SCADA_01", file_name="empty.csv", file_sha256="b" * 64,
        ).returning(ImportModel.id)).scalar_one()
    result = store.list_rejections(identifier, 1, 20, None)
    assert result.items == [] and result.total == 0
