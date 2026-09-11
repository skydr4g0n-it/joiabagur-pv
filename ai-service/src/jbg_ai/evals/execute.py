"""Running one configuration over one query. C24.

Two of the five configurations are the live orchestrator with different knobs, and this module
CALLS it rather than reproducing it. The distinction matters more than it looks: a harness that
re-implemented the pipeline would measure the re-implementation, and the previous change is the
cautionary tale — its offline stand-in embedder measured a copy and reversed the verdict.

The environment this builds is deliberately narrow. `Settings` demands `APP_ENV`,
`SERVICE_VERSION` and `JWT_SECRET`, which are the SERVING profile and have nothing to do with
measuring; they are pinned here to fixed local values so that a machine without them can still
run the harness, and so that nothing an operator happens to have exported can change a
measured number. The same rule the C21 comparison CLI already follows: a development aid reads
what it uses.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.api.schemas.retrieval import RetrievalMode, RetrievalRequest
from jbg_ai.config.settings import FUSION_DEFAULTS, Settings
from jbg_ai.evals.baselines import run_v0_fts, run_v0_nombre
from jbg_ai.evals.configs import (
    KIND_CONTEXT_ONLY,
    KIND_FULL_TEXT,
    KIND_NAME_SUBSTRING,
    KIND_PIPELINE,
    EvalConfig,
)
from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.latency import PROVIDER_STAGE, Sample, StageCollector
from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.retrieval.orchestrator import COVERAGE_CONTINUOUS, retrieve_products
from jbg_ai.retrieval.ports import ProductSearchPort
from jbg_ai.retrieval.search import SqlAlchemyProductSearch

#: `retrieve_products` returns `min(top_k * 3, 60)` candidates, so asking for twenty is how the
#: harness sees the sixty the branch depth allows. Reusing that rule rather than a constant of
#: its own keeps the harness looking at exactly the window the .NET side receives.
TOP_K_FOR_FULL_WINDOW = 20

#: The profile the harness runs under. Fixed, and none of it reaches a measured number: the
#: token is never signed or verified, because the harness is both its issuer and its consumer.
HARNESS_APP_ENV = "local"
HARNESS_SERVICE_VERSION = "0.1.0"
HARNESS_JWT_SECRET = "eval-harness-not-a-credential"


@dataclass(frozen=True)
class RankedHit:
    product_id: UUID
    sku: str
    score: float


@dataclass(frozen=True)
class QueryRun:
    """One execution: what it returned, how long it took, and whether it abstained."""

    query_id: str
    hits: tuple[RankedHit, ...]
    sample: Sample
    low_confidence: bool


def harness_settings(*, requires_database: bool = True, **overrides: object) -> Settings:
    """The measurement profile: serving fields pinned, retrieval knobs at their live defaults.

    `requires_database=False` is for the RE-SCORE phase of C25's sweep and for nothing else.
    That phase reads persisted windows and must not open a pool — the guarantee is its whole
    point — so demanding a URL it will never use would make the offline phase impossible to
    run offline, which is the opposite of the property being claimed.
    """
    values: dict[str, object] = {
        "app_env": HARNESS_APP_ENV,
        "service_version": HARNESS_SERVICE_VERSION,
        "jwt_secret": HARNESS_JWT_SECRET,
        "log_level": "INFO",
        "stub_mode": False,
        "enable_dev_endpoints": True,
        "database_url": os.environ.get("DATABASE_URL"),
        "db_pool_size": 5,
        "jpv_embedding_api_key": os.environ.get("JPV_EMBEDDING_API_KEY"),
        "jpv_embedding_model": os.environ.get("JPV_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
        "jpv_embedding_base_url": os.environ.get("JPV_EMBEDDING_BASE_URL"),
        "jpv_retrieval_distance_threshold": _float_env(
            "JPV_RETRIEVAL_DISTANCE_THRESHOLD", 0.65
        ),
        "jpv_query_expansion_enabled": True,
        "jpv_pos_prefilter_enabled": False,
        **FUSION_DEFAULTS,
    }
    values.update(overrides)
    if requires_database and not values["database_url"]:
        raise EvaluationUnavailable(
            "DATABASE_URL is not set. The pool cannot be built from a file: the harness has to "
            "run the configurations against the real index to know what each one returns"
        )
    return Settings(**values)  # type: ignore[arg-type]


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise EvaluationUnavailable(f"{name} is not a number: {raw!r}") from exc


def build_search(settings: Settings) -> ProductSearchPort:
    return SqlAlchemyProductSearch(settings)


#: A point of sale that identifies nothing, and is never applied.
#:
#: The orchestrator parses the claim even when the prefilter is off, on purpose: a token whose
#: point of sale cannot be read is broken whatever the request intends to do with it, and
#: finding that out only when somebody enables the flag is how a mis-issued token reaches
#: production. So the harness has to present one. It presents the nil UUID rather than a real
#: shop, because the golden set is labelled UNSCOPED and every configuration sets
#: `pos_prefilter: false`: with the prefilter off the value selects nothing, and borrowing a
#: real identifier would suggest a scope that is not being applied.
HARNESS_POS_ID = "00000000-0000-0000-0000-000000000000"


def harness_principal() -> ServicePrincipal:
    """The measuring caller. Its scope is never applied; see `HARNESS_POS_ID`."""
    return ServicePrincipal(
        user_id="eval-harness",
        role="Operator",
        trace_id=f"eval-{uuid4().hex[:12]}",
        pos_id=HARNESS_POS_ID,
    )


async def execute(
    config: EvalConfig,
    query_id: str,
    text: str,
    *,
    settings: Settings,
    search: ProductSearchPort,
    embed: EmbeddingClient | None,
    depth: int,
) -> QueryRun:
    """Run one configuration over one query and return its ranked list, timed.

    The two baselines are timed the same way as the pipeline and record a provider cost of
    zero. Zero is a value: a blank in that column would read as "not measured", and the whole
    point of the cost column is that the comparison between retrieval and context-stuffing is a
    number rather than an argument.
    """
    if config.kind == KIND_CONTEXT_ONLY:
        raise EvaluationUnavailable(
            f"{config.id} answers in prose over a context window and produces no ranked list; "
            "it is measured by `evals.cag`, not here"
        )

    started = time.perf_counter()
    with StageCollector() as collector:
        if config.kind == KIND_NAME_SUBSTRING:
            baseline = await run_v0_nombre(text, settings=settings, depth=depth)
            hits = tuple(
                RankedHit(item.product_id, item.sku, item.score) for item in baseline
            )
            low_confidence = not hits
        elif config.kind == KIND_FULL_TEXT:
            baseline = await run_v0_fts(text, settings=settings, depth=depth)
            hits = tuple(
                RankedHit(item.product_id, item.sku, item.score) for item in baseline
            )
            low_confidence = not hits
        elif config.kind == KIND_PIPELINE:
            if embed is None:
                raise EvaluationUnavailable(
                    f"{config.id} needs query embeddings and none were supplied"
                )
            response = await retrieve_products(
                RetrievalRequest(
                    query=text,
                    top_k=TOP_K_FOR_FULL_WINDOW,
                    mode=RetrievalMode(config.mode or "hybrid"),
                ),
                harness_principal(),
                settings=settings,
                embed=embed,
                search=search,
                expand_synonyms=config.expand_synonyms,
                rrf_k=config.rrf_k,
                weight_typed=config.weight_typed,
                weight_expanded=config.weight_expanded,
                weight_vector=config.weight_vector,
                fusion=config.fusion,
                branch_weight_lexical=config.branch_weight_lexical,
                branch_weight_vector=config.branch_weight_vector,
                coverage_rule=config.coverage_rule or COVERAGE_CONTINUOUS,
                coverage_alpha=config.coverage_alpha,
                branch_depth=config.branch_depth,
                pos_prefilter=config.pos_prefilter,
                signal_pos_id=UUID(config.signal_pos_id) if config.signal_pos_id else None,
                business_weight_availability=config.business_weight_availability,
                business_weight_rotation=config.business_weight_rotation,
            )
            hits = tuple(
                RankedHit(UUID(item.product_id), item.sku, item.score)
                for item in response.results
            )
            low_confidence = response.low_confidence
        else:  # pragma: no cover - `from_mapping` rejects unknown kinds at load time
            raise EvaluationUnavailable(f"{config.id}: unsupported kind {config.kind!r}")

        e2e_ms = (time.perf_counter() - started) * 1000
        provider_ms = collector.total(PROVIDER_STAGE)
        lexical_ms = collector.total("lexical")

    return QueryRun(
        query_id=query_id,
        hits=hits[:depth],
        sample=Sample(
            query_id=query_id,
            e2e_ms=e2e_ms,
            provider_ms=provider_ms,
            lexical_ms=lexical_ms,
        ),
        low_confidence=low_confidence,
    )
