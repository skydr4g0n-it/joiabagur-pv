"""Application settings loaded from environment via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCTION_ENV_NAMES = frozenset({"prod", "production"})

CANONICAL_OPENAPI_SERVICE_VERSION = "0.1.0"


class Settings(BaseSettings):
    """C02 settings: fail fast on missing APP_ENV / SERVICE_VERSION / JWT_SECRET."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(..., min_length=1, description="Deployment environment name")
    service_version: str = Field(..., min_length=1, description="Service version string")
    log_level: str = Field(default="INFO", description="Logging level")
    jwt_secret: str = Field(
        ...,
        min_length=1,
        description="HS256 secret shared with the .NET API for the internal service token",
    )
    jwt_ttl_seconds: int = Field(
        default=300,
        gt=0,
        description="Documented TTL for internal tokens; the .NET API is the issuer",
    )
    stub_mode: bool = Field(
        default=True,
        description="Serve deterministic fixtures instead of real retrieval/enrichment logic",
    )
    enable_dev_endpoints: bool = Field(
        default=True,
        description="Mount development-only routes such as GET /v1/evals/runs",
    )
    database_url: str | None = Field(
        default=None,
        description=(
            "PostgreSQL connection string for schema `ai`, e.g. "
            "postgresql+psycopg://user:password@host:5432/db. Optional on purpose: "
            "the service must boot without a database, so the engine is built on "
            "first use and its absence only surfaces when a session is requested"
        ),
    )
    db_pool_size: int = Field(
        default=5,
        gt=0,
        description=(
            "Hard ceiling on simultaneous connections, with no overflow. The "
            "project budget is 5-10 for the whole system, shared with the .NET API"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def derive_dev_endpoints(cls, data: Any) -> Any:
        """Default `enable_dev_endpoints` from `app_env`: off under a production profile."""
        if not isinstance(data, dict) or data.get("enable_dev_endpoints") is not None:
            return data
        app_env = str(data.get("app_env") or "").strip().lower()
        return {**data, "enable_dev_endpoints": app_env not in PRODUCTION_ENV_NAMES}

    @field_validator("app_env", "service_version", "jwt_secret", mode="before")
    @classmethod
    def reject_blank(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def blank_database_url_is_absent(cls, value: object) -> object:
        """Treat an empty `DATABASE_URL` as unset rather than as a broken URL.

        Compose and shell profiles export empty strings easily; failing later
        with an unparseable URL would be a worse error than behaving as if the
        variable had not been provided at all.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings; raises ValidationError if required env is missing."""
    return Settings()  # type: ignore[call-arg]


def canonical_openapi_settings() -> Settings:
    """Canonical development profile the versioned `openapi.json` is generated with.

    Pinned here so the snapshot test and the manual regeneration documented in the
    README can never build the app with different profiles. Values are fixed on
    purpose: environment must not leak into the committed contract.
    """
    return Settings(
        app_env="local",
        service_version=CANONICAL_OPENAPI_SERVICE_VERSION,
        log_level="WARNING",
        jwt_secret="openapi-snapshot-secret-0123456789ab",
        jwt_ttl_seconds=300,
        stub_mode=True,
        enable_dev_endpoints=True,
        # Pinned like the rest: pydantic-settings would otherwise read these
        # from the environment, and the canonical profile exists precisely so
        # that no environment leaks into the committed contract.
        database_url=None,
        db_pool_size=5,
    )
