from __future__ import annotations

import json

from catalog_pipeline.constants import DEFAULT_SEED, FAMILY_JSON_KEYS, GENERATOR_VERSION
from catalog_pipeline.generate import generate_corpus
from catalog_pipeline.schema import parse_record, read_jsonl, read_sidecar
from catalog_pipeline.validate import assert_sidecar_keys, validate_records


def test_jsonl_lines_parse_with_real_origin_and_unique_skus(fixture_csv, tmp_path):
    jsonl_path, meta_path, records = generate_corpus(fixture_csv, tmp_path, seed=DEFAULT_SEED)
    loaded = read_jsonl(jsonl_path)
    assert len(loaded) == len(records)
    validate_records(loaded)
    assert all(record.data_origin == "real" for record in loaded)
    assert len({record.sku for record in loaded}) == len(loaded)
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_record(line)
        assert "product_id" not in parsed.to_json_dict()

    sidecar = read_sidecar(meta_path)
    assert_sidecar_keys(sidecar)
    assert sidecar["generator_version"] == GENERATOR_VERSION
    assert sidecar["seed"] == DEFAULT_SEED
    assert sidecar["model"] is None
    assert "rich" in sidecar["ratios_by_tier"]
    assert "original" in sidecar["ratios_by_tier"]
    assert "empty" not in sidecar["ratios_by_tier"]
    assert "ai_assisted" in sidecar["counts_by_text_provenance"]
    assert "group_count" in sidecar["grouping"]


def test_jsonl_omits_family_seed_fields(fixture_csv, tmp_path):
    jsonl_path, _, _ = generate_corpus(fixture_csv, tmp_path, seed=DEFAULT_SEED)
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        for key in FAMILY_JSON_KEYS:
            assert key not in payload
        serialized = json.dumps(parse_record(line).to_json_dict())
        for key in FAMILY_JSON_KEYS:
            assert key not in serialized
