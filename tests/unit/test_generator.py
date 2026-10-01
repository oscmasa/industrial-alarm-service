import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from alarm_service.domain.catalog import CONDITIONS, CSV_FIELDS, EQUIPMENT
from alarm_service.infrastructure.files.synthetic import INVALID, RECOVERABLE, generate_dataset


def load(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_default_counts_and_reproducible_files(tmp_path):
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    summary = generate_dataset(first)
    generate_dataset(second)
    assert first.read_bytes() == second.read_bytes()
    assert (
        first.with_suffix(".manifest.json").read_bytes()
        == second.with_suffix(".manifest.json").read_bytes()
    )
    assert summary["categories"] == {
        "valid": 8500,
        "recoverable": 1000,
        "invalid": 300,
        "duplicate": 200,
    }
    assert summary["expected_outcomes"] == {"accepted": 9500, "rejected": 300, "duplicate": 200}
    assert summary["csv_sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    rows = load(first)
    assert len(rows) == 10000
    assert tuple(rows[0]) == CSV_FIELDS
    assert len({row["event_id"] for row in rows[:8500]}) == 8500


def test_catalog_dates_values_and_duplicate_provenance(tmp_path):
    path = tmp_path / "alarms.csv"
    generate_dataset(path, rows=1000)
    rows = load(path)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    catalog = {(item.tag, item.alarm_code): item for item in CONDITIONS}
    covered = set()
    for row, record in zip(rows, manifest["records"], strict=True):
        if record["category"] == "valid":
            condition = catalog[row["tag"], row["alarm_code"]]
            covered.add((row["tag"], row["alarm_code"]))
            timestamp = datetime.fromisoformat(row["occurred_at"])
            assert timestamp.utcoffset().total_seconds() == -18000
            assert date(2026, 9, 1) <= timestamp.date() < date(2026, 10, 1)
            assert 6 <= timestamp.hour < 22
            value = Decimal(row["value"])
            assert value.is_finite() and value >= 0
            if not record["expected_warnings"]:
                assert condition.trigger_matches(value)
                assert row["severity"] == condition.default_severity
        elif record["category"] == "duplicate":
            original = record["duplicate_of"]
            assert original < record["record_number"]
            assert row == rows[original - 1]
        elif record["category"] == "invalid":
            assert record["expected_errors"]
    assert covered == set(catalog)
    assert len(EQUIPMENT) == 7
    assert len({condition.tag for condition in CONDITIONS}) == 12


def test_mutation_coverage_and_temporal_scenarios(tmp_path):
    path = tmp_path / "alarms.csv"
    generate_dataset(path, rows=1000)
    rows = load(path)
    records = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))["records"]
    mutations = {mutation for record in records for mutation in record["mutations"]}
    assert set(INVALID) | set(RECOVERABLE) <= mutations
    assert {"VALUE_TRIGGER_MISMATCH", "SEVERITY_DIFFERS_FROM_DEFAULT"} <= mutations
    scenarios = {}
    for row, record in zip(rows, records, strict=True):
        if record["scenario_id"]:
            scenarios.setdefault(record["scenario_id"], []).append(
                datetime.fromisoformat(row["occurred_at"])
            )
    for scenario, timestamps in scenarios.items():
        gaps = [
            (right - left).total_seconds() / 60
            for left, right in zip(timestamps, timestamps[1:], strict=False)
        ]
        if scenario.startswith("supply"):
            assert len(timestamps) == 4
            assert 1 <= gaps[0] <= 3 and 10 <= gaps[1] <= 20 and 1 <= gaps[2] <= 5
        else:
            assert len(timestamps) == 2 and 1 <= gaps[0] <= 3


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rows": 99},
        {"rows": 1000001},
        {"end": date(2026, 9, 1)},
        {"invalid_rate": Decimal("NaN")},
        {"duplicate_rate": Decimal("-0.1")},
        {"recoverable_rate": Decimal("0.9")},
    ],
)
def test_invalid_generation_options_do_not_create_output(tmp_path, kwargs):
    path = tmp_path / "alarms.csv"
    with pytest.raises(ValueError):
        generate_dataset(path, **kwargs)
    assert not path.exists()


def test_configurable_rates_and_period(tmp_path):
    path = tmp_path / "alarms.csv"
    summary = generate_dataset(
        path,
        rows=100,
        start=date(2025, 1, 1),
        end=date(2025, 1, 2),
        invalid_rate=Decimal("0.10"),
        duplicate_rate=Decimal("0.05"),
    )
    assert summary["categories"] == {"valid": 75, "recoverable": 10, "invalid": 10, "duplicate": 5}
    assert sum(summary["expected_outcomes"].values()) == 100
    generate_dataset(tmp_path / "other.csv", rows=100, seed=43)
    assert path.read_bytes() != (tmp_path / "other.csv").read_bytes()
