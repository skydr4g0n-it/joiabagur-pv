"""Lexical size-family planning. Members share copy; only name suffix and price differ."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from jbg_ai.data.briefs import CollectionBrief, distribute_uneven, unassigned_brief, unassigned_count
from jbg_ai.data.constants import (
    COMPLETE_FAMILY_PRODUCT_RATIO,
    DEFAULT_SEED,
    FAMILY_MEMBER_RATIO,
    FAMILY_SIZES,
    PRICE_MAX,
    RATIO_TOLERANCE_PP,
    SIZE_PRICE_FACTORS,
    UNASSIGNED_RATIO,
)
from jbg_ai.data.errors import ValidationError
from jbg_ai.data.llm import PieceDraft
from jbg_ai.data.quality import (
    TextQualityTier,
    _is_size_token,
    assign_quality,
    name_stem,
    normalize_name,
    unit_interval,
)
from jbg_ai.data.records import SyntheticRecord, format_price

INCOMPLETE_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("S", "M"),
    ("S", "L"),
    ("S", "XL"),
    ("M", "L"),
    ("M", "XL"),
    ("L", "XL"),
    ("S", "M", "L"),
    ("S", "M", "XL"),
    ("S", "L", "XL"),
    ("M", "L", "XL"),
)


@dataclass(frozen=True)
class FamilySlot:
    brief: CollectionBrief
    sizes: tuple[str, ...]
    text_quality_tier: TextQualityTier = "rich"


def strip_size_suffix(name: str) -> str:
    tokens = name.split()
    if not tokens:
        return name
    cut = len(tokens)
    while cut > 0 and _is_size_token(normalize_name(tokens[cut - 1])):
        cut -= 1
    if cut == 0:
        return tokens[0]
    return " ".join(tokens[:cut])


def price_for_size(base_price: str, size: str) -> str:
    factor = Decimal(SIZE_PRICE_FACTORS[size])
    raw = (Decimal(str(base_price)) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if raw <= 0:
        raw = Decimal("1")
    ceiling = Decimal(PRICE_MAX) - Decimal("1")
    if raw >= Decimal(PRICE_MAX):
        raw = ceiling
    return format_price(raw)


def uniquify_base_name(name: str, taken_stems: set[str]) -> str:
    base = strip_size_suffix(name.strip()) or "Pieza"
    candidate = base
    suffix = 2
    while name_stem(candidate) in taken_stems:
        candidate = f"{base} v{suffix}"
        suffix += 1
    taken_stems.add(name_stem(candidate))
    return candidate


def expand_base(
    draft: PieceDraft,
    sizes: tuple[str, ...],
    *,
    taken_stems: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Return (name, price) pairs. Empty sizes → one unary keeping a unique stem."""
    reserved = taken_stems if taken_stems is not None else set()
    if not sizes:
        base_name = uniquify_base_name(draft.name, reserved)
        return [(base_name, format_price(draft.price))]
    base_name = uniquify_base_name(draft.name, reserved)
    return [(f"{base_name} {size}", price_for_size(draft.price, size)) for size in sizes]


def family_member_count(product_count: int, *, ratio: float = FAMILY_MEMBER_RATIO) -> int:
    if product_count <= 0:
        return 0
    return min(product_count, round(ratio * product_count))


