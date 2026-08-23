"""Sidecar keys for C06b traceability. Delivered by C06b."""

from __future__ import annotations

from datetime import datetime, timezone

from jbg_ai.data.constants import GENERATOR_VERSION, PROMPT_VERSION
from jbg_ai.data.io import assert_sidecar_keys, build_sidecar
from jbg_ai.data.records import SyntheticRecord


def test_sidecar_contains_required_traceability_keys() -> None:
    records = [
        SyntheticRecord(
            sku="SKU437",
            name="Anillo",
            description="Plata.",
            price="10.00",
            collection_name="Fuego",
            text_quality_tier="rich",
        )
    ]
    sidecar = build_sidecar(
        records,
        seed="20260822",
        model="openai:gpt-4o-mini",
        generated_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
        collection_audiences={"Fuego": "hotel"},
    )
    assert_sidecar_keys(sidecar)
    assert sidecar["generator_version"] == GENERATOR_VERSION
    assert sidecar["prompt_version"] == PROMPT_VERSION
    assert sidecar["seed"] == "20260822"
    assert sidecar["model"] == "openai:gpt-4o-mini"
    assert sidecar["product_count"] == 1
    assert "rich" in sidecar["counts_by_tier"]
    assert "sparse" in sidecar["ratios_by_tier"]
    assert "short" in sidecar["ratios_by_tier"]
    assert sidecar["target_hybrid_total"] == 1200
    assert sidecar["collection_audiences"]["Fuego"] == "hotel"
    assert sidecar["empty_short_count"] == 0
    assert sidecar["empty_short_ratio_of_short"] == 0.0
