"""Safe composition of the lexical `tsquery` and the coordination tally. Delivered by C21.

Every assertion here is offline: the module returns SQL fragments and bound parameters, and
never opens a session.
"""

from __future__ import annotations

from jbg_ai.retrieval.lexical import (
    SPARSE_VOCABULARY_FIELDS,
    build_fragments,
    counting_flags,
    expanded_request,
    typed_request,
)
from jbg_ai.retrieval.synonyms import ExpandedQuery, TermMatch, expand_query


def _named(name: str) -> str:
    return f":{name}"


def _expanded(query: str, *, enabled: bool = True) -> ExpandedQuery:
    return expand_query(query, enabled=enabled)


def test_one_placeholder_per_surface_form_and_no_operator_text_in_the_sql() -> None:
    expanded = _expanded("sortija de plata")
    fragments = build_fragments(expanded_request(expanded), placeholder=_named)

    forms = [form for group in expanded.groups for form in group]
    assert len(fragments.params) == len(forms)
    assert sorted(fragments.params.values()) == sorted(forms)
    for form in forms:
        assert form not in fragments.match, "terms travel as parameters, never as SQL text"
    assert "sortija" not in fragments.match
    assert "anillo" not in fragments.match


def test_groups_are_ored_with_each_other_and_never_conjoined() -> None:
    """Measured: `&&` between groups leaves 7 of the 10 real recorded queries at zero rows."""
    fragments = build_fragments(
        expanded_request(_expanded("anillo de plata para regalar")), placeholder=_named
    )

    assert "||" in fragments.match
    assert "&&" not in fragments.match


def test_surface_forms_use_plainto_not_phraseto() -> None:
    """`phraseto_tsquery` leaves `aro de dedo` at 0 documents against `plainto`'s 6."""
    fragments = build_fragments(
        expanded_request(_expanded("aro de dedo de plata")), placeholder=_named
    )

    assert "plainto_tsquery" in fragments.match
    assert "phraseto_tsquery" not in fragments.match
    assert "<->" not in fragments.match


def test_typed_list_uses_websearch_so_quotes_and_negation_reach_the_query() -> None:
    request = typed_request('"anillo de plata" -chapado')
    fragments = build_fragments(request, placeholder=_named)

    assert "websearch_to_tsquery" in fragments.match
    assert list(fragments.params.values()) == ['"anillo de plata" -chapado']
    assert '"anillo de plata"' not in fragments.match


def test_malformed_websearch_input_does_not_raise() -> None:
    for text in ('unbalanced "quote', "-", "", "   ", "&& || !"):
        fragments = build_fragments(typed_request(text), placeholder=_named)
        assert "websearch_to_tsquery" in fragments.match
        assert list(fragments.params.values()) == [text]


def test_sparse_vocabulary_fields_do_not_count_towards_coordination() -> None:
    """`Ocasiones:` covers 13 % of the corpus and `boda` matches 5 rows of 1.168."""
    expanded = ExpandedQuery(
        original="anillo de boda",
        groups=(("anillo",), ("de",), ("boda",)),
        matched=(
            TermMatch(term="anillo", field="piece_type", canonical="anillo"),
            TermMatch(term="boda", field="occasion_tags", canonical="boda"),
        ),
    )

    assert counting_flags(expanded) == (True, True, False)

    fragments = build_fragments(expanded_request(expanded), placeholder=_named)
    assert fragments.coordination.count("(tsv @@ ") == 2, "the occasion group does not count"
    # It is still part of the candidate set and still scores in `ts_rank`.
    assert fragments.match.count("plainto_tsquery") == 3


def test_every_sparse_field_is_excluded_and_the_structural_ones_are_not() -> None:
    assert SPARSE_VOCABULARY_FIELDS == {
        "occasion_tags",
        "style_tags",
        "color_tags",
        "size_label",
    }
    for field in ("piece_type", "materials", "stone_type"):
        assert field not in SPARSE_VOCABULARY_FIELDS


def test_unresolved_term_counts_towards_coordination() -> None:
    """A literal word nobody catalogued: the Stripe case, and the *Anillo de Filigrana*."""
    expanded = ExpandedQuery(
        original="anillo filigrana",
        groups=(("anillo",), ("filigrana",)),
        matched=(TermMatch(term="anillo", field="piece_type", canonical="anillo"),),
    )

    assert counting_flags(expanded) == (True, True)


def test_a_group_matching_nothing_adds_zero_to_every_document() -> None:
    """Which is why no separate zero-drop step is needed to detect and remove it."""
    expanded = _expanded("anillo de plata para regalar")
    fragments = build_fragments(expanded_request(expanded), placeholder=_named)

    terms = fragments.coordination.count("(tsv @@ ")
    assert terms >= 1
    assert " + " in fragments.coordination or terms == 1
    assert "EXISTS" not in fragments.coordination


def test_a_query_of_only_sparse_terms_leaves_the_ordering_to_ts_rank() -> None:
    """D4's emergent property: the vector branch decides a mostly subjective query."""
    expanded = ExpandedQuery(
        original="algo elegante",
        groups=(("elegante",),),
        matched=(TermMatch(term="elegante", field="style_tags", canonical="elegante"),),
    )

    fragments = build_fragments(expanded_request(expanded), placeholder=_named)
    assert fragments.coordination == "0"
    assert "plainto_tsquery" in fragments.match


def test_disabled_expansion_emits_one_form_per_token() -> None:
    expanded = _expanded("sortija de plata", enabled=False)
    fragments = build_fragments(expanded_request(expanded), placeholder=_named)

    assert sorted(fragments.params.values()) == ["de", "plata", "sortija"]
    assert counting_flags(expanded) == (True, True, True)
