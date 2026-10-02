from dataclasses import replace
from decimal import Decimal

import pytest

from alarm_service.application.use_cases.import_alarms import import_records


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
