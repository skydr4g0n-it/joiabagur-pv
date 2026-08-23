"""Size regex: Name then Description, never SKU. Delivered by C09."""

from __future__ import annotations

from jbg_ai.api.schemas.enrich import EnrichProductInput
from jbg_ai.enrichment.schema import EnrichmentExtraction
from jbg_ai.enrichment.size import extract_size
from jbg_ai.enrichment.pipeline import assemble_profile
from jbg_ai.enrichment.vocab import load_vocabularies


def _profile(name: str | None, description: str | None, sku: str = "SKU06") -> object:
    product = EnrichProductInput(
        product_id="P-1", sku=sku, name=name, description=description
    )
    return assemble_profile(
        product,
        EnrichmentExtraction(),
        size_hit=extract_size(name, description),
        vocabs=load_vocabularies(),
    )


def test_size_regex_marks_field_source_as_rule() -> None:
    profile = _profile("Colgante erizo de mar S", None)

    assert profile.size_label is not None
    assert profile.size_label.value == "S"
    assert profile.size_label.source == "rule"
    assert profile.size_label.confidence == 1.0


def test_size_prefers_name_over_description() -> None:
    profile = _profile("Pulsera nudo M", "Talla L, caída larga")

    assert profile.size_label is not None
    assert profile.size_label.value == "M"
    assert profile.size_label.source == "rule"


def test_size_falls_back_to_description_when_name_has_none() -> None:
    profile = _profile("Pulsera nudo", "Disponible en talla L")

    assert profile.size_label is not None
    assert profile.size_label.value == "L"
    assert profile.size_label.source == "rule"


def test_size_is_never_read_from_sku() -> None:
    profile = _profile("Colgante erizo de mar", None, sku="SKU06-S")

    assert profile.size_label is None
    hit = extract_size("Colgante erizo de mar", None)
    assert hit is None
