"""Structural filters that demote, and body filters that still exclude. Delivered by C21."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from jbg_ai.retrieval.filters import StructuralFilters, demote, extract_filters
from jbg_ai.retrieval.lexical import expanded_request, typed_request
from jbg_ai.retrieval.ports import SearchFilters
from jbg_ai.retrieval.search import compile_lexical_sql, compile_search_sql
from jbg_ai.retrieval.synonyms import ExpandedQuery, TermMatch, expand_query

FAMILY = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


@dataclass
class _Item:
    sku: str
    price: float | None = None
    size_label: str | None = None
    materials: list[str] | None = None

    def __post_init__(self) -> None:
        if self.materials is None:
            self.materials = []


def _expanded(query: str) -> ExpandedQuery:
    return expand_query(query, enabled=True)


# --------------------------------------------------------------------------------------
# 5.1 Extraction by rule, reusing what C20 already resolved
# --------------------------------------------------------------------------------------


def test_extracts_price_ceiling_from_natural_phrase() -> None:
    for text, expected in (
        ("anillo de plata menos de 80", 80.0),
        ("collar por debajo de 120 euros", 120.0),
        ("pulsera hasta 45€", 45.0),
        ("pendientes maximo 99,50", 99.5),
        ("colgante no mas de 30 eur", 30.0),
    ):
        assert extract_filters(_expanded(text)).price_ceiling == expected, text


def test_never_invents_filter_absent_from_query() -> None:
    extracted = extract_filters(_expanded("anillo bonito"))

    assert extracted.price_ceiling is None
    assert extracted.size is None
    assert extracted.materials == ()
    assert extracted.is_empty is True
    assert extracted.describe() == "none"


def test_a_bare_number_is_not_a_price_ceiling() -> None:
    """A rule firing on "80" alone would invent a constraint out of a reference number."""
    assert extract_filters(_expanded("anillo 80")).price_ceiling is None
    assert extract_filters(_expanded("collar 3 vueltas")).price_ceiling is None


def test_materials_and_size_come_from_the_terms_expansion_already_resolved() -> None:
    expanded = ExpandedQuery(
        original="anillo de plata talla 16",
        groups=(("anillo",), ("plata",), ("16",)),
        matched=(
            TermMatch(term="anillo", field="piece_type", canonical="anillo"),
            TermMatch(term="plata", field="materials", canonical="plata"),
            TermMatch(term="16", field="size_label", canonical="16"),
        ),
    )
    extracted = extract_filters(expanded)

    assert extracted.materials == ("plata",)
    assert extracted.size == "16"
    assert "materials=plata" in extracted.describe()
    assert "size=16" in extracted.describe()


# --------------------------------------------------------------------------------------
# 5.2 Demotion is a stable block sort that removes nothing
# --------------------------------------------------------------------------------------


def test_structural_filter_demotes_but_never_removes() -> None:
    items = [
        _Item("over-1", price=200.0),
        _Item("within-1", price=10.0),
        _Item("over-2", price=150.0),
        _Item("within-2", price=20.0),
        _Item("unpriced", price=None),
    ]
    ordered, demoted = demote(items, StructuralFilters(price_ceiling=80.0))

    assert len(ordered) == len(items), "nothing leaves the over-retrieval window"
    assert [item.sku for item in ordered] == [
        "within-1",
        "within-2",
        "unpriced",
        "over-1",
        "over-2",
    ]
    assert demoted == 2


def test_the_fused_order_survives_inside_each_block() -> None:
    items = [_Item(f"o{index}", price=200.0 + index) for index in range(3)]
    items += [_Item(f"w{index}", price=10.0 + index) for index in range(3)]
    ordered, _ = demote(items, StructuralFilters(price_ceiling=80.0))

    assert [item.sku for item in ordered] == ["w0", "w1", "w2", "o0", "o1", "o2"]


def test_an_unknown_projection_never_demotes() -> None:
    """Absence of a price or a size is not evidence of breaking the constraint."""
    items = [_Item("no-price"), _Item("no-size")]
    ordered, demoted = demote(items, StructuralFilters(price_ceiling=80.0, size="16"))

    assert [item.sku for item in ordered] == ["no-price", "no-size"]
    assert demoted == 0


def test_no_extracted_constraint_is_a_no_op() -> None:
    items = [_Item("a", price=900.0), _Item("b", price=1.0)]
    ordered, demoted = demote(items, StructuralFilters())

    assert [item.sku for item in ordered] == ["a", "b"]
    assert demoted == 0


def test_a_document_with_no_extracted_materials_is_not_demoted() -> None:
    """126 documents (10,8 %) carry none: they are undescribed pieces, not pieces of nothing."""
    items = [
        _Item("gold", materials=["oro"]),
        _Item("untagged", materials=[]),
        _Item("silver", materials=["plata"]),
    ]
    ordered, demoted = demote(items, StructuralFilters(materials=("plata",)))

    assert [item.sku for item in ordered] == ["untagged", "silver", "gold"]
    assert demoted == 1
    assert "gold" in [item.sku for item in ordered]


def test_multi_material_query_uses_contains_all() -> None:
    """Inverted on purpose: it pins the EXCLUSION of `@>`, not its use.

    The ficha and design §7.3 asked for `materials @> ARRAY[...]` when the query names more
    than one material. Measured against this corpus, `@>` reaches **60 documents where `&&`
    reaches 913**, because 91,6 % of the catalogue carries one material or none. Requiring
    every named material is a recall cliff, so a candidate holding only one of them stays.
    """
    items = [_Item("one-of-two", materials=["plata"]), _Item("neither", materials=["cuero"])]
    ordered, demoted = demote(items, StructuralFilters(materials=("plata", "oro")))

    assert [item.sku for item in ordered] == ["one-of-two", "neither"]
    assert demoted == 1, "only the candidate holding neither is demoted, and it is kept"


def test_size_mismatch_demotes_behind_a_price_breach_but_ahead_of_nothing() -> None:
    items = [
        _Item("wrong-size", price=10.0, size_label="20"),
        _Item("too-dear", price=900.0, size_label="16"),
        _Item("perfect", price=10.0, size_label="16"),
    ]
    ordered, _ = demote(items, StructuralFilters(price_ceiling=80.0, size="16"))

    assert [item.sku for item in ordered] == ["perfect", "wrong-size", "too-dear"]


# --------------------------------------------------------------------------------------
# 5.3 / 5.4 What still excludes, and what must never appear in SQL
# --------------------------------------------------------------------------------------


def test_body_filters_remain_hard() -> None:
    """A person clicked them in the panel, so they exclude. Rules never do."""
    filters = SearchFilters(
        materials=["plata"],
        category="anillo",
        family_id=FAMILY,
        exclude_product_ids=[UUID(int=7)],
    )
    lexical_sql, _ = compile_lexical_sql(typed_request("anillo"), filters)

    for sql in (compile_search_sql(filters), lexical_sql):
        assert "AND d.materials && CAST(:materials AS text[])" in sql
        assert "AND d.piece_type = :category" in sql
        assert "AND d.family_id = :family_id" in sql
        assert "AND d.product_id <> ALL(CAST(:exclude_ids AS uuid[]))" in sql


def test_material_filter_uses_overlap_by_default() -> None:
    filters = SearchFilters(materials=["plata", "oro"])
    lexical_sql, _ = compile_lexical_sql(typed_request("anillo"), filters)

    for sql in (compile_search_sql(filters), lexical_sql):
        assert "d.materials && CAST(:materials AS text[])" in sql
        assert "@>" not in sql, "containment is a recall cliff: 60 documents against 913"


def test_an_extracted_piece_type_produces_no_where_clause() -> None:
    """A lexical hit on the canonical term already equals filtering by `piece_type`.

    Measured by C20: `anillo` matches 268 documents and `piece_type = 'anillo'` selects the
    same 268. Adding a `WHERE` would constrain only the branch that rescues paraphrase.
    """
    expanded = _expanded("anillo de plata")
    assert any(item.field == "piece_type" for item in expanded.matched)

    extracted = extract_filters(expanded)
    assert not hasattr(extracted, "piece_type")

    empty = SearchFilters()
    lexical_sql, _ = compile_lexical_sql(expanded_request(expanded), empty)
    assert "piece_type" not in lexical_sql
    assert "piece_type" not in compile_search_sql(empty)


def test_neither_branch_carries_a_price_or_stock_predicate() -> None:
    filters = SearchFilters(materials=["plata"])
    lexical_sql, _ = compile_lexical_sql(typed_request("anillo menos de 80"), filters)

    for sql in (compile_search_sql(filters), lexical_sql):
        predicates = [
            line
            for line in sql.splitlines()
            if "price" in line and line.strip().startswith(("AND", "WHERE", "OR"))
        ]
        assert predicates == []
        assert "stock" not in sql


# --------------------------------------------------------------------- availability (C22)


class _Candidate:
    """The smallest thing `demotion_rank` can read."""

    def __init__(self, *, price=None, size_label=None, materials=None, qty_bucket=None):
        self.price = price
        self.size_label = size_label
        self.materials = materials or []
        self.qty_bucket = qty_bucket


def test_the_ordering_key_is_one_tuple_with_stock_last() -> None:
    """One key, not two sorts: priority is readable here instead of emerging from order."""
    from jbg_ai.retrieval.filters import StructuralFilters, demotion_rank

    key = demotion_rank(_Candidate(qty_bucket="0"), StructuralFilters())

    assert len(key) == 4
    assert key == (0, 0, 0, 1), "availability is the last component and nothing else fired"


def test_an_absent_bucket_is_not_a_zero_bucket() -> None:
    """`None` means the query ran unscoped. An absent signal must not demote anything."""
    from jbg_ai.retrieval.filters import StructuralFilters, demotion_rank

    assert demotion_rank(_Candidate(qty_bucket=None), StructuralFilters())[3] == 0
    assert demotion_rank(_Candidate(qty_bucket="0"), StructuralFilters())[3] == 1


def test_the_two_non_zero_buckets_rank_identically() -> None:
    """Ordering `1-2` before `3+` would be a magic number with no evidence behind it."""
    from jbg_ai.retrieval.filters import StructuralFilters, demotion_rank

    filters = StructuralFilters()

    assert demotion_rank(_Candidate(qty_bucket="1-2"), filters) == demotion_rank(
        _Candidate(qty_bucket="3+"), filters
    )


def test_stock_only_decides_between_candidates_the_typed_blocks_rank_equally() -> None:
    from jbg_ai.retrieval.filters import StructuralFilters, demotion_rank

    filters = StructuralFilters(price_ceiling=80.0)
    over_but_stocked = _Candidate(price=900.0, qty_bucket="3+")
    within_but_empty = _Candidate(price=40.0, qty_bucket="0")

    assert demotion_rank(within_but_empty, filters) < demotion_rank(over_but_stocked, filters)


def test_demote_reorders_on_stock_alone_when_no_rule_fired() -> None:
    """The early return is on "nothing to demote by", and stock is now part of that."""
    from jbg_ai.retrieval.filters import StructuralFilters, demote

    empty = _Candidate(qty_bucket="0")
    stocked = _Candidate(qty_bucket="3+")

    ordered, demoted = demote([empty, stocked], StructuralFilters())

    assert ordered == (stocked, empty)
    assert demoted == 1


def test_demote_keeps_every_candidate_inside_the_window() -> None:
    from jbg_ai.retrieval.filters import StructuralFilters, demote

    candidates = [_Candidate(qty_bucket="0"), _Candidate(qty_bucket="3+")]

    ordered, _ = demote(candidates, StructuralFilters())

    assert len(ordered) == len(candidates), "a demotion never removes"
