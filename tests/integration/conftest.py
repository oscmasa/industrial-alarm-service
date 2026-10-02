"""Shared PostgreSQL fixture isolating every test in a disposable schema."""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

URL = os.getenv("ALARM_TEST_DATABASE_URL")


@pytest.fixture
def database():
    if not URL:
        pytest.skip("ALARM_TEST_DATABASE_URL is required")
    schema = f"test_{uuid.uuid4().hex}"
    admin = create_engine(URL)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        URL, connect_args={"options": f"-c search_path={schema} -c timezone=UTC"}
    )
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine, config
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
