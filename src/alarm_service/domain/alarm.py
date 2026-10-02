"""Normalized alarm entities, independent of HTTP and persistence libraries."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Alarm:
    event_id: str
    occurred_at: datetime
    tag: str
    alarm_code: str
    severity: Severity
    message: str | None
    value: Decimal | None
    warnings: tuple[str, ...] = ()
