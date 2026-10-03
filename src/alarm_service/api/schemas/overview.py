"""Overview responses and explicit full-day plant-time intervals."""

from datetime import date
from decimal import Decimal
from typing import Self
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, model_validator

from alarm_service.api.schemas.event_filters import EventFilters
from alarm_service.domain.alarm import Severity


class OverviewFilters(EventFilters):
    start_time: AwareDatetime
    end_time: AwareDatetime

    @model_validator(mode="after")
    def full_day_range(self) -> Self:
        zone = ZoneInfo("America/Bogota")
        for value in (self.start_time, self.end_time):
            local = value.astimezone(zone)
            if any((local.hour, local.minute, local.second, local.microsecond)):
                raise ValueError("Overview bounds must be midnight in America/Bogota")
            if not 1901 <= local.year <= 9998:
                raise ValueError("Overview years must be between 1901 and 9998")
        if (self.end_time - self.start_time).days > 366:
            raise ValueError("Overview range must not exceed 366 days")
        return self


class AvailableDatesResponse(BaseModel):
    timezone: str = "America/Bogota"
    first_event: AwareDatetime | None
    last_event: AwareDatetime | None


class DailyEvents(BaseModel):
    date: date
    event_count: int
    moving_average_7_days: Decimal | None


class PeriodComparison(BaseModel):
    start_time: AwareDatetime
    end_time: AwareDatetime
    event_count: int | None
    change_percent: Decimal | None
    unavailable_reason: str | None


class OverviewResponse(BaseModel):
    timezone: str
    start_time: AwareDatetime
    end_time: AwareDatetime
    severity: Severity | None
    tag: str | None
    alarm_code: str | None
    total_events: int
    severity_counts: dict[str, int]
    daily: list[DailyEvents]
    comparison: PeriodComparison
