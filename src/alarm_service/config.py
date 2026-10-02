"""Validated application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ALARM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Industrial Alarm Service", min_length=1)
    app_version: str = "0.1.0"
    docs_enabled: bool = True
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://alarm_user:local_dev_password@localhost:5432/alarms"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
