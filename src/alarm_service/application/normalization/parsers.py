"""Explicit, lossless parsing rules for the legacy source contract."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from alarm_service.domain.catalog import SOURCE_TIMEZONE

MISSING_VALUES = frozenset(("", "null", "none", "n/a", "nan"))
LOCAL_ZONE = ZoneInfo(SOURCE_TIMEZONE)
ISO_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])?"
)
LOCAL_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2} (?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
)
DAY_FIRST_TIMESTAMP = re.compile(
    r"[0-9]{2}/[0-9]{2}/[0-9]{4} (?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
)
NUMBER = re.compile(r"[+-]?[0-9]+(?:[.,][0-9]+)?")


class ParsingError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParsingError("INVALID_FIELD_TYPE", "Expected a CSV text field.")
    if "\x00" in value:
        raise ParsingError("INVALID_TEXT_CHARACTER", "NUL characters cannot be stored.")
    cleaned = value.strip()
    return None if cleaned.casefold() in MISSING_VALUES else cleaned


def parse_timestamp(value: str) -> datetime:
    try:
        if ISO_TIMESTAMP.fullmatch(value):
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif LOCAL_TIMESTAMP.fullmatch(value):
            timestamp = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        elif DAY_FIRST_TIMESTAMP.fullmatch(value):
            timestamp = datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
        else:
            raise ValueError("unsupported format")
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=LOCAL_ZONE)
        return timestamp.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ParsingError("INVALID_TIMESTAMP", "Invalid or unsupported timestamp.") from exc


def parse_value(value: str) -> Decimal:
    if not NUMBER.fullmatch(value):
        raise ParsingError(
            "INVALID_VALUE", "Expected a decimal without units or grouping separators."
        )
    result = Decimal(value.replace(",", "."))
    if result < 0:
        raise ParsingError("VALUE_OUT_OF_RANGE", "Measurements must be nonnegative.")
    fraction = value.replace(",", ".").partition(".")[2].rstrip("0")
    if result >= Decimal("1000000000000") or len(fraction) > 6:
        raise ParsingError(
            "INVALID_VALUE_PRECISION", "Value does not fit NUMERIC(18, 6) without rounding."
        )
    return result
