"""Read projections for import audit results, independent of HTTP and SQLAlchemy."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ImportSummary:
    id: UUID
    source_system: str
    file_name: str
    file_sha256: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    records_read: int
    accepted: int
    rejected: int
    duplicates: int
    accepted_with_warnings: int


@dataclass(frozen=True)
class RejectedRecord:
    id: int
    import_id: UUID
    record_number: int
    original_data: dict
    errors: list[dict]
    created_at: datetime


@dataclass(frozen=True)
class QualityPage:
    items: list[ImportSummary] | list[RejectedRecord]
    total: int


class DataQualityStore(Protocol):
    def list_imports(self, page: int, page_size: int) -> QualityPage: ...

    def list_rejections(
        self, import_id: UUID, page: int, page_size: int, error_code: str | None
    ) -> QualityPage | None: ...
