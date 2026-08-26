"""Invariant: committed sku_provenance.json matches the JSONL corpus union."""

from __future__ import annotations

import json

from jbg_ai.data.constants import JSONL_FILENAME
from jbg_ai.data.paths import REAL_JSONL, SYNTHETIC_DIR
from jbg_ai.indexing.generate_provenance_map import build_provenance_map
from jbg_ai.indexing.provenance import PROVENANCE_MAP_PATH, load_provenance_map
from support.paths import REPO_ROOT


def test_provenance_map_matches_jsonl_union() -> None:
    synthetic = SYNTHETIC_DIR / JSONL_FILENAME
    expected = build_provenance_map(REAL_JSONL, synthetic)
    committed = json.loads(PROVENANCE_MAP_PATH.read_text(encoding="utf-8"))
    loaded = load_provenance_map()

    assert len(committed) == 1200
    assert set(committed) == set(expected)
    assert committed == expected
    assert loaded == expected

    origins = [entry["data_origin"] for entry in committed.values()]
    provenances = [entry["text_provenance"] for entry in committed.values()]
    assert origins.count("real") == 436
    assert origins.count("synthetic") == 764
    assert provenances.count("ai_assisted") == 387
    assert provenances.count("merchant") == 49
    assert provenances.count("synthetic") == 764

    jsonl_skus: list[str] = []
    for path in (REAL_JSONL, synthetic):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                jsonl_skus.append(json.loads(line)["sku"])
    assert len(jsonl_skus) == len(set(jsonl_skus))
    assert set(jsonl_skus) == set(committed)

    data_dir = REPO_ROOT / "data" / "catalog"
    map_source = PROVENANCE_MAP_PATH.read_text(encoding="utf-8")
    assert "data/catalog" not in map_source
    assert data_dir.exists()
