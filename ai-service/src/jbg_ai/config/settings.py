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
    jpv_catalog_llm_api_key: str | None = Field(
        default=None,
        description=(
            "C06b generate only (JPV_CATALOG_LLM_API_KEY). Distinct from "
            "JPV_RAG_LLM_API_KEY (C09 runtime). Not required to boot /health."
        ),
    )
    jpv_catalog_llm_model: str | None = Field(
        default=None,
        description="Optional model id for the catalog CLI. Absence does not block /health.",
    )
    jpv_catalog_llm_base_url: str | None = Field(
        default=None,
        description="Optional OpenAI-compatible base URL for the catalog CLI.",
    )
    jpv_rag_llm_api_key: str | None = Field(
        default=None,
        description=(
            "C09 runtime enrichment (JPV_RAG_LLM_API_KEY). Distinct from "
            "JPV_CATALOG_LLM_API_KEY. Not required to boot /health."
        ),
    )
    jpv_rag_llm_model: str | None = Field(
        default=None,
        description="Optional provider-prefixed model id (e.g. openai/gpt-4o).",
    )
    jpv_rag_llm_base_url: str | None = Field(
        default=None,
        description="Optional LiteLLM api_base (proxy / Azure / local).",
    )
    jpv_rag_llm_concurrency: int = Field(
        default=8,
        gt=0,
        description="In-flight enrichment calls per batch. Default 8.",
    )
    jpv_embedding_api_key: str | None = Field(
        default=None,
        description=(
            "C11 embeddings (JPV_EMBEDDING_API_KEY). Distinct from "
            "JPV_RAG_LLM_API_KEY and JPV_CATALOG_LLM_API_KEY. Not required "
            "to boot /health; required when embedding."
        ),
    )
    jpv_embedding_model: str | None = Field(
        default=None,
        description=(
            "Optional provider-prefixed embedding model "
            "(e.g. openai/text-embedding-3-small)."
        ),
    )
    jpv_embedding_base_url: str | None = Field(
        default=None,
        description="Optional LiteLLM api_base for embeddings (proxy / Azure).",
    )
    jpv_embedding_batch_size: int = Field(
        default=64,
        gt=0,
        description="Texts per provider embedding call. Default 64.",
    )
    jpv_index_feed_base_url: str | None = Field(
        default=None,
        description=(
            "C13 catalog index feed (JPV_INDEX_FEED_BASE_URL). .NET API origin "
            "for GET /api/ai/index-feed/catalog. Distinct from JWT_SECRET. "
            "Not required to boot /health; required for a real catalog sync."
        ),
    )
    jpv_index_feed_api_key: str | None = Field(
        default=None,
        description=(
            "C13 catalog index feed (JPV_INDEX_FEED_API_KEY). Sent as "
            "X-Index-Feed-Key. Distinct from JWT_SECRET and JPV_EMBEDDING_*. "
            "Not required to boot /health; required for a real catalog sync. "
            "Must not fall back to JWT_SECRET."
        ),
    )
    jpv_index_sync_time_budget_seconds: int = Field(
        default=180,
        gt=0,
        description=(
            "Wall-clock budget for one catalog drain (HTTP or CLI). Default 180. "
            "Checked after each item; exhaustion persists a resume cursor."
        ),
    )
    jpv_retrieval_distance_threshold: float = Field(
        default=0.65,
        gt=0,
        le=2,
        description=(
            "C14 cosine-distance cutoff for POST /v1/retrieval/products "
            "(JPV_RETRIEVAL_DISTANCE_THRESHOLD). Optional at boot; default 0.65. "
            "Domain is pgvector cosine distance (0, 2]. Distinct from "
            "JWT_SECRET, JPV_EMBEDDING_*, JPV_RAG_LLM_*, JPV_INDEX_FEED_* "
            "and JPV_CATALOG_LLM_*. Not required to boot /health."
        ),
    )

    jpv_family_veto_margin: float = Field(
        default=0.05,
        ge=0,
        le=1,
        description=(
            "C18a relative-veto margin for POST /v1/families/suggest "
            "(JPV_FAMILY_VETO_MARGIN). A member is flagged for review, never "
            "removed, when a product of ANOTHER proposed family is closer to it "
            "than its own worst sibling by more than this much. Never an absolute "
            "similarity cutoff: on this corpus the worst-sibling and "
            "nearest-stranger populations overlap, so no constant separates them. "
            "Calibrated at 0.05 -> 15 of 486 members across 5 families; 0.02 -> 33 "
            "across 18; 0.08 -> 9 across 2. Lives here because C24 will revisit it "
            "with the golden set, and an inlined threshold cannot be swept. "
            "Not required to boot /health."
        ),
    )

    jpv_family_orphan_margin: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description=(
            "C18b orphan-nomination margin for POST /v1/families/audit "
            "(JPV_FAMILY_ORPHAN_MARGIN). A product belonging to no family is "
            "nominated as a candidate for family F when its similarity to F's "
            "members beats F's own worst-sibling similarity by more than this much. "
            "Deliberately NOT neighbourhood purity, which was measured and rejected: "
            "over 650 orphans, purity nominates 55 synthetic against 19 real, "
            "because the synthetic corpus was built with deliberate vN near-duplicate "
            "families it cannot tell from a missing member, whereas this margin "
            "nominates 21 real against 1 synthetic. Purity travels as a ranking "
            "signal only. Measured curve: 0 -> 40 candidates, 0.02 -> 22, "
            "0.05 -> 5, 0.08 -> 3. Starts at 0 on purpose: with verdicts persisted a "
            "dismissal is paid once, while a candidate the margin excluded is never "
            "seen at all. Not required to boot /health."
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

    @field_validator(
        "database_url",
        "jpv_catalog_llm_api_key",
        "jpv_catalog_llm_model",
        "jpv_catalog_llm_base_url",
        "jpv_rag_llm_api_key",
        "jpv_rag_llm_model",
        "jpv_rag_llm_base_url",
        "jpv_embedding_api_key",
        "jpv_embedding_model",
        "jpv_embedding_base_url",
        "jpv_index_feed_base_url",
        "jpv_index_feed_api_key",
        mode="before",
    )
    @classmethod
    def blank_optional_str_is_absent(cls, value: object) -> object:
        """Treat empty optional strings as unset (DATABASE_URL, LLM_* keys).

        Compose and shell profiles export empty strings easily; failing later
        with an unparseable URL or a blank key would be a worse error than
        behaving as if the variable had not been provided at all.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("jpv_rag_llm_concurrency", mode="before")
    @classmethod
    def blank_concurrency_is_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return 8
        return value

    @field_validator("jpv_embedding_batch_size", mode="before")
    @classmethod
    def blank_embedding_batch_size_is_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return 64
        return value

    @field_validator("jpv_index_sync_time_budget_seconds", mode="before")
    @classmethod
    def blank_index_sync_time_budget_is_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return 180
        return value

    @field_validator("jpv_retrieval_distance_threshold", mode="before")
    @classmethod
    def blank_retrieval_threshold_is_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return 0.65
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
        jpv_catalog_llm_api_key=None,
        jpv_catalog_llm_model=None,
        jpv_catalog_llm_base_url=None,
        jpv_rag_llm_api_key=None,
        jpv_rag_llm_model=None,
        jpv_rag_llm_base_url=None,
        jpv_rag_llm_concurrency=8,
        jpv_embedding_api_key=None,
        jpv_embedding_model=None,
        jpv_embedding_base_url=None,
        jpv_embedding_batch_size=64,
        jpv_index_feed_base_url=None,
        jpv_index_feed_api_key=None,
        jpv_index_sync_time_budget_seconds=180,
        jpv_retrieval_distance_threshold=0.65,
    )
