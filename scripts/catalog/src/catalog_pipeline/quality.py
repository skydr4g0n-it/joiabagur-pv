from __future__ import annotations

import hashlib
from collections import Counter

from catalog_pipeline.constants import (
    DEFAULT_SEED,
    RATIO_TOLERANCE_PP,
    RICH_CUTOFF,
    SPARSE_CUTOFF,
    TARGET_RATIOS,
)
from catalog_pipeline.errors import RatioError
from catalog_pipeline.models import QualityAssignment, TextQualityTier


def unit_interval(group_key: str, seed: str = DEFAULT_SEED) -> float:
    digest = hashlib.sha256(f"{seed}\0{group_key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def bucket_for(group_key: str, seed: str = DEFAULT_SEED) -> TextQualityTier:
    value = unit_interval(group_key, seed)
    if value < RICH_CUTOFF:
        return "rich"
    if value < SPARSE_CUTOFF:
        return "sparse"
    return "original"


def assignment_for(group_key: str, seed: str = DEFAULT_SEED) -> QualityAssignment:
    tier = bucket_for(group_key, seed)
    if tier == "original":
        return QualityAssignment(text_quality_tier="original", text_provenance="merchant")
    return QualityAssignment(text_quality_tier=tier, text_provenance="ai_assisted")


def assign_quality(
    sku_to_group: dict[str, str],
    seed: str = DEFAULT_SEED,
    *,
    rebalance: bool | None = None,
) -> dict[str, QualityAssignment]:
    group_assignment = {key: assignment_for(key, seed) for key in set(sku_to_group.values())}
    assigned = {sku: group_assignment[group_key] for sku, group_key in sku_to_group.items()}
    if rebalance is None:
        rebalance = len(sku_to_group) >= 400
    if rebalance:
        return rebalance_assignments(sku_to_group, assigned)
    return assigned


def rebalance_assignments(
    sku_to_group: dict[str, str],
    assigned: dict[str, QualityAssignment],
    *,
    targets: dict[str, float] | None = None,
    tolerance_pp: float = RATIO_TOLERANCE_PP,
) -> dict[str, QualityAssignment]:
    """Move whole families so product-level ratios fall inside ±tolerance.

    The hash buckets of 0.70 / 0.90 stay the default. When family sizes
    weight a bucket outside the product-level window, the smallest families
    are moved first (then by group key) — still one tier per group.
    """
    expected = targets or TARGET_RATIOS
    members_by_group: dict[str, list[str]] = {}
    for sku, group_key in sku_to_group.items():
        members_by_group.setdefault(group_key, []).append(sku)

    current = dict(assigned)

    def current_ratios() -> dict[str, float]:
        return ratios_by_tier([current[sku].text_quality_tier for sku in sku_to_group])

    for _ in range(len(members_by_group)):
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
            for key, members in members_by_group.items()
            if current[members[0]].text_quality_tier == source
        ]
        if not candidates:
            break
        _, move_key = min(candidates)
        moved = QualityAssignment(
            text_quality_tier=destination,  # type: ignore[arg-type]
            text_provenance="merchant" if destination == "original" else "ai_assisted",
        )
        for sku in members_by_group[move_key]:
            current[sku] = moved
    return current


def counts_by_tier(tiers: list[TextQualityTier]) -> dict[str, int]:
    counter = Counter(tiers)
    return {name: int(counter.get(name, 0)) for name in ("rich", "sparse", "original")}


def ratios_by_tier(tiers: list[TextQualityTier]) -> dict[str, float]:
    total = len(tiers)
    if total == 0:
        return {name: 0.0 for name in ("rich", "sparse", "original")}
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
