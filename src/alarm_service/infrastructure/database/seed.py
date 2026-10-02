"""Idempotent insertion of the versioned equipment/tag catalog."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from alarm_service.domain.catalog import CONDITIONS, EQUIPMENT
from alarm_service.infrastructure.database.models import EquipmentModel, TagModel
from alarm_service.infrastructure.database.session import build_engine


def seed_catalog(connection: Connection) -> tuple[int, int]:
    equipment = [{"id": item.identifier, "name": item.name} for item in EQUIPMENT]
    tags = {
        item.tag: {"id": item.tag, "equipment_id": item.equipment_id, "unit": item.unit}
        for item in CONDITIONS
    }
    equipment_result = connection.execute(
        insert(EquipmentModel)
        .values(equipment)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(EquipmentModel.id)
    )
    tag_result = connection.execute(
        insert(TagModel)
        .values(list(tags.values()))
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(TagModel.id)
    )
    return len(equipment_result.scalars().all()), len(tag_result.scalars().all())


def main() -> None:
    engine = build_engine()
    try:
        with engine.begin() as connection:
            equipment_count, tag_count = seed_catalog(connection)
        print(f"Catalog loaded: {equipment_count} equipment and {tag_count} tags inserted.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
