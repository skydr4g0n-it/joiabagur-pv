"""Shared builders for C10 world tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import yaml

from jbg_ai.data.world.constants import PROFILES_PATH
from jbg_ai.data.world.profiles import parse_profiles
from jbg_ai.data.world.records import CatalogSku, WorldProfiles

AS_OF = date(2026, 8, 23)
CLOSED_AFTER = date(2025, 9, 30)

COLLECTIONS = (
    "El Jaleo",
    "Fuego",
    "Cielo estrellado",
    "La Pomada",
    "Tramontana",
    "Caliza",
    "Umbra",
    "Filigrana",
    "Marea viva",
    "Coral negro",
)


def profiles_payload() -> dict:
    return yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))


def make_profiles(*, qty_min: int = 80, qty_max: int = 160) -> WorldProfiles:
    payload = deepcopy(profiles_payload())
    for pos in payload["pos"]:
        pos["qty_min"] = qty_min
        pos["qty_max"] = qty_max
    return parse_profiles(payload)


def tiny_catalog(*, include_holes: bool = True) -> list[CatalogSku]:
    rows: list[CatalogSku] = []
    for index, collection in enumerate(COLLECTIONS, start=1):
        rows.append(
            CatalogSku(
                sku=f"SKU{index:02d}",
                name=f"Pieza {collection} S",
                collection_name=collection,
            )
        )
        rows.append(
            CatalogSku(
                sku=f"SKU{index + 20:02d}",
                name=f"Pieza {collection} M",
                collection_name=collection,
            )
        )
    if include_holes:
        rows.extend(
            [
                CatalogSku(sku="SKU135", name="Hueco 135", collection_name="El Jaleo"),
                CatalogSku(sku="SKU400", name="Hueco 400", collection_name="Fuego"),
                CatalogSku(sku="SKU418", name="Hueco 418", collection_name="Filigrana"),
            ]
        )
    return rows
