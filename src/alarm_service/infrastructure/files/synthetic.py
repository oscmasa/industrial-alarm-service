"""Generate reproducible test exports independently of the importer."""

import csv
import hashlib
import json
import random
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from alarm_service.domain.catalog import (
    CATALOG_VERSION,
    CONDITIONS,
    CSV_FIELDS,
    SEVERITIES,
    SEVERITY_ALIASES,
    SOURCE_SYSTEM,
    SOURCE_TIMEZONE,
)

RECOVERABLE = (
    "whitespace",
    "severity_alias",
    "day_first_date",
    "local_date",
    "decimal_comma",
    "optional_nulls",
    "lowercase",
    "utc_date",
)
INVALID = (
    "missing_timestamp",
    "missing_tag",
    "impossible_date",
    "unknown_tag",
    "unknown_severity",
    "invalid_number",
    "invalid_event_id",
    "unknown_alarm_code",
    "invalid_combination",
    "out_of_range",
    "long_message",
    "missing_severity",
    "missing_event_id",
    "missing_alarm_code",
    "multiple_missing",
    "invalid_boolean",
)
ERRORS = (
    "MISSING_REQUIRED_FIELD",
    "MISSING_REQUIRED_FIELD",
    "INVALID_TIMESTAMP",
    "UNKNOWN_TAG",
    "UNKNOWN_SEVERITY",
    "INVALID_VALUE",
    "INVALID_EVENT_ID",
    "UNKNOWN_ALARM_CODE",
    "INVALID_TAG_ALARM_COMBINATION",
    "VALUE_OUT_OF_RANGE",
    "MESSAGE_TOO_LONG",
    "MISSING_REQUIRED_FIELD",
    "MISSING_REQUIRED_FIELD",
    "MISSING_REQUIRED_FIELD",
    "MISSING_REQUIRED_FIELD",
    "VALUE_OUT_OF_RANGE",
)


def _windows(start: date, end: date):
    zone = ZoneInfo(SOURCE_TIMEZONE)
    return [
        datetime.combine(start + timedelta(days=day), time(6), zone)
        for day in range((end - start).days)
    ]


def _event(rng, number, condition, occurred_at):
    minimum = int(condition.sample_min * 100)
    maximum = int(condition.sample_max * 100)
    value = Decimal(rng.randint(minimum, maximum)) / 100
    return {
        "event_id": f"EVT-{number:08d}",
        "occurred_at": occurred_at.isoformat(),
        "tag": condition.tag,
        "alarm_code": condition.alarm_code,
        "severity": condition.default_severity,
        "message": condition.alarm_code.replace("_", " ").capitalize(),
        "value": format(value, ".2f"),
    }


def _recover(row, mutation):
    if mutation == "whitespace":
        for field in CSV_FIELDS:
            row[field] = f" {row[field]} "
    elif mutation == "severity_alias":
        row["severity"] = SEVERITY_ALIASES[row["severity"]][-1]
    elif mutation in ("day_first_date", "local_date"):
        fmt = "%d/%m/%Y %H:%M:%S" if mutation == "day_first_date" else "%Y-%m-%d %H:%M:%S"
        row["occurred_at"] = datetime.fromisoformat(row["occurred_at"]).strftime(fmt)
    elif mutation == "decimal_comma":
        row["value"] = row["value"].replace(".", ",")
    elif mutation == "optional_nulls":
        row["value"], row["message"] = "N/A", "null"
    elif mutation == "lowercase":
        for field in ("event_id", "tag", "alarm_code", "severity"):
            row[field] = row[field].lower()
    elif mutation == "utc_date":
        # A different, supported representation requiring conversion to UTC.
        row["occurred_at"] = (
            datetime.fromisoformat(row["occurred_at"])
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )


def _invalidate(row, mutation):
    replacements = {
        "missing_timestamp": ("occurred_at", ""),
        "missing_tag": ("tag", "N/A"),
        "impossible_date": ("occurred_at", "2026-02-30T08:00:00-05:00"),
        "unknown_tag": ("tag", "UNKNOWN_01_SIGNAL"),
        "unknown_severity": ("severity", "URGENT"),
        "invalid_number": ("value", "twelve"),
        "invalid_event_id": ("event_id", "123"),
        "unknown_alarm_code": ("alarm_code", "UNKNOWN_CONDITION"),
        "long_message": ("message", "x" * 501),
        "missing_severity": ("severity", ""),
        "missing_event_id": ("event_id", ""),
        "missing_alarm_code": ("alarm_code", ""),
    }
    if mutation in replacements:
        field, value = replacements[mutation]
        row[field] = value
    elif mutation == "invalid_combination":
        row.update(tag="PUMP_01_FLOW", alarm_code="HIGH_TEMPERATURE")
    elif mutation == "out_of_range":
        row["value"] = "-1"
    elif mutation == "multiple_missing":
        row.update(occurred_at="", tag="", severity="")
    elif mutation == "invalid_boolean":
        row.update(
            tag="PUMP_01_MOTOR_FAULT", alarm_code="MOTOR_FAULT", severity="CRITICAL", value="2"
        )


