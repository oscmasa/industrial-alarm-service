"""Pure row normalization: no database, CSV I/O, or generator manifest access."""

import re
from collections.abc import Mapping
from copy import deepcopy

from pydantic import ValidationError

from alarm_service.application.normalization.contracts import (
    Issue,
    NormalizationResult,
    NormalizedFields,
)
from alarm_service.application.normalization.parsers import (
    ParsingError,
    clean_text,
    parse_timestamp,
    parse_value,
)
from alarm_service.domain.alarm import Severity
from alarm_service.domain.catalog import CONDITIONS, CSV_FIELDS, SEVERITY_ALIASES

REQUIRED = frozenset(("event_id", "occurred_at", "tag", "alarm_code", "severity"))
TAG_CONDITIONS = {(item.tag, item.alarm_code): item for item in CONDITIONS}
TAGS = {item.tag: item for item in CONDITIONS}
ALARM_CODES = frozenset(item.alarm_code for item in CONDITIONS)
ALIASES = {
    alias: Severity(canonical)
    for canonical, aliases in SEVERITY_ALIASES.items()
    for alias in aliases
}


def normalize_record(record: Mapping[str, object]) -> NormalizationResult:
    original = deepcopy(dict(record))
    errors: list[Issue] = []
    warnings: list[Issue] = []
    cleaned = {}

    if set(record) != set(CSV_FIELDS):
        return NormalizationResult(
            None, (Issue("row", "MALFORMED_ROW", "Unexpected or missing columns."),), (), original
        )

    for field in CSV_FIELDS:
        try:
            cleaned[field] = clean_text(record[field])
        except ParsingError as exc:
            errors.append(Issue(field, exc.code, str(exc)))
            cleaned[field] = None
            continue
        if field in REQUIRED and cleaned[field] is None:
            errors.append(Issue(field, "MISSING_REQUIRED_FIELD", "Required field is missing."))
    for field in ("event_id", "tag", "alarm_code", "severity"):
        if cleaned[field] is not None:
            cleaned[field] = cleaned[field].upper()

    event_id = cleaned["event_id"]
    if event_id is not None and not re.fullmatch(r"EVT-[0-9]{8}", event_id):
        errors.append(
            Issue("event_id", "INVALID_EVENT_ID", "Expected EVT- followed by eight digits.")
        )

    timestamp, value, severity = None, None, None
    for field, parser in (("occurred_at", parse_timestamp), ("value", parse_value)):
        if cleaned[field] is not None:
            try:
                parsed = parser(cleaned[field])
                if field == "occurred_at":
                    timestamp = parsed
                else:
                    value = parsed
            except ParsingError as exc:
                errors.append(Issue(field, exc.code, str(exc)))

    if cleaned["severity"] is not None:
        severity = ALIASES.get(cleaned["severity"])
        if severity is None:
            errors.append(Issue("severity", "UNKNOWN_SEVERITY", "Unknown severity alias."))
    tag, code = cleaned["tag"], cleaned["alarm_code"]
    if tag is not None and tag not in TAGS:
        errors.append(Issue("tag", "UNKNOWN_TAG", "Tag is not in the source catalog."))
    if code is not None and code not in ALARM_CODES:
        errors.append(Issue("alarm_code", "UNKNOWN_ALARM_CODE", "Unknown alarm condition."))
    condition = TAG_CONDITIONS.get((tag, code))
    if tag in TAGS and code in ALARM_CODES and condition is None:
        errors.append(
            Issue(
                "alarm_code",
                "INVALID_TAG_ALARM_COMBINATION",
                "Condition is not allowed for this tag.",
            )
        )
    if value is not None and tag in TAGS:
        unit = TAGS[tag].unit
        if (unit == "%" and value > 100) or (unit == "boolean" and value not in (0, 1)):
            errors.append(
                Issue("value", "VALUE_OUT_OF_RANGE", "Value is outside the signal domain.")
            )
            value = None  # Do not issue a trigger warning for an invalid measurement.
    if condition is not None:
        if severity is not None and severity.value != condition.default_severity:
            warnings.append(
                Issue(
                    "severity",
                    "SEVERITY_DIFFERS_FROM_DEFAULT",
                    "Source priority differs from the catalog default; original priority retained.",
                )
            )
        if value is not None and not condition.trigger_matches(value):
            warnings.append(
                Issue(
                    "value",
                    "VALUE_TRIGGER_MISMATCH",
                    "Captured measurement does not match the synthetic trigger; value retained.",
                )
            )
    if cleaned["message"] is not None and len(cleaned["message"]) > 500:
        errors.append(
            Issue("message", "MESSAGE_TOO_LONG", "Maximum message length is 500 characters.")
        )
    if errors:
        return NormalizationResult(None, tuple(errors), tuple(warnings), original)

    try:
        validated = NormalizedFields(
            event_id=event_id,
            occurred_at=timestamp,
            tag=tag,
            alarm_code=code,
            severity=severity,
            message=cleaned["message"],
            value=value,
        )
    except ValidationError as exc:
        issues = tuple(
            Issue(
                str(error["loc"][0]),
                "INVALID_NORMALIZED_FIELD",
                "Normalized field violates the typed contract.",
            )
            for error in exc.errors()
        )
        return NormalizationResult(None, issues, tuple(warnings), original)
    return NormalizationResult(
        validated.to_alarm(tuple(issue.code for issue in warnings)), (), tuple(warnings), original
    )
