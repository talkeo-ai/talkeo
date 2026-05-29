from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "talkeo"
    ENV: Literal["development", "staging", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    # Reserved for Phase B+. Unused in Phase A.
    DB_URL: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
