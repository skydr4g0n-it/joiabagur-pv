"""Natural-key records for the world simulator. No product/POS UUIDs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class OperatorProfile:
    username: str
    first_name: str
    last_name: str
    password: str
    pos_code: str


@dataclass(frozen=True)
class PosProfile:
    code: str
    name: str
    island: str
    address: str
    is_supply_source: bool
    is_active: bool
    allow_manual_price_edit: bool
    lambda_retail: float
    coverage: float
    qty_min: int
    qty_max: int
    seasonality: dict[int, float]
    collection_weights: dict[str, float]
    operator: str | None
    closed_after: date | None


@dataclass(frozen=True)
class WorldProfiles:
    generator_version: str
    seed: str
    horizon_months: int
    phone: str
    inactive_inventory_ratio_live_pos: float
    bulk_checkout_ratio: float
    catalog_sku_holes: tuple[str, ...]
    operators: tuple[OperatorProfile, ...]
    pos: tuple[PosProfile, ...]


@dataclass(frozen=True)
class CatalogSku:
    sku: str
    name: str
    collection_name: str


@dataclass(frozen=True)
class InventoryRow:
    sku: str
    pos_code: str
    quantity: int
    is_active: bool
    last_updated_at: str


@dataclass(frozen=True)
class SaleRow:
    sale_key: str
    sku: str
    pos_code: str
    username: str
    quantity: int
    occurred_at: str
    bulk_operation_id: str | None
    payment_method_code: str
    price_was_overridden: bool = False
    notes: str | None = None
    search_event_id: str | None = None


@dataclass(frozen=True)
class MovementRow:
    sku: str
    pos_code: str
    username: str
    movement_type: int
    quantity_change: int
    quantity_before: int
    quantity_after: int
    occurred_at: str
    sale_key: str | None
    reason: str | None = None


@dataclass(frozen=True)
class CoOccurrenceRow:
    product_sku_a: str
    product_sku_b: str
    co_sales_count: int
    last_seen_at: str


@dataclass(frozen=True)
class WorldResult:
    inventories: list[InventoryRow]
    sales: list[SaleRow]
    movements: list[MovementRow]
    co_occurrence: list[CoOccurrenceRow]
    generated_at: datetime
    horizon_start: date
    horizon_end: date
    seed: str
    generator_version: str
