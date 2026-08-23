"""Pipeline assembly: vocabs, stone residual, null copy fields. Delivered by C09."""

from __future__ import annotations

from jbg_ai.api.schemas.enrich import EnrichProductInput
from jbg_ai.enrichment.constants import CONFIDENCE_ABSENT, CONFIDENCE_NO_SPAN, CONFIDENCE_SPAN
from jbg_ai.enrichment.pipeline import assemble_profile
from jbg_ai.enrichment.schema import EnrichmentExtraction
from jbg_ai.enrichment.size import extract_size
from jbg_ai.enrichment.vocab import load_vocabularies


def _assemble(
    *,
    name: str | None,
    description: str | None,
    extraction: EnrichmentExtraction,
    sku: str = "SKU-1",
):
    product = EnrichProductInput(
        product_id="P-1", sku=sku, name=name, description=description
    )
    return assemble_profile(
        product,
        extraction,
        size_hit=extract_size(name, description),
        vocabs=load_vocabularies(),
    )


def test_extracts_multiple_materials_from_description() -> None:
    profile = _assemble(
        name="Pulsera costa",
        description="Plata de ley con baño de oro en los cierres.",
        extraction=EnrichmentExtraction(materials=["plata de ley", "baño de oro"]),
    )

    assert profile.materials.value == ["plata", "baño de oro"]
    assert profile.materials.source == "inferred"
    assert "mithril" not in profile.materials.value


def test_rejects_value_outside_closed_vocabulary() -> None:
    profile = _assemble(
        name="Anillo de mithril",
        description="Forjado en mithril legendario.",
        extraction=EnrichmentExtraction(materials=["mithril"]),
    )

    assert profile.materials.value == []
    assert any("mithril" in warning for warning in profile.warnings)


def test_empty_materials_flags_review_not_default_value() -> None:
    profile = _assemble(
        name="Colgante relieve",
        description="Brillo suave, sin metal nombrado.",
        extraction=EnrichmentExtraction(materials=[]),
    )

    assert profile.materials.value == []
    assert profile.materials.confidence == CONFIDENCE_ABSENT
    assert profile.materials.source == "inferred"
    assert "plata" not in profile.materials.value


def test_generic_stone_when_gem_mentioned_without_type() -> None:
    profile = _assemble(
        name="Anillo con piedra preciosa",
        description="Lleva una gema engastada, sin nombrar cuál.",
        extraction=EnrichmentExtraction(materials=["plata"], stone_type=None, gem_mentioned=True),
    )

    assert profile.stone_type is not None
    assert profile.stone_type.value == "piedra"
    assert profile.materials.value == ["plata"]


def test_specific_stone_does_not_also_write_generic() -> None:
    profile = _assemble(
        name="Colgante de ámbar",
        description="Ámbar natural sobre plata.",
        extraction=EnrichmentExtraction(materials=["plata"], stone_type="ámbar"),
    )

    assert profile.stone_type is not None
    assert profile.stone_type.value == "ambar"
    assert profile.stone_type.value != "piedra"
    assert "ambar" not in profile.materials.value
    assert "ámbar" not in profile.materials.value


def test_stone_outside_closed_list_becomes_residual_or_null() -> None:
    residual = _assemble(
        name="Anillo con gema",
        description="Engaste de un mithril imposible.",
        extraction=EnrichmentExtraction(stone_type="mithril", gem_mentioned=True),
    )
    absent = _assemble(
        name="Colgante con relieve",
        description="Solo brillo, sin tipo nombrado.",
        extraction=EnrichmentExtraction(stone_type="mithril", gem_mentioned=False),
    )

    assert residual.stone_type is not None
    assert residual.stone_type.value == "piedra"
    assert "mithril" not in residual.warnings or any("mithril" in w for w in residual.warnings)
    assert absent.stone_type is None


def test_title_description_and_family_are_null() -> None:
    profile = _assemble(
        name="Anillo mini conchiglie",
        description="Plata de ley.",
        extraction=EnrichmentExtraction(piece_type="anillo", materials=["plata"]),
    )

    assert profile.title is None
    assert profile.description is None
    assert profile.family_id is None
    assert profile.variant_label is None


def test_piece_type_stores_hypernym_not_hyponym() -> None:
    gargantilla = _assemble(
        name="Gargantilla Horizonte Marfil",
        description=None,
        extraction=EnrichmentExtraction(piece_type="gargantilla", style_tags=["gargantilla"]),
    )
    brazalete = _assemble(
        name="Brazalete suspiro",
        description=None,
        extraction=EnrichmentExtraction(piece_type="brazalete"),
    )
    anillo = _assemble(
        name="Anillo mini conchiglie",
        description=None,
        extraction=EnrichmentExtraction(piece_type="anillo"),
    )

    assert gargantilla.piece_type is not None
    assert gargantilla.piece_type.value == "collar"
    assert "gargantilla" not in gargantilla.style_tags.value
    assert brazalete.piece_type is not None
    assert brazalete.piece_type.value == "pulsera"
    assert anillo.piece_type is not None
    assert anillo.piece_type.value == "anillo"


def test_confidence_follows_evidence_span() -> None:
    profile = _assemble(
        name="Pulsera",
        description="Plata pulida para un regalo que no se nombra como ocasión en tags.",
        extraction=EnrichmentExtraction(
            materials=["plata"],
            occasion_tags=["fiesta"],
        ),
    )

    assert profile.materials.confidence == CONFIDENCE_SPAN
    assert profile.occasion_tags.confidence == CONFIDENCE_NO_SPAN
    assert profile.materials.confidence != 0.99


def test_mixed_list_uses_least_evidenced_member_confidence() -> None:
    profile = _assemble(
        name="Pulsera",
        description="Plata pulida, sin otro metal nombrado.",
        extraction=EnrichmentExtraction(materials=["plata", "oro"]),
    )

    assert profile.materials.value == ["plata", "oro"]
    assert profile.materials.confidence == CONFIDENCE_NO_SPAN
    assert profile.materials.confidence != CONFIDENCE_SPAN
