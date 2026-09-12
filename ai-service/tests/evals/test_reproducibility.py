"""Two runs of one configuration give the same numbers, and the sink is optional. C24.

An arnés that cannot repeat a measurement cannot detect a regression, which is the use that
makes one worth having. The property is exercised end to end here — golden set, orchestrator,
metrics, report — against an in-memory index and frozen vectors, so it holds on a machine with
no provider key and no database.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa

from jbg_ai.evals.configs import load_config
from jbg_ai.evals.golden import GoldenQuery, GoldenSet, Judgement, content_version
from jbg_ai.evals.pricing import load_prices
from jbg_ai.evals.provenance import Provenance
from jbg_ai.evals.runner import run_config
from jbg_ai.evals.vectors import FrozenEmbeddingClient
from support.fake_product_search import FakeIndexedRow, FakeProductSearch
from support.settings import build_settings

TIED_A = UUID("11111111-1111-1111-1111-111111111111")
TIED_B = UUID("99999999-9999-9999-9999-999999999999")
QUERY = "anillo de plata"


def _golden(tmp_path: Path) -> GoldenSet:
    root = tmp_path / "g"
    root.mkdir(exist_ok=True)
    (root / "criterion.md").write_text("x", encoding="utf-8")
    (root / "queries.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "judgements.jsonl").write_text("{}\n", encoding="utf-8")
    query = GoldenQuery(
        id="q1",
        text=QUERY,
        category="materiales",
        in_tuning_set=False,
        judged=True,
        judged_depth=20,
    )
    judgements = (
        Judgement(
            query_id="q1",
            product_id=str(TIED_A),
            grade=2,
            pooled_in=("v2-hibrido",),
            judged_at="2026-09-07",
            source_hash="0" * 64,
            data_origin="real",
            lexically_reachable=True,
        ),
        Judgement(
            query_id="q1",
            product_id=str(TIED_B),
            grade=0,
            pooled_in=("v2-hibrido",),
            judged_at="2026-09-07",
            source_hash="0" * 64,
            data_origin="real",
            lexically_reachable=True,
        ),
    )
    return GoldenSet(
        version=content_version(root),
        root=root,
        queries=(query,),
        judgements=judgements,
        by_query={"q1": judgements},
    )


def _search() -> FakeProductSearch:
    """Two documents the ordering cannot separate, so the tiebreak is what decides."""
    return FakeProductSearch(
        [
            FakeIndexedRow(
                product_id=TIED_B,
                sku="tied-high",
                distance=0.25,
                doc_text="Tipo: anillo. Materiales: plata.",
                piece_type="anillo",
                materials=["plata"],
            ),
            FakeIndexedRow(
                product_id=TIED_A,
                sku="tied-low",
                distance=0.25,
                doc_text="Tipo: anillo. Materiales: plata.",
                piece_type="anillo",
                materials=["plata"],
            ),
        ]
    )


def _embed() -> FrozenEmbeddingClient:
    return FrozenEmbeddingClient(
        model="openai/text-embedding-3-small", by_text={QUERY: (0.1,) * 4}
    )


async def _run_once(tmp_path: Path):
    golden = _golden(tmp_path)
    return await run_config(
        load_config("v2b-fusion"),
        golden,
        settings=build_settings(
            stub_mode=False, jpv_embedding_model="openai/text-embedding-3-small"
        ),
        search=_search(),
        embed=_embed(),
        prices=load_prices(),
        provenance=Provenance(
            golden_set_version=golden.version,
            config_id="v2b-fusion",
            index_set_hash="0" * 64,
            embedding_model_version_key="openai/text-embedding-3-small:1536",
            git_sha="a03b4ad",
            fusion_mode="branch",
        ),
        repeat=2,
    )


def test_repeating_a_run_yields_identical_metrics(tmp_path: Path) -> None:
    first = asyncio.run(_run_once(tmp_path))
    second = asyncio.run(_run_once(tmp_path))

    assert first.readings["global"].values == second.readings["global"].values
    assert first.ranked == second.ranked
    assert first.provenance == second.provenance


def test_the_same_document_survives_the_tie_on_every_run(tmp_path: Path) -> None:
    """Without the deterministic key this test passes while the harness produces noise."""
    rankings = {asyncio.run(_run_once(tmp_path)).ranked["q1"] for _ in range(3)}

    assert len(rankings) == 1
    assert next(iter(rankings))[0] == str(TIED_A), "the lower identifier breaks the tie"


def test_the_harness_never_calls_the_provider_during_a_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The vectors are frozen, so a run costs nothing and cannot depend on a network.

    The provider ADAPTER is what gets blocked, not the socket layer: on Windows the event loop
    opens a socket pair of its own for its self-pipe, so forbidding sockets outright would fail
    the test for a reason that has nothing to do with the provider.
    """
    import litellm

    async def _forbidden(**_kwargs: object) -> None:
        raise AssertionError("an evaluation run must not call the embedding provider")

    monkeypatch.setattr(litellm, "aembedding", _forbidden)

    report = asyncio.run(_run_once(tmp_path))

    assert report.cost_per_query_usd > 0, "the cost is priced from the file, not from a call"


