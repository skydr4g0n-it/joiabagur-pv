"""Deterministic size extraction from name, then description. Never the SKU."""

from __future__ import annotations

import re
from dataclasses import dataclass

from jbg_ai.enrichment.constants import CONFIDENCE_RULE
from jbg_ai.enrichment.vocab import fold

_LETTER_CANONICAL = {
    "xxs": "XXS",
    "xs": "XS",
    "s": "S",
    "m": "M",
    "l": "L",
    "xl": "XL",
    "xxl": "XXL",
}
_WORD_CANONICAL = {
    "extramini": "extramini",
    "mini": "mini",
    "pequeno": "pequeno",
    "pequena": "pequeno",
    "pequenas": "pequeno",
    "mediano": "mediano",
    "mediana": "mediano",
    "medianas": "mediano",
    "grande": "grande",
    "grandes": "grande",
}
_MEASURE_RE = re.compile(r"^(\d+)(mm|cm)$")
_NUMERIC_RE = re.compile(r"^\d+$")


@dataclass(frozen=True)
class SizeHit:
    value: str
    source: str = "rule"
    confidence: float = CONFIDENCE_RULE


def _canonical_for_token(token: str) -> str | None:
    if token in _WORD_CANONICAL:
        return _WORD_CANONICAL[token]
    if token in _LETTER_CANONICAL:
        return _LETTER_CANONICAL[token]
    measure = _MEASURE_RE.match(token)
    if measure:
        return f"{measure.group(1)}{measure.group(2)}"
    if _NUMERIC_RE.match(token):
        number = int(token)
        if 5 <= number <= 48:
            return token
    return None


def _scan(text: str | None) -> SizeHit | None:
    if not text or not text.strip():
        return None
    for token in fold(text).split():
        canonical = _canonical_for_token(token)
        if canonical is not None:
            return SizeHit(value=canonical)
    return None


def extract_size(name: str | None, description: str | None) -> SizeHit | None:
    """Prefer Name over Description. The SKU is never an argument on purpose."""
    hit = _scan(name)
    if hit is not None:
        return hit
    return _scan(description)
