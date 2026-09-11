"""Orchestrates the configurations and builds the `Report`. C24.

**The runner does not import the persistence module.** It produces a `Report` in memory and
does not know that a database exists; `report.py` always serialises it into the repository and
`repository.py` optionally writes it to the evaluation tables. The direction of that dependency
is the design decision: the artefact in git is the normative copy, diffable between revisions,
and the tables are a convenience the published route needs.

**Configurations run in series, never in parallel.** The connection pool is capped at five with
no overflow and it is shared with the live path; three concurrent runs would exhaust it. On
1.168 documents the wall-clock cost of running them one after another is minutes.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.evals.configs import EvalConfig
from jbg_ai.evals.execute import QueryRun, execute
from jbg_ai.evals.golden import GoldenQuery, GoldenSet
from jbg_ai.evals.latency import LatencySummary, Sample, summarise
from jbg_ai.evals.metrics import (
    Aggregate,
    CaseMetrics,
    aggregate,
    abstention_rate,
    grade_distribution,
    score_case,
    stale_judgements,
)
from jbg_ai.evals.pricing import PriceList
from jbg_ai.evals.provenance import Provenance, current_git_sha, index_set_hash
from jbg_ai.indexing.embeddings import EmbeddingClient
from jbg_ai.retrieval.ports import ProductSearchPort

#: Executions per query. The first is discarded, so three means two warm samples per query and
#: 96 over the set — enough for a 95th percentile to describe something other than a cold start.
DEFAULT_REPEAT = 3

#: Tokens a query costs the embedding provider. Ten is the measured shape of these queries and
#: the figure the exploration used; it is an estimate and the report says so, because the
#: provider does not return a token count for embeddings.
QUERY_TOKENS = 10

OUT_OF_DOMAIN = "fuera-de-dominio"

_ACTIVE_IDS = "SELECT product_id FROM ai.product_document WHERE is_active IS TRUE"
_HASHES = "SELECT product_id, source_hash FROM ai.product_document WHERE is_active IS TRUE"

#: Cosine distance of a judged document to the query vector. Read directly rather than taken
#: from the pipeline, because `RetrievalResult` deliberately does not carry a distance: the
#: contract emits a score, and reconstructing a distance from it would be an inversion of a
#: clamp rather than a measurement.
_DISTANCES = """
SELECT product_id, embedding <=> CAST(:q AS vector) AS distance
FROM ai.product_document
WHERE embedding IS NOT NULL
  AND is_active IS TRUE
  AND product_id = ANY(CAST(:ids AS uuid[]))
