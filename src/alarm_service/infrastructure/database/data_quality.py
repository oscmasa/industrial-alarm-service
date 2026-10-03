"""Bounded read-only audit queries with snapshot-consistent counts and pages."""
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine

from alarm_service.application.ports.data_quality import (
    ImportSummary,
    QualityPage,
    RejectedRecord,
)
from alarm_service.infrastructure.database.models import ImportModel, RejectedRecordModel


class PostgresDataQuality:
    def __init__(self, engine: Engine):
        self.engine = engine

    def list_imports(self, page: int, page_size: int) -> QualityPage:
        table = ImportModel.__table__
        # Operational exception details are not part of the public audit projection.
        columns = [table.c[name] for name in ImportSummary.__dataclass_fields__]
        rows_query = (
            select(*columns).order_by(table.c.started_at.desc(), table.c.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        with (
            self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
            conn.begin(),
        ):
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout = '10s'"))
            total = conn.scalar(select(func.count()).select_from(table))
            rows = conn.execute(rows_query).mappings().all()
        return QualityPage([ImportSummary(**row) for row in rows], total)

    def list_rejections(
        self, import_id: UUID, page: int, page_size: int, error_code: str | None
    ) -> QualityPage | None:
        table = RejectedRecordModel.__table__
        conditions = [table.c.import_id == import_id]
        if error_code is not None:
            conditions.append(table.c.errors.contains([{"code": error_code}]))
        rows_query = (
            select(table).where(*conditions).order_by(table.c.record_number, table.c.id)
            .offset((page - 1) * page_size).limit(page_size)
        )
        with (
            self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
            conn.begin(),
        ):
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout = '10s'"))
            if conn.scalar(select(ImportModel.id).where(ImportModel.id == import_id)) is None:
                return None
            total = conn.scalar(select(func.count()).select_from(table).where(*conditions))
            rows = conn.execute(rows_query).mappings().all()
        return QualityPage([RejectedRecord(**row) for row in rows], total)
