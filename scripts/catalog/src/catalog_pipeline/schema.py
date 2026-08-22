from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from catalog_pipeline.constants import GENERATOR_VERSION, JSONL_FILENAME, META_FILENAME
from catalog_pipeline.errors import ValidationError
from catalog_pipeline.models import EnrichedRecord, record_from_json
from catalog_pipeline.quality import counts_by_tier, ratios_by_tier


def serialize_record(record: EnrichedRecord) -> str:
    return json.dumps(record.to_json_dict(), ensure_ascii=False, separators=(",", ":"))


def parse_record(line: str) -> EnrichedRecord:
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise ValidationError("JSONL line is not an object.")
    return record_from_json(payload)


def write_jsonl(path: Path, records: list[EnrichedRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(serialize_record(record) + "\n")


def read_jsonl(path: Path | str) -> list[EnrichedRecord]:
    source = Path(path)
    records: list[EnrichedRecord] = []
    with source.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(parse_record(text))
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValidationError(f"{source}:{line_no}: {exc}") from exc
    return records


def build_sidecar(
    records: list[EnrichedRecord],
    *,
    seed: str,
    grouping: dict[str, int],
    generated_at: datetime | None = None,
    generator_version: str = GENERATOR_VERSION,
) -> dict[str, Any]:
    tiers = [record.text_quality_tier for record in records]
    provenances = [record.text_provenance for record in records]
    ai_assisted = sum(1 for item in provenances if item == "ai_assisted")
    merchant = sum(1 for item in provenances if item == "merchant")
    total = len(records) or 1
    stamp = generated_at or datetime.now(timezone.utc)
    return {
        "generator_version": generator_version,
        "seed": seed,
        "generated_at": stamp.isoformat(),
        "model": None,
        "product_count": len(records),
        "counts_by_tier": counts_by_tier(tiers),
        "ratios_by_tier": ratios_by_tier(tiers),
        "counts_by_text_provenance": {
            "ai_assisted": ai_assisted,
            "merchant": merchant,
        },
        "ratios_by_text_provenance": {
            "ai_assisted": 100.0 * ai_assisted / total,
            "merchant": 100.0 * merchant / total,
        },
        "grouping": grouping,
    }


def write_sidecar(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_sidecar(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def default_output_paths(directory: Path) -> tuple[Path, Path]:
    return directory / JSONL_FILENAME, directory / META_FILENAME
