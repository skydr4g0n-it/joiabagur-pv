from __future__ import annotations

from catalog_pipeline.grouping import group_products


def test_size_family_shares_group_and_labels(fixture_rows):
    grouping = group_products(fixture_rows)
    family = [grouping[sku] for sku in ("RING-S", "RING-M", "RING-L")]
    keys = {item.variant_group_key for item in family}
    assert len(keys) == 1
    assert all(item.variant_label for item in family)
    members = set(family[0].family_seed.member_skus)
    assert members == {"RING-S", "RING-M", "RING-L"}
    assert family[0].family_seed.member_skus == tuple(sorted(members))


def test_unary_products_are_singleton_groups(fixture_rows):
    grouping = group_products(fixture_rows)
    for sku in ("NECK-01", "BRAC-01", "EAR-01", "UNMATCH-99"):
        item = grouping[sku]
        assert item.family_seed.member_skus == (sku,)
        assert item.variant_label is None


def test_grouping_is_deterministic(fixture_rows):
    first = {sku: item.variant_group_key for sku, item in group_products(fixture_rows).items()}
    second = {sku: item.variant_group_key for sku, item in group_products(fixture_rows).items()}
    assert first == second
