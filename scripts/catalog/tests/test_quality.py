from __future__ import annotations

from catalog_pipeline.constants import DEFAULT_SEED
from catalog_pipeline.errors import RatioError
from catalog_pipeline.generate import build_records
from catalog_pipeline.grouping import group_products
from catalog_pipeline.quality import assign_quality, assert_ratio_tolerance, ratios_by_tier
import pytest


def test_variant_family_shares_text_quality(fixture_rows):
    grouping = group_products(fixture_rows)
    sku_to_group = {sku: item.variant_group_key for sku, item in grouping.items()}
    assigned = assign_quality(sku_to_group, seed=DEFAULT_SEED)
    family = [assigned[sku].text_quality_tier for sku in ("RING-S", "RING-M", "RING-L")]
    assert len(set(family)) == 1
    for sku in ("RING-S", "RING-M", "RING-L"):
        quality = assigned[sku]
        if quality.text_quality_tier == "original":
            assert quality.text_provenance == "merchant"
        else:
            assert quality.text_provenance == "ai_assisted"


def test_ratios_pass_on_balanced_synthetic_and_fail_otherwise():
    balanced = ["rich"] * 70 + ["sparse"] * 20 + ["original"] * 10
    assert_ratio_tolerance(ratios_by_tier(balanced))
    with pytest.raises(RatioError):
        assert_ratio_tolerance(ratios_by_tier(["rich"] * 100))


def test_rebalance_moves_whole_families_into_tolerance():
    from catalog_pipeline.models import QualityAssignment
    from catalog_pipeline.quality import rebalance_assignments

    sku_to_group = {f"S{i:03}": f"g{i:03}" for i in range(100)}
    assigned = {
        sku: QualityAssignment(text_quality_tier="rich", text_provenance="ai_assisted")
        for sku in sku_to_group
    }
    rebalanced = rebalance_assignments(sku_to_group, assigned)
    tiers = [item.text_quality_tier for item in rebalanced.values()]
    assert_ratio_tolerance(ratios_by_tier(tiers))
    by_group: dict[str, set[str]] = {}
    for sku, group in sku_to_group.items():
        by_group.setdefault(group, set()).add(rebalanced[sku].text_quality_tier)
    assert all(len(tiers) == 1 for tiers in by_group.values())


def test_generator_is_deterministic_for_same_seed(fixture_rows):
    first = build_records(fixture_rows, seed=DEFAULT_SEED)
    second = build_records(fixture_rows, seed=DEFAULT_SEED)
    assert {r.sku: (r.variant_group_key, r.text_quality_tier) for r in first} == {
        r.sku: (r.variant_group_key, r.text_quality_tier) for r in second
    }
    assert {r.sku: r.description for r in first} == {r.sku: r.description for r in second}


def test_different_seed_may_change_tiers_without_mixing(fixture_rows):
    default = {r.sku: r.text_quality_tier for r in build_records(fixture_rows, seed=DEFAULT_SEED)}
    other = {r.sku: r.text_quality_tier for r in build_records(fixture_rows, seed="99999999")}
    records = build_records(fixture_rows, seed="99999999")
    by_group: dict[str, set[str]] = {}
    for record in records:
        by_group.setdefault(record.variant_group_key, set()).add(record.text_quality_tier)
    assert all(len(tiers) == 1 for tiers in by_group.values())
    assert default.keys() == other.keys()
