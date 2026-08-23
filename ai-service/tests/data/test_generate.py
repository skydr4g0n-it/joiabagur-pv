"""Generate orchestration with a fake LLM. Delivered by C06b."""

from __future__ import annotations

from pathlib import Path

import pytest

from jbg_ai.data.constants import PROMPT_VERSION
from jbg_ai.data.errors import ValidationError
from jbg_ai.data.generate import generate_corpus
from jbg_ai.data.io import read_jsonl, read_sidecar
from jbg_ai.data.paths import PROMPT_MARKDOWN, REAL_JSONL
from support.fake_llm import FakeCatalogLlm


def test_prompt_file_exists_and_is_versioned() -> None:
    text = PROMPT_MARKDOWN.read_text(encoding="utf-8")
    assert "nombre de diseño" in text.casefold() or "Nombre de diseño" in text
    assert "público" in text.casefold()
    assert "35" in text
    assert "assist.py" in text or "El anillo con X" in text
    assert PROMPT_VERSION == "catalog-synth/v3"
    assert "text_quality_tier" in text
    assert "jaleo de cavalls" in text.casefold()
    assert "sin talla" in text.casefold()


def test_generate_writes_jsonl_and_sidecar_with_fake(tmp_path: Path) -> None:
    llm = FakeCatalogLlm()
    jsonl_path, meta_path, records = generate_corpus(
        output_dir=tmp_path,
        llm=llm,
        real_jsonl=REAL_JSONL,
        product_count=12,
        seed="20260822",
    )
    assert len(records) == 12
    assert jsonl_path.exists()
    sidecar = read_sidecar(meta_path)
    assert sidecar["prompt_version"] == PROMPT_VERSION
    assert sidecar["model"] == "fake:c06b"
    assert sidecar["seed"] == "20260822"
    loaded = read_jsonl(jsonl_path)
    assert loaded[0].sku == "SKU440"
    assert all(item.data_origin == "synthetic" for item in loaded)
    for key in ("variant_group_key", "variant_label", "family_seed", "materials", "product_id"):
        assert key not in loaded[0].to_json_dict()
    named = {item.collection_name for item in loaded if item.collection_name.strip()}
    assert 8 <= len(named) <= 12
    assert llm.calls


def test_generate_applies_uneven_collections_and_families(tmp_path: Path) -> None:
    llm = FakeCatalogLlm()
    _, _, records = generate_corpus(
        output_dir=tmp_path,
        llm=llm,
        real_jsonl=REAL_JSONL,
        product_count=80,
        seed="20260822",
    )
    assert len(records) == 80
    named_counts = {}
    unassigned = 0
    for item in records:
        if not item.collection_name.strip():
            unassigned += 1
            continue
        named_counts[item.collection_name] = named_counts.get(item.collection_name, 0) + 1
    assert 8 <= len(named_counts) <= 12
    assert abs(100.0 * unassigned / 80 - 20.0) <= 5.0
    assert len(set(named_counts.values())) == len(named_counts)


def test_generate_does_not_overwrite_without_flag(tmp_path: Path) -> None:
    first = FakeCatalogLlm()
    jsonl_path, _, first_records = generate_corpus(
        output_dir=tmp_path,
        llm=first,
        real_jsonl=REAL_JSONL,
        product_count=12,
    )
    original = jsonl_path.read_text(encoding="utf-8")
    second = FakeCatalogLlm()
    _, _, again = generate_corpus(
        output_dir=tmp_path,
        llm=second,
        real_jsonl=REAL_JSONL,
        product_count=12,
        regenerate_text=False,
    )
    assert jsonl_path.read_text(encoding="utf-8") == original
    assert [item.sku for item in again] == [item.sku for item in first_records]
    assert second.calls == []


def test_generate_rejects_overlong_description(tmp_path: Path) -> None:
    llm = FakeCatalogLlm(overlong_on=("El Jaleo", 0))
    with pytest.raises(ValidationError, match="1000"):
        generate_corpus(
            output_dir=tmp_path,
            llm=llm,
            real_jsonl=REAL_JSONL,
            product_count=12,
        )


def test_generate_rejects_price_at_or_above_50000(tmp_path: Path) -> None:
    llm = FakeCatalogLlm(expensive_on=("El Jaleo", 0))
    with pytest.raises(ValidationError, match="50000"):
        generate_corpus(
            output_dir=tmp_path,
            llm=llm,
            real_jsonl=REAL_JSONL,
            product_count=12,
        )
