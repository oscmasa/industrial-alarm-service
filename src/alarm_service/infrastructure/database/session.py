"""Database engine factory; callers control session and transaction lifetime."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from alarm_service.config import Settings, get_settings


def build_engine(settings: Settings | None = None) -> Engine:
    configuration = settings if settings is not None else get_settings()
    return create_engine(
        configuration.database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": 10},
    )
