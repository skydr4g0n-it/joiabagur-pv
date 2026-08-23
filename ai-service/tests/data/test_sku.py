"""SKU allocator: real scheme from 437, unique vs C06a. Delivered by C06b."""

from __future__ import annotations

from jbg_ai.data.sku import allocate_skus, format_sku, is_real_scheme_sku, occupied_skus_from_jsonl
from support.paths import REAL_CATALOG_JSONL


def test_sku_follows_real_magnitude_scheme() -> None:
    assert format_sku(1) == "SKU01"
    assert format_sku(9) == "SKU09"
    assert format_sku(99) == "SKU99"
    assert format_sku(100) == "SKU100"
    assert format_sku(437) == "SKU437"
    assert format_sku(999) == "SKU999"
    assert format_sku(1000) == "SKU1000"
    assert is_real_scheme_sku("SKU437")
    assert not is_real_scheme_sku("SYN-437")
    assert not is_real_scheme_sku("JB-S-437")


def test_skus_are_unique_across_real_and_synthetic() -> None:
    occupied = occupied_skus_from_jsonl(REAL_CATALOG_JSONL)
    reserved = allocate_skus(20, occupied, seed="20260822")
    assert reserved[0] == "SKU440"
    assert occupied.isdisjoint(reserved)
    assert len(set(reserved)) == 20
    assert all(is_real_scheme_sku(sku) for sku in reserved)
    assert not any(sku.startswith(("SYN-", "JB-S-")) for sku in reserved)


def test_sku_allocator_is_deterministic_for_same_seed() -> None:
    occupied = {"SKU01", "SKU437"}
    first = allocate_skus(5, occupied, seed="20260822")
    second = allocate_skus(5, occupied, seed="20260822")
    assert first == second
    assert first[0] == "SKU438"