@pytest.mark.db
def test_a_persisted_report_can_be_read_back_through_the_repository(
    migrated: sa.Engine, database_url: str, tmp_path: Path
) -> None:
    """The optional half: with `--persist`, the published route has something to serve."""
    from jbg_ai.evals.repository import persist, read_runs
    from jbg_ai.evals.runner import Report

    from datetime import UTC, datetime
    from uuid import uuid4

    golden = _golden(tmp_path)
    config_report = asyncio.run(_run_once(tmp_path))
    report = Report(
        run_id=str(uuid4()),
        generated_at=datetime(2026, 9, 7, 10, tzinfo=UTC),
        golden_set_version=golden.version,
        index_set_hash="0" * 64,
        git_sha="a03b4ad",
        corpus_size=2,
        configs=(config_report,),
        distance_distribution={},
        stale_judgements=0,
        price_list=load_prices(),
    )
    settings = build_settings(
        stub_mode=False,
        database_url=database_url.replace("postgresql://", "postgresql+psycopg://"),
    )

    async def _round_trip() -> list[dict]:
        from jbg_ai.db.engine import dispose_engine

        await persist(report, golden, settings=settings)
        rows = await read_runs(settings=settings, limit=10)
        await dispose_engine()
        return rows

    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    rows = asyncio.run(_round_trip())

    assert [row["suite"] for row in rows] == ["v2b-fusion"]
    assert rows[0]["status"] == "completed"
    assert any(metric["name"] == "global.ndcg_at_5" for metric in rows[0]["metrics"])

    with migrated.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM ai.eval_case")).scalar() == 1
        assert connection.execute(sa.text("SELECT count(*) FROM ai.eval_result")).scalar() >= 1


@pytest.mark.db
def test_the_zero_cost_baselines_are_persisted_like_any_other_row(
    migrated: sa.Engine, database_url: str, tmp_path: Path
) -> None:
    """A table of ablations missing its reference rows is not a table of ablations.

    And the baselines are the rows most easily lost: they call no provider, so a sink written
    around "what the provider cost" would drop exactly the two rows the comparison rests on.
    They are also the ones that record NULL for the embedding model, which is a value and not a
    gap — it says the run does not depend on the embedder.
    """
    from datetime import UTC, datetime
    from uuid import uuid4

    from jbg_ai.evals.repository import persist, read_runs
    from jbg_ai.evals.runner import Report

    golden = _golden(tmp_path)
    hybrid = asyncio.run(_run_once(tmp_path))
    lexical = replace(
        hybrid,
        config_id="v0-fts",
        label="baseline",
        cost_per_query_usd=0.0,
        provenance=replace(hybrid.provenance, config_id="v0-fts", embedding_model_version_key=None),
    )
    report = Report(
        run_id=str(uuid4()),
        generated_at=datetime(2026, 9, 7, 10, tzinfo=UTC),
        golden_set_version=golden.version,
        index_set_hash="0" * 64,
        git_sha="a03b4ad",
        corpus_size=2,
        configs=(hybrid, lexical),
        distance_distribution={},
        stale_judgements=0,
        price_list=load_prices(),
    )
    settings = build_settings(
        stub_mode=False,
        database_url=database_url.replace("postgresql://", "postgresql+psycopg://"),
    )

    async def _round_trip() -> list[dict]:
        from jbg_ai.db.engine import dispose_engine

        await persist(report, golden, settings=settings)
        rows = await read_runs(settings=settings, limit=10)
        await dispose_engine()
        return rows

    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    rows = asyncio.run(_round_trip())

    assert sorted(row["suite"] for row in rows) == ["v0-fts", "v2b-fusion"]
    costs = {
        row["suite"]: next(
            metric["value"]
            for metric in row["metrics"]
            if metric["name"] == "cost_per_query_usd"
        )
        for row in rows
    }
    assert costs["v0-fts"] == 0.0, "zero is a recorded value, never an absent one"

    with migrated.connect() as connection:
        stored = dict(
            connection.execute(
                sa.text(
                    "SELECT config_id, embedding_model_version_key FROM ai.eval_run"
                )
            ).all()
        )
    assert stored["v0-fts"] is None
    assert stored["v2b-fusion"] is not None
