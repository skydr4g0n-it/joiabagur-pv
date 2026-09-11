"""The context-only baseline: the whole catalogue in the prompt, no retrieval. C24.

**This is not a quality row. It is the measured proof of why retrieval exists.** Context
augmentation has zero lines anywhere else in this system — it appears in the design and in the
project checklist and nowhere in the code — and the project has to describe the progression
from a context-only prototype to a retrieval system. Without this row that section would
explain what the technique is in general rather than what it costs here.

It produces three things and nothing else:

1. the token size and the cost per query of the compacted catalogue;
2. recall over the twelve unanchored queries, which is where having the whole catalogue in
   front of it is as favourable to this configuration as this corpus gets;
3. the scale curve — the same catalogue at 2.500 and 5.000 products, up to where it stops
   fitting.

**No price enters the context.** `RetrievalResult` does not emit a price and the boundary rule
is that .NET owns it; a price crossing into a prompt from here would open, ahead of time,
exactly the surface a later change's anti-hallucination validator exists to close. If a query
needs a price to be answered, this configuration fails it, and that is a result.

**It calls a language model, so it is not reproducible bit for bit even at temperature zero.**
It is one dated measurement with its model recorded, not a row that re-runs on every
evaluation, and the report says so where the number appears.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import UUID

#: One line per product: code, name, type, materials. No price, no description, no collection.
#: Four fields because they are what a shop assistant would read off a shelf label, and because
#: the whole catalogue has to fit — the description alone would multiply the context by twenty.
LINE = "{sku} · {name} · {piece_type} · {materials}"

#: Catalogue sizes the scale curve is projected at. The corpus is 1.168 documents today; these
#: are what the same shop looks like after a few years of new collections.
SCALE_POINTS = (1168, 2500, 5000)

_ANSWER = re.compile(r"\b(SKU[0-9]+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogueLine:
    product_id: UUID
    sku: str
    text: str


@dataclass(frozen=True)
class CompactCatalogue:
    """The context that was actually sent, and what was left out of it."""

    lines: tuple[CatalogueLine, ...]
    documents_total: int
    documents_omitted: int
    tokens: int

    @property
    def text(self) -> str:
        return "\n".join(item.text for item in self.lines)


def compact_line(row: dict) -> str:
    return LINE.format(
        sku=row["sku"],
        name=row["name"],
        piece_type=row.get("piece_type") or "-",
        materials=", ".join(sorted(row.get("materials") or [])) or "-",
    )


def build_context(
    rows: list[dict], *, budget_tokens: int, count_tokens
) -> CompactCatalogue:
    """Compact the catalogue, truncating deterministically when it does not fit.

    Truncation is by `product_id`, ascending, and it is the whole point of the requirement.
    The test that guards this does NOT assert that the catalogue fits — that assertion stops
    being true the day the shop grows, and a test that silently starts passing for the wrong
    reason is worse than none. It asserts that a catalogue LARGER than the budget is cut the
    same way on every run and that the number of documents left out is recorded, so the recall
    figure is read knowing which part of the catalogue was never seen.
    """
    ordered = sorted(rows, key=lambda row: str(row["product_id"]))
    kept: list[CatalogueLine] = []
    tokens = 0
    for row in ordered:
        text = compact_line(row)
        cost = count_tokens(text)
        if tokens + cost > budget_tokens:
            break
        kept.append(
            CatalogueLine(
                product_id=UUID(str(row["product_id"])), sku=str(row["sku"]), text=text
            )
        )
        tokens += cost
    return CompactCatalogue(
        lines=tuple(kept),
        documents_total=len(ordered),
        documents_omitted=len(ordered) - len(kept),
        tokens=tokens,
    )


def breaking_point(catalogue: CompactCatalogue, *, budget_tokens: int) -> int:
    """The smallest catalogue size whose context no longer fits the budget.

    The curve below is three SAMPLED points, and today all three fit: the wall is real and the
    table cannot show it. Publishing the number is what keeps "up to the point where it no
    longer fits" from being a division the reader is expected to do — and it is the one figure
    that does not move when somebody widens `SCALE_POINTS`.

    Same rounding rule as the curve, so the two can never disagree about whether a sampled size
    fits: the search starts at the analytic crossing and steps until `round` agrees.
    """
    per_document = catalogue.tokens / max(len(catalogue.lines), 1)
    if per_document <= 0:
        return 0
    size = max(int(budget_tokens / per_document), 0)
    while round(per_document * size) <= budget_tokens:
        size += 1
    return size


def scale_projection(catalogue: CompactCatalogue, *, budget_tokens: int) -> list[dict]:
    """Tokens against catalogue size, and where it stops fitting.

    Linear because the context IS linear in the number of products: one line each. That is the
    argument in one line — retrieval's cost per query does not move with the catalogue, and
    this one does, until it hits a wall.
    """
    per_document = catalogue.tokens / max(len(catalogue.lines), 1)
    out = []
    for size in SCALE_POINTS:
        projected = round(per_document * size)
        out.append(
            {
                "documents": size,
                "tokens": projected,
                "fits": projected <= budget_tokens,
            }
        )
    return out


def answered_skus(answer: str) -> list[str]:
    """Codes the model named, in order, deduplicated.

    The configuration answers in prose, so its "ranked list" is whatever it cited. Parsing the
    codes rather than asking for JSON keeps the prompt closer to what a context-only prototype
    would actually have looked like.
    """
    seen: set[str] = set()
    out: list[str] = []
    for match in _ANSWER.finditer(answer or ""):
        sku = match.group(1).upper()
        if sku not in seen:
            seen.add(sku)
            out.append(sku)
    return out


PROMPT = (
    "Eres el buscador de una joyería. Abajo tienes el catálogo completo, una línea por "
    "producto con el formato `SKU · nombre · tipo · materiales`.\n\n"
    "Devuelve los {k} productos que mejor responden a la consulta, del mejor al peor, "
    "citando SOLO sus SKU separados por comas. Si el catálogo no puede responderla, "
    "responde exactamente NINGUNO.\n\n"
    "Consulta: {query}\n\n"
    "Catálogo:\n{catalogue}\n"
)


def build_prompt(query: str, catalogue: CompactCatalogue, *, k: int = 5) -> str:
    return PROMPT.format(k=k, query=query, catalogue=catalogue.text)


def as_json(catalogue: CompactCatalogue, *, budget_tokens: int) -> str:
    return json.dumps(
        {
            "documents_total": catalogue.documents_total,
            "documents_omitted": catalogue.documents_omitted,
            "tokens": catalogue.tokens,
            "budget_tokens": budget_tokens,
            "scale": scale_projection(catalogue, budget_tokens=budget_tokens),
            "breaks_at_documents": breaking_point(catalogue, budget_tokens=budget_tokens),
        },
        ensure_ascii=False,
    )