def generate_dataset(
    output: Path,
    *,
    rows: int = 10_000,
    seed: int = 42,
    start: date = date(2026, 9, 1),
    end: date = date(2026, 10, 1),
    recoverable_rate: Decimal = Decimal("0.10"),
    invalid_rate: Decimal = Decimal("0.03"),
    duplicate_rate: Decimal = Decimal("0.02"),
) -> dict:
    """Write CSV and audit manifest; end date is exclusive in plant local time."""
    if not 100 <= rows <= 1_000_000:
        raise ValueError("rows must be between 100 and 1,000,000")
    if not 1 <= (end - start).days <= 366:
        raise ValueError("date range must contain between 1 and 366 days")
    rates = (recoverable_rate, invalid_rate, duplicate_rate)
    if any(not rate.is_finite() or rate < 0 or rate > 1 for rate in rates) or sum(rates) > Decimal(
        "0.80"
    ):
        raise ValueError("rates must be finite, between 0 and 1, with total at most 0.80")
    counts = {
        "recoverable": int(rows * recoverable_rate),
        "invalid": int(rows * invalid_rate),
        "duplicate": int(rows * duplicate_rate),
    }
    counts["valid"] = rows - sum(counts.values())
    rng = random.Random(seed)
    windows = _windows(start, end)
    events, records = [], []
    # First cover every condition, then add linked scenarios. Ordering is stable.
    planned = [
        (condition, windows[0] + timedelta(minutes=i), None)
        for i, condition in enumerate(CONDITIONS)
    ]
    scenario_count = max(1, counts["valid"] // 500)
    for episode in range(scenario_count):
        base = rng.choice(windows) + timedelta(hours=rng.randrange(1, 12))
        scenario_id = f"supply-{episode:04d}"
        first = base + timedelta(minutes=rng.randint(1, 3))
        second = first + timedelta(minutes=rng.randint(10, 20))
        third = second + timedelta(minutes=rng.randint(1, 5))
        planned.extend(
            zip(
                (CONDITIONS[0], CONDITIONS[2], CONDITIONS[6], CONDITIONS[8]),
                (base, first, second, third),
                [scenario_id] * 4,
                strict=True,
            )
        )
        air_base = base + timedelta(minutes=40)
        planned.extend(
            (
                (CONDITIONS[12], air_base, f"air-{episode:04d}"),
                (
                    CONDITIONS[9],
                    air_base + timedelta(minutes=rng.randint(1, 3)),
                    f"air-{episode:04d}",
                ),
            )
        )

    for category in ("valid", "recoverable", "invalid"):
        for index in range(counts[category]):
            scenario_id = None
            if category == "valid" and index < len(planned):
                condition, timestamp, scenario_id = planned[index]
            else:
                condition = rng.choices(CONDITIONS, weights=[item.weight for item in CONDITIONS])[0]
                # Differential pressure episodes concentrate on every seventh day.
                candidates = windows[::7] if condition == CONDITIONS[4] else windows
                timestamp = rng.choice(candidates) + timedelta(seconds=rng.randrange(16 * 3600))
            row = _event(rng, len(events) + 1, condition, timestamp)
            mutations, errors, warnings = [], [], []
            if category == "recoverable":
                mutation = RECOVERABLE[index % len(RECOVERABLE)]
                _recover(row, mutation)
                mutations.append(mutation)
            elif category == "invalid":
                offset = index % len(INVALID)
                _invalidate(row, INVALID[offset])
                mutations.append(INVALID[offset])
                errors.append(ERRORS[offset])
            elif index >= len(planned) and index % 50 == 0:
                # Accepted but suspicious: never silently repair semantic data.
                if index % 100 == 0:
                    row["value"] = str(
                        condition.threshold - 1
                        if condition.operator == "gt"
                        else condition.threshold + 1
                        if condition.operator == "lt"
                        else 0
                    )
                    warnings.append("VALUE_TRIGGER_MISMATCH")
                else:
                    row["severity"] = SEVERITIES[
                        (SEVERITIES.index(condition.default_severity) + 1) % len(SEVERITIES)
                    ]
                    warnings.append("SEVERITY_DIFFERS_FROM_DEFAULT")
                mutations.extend(warnings)
            events.append(row)
            records.append(
                {
                    "record_number": len(events),
                    "category": category,
                    "expected_outcome": "rejected" if errors else "accepted",
                    "mutations": mutations,
                    "expected_errors": errors,
                    "expected_warnings": warnings,
                    "scenario_id": scenario_id,
                }
            )

    for _ in range(counts["duplicate"]):
        original = rng.randrange(counts["valid"])
        events.append(events[original].copy())
        records.append(
            {
                "record_number": len(events),
                "category": "duplicate",
                "expected_outcome": "duplicate",
                "duplicate_of": original + 1,
                "mutations": [],
                "expected_errors": [],
                "expected_warnings": [],
                "scenario_id": None,
            }
        )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(events)
    manifest = {
        "generator_version": "1.0",
        "catalog_version": CATALOG_VERSION,
        "source_system": SOURCE_SYSTEM,
        "source_timezone": SOURCE_TIMEZONE,
        "seed": seed,
        "rows": rows,
        "start_date": start.isoformat(),
        "end_date_exclusive": end.isoformat(),
        "rates": dict(zip(("recoverable", "invalid", "duplicate"), map(str, rates), strict=True)),
        "categories": counts,
        "expected_outcomes": dict(Counter(record["expected_outcome"] for record in records)),
        "accepted_with_warnings": sum(bool(record["expected_warnings"]) for record in records),
        "csv_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "records": records,
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {key: value for key, value in manifest.items() if key != "records"}
