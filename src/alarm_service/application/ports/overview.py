"""Read contracts for the historical overview, independent of HTTP and SQL."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from alarm_service.domain.alarm import Severity


@dataclass(frozen=True)
class OverviewQuery:
    start_time: datetime
    end_time: datetime
    severity: Severity | None = None
    tag: str | None = None
    alarm_code: str | None = None


@dataclass(frozen=True)
class EventDates:
    first_event: datetime | None
    last_event: datetime | None


@dataclass(frozen=True)
class DailySeverityCount:
    day: date
    severity: str
    event_count: int


@dataclass(frozen=True)
class OverviewSnapshot:
    dates: EventDates
    counts: list[DailySeverityCount]


class OverviewStore(Protocol):
    def available_dates(self) -> EventDates: ...

    def overview(self, query: OverviewQuery) -> OverviewSnapshot: ...
