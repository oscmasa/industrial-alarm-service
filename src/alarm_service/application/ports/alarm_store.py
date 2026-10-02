"""Persistence port used by the batch import use case."""

from dataclasses import dataclass
from typing import Protocol

from alarm_service.application.normalization.contracts import Issue
from alarm_service.domain.alarm import Alarm


@dataclass(frozen=True)
class RejectedRow:
    record_number: int
    original_data: dict
    errors: tuple[Issue, ...]


class AlarmStore(Protocol):
    def find_events(self, event_ids: list[str]) -> dict[str, Alarm]: ...
    def insert_events(self, alarms: list[Alarm]) -> None: ...
    def insert_rejections(self, rows: list[RejectedRow]) -> None: ...
