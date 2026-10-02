"""Shared time/severity filters with explicit UTC and range validation."""

from datetime import UTC, datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator, model_validator

from alarm_service.application.normalization.parsers import ISO_TIMESTAMP, parse_timestamp
from alarm_service.domain.alarm import Severity


class TimeSeverityFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    severity: Severity | None = None

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
