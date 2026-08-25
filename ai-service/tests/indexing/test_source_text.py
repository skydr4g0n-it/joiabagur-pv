"""Canonical source-text/v1 renderer and hash. Delivered by C11."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from jbg_ai.indexing import SOURCE_TEXT_VERSION, ProductSourceText, build_source_text, hash_source_text


def _base(**overrides: object) -> ProductSourceText:
    payload: dict[str, object] = {
        "sku": "SKU01",
        "name": "Anillo erizo de mar",
        "description": "Anillo de plata con erizo",
        "collection_name": "Mar",
        "piece_type": "anillo",
        "materials": ["plata"],
        "stone_type": "ambar",
        "size_label": "S",
        "family_name": "Anillo erizo de mar",
        "variant_label": "S",
        "color_tags": ["beige"],
        "style_tags": ["boho"],
        "occasion_tags": ["diario"],
    }
    payload.update(overrides)
    return ProductSourceText.model_validate(payload)


def test_source_text_version_constant() -> None:
    assert SOURCE_TEXT_VERSION == "source-text/v1"


def test_dto_rejects_blank_sku_and_name() -> None:
    with pytest.raises(ValidationError):
        ProductSourceText(sku="  ", name="Anillo")
    with pytest.raises(ValidationError):
        ProductSourceText(sku="SKU01", name="")


def test_dto_forbids_price_and_provenance_fields() -> None:
    with pytest.raises(ValidationError):
        ProductSourceText(sku="SKU01", name="Anillo", price=99.5)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ProductSourceText(sku="SKU01", name="Anillo", family_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ProductSourceText(sku="SKU01", name="Anillo", source="inferred")  # type: ignore[call-arg]


def test_source_text_is_stable_for_same_profile() -> None:
    record = _base()
    first = build_source_text(record)
    second = build_source_text(record)

    assert first == second
    assert "\r" not in first
    digest = hash_source_text(first)
    assert digest == hash_source_text(second)
    assert digest == hashlib.sha256(first.encode("utf-8")).hexdigest()
    assert len(digest) == 64
    assert digest == digest.lower()
    assert first.startswith("SKU: SKU01\nNombre: Anillo erizo de mar\n")


def test_material_order_does_not_change_hash() -> None:
    left = build_source_text(_base(materials=["oro", "plata"]))
    right = build_source_text(_base(materials=["plata", "oro"]))

    assert "Materiales: oro, plata" in left
    assert left == right
    assert hash_source_text(left) == hash_source_text(right)

    tags_left = build_source_text(_base(color_tags=["rojo", "beige"], style_tags=["boho", "clasico"]))
    tags_right = build_source_text(_base(color_tags=["beige", "rojo"], style_tags=["clasico", "boho"]))
    assert hash_source_text(tags_left) == hash_source_text(tags_right)


def test_hash_changes_when_family_changes() -> None:
    without = hash_source_text(build_source_text(_base(family_name=None)))
    with_family = build_source_text(_base(family_name="Anillo erizo de mar"))
    renamed = hash_source_text(build_source_text(_base(family_name="Anillo concha")))

    assert "Familia: Anillo erizo de mar" in with_family
    assert without != hash_source_text(with_family)
    assert hash_source_text(with_family) != renamed


def test_absent_fields_are_omitted_not_sentinel() -> None:
    text = build_source_text(
        ProductSourceText(
            sku="SKU01",
            name="Anillo",
            materials=[],
            color_tags=[],
            style_tags=[],
            occasion_tags=[],
        )
    )

    for label in ("Piedra:", "Talla:", "Familia:", "Colores:", "Estilo:", "Ocasiones:", "Materiales:"):
        assert label not in text
    assert "ninguna" not in text
    assert "n/a" not in text
    assert text == "SKU: SKU01\nNombre: Anillo"


def test_price_is_not_in_source_text() -> None:
    text = build_source_text(
        ProductSourceText(sku="SKU01", name="Anillo", style_tags=["boho"])
    )

    assert "SKU: SKU01" in text
    assert "Estilo: boho" in text
    assert "price" not in text.lower()
    assert "price_band" not in text
    assert "99" not in text


def test_family_id_uuid_is_not_in_source_text() -> None:
    family_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    text = build_source_text(_base(family_name="Anillo erizo de mar"))

    assert family_id not in text
    assert "Familia: Anillo erizo de mar" in text
    assert "aaaaaaaa" not in text
