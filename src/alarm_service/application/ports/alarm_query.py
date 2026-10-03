"""Read port and typed query values for alarm listing."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from alarm_service.domain.alarm import Alarm, Severity


@dataclass(frozen=True)
class AlarmQuery:
    start_time: datetime | None = None
    end_time: datetime | None = None
    severity: Severity | None = None
    tag: str | None = None
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True)
class AlarmRecord:
    id: int
    source_system: str
    import_id: uuid.UUID
    alarm: Alarm
    unit: str | None = None


@dataclass(frozen=True)
class AlarmPage:
    items: list[AlarmRecord]
    total: int
    page: int
    page_size: int


class AlarmQueryStore(Protocol):
    def list_alarms(self, query: AlarmQuery) -> AlarmPage: ...
