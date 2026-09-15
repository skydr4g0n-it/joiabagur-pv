"""Run the routing evaluation against the real classifier. C31.

    uv run --system-certs python -m jbg_ai.evals.routing_run [--limit N] [--model M]

**Real provider calls, one per case, no retry.** 119 classifications at around thirty output
tokens each; the cost does not decide anything here and saying so in writing is cheaper than
leaving a reader to wonder. A case that fails to parse counts as a degradation in the matrix
rather than being re-rolled until it agrees — re-rolling would measure the best of N attempts
and publish it as the behaviour of one.

The credential follows the serving path's own chain — router, assist, enrichment — and the
resolved link is printed **by name and never by value**.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from jbg_ai.assist.constants import DEFAULT_ROUTER_MODEL
from jbg_ai.assist.router_llm import LiteLlmRouterClient
from jbg_ai.evals.routing import (
    VETO_CLASS,
    build_matrix,
    classify_all,
    load_routing_cases,
    provenance,
    render_markdown,
    report,
    resolved_credential,
    veto_violations,
    RESULTS_DIR,
    write_result,
)

#: Wider than the serving timeout on purpose: a sweep has nobody waiting at a counter, and a
#: cut taken from a serving budget would turn provider jitter into measured degradations.
SWEEP_TIMEOUT_SECONDS = 20.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("JPV_ROUTER_LLM_MODEL") or DEFAULT_ROUTER_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="first N cases of each class")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.3, help="pause after each call")
    parser.add_argument("--attempts", type=int, default=8, help="rate-limit retries only")
    parser.add_argument("--backoff", type=float, default=4.0)
    parser.add_argument("--timeout", type=float, default=SWEEP_TIMEOUT_SECONDS)
    parser.add_argument("--name", default="c31-routing-confusion")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cases = load_routing_cases()
    selected = list(cases)
    if args.limit:
        by_class: dict[str, list] = {}
        for case in cases:
            by_class.setdefault(case.expected, []).append(case)
        selected = [item for group in by_class.values() for item in group[: args.limit]]

    key, credential = resolved_credential()
    meta = provenance(model=args.model)
    print(json.dumps({**meta, "cases": len(selected), "credential": credential}, indent=2))
    if args.dry_run:
        print(f"dry run: {len(selected)} classifications, none executed")
        return 0
    if key is None:
        print(
            "no credential: set JPV_ROUTER_LLM_API_KEY, JPV_ASSIST_LLM_API_KEY or "
            "JPV_RAG_LLM_API_KEY",
            file=sys.stderr,
        )
        return 2

    # **Warm the provider library before the clock starts.** `assist/router_llm.py` imports
    # `litellm` INSIDE the call, deliberately — the package must stay importable and the suite
    # offline without the provider library being reached at import time — but that import lands
    # inside `asyncio.wait_for`, so the first call of a process pays several seconds of it
    # against its own timeout. Measured here: the first two cases of a run timed out at 20 s
    # for that reason alone and nothing else. A sweep that recorded those as degradations would
    # be publishing an import cost as a classifier failure.
    import litellm  # noqa: F401

    client = LiteLlmRouterClient(
        api_key=key,
        model=args.model,
        base_url=os.environ.get("JPV_RAG_LLM_BASE_URL") or None,
        timeout=args.timeout,
    )
    done = {"n": 0}

    def tick(case, predicted, cause):
        done["n"] += 1
        if done["n"] % 20 == 0 or done["n"] == len(selected):
            print(f"  {done['n']}/{len(selected)}", file=sys.stderr)

    results = asyncio.run(
        classify_all(
            selected,
            client=client,
            concurrency=args.concurrency,
            delay=args.delay,
            attempts=args.attempts,
            backoff=args.backoff,
            on_result=tick,
        )
    )
    matrix, per_category = build_matrix(results)
    violations = veto_violations([(case, predicted) for case, predicted, _ in results])
    payload = report(
        matrix,
        violations=violations,
        meta={**meta, "credential": credential, "timeout_seconds": args.timeout},
        per_category=per_category,
        results_for_coverage=[
            (case, predicted)
            for case, predicted, _ in results
            if case.expected == VETO_CLASS
        ],
    )
    payload["cases"] = [
        {
            "id": case.id,
            "expected": case.expected,
            "predicted": predicted,
            "degraded_cause": cause,
            "category": case.category,
            "text": case.text,
        }
        for case, predicted, cause in results
    ]
    path = write_result(payload, name=args.name)
    markdown = RESULTS_DIR / f"{args.name}-{payload['run_id']}.md"
    markdown.write_text(render_markdown(payload), encoding="utf-8")
    print(f"\nwrote {path}\nwrote {markdown}")
    print(render_markdown(payload))
    return 0 if payload["veto"]["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
