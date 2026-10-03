"""Read-only snapshot with indexed time bounds and PostgreSQL daily grouping."""

from datetime import timedelta

from sqlalchemy import Date, cast, func, select, text
from sqlalchemy.engine import Engine

from alarm_service.application.ports.overview import (
    DailySeverityCount,
    EventDates,
    OverviewQuery,
    OverviewSnapshot,
)
from alarm_service.infrastructure.database.models import AlarmModel


class PostgresOverview:
    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _dates(connection) -> EventDates:
        column = AlarmModel.occurred_at
        first = connection.scalar(select(column).order_by(column).limit(1))
        last = connection.scalar(select(column).order_by(column.desc()).limit(1))
        return EventDates(first, last)

    def available_dates(self) -> EventDates:
        with (
            self.engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            return self._dates(connection)

    def overview(self, query: OverviewQuery) -> OverviewSnapshot:
        duration = query.end_time - query.start_time
        lower = min(query.start_time - duration, query.start_time - timedelta(days=6))
        table = AlarmModel.__table__
        day = cast(func.timezone("America/Bogota", table.c.occurred_at), Date).label("day")
        conditions = [table.c.occurred_at >= lower, table.c.occurred_at < query.end_time]
        if query.severity is not None:
            conditions.append(table.c.severity == query.severity.value)
        if query.tag is not None:
            conditions.append(table.c.tag_id == query.tag)
        if query.alarm_code is not None:
            conditions.append(table.c.alarm_code == query.alarm_code)
        statement = (
            select(day, table.c.severity, func.count().label("event_count"))
            .where(*conditions)
            .group_by(day, table.c.severity)
            .order_by(day)
        )
        with (
            self.engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            dates = self._dates(connection)
            rows = connection.execute(statement).all()
        return OverviewSnapshot(
            dates, [DailySeverityCount(row.day, row.severity, row.event_count) for row in rows]
        )
