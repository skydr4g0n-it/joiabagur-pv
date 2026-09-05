"""Application settings loaded from environment via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCTION_ENV_NAMES = frozenset({"prod", "production"})

CANONICAL_OPENAPI_SERVICE_VERSION = "0.1.0"

#: C21 fusion defaults, in one place so the field default, the blank-string fallback and
#: the canonical OpenAPI profile cannot drift apart. Every figure is measured; the reasons
#: live in the field descriptions and in `retrieval/fusion.py`.
FUSION_DEFAULTS: dict[str, Any] = {
    "jpv_rrf_k": 60,
    "jpv_rrf_weight_typed": 0.5,
    "jpv_rrf_weight_expanded": 0.5,
    "jpv_rrf_weight_vector": 0.33,
    "jpv_branch_depth": 60,
}


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

    jpv_query_expansion_enabled: bool = Field(
        default=True,
        description=(
            "C20 query-side synonym expansion for the lexical branch "
            "(JPV_QUERY_EXPANSION_ENABLED). Optional at boot; default true. This "
            "supplies only the DEFAULT: the effective value travels as a parameter of "
            "the retrieval orchestration call, because C24 sweeps configurations in one "
            "process and an environment-only switch would force a restart per config, "
            "while a request field would move the frozen openapi.json. Default is on "
            "because measured on the live index the lexical branch answers zero "
            "documents to `gargantilla dorada` and `collares de plata` without it; the "
            "flag exists so C24 can ablate, not because the finding is in doubt. Turning "
            "it off is also the rollback for C20. Distinct from JWT_SECRET, "
            "JPV_EMBEDDING_*, JPV_RAG_LLM_*, JPV_INDEX_FEED_*, JPV_CATALOG_LLM_* and "
            "JPV_RETRIEVAL_DISTANCE_THRESHOLD. Not required to boot /health, which never "
            "loads the dictionary."
        ),
    )

    jpv_rrf_k: int = Field(
        default=FUSION_DEFAULTS["jpv_rrf_k"],
        gt=0,
        description=(
            "C21 smoothing constant of the reciprocal rank fusion (JPV_RRF_K). Optional at "
            "boot; default 60; blank -> 60. It is not independent of JPV_BRANCH_DEPTH: at "
            "k=60 a rank-200 document still holds 38 % of the leader's vote, so depth and k "
            "must be swept together. Distinct from JWT_SECRET, JPV_EMBEDDING_*, "
            "JPV_RAG_LLM_*, JPV_INDEX_FEED_*, JPV_CATALOG_LLM_*, "
            "JPV_RETRIEVAL_DISTANCE_THRESHOLD and JPV_QUERY_EXPANSION_ENABLED. Not required "
            "to boot /health."
        ),
    )

    jpv_rrf_weight_typed: float = Field(
        default=FUSION_DEFAULTS["jpv_rrf_weight_typed"],
        ge=0,
        description=(
            "C21 fusion weight of the lexical list built from the operator's own text "
            "(JPV_RRF_WEIGHT_TYPED). Optional at boot; default 0.5; blank -> 0.5. Together "
            "with JPV_RRF_WEIGHT_EXPANDED it sums to 1.0, so disabling the expansion — which "
            "makes the two lexical lists identical — degrades to exactly one lexical list at "
            "full weight. Supplies only the DEFAULT: the effective value travels as a "
            "parameter of the retrieval orchestration call, because C24 sweeps configurations "
            "in one process. Not required to boot /health."
        ),
    )

    jpv_rrf_weight_expanded: float = Field(
        default=FUSION_DEFAULTS["jpv_rrf_weight_expanded"],
        ge=0,
        description=(
            "C21 fusion weight of the lexical list built from C20's equivalence groups "
            "(JPV_RRF_WEIGHT_EXPANDED). Optional at boot; default 0.5; blank -> 0.5. See "
            "JPV_RRF_WEIGHT_TYPED for why the two sum to 1.0. Not required to boot /health."
        ),
    )

    jpv_rrf_weight_vector: float = Field(
        default=FUSION_DEFAULTS["jpv_rrf_weight_vector"],
        ge=0,
        description=(
            "C21 fusion weight of the vector list (JPV_RRF_WEIGHT_VECTOR). Optional at boot; "
            "default 0.33; blank -> 0.33. Deliberately BELOW either lexical weight, and this "
            "is the default easiest to undo by accident: measured over twelve operator "
            "queries, branch parity (1.0) is the WORST fused configuration at 96/120 against "
            "105/120 at 0.33, because the distance threshold passes essentially the whole "
            "corpus and the vector branch therefore returns a full list whether or not it "
            "understood the query — a branch that always fills its list always votes at full "
            "strength. Raising it sinks `dije de plata` from 10/10 to 2/10. Not required to "
            "boot /health."
        ),
    )

    jpv_branch_depth: int = Field(
        default=FUSION_DEFAULTS["jpv_branch_depth"],
        gt=0,
        description=(
            "C21 depth at which EVERY fused list is truncated before fusing "
            "(JPV_BRANCH_DEPTH). Optional at boot; default 60; blank -> 60. One value shared "
            "by all three lists: an asymmetric 200 lexical / 60 vector costs 6-8 points of "
            "120. Conceptually distinct from the over-retrieval window the endpoint returns, "
            "which follows `top_k`, even though both default to 60 — reusing the existing "
            "OVER_RETRIEVAL_CAP is one fewer arbitrary constant, not the same parameter. Not "
            "required to boot /health."
        ),
    )

    jpv_pos_prefilter_enabled: bool = Field(
        default=True,
        description=(
            "C22 point-of-sale prefilter for POST /v1/retrieval/products "
            "(JPV_POS_PREFILTER_ENABLED). Optional at boot; default true; blank -> true. "
            "Supplies only the DEFAULT: the effective value travels as a parameter of the "
            "retrieval orchestration call, in the same pattern as "
            "JPV_QUERY_EXPANSION_ENABLED, because C24 sweeps configurations in one process "
            "and putting it on the request would move the frozen openapi.json. With it off, "
            "retrieval behaves exactly as it did before the projection existed, which makes "
            "it the rollback for this change: no deploy, no migration to undo, and "
            "ai.pos_projection can stay populated because nothing else reads it. Default on "
            "because, measured over 20 probes on the live index, eight of the eleven points "
            "of sale answer fewer than ten products to at least 6 of every 20 searches once "
            "the .NET side has dropped what they do not carry. Not required to boot /health."
        ),
    )

    jpv_pos_projection_max_age_seconds: int = Field(
        default=3600,
        gt=0,
        description=(
            "C22 staleness ceiling of ai.pos_projection "
            "(JPV_POS_PROJECTION_MAX_AGE_SECONDS). Optional at boot; default 3600; blank -> "
            "3600. Above it the point-of-sale scope is NOT applied for that request, the "
            "degradation is logged, and the response still reports the age: a stale "
            "projection may leave the page short, but it must never hide a valid product "
            "from the .NET authority. Deliberately generous — the design cadence is 5-10 "
            "minutes and the real one is a cron, so an hour degrades only under sustained "
            "failure and not under ordinary lateness. Degrading eagerly would surrender the "
            "whole benefit of the change on any transient. Measured against "
            "ai.sync_checkpoint.last_incremental_sync_at, never against "
            "ai.pos_projection.refreshed_at, which records when an assignment last changed "
            "and would report months on a projection synchronised seconds ago. Not required "
            "to boot /health."
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

    @field_validator("jpv_query_expansion_enabled", mode="before")
    @classmethod
    def blank_query_expansion_flag_is_default(cls, value: object) -> object:
        """A blank export means "unset", not "false" — same rule as the other options."""
        if isinstance(value, str) and not value.strip():
            return True
        return value

    @field_validator("jpv_pos_prefilter_enabled", mode="before")
    @classmethod
    def blank_pos_prefilter_flag_is_default(cls, value: object) -> object:
        """A blank export means "unset". Read as false it would silently unscope every search."""
        if isinstance(value, str) and not value.strip():
            return True
        return value

    @field_validator("jpv_pos_projection_max_age_seconds", mode="before")
    @classmethod
    def blank_projection_max_age_is_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return 3600
        return value

    @field_validator(
        "jpv_rrf_k",
        "jpv_rrf_weight_typed",
        "jpv_rrf_weight_expanded",
        "jpv_rrf_weight_vector",
        "jpv_branch_depth",
        mode="before",
    )
    @classmethod
    def blank_fusion_setting_is_default(cls, value: object, info: ValidationInfo) -> object:
        """A blank export means "unset". A blank weight read as 0 would silence a branch."""
        if isinstance(value, str) and not value.strip():
            return FUSION_DEFAULTS[str(info.field_name)]
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
        jpv_query_expansion_enabled=True,
        jpv_pos_prefilter_enabled=True,
        jpv_pos_projection_max_age_seconds=3600,
        # Pinned like the rest, so a process environment value cannot leak into the
        # committed OpenAPI snapshot through a fusion weight.
        **FUSION_DEFAULTS,
    )
