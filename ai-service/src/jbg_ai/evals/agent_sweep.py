"""The two-armed provider pass of the agent loop. C32b.

**A dated measurement, not a reproducible row.** It calls a language model, so it lives beside
`assist_sweep.py` and `cag_run.py` and not inside the runner that re-executes on every
evaluation — keeping the two apart is what stops an irreproducible figure from entering a table
of reproducible ones.

What it measures, and the reading that matters is always the **distribution**:

    carga          p50/p95 de tokens, de contexto y de reloj · curva de crecimiento por vuelta
                   coste por brazo de modelo · sobrecoste contra el pipeline determinista
    calibración    herramienta muerta · causa de argumento recurrente · NOMBRE INVENTADO
                   llamadas casi idénticas · tasa de pivote POR ETIQUETA de disponibilidad

An agent has a long tail — the request that loops to its limit is the one that ruins a mean —
so no aggregate is published here without its percentiles.

**It drives the real layer.** `run_agent` is the function the route calls; a harness that
re-implemented the loop would measure the re-implementation, which is the mistake this
repository already names in `evals/configs.py`. What it changes is the model of the arm and
nothing else: the budgets, the prompts and the registry are the serving ones.

**This is the declared exception to the no-persistence rule.** The serving path writes no
transcript, no argument and no tool argument anywhere, log included. The harness writes the
**rich** trace — arguments and observations — bound to a run identifier, a commit and the
prompt versions, because the granularity question cannot be answered without it: «two nearly
identical calls to one tool» is a statement about arguments. The transcripts are synthetic and
no operator wrote them, which is what makes that exception cheap here.

    uv run python -m jbg_ai.evals.agent_sweep --dry-run          # procedencia y tamaño
    uv run python -m jbg_ai.evals.agent_sweep --limit 3 --arms openai/gpt-4o   # humo
    uv run python -m jbg_ai.evals.agent_sweep                    # la pasada entera
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml

from jbg_ai.api.auth import ServicePrincipal
from jbg_ai.assist.agent import AgentBudgets, run_agent
from jbg_ai.assist.agent_llm import LiteLlmAgentClient
from jbg_ai.assist.constants import (
    AGENT_PITCH_PROMPT_VERSION,
    AGENT_PROMPT_VERSION,
    AVAILABILITY_LABEL_BY_BUCKET,
    AVAILABILITY_NO_SCOPE,
    DEFAULT_AGENT_MODEL,
    MAX_AGENT_PROVIDER_CALLS,
    PROMPT_VERSION,
    ROUTER_PROMPT_VERSION,
    TOOL_NAMES,
)
from jbg_ai.assist.llm import LiteLlmAssistClient
from jbg_ai.assist.router_llm import LiteLlmRouterClient
from jbg_ai.assist.tools import build_registry
from jbg_ai.assist.transcript import Turn
from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.db.engine import dispose_engine
from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.execute import harness_settings
from jbg_ai.evals.provenance import UNKNOWN_SHA
from jbg_ai.knowledge.search import SqlAlchemyKnowledgeIndex
from jbg_ai.retrieval.orchestrator import build_retrieval_embed_client
from jbg_ai.retrieval.search import SqlAlchemyProductSearch

AGENT_SETS = AI_SERVICE_ROOT / "evals" / "agent"
LOAD_SET = AGENT_SETS / "load-set.yaml"
CALIBRATION = AGENT_SETS / "calibration.yaml"
RESULTS_DIR = AI_SERVICE_ROOT / "evals" / "results"

#: The two arms, and the second is the whole reason the model is a variable of its own. The
#: cost arithmetic decomposes the agent's overhead against the deterministic pipeline into a
#: multiplier of TOKENS, which is structural, and a multiplier of MODEL, which is an
#: environment variable. Measuring both turns that second one into a measurement instead of a
#: preference — and it is cheap: the second arm is a fraction of the first.
DEFAULT_ARMS: tuple[str, ...] = (DEFAULT_AGENT_MODEL, "openai/gpt-4o-mini")

#: MAO-AIR, the point of sale with the most exposure to stockouts in the C10 world: 34,4 % of
#: its assortment at zero stock, 143 of 416. **Declared and not inferred**, and it is the same
#: identifier `evals/configs/v3-senales.yaml` declares for the same reason — a test asserts the
#: two agree rather than letting them drift.
MAO_AIR = UUID("43da2f6a-cb64-4067-b5c2-cd67f5a8f6b3")

#: The marker a calibration scenario carries where the harness must put a real reference. A
#: scenario that said «esta pieza» would give the model nothing to anchor the availability tool
#: on, and its pivot rate would be computed over whatever the search happened to return.
PIECE_MARKER = "{pieza}"

#: The key under which `resolve_pieces` returns a SKU whose family has several members.
#: It is **not** an availability label and is kept out of that vocabulary on purpose.
FAMILY_WITH_VARIANTS = "family:con_variantes"

#: Per million tokens, in USD. Published prices of 2026-09, recorded **in the artefact** so a
#: figure can be recomputed later against what it was actually priced at rather than against
#: whatever the price is when somebody reads the report.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
}


def _git_sha() -> str:
    import subprocess

    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, cwd=AI_SERVICE_ROOT,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True, cwd=AI_SERVICE_ROOT,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — a run outside a checkout still records something
        return UNKNOWN_SHA
    # A run taken on a dirty tree was NOT produced by the commit it names. C25 was bitten by
    # exactly this and `provenance.py` records the rule; it is reused rather than restated.
    return f"{sha}+dirty" if dirty else sha


#: The three chains, exactly as `api/routers/assist.py` resolves them. **Three and not one,
#: and the first pass proved why it matters.** That run resolved a single credential and handed
#: it to all three clients, which did two things at once: it measured a configuration the route
#: never serves, and it pointed every call of every stage at one key — so the key's rate limit
#: was reached on request six and the classifier degraded on all sixty-four that followed.
#:
#: The classifier's key is deliberately absent from the agent's chain and vice versa: a request
#: of this route resolves two clients, and letting one fall back to the other would make the
#: cost of the two stages impossible to tell apart.
CREDENTIAL_CHAINS: dict[str, tuple[tuple[str, str], ...]] = {
    "agent": (
        ("JPV_AGENT_LLM_API_KEY", "agent"),
        ("JPV_ASSIST_LLM_API_KEY", "assist_fallback"),
        ("JPV_RAG_LLM_API_KEY", "rag_fallback"),
    ),
    "router": (
        ("JPV_ROUTER_LLM_API_KEY", "router"),
        ("JPV_ASSIST_LLM_API_KEY", "assist_fallback"),
        ("JPV_RAG_LLM_API_KEY", "rag_fallback"),
    ),
    "pitch": (
        ("JPV_ASSIST_LLM_API_KEY", "assist"),
        ("JPV_RAG_LLM_API_KEY", "rag_fallback"),
    ),
}


def _credential(stage: str = "agent") -> tuple[str | None, str]:
    """The chain of ONE stage, so the pass measures what would actually serve."""
    for variable, link in CREDENTIAL_CHAINS[stage]:
        value = os.environ.get(variable)
        if value:
            return value, link
    return None, "absent"


def _credentials() -> dict[str, tuple[str | None, str]]:
    return {stage: _credential(stage) for stage in CREDENTIAL_CHAINS}


class TokenPacer:
    """Keeps the run under a **tokens-per-minute** ceiling, measured rather than assumed.

    **The first pass failed because the limit is not what it looked like.** It broke on request
    six, twice, with three different keys and a delay between requests — so it was neither a
    per-key limit nor a per-request one. The arithmetic says what it was: 55.649 tokens in 33
    seconds, a rate of ~100.000 tokens per minute against an organisation ceiling well below
    that. Splitting the credentials across stages did nothing because the quota is the
    organisation's, not the key's.

    A fixed delay is the wrong instrument for a token ceiling: requests here range from ~1.800
    to ~16.000 tokens, so a pause long enough for the biggest wastes most of the run and one
    tuned to the average still bursts through the limit. This sleeps only as long as the
    *tokens already spent in the last minute* require, which self-tunes to whatever the real
    ceiling turns out to be.

    It paces **between** requests and never inside one: a pause in the middle would land in the
    wall-clock budget this pass exists to measure.
    """

    def __init__(self, tokens_per_minute: int) -> None:
        self.limit = tokens_per_minute
        self._spent: list[tuple[float, int]] = []

    def record(self, tokens: int) -> None:
        self._spent.append((time.monotonic(), tokens))

    def _in_window(self, now: float) -> int:
        self._spent = [item for item in self._spent if now - item[0] < 60.0]
        return sum(tokens for _when, tokens in self._spent)

    async def wait_for(self, estimated: int) -> float:
        """Sleep until `estimated` more tokens fit under the ceiling. Returns seconds slept."""
        if self.limit <= 0:
            return 0.0
        slept = 0.0
        while True:
            now = time.monotonic()
            used = self._in_window(now)
            if used + estimated <= self.limit or not self._spent:
                return slept
            # Wait until the oldest entry leaves the window; it is the smallest sleep that can
            # change the answer, so this never over-waits.
            oldest = self._spent[0][0]
            pause = max(60.0 - (now - oldest), 0.1)
            await asyncio.sleep(pause)
            slept += pause


def load_sets() -> tuple[dict, dict]:
    return (
        yaml.safe_load(LOAD_SET.read_text(encoding="utf-8")),
        yaml.safe_load(CALIBRATION.read_text(encoding="utf-8")),
    )


# --- resolving the fixtures against the projection ------------------------------------------


async def resolve_pieces(search: SqlAlchemyProductSearch) -> dict[str, str]:
    """One real SKU per availability label, read from MAO-AIR's projection **at run time**.

    A SKU written into the set would calibrate against a label that the next sync makes
    something else, and the scenario would stop measuring what it claims with nothing failing.
    The chosen references are recorded in the artefact's provenance, so the run is auditable
    without the set having to lie about being stable.

    `sin_ambito` is the one that cannot come from a bucket: it means **no row was read**, so it
    is resolved as a piece the index holds and this point of sale does not carry — which is the
    distinction C32a made a fourth value precisely so it would not be confused with zero.
    """
    buckets = await search.scope_buckets(MAO_AIR)
    chosen: dict[str, str] = {}

    for product_id, bucket in sorted(buckets.items()):
        label = AVAILABILITY_LABEL_BY_BUCKET.get(bucket)
        if label is None or label in chosen:
            continue
        document = await search.source_document(UUID(product_id))
        if document is not None and document.is_active:
            chosen[label] = document.sku

    # A piece the point of sale does not carry: the honest source of «no scope».
    if AVAILABILITY_NO_SCOPE not in chosen:
        unscoped = await _first_unscoped(search, set(buckets))
        if unscoped is not None:
            chosen[AVAILABILITY_NO_SCOPE] = unscoped

    # Not an availability label: the reference a chaining scenario needs.
    variants = await _piece_with_variants(search)
    if variants is not None:
        chosen[FAMILY_WITH_VARIANTS] = variants
    return chosen


async def _piece_with_variants(search: SqlAlchemyProductSearch) -> str | None:
    """A SKU whose family holds more than one active member.

    Needed because a scenario about «are there other sizes of that one?» has to name a piece
    that actually has other sizes — the first version of C05 asked the model to chain onto a
    reference the conversation never contained, which made it unsatisfiable rather than hard.
    """
    from sqlalchemy import text

    from jbg_ai.db.engine import session_scope

    async with session_scope(search._settings) as session:  # noqa: SLF001 — harness only
        rows = await session.execute(
            text(
                "SELECT sku FROM ("
                "  SELECT sku, count(*) OVER (PARTITION BY family_id) AS members"
                "  FROM ai.product_document"
                "  WHERE is_active AND family_id IS NOT NULL) q"
                " WHERE members >= 2 ORDER BY sku LIMIT 1"
            )
        )
        row = rows.first()
    return str(row[0]) if row else None


async def _first_unscoped(
    search: SqlAlchemyProductSearch, carried: set[str]
) -> str | None:
    """A SKU the index holds and this point of sale does not carry."""
    from sqlalchemy import text

    from jbg_ai.db.engine import session_scope

    async with session_scope(search._settings) as session:  # noqa: SLF001 — harness only
        rows = await session.execute(
            text(
                "SELECT sku FROM ai.product_document "
                "WHERE is_active AND product_id::text <> ALL(:carried) "
                "ORDER BY sku LIMIT 1"
            ),
            {"carried": list(carried) or [""]},
        )
        row = rows.first()
    return str(row[0]) if row else None


def scenario_turns(item: dict, pieces: dict[str, str]) -> list[Turn] | None:
    """The turns of one scenario with its marker resolved, or `None` when it cannot be run.

    Returning `None` rather than raising: a projection that happens to carry no piece at one
    label costs that scenario and not the pass, and the artefact records which were skipped.
    """
    fixture = item.get("fixture") or {}
    key = (
        fixture["availability"]
        if "availability" in fixture
        else FAMILY_WITH_VARIANTS
        if fixture.get("family") == "con_variantes"
        else None
    )
    replacement = pieces.get(key) if key else None
    if fixture and replacement is None:
        return None
    turns: list[Turn] = []
    for turn in item["turns"]:
        text = turn["text"]
        if replacement is not None:
            text = text.replace(PIECE_MARKER, replacement)
        turns.append(Turn(role=turn["role"], text=text))
    return turns


# --- one request ------------------------------------------------------------------------------


def _row(*, item: dict, set_id: str, arm: str, run, elapsed_ms: float) -> dict[str, Any]:
    """Everything one request produced, flattened for analysis. Distribution first."""
    per_iteration = [
        {
            "iteration": trace.iteration,
            "prompt_tokens": trace.prompt_tokens,
            "completion_tokens": trace.completion_tokens,
            # The two halves of the context pair: what the pre-flight budget counted, and what
            # the provider actually charged for the same turn.
            "context_chars": trace.context_chars,
            "elapsed_ms": round(trace.elapsed_ms, 1),
            "discarded_chars": trace.discarded_chars,
            "provider_error": trace.provider_error,
            "tools": [
                {
                    "tool": call.tool,
                    "ok": call.ok,
                    "cause": call.cause,
                    # The rich trace: the declared exception, and what the granularity
                    # question needs. «Two nearly identical calls» is about arguments.
                    "arguments": dict(call.arguments) if call.arguments else None,
                }
                for call in trace.tools
            ],
        }
        for trace in run.trace
    ]
    invoked = [call["tool"] for turn in per_iteration for call in turn["tools"]]
    return {
        "id": item["id"],
        "set": set_id,
        "arm": arm,
        "operator_turns": item.get(
            "operator_turns",
            sum(1 for turn in item["turns"] if turn["role"] == "operario"),
        ),
        "measures": item.get("measures"),
        "expects": item.get("expects"),
        "expects_any": item.get("expects_any"),
        "forbids": item.get("forbids"),
        "fixture": item.get("fixture"),
        "stop_reason": run.stop_reason,
        "partial": run.partial,
        "iterations": run.iterations,
        "tool_calls_used": run.tool_calls_used,
        "tools_invoked": invoked,
        # A name the model reached for that is not one of the six. **The most informative
        # datum this run can produce**, because the name states which tool is missing.
        "invented_tools": sorted({name for name in invoked if name not in TOOL_NAMES}),
        "abstained": run.abstained,
        "clarified": run.clarification_question is not None,
        "warnings": list(run.warnings),
        "groups": len(run.groups),
        "citations": len(run.citations),
        "pitch_chars": len(run.pitch),
        # **Why there is no argument, when there is none.** Without this a row reading
        # `pitch_chars: 0` is unanalysable and the only way to find out costs another run —
        # which is the whole point of recording it before the expensive one. The causes are
        # the generation layer's own closed vocabulary, so they partition.
        "pitch_withheld": run.pitch_outcome is not None and run.pitch_outcome.withheld,
        "pitch_ran": run.pitch_outcome is not None,
        "pitch_violations": (
            list(run.pitch_outcome.causes()) if run.pitch_outcome else []
        ),
        "pitch_initial_violations": (
            [item.cause for item in run.pitch_outcome.initial_violations]
            if run.pitch_outcome
            else []
        ),
        "pitch_withdrawn_citations": (
            list(run.pitch_outcome.withdrawn_citation_ids) if run.pitch_outcome else []
        ),
        "pitch_provider_error": (
            run.pitch_outcome.provider_error if run.pitch_outcome else None
        ),
        "pitch_calls": run.pitch_outcome.usage.calls if run.pitch_outcome else 0,
        "prompt_tokens": run.usage.prompt_tokens,
        "completion_tokens": run.usage.completion_tokens,
        "total_tokens": run.usage.total_tokens,
        "provider_calls": run.usage.calls,
        "embedding_calls": run.embedding_calls,
        "elapsed_ms": round(elapsed_ms, 1),
        "per_iteration": per_iteration,
    }


def _cost(row: dict, arm: str) -> float:
    prompt_price, completion_price = PRICES.get(arm, (0.0, 0.0))
    return (
        row["prompt_tokens"] * prompt_price + row["completion_tokens"] * completion_price
    ) / 1_000_000


# --- the summary, always partitioned ---------------------------------------------------------


def _percentiles(values: list[float]) -> dict[str, float]:
    """p50 and p95, and never a mean on its own.

    An agent's cost distribution has a long tail: the request that loops to its limit is the
    one a mean hides. The mean is reported too, but beside the percentiles and never instead.
    """
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "p50": round(statistics.median(ordered), 1),
        "p95": round(ordered[max(int(0.95 * len(ordered)) - 1, 0)], 1),
        "max": round(ordered[-1], 1),
        "mean": round(statistics.fmean(ordered), 1),
    }


def summarise(rows: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in sorted({row["arm"] for row in rows}):
        for set_id in sorted({row["set"] for row in rows if row["arm"] == arm}):
            subset = [
                row for row in rows if row["arm"] == arm and row["set"] == set_id
            ]
            out[f"{arm}::{set_id}"] = _summarise_subset(subset, arm)
    return out


def _summarise_subset(subset: list[dict], arm: str) -> dict[str, Any]:
    stops: dict[str, int] = {}
    for row in subset:
        stops[row["stop_reason"]] = stops.get(row["stop_reason"], 0) + 1

    tool_counts: dict[str, int] = {name: 0 for name in TOOL_NAMES}
    causes: dict[str, int] = {}
    for row in subset:
        for turn in row["per_iteration"]:
            for call in turn["tools"]:
                tool_counts[call["tool"]] = tool_counts.get(call["tool"], 0) + 1
                if call["cause"]:
                    causes[call["cause"]] = causes.get(call["cause"], 0) + 1

    costs = [_cost(row, arm) for row in subset]
    return {
        "requests": len(subset),
        "partial": sum(1 for row in subset if row["partial"]),
        "stop_reasons": stops,
        "tokens_prompt": _percentiles([row["prompt_tokens"] for row in subset]),
        "tokens_total": _percentiles([row["total_tokens"] for row in subset]),
        "context_chars": _percentiles(
            [
                max((turn["context_chars"] for turn in row["per_iteration"]), default=0)
                for row in subset
            ]
        ),
        "wall_ms": _percentiles([row["elapsed_ms"] for row in subset]),
        "iterations": _percentiles([float(row["iterations"]) for row in subset]),
        "provider_calls": _percentiles([float(row["provider_calls"]) for row in subset]),
        "provider_calls_over_ceiling": sum(
            1 for row in subset if row["provider_calls"] > MAX_AGENT_PROVIDER_CALLS
        ),
        # The curve, which is what says whether the accumulated context has to be compacted.
        "growth_by_turn": _growth(subset),
        "tool_usage": tool_counts,
        "tools_never_chosen": sorted(
            name for name, count in tool_counts.items() if count == 0
        ),
        "invented_tool_names": sorted(
            {name for row in subset for name in row["invented_tools"]}
        ),
        "failure_causes": causes,
        # The generation layer's verdict, partitioned. An argument withheld is a request that
        # cost everything and served no prose, so the rate and its causes belong beside the
        # cost rather than in a footnote.
        "pitch_ran": sum(1 for row in subset if row["pitch_ran"]),
        "pitch_withheld": sum(1 for row in subset if row["pitch_withheld"]),
        "pitch_violation_causes": _tally(
            cause for row in subset for cause in row["pitch_initial_violations"]
        ),
        "cost_usd_total": round(sum(costs), 4),
        "cost_usd_per_request": round(sum(costs) / max(len(costs), 1), 6),
    }


def _tally(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


def _growth(subset: list[dict]) -> dict[str, dict[str, float]]:
    """Accumulated prompt tokens and context characters **per turn index**.

    The figure that decides whether compaction is needed, and the one D-14 refused to act on
    before measuring: first the curve, then the decision.
    """
    by_turn: dict[int, list[tuple[int, int]]] = {}
    for row in subset:
        for turn in row["per_iteration"]:
            by_turn.setdefault(turn["iteration"], []).append(
                (turn["prompt_tokens"], turn["context_chars"])
            )
    return {
        str(index): {
            "requests": len(items),
            "prompt_tokens_p50": round(statistics.median([a for a, _ in items]), 1),
            "context_chars_p50": round(statistics.median([b for _, b in items]), 1),
        }
        for index, items in sorted(by_turn.items())
    }


def pivot_rates(rows: list[dict]) -> dict[str, Any]:
    """The substitute-pivot rate **per availability label**, over- and under- kept apart.

    The expensive failure is pivoting away from a piece the shop can sell, and an aggregate
    rate cannot tell it from the cheap one.
    """
    out: dict[str, Any] = {}
    for row in rows:
        fixture = row.get("fixture")
        if not fixture:
            continue
        label = fixture["availability"]
        bucket = out.setdefault(
            label, {"scenarios": 0, "pivoted": 0, "should_pivot": None}
        )
        bucket["scenarios"] += 1
        bucket["pivoted"] += int("buscar_sustitutos" in row["tools_invoked"])
        bucket["should_pivot"] = "buscar_sustitutos" in (row["expects"] or [])
    for label, bucket in out.items():
        rate = bucket["pivoted"] / max(bucket["scenarios"], 1)
        bucket["pivot_rate"] = round(rate, 4)
        bucket["failure"] = (
            "infra-pivote" if bucket["should_pivot"] and rate < 1.0
            else "sobre-pivote" if not bucket["should_pivot"] and rate > 0.0
            else "ninguno"
        )
    return out


# --- the run ------------------------------------------------------------------------------------


async def run(args: argparse.Namespace) -> int:
    load_set, calibration = load_sets()
    # The dry run must work with nothing configured: its whole job is to print what the
    # pass WOULD do before anybody pays for it, and demanding a database to do that would
    # make the cheap check the expensive one.
    settings = harness_settings(requires_database=not args.dry_run)
    credentials = _credentials()

    chosen_sets: list[tuple[str, dict, str]] = []
    if args.sets in ("both", "load"):
        chosen_sets.append(("load", load_set, "transcripts"))
    if args.sets in ("both", "calibration"):
        chosen_sets.append(("calibration", calibration, "scenarios"))

    arms = list(args.arms or DEFAULT_ARMS)
    run_id = uuid4().hex[:12]
    provenance: dict[str, Any] = {
        "run_id": run_id,
        "git_sha": _git_sha(),
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "agent_prompt_version": AGENT_PROMPT_VERSION,
        "pitch_prompt_version": AGENT_PITCH_PROMPT_VERSION,
        "router_prompt_version": ROUTER_PROMPT_VERSION,
        "deterministic_route_prompt_version": PROMPT_VERSION,
        "arms": arms,
        "credential_links": {stage: link for stage, (_key, link) in credentials.items()},
        "delay_seconds": args.delay,
        "tokens_per_minute_ceiling": args.tpm,
        "sets": {
            name: {"id": document["id"], "size": len(document[key_name])}
            for name, document, key_name in chosen_sets
        },
        "point_of_sale": str(MAO_AIR),
        "budgets": AgentBudgets().__dict__,
        "provider_call_ceiling": MAX_AGENT_PROVIDER_CALLS,
        "prices_usd_per_million": PRICES,
        "limit": args.limit or None,
    }

    planned = sum(
        min(len(document[key_name]), args.limit or len(document[key_name]))
        for _name, document, key_name in chosen_sets
    ) * len(arms)
    provenance["planned_requests"] = planned

    print(json.dumps(provenance, indent=2, ensure_ascii=False, default=str))
    if args.dry_run:
        print(
            f"\ndry run: {len(arms)} arms x "
            f"{planned // max(len(arms), 1)} transcripts = {planned} requests, "
            "none executed, nothing written"
        )
        return 0

    if not settings.database_url:
        raise EvaluationUnavailable("DATABASE_URL is required for the agent sweep")
    unresolved = [stage for stage, (value, _link) in credentials.items() if value is None]
    if unresolved:
        raise EvaluationUnavailable(
            "no credential resolves for: "
            + ", ".join(unresolved)
            + ". Each stage has its own chain: "
            + "; ".join(
                stage + " -> " + " then ".join(name for name, _ in chain)
                for stage, chain in CREDENTIAL_CHAINS.items()
            )
        )

    embed = build_retrieval_embed_client(settings)
    search = SqlAlchemyProductSearch(settings)
    knowledge = SqlAlchemyKnowledgeIndex(settings)
    rows: list[dict] = []
    skipped: list[str] = []
    pacer = TokenPacer(args.tpm)
    # The running mean, so the first requests are paced on the estimate and the later ones
    # on what this run actually costs.
    estimate = 12_000
    paced_seconds = 0.0

    try:
        pieces = await resolve_pieces(search)
        provenance["resolved_pieces"] = pieces
        provenance["index_compatible_documents"] = await search.count_compatible(
            model_version_key=embed.model_version_key, model_id=embed.model_id
        )
        provenance["assortment_size"] = await search.count_scope(MAO_AIR)
        print(json.dumps(
            {"resolved_pieces": pieces,
             "index": provenance["index_compatible_documents"],
             "assortment": provenance["assortment_size"]},
            indent=2, ensure_ascii=False,
        ))

        for arm in arms:
            for set_name, document, key_name in chosen_sets:
                items = document[key_name]
                if args.limit:
                    items = items[: args.limit]
                for item in items:
                    turns = scenario_turns(item, pieces)
                    if turns is None:
                        skipped.append(f"{set_name}:{item['id']}")
                        print(f"  skipped {item['id']}: no piece for its fixture")
                        continue
                    principal = ServicePrincipal(
                        user_id="agent-sweep",
                        role="Operator",
                        trace_id=f"sweep-{run_id}-{item['id']}",
                        pos_id=str(MAO_AIR),
                    )
                    paced_seconds += await pacer.wait_for(estimate)
                    started = time.perf_counter()
                    result = await run_agent(
                        turns,
                        principal,
                        registry=build_registry(
                            principal=principal,
                            settings=settings,
                            embed=embed,
                            search=search,
                            knowledge=knowledge,
                        ),
                        agent_client=LiteLlmAgentClient(
                            api_key=credentials["agent"][0],
                            model=arm,
                            base_url=settings.jpv_rag_llm_base_url,
                            timeout=settings.jpv_agent_timeout_seconds,
                        ),
                        router_client=LiteLlmRouterClient(
                            api_key=credentials["router"][0],
                            model=settings.jpv_router_llm_model,
                            base_url=settings.jpv_rag_llm_base_url,
                            timeout=settings.jpv_router_timeout_seconds,
                        ),
                        pitch_client=LiteLlmAssistClient(
                            api_key=credentials["pitch"][0],
                            model=settings.jpv_assist_llm_model,
                            base_url=settings.jpv_rag_llm_base_url,
                            timeout=settings.jpv_assist_pitch_timeout_seconds,
                        ),
                    )
                    elapsed = (time.perf_counter() - started) * 1000.0
                    row = _row(
                        item=item, set_id=set_name, arm=arm, run=result, elapsed_ms=elapsed
                    )
                    rows.append(row)
                    pacer.record(row["total_tokens"])
                    estimate = max(
                        1_000,
                        int(sum(item["total_tokens"] for item in rows) / len(rows)),
                    )
                    if args.delay:
                        # Between requests and never inside one: pausing mid-request
                        # would land in the wall-clock budget being measured.
                        await asyncio.sleep(args.delay)
                    print(
                        f"  {arm:<20} {set_name:<12} {item['id']:>5} "
                        f"{row['stop_reason']:<24} it={row['iterations']} "
                        f"tools={row['tool_calls_used']} "
                        f"tok={row['total_tokens']:>6} {row['elapsed_ms']:>7.0f} ms",
                        flush=True,
                    )
    finally:
        await dispose_engine()

    provenance["skipped"] = skipped
    provenance["paced_seconds"] = round(paced_seconds, 1)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    artefact = RESULTS_DIR / f"c32b-agent-sweep-{run_id}.json"
    artefact.write_text(
        json.dumps(
            {
                "provenance": provenance,
                "summary": summarise(rows),
                "pivot_rates": pivot_rates(rows),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {artefact}")
    print(json.dumps(summarise(rows), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m jbg_ai.evals.agent_sweep",
        description="C32b two-armed provider pass of the sale assistant's agent loop",
    )
    parser.add_argument(
        "--arms",
        nargs="*",
        default=None,
        help=f"Models under measurement. Default: {' '.join(DEFAULT_ARMS)}",
    )
    parser.add_argument(
        "--sets",
        choices=("both", "load", "calibration"),
        default="both",
        help="Which instrument to run. Default: both",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="First N of each set, for a smoke test"
    )
    parser.add_argument(
        "--tpm",
        type=int,
        default=25_000,
        help=(
            "Tokens-per-minute ceiling to stay under. The organisation's quota, not the "
            "key's: the first pass measured ~100k/min against a lower ceiling and every "
            "request after the sixth came back empty. 0 disables the pacing"
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help=(
            "Seconds to wait between requests. A request makes up to eight provider "
            "calls, so a key on a low rate tier is exhausted in a handful of them: the "
            "first pass of C32b hit its limit on request six and every one after it came "
            "back empty. Pacing turns a wasted run into a slow one"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Provenance and size only: nothing executed and nothing written",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # The shared local env file, exactly as `evals/cli.py` loads it, and **existing process
    # environment wins** so an explicit export still overrides. It is here so a credential
    # never has to be typed on a command line, where it would land in shell history.
    from jbg_ai.data.envload import load_local_env

    load_local_env()

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
