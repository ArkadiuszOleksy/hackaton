from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CivicLens Data Service"
    app_env: str = "development"
    app_version: str = "0.1.0"
    app_port: int = 8001
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/civiclens"
    db_echo: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()