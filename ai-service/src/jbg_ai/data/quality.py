"""Name-stem grouping and 70/20/10 quality assignment. Delivered by C06b."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import replace
from typing import Literal

from jbg_ai.data.constants import (
    DEFAULT_SEED,
    DESCRIPTION_MAX_LEN,
    RATIO_TOLERANCE_PP,
    RICH_CUTOFF,
    RICH_MAX_SENTENCES,
    RICH_MIN_CHARS,
    RICH_MIN_SENTENCES,
    SHORT_EMPTY_RATIO,
    SHORT_MAX_CHARS,
    SPARSE_CUTOFF,
    SPARSE_MAX_CHARS,
    SPARSE_MAX_SENTENCES,
    SPARSE_OVERFLOW_CHARS,
    TARGET_RATIOS,
)
from jbg_ai.data.errors import RatioError

TextQualityTier = Literal["rich", "sparse", "short"]

_SIZE_TOKENS = frozenset(
    {
        "xxs",
        "xs",
        "s",
        "m",
        "l",
        "xl",
        "xxl",
        "mini",
        "extramini",
        "pequeno",
        "pequena",
        "pequenas",
        "mediano",
        "mediana",
        "medianas",
        "grande",
        "grandes",
    }
)
_MEASURE_RE = re.compile(r"^\d+(?:mm|cm)$")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_name(name: str) -> str:
    folded = strip_accents(name).casefold()
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return " ".join(folded.split())


def _is_size_token(token: str) -> bool:
    if token in _SIZE_TOKENS:
        return True
    if _MEASURE_RE.match(token):
        return True
    return token.isdigit() and 5 <= int(token) <= 48


def name_stem(name: str) -> str:
    """Stem used only for the quality raffle — never serialised to JSONL."""
    tokens = normalize_name(name).split()
    if not tokens:
        return "producto"
    cut = len(tokens)
    while cut > 0 and _is_size_token(tokens[cut - 1]):
        cut -= 1
    stem = tokens[:cut] or tokens[:1]
    return "-".join(stem)


def stems_for(names: dict[str, str]) -> dict[str, str]:
    """Map sku → stem. Same names → same map."""
    return {sku: name_stem(name) for sku, name in names.items()}


def unit_interval(group_key: str, seed: str = DEFAULT_SEED) -> float:
    digest = hashlib.sha256(f"{seed}\0{group_key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def bucket_for(group_key: str, seed: str = DEFAULT_SEED) -> TextQualityTier:
    value = unit_interval(group_key, seed)
    if value < RICH_CUTOFF:
        return "rich"
    if value < SPARSE_CUTOFF:
        return "sparse"
    return "short"


def assign_quality(
    sku_to_stem: dict[str, str],
    seed: str = DEFAULT_SEED,
    *,
    rebalance: bool | None = None,
) -> dict[str, TextQualityTier]:
    stem_tier = {stem: bucket_for(stem, seed) for stem in set(sku_to_stem.values())}
    assigned = {sku: stem_tier[stem] for sku, stem in sku_to_stem.items()}
    if rebalance is None:
        rebalance = len(sku_to_stem) >= 50
    if rebalance:
        return rebalance_assignments(sku_to_stem, assigned)
    return assigned


def rebalance_assignments(
    sku_to_stem: dict[str, str],
    assigned: dict[str, TextQualityTier],
    *,
    targets: dict[str, float] | None = None,
    tolerance_pp: float = RATIO_TOLERANCE_PP,
) -> dict[str, TextQualityTier]:
    expected = targets or TARGET_RATIOS
    members_by_stem: dict[str, list[str]] = defaultdict(list)
    for sku, stem in sku_to_stem.items():
        members_by_stem[stem].append(sku)
    current = dict(assigned)

    def current_ratios() -> dict[str, float]:
        return ratios_by_tier([current[sku] for sku in sku_to_stem])

    for _ in range(len(members_by_stem)):
        ratios = current_ratios()
        try:
            assert_ratio_tolerance(ratios, targets=expected, tolerance_pp=tolerance_pp)
            break
        except RatioError:
            pass
        destination = min(expected, key=lambda name: ratios[name] - expected[name])
        source = max(
            (name for name in expected if name != destination),
            key=lambda name: ratios[name] - expected[name],
        )
        candidates = [
            (len(members), key)
            for key, members in members_by_stem.items()
            if current[members[0]] == source
        ]
        if not candidates:
            break
        _, move_key = min(candidates)
        for sku in members_by_stem[move_key]:
            current[sku] = destination  # type: ignore[assignment]
    return current


def counts_by_tier(tiers: list[TextQualityTier]) -> dict[str, int]:
    counter = Counter(tiers)
    return {name: int(counter.get(name, 0)) for name in TARGET_RATIOS}


def ratios_by_tier(tiers: list[TextQualityTier]) -> dict[str, float]:
    total = len(tiers)
    if total == 0:
        return {name: 0.0 for name in TARGET_RATIOS}
    counts = counts_by_tier(tiers)
    return {name: 100.0 * count / total for name, count in counts.items()}


def assert_ratio_tolerance(
    ratios: dict[str, float],
    *,
    targets: dict[str, float] | None = None,
    tolerance_pp: float = RATIO_TOLERANCE_PP,
) -> None:
    expected = targets or TARGET_RATIOS
    failures: list[str] = []
    for name, target in expected.items():
        actual = ratios.get(name, 0.0)
        if abs(actual - target) > tolerance_pp:
            failures.append(f"{name}: {actual:.2f}% (target {target:.0f}% ±{tolerance_pp:g} pp)")
    if failures:
        raise RatioError("Quality ratios outside tolerance: " + "; ".join(failures))


def assert_no_mixed_tiers(sku_to_stem: dict[str, str], tiers: dict[str, TextQualityTier]) -> None:
    by_stem: dict[str, set[str]] = defaultdict(set)
    for sku, stem in sku_to_stem.items():
        by_stem[stem].add(tiers[sku])
    mixed = {stem: values for stem, values in by_stem.items() if len(values) > 1}
    if mixed:
        raise RatioError(f"Name stems mix quality tiers: {sorted(mixed)}")


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_TERMINAL_PUNCT = frozenset(".!?…")
_DANGLING_LAST = frozenset(
    {
        "a",
        "al",
        "como",
        "con",
        "cuya",
        "cuyas",
        "cuyo",
        "cuyos",
        "de",
        "del",
        "e",
        "el",
        "en",
        "entre",
        "hacia",
        "la",
        "las",
        "los",
        "o",
        "para",
        "por",
        "que",
        "sin",
        "sobre",
        "u",
        "un",
        "una",
        "y",
    }
)


def split_sentences(text: str) -> list[str]:
    collapsed = " ".join(text.split())
    if not collapsed:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT.split(collapsed) if part.strip()]


def description_score(text: str) -> tuple[int, int]:
    stripped = text.strip()
    return (len(split_sentences(stripped)), len(stripped))


def _normalize_sentence(part: str) -> str:
    text = part.strip()
    if not text:
        return ""
    if text[-1] not in _TERMINAL_PUNCT:
        return text + "."
    return text


def description_is_complete(text: str) -> bool:
    """Empty is allowed. Non-empty copy must be whole sentences, never a word-clip stub."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped[-1] not in _TERMINAL_PUNCT:
        return False
    for raw in split_sentences(stripped):
        sentence = _normalize_sentence(raw)
        last = re.sub(r"[.!?…]+$", "", sentence).strip().rsplit(" ", 1)[-1]
        last = last.casefold().strip("«»\"'“”")
        if not last or last in _DANGLING_LAST:
            return False
    return True


