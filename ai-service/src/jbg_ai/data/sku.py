"""SKU allocator: same magnitude scheme as the C06a real catalog, from 437."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from jbg_ai.data.constants import SKU_MAX_LEN, SKU_START
from jbg_ai.data.errors import ValidationError

_SKU_RE = re.compile(r"^SKU(?:[1-9]\d{3}|[1-9]\d{2}|0[1-9]|[1-9]\d)$")


def format_sku(number: int) -> str:
    """Format `SKU` + 2/3/4 digits according to magnitude.

    n < 100 → `SKU01`…`SKU99`; n < 1000 → `SKU100`…`SKU999`; else `SKU1000`…
    """
    if number < 1:
        raise ValidationError(f"SKU number must be >= 1, got {number}.")
    if number < 100:
        sku = f"SKU{number:02d}"
    elif number < 10_000:
        sku = f"SKU{number}"
    else:
        raise ValidationError(f"SKU number {number} needs more than 4 digits.")
    if len(sku) > SKU_MAX_LEN:
        raise ValidationError(f"{sku!r} exceeds SKU max length {SKU_MAX_LEN}.")
    return sku


def is_real_scheme_sku(sku: str) -> bool:
    """True when `sku` matches the real-catalog magnitude scheme (no SYN- prefix)."""
    return bool(_SKU_RE.fullmatch(sku))


def parse_sku_number(sku: str) -> int:
    if not sku.startswith("SKU"):
        raise ValidationError(f"SKU {sku!r} does not use the real scheme.")
    rest = sku[3:]
    if not rest.isdigit():
        raise ValidationError(f"SKU {sku!r} is not numeric after the prefix.")
    return int(rest)


def occupied_skus_from_jsonl(path: Path) -> set[str]:
    occupied: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            sku = payload.get("sku")
            if not sku:
                raise ValidationError(f"{path}:{line_no}: missing sku.")
            occupied.add(str(sku))
    return occupied


def allocate_skus(
    count: int,
    occupied: Iterable[str],
    *,
    seed: str,
    start: int = SKU_START,
) -> list[str]:
    """Reserve `count` unused SKUs starting at `start` (437), skipping occupied.

    The C06a JSONL has 436 products but the highest number is 439, so the
    first free identifier is `SKU440`. `seed` is part of the public contract
    (same seed + same occupied → same sequence). Sequential, no SYN- prefix.
    """
    if count < 0:
        raise ValidationError("SKU count must be >= 0.")
    _ = seed
    taken = {item.strip() for item in occupied if item and item.strip()}
    reserved: list[str] = []
    number = start
    while len(reserved) < count:
        candidate = format_sku(number)
        if candidate not in taken:
            reserved.append(candidate)
            taken.add(candidate)
        number += 1
    return reserved
