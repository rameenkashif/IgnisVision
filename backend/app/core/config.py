from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Ignis Vision"
    environment: Literal["dev", "test", "prod"] = "dev"
    version: str = "0.1.0"

    database_url: str = "postgresql+asyncpg://ignis:ignis@localhost:5432/ignis"
    cors_origins: list[str] = ["https://localhost"]

    ml_backend: Literal["mock", "real"] = "mock"
    llm_provider: Literal["template", "anthropic"] = "template"
    tts_provider: Literal["browser"] = "browser"


@lru_cache
def get_settings() -> Settings:
    return Settings()
