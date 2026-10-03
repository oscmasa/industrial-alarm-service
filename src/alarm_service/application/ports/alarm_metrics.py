"""Port for aggregated alarm activation counts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from alarm_service.domain.alarm import Severity


@dataclass(frozen=True)
class TopTagsQuery:
    start_time: datetime | None = None
    end_time: datetime | None = None
    severity: Severity | None = None
    limit: int = 10
    tag: str | None = None
    alarm_code: str | None = None


@dataclass(frozen=True)
class TagCount:
    tag: str
    event_count: int


class AlarmMetricsStore(Protocol):
    def top_tags(self, query: TopTagsQuery) -> list[TagCount]: ...
