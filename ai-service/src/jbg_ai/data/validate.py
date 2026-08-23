"""Invariants for the synthetic JSONL before ingest. Delivered by C06b."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from jbg_ai.data.constants import (
    CHANNEL_COLLECTION_NAMES,
    COLLECTION_NAME_MAX_LEN,
    DESCRIPTION_MAX_LEN,
    FORBIDDEN_JSON_KEYS,
    NAME_MAX_LEN,
    PRICE_MAX,
)
from jbg_ai.data.errors import ValidationError
from jbg_ai.data.families import (
    assert_family_completeness,
    assert_family_copy_consistent,
    assert_unassigned_ratio,
)
from jbg_ai.data.quality import assert_no_mixed_tiers, description_matches_tier, name_stem
from jbg_ai.data.records import SyntheticRecord
from jbg_ai.data.sku import is_real_scheme_sku


def _fold(value: str) -> str:
    return " ".join(value.casefold().split())


def assert_unique_skus(records: list[SyntheticRecord]) -> None:
    seen: set[str] = set()
    for record in records:
        key = record.sku.casefold()
        if key in seen:
            raise ValidationError(f"Duplicate SKU {record.sku!r}.")
        seen.add(key)


def assert_skus_disjoint_from_real(records: list[SyntheticRecord], real_skus: set[str]) -> None:
    taken = {sku.casefold() for sku in real_skus}
    collisions = [record.sku for record in records if record.sku.casefold() in taken]
    if collisions:
        raise ValidationError(f"Synthetic SKUs collide with the real corpus: {collisions[:8]}.")


def assert_sku_scheme(records: list[SyntheticRecord]) -> None:
    for record in records:
        if not is_real_scheme_sku(record.sku):
            raise ValidationError(f"{record.sku!r} is not the real-catalog SKU scheme.")
        if record.sku.startswith(("SYN-", "JB-S-")):
            raise ValidationError(f"{record.sku!r} leaks a synthetic prefix.")


def assert_description_length(records: list[SyntheticRecord]) -> None:
    for record in records:
        if len(record.description) > DESCRIPTION_MAX_LEN:
            raise ValidationError(
                f"{record.sku}: description is {len(record.description)} "
                f"characters (max {DESCRIPTION_MAX_LEN})."
            )


def assert_name_length(records: list[SyntheticRecord]) -> None:
    for record in records:
        if not record.name.strip():
            raise ValidationError(f"{record.sku}: name is empty.")
        if len(record.name) > NAME_MAX_LEN:
            raise ValidationError(f"{record.sku}: name exceeds {NAME_MAX_LEN} characters.")


def assert_prices(records: list[SyntheticRecord]) -> None:
    for record in records:
        try:
            value = Decimal(record.price)
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError(f"{record.sku}: invalid price {record.price!r}.") from exc
        if value <= 0:
            raise ValidationError(f"{record.sku}: price must be > 0.")
        if value >= PRICE_MAX:
            raise ValidationError(f"{record.sku}: price {value} is >= {PRICE_MAX}.")
        if value.as_tuple().exponent < -2:
            raise ValidationError(f"{record.sku}: price has more than 2 decimal places.")


def assert_collection_names(
    records: list[SyntheticRecord],
    *,
    real_collections: set[str],
) -> None:
    real_folded = {_fold(name) for name in real_collections}
    seen: set[str] = set()
    for record in records:
        name = record.collection_name.strip()
        if not name:
            continue
        if len(name) > COLLECTION_NAME_MAX_LEN:
            raise ValidationError(f"{record.sku}: collection_name exceeds {COLLECTION_NAME_MAX_LEN}.")
        folded = _fold(name)
        if folded in CHANNEL_COLLECTION_NAMES:
            raise ValidationError(f"{record.sku}: collection_name {name!r} is a channel/POS label.")
        if folded in real_folded:
            raise ValidationError(f"{record.sku}: collection_name {name!r} reuses a real collection.")
        seen.add(name)
    if not 8 <= len(seen) <= 12:
        raise ValidationError(f"Expected 8–12 design collections, found {len(seen)}.")


def assert_provenance_and_tiers(records: list[SyntheticRecord]) -> None:
    for record in records:
        if record.data_origin != "synthetic":
            raise ValidationError(f"{record.sku}: data_origin must be synthetic.")
        if record.text_provenance != "synthetic":
            raise ValidationError(f"{record.sku}: text_provenance must be synthetic.")
        if record.text_quality_tier not in {"rich", "sparse", "short"}:
            raise ValidationError(f"{record.sku}: invalid text_quality_tier.")
        if record.text_quality_tier == "empty":
            raise ValidationError(f"{record.sku}: tier 'empty' is forbidden.")


def assert_no_forbidden_payload_keys(payloads: list[dict]) -> None:
    for payload in payloads:
        extra = [key for key in FORBIDDEN_JSON_KEYS if key in payload]
        if extra:
            raise ValidationError(f"Forbidden JSONL keys present: {extra}.")


def assert_stem_tiers_consistent(records: list[SyntheticRecord]) -> None:
    sku_to_stem = {record.sku: name_stem(record.name) for record in records}
    tiers = {record.sku: record.text_quality_tier for record in records}
    assert_no_mixed_tiers(sku_to_stem, tiers)


def validate_records(
    records: list[SyntheticRecord],
    *,
    real_skus: set[str],
    real_collections: set[str],
    enforce_collection_count: bool = True,
    enforce_mix: bool | None = None,
) -> None:
    if not records:
        raise ValidationError("Synthetic corpus is empty.")
    assert_unique_skus(records)
    assert_skus_disjoint_from_real(records, real_skus)
    assert_sku_scheme(records)
    assert_description_length(records)
    assert_name_length(records)
    assert_prices(records)
    assert_provenance_and_tiers(records)
    assert_stem_tiers_consistent(records)
    assert_family_copy_consistent(records)
    if enforce_mix is None:
        enforce_mix = len(records) >= 50
    if enforce_mix:
        assert_unassigned_ratio(records)
        assert_family_completeness(records)
        assert_descriptions_match_tiers(records)
    if enforce_collection_count:
        assert_collection_names(records, real_collections=real_collections)
    else:
        for record in records:
            name = record.collection_name.strip()
            if not name:
                continue
            folded = _fold(name)
            if folded in CHANNEL_COLLECTION_NAMES:
                raise ValidationError(
                    f"{record.sku}: collection_name {record.collection_name!r} is a channel/POS label."
                )
            if folded in {_fold(item) for item in real_collections}:
                raise ValidationError(
                    f"{record.sku}: collection_name {record.collection_name!r} reuses a real collection."
                )


def assert_descriptions_match_tiers(records: list[SyntheticRecord]) -> None:
    failures = [
        record.sku
        for record in records
        if not description_matches_tier(record.description, record.text_quality_tier)
    ]
    if failures:
        raise ValidationError(
            "Description length does not match text_quality_tier for: "
            + ", ".join(failures[:8])
        )
