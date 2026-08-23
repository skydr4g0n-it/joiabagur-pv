"""Poisson world simulation. Natural keys only; never opens Postgres."""

from __future__ import annotations

import calendar
import json
import math
import random
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from jbg_ai.data.quality import name_stem
from jbg_ai.data.world.catalog import load_catalog_skus
from jbg_ai.data.world.constants import (
    ADMIN_USERNAME,
    CLOSED_HOTEL_CODE,
    CO_OCCURRENCE_FILENAME,
    GENERATED_DIR,
    GENERATOR_VERSION,
    INVENTORIES_FILENAME,
    META_FILENAME,
    MOVEMENT_IMPORT,
    MOVEMENT_RETURN,
    MOVEMENT_SALE,
    MOVEMENTS_FILENAME,
    OPERATOR_POS,
    PAYMENT_CODES,
    SALES_FILENAME,
    SUPPLY_SOURCE_CODE,
)
from jbg_ai.data.world.cooccurrence import derive_co_occurrence
from jbg_ai.data.world.profiles import load_profiles
from jbg_ai.data.world.records import (
    CatalogSku,
    InventoryRow,
    MovementRow,
    PosProfile,
    SaleRow,
    WorldProfiles,
    WorldResult,
)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    limit = math.exp(-lam)
    count = 0
    product = 1.0
    while product > limit:
        count += 1
        product *= rng.random()
    return count - 1


def _weighted_choice(rng: random.Random, items: list, weights: list[float]):
    total = sum(weights)
    if total <= 0:
        return rng.choice(items)
    pick = rng.random() * total
    cumulative = 0.0
    for item, weight in zip(items, weights, strict=True):
        cumulative += weight
        if pick <= cumulative:
            return item
    return items[-1]


def _collection_weight(profile: PosProfile, collection_name: str) -> float:
    if collection_name in profile.collection_weights:
        return max(profile.collection_weights[collection_name], 0.0)
    if not collection_name:
        return 0.15
    return 0.08


def _assign_inventory(
    rng: random.Random,
    profiles: WorldProfiles,
    catalog: list[CatalogSku],
) -> dict[str, dict[str, dict]]:
    """pos_code -> sku -> {qty, active, sku_obj}."""
    cells: dict[str, dict[str, dict]] = {}
    for pos in profiles.pos:
        n_take = max(1, min(len(catalog), round(pos.coverage * len(catalog))))
        if pos.code == SUPPLY_SOURCE_CODE:
            n_take = max(n_take, int(0.96 * len(catalog)))
        weights = [_collection_weight(pos, sku.collection_name) for sku in catalog]
        chosen: list[CatalogSku] = []
        remaining = list(catalog)
        remaining_w = list(weights)
        take = min(n_take, len(remaining))
        for _ in range(take):
            picked = _weighted_choice(rng, remaining, remaining_w)
            index = remaining.index(picked)
            chosen.append(picked)
            remaining.pop(index)
            remaining_w.pop(index)
        pos_cells: dict[str, dict] = {}
        for sku in chosen:
            qty = rng.randint(pos.qty_min, max(pos.qty_min, pos.qty_max))
            pos_cells[sku.sku] = {
                "qty": qty,
                "active": True,
                "sku": sku,
            }
        cells[pos.code] = pos_cells

    live_keys: list[tuple[str, str]] = []
    for pos in profiles.pos:
        if pos.code == CLOSED_HOTEL_CODE:
            continue
        for sku in cells[pos.code]:
            live_keys.append((pos.code, sku))
    idle_n = round(profiles.inactive_inventory_ratio_live_pos * len(live_keys))
    rng.shuffle(live_keys)
    for pos_code, sku in live_keys[:idle_n]:
        cells[pos_code][sku]["active"] = False
    return cells


def _username_for(pos_code: str) -> str:
    for username, assigned in OPERATOR_POS.items():
        if assigned == pos_code:
            return username
    return ADMIN_USERNAME


def _pos_is_open(pos: PosProfile, day: date) -> bool:
    if pos.closed_after is not None and day > pos.closed_after:
        return False
    return True


