"""World ingest on FakeWorldStore: no catalog writes, D6 users, rollback."""

from __future__ import annotations

import random

import pytest

from jbg_ai.data.errors import IngestAborted
from jbg_ai.data.world.constants import (
    CLOSED_HOTEL_CODE,
    OPERATOR_POS,
    PAYMENT_CODES,
)
from jbg_ai.data.world.ingest import FakeWorldStore, password_matches, run_ingest
from jbg_ai.data.world.simulate import simulate_world
from tests.data.world.helpers import AS_OF, make_profiles, tiny_catalog


def _hash(password: str) -> str:
    return f"$test${password}"


def _store_and_world():
    catalog = tiny_catalog(include_holes=False)
    profiles = make_profiles()
    result = simulate_world(profiles, catalog, as_of=AS_OF, rng=random.Random("20260823"))
    products = {
        item.sku: {"id": f"id-{item.sku}", "name": item.name, "price": "89.00"}
        for item in catalog
        if item.sku not in {"SKU135", "SKU400", "SKU418"}
    }
    store = FakeWorldStore(
        products=products,
        collections={"El Jaleo", "Cielo estrellado"},
    )
    return store, profiles, result, dict(products)


def test_ingest_does_not_touch_products_or_collections() -> None:
    store, profiles, result, products_before = _store_and_world()
    counts = run_ingest(
        store,
        profiles,
        result.inventories,
        result.sales,
        result.movements,
        hash_password=_hash,
    )
    assert counts.pos == 12
    assert counts.users == 3
    assert counts.user_pos == 3
    assert counts.payments == 11 * len(PAYMENT_CODES)
    assert store.snapshot_product_skus() == {
        sku: (row["name"], row["price"]) for sku, row in products_before.items()
    }
    assert store.collections == {"El Jaleo", "Cielo estrellado"}
    assert store.family_counts == (0, 0)
    assert store.ai_rows == 0
    assert store.committed is True


def test_operator_sales_only_on_assigned_pos() -> None:
    store, profiles, result, _ = _store_and_world()
    run_ingest(
        store,
        profiles,
        result.inventories,
        result.sales,
        result.movements,
        hash_password=_hash,
    )
    users_by_id = {row["id"]: username for username, row in store.users.items()}
    pos_by_id = {row["id"]: code for code, row in store.pos.items()}
    inverse = {assigned: username for username, assigned in OPERATOR_POS.items()}
    for sale in store.sales:
        pos_code = pos_by_id[sale["pos_id"]]
        user_id = sale["user_id"]
        if pos_code in inverse:
            assert users_by_id[user_id] == inverse[pos_code]
        else:
            assert user_id == store.admin_user_id()
    assert CLOSED_HOTEL_CODE not in {
        pos_by_id[row["pos_id"]] for row in store.user_pos
    }
    for username in OPERATOR_POS:
        assert store.users[username]["role"] == "Operator"
        assert store.users[username]["password_hash"] == _hash("Operator123!")


def test_artrutx_is_inactive_without_active_payments() -> None:
    store, profiles, result, _ = _store_and_world()
    run_ingest(
        store,
        profiles,
        result.inventories,
        result.sales,
        result.movements,
        hash_password=_hash,
    )
    artrutx = store.pos[CLOSED_HOTEL_CODE]
    assert artrutx["is_active"] is False
    artrutx_id = artrutx["id"]
    assert not any(row["pos_id"] == artrutx_id for row in store.pos_payments)
    for key, row in store.inventories.items():
        if key[0] == CLOSED_HOTEL_CODE:
            assert row["is_active"] is False
    live_inactive = [
        row
        for key, row in store.inventories.items()
        if key[0] != CLOSED_HOTEL_CODE and not row["is_active"]
    ]
    assert live_inactive


def test_ingest_rolls_back_on_unmatched_sku() -> None:
    store, profiles, result, products_before = _store_and_world()
    ghost = list(result.inventories)
    ghost[0] = ghost[0].__class__(
        sku="SKU-MISSING",
        pos_code=ghost[0].pos_code,
        quantity=ghost[0].quantity,
        is_active=ghost[0].is_active,
        last_updated_at=ghost[0].last_updated_at,
    )
    with pytest.raises(IngestAborted, match="Unmatched"):
        run_ingest(store, profiles, ghost, result.sales, result.movements, hash_password=_hash)
    assert store.committed is False
    assert store.pos == {}
    assert store.users == {}
    assert store.sales == []
    assert store.snapshot_product_skus() == {
        sku: (row["name"], row["price"]) for sku, row in products_before.items()
    }


def test_operator_password_hash_verifies_with_bcrypt() -> None:
    from jbg_ai.data.world.ingest import hash_operator_password

    hashed = hash_operator_password("Operator123!")
    assert password_matches("Operator123!", hashed)
    assert hashed.startswith("$2a$12$")
    assert not password_matches("wrong", hashed)
