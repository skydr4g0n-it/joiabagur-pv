from __future__ import annotations

from decimal import Decimal

from catalog_pipeline.identity import identities_match
from catalog_pipeline.models import EnrichedRecord, FamilySeed, SourceRow


def _record(**overrides) -> EnrichedRecord:
    payload = dict(
        sku="RING-S",
        name="Anillo corazón oro S",
        description="texto asistido",
        price="65.00",
        collection_name="Colección Fixture",
        data_origin="real",
        text_provenance="ai_assisted",
        text_quality_tier="rich",
        variant_group_key="anillo-corazon",
        variant_label="oro s",
        family_seed=FamilySeed(group_key="anillo-corazon", member_skus=("RING-L", "RING-M", "RING-S")),
    )
    payload.update(overrides)
    return EnrichedRecord(**payload)


def test_sku_price_name_and_collection_are_never_modified(fixture_rows, fixture_records):
    by_sku = {row.sku: row for row in fixture_rows}
    for record in fixture_records:
        source = by_sku[record.sku]
        assert identities_match(source, record)
        assert record.description != source.description or record.text_quality_tier == "original"


def test_identity_allows_description_to_differ():
    source = SourceRow(
        sku="RING-S",
        name="Anillo corazón oro S",
        description="plata de ley",
        price=Decimal("65.00"),
        collection_name="Colección Fixture",
    )
    assert identities_match(source, _record(description="otra cosa"))
    assert not identities_match(source, _record(name="Otro nombre"))
    assert not identities_match(source, _record(price="66.00"))
    assert not identities_match(source, _record(collection_name="Otra"))
    assert not identities_match(source, _record(sku="OTHER"))
