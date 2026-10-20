from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {"", "change-me", "dev-insecure-secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Ignis Vision"
    environment: Literal["dev", "test", "prod"] = "dev"
    version: str = "0.1.0"

    database_url: str = "postgresql+asyncpg://ignis:ignis@localhost:5432/ignis"
    cors_origins: list[str] = ["https://localhost"]

    # Auth (HANDOFF §6)
    jwt_secret: str = "dev-insecure-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    idle_timeout_minutes: int = 30
    refresh_cookie_name: str = "iv_refresh"
    refresh_cookie_path: str = "/api/v1/auth"

    ml_backend: Literal["mock", "real"] = "mock"
    llm_provider: Literal["template", "anthropic"] = "template"
    tts_provider: Literal["browser"] = "browser"

    @model_validator(mode="after")
    def _refuse_insecure_prod(self) -> "Settings":
        if self.environment == "prod" and self.jwt_secret in _INSECURE_SECRETS:
            raise ValueError("JWT_SECRET must be set to a strong random value in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