"""


@dataclass(frozen=True)
class ConfigReport:
    """Everything one row of the ablation table carries."""

    config_id: str
    label: str
    provenance: Provenance
    readings: dict[str, Aggregate]
    by_origin: dict[str, Aggregate]
    by_category: dict[str, Aggregate]
    abstention_rate: float
    latency: LatencySummary
    cost_per_query_usd: float
    documents_omitted: int
    cases: tuple[CaseMetrics, ...]
    ranked: dict[str, tuple[str, ...]]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Report:
    """The whole run, in memory. Nothing in here knows how it will be written down."""

    run_id: str
    generated_at: datetime
    golden_set_version: str
    index_set_hash: str
    git_sha: str
    corpus_size: int
    configs: tuple[ConfigReport, ...]
    distance_distribution: dict[str, dict[str, float]]
    stale_judgements: int
    price_list: PriceList
    cag: dict | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def config(self, config_id: str) -> ConfigReport:
        for item in self.configs:
            if item.config_id == config_id:
                return item
        raise KeyError(config_id)


async def corpus_snapshot(settings: Settings) -> tuple[list[UUID], dict[str, str]]:
    """The indexed set and the text hashes, read once per run."""
    async with session_scope(settings) as session:
        ids = [UUID(str(row[0])) for row in (await session.execute(text(_ACTIVE_IDS))).all()]
        hashes = {
            str(row[0]): str(row[1]) for row in (await session.execute(text(_HASHES))).all()
        }
    return ids, hashes


async def judged_distances(
    golden: GoldenSet, *, settings: Settings, embed: EmbeddingClient
) -> list[tuple[int, float]]:
    """`(grade, distance)` for every judged document, over every judged query.

    This is the histogram a later change needs in order to decide whether a single distance
    threshold can separate relevant from irrelevant at all. In the knowledge corpus it could,
    by eight thousandths; whether the product corpus has that gap is an open question, and
    either answer is a finding rather than a pending task.
    """
    pairs: list[tuple[int, float]] = []
    for query in golden.judged_queries:
        judgements = golden.judgements_for(query.id)
        if not judgements:
            continue
        vector = (await embed.embed([query.text])).vectors[0]
        literal = "[" + ",".join(str(value) for value in vector) + "]"
        ids = [item.product_id for item in judgements]
        async with session_scope(settings) as session:
            rows = (
                await session.execute(text(_DISTANCES), {"q": literal, "ids": ids})
            ).all()
        by_id = {str(row[0]): float(row[1]) for row in rows}
        for item in judgements:
            distance = by_id.get(item.product_id)
            if distance is not None:
                pairs.append((item.grade, distance))
    return pairs


def split_readings(
    golden: GoldenSet, cases: Sequence[CaseMetrics]
) -> dict[str, Aggregate]:
    """Global, tuning subset, and new queries — the three readings, always all three.

    A configuration that wins only on the queries used to calibrate it has not been confirmed;
    it has been fitted. Publishing the three makes the contamination visible and quantified
    instead of leaving it to be assumed away.
    """
    tuning = {query.id for query in golden.queries if query.in_tuning_set}
    return {
        "global": aggregate(list(cases)),
        "tuning": aggregate([case for case in cases if case.query_id in tuning]),
        "new": aggregate([case for case in cases if case.query_id not in tuning]),
    }


def origin_readings(
    golden: GoldenSet, per_origin: dict[str, list[CaseMetrics]]
) -> dict[str, Aggregate]:
    return {origin: aggregate(cases) for origin, cases in sorted(per_origin.items())}


async def run_config(
    config: EvalConfig,
    golden: GoldenSet,
    *,
    settings: Settings,
    search: ProductSearchPort,
    embed: EmbeddingClient | None,
    prices: PriceList,
    provenance: Provenance,
    repeat: int = DEFAULT_REPEAT,
) -> ConfigReport:
    """Evaluate one configuration over the whole judged set."""
    queries = list(golden.judged_queries)
    # The operational reading needs the bucket of every JUDGED document, not only of the ones
    # this configuration retrieved, because the ideal ordering is built from the same gain
    # function. One statement per run, and `None` for a configuration that reads no signal —
    # which is what makes the third reading absent rather than equal to the graded one.
    buckets = (
        await search.scope_buckets(UUID(config.signal_pos_id))
        if config.signal_pos_id
        else None
    )
    ranked: dict[str, tuple[str, ...]] = {}
    abstained: dict[str, bool] = {}
    cold: list[Sample] = []
    warm: list[Sample] = []

    for query in queries:
        runs: list[QueryRun] = []
        for attempt in range(max(repeat, 1)):
            run = await execute(
                config,
                query.id,
                query.text,
                settings=settings,
                search=search,
                embed=embed,
                depth=config.max_results,
            )
            runs.append(run)
            (cold if attempt == 0 else warm).append(run.sample)
        # Every repetition returns the same list — that is what the deterministic tiebreak and
        # the frozen vectors buy — so the first is as good as any for the ranking itself.
        ranked[query.id] = tuple(str(hit.product_id) for hit in runs[0].hits)
        abstained[query.id] = runs[0].low_confidence

    cases = [
        score_case(
            golden,
            query.id,
            [UUID(value) for value in ranked[query.id]],
            abstained=abstained[query.id],
            buckets=buckets,
        )
        for query in queries
    ]

    per_origin: dict[str, list[CaseMetrics]] = {"real": [], "synthetic": []}
    for query in queries:
        for origin in ("real", "synthetic"):
            if any(
                item.data_origin == origin
                for item in golden.relevant_documents(query.id)
            ):
                per_origin[origin].append(
                    score_case(
                        golden,
                        query.id,
                        [UUID(value) for value in ranked[query.id]],
                        abstained=abstained[query.id],
                        origin=origin,
                    )
                )

    by_category: dict[str, Aggregate] = {}
    for category in sorted({query.category for query in queries}):
        members = {query.id for query in queries if query.category == category}
        by_category[category] = aggregate(
            [case for case in cases if case.query_id in members]
        )

    out_of_domain = {
        query.id for query in queries if query.category == OUT_OF_DOMAIN
    }
    cost = (
        prices.cost(
            settings.jpv_embedding_model or "", input_tokens=QUERY_TOKENS
        )
        if config.uses_provider
        else 0.0
    )

    return ConfigReport(
        config_id=config.id,
        label=config.label,
        provenance=provenance,
        readings=split_readings(golden, cases),
        by_origin=origin_readings(golden, per_origin),
        by_category=by_category,
        abstention_rate=abstention_rate(
            [case for case in cases if case.query_id in out_of_domain]
        ),
        latency=summarise(warm, cold=cold),
        cost_per_query_usd=cost,
        documents_omitted=0,
        cases=tuple(cases),
        ranked=ranked,
    )


async def run(
    configs: Sequence[EvalConfig],
    golden: GoldenSet,
    *,
    settings: Settings,
    search: ProductSearchPort,
    embed: EmbeddingClient | None,
    prices: PriceList,
    repeat: int = DEFAULT_REPEAT,
) -> Report:
    """Run every configuration in series and build the report. Never writes anything."""
    started = time.perf_counter()
    ids, hashes = await corpus_snapshot(settings)
    fingerprint = index_set_hash(ids)
    sha = current_git_sha()

    reports: list[ConfigReport] = []
    for config in configs:
        provenance = Provenance(
            golden_set_version=golden.version,
            config_id=config.id,
            index_set_hash=fingerprint,
            embedding_model_version_key=(
                embed.model_version_key if config.uses_provider and embed else None
            ),
            git_sha=sha,
        )
        reports.append(
            await run_config(
                config,
                golden,
                settings=settings,
                search=search,
                embed=embed,
                prices=prices,
                provenance=provenance,
                repeat=repeat,
            )
        )

    distances = (
        await judged_distances(golden, settings=settings, embed=embed)
        if embed is not None
        else []
    )

    return Report(
        run_id=str(uuid4()),
        generated_at=datetime.now(tz=UTC),
        golden_set_version=golden.version,
        index_set_hash=fingerprint,
        git_sha=sha,
        corpus_size=len(ids),
        configs=tuple(reports),
        distance_distribution=grade_distribution(distances),
        stale_judgements=stale_judgements(golden, hashes),
        price_list=prices,
        notes=(f"wall clock {round(time.perf_counter() - started, 1)} s",),
    )
