"""Load the committed SKU provenance map. Runtime never reads `data/catalog/`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict

from jbg_ai.indexing.sync_errors import ProvenanceMapError

PROVENANCE_MAP_PATH = Path(__file__).resolve().parent / "sku_provenance.json"

DataOrigin = Literal["real", "synthetic"]
TextProvenance = Literal["merchant", "ai_assisted", "synthetic"]


class ProvenanceEntry(TypedDict):
    data_origin: DataOrigin
    text_provenance: TextProvenance


def load_provenance_map(path: Path | None = None) -> dict[str, ProvenanceEntry]:
    """Return SKU → origin/provenance. Missing or unreadable → ProvenanceMapError."""
    target = path if path is not None else PROVENANCE_MAP_PATH
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProvenanceMapError(
            "sku_provenance.json is missing; refusing catalog sync"
        ) from exc
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProvenanceMapError(
            "sku_provenance.json is unreadable; refusing catalog sync"
        ) from exc
    if not isinstance(raw, dict) or not raw:
        raise ProvenanceMapError(
            "sku_provenance.json is missing or unreadable; refusing catalog sync"
        )
    mapping: dict[str, ProvenanceEntry] = {}
    for sku, entry in raw.items():
        if not isinstance(sku, str) or not isinstance(entry, dict):
            raise ProvenanceMapError("sku_provenance.json is unreadable; refusing catalog sync")
        origin = entry.get("data_origin")
        provenance = entry.get("text_provenance")
        if origin not in ("real", "synthetic"):
            raise ProvenanceMapError("sku_provenance.json is unreadable; refusing catalog sync")
        if provenance not in ("merchant", "ai_assisted", "synthetic"):
            raise ProvenanceMapError("sku_provenance.json is unreadable; refusing catalog sync")
        mapping[sku] = {
            "data_origin": origin,
            "text_provenance": provenance,
        }
    return mapping
