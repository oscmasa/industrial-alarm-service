"""Group accepted events in PostgreSQL rather than loading them into Python."""

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine

from alarm_service.application.ports.alarm_metrics import TagCount, TopTagsQuery
from alarm_service.infrastructure.database.models import AlarmModel


class PostgresAlarmMetrics:
    def __init__(self, engine: Engine):
        self.engine = engine

    def top_tags(self, query: TopTagsQuery) -> list[TagCount]:
        table = AlarmModel.__table__
        conditions = []
        if query.start_time is not None:
            conditions.append(table.c.occurred_at >= query.start_time)
        if query.end_time is not None:
            conditions.append(table.c.occurred_at < query.end_time)
        if query.severity is not None:
            conditions.append(table.c.severity == query.severity.value)
        count = func.count().label("event_count")
        statement = (
            select(table.c.tag_id.label("tag"), count)
            .where(*conditions)
            .group_by(table.c.tag_id)
            .order_by(count.desc(), table.c.tag_id.asc())
            .limit(query.limit)
        )
        with self.engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            rows = connection.execute(statement).all()
        return [TagCount(row.tag, row.event_count) for row in rows]
