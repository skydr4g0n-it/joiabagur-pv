"""Simulate invariants: stock, holes, dates, seasonality, mix."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime
from unittest.mock import patch

from jbg_ai.data.world.constants import (
    CLOSED_HOTEL_CODE,
    MOVEMENT_RETURN,
    MOVEMENT_SALE,
    SUPPLY_SOURCE_CODE,
)
from jbg_ai.data.world.simulate import simulate_world
from tests.data.world.helpers import AS_OF, CLOSED_AFTER, make_profiles, tiny_catalog


def _simulate(**kwargs):
    profiles = make_profiles()
    catalog = tiny_catalog()
    return simulate_world(profiles, catalog, as_of=AS_OF, rng=random.Random("20260823"), **kwargs)


def test_known_catalog_holes_are_not_sold() -> None:
    result = _simulate()
    holes = {"SKU135", "SKU400", "SKU418"}
    sold = {row.sku for row in result.sales}
    stocked = {row.sku for row in result.inventories}
    assert holes.isdisjoint(sold)
    assert holes.isdisjoint(stocked)


def test_simulate_does_not_require_postgres() -> None:
    with patch("psycopg.connect", side_effect=AssertionError("Postgres must not open")):
        result = _simulate()
    assert result.inventories
    blob = " ".join(
        f"{row.sku} {row.pos_code} {row.username}"
        for row in result.sales + result.movements
    )
    for row in result.inventories:
        blob += f" {row.sku} {row.pos_code}"
    assert "SKU135" not in {row.sku for row in result.inventories}
    for token in blob.split():
        if len(token) == 36 and token.count("-") == 4:
            raise AssertionError(f"UUID leaked in output: {token}")


def test_no_sale_without_stock_at_that_pos() -> None:
    result = _simulate()
    running: dict[tuple[str, str], int] = {}
    active: dict[tuple[str, str], bool] = {}
    for move in result.movements:
        key = (move.pos_code, move.sku)
        if move.movement_type != MOVEMENT_SALE:
            running[key] = move.quantity_after
            continue
        assert key in running
        assert move.quantity_change < 0
        assert move.quantity_after == move.quantity_before + move.quantity_change
        assert move.quantity_after >= 0
        running[key] = move.quantity_after
    assert all(move.movement_type != MOVEMENT_RETURN for move in result.movements)
    final = {(row.pos_code, row.sku): row.quantity for row in result.inventories}
    for key, qty in running.items():
        if key in final:
            assert final[key] == qty
    _ = active


def test_inventory_movements_reconcile_with_final_stock() -> None:
    result = _simulate()
    last_after: dict[tuple[str, str], int] = {}
    for move in result.movements:
        last_after[(move.pos_code, move.sku)] = move.quantity_after
    for row in result.inventories:
        assert last_after[(row.pos_code, row.sku)] == row.quantity


def test_sale_and_movement_share_date_and_user() -> None:
    result = _simulate()
    sales = {row.sale_key: row for row in result.sales}
    sale_moves = [row for row in result.movements if row.movement_type == MOVEMENT_SALE]
    assert len(sale_moves) == len(result.sales)
    for move in sale_moves:
        sale = sales[move.sale_key]
        assert move.occurred_at == sale.occurred_at
        assert move.username == sale.username
        stamp = datetime.fromisoformat(sale.occurred_at.replace("Z", "+00:00"))
        assert stamp.tzinfo is not None
        assert sale.price_was_overridden is False
        assert sale.notes is None
        assert sale.search_event_id is None


def test_seasonality_peaks_match_pos_profile() -> None:
    result = _simulate()
    by_pos_month: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    after_close = []
    for sale in result.sales:
        stamp = datetime.fromisoformat(sale.occurred_at.replace("Z", "+00:00"))
        by_pos_month[sale.pos_code][stamp.month] += sale.quantity
        if sale.pos_code == CLOSED_HOTEL_CODE and stamp.date() > CLOSED_AFTER:
            after_close.append(sale)
    assert after_close == []

    def summer(pos: str) -> int:
        return sum(by_pos_month[pos][month] for month in (6, 7, 8, 9))

    def winter(pos: str) -> int:
        return sum(by_pos_month[pos][month] for month in (1, 2, 11, 12))

    for hotel in ("HT-GALDANA", "HT-SONBOU", "FORNELLS"):
        if summer(hotel) + winter(hotel) == 0:
            continue
        assert summer(hotel) > winter(hotel)

    ciu = sum(by_pos_month["CIU-CENTRE"].values())
    fornells = sum(by_pos_month["FORNELLS"].values())
    taller = sum(by_pos_month[SUPPLY_SOURCE_CODE].values())
    assert ciu > fornells
    assert taller <= max(ciu * 0.05, 2)


def test_airport_mix_is_not_atelier() -> None:
    profiles = make_profiles(qty_min=4000, qty_max=5000)
    catalog = tiny_catalog()
    result = simulate_world(profiles, catalog, as_of=AS_OF, rng=random.Random("20260823"))
    catalog_map = {item.sku: item for item in tiny_catalog()}

    def share(pos: str, names: set[str]) -> float:
        rows = [sale for sale in result.sales if sale.pos_code == pos]
        if not rows:
            return 0.0
        hit = sum(1 for sale in rows if catalog_map[sale.sku].collection_name in names)
        return hit / len(rows)

    airport_tourist = share("MAO-AIR", {"El Jaleo", "Marea viva"})
    airport_atelier = share("MAO-AIR", {"Cielo estrellado", "Filigrana"})
    ciu_atelier = share("CIU-CENTRE", {"Cielo estrellado", "Filigrana"})
    assert airport_tourist > airport_atelier
    assert ciu_atelier >= airport_atelier


def test_bulk_ratio_is_about_fifteen_percent() -> None:
    result = _simulate()
    ops: dict[str | None, int] = defaultdict(int)
    singles = 0
    multi = 0
    grouped: dict[str, int] = defaultdict(int)
    for sale in result.sales:
        if sale.bulk_operation_id:
            grouped[sale.bulk_operation_id] += 1
        else:
            singles += 1
    multi = sum(1 for count in grouped.values() if count >= 2)
    total_ops = singles + len(grouped)
    if total_ops == 0:
        return
    ratio = multi / total_ops
    assert 0.05 <= ratio <= 0.35
    _ = ops


def test_cartesian_inventory_is_not_emitted() -> None:
    result = _simulate()
    catalog_n = len([row for row in tiny_catalog() if row.sku not in {"SKU135", "SKU400", "SKU418"}])
    assert len(result.inventories) < catalog_n * 12
    assert len({row.pos_code for row in result.inventories}) == 12
