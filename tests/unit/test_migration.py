from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_initial_migration_renders_postgresql_sql():
    buffer = StringIO()
    configuration = Config(
        str(Path(__file__).resolve().parents[2] / "alembic.ini"), output_buffer=buffer
    )
    command.upgrade(configuration, "head", sql=True)
    sql = buffer.getvalue()
    for table in ("equipment", "tags", "alarms", "imports", "rejected_records"):
        assert f"CREATE TABLE {table}" in sql
    assert "UNIQUE (source_system, event_id)" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "ix_alarms_tag_occurred_at_id" in sql
    assert "accepted + rejected + duplicates" in sql
