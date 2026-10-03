"""HTTP query validation and stable paginated response contracts."""

import uuid
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from alarm_service.api.schemas.filters import TimeSeverityFilters
from alarm_service.domain.alarm import Severity


class AlarmFilters(TimeSeverityFilters):
    tag: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=50, ge=1, le=100)

    @field_validator("tag", mode="before")
    @classmethod
    def normalize_tag(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class AlarmItem(BaseModel):
    id: int
    event_id: str
    source_system: str
    import_id: uuid.UUID
    occurred_at: AwareDatetime
    tag: str
    alarm_code: str
    severity: Severity
    message: str | None
    value: Decimal | None
    unit: str | None = None
    warnings: list[str]


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class AlarmListResponse(BaseModel):
    items: list[AlarmItem]
    pagination: Pagination
