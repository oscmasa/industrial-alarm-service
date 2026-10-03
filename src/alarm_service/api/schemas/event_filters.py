"""Optional normalized signal and condition identifiers for aggregate queries."""

from pydantic import Field, field_validator

from alarm_service.api.schemas.filters import TimeSeverityFilters


class EventFilters(TimeSeverityFilters):
    tag: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    alarm_code: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$"
    )

    @field_validator("tag", "alarm_code", mode="before")
    @classmethod
    def normalize_identifier(cls, value):
        return value.strip().upper() if isinstance(value, str) else value
