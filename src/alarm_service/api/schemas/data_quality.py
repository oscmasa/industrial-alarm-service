"""Validated audit pagination and source-preserving response contracts."""
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from alarm_service.api.schemas.alarms import Pagination


class QualityFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=20, ge=1, le=100)


class RejectionFilters(QualityFilters):
    error_code: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$"
    )

    @field_validator("error_code", mode="before")
    @classmethod
    def normalize_error_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class ImportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_system: str
    file_name: str
    file_sha256: str
    status: str
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    records_read: int
    accepted: int
    rejected: int
    duplicates: int
    accepted_with_warnings: int


class RejectionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    import_id: UUID
    record_number: int
    original_data: dict
    errors: list[dict]
    created_at: AwareDatetime


class ImportListResponse(BaseModel):
    items: list[ImportItem]
    pagination: Pagination


class RejectionListResponse(BaseModel):
    import_id: UUID
    items: list[RejectionItem]
    pagination: Pagination
