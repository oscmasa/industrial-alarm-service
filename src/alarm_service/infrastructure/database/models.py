"""PostgreSQL persistence models; domain rules stay independent of the ORM."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class EquipmentModel(Base):
    __tablename__ = "equipment"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class TagModel(Base):
    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id", ondelete="RESTRICT"))
    unit: Mapped[str] = mapped_column(String(20))
    __table_args__ = (Index("ix_tags_equipment_id", "equipment_id"),)


class ImportModel(Base):
    __tablename__ = "imports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_system: Mapped[str] = mapped_column(String(64))
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), server_default="PENDING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_read: Mapped[int] = mapped_column(BigInteger, server_default="0")
    accepted: Mapped[int] = mapped_column(BigInteger, server_default="0")
    rejected: Mapped[int] = mapped_column(BigInteger, server_default="0")
    duplicates: Mapped[int] = mapped_column(BigInteger, server_default="0")
    accepted_with_warnings: Mapped[int] = mapped_column(BigInteger, server_default="0")
    error_message: Mapped[str | None] = mapped_column(String(1000))
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')", name="status"),
        CheckConstraint(
            "records_read >= 0 AND accepted >= 0 AND rejected >= 0 AND duplicates >= 0 "
            "AND accepted_with_warnings >= 0 AND accepted_with_warnings <= accepted",
            name="counters",
        ),
        CheckConstraint(
            "status != 'COMPLETED' OR (records_read = accepted + rejected + duplicates "
            "AND finished_at IS NOT NULL)",
            name="completed_counts",
        ),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="time_order"),
        Index("ix_imports_started_at", "started_at"),
    )


class AlarmModel(Base):
    __tablename__ = "alarms"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str] = mapped_column(String(12))
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("imports.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"))
    alarm_code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str | None] = mapped_column(String(500))
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    warnings: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("source_system", "event_id", name="uq_alarms_source_event"),
        CheckConstraint("event_id ~ '^EVT-[0-9]{8}$'", name="event_id_format"),
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="severity"),
        CheckConstraint("value IS NULL OR (value >= 0 AND value != 'NaN'::numeric)", name="value"),
        CheckConstraint("jsonb_typeof(warnings) = 'array'", name="warnings_array"),
        Index("ix_alarms_occurred_at_id", "occurred_at", "id"),
        Index("ix_alarms_severity_occurred_at_id", "severity", "occurred_at", "id"),
        Index("ix_alarms_tag_occurred_at_id", "tag_id", "occurred_at", "id"),
        Index("ix_alarms_import_id", "import_id"),
    )


class RejectedRecordModel(Base):
    __tablename__ = "rejected_records"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("imports.id", ondelete="RESTRICT"))
    record_number: Mapped[int] = mapped_column(BigInteger)
    original_data: Mapped[dict] = mapped_column(JSONB)
    errors: Mapped[list[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("import_id", "record_number", name="uq_rejected_records_import_record"),
        CheckConstraint("record_number > 0", name="record_number"),
        CheckConstraint("jsonb_typeof(original_data) = 'object'", name="original_data_object"),
        CheckConstraint(
            "CASE WHEN jsonb_typeof(errors) = 'array' "
            "THEN jsonb_array_length(errors) > 0 ELSE false END",
            name="errors_nonempty",
        ),
    )
