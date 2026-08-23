"""Lexical family planner and copy consistency. Delivered by C06b."""

from __future__ import annotations

from jbg_ai.data.briefs import default_briefs, distribute_uneven, unassigned_count
from jbg_ai.data.families import (
    assert_family_copy_consistent,
    expand_base,
    family_completeness_ratios,
    plan_family_shapes,
    plan_slots,
    strip_size_suffix,
)
from jbg_ai.data.llm import PieceDraft
from jbg_ai.data.records import SyntheticRecord


def test_distribute_uneven_is_unequal_for_full_budget() -> None:
    counts = distribute_uneven(611, 10, "20260822")
    assert sum(counts) == 611
    assert all(count >= 1 for count in counts)
    assert len(set(counts)) == 10


def test_unassigned_count_is_about_20_percent() -> None:
    assert unassigned_count(764) == 153


def test_family_shapes_hit_60_40_on_full_budget() -> None:
    shapes = plan_family_shapes(764, "20260822")
    assert sum(len(shape) if shape else 1 for shape in shapes) == 764
    complete = sum(len(shape) for shape in shapes if len(shape) == 4)
    incomplete = sum(len(shape) for shape in shapes if 2 <= len(shape) <= 3)
    total = complete + incomplete
    assert total > 0
    complete_pct = 100.0 * complete / total
    assert abs(complete_pct - 60.0) <= 5.0


def test_plan_slots_keeps_family_in_one_collection() -> None:
    slots = plan_slots(764, default_briefs(), "20260822")
    products = sum(len(slot.sizes) if slot.sizes else 1 for slot in slots)
    assert products == 764
    unassigned = sum(
        (len(slot.sizes) if slot.sizes else 1)
        for slot in slots
        if not slot.brief.name
    )
    assert abs(100.0 * unassigned / 764 - 20.0) <= 5.0
    named = [slot.brief.name for slot in slots if slot.brief.name]
    assert 8 <= len(set(named)) <= 12


def test_strip_size_and_expand_share_copy() -> None:
    assert strip_size_suffix("Colgante erizo S") == "Colgante erizo"
    draft = PieceDraft(name="Anillo Alhambra M", description="Plata de montura.", price="100.00")
    expanded = expand_base(draft, ("S", "M", "L", "XL"), taken_stems=set())
    assert [name for name, _ in expanded] == [
        "Anillo Alhambra S",
        "Anillo Alhambra M",
        "Anillo Alhambra L",
        "Anillo Alhambra XL",
    ]
    assert len({price for _, price in expanded}) == 4


def test_family_copy_consistency_and_completeness_ratios() -> None:
    records = [
        SyntheticRecord(
            sku="SKU440",
            name="Anillo X S",
            description="Misma.",
            price="90.00",
            collection_name="Fuego",
        ),
        SyntheticRecord(
            sku="SKU441",
            name="Anillo X M",
            description="Misma.",
            price="100.00",
            collection_name="Fuego",
        ),
        SyntheticRecord(
            sku="SKU442",
            name="Anillo X L",
            description="Misma.",
            price="115.00",
            collection_name="Fuego",
        ),
        SyntheticRecord(
            sku="SKU443",
            name="Anillo X XL",
            description="Misma.",
            price="130.00",
            collection_name="Fuego",
        ),
        SyntheticRecord(
            sku="SKU444",
            name="Colgante Y S",
            description="Otra.",
            price="80.00",
            collection_name="",
        ),
        SyntheticRecord(
            sku="SKU445",
            name="Colgante Y L",
            description="Otra.",
            price="95.00",
            collection_name="",
        ),
    ]
    assert_family_copy_consistent(records)
    complete_pct, incomplete_pct, total = family_completeness_ratios(records)
    assert total == 6
    assert abs(complete_pct - (400 / 6)) < 0.01
    assert abs(incomplete_pct - (200 / 6)) < 0.01
