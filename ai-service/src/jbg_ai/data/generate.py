"""Orchestrate SKU reservation, LLM drafts, stamping and JSONL write."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jbg_ai.data.briefs import CollectionBrief, default_briefs
from jbg_ai.data.constants import (
    DEFAULT_SEED,
    DEFAULT_SYNTHETIC_COUNT,
    DESCRIPTION_MAX_LEN,
    GENERATOR_VERSION,
    LLM_DRAFT_BATCH_SIZE,
    PROMPT_VERSION,
    REAL_CORPUS_COUNT,
)
from jbg_ai.data.errors import GenerateError
from jbg_ai.data.families import expand_base, group_slots_for_draft, plan_slots
from jbg_ai.data.io import (
    build_sidecar,
    collection_names_from_jsonl,
    read_jsonl,
    write_jsonl,
    write_sidecar,
)
from jbg_ai.data.llm import CatalogLlm, DraftRequest, PieceDraft, load_prompt
from jbg_ai.data.paths import REAL_JSONL, default_output_paths
from jbg_ai.data.quality import (
    TextQualityTier,
    apply_empty_short_descriptions,
    description_matches_tier,
    fit_description_to_tier,
)
from jbg_ai.data.records import SyntheticRecord
from jbg_ai.data.sku import allocate_skus, occupied_skus_from_jsonl
from jbg_ai.data.validate import validate_records


def generate_corpus(
    *,
    output_dir: Path,
    llm: CatalogLlm,
    real_jsonl: Path | None = None,
    seed: str = DEFAULT_SEED,
    product_count: int = DEFAULT_SYNTHETIC_COUNT,
    regenerate_text: bool = False,
    extra_occupied_skus: set[str] | None = None,
    briefs: list[CollectionBrief] | None = None,
    prompt: str | None = None,
    enforce_collection_count: bool = True,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, list[SyntheticRecord]]:
    jsonl_path, meta_path = default_output_paths(output_dir)
    if jsonl_path.exists() and not regenerate_text:
        return jsonl_path, meta_path, read_jsonl(jsonl_path)

    source = real_jsonl or REAL_JSONL
    if not source.exists():
        raise GenerateError(f"Real corpus not found: {source}")

    occupied = occupied_skus_from_jsonl(source)
    if extra_occupied_skus:
        occupied |= extra_occupied_skus
    real_collections = collection_names_from_jsonl(source)
    planned = briefs or default_briefs()
    slots = plan_slots(product_count, planned, seed)
    if not slots:
        raise GenerateError("product_count produced no collection briefs.")

    skus = allocate_skus(product_count, occupied, seed=seed)
    system_prompt = prompt if prompt is not None else load_prompt()

    stamped: list[tuple[str, str, str, str, str, str]] = []
    sku_index = 0
    drafted_bases = 0
    taken_stems: set[str] = set()
    for brief, group in group_slots_for_draft(slots):
        bases = _draft_in_batches(
            llm, brief, len(group), system_prompt, text_quality_tier=group[0].text_quality_tier
        )
        if len(bases) != len(group):
            raise GenerateError(
                f"LLM returned {len(bases)} bases for {brief.name or 'unassigned'!r}, "
                f"expected {len(group)}."
            )
        drafted_bases += len(bases)
        print(
            f"drafted {len(bases)} bases for {brief.name or 'sin colección'!r} "
            f"({drafted_bases} bases)",
            flush=True,
        )
        for slot, piece in zip(group, bases, strict=True):
            description, piece = _fit_or_redraft(
                llm, brief, slot.text_quality_tier, piece, system_prompt
            )
            for name, price in expand_base(piece, slot.sizes, taken_stems=taken_stems):
                stamped.append(
                    (
                        skus[sku_index],
                        name,
                        description,
                        price,
                        slot.brief.name,
                        slot.text_quality_tier,
                    )
                )
                sku_index += 1

    if sku_index != product_count:
        raise GenerateError(f"Expanded {sku_index} products, expected {product_count}.")

    records = [
        SyntheticRecord(
            sku=sku,
            name=name,
            description=description,
            price=price,
            collection_name=collection_name,
            text_quality_tier=tier,
        )
        for sku, name, description, price, collection_name, tier in stamped
    ]
    records = apply_empty_short_descriptions(records, seed)

    validate_records(
        records,
        real_skus=occupied,
        real_collections=real_collections,
        enforce_collection_count=enforce_collection_count,
    )
    write_jsonl(jsonl_path, records)
    audiences = {brief.name: brief.audience for brief in planned if brief.name}
    sidecar = build_sidecar(
        records,
        seed=seed,
        model=llm.model_id,
        prompt_version=PROMPT_VERSION,
        generator_version=GENERATOR_VERSION,
        generated_at=generated_at or datetime.now(timezone.utc),
        collection_audiences=audiences,
        real_count=REAL_CORPUS_COUNT,
    )
    write_sidecar(meta_path, sidecar)
    return jsonl_path, meta_path, records


def _fit_or_redraft(
    llm: CatalogLlm,
    brief: CollectionBrief,
    tier: TextQualityTier,
    piece: PieceDraft,
    prompt: str,
) -> tuple[str, PieceDraft]:
    fitted = _fit_piece(piece.description, tier)
    if description_matches_tier(fitted, tier):
        return fitted, piece
    retry = llm.draft_pieces(
        DraftRequest(
            collection_name=brief.name,
            audience=brief.audience,
            count=1,
            theme=brief.theme,
            text_quality_tier=tier,
        ),
        prompt,
    )
    piece = retry[0]
    return _fit_piece(piece.description, tier), piece


def _fit_piece(description: str, tier: TextQualityTier) -> str:
    if len(description) > DESCRIPTION_MAX_LEN:
        return description
    return fit_description_to_tier(description, tier)


def _draft_in_batches(
    llm: CatalogLlm,
    brief: CollectionBrief,
    count: int,
    prompt: str,
    *,
    text_quality_tier: TextQualityTier,
    batch_size: int = LLM_DRAFT_BATCH_SIZE,
) -> list[PieceDraft]:
    """Split a brief into small structured-output calls (one base piece per slot)."""
    pieces: list[PieceDraft] = []
    remaining = count
    while remaining > 0:
        n = min(batch_size, remaining)
        batch = llm.draft_pieces(
            DraftRequest(
                collection_name=brief.name,
                audience=brief.audience,
                count=n,
                theme=brief.theme,
                text_quality_tier=text_quality_tier,
            ),
            prompt,
        )
        if len(batch) != n:
            raise GenerateError(
                f"LLM returned {len(batch)} pieces for {brief.name or 'unassigned'!r}, expected {n}."
            )
        pieces.extend(batch)
        remaining -= n
    return pieces
