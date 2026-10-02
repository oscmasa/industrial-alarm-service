import csv
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from alarm_service.domain.catalog import CSV_FIELDS
from alarm_service.infrastructure.database.import_runner import ImportFailed, run_import
from alarm_service.infrastructure.database.models import (
    AlarmModel,
    ImportModel,
    RejectedRecordModel,
)
from alarm_service.infrastructure.database.seed import seed_catalog
from alarm_service.infrastructure.files.synthetic import generate_dataset


def test_full_dataset_and_repeat_are_idempotent(database, tmp_path):
    engine, _ = database
    with engine.begin() as connection:
        seed_catalog(connection)
    path = tmp_path / "alarms.csv"
    generate_dataset(path)
    first = run_import(engine, path, batch_size=257)
    assert (
        first["accepted"],
        first["rejected"],
        first["duplicates"],
        first["accepted_with_warnings"],
    ) == (9500, 300, 200, 167)
    second = run_import(engine, path, batch_size=5000)
    assert (second["accepted"], second["rejected"], second["duplicates"]) == (0, 300, 9700)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(AlarmModel)) == 9500
        assert connection.scalar(select(func.count()).select_from(RejectedRecordModel)) == 600
        assert connection.scalar(select(func.count()).select_from(ImportModel)) == 2
        assert (
            connection.scalar(
                select(func.count()).select_from(AlarmModel).where(AlarmModel.warnings != [])
            )
            == 167
        )


def test_file_failure_rolls_back_previous_batches(database, tmp_path):
    engine, _ = database
    with engine.begin() as connection:
        seed_catalog(connection)
    path = tmp_path / "broken.csv"
    path.write_text(
        ",".join(CSV_FIELDS)
        + "\nEVT-00000001,2026-09-15T12:00:00,PUMP_01_FLOW,LOW_FLOW,HIGH,Low flow,12.5\n"
        '"unfinished',
        encoding="utf-8",
    )
    with pytest.raises(ImportFailed):
        run_import(engine, path, batch_size=1)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(AlarmModel)) == 0
        assert connection.scalar(select(func.count()).select_from(RejectedRecordModel)) == 0
        assert connection.scalar(select(ImportModel.status)) == "FAILED"


def test_concurrent_source_imports_do_not_duplicate(database, tmp_path):
    engine, _ = database
    with engine.begin() as connection:
        seed_catalog(connection)
    path = tmp_path / "alarms.csv"
    generate_dataset(path, rows=100)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run_import(engine, path), range(2)))
    assert sorted(result["accepted"] for result in results) == [0, 95]
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(AlarmModel)) == 95


def test_conflict_and_nul_rejection_preserve_original(database, tmp_path):
    engine, _ = database
    with engine.begin() as connection:
        seed_catalog(connection)
    path = tmp_path / "conflict.csv"
    initial = dict(
        event_id="EVT-00000001",
        occurred_at="2026-09-15T12:00:00",
        tag="PUMP_01_FLOW",
        alarm_code="LOW_FLOW",
        severity="HIGH",
        message="Low flow",
        value="12.5",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(
            [
                initial,
                initial | {"value": "15"},
                initial | {"event_id": "EVT-00000002", "message": "bad\x00text"},
            ]
        )
    result = run_import(engine, path, batch_size=1)
    assert (result["accepted"], result["rejected"]) == (1, 2)
    with engine.connect() as connection:
        errors = (
            connection.execute(
                select(RejectedRecordModel.errors).order_by(RejectedRecordModel.record_number)
            )
            .scalars()
            .all()
        )
        assert [row[0]["code"] for row in errors] == [
            "DUPLICATE_CONFLICT",
            "INVALID_TEXT_CHARACTER",
        ]
        encoded = connection.scalar(
            select(RejectedRecordModel.original_data).where(RejectedRecordModel.record_number == 3)
        )
        assert encoded["encoding"] == "base64-json-utf8"
