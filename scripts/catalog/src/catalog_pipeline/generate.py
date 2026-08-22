from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from catalog_pipeline.assist import draft_description
from catalog_pipeline.constants import DEFAULT_SEED, GENERATOR_VERSION
from catalog_pipeline.grouping import group_products, grouping_counts
from catalog_pipeline.models import EnrichedRecord, SourceRow
from catalog_pipeline.quality import assign_quality
from catalog_pipeline.reader import format_price, read_export
from catalog_pipeline.schema import build_sidecar, default_output_paths, read_jsonl, write_jsonl, write_sidecar
from catalog_pipeline.validate import validate_records


def build_records(
    rows: list[SourceRow],
    *,
    seed: str = DEFAULT_SEED,
    existing: dict[str, EnrichedRecord] | None = None,
    regenerate_text: bool = False,
) -> list[EnrichedRecord]:
    groupings = group_products(rows)
    sku_to_group = {sku: item.variant_group_key for sku, item in groupings.items()}
    qualities = assign_quality(sku_to_group, seed=seed)
    records: list[EnrichedRecord] = []
    for row in rows:
        grouping = groupings[row.sku]
        quality = qualities[row.sku]
        previous = None if existing is None else existing.get(row.sku)
        if (
            previous is not None
            and not regenerate_text
            and previous.text_quality_tier == quality.text_quality_tier
        ):
            description = previous.description
        else:
            description = draft_description(row, quality.text_quality_tier)
        records.append(
            EnrichedRecord(
                sku=row.sku,
                name=row.name,
                description=description,
                price=format_price(row.price),
                collection_name=row.collection_name,
                data_origin="real",
                text_provenance=quality.text_provenance,
                text_quality_tier=quality.text_quality_tier,
                variant_group_key=grouping.variant_group_key,
                variant_label=grouping.variant_label,
                family_seed=grouping.family_seed,
                product_id=None if previous is None else previous.product_id,
            )
        )
    return records


def generate_corpus(
    source: Path,
    output_dir: Path,
    *,
    seed: str = DEFAULT_SEED,
    regenerate_text: bool = False,
    generator_version: str = GENERATOR_VERSION,
) -> tuple[Path, Path, list[EnrichedRecord]]:
    rows = read_export(source)
    jsonl_path, meta_path = default_output_paths(output_dir)
    existing: dict[str, EnrichedRecord] = {}
    if jsonl_path.exists() and not regenerate_text:
        existing = {record.sku: record for record in read_jsonl(jsonl_path)}
    records = build_records(rows, seed=seed, existing=existing or None, regenerate_text=regenerate_text)
    validate_records(records, source_rows=rows)
    write_jsonl(jsonl_path, records)
    sidecar = build_sidecar(
        records,
        seed=seed,
        grouping=grouping_counts(group_products(rows)),
        generated_at=datetime.now(timezone.utc),
        generator_version=generator_version,
    )
    write_sidecar(meta_path, sidecar)
    return jsonl_path, meta_path, records
