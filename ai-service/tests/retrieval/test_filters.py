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
        assert "AND materials && CAST(:materials AS text[])" in sql
        assert "AND piece_type = :category" in sql
        assert "AND family_id = :family_id" in sql
        assert "AND product_id <> ALL(CAST(:exclude_ids AS uuid[]))" in sql


def test_material_filter_uses_overlap_by_default() -> None:
    filters = SearchFilters(materials=["plata", "oro"])
    lexical_sql, _ = compile_lexical_sql(typed_request("anillo"), filters)

    for sql in (compile_search_sql(filters), lexical_sql):
        assert "materials && CAST(:materials AS text[])" in sql
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
