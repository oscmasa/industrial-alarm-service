"""HTTP query validation and stable paginated response contracts."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from alarm_service.application.normalization.parsers import ISO_TIMESTAMP, parse_timestamp
from alarm_service.domain.alarm import Severity


class AlarmFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    severity: Severity | None = None
    tag: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=50, ge=1, le=100)

    @field_validator("tag", mode="before")
    @classmethod
    def normalize_tag(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def require_iso_timezone(cls, value):
        if value is None or isinstance(value, datetime):
            return value
        if (
            not isinstance(value, str)
            or not ISO_TIMESTAMP.fullmatch(value)
            or not (value.endswith("Z") or value[-6:-5] in ("+", "-"))
        ):
            raise ValueError("Use an ISO 8601 datetime with Z or an explicit UTC offset")
        return parse_timestamp(value)

    @field_validator("start_time", "end_time")
    @classmethod
    def to_utc(cls, value):
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValueError("start_time must be before end_time")
        return self


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
    warnings: list[str]


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class AlarmListResponse(BaseModel):
    items: list[AlarmItem]
    pagination: Pagination
