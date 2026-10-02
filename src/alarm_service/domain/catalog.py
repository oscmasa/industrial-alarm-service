"""Immutable synthetic catalog shared by generation and validation."""

from dataclasses import dataclass
from decimal import Decimal

CATALOG_VERSION = "1.0"
SOURCE_SYSTEM = "SCADA_01"
SOURCE_TIMEZONE = "America/Bogota"
CSV_FIELDS = ("event_id", "occurred_at", "tag", "alarm_code", "severity", "message", "value")
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
SEVERITY_ALIASES = {
    "LOW": ("LOW", "BAJA", "1"),
    "MEDIUM": ("MEDIUM", "MEDIA", "2"),
    "HIGH": ("HIGH", "ALTA", "3"),
    "CRITICAL": ("CRITICAL", "CRITICA", "CRÍTICA", "4"),
}


@dataclass(frozen=True)
class Equipment:
    identifier: str
    name: str


@dataclass(frozen=True)
class AlarmCondition:
    equipment_id: str
    tag: str
    unit: str
    alarm_code: str
    default_severity: str
    operator: str
    threshold: Decimal
    sample_min: Decimal
    sample_max: Decimal
    weight: int = 1

    def trigger_matches(self, value: Decimal) -> bool:
        if self.operator == "lt":
            return value < self.threshold
        if self.operator == "gt":
            return value > self.threshold
        return value == self.threshold


EQUIPMENT = (
    Equipment("TANK_IN_01", "Inlet tank"),
    Equipment("PUMP_01", "Feed pump"),
    Equipment("FILTER_01", "Filtration system"),
    Equipment("TANK_OUT_01", "Treated water tank"),
    Equipment("FILLER_01", "Filling machine"),
    Equipment("CONVEYOR_01", "Conveyor"),
    Equipment("COMPRESSOR_01", "Air compressor"),
)


def _condition(equipment, signal, unit, code, severity, operator, threshold, low, high, weight=1):
    return AlarmCondition(
        equipment,
        f"{equipment}_{signal}",
        unit,
        code,
        severity,
        operator,
        Decimal(str(threshold)),
        Decimal(str(low)),
        Decimal(str(high)),
        weight,
    )


CONDITIONS = (
    _condition("TANK_IN_01", "LEVEL", "%", "LOW_LEVEL", "HIGH", "lt", 15, 1, 14, 3),
    _condition("TANK_IN_01", "LEVEL", "%", "HIGH_LEVEL", "MEDIUM", "gt", 90, 91, 99),
    _condition("PUMP_01", "FLOW", "L/min", "LOW_FLOW", "HIGH", "lt", 20, 1, 19, 4),
    _condition("PUMP_01", "MOTOR_FAULT", "boolean", "MOTOR_FAULT", "CRITICAL", "eq", 1, 1, 1),
    _condition(
        "FILTER_01", "DIFF_PRESSURE", "bar", "HIGH_DIFF_PRESSURE", "MEDIUM", "gt", 1.5, 1.6, 3, 6
    ),
    _condition("FILTER_01", "PRESSURE", "bar", "HIGH_PRESSURE", "HIGH", "gt", 6, 6.1, 9),
    _condition("TANK_OUT_01", "LEVEL", "%", "LOW_LEVEL", "HIGH", "lt", 15, 1, 14, 3),
    _condition("TANK_OUT_01", "LEVEL", "%", "HIGH_LEVEL", "MEDIUM", "gt", 90, 91, 99),
    _condition("FILLER_01", "PRESSURE", "bar", "LOW_PRESSURE", "HIGH", "lt", 2, 0.1, 1.9, 4),
    _condition("FILLER_01", "CYCLE_FAULT", "boolean", "CYCLE_FAULT", "HIGH", "eq", 1, 1, 1, 2),
    _condition("CONVEYOR_01", "JAM", "boolean", "JAM", "MEDIUM", "eq", 1, 1, 1, 2),
    _condition("CONVEYOR_01", "MOTOR_TEMP", "degC", "HIGH_TEMPERATURE", "LOW", "gt", 70, 71, 90),
    _condition("COMPRESSOR_01", "PRESSURE", "bar", "LOW_PRESSURE", "HIGH", "lt", 5, 1, 4.9, 3),
    _condition("COMPRESSOR_01", "TEMP", "degC", "HIGH_TEMPERATURE", "HIGH", "gt", 95, 96, 120),
)
