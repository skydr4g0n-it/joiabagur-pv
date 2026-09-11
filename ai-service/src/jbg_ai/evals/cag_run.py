"""Executing the context-only measurement. C24.

Separate from `cag.py`, which is pure and testable without a provider, and separate from the
runner, which produces the reproducible rows. This one calls a language model, so it is a
DATED measurement with its model recorded rather than a row that re-runs on every evaluation —
and keeping the two apart is what stops an irreproducible figure from silently entering a table
of reproducible ones.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.db.engine import dispose_engine, session_scope
from jbg_ai.evals.cag import build_context, build_prompt, answered_skus, scale_projection
from jbg_ai.evals.configs import load_config
from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.execute import harness_settings
from jbg_ai.evals.golden import load_golden_set
from jbg_ai.evals.metrics import CUTOFF
from jbg_ai.evals.pricing import load_prices

RESULTS_DIR = AI_SERVICE_ROOT / "evals" / "results"
SUMMARY_NAME = "c24-cag-measurement.json"

_CATALOGUE = """
SELECT product_id, sku, name, piece_type, materials
FROM ai.product_document
WHERE is_active IS TRUE
"""


def _count_tokens(model: str):
    from litellm import token_counter

    def _count(value: str) -> int:
        return int(token_counter(model=model.split("/")[-1], text=value))

    return _count


async def measure(args: argparse.Namespace) -> int:
    config = load_config("v0-cag")
    settings = harness_settings()
    golden = load_golden_set()
    prices = load_prices()
    model = config.context_model or "openai/gpt-4o-mini"
    budget = config.context_budget_tokens or 100_000

    async with session_scope(settings) as session:
        rows = [
            {
                "product_id": row[0],
                "sku": row[1],
                "name": row[2],
                "piece_type": row[3],
                "materials": list(row[4] or []),
            }
            for row in (await session.execute(text(_CATALOGUE))).all()
        ]
    await dispose_engine()

    catalogue = build_context(rows, budget_tokens=budget, count_tokens=_count_tokens(model))
    queries = [
        item
        for item in golden.judged_queries
        if item.category == (config.subset_category or "descripcion-sin-anclaje")
    ]

    summary: dict = {
        "model": model,
        "measured_at": datetime.now(tz=UTC).date().isoformat(),
        "documents_total": catalogue.documents_total,
        "documents_omitted": catalogue.documents_omitted,
        "tokens": catalogue.tokens,
        "budget_tokens": budget,
        "scale": scale_projection(catalogue, budget_tokens=budget),
        "queries": len(queries),
        "cost_per_query_usd": prices.cost(
            model, input_tokens=catalogue.tokens, output_tokens=60
        ),
        "price_verified": prices.verified,
    }

    if args.dry_run:
        summary["recall_at_5_capped"] = None
        summary["note"] = "dry run: size and cost only, no model was called"
    else:
        summary.update(await _ask(queries, catalogue, golden, model=model))

    target_dir = Path(args.out) if args.out else RESULTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / SUMMARY_NAME
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(f"wrote {path}\n")
    return 0


async def _ask(queries, catalogue, golden, *, model: str) -> dict:
    import os

    from litellm import acompletion

    key = os.environ.get("JPV_RAG_LLM_API_KEY")
    if not key:
        raise EvaluationUnavailable(
            "JPV_RAG_LLM_API_KEY is required for the context-only measurement. It is a "
            "different key from JPV_EMBEDDING_API_KEY on purpose"
        )
    by_sku = {
        item.sku: item.product_id
        for query in queries
        for item in golden.judgements_for(query.id)
        if item.sku
    }

    found: list[float] = []
    answers: dict[str, list[str]] = {}
    for query in queries:
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": build_prompt(query.text, catalogue)}],
            temperature=0,
            api_key=key,
            num_retries=1,
        )
        answer = response["choices"][0]["message"]["content"] or ""
        skus = answered_skus(answer)[:CUTOFF]
        answers[query.id] = skus
        relevant = {
            item.product_id for item in golden.relevant_documents(query.id)
        }
        hits = sum(1 for sku in skus if by_sku.get(sku) in relevant)
        total = len(relevant)
        found.append((hits / min(CUTOFF, total)) if total else 0.0)

    return {
        "recall_at_5_capped": sum(found) / len(found) if found else 0.0,
        "answers": answers,
    }
