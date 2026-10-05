import csv
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

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
        {"start_id": 0},
        {"start_id": -1},
        {"start_id": 100_000_000},
        {"start_id": 99_999_999},
        {"start_id": True},
        {"start_id": 1.5},
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


def test_offset_preserves_measurements_and_duplicate_provenance(tmp_path):
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    generate_dataset(first, rows=1000)
    summary = generate_dataset(second, rows=1000, start_id=10001)
    original_rows, offset_rows = load(first), load(second)
    manifest = json.loads(second.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert summary["start_id"] == 10001
    assert summary["end_id"] == 10980
    assert summary["next_start_id"] == 10981
    assert offset_rows[0]["event_id"] == "EVT-00010001"
    for original, shifted, record in zip(
        original_rows, offset_rows, manifest["records"], strict=True
    ):
        assert {key: value for key, value in original.items() if key != "event_id"} == {
            key: value for key, value in shifted.items() if key != "event_id"
        }
        if record["category"] == "duplicate":
            assert shifted == offset_rows[record["duplicate_of"] - 1]


def test_last_eight_digit_range_and_exhaustion(tmp_path):
    path = tmp_path / "last.csv"
    summary = generate_dataset(path, rows=100, start_id=99_999_902)
    assert summary["end_id"] == 99_999_999
    assert summary["next_start_id"] is None
    assert any(row["event_id"] == "EVT-99999999" for row in load(path))


@pytest.mark.parametrize("start_id,exit_code", [(10001, 0), (0, 2)])
def test_start_id_cli(tmp_path, start_id, exit_code):
    output = tmp_path / "cli.csv"
    command = Path(__file__).resolve().parents[2] / "scripts/generate_dataset.py"
    result = subprocess.run(
        [
            sys.executable,
            str(command),
            "--rows",
            "100",
            "--start-id",
            str(start_id),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == exit_code
    if exit_code == 0:
        assert json.loads(result.stdout)["start_id"] == start_id
        assert load(output)[0]["event_id"] == "EVT-00010001"
    else:
        assert "start_id" in result.stderr
        assert not output.exists()