def simulate_world(
    profiles: WorldProfiles,
    catalog: list[CatalogSku],
    *,
    as_of: date | None = None,
    rng: random.Random | None = None,
) -> WorldResult:
    if rng is None:
        rng = random.Random(profiles.seed)
    hole_set = {item.casefold() for item in profiles.catalog_sku_holes}
    catalog = [item for item in catalog if item.sku.casefold() not in hole_set]
    horizon_end = as_of or date.today()
    horizon_start = add_months(horizon_end, -profiles.horizon_months)
    stamp_horizon_start = datetime.combine(horizon_start, time(8, 0), tzinfo=timezone.utc)
    cells = _assign_inventory(rng, profiles, catalog)
    sku_by_code = {item.sku: item for item in catalog}

    inventories_start: dict[tuple[str, str], int] = {}
    active_start: dict[tuple[str, str], bool] = {}
    for pos_code, by_sku in cells.items():
        for sku, cell in by_sku.items():
            inventories_start[(pos_code, sku)] = int(cell["qty"])
            active_start[(pos_code, sku)] = bool(cell["active"])

    movements: list[MovementRow] = []
    for (pos_code, sku), qty in inventories_start.items():
        occurred = stamp_horizon_start.isoformat().replace("+00:00", "Z")
        movements.append(
            MovementRow(
                sku=sku,
                pos_code=pos_code,
                username=ADMIN_USERNAME,
                movement_type=MOVEMENT_IMPORT,
                quantity_change=qty,
                quantity_before=0,
                quantity_after=qty,
                occurred_at=occurred,
                sale_key=None,
                reason="C10 initial stock",
            )
        )

    running = {key: qty for key, qty in inventories_start.items()}
    sales: list[SaleRow] = []
    sale_seq = 0
    bulk_seq = 0
    day = horizon_start
    while day <= horizon_end:
        for pos in profiles.pos:
            if not _pos_is_open(pos, day):
                continue
            lam = pos.lambda_retail * pos.seasonality[day.month]
            n_lines = poisson(rng, lam)
            if n_lines <= 0:
                continue
            available = [
                sku
                for sku, cell in cells[pos.code].items()
                if cell["active"] and running[(pos.code, sku)] > 0
            ]
            if not available:
                continue
            day_lines: list[tuple[str, int, datetime]] = []
            for _ in range(n_lines):
                live = [sku for sku in available if running[(pos.code, sku)] > 0]
                if not live:
                    break
                weights = [
                    _collection_weight(pos, sku_by_code[sku].collection_name) for sku in live
                ]
                sku = _weighted_choice(rng, live, weights)
                qty = 1
                if running[(pos.code, sku)] > 1 and rng.random() < 0.08:
                    qty = 2
                qty = min(qty, running[(pos.code, sku)])
                hour = rng.randint(10, 19)
                minute = rng.randint(0, 59)
                occurred = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
                day_lines.append((sku, qty, occurred))
                running[(pos.code, sku)] -= qty

            operations, bulk_seq = _pack_operations(
                rng, day_lines, sku_by_code, profiles.bulk_checkout_ratio, bulk_seq
            )
            username = _username_for(pos.code)
            for bulk_id, lines in operations:
                for sku, qty, occurred in lines:
                    sale_seq += 1
                    sale_key = f"s{sale_seq}"
                    iso = occurred.isoformat().replace("+00:00", "Z")
                    before = running[(pos.code, sku)] + qty
                    after = running[(pos.code, sku)]
                    sales.append(
                        SaleRow(
                            sale_key=sale_key,
                            sku=sku,
                            pos_code=pos.code,
                            username=username,
                            quantity=qty,
                            occurred_at=iso,
                            bulk_operation_id=bulk_id,
                            payment_method_code=rng.choice(PAYMENT_CODES),
                        )
                    )
                    movements.append(
                        MovementRow(
                            sku=sku,
                            pos_code=pos.code,
                            username=username,
                            movement_type=MOVEMENT_SALE,
                            quantity_change=-qty,
                            quantity_before=before,
                            quantity_after=after,
                            occurred_at=iso,
                            sale_key=sale_key,
                        )
                    )
                    if after < 0:
                        raise RuntimeError("negative stock emitted")
        day += timedelta(days=1)

    inventories: list[InventoryRow] = []
    for pos in profiles.pos:
        for sku, cell in cells[pos.code].items():
            is_active = bool(cell["active"])
            if pos.code == CLOSED_HOTEL_CODE:
                is_active = False
            last = stamp_horizon_start
            inventories.append(
                InventoryRow(
                    sku=sku,
                    pos_code=pos.code,
                    quantity=running[(pos.code, sku)],
                    is_active=is_active,
                    last_updated_at=last.isoformat().replace("+00:00", "Z"),
                )
            )

    # LastUpdatedAt should follow the last movement for that cell.
    last_move: dict[tuple[str, str], str] = {}
    for move in movements:
        last_move[(move.pos_code, move.sku)] = move.occurred_at
    inventories = [
        InventoryRow(
            sku=row.sku,
            pos_code=row.pos_code,
            quantity=row.quantity,
            is_active=row.is_active,
            last_updated_at=last_move.get((row.pos_code, row.sku), row.last_updated_at),
        )
        for row in inventories
    ]

    co_occurrence = derive_co_occurrence(sales)
    return WorldResult(
        inventories=inventories,
        sales=sales,
        movements=movements,
        co_occurrence=co_occurrence,
        generated_at=datetime.now(timezone.utc),
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        seed=profiles.seed,
        generator_version=profiles.generator_version,
    )


