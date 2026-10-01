import pytest
from pydantic import ValidationError

from alarm_service.config import Settings


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ALARM_APP_NAME=File Name\n", encoding="utf-8")
    monkeypatch.setenv("ALARM_APP_NAME", "Environment Name")

    assert Settings(_env_file=env_file).app_name == "Environment Name"


def test_invalid_boolean_is_rejected(monkeypatch):
    monkeypatch.setenv("ALARM_DOCS_ENABLED", "invalid")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
