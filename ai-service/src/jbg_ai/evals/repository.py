"""Optional sink: a `Report` into `ai.eval_run`, `ai.eval_case` and `ai.eval_result`. C24.

Nothing imports this except the CLI, and only when persistence is asked for. The runner does
not know it exists, which is the point: the producer builds a `Report` and does not know its
consumers, so an evaluation still produces its evidence when there is no database at all.

**Why the tables exist is contract, not utility.** Nobody will run SQL against them — the
reports are in git and diffable, which is more convenient — but `GET /v1/evals/runs` has been
published in the frozen OpenAPI snapshot since the service's second change, the live
specification describes it, and its placeholder named this change in writing as the one that
would deliver it. Leaving a published route lying costs more to explain than to implement.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text

from jbg_ai.config.settings import Settings
from jbg_ai.db.engine import session_scope
from jbg_ai.evals.golden import GoldenSet
from jbg_ai.evals.runner import Report

STATUS_COMPLETED = "completed"

_INSERT_RUN = """
INSERT INTO ai.eval_run (
    run_id, config_id, golden_set_version, index_set_hash, embedding_model_version_key,
    git_sha, started_at, finished_at, status, metrics, documents_omitted, notes
) VALUES (
    :run_id, :config_id, :golden_set_version, :index_set_hash, :embedding_model_version_key,
    :git_sha, :started_at, :finished_at, :status, CAST(:metrics AS jsonb),
    :documents_omitted, :notes
)
"""

_INSERT_CASE = """
INSERT INTO ai.eval_case (
    run_id, query_id, category, in_tuning_set, data_origin_bucket, judged_depth, metrics
) VALUES (
    :run_id, :query_id, :category, :in_tuning_set, :data_origin_bucket, :judged_depth,
    CAST(:metrics AS jsonb)
)
"""

_INSERT_RESULT = """
INSERT INTO ai.eval_result (run_id, query_id, product_id, rank, score, grade, unjudged)
VALUES (:run_id, :query_id, :product_id, :rank, :score, :grade, :unjudged)
"""


async def persist(report: Report, golden: GoldenSet, *, settings: Settings) -> list[UUID]:
    """Write one row per configuration and its cases and results. Returns the run identifiers.

    One `eval_run` per CONFIGURATION rather than one per invocation: the published contract
    returns a run with a suite and a status, and an ablation table is a set of comparable runs.
    Collapsing five configurations into one row would make the route describe something the
    report does not.

    The zero-cost baselines are persisted like any other. A table of ablations missing its
    reference rows is not a table of ablations.
    """
    run_ids: list[UUID] = []
    async with session_scope(settings) as session:
        for item in report.configs:
            run_id = UUID(report.run_id) if len(report.configs) == 1 else _derive(report, item)
            run_ids.append(run_id)
            await session.execute(
                text(_INSERT_RUN),
                {
                    "run_id": run_id,
                    "config_id": item.config_id,
                    "golden_set_version": report.golden_set_version,
                    "index_set_hash": report.index_set_hash,
                    "embedding_model_version_key": (
                        item.provenance.embedding_model_version_key
                    ),
                    "git_sha": report.git_sha,
                    "started_at": report.generated_at,
                    "finished_at": report.generated_at,
                    "status": STATUS_COMPLETED,
                    "metrics": json.dumps(
                        {
                            **{
                                f"{reading}.{name}": value
                                for reading, agg in item.readings.items()
                                for name, value in agg.values.items()
                            },
                            "abstention_rate": item.abstention_rate,
                            "cost_per_query_usd": item.cost_per_query_usd,
                            **item.latency.as_dict(),
                        }
                    ),
                    "documents_omitted": item.documents_omitted,
                    "notes": item.label,
                },
            )
            for case in item.cases:
                query = golden.query(case.query_id)
                await session.execute(
                    text(_INSERT_CASE),
                    {
                        "run_id": run_id,
                        "query_id": case.query_id,
                        "category": query.category,
                        "in_tuning_set": query.in_tuning_set,
                        "data_origin_bucket": golden.origin_bucket(case.query_id),
                        "judged_depth": query.judged_depth or 0,
                        "metrics": json.dumps(case.as_dict()),
                    },
                )
                for rank, product_id in enumerate(item.ranked.get(case.query_id, ()), start=1):
                    grade = golden.grade(case.query_id, product_id)
                    await session.execute(
                        text(_INSERT_RESULT),
                        {
                            "run_id": run_id,
                            "query_id": case.query_id,
                            "product_id": UUID(product_id),
                            "rank": rank,
                            "score": 0.0,
                            "grade": grade,
                            "unjudged": grade is None,
                        },
                    )
    return run_ids


def _derive(report: Report, item) -> UUID:
    """A stable identifier per `(run, configuration)`.

    Derived rather than random so that re-persisting a report cannot silently duplicate it: the
    primary key rejects the second attempt instead of leaving two copies of one measurement.
    """
    import hashlib

    digest = hashlib.sha256(f"{report.run_id}:{item.config_id}".encode()).hexdigest()
    return UUID(digest[:32])


_LIST_RUNS = """
SELECT run_id, config_id, status, started_at, finished_at, metrics
FROM ai.eval_run
ORDER BY started_at DESC, run_id
LIMIT :limit
"""


async def read_runs(*, settings: Settings, limit: int = 50) -> list[dict]:
    """The persisted runs, most recent first. An empty history is an empty list, not an error.

    "No evaluation has been run against this database" is a valid answer and a common one:
    the report always lands in the repository and persistence is opt-in, so a perfectly healthy
    deployment can have nothing here.
    """
    async with session_scope(settings) as session:
        rows = (await session.execute(text(_LIST_RUNS), {"limit": limit})).mappings().all()
    return [
        {
            "run_id": str(row["run_id"]),
            # `suite` in the published contract is what was evaluated. The configuration is
            # what distinguishes one row of an ablation table from another, so that is what
            # goes here rather than a constant nobody could tell apart.
            "suite": str(row["config_id"]),
            "status": str(row["status"]),
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "metrics": [
                {"name": name, "value": float(value)}
                for name, value in sorted((row["metrics"] or {}).items())
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ],
        }
        for row in rows
    ]
