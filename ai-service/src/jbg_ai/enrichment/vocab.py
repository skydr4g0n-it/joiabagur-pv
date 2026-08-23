"""Closed-vocabulary load and synonym normalisation. Delivered by C09."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

VOCAB_RESOURCE = "vocabularies.yaml"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def fold(text: str) -> str:
    """Lowercase, strip accents, collapse punctuation to spaces."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(_NON_ALNUM.sub(" ", stripped.casefold()).split())


@dataclass(frozen=True)
class ClosedVocab:
    name: str
    canonical: tuple[str, ...]
    synonyms: dict[str, str]  # folded synonym -> canonical form

    def __post_init__(self) -> None:
        folded_canonical = {fold(term): term for term in self.canonical}
        object.__setattr__(self, "_folded_canonical", folded_canonical)

    @property
    def as_set(self) -> frozenset[str]:
        return frozenset(self.canonical)

    def resolve(self, raw: str | None) -> str | None:
        if raw is None:
            return None
        folded = fold(str(raw))
        if not folded:
            return None
        mapped = getattr(self, "_folded_canonical")
        if folded in mapped:
            return mapped[folded]  # type: ignore[no-any-return]
        return self.synonyms.get(folded)

    def phrases_for(self, canonical: str) -> tuple[str, ...]:
        """Canonical form plus synonyms that map to it, folded, longest first."""
        phrases = [fold(canonical)]
        phrases.extend(syn for syn, target in self.synonyms.items() if target == canonical)
        unique = tuple(dict.fromkeys(p for p in phrases if p))
        return tuple(sorted(unique, key=len, reverse=True))


@dataclass(frozen=True)
class Vocabularies:
    piece_type: ClosedVocab
    materials: ClosedVocab
    stone_type: ClosedVocab
    size_label: ClosedVocab
    color_tags: ClosedVocab
    style_tags: ClosedVocab
    occasion_tags: ClosedVocab

    def field(self, name: str) -> ClosedVocab:
        return getattr(self, name)  # type: ignore[no-any-return]


def _closed_vocab(name: str, payload: dict[str, Any]) -> ClosedVocab:
    terms = tuple(str(item) for item in payload.get("terms") or ())
    raw_synonyms = payload.get("synonyms") or {}
    folded_synonyms: dict[str, str] = {}
    canonical_by_fold = {fold(term): term for term in terms}
    for source, target in raw_synonyms.items():
        target_canonical = canonical_by_fold.get(fold(str(target)), str(target))
        folded_synonyms[fold(str(source))] = target_canonical
    return ClosedVocab(name=name, canonical=terms, synonyms=folded_synonyms)


def load_vocabularies_from_path(path: Path) -> Vocabularies:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"vocabularies file must be a mapping: {path}")
    return Vocabularies(
        piece_type=_closed_vocab("piece_type", payload["piece_type"]),
        materials=_closed_vocab("materials", payload["materials"]),
        stone_type=_closed_vocab("stone_type", payload["stone_type"]),
        size_label=_closed_vocab("size_label", payload["size_label"]),
        color_tags=_closed_vocab("color_tags", payload["color_tags"]),
        style_tags=_closed_vocab("style_tags", payload["style_tags"]),
        occasion_tags=_closed_vocab("occasion_tags", payload["occasion_tags"]),
    )


@lru_cache(maxsize=1)
def load_vocabularies() -> Vocabularies:
    resource = files("jbg_ai.enrichment").joinpath(VOCAB_RESOURCE)
    return load_vocabularies_from_path(Path(str(resource)))


def normalize_value(raw: str | None, vocab: ClosedVocab) -> str | None:
    return vocab.resolve(raw)
