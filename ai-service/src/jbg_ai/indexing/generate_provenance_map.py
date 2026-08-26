"""Generate `sku_provenance.json` from the committed JSONL corpus. Run once.

    uv run --system-certs python -m jbg_ai.indexing.generate_provenance_map

Runtime loads only the JSON under `src/`; it never reads `data/catalog/`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jbg_ai.data.paths import REAL_JSONL, SYNTHETIC_DIR
from jbg_ai.data.constants import JSONL_FILENAME

PROVENANCE_MAP_PATH = Path(__file__).resolve().parent / "sku_provenance.json"

ALLOWED_ORIGINS = frozenset({"real", "synthetic"})
ALLOWED_PROVENANCE = frozenset({"merchant", "ai_assisted", "synthetic"})


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def build_provenance_map(real_path: Path, synthetic_path: Path) -> dict[str, dict[str, str]]:
    """SKU → {data_origin, text_provenance}. Overlaps and missing fields fail."""
    mapping: dict[str, dict[str, str]] = {}
    for path in (real_path, synthetic_path):
        for record in _read_jsonl(path):
            sku = str(record["sku"]).strip()
            origin = str(record["data_origin"]).strip()
            provenance = str(record["text_provenance"]).strip()
            if origin not in ALLOWED_ORIGINS:
                raise ValueError(f"{path}: SKU {sku} has data_origin={origin!r}")
            if provenance not in ALLOWED_PROVENANCE:
                raise ValueError(f"{path}: SKU {sku} has text_provenance={provenance!r}")
            if sku in mapping:
                raise ValueError(f"SKU {sku} appears in both JSONL files")
            mapping[sku] = {"data_origin": origin, "text_provenance": provenance}
    return mapping


def main(argv: list[str] | None = None) -> int:
    _ = argv
    synthetic_path = SYNTHETIC_DIR / JSONL_FILENAME
    mapping = build_provenance_map(REAL_JSONL, synthetic_path)
    PROVENANCE_MAP_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"wrote {len(mapping)} keys to {PROVENANCE_MAP_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