def _clip_to_complete_sentences(text: str, max_chars: int, max_sentences: int) -> str:
    """Keep whole sentences that fit. Never cut mid-sentence."""
    kept: list[str] = []
    for raw in split_sentences(text)[:max_sentences]:
        sentence = _normalize_sentence(raw)
        if not sentence or not description_is_complete(sentence):
            break
        candidate = " ".join((*kept, sentence))
        if len(candidate) > max_chars:
            break
        kept.append(sentence)
    return " ".join(kept)


def fit_description_to_tier(text: str, tier: TextQualityTier) -> str:
    """Keep whole sentences that fit the tier. Does not invent rich text."""
    collapsed = " ".join(text.split())
    if tier == "short":
        return _clip_to_complete_sentences(collapsed, SHORT_MAX_CHARS, 1)
    if tier == "sparse":
        packed = _clip_to_complete_sentences(collapsed, SPARSE_MAX_CHARS, SPARSE_MAX_SENTENCES)
        if description_matches_tier(packed, "sparse"):
            return packed
        overflow = _clip_to_complete_sentences(collapsed, SPARSE_OVERFLOW_CHARS, 1)
        if description_matches_tier(overflow, "sparse"):
            return overflow
        return packed
    return _clip_to_complete_sentences(collapsed, DESCRIPTION_MAX_LEN, RICH_MAX_SENTENCES)


