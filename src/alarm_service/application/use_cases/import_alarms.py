"""Bounded-memory import orchestration independent of files and SQLAlchemy."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import islice

from alarm_service.application.normalization.contracts import Issue
from alarm_service.application.normalization.service import normalize_record
from alarm_service.application.ports.alarm_store import AlarmStore, RejectedRow


@dataclass
class ImportCounts:
    records_read: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    accepted_with_warnings: int = 0


def import_records(
    records: Iterable[tuple[int, Mapping[str, object]]],
    store: AlarmStore,
    *,
    batch_size: int = 1000,
    counts: ImportCounts | None = None,
) -> ImportCounts:
    if not 1 <= batch_size <= 5000:
        raise ValueError("batch_size must be between 1 and 5000")
    totals = counts if counts is not None else ImportCounts()
    iterator = iter(records)
    while batch := list(islice(iterator, batch_size)):
        results = [(number, normalize_record(row)) for number, row in batch]
        known = store.find_events(
            [result.alarm.event_id for _, result in results if result.accepted]
        )
        accepted, rejected = [], []
        for number, result in results:
            totals.records_read += 1
            if not result.accepted:
                rejected.append(RejectedRow(number, result.original_data, result.errors))
                totals.rejected += 1
                continue
            alarm = result.alarm
            previous = known.get(alarm.event_id)
            if previous is None:
                known[alarm.event_id] = alarm
                accepted.append(alarm)
                totals.accepted += 1
                totals.accepted_with_warnings += bool(alarm.warnings)
            elif (
                previous.event_id,
                previous.occurred_at,
                previous.tag,
                previous.alarm_code,
                previous.severity,
                previous.message,
                previous.value,
            ) == (
                alarm.event_id,
                alarm.occurred_at,
                alarm.tag,
                alarm.alarm_code,
                alarm.severity,
                alarm.message,
                alarm.value,
            ):
                # Derived warnings and import metadata do not define event identity.
                totals.duplicates += 1
            else:
                rejected.append(
                    RejectedRow(
                        number,
                        result.original_data,
                        (
                            Issue(
                                "event_id",
                                "DUPLICATE_CONFLICT",
                                "Existing source event differs; original retained.",
                            ),
                        ),
                    )
                )
                totals.rejected += 1
        store.insert_events(accepted)
        store.insert_rejections(rejected)
    assert totals.records_read == totals.accepted + totals.rejected + totals.duplicates
    return totals
