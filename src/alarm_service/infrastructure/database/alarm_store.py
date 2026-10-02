"""Bulk persistence adapter bound to one source, import, and transaction."""

import base64
import json
import uuid
from dataclasses import asdict

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from alarm_service.application.ports.alarm_store import RejectedRow
from alarm_service.domain.alarm import Alarm, Severity
from alarm_service.infrastructure.database.models import AlarmModel, RejectedRecordModel


def original_for_jsonb(original: dict) -> dict:
    serialized = json.dumps(original, ensure_ascii=True)
    if "\\u0000" in serialized:
        # PostgreSQL JSONB cannot represent NUL. Retain the entire original losslessly.
        return {
            "encoding": "base64-json-utf8",
            "payload": base64.b64encode(serialized.encode("utf-8")).decode("ascii"),
        }
    return original


class PostgresAlarmStore:
    def __init__(self, connection: Connection, source_system: str, import_id: uuid.UUID):
        self.connection = connection
        self.source_system = source_system
        self.import_id = import_id

    def find_events(self, event_ids: list[str]) -> dict[str, Alarm]:
        if not event_ids:
            return {}
        table = AlarmModel.__table__
        rows = self.connection.execute(
            select(table).where(
                table.c.source_system == self.source_system, table.c.event_id.in_(event_ids)
            )
        ).mappings()
        return {
            row["event_id"]: Alarm(
                row["event_id"],
                row["occurred_at"],
                row["tag_id"],
                row["alarm_code"],
                Severity(row["severity"]),
                row["message"],
                row["value"],
                tuple(row["warnings"]),
            )
            for row in rows
        }

    def insert_events(self, alarms: list[Alarm]) -> None:
        if alarms:
            self.connection.execute(
                insert(AlarmModel),
                [
                    dict(
                        source_system=self.source_system,
                        import_id=self.import_id,
                        event_id=alarm.event_id,
                        occurred_at=alarm.occurred_at,
                        tag_id=alarm.tag,
                        alarm_code=alarm.alarm_code,
                        severity=alarm.severity.value,
                        message=alarm.message,
                        value=alarm.value,
                        warnings=list(alarm.warnings),
                    )
                    for alarm in alarms
                ],
            )

    def insert_rejections(self, rows: list[RejectedRow]) -> None:
        if rows:
            self.connection.execute(
                insert(RejectedRecordModel),
                [
                    dict(
                        import_id=self.import_id,
                        record_number=row.record_number,
                        original_data=original_for_jsonb(row.original_data),
                        errors=[asdict(error) for error in row.errors],
                    )
                    for row in rows
                ],
            )
