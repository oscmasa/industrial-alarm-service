"""Expose the configured signal-condition relationships, independent of history."""

from dataclasses import dataclass

from alarm_service.domain.catalog import CONDITIONS, EQUIPMENT


@dataclass(frozen=True)
class SignalDefinition:
    tag: str
    equipment_name: str
    unit: str
    alarm_types: tuple[str, ...]


def signal_catalog() -> list[SignalDefinition]:
    equipment_names = {item.identifier: item.name for item in EQUIPMENT}
    tags = sorted({condition.tag for condition in CONDITIONS})
    return [
        SignalDefinition(
            tag=tag,
            equipment_name=equipment_names[
                next(c.equipment_id for c in CONDITIONS if c.tag == tag)
            ],
            unit=next(c.unit for c in CONDITIONS if c.tag == tag),
            alarm_types=tuple(sorted({c.alarm_code for c in CONDITIONS if c.tag == tag})),
        )
        for tag in tags
    ]
