"""Read catalog JSONL for mix bias. Simulate never opens Postgres."""

from __future__ import annotations

import json
from pathlib import Path

from jbg_ai.data.paths import REAL_JSONL, SYNTHETIC_DIR
from jbg_ai.data.world.records import CatalogSku

SYNTHETIC_JSONL = SYNTHETIC_DIR / "catalog-synthetic.jsonl"


def default_catalog_paths() -> tuple[Path, Path]:
    return REAL_JSONL, SYNTHETIC_JSONL


def load_catalog_skus(
    paths: list[Path] | None = None,
    *,
    holes: tuple[str, ...] = (),
) -> list[CatalogSku]:
    hole_set = {item.casefold() for item in holes}
    seen: set[str] = set()
    rows: list[CatalogSku] = []
    for path in paths or list(default_catalog_paths()):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                payload = json.loads(text)
                sku = str(payload.get("sku") or "").strip()
                if not sku or sku.casefold() in hole_set or sku in seen:
                    continue
                seen.add(sku)
                rows.append(
                    CatalogSku(
                        sku=sku,
                        name=str(payload.get("name") or "").strip(),
                        collection_name=str(payload.get("collection_name") or "").strip(),
                    )
                )
    return rows
