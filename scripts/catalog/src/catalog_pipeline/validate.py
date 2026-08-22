from __future__ import annotations

from collections import defaultdict

from catalog_pipeline.assist import assert_no_meta_copy, assert_no_unevidenced_claims
from catalog_pipeline.constants import DESCRIPTION_MAX_LEN, FAMILY_JSON_KEYS
from catalog_pipeline.errors import ValidationError
from catalog_pipeline.grouping import group_products
from catalog_pipeline.models import EnrichedRecord, SourceRow


def _description_value(record: EnrichedRecord) -> str:
    return "" if record.description is None else record.description


def assert_unique_skus(records: list[EnrichedRecord]) -> None:
    seen: dict[str, int] = {}
    for index, record in enumerate(records):
        key = record.sku.casefold()
        if key in seen:
            raise ValidationError(f"Duplicate SKU {record.sku!r}.")
        seen[key] = index


def assert_data_origin_and_provenance(records: list[EnrichedRecord]) -> None:
    for record in records:
        if record.data_origin != "real":
            raise ValidationError(f"{record.sku}: data_origin must be 'real'.")
        if record.text_provenance not in {"ai_assisted", "merchant"}:
            raise ValidationError(f"{record.sku}: invalid text_provenance.")
        if record.text_quality_tier not in {"rich", "sparse", "original"}:
            raise ValidationError(f"{record.sku}: invalid text_quality_tier.")


def assert_description_length(records: list[EnrichedRecord]) -> None:
    for record in records:
        text = _description_value(record)
        if len(text) > DESCRIPTION_MAX_LEN:
            raise ValidationError(
                f"{record.sku}: description is {len(text)} characters (max {DESCRIPTION_MAX_LEN})."
            )


def assert_tier_provenance_consistency(records: list[EnrichedRecord]) -> None:
    for record in records:
        text = _description_value(record)
        if record.text_quality_tier == "original":
            if record.text_provenance != "merchant":
                raise ValidationError(f"{record.sku}: original tier must be merchant.")
        else:
            if record.text_provenance != "ai_assisted":
                raise ValidationError(f"{record.sku}: {record.text_quality_tier} must be ai_assisted.")
            if text.strip() == "":
                raise ValidationError(f"{record.sku}: {record.text_quality_tier} needs non-empty text.")


def assert_original_matches_source(
    records: list[EnrichedRecord], source_rows: list[SourceRow]
) -> None:
    by_sku = {row.sku: row for row in source_rows}
    for record in records:
        if record.text_quality_tier != "original":
            continue
        source = by_sku.get(record.sku)
        if source is None:
            raise ValidationError(f"{record.sku}: original tier has no matching export row.")
        if record.description != source.description:
            raise ValidationError(
                f"{record.sku}: original description must equal the export Description."
            )


def assert_no_mixed_tiers(records: list[EnrichedRecord]) -> None:
    if not any(record.variant_group_key for record in records):
        return
    by_group: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if not record.variant_group_key:
            continue
        by_group[record.variant_group_key].add(record.text_quality_tier)
    mixed = {key: tiers for key, tiers in by_group.items() if len(tiers) > 1}
    if mixed:
        raise ValidationError(f"Groups mix quality tiers: {sorted(mixed)}")


def assert_no_mixed_tiers_from_source(
    records: list[EnrichedRecord], source_rows: list[SourceRow]
) -> None:
    grouping = group_products(source_rows)
    by_group: dict[str, set[str]] = defaultdict(set)
    for record in records:
        item = grouping.get(record.sku)
        if item is None:
            continue
        by_group[item.variant_group_key].add(record.text_quality_tier)
    mixed = {key: tiers for key, tiers in by_group.items() if len(tiers) > 1}
    if mixed:
        raise ValidationError(f"Groups mix quality tiers: {sorted(mixed)}")


def assert_family_seed(records: list[EnrichedRecord]) -> None:
    if not any(record.variant_group_key for record in records):
        return
    by_group: dict[str, list[str]] = defaultdict(list)
    for record in records:
        if record.variant_group_key:
            by_group[record.variant_group_key].append(record.sku)
    for record in records:
        if not record.variant_group_key:
            continue
        if record.family_seed.group_key != record.variant_group_key:
            raise ValidationError(f"{record.sku}: family_seed.group_key mismatch.")
        expected = tuple(sorted(by_group[record.variant_group_key]))
        if record.family_seed.member_skus and tuple(record.family_seed.member_skus) != expected:
            raise ValidationError(f"{record.sku}: family_seed.member_skus mismatch.")


def assert_assisted_copy(records: list[EnrichedRecord], source_rows: list[SourceRow] | None) -> None:
    by_sku = {row.sku: row for row in source_rows} if source_rows else {}
    for record in records:
        if record.text_quality_tier not in {"rich", "sparse"}:
            continue
        text = _description_value(record)
        try:
            assert_no_meta_copy(text, record.sku)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        source = by_sku.get(record.sku)
        if source is None:
            continue
        try:
            assert_no_unevidenced_claims(text, source)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc


def assert_payload_omits_family_fields(payload: dict) -> None:
    present = [key for key in FAMILY_JSON_KEYS if key in payload]
    if present:
        raise ValidationError(f"JSONL must not emit family fields: {present}")


def assert_sidecar_keys(payload: dict) -> None:
    required = (
        "generator_version",
        "seed",
        "generated_at",
        "counts_by_tier",
        "ratios_by_tier",
        "counts_by_text_provenance",
        "ratios_by_text_provenance",
        "grouping",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValidationError(f"Sidecar missing keys: {missing}")


def validate_records(
    records: list[EnrichedRecord],
    source_rows: list[SourceRow] | None = None,
) -> None:
    if not records:
        raise ValidationError("JSONL is empty.")
    assert_unique_skus(records)
    assert_data_origin_and_provenance(records)
    assert_description_length(records)
    assert_tier_provenance_consistency(records)
    assert_no_mixed_tiers(records)
    assert_family_seed(records)
    assert_assisted_copy(records, source_rows)
    if source_rows is not None:
        assert_original_matches_source(records, source_rows)
        assert_no_mixed_tiers_from_source(records, source_rows)