def plan_family_shapes(
    product_count: int,
    seed: str = DEFAULT_SEED,
    *,
    member_ratio: float = FAMILY_MEMBER_RATIO,
    complete_ratio: float = COMPLETE_FAMILY_PRODUCT_RATIO,
) -> list[tuple[str, ...]]:
    """Shapes whose lengths sum to `product_count`. `()` is a unary (no forced size)."""
    complete_members, incomplete_members = _choose_family_budget(
        product_count, member_ratio, complete_ratio
    )
    incomplete_sizes = _split_incomplete(incomplete_members)
    used = complete_members + sum(incomplete_sizes)
    unaries = product_count - used
    if unaries < 0:
        raise ValidationError("Family plan exceeded product_count.")

    shapes: list[tuple[str, ...]] = [FAMILY_SIZES] * (complete_members // 4)
    for length in incomplete_sizes:
        shapes.append(_incomplete_pattern(length, seed, len(shapes)))
    shapes.extend([()] * unaries)
    return shapes


def _choose_family_budget(
    product_count: int,
    member_ratio: float,
    complete_ratio: float,
) -> tuple[int, int]:
    target_members = family_member_count(product_count, ratio=member_ratio)
    best: tuple[int, int, int, float] | None = None
    low = max(0, target_members - 24)
    high = min(product_count, target_members + 24)
    for members in range(low, high + 1):
        for complete in range(0, members + 1, 4):
            incomplete = members - complete
            if incomplete == 1:
                continue
            if incomplete >= 2 and not _split_incomplete(incomplete):
                continue
            if members == 0:
                score = (abs(target_members), 1.0)
            else:
                actual = complete / members
                if abs(100.0 * actual - 100.0 * complete_ratio) > RATIO_TOLERANCE_PP:
                    continue
                score = (abs(members - target_members), abs(actual - complete_ratio))
            ranked = (score[0], score[1], complete, incomplete)
            if best is None or ranked[:2] < best[:2]:
                best = ranked
    if best is None:
        return 0, 0
    return best[2], best[3]


def plan_slots(
    product_count: int,
    briefs: list[CollectionBrief],
    seed: str = DEFAULT_SEED,
) -> list[FamilySlot]:
    if product_count <= 0:
        return []
    if not briefs:
        raise ValidationError("Need at least one design brief.")

    detached = unassigned_count(product_count)
    assigned = product_count - detached
    quotas = distribute_uneven(assigned, len(briefs), seed)
    capacities = list(quotas) + [detached]
    bucket_briefs = list(briefs) + [unassigned_brief()]

    shapes = sorted(plan_family_shapes(product_count, seed), key=len, reverse=True)
    remaining = capacities[:]
    slots: list[FamilySlot] = []
    for shape in shapes:
        need = len(shape) if shape else 1
        bucket = _pick_bucket(remaining, need)
        if bucket is None:
            for _ in range(need):
                unary = _pick_bucket(remaining, 1)
                if unary is None:
                    raise ValidationError("No collection bucket left for a unary product.")
                remaining[unary] -= 1
                slots.append(FamilySlot(brief=bucket_briefs[unary], sizes=()))
            continue
        remaining[bucket] -= need
        slots.append(FamilySlot(brief=bucket_briefs[bucket], sizes=shape))
    return assign_slot_tiers(slots, seed)


def assign_slot_tiers(slots: list[FamilySlot], seed: str) -> list[FamilySlot]:
    """70/20/10 by product count; every member of a slot shares the tier."""
    if not slots:
        return []
    sku_to_stem: dict[str, str] = {}
    for index, slot in enumerate(slots):
        count = len(slot.sizes) if slot.sizes else 1
        for member in range(count):
            sku_to_stem[f"{index}:{member}"] = f"slot-{index}"
    assigned = assign_quality(sku_to_stem, seed=seed)
    return [
        FamilySlot(
            brief=slot.brief,
            sizes=slot.sizes,
            text_quality_tier=assigned[f"{index}:0"],
        )
        for index, slot in enumerate(slots)
    ]


def bases_needed(slots: list[FamilySlot]) -> int:
    return len(slots)


def group_slots_for_draft(slots: list[FamilySlot]) -> list[tuple[CollectionBrief, list[FamilySlot]]]:
    grouped: dict[tuple[str, str, str, str], list[FamilySlot]] = defaultdict(list)
    order: list[tuple[str, str, str, str]] = []
    for slot in slots:
        key = (slot.brief.name, slot.brief.audience, slot.brief.theme, slot.text_quality_tier)
        if key not in grouped:
            order.append(key)
        grouped[key].append(slot)
    return [(group[0].brief, group) for group in (grouped[key] for key in order)]


def lexical_family_groups(records: list[SyntheticRecord]) -> dict[str, list[SyntheticRecord]]:
    """Stems with two or more members and at least one size suffix."""
    by_stem: dict[str, list[SyntheticRecord]] = defaultdict(list)
    for record in records:
        by_stem[name_stem(record.name)].append(record)
    families: dict[str, list[SyntheticRecord]] = {}
    for stem, members in by_stem.items():
        if len(members) < 2:
            continue
        if any(_name_has_size(member.name) for member in members):
            families[stem] = members
    return families


def family_completeness_ratios(records: list[SyntheticRecord]) -> tuple[float, float, int]:
    """Return (complete_pct, incomplete_pct, family_member_n) among lexical family members."""
    families = lexical_family_groups(records)
    complete = 0
    incomplete = 0
    for members in families.values():
        sizes = {_suffix_size(member.name) for member in members}
        sizes.discard(None)
        if sizes == set(FAMILY_SIZES) and len(members) == len(FAMILY_SIZES):
            complete += len(members)
        else:
            incomplete += len(members)
    total = complete + incomplete
    if total == 0:
        return 0.0, 0.0, 0
    return 100.0 * complete / total, 100.0 * incomplete / total, total


def _split_incomplete(member_count: int) -> list[int]:
    if member_count < 2:
        return []
    for threes in range(member_count // 3, -1, -1):
        rest = member_count - 3 * threes
        if rest % 2 == 0:
            return [3] * threes + [2] * (rest // 2)
    return _split_incomplete(member_count - 1)


def _incomplete_pattern(length: int, seed: str, index: int) -> tuple[str, ...]:
    candidates = [pattern for pattern in INCOMPLETE_PATTERNS if len(pattern) == length]
    pick = int(unit_interval(f"{seed}\0incomplete\0{index}") * len(candidates))
    return candidates[min(pick, len(candidates) - 1)]


def _pick_bucket(remaining: list[int], need: int) -> int | None:
    fit = [index for index, left in enumerate(remaining) if left >= need]
    if not fit:
        return None
    return max(fit, key=lambda index: (remaining[index], -index))


def _name_has_size(name: str) -> bool:
    tokens = normalize_name(name).split()
    return bool(tokens) and _is_size_token(tokens[-1])


def _suffix_size(name: str) -> str | None:
    tokens = name.split()
    if not tokens:
        return None
    folded = normalize_name(tokens[-1])
    for size in FAMILY_SIZES:
        if folded == size.casefold():
            return size
    return None


def assert_family_copy_consistent(records: list[SyntheticRecord]) -> None:
    for stem, members in lexical_family_groups(records).items():
        descriptions = {member.description for member in members}
        collections = {member.collection_name for member in members}
        if len(descriptions) != 1:
            raise ValidationError(f"Family {stem!r} mixes descriptions.")
        if len(collections) != 1:
            raise ValidationError(f"Family {stem!r} mixes collection_name.")
        sizes = [_suffix_size(member.name) for member in members]
        if any(size is None for size in sizes):
            raise ValidationError(f"Family {stem!r} has a member without a size suffix.")
        if len(set(sizes)) != len(members):
            raise ValidationError(f"Family {stem!r} repeats a size.")
        prices = {member.price for member in members}
        if len(prices) == 1 and len(members) > 1:
            raise ValidationError(f"Family {stem!r} repeats the same price across sizes.")


def assert_family_completeness(
    records: list[SyntheticRecord],
    *,
    complete_ratio: float = COMPLETE_FAMILY_PRODUCT_RATIO,
    tolerance_pp: float = RATIO_TOLERANCE_PP,
) -> None:
    complete_pct, _, total = family_completeness_ratios(records)
    if total == 0:
        raise ValidationError("Expected lexical size families, found none.")
    target = 100.0 * complete_ratio
    if abs(complete_pct - target) > tolerance_pp:
        raise ValidationError(
            f"Complete-family products are {complete_pct:.2f}% "
            f"(target {target:.0f}% ±{tolerance_pp:g} pp)."
        )


def assert_unassigned_ratio(
    records: list[SyntheticRecord],
    *,
    ratio: float = UNASSIGNED_RATIO,
    tolerance_pp: float = RATIO_TOLERANCE_PP,
) -> None:
    if not records:
        raise ValidationError("Synthetic corpus is empty.")
    unassigned = sum(1 for record in records if not record.collection_name.strip())
    actual = 100.0 * unassigned / len(records)
    target = 100.0 * ratio
    if abs(actual - target) > tolerance_pp:
        raise ValidationError(
            f"Unassigned products are {actual:.2f}% (target {target:.0f}% ±{tolerance_pp:g} pp)."
        )
