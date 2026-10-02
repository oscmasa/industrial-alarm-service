"""Regression against generated corruption evidence; no manifest passed to normalizer."""

import json
from collections import Counter

from alarm_service.application.normalization.service import normalize_record
from alarm_service.infrastructure.files.csv_reader import iter_csv_records
from alarm_service.infrastructure.files.synthetic import generate_dataset


def test_normalizer_independently_matches_generator_manifest(tmp_path):
    path = tmp_path / "alarms.csv"
    generate_dataset(path)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    counts = Counter()
    warning_count = 0
    for (number, row), expected in zip(iter_csv_records(path), manifest["records"], strict=True):
        result = normalize_record(row)
        assert number == expected["record_number"]
        if expected["category"] == "duplicate":
            assert result.accepted  # Deduplication is a separate import concern.
            counts["valid_duplicate_rows"] += 1
        elif expected["expected_outcome"] == "rejected":
            assert not result.accepted
            assert set(expected["expected_errors"]) <= {issue.code for issue in result.errors}
            counts["rejected"] += 1
        else:
            assert result.accepted
            assert set(result.alarm.warnings) == set(expected["expected_warnings"])
            counts["accepted_unique"] += 1
            warning_count += bool(result.warnings)
    assert counts == {"accepted_unique": 9500, "rejected": 300, "valid_duplicate_rows": 200}
    assert warning_count == 167
