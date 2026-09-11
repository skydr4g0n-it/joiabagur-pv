"""eval_run, eval_case, eval_result

The three evaluation tables (C24). Hand-written like every revision here; do not
autogenerate — C05 left HNSW/GIN indexes and generated columns that autogen would
rewrite.

Additive: three new tables in schema `ai`, nothing existing altered. The downgrade
drops exactly them and leaves no trace, which it can only do because no enumerated
type is created — the closed vocabularies are CHECK constraints, for the reason the
foundation revision records.

Four choices in here are decisions rather than defaults:

* **`metrics` is `jsonb`, not a column per metric.** C38 adds generation metrics to
  the same runner, and a shape that forced a second revision for every metric added
  would make the harness expensive to extend at exactly the moment it is supposed to
  be cheap. The cost is that no metric is constrained by the schema; the artefact in
  git is the normative copy, and these tables are the queryable one.
* **No foreign key on `product_id`.** Same boundary as `ai.product_document`: the
  identifier is assigned by the .NET side. And a key into `ai.product_document` would
  be worse than useless — deactivating a product would cascade away the evaluation
  history that recorded how it once ranked, which is the one thing an evaluation
  archive exists to keep.
* **`embedding_model_version_key` is nullable, and NULL is a recorded value.** The two
  lexical baselines call no embedder at all, so they have no embedding model version.
  Writing the live one in anyway would assert a dependency they do not have, and would
  make a model change mark them incomparable with their own earlier runs for no reason.
  NULL here means "this configuration does not depend on the embedder", never "unknown".
* **The identity of a case is `(run_id, query_id)` and of a result `(run_id, query_id,
  rank)`.** Those are the composite primary keys, so the indexes the design asks for on
  exactly those columns exist as the keys themselves rather than beside them, and a
  duplicated case, or two documents claiming one rank position, are rejected by the
  database rather than by the writer remembering to check.

Revision ID: d7c4e91b25a0
Revises: c9a71f2b6d54
Create Date: 2026-09-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7c4e91b25a0"
down_revision: str | None = "c9a71f2b6d54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AI = "ai"

#: A run is `running` until it finishes, then `completed` or `failed`. Closed as a CHECK
#: and not as a type: a type created for a column outlives its table, so a revert would
#: leave it orphaned and the next upgrade would fail on "type already exists".
RUN_STATUS = ("running", "completed", "failed")

#: How a query is grouped for the origin breakdown, decided by the origin of its RELEVANT
#: documents and never by restricting the corpus. `NULL` is the out-of-domain category,
#: which has no relevant document to take an origin from.
ORIGIN_BUCKET = ("real", "synthetic", "mixed")


def _in_list(column: str, values: Sequence[str]) -> str:
    return f"{column} IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    _create_eval_run()
    _create_eval_case()
    _create_eval_result()


def downgrade() -> None:
    """Drop the three tables, children first. Nothing else in `ai` is touched."""
    op.drop_table("eval_result", schema=AI)
    op.drop_table("eval_case", schema=AI)
    op.drop_table("eval_run", schema=AI)


def _create_eval_run() -> None:
    """One row per configuration evaluated once, with the provenance that makes it comparable."""
    op.create_table(
        "eval_run",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_id", sa.Text(), nullable=False),
        # The five-part provenance tuple: golden set, configuration, index fingerprint,
        # embedding model and code revision. Two runs whose tuple differs are reported as
        # not comparable rather than compared — which is the whole reason it is stored on
        # the run and not in a log.
        sa.Column("golden_set_version", sa.Text(), nullable=False),
        sa.Column("index_set_hash", sa.CHAR(64), nullable=False),
        sa.Column("embedding_model_version_key", sa.Text()),
        sa.Column("git_sha", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # How much of the catalogue a context-only configuration never saw. Zero is the
        # ordinary value and is recorded rather than left absent, so a recall figure is
        # never read without knowing whether it was computed over a truncated catalogue.
        sa.Column(
            "documents_omitted",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(_in_list("status", RUN_STATUS), name="ck_eval_run_status"),
        sa.CheckConstraint("documents_omitted >= 0", name="ck_eval_run_documents_omitted"),
        schema=AI,
    )
    # The two access paths a report takes: every run of one configuration, and the most
    # recent runs regardless of configuration — which is the order `GET /v1/evals/runs`
    # serves in.
    op.create_index("ix_eval_run_config_id", "eval_run", ["config_id"], schema=AI)
    op.create_index("ix_eval_run_started_at", "eval_run", ["started_at"], schema=AI)


def _create_eval_case() -> None:
    """One row per query inside a run: how it grouped, how deep it was judged, how it scored."""
    op.create_table(
        "eval_case",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        # Carried per case and not derived at read time: the split the report publishes
        # three readings over has to be the one the run actually used, even if the golden
        # set is re-marked afterwards.
        sa.Column("in_tuning_set", sa.Boolean(), nullable=False),
        sa.Column("data_origin_bucket", sa.Text()),
        sa.Column("judged_depth", sa.Integer(), nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            [f"{AI}.eval_run.run_id"],
            name="fk_eval_case_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "query_id", name="pk_eval_case"),
        sa.CheckConstraint(
            "data_origin_bucket IS NULL OR " + _in_list("data_origin_bucket", ORIGIN_BUCKET),
            name="ck_eval_case_data_origin_bucket",
        ),
        sa.CheckConstraint("judged_depth >= 0", name="ck_eval_case_judged_depth"),
        schema=AI,
    )


def _create_eval_result() -> None:
    """One row per position of a query's result list, with the judgement it was scored against."""
    op.create_table(
        "eval_result",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_id", sa.Text(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("grade", sa.SmallInteger()),
        sa.Column("unjudged", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            [f"{AI}.eval_run.run_id"],
            name="fk_eval_result_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", "query_id", "rank", name="pk_eval_result"),
        sa.CheckConstraint("grade IS NULL OR grade IN (0, 1, 2)", name="ck_eval_result_grade"),
        # The one invariant that keeps `unjudged@5` honest: a row is unjudged exactly when
        # it carries no grade. Storing the flag and the grade independently would let a
        # writer report a comfortable unjudged rate over rows that do have grades, or a
        # grade of 0 for a document nobody ever looked at — which is the difference between
        # "measured irrelevant" and "not measured", and the whole reason the metric exists.
        sa.CheckConstraint(
            "(grade IS NULL) = unjudged",
            name="ck_eval_result_unjudged_matches_grade",
        ),
        sa.CheckConstraint("rank >= 1", name="ck_eval_result_rank"),
        schema=AI,
    )
