"""The judgement pool: what gets labelled, how deep, and how labels are appended. C24.

The pool is the union, without repetition, of what each indexed configuration returns. What
falls outside it is assumed irrelevant — the standard assumption, and declared in the report
rather than left implicit, because it is the assumption that quietly punishes any FUTURE
configuration that promotes a document nobody judged.

**Depth is adaptive, and the arithmetic is why.** At 48 queries and about 4.6 seconds a
judgement, a fixed depth of 10 per configuration is roughly an hour and buys an optimistic
recall denominator; a fixed depth of 60 is over seven hours, most of it spent recording
obvious zeros — for "a piece shaped like a sea shell" the catalogue holds about four shells,
so positions 20 to 60 are forty guaranteed noughts — and seven hours in one sitting is exactly
the failure mode a single annotator has no second annotator to catch.

So: base 20, which is the `top_k × 3` window the .NET side actually receives; continue in
blocks of ten while the previous block contributed at least one relevant document; stop at 60,
the branch depth beyond which the live pipeline cannot surface anything at all, so judging
deeper informs nothing. The depth reached is recorded per query.

**Judgements are keyed by `(query_id, product_id)` and appended, never rewritten.** That is
what lets a later change deepen the pool without re-labelling, and it is why the reported
`unjudged@5` matters: a configuration whose top five is largely unjudged is *visibly* not
comparable instead of silently penalised.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from jbg_ai.evals.golden import GOLDEN_DIR, JUDGEMENTS_FILE, Judgement

#: The window the .NET API receives (`top_k × 3`, capped). Every configuration contributes at
#: least this much, so the base of the pool is the same for all of them.
BASE_DEPTH = 20

#: One block of deepening. Small enough that a block which contributes nothing has cost little.
BLOCK = 10

#: `JPV_BRANCH_DEPTH`. Beyond it no branch produces a candidate, so a judgement there could
#: never change any configuration's score, now or later.
MAX_DEPTH = 60


@dataclass(frozen=True)
class PooledDocument:
    """One document in the pool, and which configurations put it there."""

    product_id: UUID
    sku: str
    pooled_in: tuple[str, ...]
    best_rank: int


def pool_at_depth(
    lists: Mapping[str, Sequence[tuple[UUID, str]]], depth: int
) -> tuple[PooledDocument, ...]:
    """Union of the first `depth` of each list, ordered by best rank then by identifier.

    Deterministic on purpose, and by the same key the live path now truncates with: the pool a
    run produces has to be a function of the query and the index, or the set of things judged
    would itself depend on the day it was built.
    """
    best: dict[UUID, tuple[int, str, list[str]]] = {}
    for config_id in sorted(lists):
        for rank, (product_id, sku) in enumerate(lists[config_id][:depth], start=1):
            current = best.get(product_id)
            if current is None:
                best[product_id] = (rank, sku, [config_id])
            else:
                best[product_id] = (min(current[0], rank), current[1], [*current[2], config_id])
    return tuple(
        PooledDocument(
            product_id=product_id,
            sku=sku,
            pooled_in=tuple(sorted(set(configs))),
            best_rank=rank,
        )
        for product_id, (rank, sku, configs) in sorted(
            best.items(), key=lambda item: (item[1][0], str(item[0]))
        )
    )


def depth_schedule() -> tuple[int, ...]:
    """The depths the adaptive rule may reach, in order."""
    depths = [BASE_DEPTH]
    while depths[-1] + BLOCK <= MAX_DEPTH:
        depths.append(depths[-1] + BLOCK)
    return tuple(depths)


def adaptive_depth(
    lists: Mapping[str, Sequence[tuple[UUID, str]]],
    is_relevant: Callable[[UUID], bool | None],
) -> tuple[int, tuple[PooledDocument, ...]]:
    """Deepen while the last block still finds something, and report how far it went.

    `is_relevant` returns None for a document nobody has judged yet, which stops the deepening:
    a block whose verdicts are not all in cannot say whether it contributed, and guessing that
    it did would deepen for ever on an unlabelled pool.
    """
    reached = BASE_DEPTH
    pool = pool_at_depth(lists, reached)
    # The base pool is the first "previous block". From then on the test is on what the LAST
    # extension added, not on the pool as a whole: a query with a rich first twenty would
    # otherwise deepen to the cap however barren every extension turned out to be, which is the
    # fixed-depth-60 cost the adaptive rule exists to avoid.
    previous_block = pool
    for depth in depth_schedule()[1:]:
        verdicts = [is_relevant(item.product_id) for item in previous_block]
        if any(verdict is None for verdict in verdicts) or not any(verdicts):
            break
        wider = pool_at_depth(lists, depth)
        seen = {item.product_id for item in pool}
        added = tuple(item for item in wider if item.product_id not in seen)
        if not added:
            # Every list is already exhausted, so a further block cannot add anything either.
            break
        reached, pool, previous_block = depth, wider, added
    return reached, pool


def judgements_path(root: Path | None = None) -> Path:
    return (root or GOLDEN_DIR) / JUDGEMENTS_FILE


def append_judgements(items: Iterable[Judgement], root: Path | None = None) -> Path:
    """Append, sorted, and never rewrite an existing pair.

    Appending is the whole contract of the file: a later change deepens the pool and adds
    verdicts for documents nobody had seen, and the labels already recorded must come through
    that untouched — otherwise every deepening silently re-opens every earlier decision.
    """
    path = judgements_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_keys(path)
    fresh = [item for item in items if (item.query_id, item.product_id) not in existing]
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for item in sorted(fresh, key=lambda value: (value.query_id, value.product_id)):
            handle.write(json.dumps(_as_json(item), ensure_ascii=False) + "\n")
    return path


def _existing_keys(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    keys: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            keys.add((str(payload["query_id"]), str(payload["product_id"])))
    return keys


def _as_json(item: Judgement) -> dict[str, object]:
    payload: dict[str, object] = {
        "query_id": item.query_id,
        "product_id": item.product_id,
        "grade": item.grade,
        "pooled_in": list(item.pooled_in),
        "judged_at": item.judged_at,
        "source_hash": item.source_hash,
        "data_origin": item.data_origin,
        "lexically_reachable": item.lexically_reachable,
    }
    if item.sku:
        payload["sku"] = item.sku
    if item.note:
        payload["note"] = item.note
    return payload


def now_stamp() -> str:
    return datetime.now(tz=UTC).date().isoformat()
