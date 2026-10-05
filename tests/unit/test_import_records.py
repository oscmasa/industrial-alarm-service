from dataclasses import replace
from decimal import Decimal

import pytest

from alarm_service.application.use_cases.import_alarms import import_records
from alarm_service.infrastructure.files.csv_reader import iter_csv_records
from alarm_service.infrastructure.files.synthetic import generate_dataset


class MemoryStore:
    def __init__(self):
        self.alarms = {}
        self.rejections = []
        self.batch_sizes = []

    def find_events(self, ids):
        self.batch_sizes.append(len(ids))
        return {key: self.alarms[key] for key in ids if key in self.alarms}

    def insert_events(self, alarms):
        self.alarms.update({alarm.event_id: alarm for alarm in alarms})

    def insert_rejections(self, rejections):
        self.rejections.extend(rejections)


def row(event_id="EVT-00000001", **changes):
    return (
        dict(
            event_id=event_id,
            occurred_at="2026-09-15T14:32:10-05:00",
            tag="PUMP_01_FLOW",
            alarm_code="LOW_FLOW",
            severity="HIGH",
            message="Low flow",
            value="12.5",
        )
        | changes
    )


@pytest.mark.parametrize("size", [1, 2, 1000])
def test_first_valid_wins_across_batches_and_repeated_loads(size):
    store = MemoryStore()
    records = list(
        enumerate(
            [
                row(occurred_at=""),
                row(),
                row(severity="Alta", value="12,5", occurred_at="2026-09-15T19:32:10Z"),
                row(value="15"),
                row("EVT-00000002", message="", value=""),
            ],
            1,
        )
    )
    counts = import_records(records, store, batch_size=size)
    assert (counts.records_read, counts.accepted, counts.rejected, counts.duplicates) == (
        5,
        2,
        2,
        1,
    )
    assert store.alarms["EVT-00000001"].value == Decimal("12.5")
    assert store.rejections[-1].errors[0].code == "DUPLICATE_CONFLICT"
    assert max(store.batch_sizes) <= size
    repeat = import_records(records, store, batch_size=size)
    assert (repeat.accepted, repeat.rejected, repeat.duplicates) == (0, 2, 3)


def test_derived_warnings_do_not_define_identity():
    store = MemoryStore()
    import_records([(1, row())], store)
    alarm = store.alarms["EVT-00000001"]
    store.alarms[alarm.event_id] = replace(alarm, warnings=("OTHER_CATALOG_WARNING",))
    counts = import_records([(1, row())], store)
    assert counts.duplicates == 1


@pytest.mark.parametrize("size", [0, 5001])
def test_batch_size_bounds(size):
    with pytest.raises(ValueError):
        import_records([], MemoryStore(), batch_size=size)


def test_warning_count_only_includes_new_events():
    store = MemoryStore()
    counts = import_records(
        [(1, row(severity="LOW", value="80")), (2, row(severity="LOW", value="80"))], store
    )
    assert (counts.accepted, counts.accepted_with_warnings, counts.duplicates) == (1, 1, 1)


def test_nul_original_is_preserved_losslessly():
    import base64
    import json

    from alarm_service.infrastructure.database.alarm_store import original_for_jsonb

    original = row(message="bad\x00text")
    encoded = original_for_jsonb(original)
    assert encoded["encoding"] == "base64-json-utf8"
    assert json.loads(base64.b64decode(encoded["payload"])) == original


def test_generated_exports_with_disjoint_ids_accumulate_and_reimport(tmp_path):
    store = MemoryStore()
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    summary = generate_dataset(first, rows=100)
    generate_dataset(second, rows=100, start_id=summary["next_start_id"], seed=99)
    for path in (first, second):
        counts = import_records(iter_csv_records(path), store, batch_size=17)
        assert (counts.accepted, counts.rejected, counts.duplicates) == (95, 3, 2)
    assert len(store.alarms) == 190
    repeat = import_records(iter_csv_records(second), store, batch_size=31)
    assert (repeat.accepted, repeat.rejected, repeat.duplicates) == (0, 3, 97)
    assert len(store.alarms) == 190
