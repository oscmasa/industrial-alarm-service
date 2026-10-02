from datetime import UTC, datetime
from decimal import Decimal

import pytest

from alarm_service.application.normalization.service import normalize_record


@pytest.fixture
def row():
    return {
        "event_id": "EVT-00000001",
        "occurred_at": "2026-09-15T14:32:10-05:00",
        "tag": "PUMP_01_FLOW",
        "alarm_code": "LOW_FLOW",
        "severity": "HIGH",
        "message": "Feed flow below limit",
        "value": "12.5",
    }


def codes(result):
    return {error.code for error in result.errors}


def test_normalization_is_lossless_and_does_not_mutate_input(row):
    row.update(tag=" pump_01_flow ", severity=" Alta ", value="12,5", event_id=" evt-00000001 ")
    result = normalize_record(row)
    assert result.accepted
    assert result.alarm.tag == "PUMP_01_FLOW"
    assert result.alarm.severity == "HIGH"
    assert result.alarm.value == Decimal("12.5")
    assert result.alarm.occurred_at == datetime(2026, 9, 15, 19, 32, 10, tzinfo=UTC)
    assert result.original_data == row
    assert row["tag"] == " pump_01_flow "
    row["tag"] = "CHANGED"
    assert result.original_data["tag"] == " pump_01_flow "


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-09-15T14:32:10-05:00",
        "2026-09-15T19:32:10Z",
        "2026-09-15T14:32:10",
        "2026-09-15 14:32:10",
        "15/09/2026 14:32:10",
    ],
)
def test_supported_dates_represent_same_instant(row, timestamp):
    row["occurred_at"] = timestamp
    assert normalize_record(row).alarm.occurred_at == datetime(2026, 9, 15, 19, 32, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-02-30T08:00:00",
        "2026-09-15",
        "09/15/2026 14:32:10",
        "1726400000",
        "20260915T143210",
        "2026-09-15T14:32:10.1234567",
        "2026-09-15T24:00:00",
        "2026-09-15T14:32:10+24:00",
    ],
)
def test_invalid_dates_are_not_guessed(row, timestamp):
    row["occurred_at"] = timestamp
    assert codes(normalize_record(row)) == {"INVALID_TIMESTAMP"}


def test_day_first_date_and_fractional_seconds(row):
    row["occurred_at"] = "01/02/2026 08:00:00"
    assert normalize_record(row).alarm.occurred_at.month == 2
    row["occurred_at"] = "2026-09-15T19:32:10.123456Z"
    assert normalize_record(row).alarm.occurred_at.microsecond == 123456


@pytest.mark.parametrize("missing", ["", "  ", "NULL", "None", "N/A", "nan", None])
def test_optional_missing_values_are_allowed(row, missing):
    row.update(message=missing, value=missing)
    result = normalize_record(row)
    assert result.accepted
    assert result.alarm.message is None and result.alarm.value is None
    assert not result.warnings


@pytest.mark.parametrize("field", ["event_id", "occurred_at", "tag", "alarm_code", "severity"])
def test_required_fields_are_not_invented(row, field):
    row[field] = "N/A"
    result = normalize_record(row)
    assert not result.accepted
    assert codes(result) == {"MISSING_REQUIRED_FIELD"}


@pytest.mark.parametrize(
    "value,expected",
    [("0", "0"), ("+12", "12"), ("12,5", "12.5"), ("0.000001", "0.000001"), ("12.5000000", "12.5")],
)
def test_numeric_conversion_preserves_value(row, value, expected):
    row["value"] = value
    assert normalize_record(row).alarm.value == Decimal(expected)


@pytest.mark.parametrize(
    "value,code",
    [
        ("twelve", "INVALID_VALUE"),
        ("1e3", "INVALID_VALUE"),
        ("Infinity", "INVALID_VALUE"),
        ("1,234.56", "INVALID_VALUE"),
        ("12 L/min", "INVALID_VALUE"),
        ("-1", "VALUE_OUT_OF_RANGE"),
        ("0.0000001", "INVALID_VALUE_PRECISION"),
        ("1000000000000", "INVALID_VALUE_PRECISION"),
    ],
)
def test_invalid_numbers_are_not_rounded_or_silently_dropped(row, value, code):
    row["value"] = value
    assert codes(normalize_record(row)) == {code}


def test_semantic_warnings_preserve_source_values(row):
    row.update(severity="LOW", value="80")
    result = normalize_record(row)
    assert result.accepted
    assert result.alarm.severity == "LOW" and result.alarm.value == Decimal("80")
    assert set(result.alarm.warnings) == {"SEVERITY_DIFFERS_FROM_DEFAULT", "VALUE_TRIGGER_MISMATCH"}


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({"tag": "UNKNOWN"}, "UNKNOWN_TAG"),
        ({"alarm_code": "UNKNOWN"}, "UNKNOWN_ALARM_CODE"),
        ({"alarm_code": "HIGH_TEMPERATURE"}, "INVALID_TAG_ALARM_COMBINATION"),
        ({"severity": "URGENT"}, "UNKNOWN_SEVERITY"),
        ({"event_id": "EVT-123"}, "INVALID_EVENT_ID"),
        ({"message": "x" * 501}, "MESSAGE_TOO_LONG"),
        ({"value": 12.5}, "INVALID_FIELD_TYPE"),
        ({"message": "bad\x00text"}, "INVALID_TEXT_CHARACTER"),
    ],
)
def test_catalog_and_field_errors(row, fields, expected):
    row.update(fields)
    assert expected in codes(normalize_record(row))


def test_bounds_and_zero_are_independent_of_trigger(row):
    row.update(tag="TANK_IN_01_LEVEL", alarm_code="LOW_LEVEL", value="100")
    assert normalize_record(row).accepted
    row["value"] = "100.01"
    assert codes(normalize_record(row)) == {"VALUE_OUT_OF_RANGE"}
    row.update(tag="PUMP_01_MOTOR_FAULT", alarm_code="MOTOR_FAULT", severity="CRITICAL", value="0")
    assert normalize_record(row).alarm.value == 0
    row["value"] = "2"
    assert codes(normalize_record(row)) == {"VALUE_OUT_OF_RANGE"}


def test_collects_independent_errors_and_skips_dependent_checks(row):
    row.update(tag="", occurred_at="", severity="", value="bad")
    result = normalize_record(row)
    assert len(result.errors) == 4
    assert not result.warnings


def test_invalid_column_shape_is_rejected(row):
    row["unexpected"] = "anything"
    assert codes(normalize_record(row)) == {"MALFORMED_ROW"}


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("LOW", "LOW"),
        ("BAJA", "LOW"),
        ("1", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("MEDIA", "MEDIUM"),
        ("2", "MEDIUM"),
        ("HIGH", "HIGH"),
        ("ALTA", "HIGH"),
        ("3", "HIGH"),
        ("CRITICAL", "CRITICAL"),
        ("CRITICA", "CRITICAL"),
        ("CRÍTICA", "CRITICAL"),
        ("4", "CRITICAL"),
    ],
)
def test_all_severity_aliases(row, alias, canonical):
    row["severity"] = f" {alias.lower()} "
    assert normalize_record(row).alarm.severity == canonical
