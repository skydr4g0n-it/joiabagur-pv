"""`uv run evals …` — the evaluation harness command line. C24.

    uv run evals run --config v2-hibrido [--persist] [--repeat 3]
    uv run evals run --all --name c24-baselines-2026-09-07.md
    uv run evals cag                 # the context-only measurement, dated and separate
    uv run evals freeze-vectors      # once, against the real provider
    uv run evals validate            # the golden set alone, no database, no provider

Two Windows traps this has to handle, both development-machine problems that will never
reproduce in the Linux container: psycopg cannot run async on the default event loop policy,
and LiteLLM verifies TLS against `certifi` rather than the operating system store. The first is
handled here; the second needs `SSL_CERT_FILE` in the environment and the README says so.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from jbg_ai.evals.configs import ABLATION_ORDER, load_all, load_config
from jbg_ai.evals.errors import EvalError, EvaluationUnavailable
from jbg_ai.evals.golden import load_golden_set
from jbg_ai.evals.pricing import load_prices

DEFAULT_REPORT_PREFIX = "c24-baselines"

#: Named because it is joined into report bodies that are themselves full of f-strings.
NEWLINE = "\n"


def _report_name(explicit: str | None) -> str:
    if explicit:
        return explicit
    return f"{DEFAULT_REPORT_PREFIX}-{datetime.now(tz=UTC).date().isoformat()}.md"


def _load_cag_summary(args: argparse.Namespace) -> dict | None:
    """The context-only summary, if `uv run evals cag` has been run. Absence is normal."""
    import json

    from jbg_ai.evals.cag_run import RESULTS_DIR, SUMMARY_NAME

    path = (Path(args.out) if args.out else RESULTS_DIR) / SUMMARY_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


async def _run(args: argparse.Namespace) -> int:
    from jbg_ai.evals import report as report_module
    from jbg_ai.evals.execute import build_search, harness_settings
    from jbg_ai.evals.runner import run
    from jbg_ai.evals.vectors import FrozenEmbeddingClient

    golden = load_golden_set()
    configs = (
        [item for item in load_all() if item.id in ABLATION_ORDER and item.pooled]
        if args.all
        else [load_config(args.config)]
    )
    configs = [item for item in configs if item.pooled]
    if not configs:
        raise EvaluationUnavailable(
            "no ranked-list configuration selected. `v0-cag` answers in prose and is measured "
            "by `uv run evals cag`, which records its model and its date"
        )

    settings = harness_settings()
    search = build_search(settings)
    embed = FrozenEmbeddingClient.from_file(settings.jpv_embedding_model or "")
    prices = load_prices()

    result = await run(
        configs,
        golden,
        settings=settings,
        search=search,
        embed=embed,
        prices=prices,
        repeat=args.repeat,
    )

    # The context-only measurement is dated and irreproducible, so it is taken separately and
    # folded in if it exists. Re-running it on every evaluation would put a figure that cannot
    # be repeated inside a table whose whole point is that its rows can.
    result = replace(result, cag=_load_cag_summary(args))

    target = report_module.write(
        result,
        title=args.title or "C24 — líneas base de recuperación con relevancia graduada",
        name=_report_name(args.name),
        out_dir=Path(args.out) if args.out else None,
    )
    sys.stdout.write(f"wrote {target}\n")

    if args.persist:
        from jbg_ai.evals.repository import persist

        run_ids = await persist(result, golden, settings=settings)
        sys.stdout.write(f"persisted {len(run_ids)} runs into ai.eval_run\n")

    from jbg_ai.db.engine import dispose_engine

    await dispose_engine()
    return 0


async def _freeze(args: argparse.Namespace) -> int:
    import os

    from jbg_ai.evals.golden import load_queries
    from jbg_ai.evals.vectors import FrozenVector, write_vectors
    from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL
    from jbg_ai.indexing.embeddings import LiteLlmEmbeddingClient, model_version_key

    queries = [item for item in load_queries() if item.judged]
    model = os.environ.get("JPV_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
    key = os.environ.get("JPV_EMBEDDING_API_KEY")
    if not key:
        raise EvaluationUnavailable(
            "JPV_EMBEDDING_API_KEY is required to freeze the query vectors. They are frozen "
            "ONCE against the real provider: a stand-in embedder cannot arbitrate a dispute "
            "between a lexical branch and a vector one, because it is one of the parties"
        )
    client = LiteLlmEmbeddingClient(api_key=key, model=model)
    result = await client.embed([item.text for item in queries])
    path = write_vectors(
        [
            FrozenVector(
                query_id=item.id,
                text=item.text,
                model_version_key=model_version_key(model),
                vector=tuple(vector),
            )
            for item, vector in zip(queries, result.vectors, strict=True)
        ]
    )
    sys.stdout.write(f"froze {len(queries)} vectors into {path}\n")
    return 0


def _validate(_args: argparse.Namespace) -> int:
    golden = load_golden_set()
    sys.stdout.write(
        f"golden set {golden.version}: {len(golden.queries)} queries "
        f"({len(golden.judged_queries)} judged), {len(golden.judgements)} judgements\n"
    )
    return 0


async def _sweep(args: argparse.Namespace) -> int:
    from jbg_ai.db.engine import dispose_engine
    from jbg_ai.evals.execute import build_search, harness_settings
    from jbg_ai.evals.provenance import Provenance, current_git_sha, index_set_hash
    from jbg_ai.evals.runner import corpus_snapshot
    from jbg_ai.evals.sweep import decide, sweep
    from jbg_ai.evals.vectors import FrozenEmbeddingClient

    golden = load_golden_set()
    config = load_config(args.config)
    settings = harness_settings()
    search = build_search(settings)
    embed = FrozenEmbeddingClient.from_file(settings.jpv_embedding_model or "")
    ids, _ = await corpus_snapshot(settings)
    provenance = Provenance(
        golden_set_version=golden.version,
        config_id=config.id,
        index_set_hash=index_set_hash(ids),
        embedding_model_version_key=embed.model_version_key,
        git_sha=current_git_sha(),
    )
    baseline, candidates = await sweep(
        config,
        golden,
        settings=settings,
        search=search,
        embed=embed,
        prices=load_prices(),
        provenance=provenance,
        repeat=1,
    )
    verdict = decide(baseline, candidates)

    lines = [
        "# C24 — barrido direccional del peso de la rama vectorial y de la profundidad",
        "",
        "La regla que decide se escribió **antes** de medir; ver `evals/sweep.py`. El barrido "
        "es direccional: la rúbrica que fijó los pesos vigentes es la función objetivo de la "
        "rama léxica, así que infravalora la vectorial por construcción y el óptimo verdadero "
        "no puede estar por debajo del valor en vigor.",
        "",
        "| wC | profundidad | nDCG@5 global | sólo ajuste | sólo nuevas |",
        "|---:|---:|---:|---:|---:|",
    ]
    for point in sorted(
        [baseline, *candidates], key=lambda item: (item.weight_vector, item.branch_depth)
    ):
        mark = " **(vigente)**" if point is baseline else ""
        lines.append(
            f"| {point.weight_vector}{mark} | {point.branch_depth} | "
            f"{point.score('global'):.3f} | {point.score('tuning'):.3f} | "
            f"{point.score('new'):.3f} |"
        )
    lines += ["", "## Veredicto de la regla", "", *verdict.as_lines(), ""]

    target_dir = Path(args.out) if args.out else Path("evals/results")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (args.name or "c24-sweep.md")
    target.write_text(NEWLINE.join(lines), encoding="utf-8")
    sys.stdout.write(f"wrote {target}\n")
    await dispose_engine()
    return 0


async def _provider_latency(args: argparse.Namespace) -> int:
    """Measure the embedding provider itself: cold, warm, and the singleton cache.

    This is what the frozen vectors deliberately remove from the run, and what the end-to-end
    column therefore cannot contain. It also settles the two measurements the fusion change
    left without an owner: what the provider round trip really costs inside the orchestrator,
    and what the process-wide client with its bounded cache is worth on a repeated query.
    """
    import os
    import time

    from jbg_ai.evals.golden import load_queries
    from jbg_ai.evals.latency import percentile
    from jbg_ai.indexing.constants import DEFAULT_EMBEDDING_MODEL
    from jbg_ai.retrieval.cache import BoundedEmbeddingCache
    from jbg_ai.indexing.embeddings import LiteLlmEmbeddingClient

    key = os.environ.get("JPV_EMBEDDING_API_KEY")
    if not key:
        raise EvaluationUnavailable("JPV_EMBEDDING_API_KEY is required to time the provider")
    client = LiteLlmEmbeddingClient(
        api_key=key,
        model=os.environ.get("JPV_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
        max_attempts=1,
        cache=BoundedEmbeddingCache(),
    )
    queries = [item.text for item in load_queries() if item.judged][: args.limit]

    cold: list[float] = []
    warm: list[float] = []
    for text_value in queries:
        started = time.perf_counter()
        await client.embed([text_value])
        cold.append((time.perf_counter() - started) * 1000)
    for text_value in queries:
        started = time.perf_counter()
        await client.embed([text_value])
        warm.append((time.perf_counter() - started) * 1000)

    sys.stdout.write(
        "provider round trip over {n} queries\n"
        "  cold (cache miss): p50 {c50:.1f} ms · p95 {c95:.1f} ms\n"
        "  warm (cache hit) : p50 {w50:.1f} ms · p95 {w95:.1f} ms\n".format(
            n=len(queries),
            c50=percentile(cold, 0.50) or 0.0,
            c95=percentile(cold, 0.95) or 0.0,
            w50=percentile(warm, 0.50) or 0.0,
            w95=percentile(warm, 0.95) or 0.0,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evals")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Evaluate one configuration, or the ablation table")
    run_cmd.add_argument("--config", default=None, help="Configuration id, e.g. v2-hibrido")
    run_cmd.add_argument("--all", action="store_true", help="Every ranked-list configuration")
    run_cmd.add_argument("--persist", action="store_true", help="Also write ai.eval_*")
    run_cmd.add_argument("--repeat", type=int, default=3, help="Executions per query")
    run_cmd.add_argument("--out", default=None, help="Directory for the report")
    run_cmd.add_argument("--name", default=None, help="Report file name")
    run_cmd.add_argument("--title", default=None, help="Report title")

    cag = sub.add_parser("cag", help="The context-only measurement (dated, not reproducible)")
    cag.add_argument("--out", default=None, help="Directory for the JSON summary")
    cag.add_argument("--dry-run", action="store_true", help="Size and cost only, no model call")

    sweep_cmd = sub.add_parser("sweep", help="Directional sweep of the fusion knobs (D13)")
    sweep_cmd.add_argument("--config", default="v2-hibrido")
    sweep_cmd.add_argument("--out", default=None)
    sweep_cmd.add_argument("--name", default=None)

    provider = sub.add_parser(
        "provider-latency", help="Time the embedding provider itself, cold and warm"
    )
    provider.add_argument("--limit", type=int, default=48)

    sub.add_parser("freeze-vectors", help="Freeze the query vectors against the real provider")
    sub.add_parser("validate", help="Load and validate the golden set. No database, no provider")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "run" and not args.all and not args.config:
        parser.error("run needs --config <id> or --all")

    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "cag":
            from jbg_ai.evals.cag_run import measure

            return asyncio.run(measure(args))
        if args.command == "freeze-vectors":
            return asyncio.run(_freeze(args))
        if args.command == "sweep":
            return asyncio.run(_sweep(args))
        if args.command == "provider-latency":
            return asyncio.run(_provider_latency(args))
        return asyncio.run(_run(args))
    except EvalError as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 1


def run_module(argv: Sequence[str] | None = None) -> int:
    """Process entry point. Loads `backend/.env`, where the local credentials live.

    Also installs the selector event loop policy on Windows: `psycopg` cannot run in async mode
    on the proactor loop, which is the default there, and the failure message names neither
    psycopg nor the policy.
    """
    from jbg_ai.data.envload import load_local_env

    load_local_env()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return main(argv)
