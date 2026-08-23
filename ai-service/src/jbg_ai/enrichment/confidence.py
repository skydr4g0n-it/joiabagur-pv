"""Evidence-span confidence. The model's own score is never copied."""

from __future__ import annotations

from jbg_ai.enrichment.constants import (
    CONFIDENCE_ABSENT,
    CONFIDENCE_NO_SPAN,
    CONFIDENCE_SPAN,
)
from jbg_ai.enrichment.vocab import ClosedVocab, fold


def _blob(name: str | None, description: str | None) -> str:
    joined = f"{name or ''} {description or ''}"
    return f" {fold(joined)} "


def has_span(name: str | None, description: str | None, value: str, vocab: ClosedVocab) -> bool:
    haystack = _blob(name, description)
    for phrase in vocab.phrases_for(value):
        if f" {phrase} " in haystack:
            return True
    return False


def scalar_confidence(
    value: str | None,
    *,
    name: str | None,
    description: str | None,
    vocab: ClosedVocab,
) -> float:
    if value is None:
        return CONFIDENCE_ABSENT
    if has_span(name, description, value, vocab):
        return CONFIDENCE_SPAN
    return CONFIDENCE_NO_SPAN


def list_confidence(
    values: list[str],
    *,
    name: str | None,
    description: str | None,
    vocab: ClosedVocab,
) -> float:
    if not values:
        return CONFIDENCE_ABSENT
    return min(
        scalar_confidence(item, name=name, description=description, vocab=vocab)
        for item in values
    )
