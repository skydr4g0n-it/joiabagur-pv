"""Application settings loaded from environment via pydantic-settings."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Minimal C01 settings: fail fast on missing APP_ENV / SERVICE_VERSION."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(..., min_length=1, description="Deployment environment name")
    service_version: str = Field(..., min_length=1, description="Service version string")
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("app_env", "service_version", mode="before")
    @classmethod
    def reject_blank(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be empty")
        return value


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings; raises ValidationError if required env is missing."""
    return Settings()  # type: ignore[call-arg]
