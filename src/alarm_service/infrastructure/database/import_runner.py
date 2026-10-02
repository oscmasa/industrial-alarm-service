"""Atomic file import with durable run audit and source-scoped concurrency lock."""

import hashlib
import re
import uuid
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import func, insert, text, update
from sqlalchemy.engine import Engine

from alarm_service.application.use_cases.import_alarms import ImportCounts, import_records
from alarm_service.domain.catalog import SOURCE_SYSTEM
from alarm_service.infrastructure.database.alarm_store import PostgresAlarmStore
from alarm_service.infrastructure.database.models import ImportModel
from alarm_service.infrastructure.files.csv_reader import iter_csv_records


class ImportFailed(RuntimeError):
    def __init__(self, import_id: uuid.UUID, cause: str):
        super().__init__(
            f"Import {import_id} failed ({cause}); all event/rejection writes were rolled back."
        )
        self.import_id = import_id


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_import(
    engine: Engine, path: Path, *, source_system: str = SOURCE_SYSTEM, batch_size: int = 1000
) -> dict:
    path = Path(path)
    if not re.fullmatch(r"[A-Z0-9_-]{1,64}", source_system):
        raise ValueError(
            "source_system must contain 1-64 characters: A-Z, 0-9, underscore or hyphen"
        )
    if not 1 <= batch_size <= 5000:
        raise ValueError("batch_size must be between 1 and 5000")
    if len(path.name) > 255:
        raise ValueError("file name must not exceed 255 characters")
    sha256 = checksum(path)
    import_id = uuid.uuid4()
    counts = ImportCounts()
    with engine.begin() as connection:
        connection.execute(
            insert(ImportModel).values(
                id=import_id,
                source_system=source_system,
                file_name=path.name,
                file_sha256=sha256,
                status="RUNNING",
            )
        )
    try:
        with engine.begin() as connection:
            # Serialize imports per source; uniqueness also remains enforced by PostgreSQL.
            connection.execute(text("SET LOCAL lock_timeout = '30s'"))
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:source, 0))"),
                {"source": source_system},
            )
            store = PostgresAlarmStore(connection, source_system, import_id)
            import_records(iter_csv_records(path), store, batch_size=batch_size, counts=counts)
            if checksum(path) != sha256:
                raise ValueError("Source file changed during import")
            connection.execute(
                update(ImportModel)
                .where(ImportModel.id == import_id)
                .values(status="COMPLETED", finished_at=func.clock_timestamp(), **asdict(counts))
            )
    except Exception as exc:
        # Failed run retains an audit row, but no partially inserted events/rejections.
        with engine.begin() as connection:
            connection.execute(
                update(ImportModel)
                .where(ImportModel.id == import_id)
                .values(
                    status="FAILED",
                    finished_at=func.clock_timestamp(),
                    records_read=counts.records_read,
                    error_message=f"{type(exc).__name__}: atomic import rolled back.",
                )
            )
        raise ImportFailed(import_id, type(exc).__name__) from exc
    return {
        "import_id": str(import_id),
        "status": "COMPLETED",
        "source_system": source_system,
        "file_sha256": sha256,
        **asdict(counts),
    }