def _pack_operations(
    rng: random.Random,
    lines: list[tuple[str, int, datetime]],
    sku_by_code: dict[str, CatalogSku],
    bulk_ratio: float,
    bulk_seq: int,
) -> tuple[list[tuple[str | None, list[tuple[str, int, datetime]]]], int]:
    remaining = list(lines)
    rng.shuffle(remaining)
    operations: list[tuple[str | None, list[tuple[str, int, datetime]]]] = []
    while remaining:
        if len(remaining) >= 2 and rng.random() < bulk_ratio:
            size = 3 if len(remaining) >= 3 and rng.random() < 0.45 else 2
            picked = [remaining.pop(0)]
            while len(picked) < size and remaining:
                target_stems = {name_stem(sku_by_code[item[0]].name) for item in picked}
                target_cols = {sku_by_code[item[0]].collection_name for item in picked}
                distinct = next(
                    (
                        index
                        for index, item in enumerate(remaining)
                        if name_stem(sku_by_code[item[0]].name) not in target_stems
                        or sku_by_code[item[0]].collection_name not in target_cols
                    ),
                    0,
                )
                picked.append(remaining.pop(distinct))
            bulk_seq += 1
            operations.append((f"b{bulk_seq}", picked))
        else:
            operations.append((None, [remaining.pop(0)]))
    return operations, bulk_seq


def _write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")


def write_world(result: WorldResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "inventories": output_dir / INVENTORIES_FILENAME,
        "sales": output_dir / SALES_FILENAME,
        "movements": output_dir / MOVEMENTS_FILENAME,
        "co_occurrence": output_dir / CO_OCCURRENCE_FILENAME,
        "meta": output_dir / META_FILENAME,
    }
    _write_jsonl(paths["inventories"], result.inventories)
    _write_jsonl(paths["sales"], result.sales)
    _write_jsonl(paths["movements"], result.movements)
    _write_jsonl(paths["co_occurrence"], result.co_occurrence)
    meta = {
        "generator_version": result.generator_version,
        "seed": result.seed,
        "generated_at": result.generated_at.isoformat().replace("+00:00", "Z"),
        "horizon_start": result.horizon_start.isoformat(),
        "horizon_end": result.horizon_end.isoformat(),
        "pos_count": len({row.pos_code for row in result.inventories}),
        "inventory_count": len(result.inventories),
        "sales_count": len(result.sales),
        "movement_count": len(result.movements),
        "co_occurrence_pairs": len(result.co_occurrence),
        "import_movements": sum(1 for row in result.movements if row.movement_type == MOVEMENT_IMPORT),
        "sale_movements": sum(1 for row in result.movements if row.movement_type == MOVEMENT_SALE),
        "return_movements": sum(1 for row in result.movements if row.movement_type == MOVEMENT_RETURN),
    }
    paths["meta"].write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return paths


def run_simulate(
    *,
    profiles_path: Path,
    output_dir: Path | None = None,
    catalog_paths: list[Path] | None = None,
    as_of: date | None = None,
) -> WorldResult:
    profiles = load_profiles(profiles_path)
    catalog = load_catalog_skus(catalog_paths, holes=profiles.catalog_sku_holes)
    result = simulate_world(profiles, catalog, as_of=as_of)
    write_world(result, output_dir or GENERATED_DIR)
    return result