def description_matches_tier(text: str, tier: TextQualityTier) -> bool:
    if not description_is_complete(text):
        return False
    sentences = split_sentences(text)
    chars = len(text.strip())
    if tier == "short":
        return chars == 0 or (chars <= SHORT_MAX_CHARS and len(sentences) <= 1)
    if tier == "sparse":
        return (
            1 <= len(sentences) <= SPARSE_MAX_SENTENCES
            and SHORT_MAX_CHARS < chars <= SPARSE_OVERFLOW_CHARS
        )
    return chars >= RICH_MIN_CHARS


def assign_tiers_by_description_richness(
    sku_to_stem: dict[str, str],
    stem_to_description: dict[str, str],
) -> dict[str, TextQualityTier]:
    """Richest stems become rich, then sparse, then short, targeting 70/20/10 by product."""
    members_by_stem: dict[str, list[str]] = defaultdict(list)
    for sku, stem in sku_to_stem.items():
        members_by_stem[stem].append(sku)
    ranked = sorted(
        members_by_stem,
        key=lambda stem: (
            description_score(stem_to_description.get(stem, ""))[1],
            description_score(stem_to_description.get(stem, ""))[0],
            stem,
        ),
        reverse=True,
    )
    total = len(sku_to_stem)
    n_rich = round(total * TARGET_RATIOS["rich"] / 100.0)
    n_sparse = round(total * TARGET_RATIOS["sparse"] / 100.0)
    quotas = {"rich": n_rich, "sparse": n_sparse, "short": total - n_rich - n_sparse}
    filled = {"rich": 0, "sparse": 0, "short": 0}
    stem_tier: dict[str, TextQualityTier] = {}
    for stem in ranked:
        size = len(members_by_stem[stem])
        for bucket in ("rich", "sparse", "short"):
            if bucket != "short" and filled[bucket] + size > quotas[bucket]:
                continue
            stem_tier[stem] = bucket  # type: ignore[assignment]
            filled[bucket] += size
            break
        else:
            stem_tier[stem] = "short"
            filled["short"] += size
    return {sku: stem_tier[stem] for sku, stem in sku_to_stem.items()}


def apply_empty_short_descriptions(
    records: list,
    seed: str = DEFAULT_SEED,
    *,
    empty_ratio: float = SHORT_EMPTY_RATIO,
) -> list:
    """Blank ~20 % of short-tier products (whole name stems, so families stay aligned)."""
    sku_to_stem = {record.sku: name_stem(record.name) for record in records}
    members_by_stem: dict[str, list] = defaultdict(list)
    for record in records:
        if record.text_quality_tier == "short":
            members_by_stem[sku_to_stem[record.sku]].append(record)
    if not members_by_stem:
        return list(records)
    short_n = sum(len(members) for members in members_by_stem.values())
    target = max(1, round(empty_ratio * short_n)) if short_n else 0
    ordered = sorted(
        members_by_stem,
        key=lambda stem: (len(members_by_stem[stem]), unit_interval(f"{seed}\0empty-short\0{stem}"), stem),
    )
    empty_stems: set[str] = set()
    filled = 0
    for stem in ordered:
        if filled >= target:
            break
        empty_stems.add(stem)
        filled += len(members_by_stem[stem])
    return [
        replace(record, description="")
        if sku_to_stem[record.sku] in empty_stems
        else record
        for record in records
    ]


def realign_records_to_copy(records: list, seed: str = DEFAULT_SEED) -> list:
    """Reassign 70/20/10 by actual richness, then clip sparse/short. Same stem keeps copy."""
    sku_to_stem = {record.sku: name_stem(record.name) for record in records}
    stem_to_description: dict[str, str] = {}
    for record in records:
        stem_to_description.setdefault(sku_to_stem[record.sku], record.description)
    tiers = assign_tiers_by_description_richness(sku_to_stem, stem_to_description)
    stem_tier = {sku_to_stem[sku]: tier for sku, tier in tiers.items()}
    fitted = {
        stem: fit_description_to_tier(description, stem_tier[stem])
        for stem, description in stem_to_description.items()
    }
    aligned = [
        replace(
            record,
            description=fitted[sku_to_stem[record.sku]],
            text_quality_tier=tiers[record.sku],
        )
        for record in records
    ]
    return apply_empty_short_descriptions(aligned, seed)
