"""Real PostgreSQL checks; use a disposable schema, never production tables."""

import os
import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import insert, inspect, select
from sqlalchemy.exc import IntegrityError

from alarm_service.infrastructure.database.models import (
    AlarmModel,
    Base,
    EquipmentModel,
    ImportModel,
    RejectedRecordModel,
    TagModel,
)

URL = os.getenv("ALARM_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="ALARM_TEST_DATABASE_URL is required")


def populate(connection):
    import_id = uuid.uuid4()
    connection.execute(insert(EquipmentModel).values(id="PUMP_01", name="Feed pump"))
    connection.execute(
        insert(TagModel).values(id="PUMP_01_FLOW", equipment_id="PUMP_01", unit="L/min")
    )
    connection.execute(
        insert(ImportModel).values(
            id=import_id, source_system="SCADA_01", file_name="test.csv", file_sha256="a" * 64
        )
    )
    return dict(
        source_system="SCADA_01",
        event_id="EVT-00000001",
        import_id=import_id,
        occurred_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        tag_id="PUMP_01_FLOW",
        alarm_code="LOW_FLOW",
        severity="HIGH",
        value="12.5",
        warnings=["VALUE_TRIGGER_MISMATCH"],
    )


def test_migration_matches_models_and_can_be_reversed(database):
    engine, config = database
    with engine.begin() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert differences == []
        assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables) | {
            "alembic_version"
        }
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        assert "alarms" in inspect(connection).get_table_names()


def test_alarm_uniqueness_foreign_keys_severity_and_utc(database):
    engine, _ = database
    with engine.begin() as connection:
        alarm = populate(connection)
        connection.execute(insert(AlarmModel).values(**alarm))
        result = connection.execute(select(AlarmModel.occurred_at, AlarmModel.warnings)).one()
        assert result.occurred_at.utcoffset().total_seconds() == 0
        assert result.warnings == ["VALUE_TRIGGER_MISMATCH"]
        for overrides in (
            {},
            {"event_id": "EVT-00000002", "severity": "UNKNOWN"},
            {"event_id": "EVT-00000003", "tag_id": "UNKNOWN"},
            {"event_id": "EVT-00000004", "value": "-1"},
        ):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(insert(AlarmModel).values(**(alarm | overrides)))


def test_completed_import_requires_reconciled_counts_and_rejections(database):
    engine, _ = database
    with engine.begin() as connection:
        alarm = populate(connection)
        import_id = alarm["import_id"]
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                ImportModel.__table__.update()
                .where(ImportModel.id == import_id)
                .values(
                    status="COMPLETED", records_read=2, accepted=1, finished_at=datetime.now(UTC)
                )
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                insert(RejectedRecordModel).values(
                    import_id=import_id, record_number=1, original_data={}, errors=[]
                )
            )
        connection.execute(
            ImportModel.__table__.update()
            .where(ImportModel.id == import_id)
            .values(
                status="COMPLETED",
                records_read=2,
                accepted=1,
                rejected=1,
                finished_at=datetime.now(UTC),
            )
        )


def test_catalog_seed_is_idempotent(database):
    from alarm_service.infrastructure.database.seed import seed_catalog

    engine, _ = database
    with engine.begin() as connection:
        assert seed_catalog(connection) == (7, 12)
        assert seed_catalog(connection) == (0, 0)
