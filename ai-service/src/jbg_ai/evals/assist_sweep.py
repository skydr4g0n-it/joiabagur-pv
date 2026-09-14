"""The context-width sweep of the generated argument. C30b.

**A dated measurement, not a reproducible row.** It calls a language model, so it lives beside
`cag_run.py` and not inside the runner that re-executes on every evaluation — keeping the two
apart is what stops an irreproducible figure from entering a table of reproducible ones.

What it measures, and the reading that matters is the **partition**:

    tasa de rechazo por causa   cifra ausente · adyacencia a moneda · adyacencia a stock
                                formato de enumeración · desacuerdo de separadores
    correspondencia             cuántas veces el tramo declarado no está en la prosa,
                                y de ésas cuántas lo estarían plegando la puntuación
    coste y latencia            tokens sumados, y cuántas generaciones habría cortado
                                el timeout de servicio

An aggregate rejection rate cannot tell a gate that works from a gate that gets in the way, so
no aggregate is published without its partition.

**It drives the real layer.** `generate_pitch` is the function the route calls; a harness that
re-implemented the loop would measure the re-implementation, which is the mistake this
repository already names in `evals/configs.py`. The only thing it changes is the provider
timeout, and for a stated reason: the serving value is three seconds, and measuring the gate
through a timeout that might cut everything would produce no measurement of the gate at all.
Latency is recorded and **the cut is reported separately**, which answers the same question
without destroying the primary one.

**This is the declared exception to the no-persistence rule.** The serving path never writes
the argument anywhere, log included; the harness writes the **complete generation object** —
the prose plus every declared citation with its supporting span — bound to a run identifier, a
commit and a prompt version. Not just the text: with the spans, C38 has claim↔citation pairs
already aligned and can measure faithfulness per claim instead of over the whole answer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import yaml

from jbg_ai.assist.constants import (
    CAUSE_CLAIM_NOT_IN_PITCH,
    DEFAULT_ASSIST_MODEL,
    DEFAULT_MATERIAL_CAP,
    PITCH_TIMEOUT_SECONDS,
    PITCH_VIOLATION_CAUSES,
    PROMPT_VERSION,
)
from jbg_ai.assist.grounding import ground_piece
from jbg_ai.assist.llm import LiteLlmAssistClient
from jbg_ai.assist.modes import AssistMode
from jbg_ai.assist.pitch import PitchOutcome, generate_pitch
from jbg_ai.assist.prompt import PitchCitation, payload_from
from jbg_ai.assist.verification import normalise_text
from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.db.engine import dispose_engine
from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.execute import harness_settings
from jbg_ai.evals.provenance import UNKNOWN_SHA
from jbg_ai.knowledge.search import SqlAlchemyKnowledgeIndex
from jbg_ai.retrieval.search import SqlAlchemyProductSearch

SAMPLE = AI_SERVICE_ROOT / "evals" / "assist" / "sweep-sample.yaml"
RESULTS_DIR = AI_SERVICE_ROOT / "evals" / "results"

#: Generous on purpose, and never the serving value. See the module docstring: the sweep
#: records latency and reports the cut separately instead of measuring through it.
SWEEP_TIMEOUT_SECONDS = 45.0

#: Punctuation, for the ONE question the sweep has to answer about the correspondence check:
#: would sign folding have saved this span? Classifying is not admitting — the check is
#: unchanged, and the threshold for changing it is declared at more than one failure in ten.
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def _git_sha() -> str:
    import subprocess

    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=AI_SERVICE_ROOT,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=AI_SERVICE_ROOT,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — a sweep outside a checkout still records something
        return UNKNOWN_SHA
    # A run taken on a dirty tree was NOT produced by the commit it names. C25 was bitten by
    # exactly this, and `provenance.py` records the rule; it is reused rather than restated.
    return f"{sha}+dirty" if dirty else sha


def load_sample(path: Path = SAMPLE) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _punctuation_only(claim: str, pitch: str) -> bool:
    """Would this span have matched with the signs folded away?"""
    folded = _PUNCTUATION.sub("", normalise_text(claim))
    return bool(folded) and folded in _PUNCTUATION.sub("", normalise_text(pitch))


def _row(
    *,
    arm: dict,
    stratum: str,
    product: dict,
    materials: list[str],
    citations: tuple,
    outcome: PitchOutcome,
) -> dict:
    initial = outcome.initial_generated
    correspondence = []
    if initial is not None:
        for violation in outcome.initial_violations:
            if violation.cause != CAUSE_CLAIM_NOT_IN_PITCH:
                continue
            claim = next(
                (
                    item.supported_claim
                    for item in initial.used
                    if item.citation_id == violation.citation_id
                ),
                "",
            )
            correspondence.append(
                {
                    "citation_id": violation.citation_id,
                    "punctuation_only": _punctuation_only(claim, initial.pitch),
                }
            )
    return {
        "stratum": stratum,
        "sections": arm["sections"],
        "section_slugs": list(arm["section_slugs"]),
        "product_id": product["product_id"],
        "sku": product["sku"],
        "declared_materials": materials,
        "citations_offered": [item.citation_id for item in citations],
        "provider_calls": outcome.usage.calls,
        "prompt_tokens": outcome.usage.prompt_tokens,
        "completion_tokens": outcome.usage.completion_tokens,
        "total_tokens": outcome.usage.total_tokens,
        "elapsed_ms": round(outcome.elapsed_ms, 1),
        # PER CALL, because the timeout is per call. Comparing a two-call request against a
        # one-call limit is how a five per cent cut reads as seventy, and the first pass of
        # this runner did exactly that.
        "call_latencies_ms": [round(item, 1) for item in outcome.call_latencies_ms],
        "calls_over_serving_timeout": sum(
            1
            for item in outcome.call_latencies_ms
            if item > PITCH_TIMEOUT_SECONDS * 1000.0
        ),
        "provider_error": outcome.provider_error,
        "initial_causes": [item.cause for item in outcome.initial_violations],
        "initial_figures": [
            item.figure for item in outcome.initial_violations if item.figure
        ],
        "surviving_causes": list(outcome.causes()),
        "correspondence_failures": correspondence,
        "published": not outcome.withheld,
        "published_citation_ids": list(outcome.used_citation_ids),
        "withdrawn_citation_ids": list(outcome.withdrawn_citation_ids),
        "pitch_chars": len(outcome.pitch),
        "pitch_sentences": len([s for s in outcome.pitch.split(".") if s.strip()]),
        # THE DECLARED EXCEPTION. The whole generation object, spans included, outside the
        # serving path and bound to the provenance written beside it.
        "generation": {
            "pitch": outcome.generated.pitch if outcome.generated else "",
            "used": [asdict_used(item) for item in (outcome.generated.used if outcome.generated else [])],
        },
        "initial_generation": {
            "pitch": initial.pitch if initial else "",
            "used": [asdict_used(item) for item in (initial.used if initial else [])],
        },
    }


def asdict_used(item) -> dict:  # noqa: ANN001 — a pydantic model, kept local and small
    return {"citation_id": item.citation_id, "supported_claim": item.supported_claim}


async def run(args: argparse.Namespace) -> int:
    sample = load_sample()
    settings = harness_settings()
    if not settings.database_url:
        raise EvaluationUnavailable("DATABASE_URL is required for the assist sweep")
    # Same resolution order the route uses, so the sweep measures the credential that would
    # actually serve rather than one the harness picked for itself.
    key = os.environ.get("JPV_ASSIST_LLM_API_KEY") or os.environ.get("JPV_RAG_LLM_API_KEY")
    if not key and not args.dry_run:
        raise EvaluationUnavailable(
            "JPV_ASSIST_LLM_API_KEY or JPV_RAG_LLM_API_KEY is required for the assist sweep. "
            "Either is a different credential from JPV_EMBEDDING_API_KEY"
        )

    arms = [
        arm
        for arm in sample["arms"]
        if not args.sections or arm["sections"] in args.sections
    ]
    products = [
        (name, item)
        for name, stratum in sample["strata"].items()
        for item in stratum["products"]
    ]
    if args.limit:
        products = products[: args.limit] + products[-args.limit :]

    run_id = uuid4().hex[:12]
    provenance = {
        "run_id": run_id,
        "git_sha": _git_sha(),
        "prompt_version": PROMPT_VERSION,
        "model": args.model,
        "sample_id": sample["id"],
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "material_cap": DEFAULT_MATERIAL_CAP,
        "sweep_timeout_seconds": SWEEP_TIMEOUT_SECONDS,
        "serving_timeout_seconds": PITCH_TIMEOUT_SECONDS,
    }
    print(json.dumps(provenance, indent=2))
    if args.dry_run:
        print(f"dry run: {len(arms)} arms x {len(products)} pieces = "
              f"{len(arms) * len(products)} generations, none executed")
        return 0

    search = SqlAlchemyProductSearch(settings)
    knowledge = SqlAlchemyKnowledgeIndex(settings)
    client = LiteLlmAssistClient(
        api_key=key, model=args.model, timeout=SWEEP_TIMEOUT_SECONDS
    )

    rows: list[dict] = []
    try:
        for arm in arms:
            for stratum, product in products:
                source = await search.source_document(UUID(product["product_id"]))
                if source is None:
                    print(f"  skipped {product['sku']}: not in the index", file=sys.stderr)
                    continue
                citations = await ground_piece(
                    source.materials,
                    index=knowledge,
                    sections=tuple(arm["section_slugs"]),
                    material_cap=DEFAULT_MATERIAL_CAP,
                )
                payload = payload_from(
                    sku=source.sku,
                    piece_type=source.piece_type,
                    materials=list(source.materials),
                    size_label=source.size_label,
                    citations=[
                        PitchCitation(
                            citation_id=item.citation_id,
                            document_title=item.document_title,
                            section_title=item.section_title,
                            claim_scope=item.claim_scope,
                            content=item.content,
                        )
                        for item in citations
                    ],
                )
                outcome = await generate_pitch(
                    payload, AssistMode.PIECE_ONLY, client=client
                )
                rows.append(
                    _row(
                        arm=arm,
                        stratum=stratum,
                        product=product,
                        materials=list(source.materials),
                        citations=citations,
                        outcome=outcome,
                    )
                )
                print(
                    f"  arm={arm['sections']} {product['sku']:>8} "
                    f"{'published' if rows[-1]['published'] else 'WITHHELD':>9} "
                    f"calls={rows[-1]['provider_calls']} "
                    f"{rows[-1]['elapsed_ms']:.0f} ms "
                    f"{','.join(rows[-1]['initial_causes']) or 'clean'}",
                    flush=True,
                )
    finally:
        await dispose_engine()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    artefact = RESULTS_DIR / f"c30b-assist-sweep-{run_id}.json"
    artefact.write_text(
        json.dumps(
            {"provenance": provenance, "summary": summarise(rows), "rows": rows},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {artefact}")
    print(json.dumps(summarise(rows), ensure_ascii=False, indent=2))
    return 0


def summarise(rows: list[dict]) -> dict:
    """Per arm, and always partitioned by cause. No aggregate travels alone."""
    out: dict[str, dict] = {}
    for arm in sorted({row["sections"] for row in rows}):
        subset = [row for row in rows if row["sections"] == arm]
        causes = {cause: 0 for cause in PITCH_VIOLATION_CAUSES}
        for row in subset:
            for cause in row["initial_causes"]:
                causes[cause] += 1
        correspondence = [
            item for row in subset for item in row["correspondence_failures"]
        ]
        dirty = [row for row in subset if row["initial_causes"]]
        out[f"{arm}-secciones"] = {
            "generations": len(subset),
            "citations_offered_mean": round(
                sum(len(row["citations_offered"]) for row in subset) / max(len(subset), 1), 2
            ),
            "first_pass_clean": len(subset) - len(dirty),
            "first_pass_rejected": len(dirty),
            "first_pass_rejection_rate": round(len(dirty) / max(len(subset), 1), 4),
            "violations_by_cause": {k: v for k, v in causes.items() if v},
            "repaired": sum(1 for row in subset if row["provider_calls"] > 1),
            "published": sum(1 for row in subset if row["published"]),
            "withheld": sum(1 for row in subset if not row["published"]),
            "final_withheld_rate": round(
                sum(1 for row in subset if not row["published"]) / max(len(subset), 1), 4
            ),
            "citations_withdrawn": sum(
                len(row["withdrawn_citation_ids"]) for row in subset
            ),
            "correspondence_failures": len(correspondence),
            "correspondence_failures_punctuation_only": sum(
                1 for item in correspondence if item["punctuation_only"]
            ),
            "prompt_tokens": sum(row["prompt_tokens"] for row in subset),
            "completion_tokens": sum(row["completion_tokens"] for row in subset),
            "provider_calls": sum(row["provider_calls"] for row in subset),
            "request_ms_mean": round(
                sum(row["elapsed_ms"] for row in subset) / max(len(subset), 1), 1
            ),
            "request_ms_max": max((row["elapsed_ms"] for row in subset), default=0.0),
            **_call_latency(subset),
            "pitch_sentences_mean": round(
                sum(row["pitch_sentences"] for row in subset if row["published"])
                / max(sum(1 for row in subset if row["published"]), 1),
                2,
            ),
            "provider_errors": sum(1 for row in subset if row["provider_error"]),
        }
    return out


def _call_latency(subset: list[dict]) -> dict:
    """The distribution the timeout actually applies to: one entry per provider call."""
    calls = sorted(item for row in subset for item in row["call_latencies_ms"])
    if not calls:
        return {"calls_measured": 0}
    return {
        "calls_measured": len(calls),
        "call_ms_p50": round(calls[len(calls) // 2], 1),
        "call_ms_p95": round(calls[max(int(0.95 * len(calls)) - 1, 0)], 1),
        "call_ms_max": round(calls[-1], 1),
        "calls_over_serving_timeout": sum(
            1 for item in calls if item > PITCH_TIMEOUT_SECONDS * 1000.0
        ),
        "calls_over_serving_timeout_rate": round(
            sum(1 for item in calls if item > PITCH_TIMEOUT_SECONDS * 1000.0) / len(calls), 4
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m jbg_ai.evals.assist_sweep",
        description="C30b context-width sweep of the generated sale argument",
    )
    parser.add_argument(
        "--sections",
        type=lambda value: [int(item) for item in value.split(",")],
        default=None,
        help="Arms to run, e.g. 1,2,3. Default: every arm the sample declares",
    )
    parser.add_argument("--limit", type=int, default=0, help="Pieces per stratum, for a probe")
    parser.add_argument(
        "--model",
        default=os.environ.get("JPV_ASSIST_LLM_MODEL") or DEFAULT_ASSIST_MODEL,
        help="Model under measurement; recorded in the artefact's provenance",
    )
    parser.add_argument("--dry-run", action="store_true", help="Provenance and size only")
    return parser


def main(argv: list[str] | None = None) -> int:
    # `psycopg` refuses the ProactorEventLoop, which is what Python installs by default on
    # Windows. Every loose script that opens the async engine needs this; in the tests
    # `support/async_db.run_db` already does it.
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        return asyncio.run(run(build_parser().parse_args(argv)))
    except EvaluationUnavailable as exc:
        print(f"unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
