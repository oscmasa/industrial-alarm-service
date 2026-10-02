"""Validated intermediate contract and structured normalization outcomes."""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from alarm_service.domain.alarm import Alarm, Severity


class NormalizedFields(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event_id: str = Field(pattern=r"^EVT-[0-9]{8}$")
    occurred_at: AwareDatetime
    tag: str = Field(min_length=1, max_length=64)
    alarm_code: str = Field(min_length=1, max_length=64)
    severity: Severity
    message: str | None = Field(max_length=500)
    value: Decimal | None = Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)

    def to_alarm(self, warnings: tuple[str, ...]) -> Alarm:
        return Alarm(
            event_id=self.event_id,
            occurred_at=self.occurred_at,
            tag=self.tag,
            alarm_code=self.alarm_code,
            severity=self.severity,
            message=self.message,
            value=self.value,
            warnings=warnings,
        )


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    message: str


@dataclass(frozen=True)
class NormalizationResult:
    alarm: Alarm | None
    errors: tuple[Issue, ...]
    warnings: tuple[Issue, ...]
    original_data: dict

    @property
    def accepted(self) -> bool:
        return self.alarm is not None and not self.errors
