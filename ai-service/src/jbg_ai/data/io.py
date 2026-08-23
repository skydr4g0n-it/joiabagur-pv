"""JSONL and sidecar I/O. Delivered by C06b."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jbg_ai.data.constants import (
    GENERATOR_VERSION,
    PROMPT_VERSION,
    TARGET_HYBRID_TOTAL,
)
from jbg_ai.data.errors import ValidationError
from jbg_ai.data.families import family_completeness_ratios, lexical_family_groups
from jbg_ai.data.quality import counts_by_tier, ratios_by_tier
from jbg_ai.data.records import SyntheticRecord, record_from_json


def serialize_record(record: SyntheticRecord) -> str:
    return json.dumps(record.to_json_dict(), ensure_ascii=False, separators=(",", ":"))


def write_jsonl(path: Path, records: list[SyntheticRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(serialize_record(record) + "\n")


def read_jsonl(path: Path | str) -> list[SyntheticRecord]:
    source = Path(path)
    records: list[SyntheticRecord] = []
    with source.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    raise ValidationError("JSONL line is not an object.")
                records.append(record_from_json(payload))
            except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
                raise ValidationError(f"{source}:{line_no}: {exc}") from exc
    return records


def collection_names_from_jsonl(path: Path) -> set[str]:
    names: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            name = payload.get("collection_name")
            if name and str(name).strip():
                names.add(str(name).strip())
    return names


def build_sidecar(
    records: list[SyntheticRecord],
    *,
    seed: str,
    model: str,
    prompt_version: str = PROMPT_VERSION,
    generator_version: str = GENERATOR_VERSION,
    generated_at: datetime | None = None,
    collection_audiences: dict[str, str] | None = None,
    real_count: int = 436,
    target_total: int = TARGET_HYBRID_TOTAL,
) -> dict[str, Any]:
    tiers = [record.text_quality_tier for record in records]
    stamp = generated_at or datetime.now(timezone.utc)
    hybrid_total = real_count + len(records)
    payload: dict[str, Any] = {
        "generator_version": generator_version,
        "seed": seed,
        "model": model,
        "prompt_version": prompt_version,
        "generated_at": stamp.isoformat(),
        "product_count": len(records),
        "real_count": real_count,
        "hybrid_total": hybrid_total,
        "target_hybrid_total": target_total,
        "slack_vs_target": hybrid_total - target_total,
        "counts_by_tier": counts_by_tier(tiers),
        "ratios_by_tier": ratios_by_tier(tiers),
        "counts_by_text_provenance": {"synthetic": len(records)},
        "ratios_by_text_provenance": {"synthetic": 100.0 if records else 0.0},
    }
    empty_short = sum(
        1
        for record in records
        if record.text_quality_tier == "short" and not record.description.strip()
    )
    payload["empty_short_count"] = empty_short
    short_n = payload["counts_by_tier"]["short"]
    payload["empty_short_ratio_of_short"] = 100.0 * empty_short / short_n if short_n else 0.0
    unassigned = sum(1 for record in records if not record.collection_name.strip())
    complete_pct, incomplete_pct, family_members = family_completeness_ratios(records)
    payload["unassigned_count"] = unassigned
    payload["unassigned_ratio"] = 100.0 * unassigned / len(records) if records else 0.0
    payload["family_group_count"] = len(lexical_family_groups(records))
    payload["family_member_count"] = family_members
    payload["complete_family_product_ratio"] = complete_pct
    payload["incomplete_family_product_ratio"] = incomplete_pct
    if collection_audiences:
        payload["collection_audiences"] = collection_audiences
    return payload


def write_sidecar(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_sidecar(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


SIDECAR_REQUIRED_KEYS = (
    "generator_version",
    "seed",
    "model",
    "prompt_version",
    "generated_at",
    "product_count",
    "counts_by_tier",
    "ratios_by_tier",
)


def assert_sidecar_keys(payload: dict[str, Any]) -> None:
    missing = [key for key in SIDECAR_REQUIRED_KEYS if key not in payload]
    if missing:
        raise ValidationError(f"Sidecar missing keys: {missing}.")
