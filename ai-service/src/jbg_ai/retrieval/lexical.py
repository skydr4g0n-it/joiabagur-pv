"""Safe composition of the lexical `tsquery`. Delivered by C21.

The shape is inherited from `retrieval/measure.py`, which was the only place in C20 that
composed a `tsquery` at all: one `plainto_tsquery` per emitted surface form, alternatives
OR-ed inside a group, every term a bound parameter and no query syntax ever concatenated.
Two things change here.

**Groups are OR-ed with each other, not AND-ed.** Measured against the live index, a strict
conjunction between groups leaves 7 of the 10 real recorded operator queries matching zero
documents, because the conjunction of individually frequent words matches nothing:
`anillo & plata & regalar` = 0, since only 7 documents of 1.168 mention `regalo` and none of
them is a silver ring. OR plus coordination *contains* the conjunction's result and places it
at the head of the list, so it dominates the conjunction rather than trading precision for it.

**Coordination decides the order, and only some groups may decide it.** See
`SPARSE_VOCABULARY_FIELDS`.

Nothing here opens a session or a socket: it returns SQL fragments plus their bound
parameters, and `retrieval/search.py` assembles the statement.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from jbg_ai.retrieval.synonyms import ExpandedQuery

#: Vocabulary fields whose absence from a document is **not** evidence that the document is
#: irrelevant, measured as `doc_text` line coverage over the 1.168 live rows on 2026-09-02:
#: `Ocasiones:` 13 %, `Estilo:` 11 %, `Colores:` 19 %, `Talla:` 45 %. A group resolving to one
#: of these still contributes to `ts_rank`; what it loses is the right to jump the queue. With
#: `boda` matching 5 documents of 1.168, letting it count would put those five ahead of 1.163
#: equally suitable pieces — false precision manufactured out of a sparsely tagged field.
#:
#: A code constant and deliberately not a setting: it is a property of the corpus, not of the
#: deployment, and exposing it would invite editing it without re-measuring coverage.
#: `size_label` is here because the demoting filter of `retrieval/filters.py` owns it — one
#: field, one mechanism. `piece_type` (99 %), `materials` (89 %) and `stone_type` (54 %) count.
SPARSE_VOCABULARY_FIELDS = frozenset(
    {
        "occasion_tags",  # 13 %
        "style_tags",  # 11 %
        "color_tags",  # 19 %
        "size_label",  # 45 %, owned by the demoting filter instead
    }
)

TYPED_LIST = "typed"
EXPANDED_LIST = "expanded"

#: `plainto_tsquery` for every emitted surface form, always, and never `phraseto_tsquery`:
#: measured, the positional operator leaves `aro de dedo` — the overlay entry C20 credits with
#: +262 documents — matching 0 documents against `plainto`'s 6. If an emitted form ever proves
#: too loose the fix is the dictionary entry, not the constructor.
_PLAINTO = "plainto_tsquery('spanish', {placeholder})"

#: `websearch_to_tsquery` for the operator's own text, which buys `"quoted phrases"` and
#: `-negation` for free. A syntax mistake cannot empty the result, because the expanded list
#: interprets no syntax at all: at worst the typed list loses a vote.
_WEBSEARCH = "websearch_to_tsquery('spanish', {placeholder})"

Placeholder = Callable[[str], str]
"""Renders a bound term's name as its placeholder: `:lex_3`, `%(lex_3)s`, or a bare `%s`.

The driver decides the style; the naming stays here so a fragment repeated in the SELECT and
in the WHERE binds the same parameter twice instead of demanding it twice.
"""


def term_name(index: int) -> str:
    """The bound name of the index-th surface form."""
    return f"lex_{index}"


@dataclass(frozen=True)
class LexicalRequest:
    """What one lexical list searches for. Carries no SQL, so the port stays SQL-free."""

    name: str
    text: str
    groups: tuple[tuple[str, ...], ...] = ()
    counting: tuple[bool, ...] = ()


@dataclass(frozen=True)
class LexicalFragments:
    """SQL fragments plus their bound parameters. Terms never reach the statement text."""

    match: str
    coordination: str
    params: dict[str, object]


def compose_group_fragments(
    groups: Sequence[Sequence[str]],
    *,
    placeholder: Placeholder,
) -> tuple[tuple[str, ...], list[str]]:
    """One `plainto_tsquery` per surface form, alternatives OR-ed inside each group.

    Returns the per-group fragments and the terms to bind, in the order the placeholders
    were requested. How the groups are combined with each other is the caller's decision:
    the lexical branch ORs them (`build_fragments`), the C20 reach measurement ANDs them.
    """
    fragments: list[str] = []
    params: list[str] = []
    for group in groups:
        alternatives = []
        for form in group:
            alternatives.append(_PLAINTO.format(placeholder=placeholder(term_name(len(params)))))
            params.append(form)
        fragments.append("(" + " || ".join(alternatives) + ")")
    return tuple(fragments), params


def counting_flags(expanded: ExpandedQuery) -> tuple[bool, ...]:
    """One flag per group: may it decide the coordination order?

    Read off `ExpandedQuery.matched`, which C20 delivered for exactly this and which lists
    the resolved terms in group order. A group the vocabulary did not resolve **counts**: it
    is a literal word the operator typed, and absence of a word nobody catalogued is the
    strongest evidence there is — it is what lifts the *Anillo de Filigrana* from position 7
    to 1 for `anillo de filigrana tradicional menorquina`.
    """
    pending = list(expanded.matched)
    flags: list[bool] = []
    for group in expanded.groups:
        head = group[0] if group else ""
        if pending and pending[0].term == head:
            resolved = pending.pop(0)
            flags.append(resolved.field not in SPARSE_VOCABULARY_FIELDS)
        else:
            flags.append(True)
    return tuple(flags)


def typed_request(text: str) -> LexicalRequest:
    """List A: the operator's own phrasing, keeping a vote of its own.

    It must exist because the expanded list, on its own, places none of the nine products
    literally named "Sortija" in its top six for `sortija de plata`.
    """
    return LexicalRequest(name=TYPED_LIST, text=text)


def expanded_request(expanded: ExpandedQuery) -> LexicalRequest:
    """List B: C20's equivalence groups, OR-ed, ordered by coordination."""
    return LexicalRequest(
        name=EXPANDED_LIST,
        text=expanded.original,
        groups=expanded.groups,
        counting=counting_flags(expanded),
    )


def build_fragments(request: LexicalRequest, *, placeholder: Placeholder) -> LexicalFragments:
    """Compose the candidate-set expression and the coordination tally for one list."""
    if not request.groups:
        name = term_name(0)
        match = _WEBSEARCH.format(placeholder=placeholder(name))
        return LexicalFragments(
            match=match,
            coordination=f"(tsv @@ {match})::int",
            params={name: request.text},
        )

    fragments, terms = compose_group_fragments(request.groups, placeholder=placeholder)
    params: dict[str, object] = {term_name(index): term for index, term in enumerate(terms)}

    counting = request.counting or tuple(True for _ in fragments)
    tallied = [
        f"(tsv @@ {fragment})::int"
        for fragment, counts in zip(fragments, counting, strict=False)
        if counts
    ]
    # A group matching no document adds 0 to every document's coordination, so it cannot
    # change the order: the `EXISTS`-per-group zero-drop the exploration first proposed is
    # unnecessary. A query with no counting group at all leaves the ordering to `ts_rank`,
    # and through it to the vector branch — which is D4's emergent adaptive weighting.
    return LexicalFragments(
        match="(" + " || ".join(fragments) + ")",
        coordination=" + ".join(tallied) if tallied else "0",
        params=params,
    )
