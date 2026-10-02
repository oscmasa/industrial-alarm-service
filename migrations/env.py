"""Alembic migration context, configured without logging database secrets."""

from alembic import context
from sqlalchemy import create_engine, pool

from alarm_service.config import get_settings
from alarm_service.infrastructure.database.models import Base

url = get_settings().database_url.get_secret_value()


def run_migrations_offline():
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    provided_connection = context.config.attributes.get("connection")
    if provided_connection is not None:
        context.configure(
            connection=provided_connection, target_metadata=Base.metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": 10},
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=Base.metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
