"""Indexed alarm queries using one read-only repeatable-read snapshot."""

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine

from alarm_service.application.ports.alarm_query import AlarmPage, AlarmQuery, AlarmRecord
from alarm_service.domain.alarm import Alarm, Severity
from alarm_service.infrastructure.database.models import AlarmModel


class PostgresAlarmQuery:
    def __init__(self, engine: Engine):
        self.engine = engine

    def list_alarms(self, query: AlarmQuery) -> AlarmPage:
        table = AlarmModel.__table__
        conditions = []
        if query.start_time is not None:
            conditions.append(table.c.occurred_at >= query.start_time)
        if query.end_time is not None:
            conditions.append(table.c.occurred_at < query.end_time)
        if query.severity is not None:
            conditions.append(table.c.severity == query.severity.value)
        if query.tag is not None:
            conditions.append(table.c.tag_id == query.tag)
        count_query = select(func.count()).select_from(table).where(*conditions)
        rows_query = (
            select(table)
            .where(*conditions)
            .order_by(table.c.occurred_at.desc(), table.c.id.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        with (
            self.engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            total = connection.scalar(count_query)
            rows = connection.execute(rows_query).mappings().all()
        items = [
            AlarmRecord(
                row["id"],
                row["source_system"],
                row["import_id"],
                Alarm(
                    row["event_id"],
                    row["occurred_at"],
                    row["tag_id"],
                    row["alarm_code"],
                    Severity(row["severity"]),
                    row["message"],
                    row["value"],
                    tuple(row["warnings"]),
                ),
            )
            for row in rows
        ]
        return AlarmPage(items, total, query.page, query.page_size)
