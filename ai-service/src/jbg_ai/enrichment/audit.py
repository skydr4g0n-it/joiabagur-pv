"""Batch quality gates, evaluated outside the HTTP POST. Delivered by C09."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from jbg_ai.api.schemas.enrich import ProposedList, ProposedProfile, ProposedText
from jbg_ai.enrichment.vocab import Vocabularies, load_vocabularies

ORIGINAL_SHORT = frozenset({"original", "short"})
SPARSE = "sparse"
AI_ASSISTED = frozenset({"ai_assisted", "rich"})

AI_ASSISTED_THRESHOLD = 0.90
GLOBAL_THRESHOLD = 0.70


@dataclass(frozen=True)
class AuditRecord:
    sku: str
    profile: ProposedProfile
    stratum: str


@dataclass(frozen=True)
class AuditResult:
    ok: bool
    failures: tuple[str, ...] = field(default_factory=tuple)


def _has_any_tag(profile: ProposedProfile) -> bool:
    return any(
        list_field.value
        for list_field in (profile.color_tags, profile.style_tags, profile.occasion_tags)
    )


def _values(field: ProposedText | ProposedList | None) -> list[str]:
    if field is None:
        return []
    raw = field.value
    if isinstance(raw, list):
        return list(raw)
    return [raw]


def _vocab_failures(profile: ProposedProfile, vocabs: Vocabularies) -> list[str]:
    failures: list[str] = []
    checks = (
        ("piece_type", profile.piece_type, vocabs.piece_type),
        ("stone_type", profile.stone_type, vocabs.stone_type),
        ("size_label", profile.size_label, vocabs.size_label),
        ("materials", profile.materials, vocabs.materials),
        ("color_tags", profile.color_tags, vocabs.color_tags),
        ("style_tags", profile.style_tags, vocabs.style_tags),
        ("occasion_tags", profile.occasion_tags, vocabs.occasion_tags),
    )
    for field_name, proposed, vocab in checks:
        for value in _values(proposed):
            if vocab.resolve(value) != value:
                failures.append(f"{profile.sku}: {field_name} value {value!r} is outside vocabulary")
    return failures


def audit_batch(
    records: list[AuditRecord],
    vocabs: Vocabularies | None = None,
) -> AuditResult:
    """Pure auditor: SKU uniqueness, vocab membership, tag coverage by stratum."""
    resolved = vocabs or load_vocabularies()
    failures: list[str] = []

    sku_counts = Counter(record.sku for record in records)
    duplicates = sorted(sku for sku, count in sku_counts.items() if count > 1)
    if duplicates:
        failures.append(f"duplicate SKUs: {duplicates}")

    for record in records:
        failures.extend(_vocab_failures(record.profile, resolved))

    sparse_empty = [
        record.sku
        for record in records
        if record.stratum == SPARSE and not _has_any_tag(record.profile)
    ]
    if sparse_empty:
        failures.append(f"sparse products missing tag lists: {sparse_empty}")

    ai_records = [record for record in records if record.stratum in AI_ASSISTED]
    if ai_records:
        ai_covered = sum(1 for record in ai_records if _has_any_tag(record.profile))
        ai_ratio = ai_covered / len(ai_records)
        if ai_ratio < AI_ASSISTED_THRESHOLD:
            failures.append(
                f"ai_assisted tag coverage {ai_ratio:.2%} below {AI_ASSISTED_THRESHOLD:.0%}"
            )

    global_records = [record for record in records if record.stratum not in ORIGINAL_SHORT]
    if global_records:
        global_covered = sum(1 for record in global_records if _has_any_tag(record.profile))
        global_ratio = global_covered / len(global_records)
        if global_ratio < GLOBAL_THRESHOLD:
            failures.append(
                f"global tag coverage {global_ratio:.2%} below {GLOBAL_THRESHOLD:.0%} "
                "(original/short excluded)"
            )

    return AuditResult(ok=not failures, failures=tuple(failures))
