"""Query-side synonym dictionary and expansion. Delivered by C20.

Two layers. `jbg_ai.enrichment.vocabularies` supplies the base equivalence classes
and is never modified from here; `query_synonyms.yaml` overlays what must not enter
the extraction contract. See `openspec/changes/add-synonym-dictionary/design.md`.

Nothing in this module performs I/O beyond reading its own packaged YAML: no database
session, no provider call, no socket. C21 turns the groups into a `tsquery`; C20 does
not, because `ts_rank` cannot tell the operator's own word from a synonym once they
are OR-ed into one query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from jbg_ai.enrichment.vocab import Vocabularies, fold, load_vocabularies

OVERLAY_RESOURCE = "query_synonyms.yaml"

# Order matters and is deliberate: a term that is a canonical of some vocabulary
# reports as that canonical rather than as another vocabulary's synonym. Canonicals
# of every field are registered before any synonym, so `dorado` resolves to the
# colour it is rather than to the plating it also names — an ambiguity the bridge
# in the overlay then removes for emission anyway.
VOCABULARY_FIELDS = (
    "piece_type",
    "materials",
    "stone_type",
    "size_label",
    "color_tags",
    "style_tags",
    "occasion_tags",
)

_PLURAL_SUFFIXES = ("es", "s")
_MIN_SINGULAR_STEM = 3
_EDGE_PUNCTUATION = re.compile(r"^[^0-9A-Za-zÀ-ÿ]+|[^0-9A-Za-zÀ-ÿ]+$")

ClassKey = tuple[str, str]
"""`(vocabulary field, canonical term)` — identifies one equivalence class."""


class SynonymDictionaryError(ValueError):
    """The overlay contradicts the base, or names something the base does not know."""


@dataclass(frozen=True)
class TermMatch:
    """What one query term resolved to. C21 reads this to extract rule-based filters."""

    term: str
    field: str
    canonical: str


@dataclass(frozen=True)
class ExpandedQuery:
    """Equivalence groups, never a rewritten query string.

    `original` travels so the consumer can rank the operator's own phrasing as its own
    list and fuse: measured on this corpus, a single widened `tsquery` pushes the three
    products literally named "Sortija" out of the top ten.
    """

    original: str
    groups: tuple[tuple[str, ...], ...]
    matched: tuple[TermMatch, ...]


@dataclass(frozen=True)
class SynonymDictionary:
    """Folded lookup to a class, and the surface forms that class emits.

    Lookup is folded so a query typed without diacritics resolves. Emission is *not*
    folded: the Spanish configuration folds acute accents but leaves `ñ` alone, so
    `bano` stems to 'ban' and never meets 'bañ'.
    """

    lookup: dict[str, ClassKey]
    forms: dict[ClassKey, tuple[str, ...]]
    max_phrase_words: int

    def resolve(self, folded_phrase: str) -> ClassKey | None:
        return self.lookup.get(folded_phrase)

    def forms_for(self, key: ClassKey) -> tuple[str, ...]:
        return self.forms.get(key, ())


def singular_candidates(folded_token: str) -> tuple[str, ...]:
    """Plural reductions worth trying. Applied only when the result is in the dictionary."""
    out: list[str] = []
    for suffix in _PLURAL_SUFFIXES:
        if folded_token.endswith(suffix) and len(folded_token) - len(suffix) >= _MIN_SINGULAR_STEM:
            out.append(folded_token[: -len(suffix)])
    return tuple(out)


def _dedup_surface(values: list[str]) -> tuple[str, ...]:
    """First occurrence wins, so the operator's own form leads the group.

    Deduplication is by case only, never by `fold`. Folding here would be the exact
    bug this dictionary exists to avoid: `bano de oro` and `baño de oro` fold to the
    same key, so the typed unaccented form would suppress the accented one — and
    'ban' never meets 'bañ' in the Spanish configuration, so the group would stop
    reaching the 38 documents it was expanded to reach.
    """
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = value.strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return tuple(out)


def _base_layer(vocabs: Vocabularies) -> tuple[dict[str, ClassKey], dict[ClassKey, list[str]]]:
    lookup: dict[str, ClassKey] = {}
    forms: dict[ClassKey, list[str]] = {}
    for field in VOCABULARY_FIELDS:
        for canonical in vocabs.field(field).canonical:
            key = (field, canonical)
            forms.setdefault(key, [canonical])
            lookup.setdefault(fold(canonical), key)
    for field in VOCABULARY_FIELDS:
        for folded_synonym, canonical in vocabs.field(field).synonyms.items():
            key = (field, canonical)
            if key in forms:
                lookup.setdefault(folded_synonym, key)
    return lookup, forms


def _require_known_class(key: ClassKey, forms: dict[ClassKey, list[str]], where: str) -> None:
    if key not in forms:
        raise SynonymDictionaryError(
            f"{where} anchors '{key[1]}' in field '{key[0]}', which the enrichment "
            "vocabulary does not define. A term the base does not know is a vocabulary "
            "gap, not a synonym: it belongs to `fix-enrichment-vocabulary-gaps`."
        )


def _apply_overlay(
    payload: dict[str, Any],
    lookup: dict[str, ClassKey],
    forms: dict[ClassKey, list[str]],
) -> None:
    for entry in payload.get("classes") or ():
        key: ClassKey = (str(entry["field"]), str(entry["canonical"]))
        _require_known_class(key, forms, "overlay class")
        for form in entry.get("forms") or ():
            surface = str(form)
            folded = fold(surface)
            if not folded:
                continue
            existing = lookup.get(folded)
            if existing is not None and existing != key:
                raise SynonymDictionaryError(
                    f"overlay form '{surface}' would reassign '{existing[1]}' "
                    f"(field '{existing[0]}') to '{key[1]}' (field '{key[0]}'). The "
                    "overlay may add surface forms, never reassign a base canonical."
                )
            lookup[folded] = key
            if surface not in forms[key]:
                forms[key].append(surface)

    # Bridges donate from a snapshot taken before any of them runs. Donating from the
    # live state would let direction leak transitively: with `dorado` widened towards
    # `oro` first, a later bridge from `baño de oro` towards `dorado` would inherit
    # `oro` too — which is exactly the direction measured and rejected.
    before_bridges = {key: tuple(value) for key, value in forms.items()}
    for bridge in payload.get("bridges") or ():
        widened = [(str(a["field"]), str(a["canonical"])) for a in bridge.get("widens") or ()]
        sources = [(str(a["field"]), str(a["canonical"])) for a in bridge.get("with") or ()]
        for key in (*widened, *sources):
            _require_known_class(key, forms, "overlay bridge")
        donated = [form for key in sources for form in before_bridges[key]]
        for key in widened:
            forms[key] = list(_dedup_surface([*forms[key], *donated]))


def build_dictionary(vocabs: Vocabularies, overlay: dict[str, Any]) -> SynonymDictionary:
    """Merge base and overlay. Raises `SynonymDictionaryError` on a contradiction."""
    lookup, forms = _base_layer(vocabs)
    _apply_overlay(overlay, lookup, forms)
    max_words = max((len(phrase.split()) for phrase in lookup), default=1)
    return SynonymDictionary(
        lookup=lookup,
        forms={key: tuple(value) for key, value in forms.items()},
        max_phrase_words=max_words,
    )


def load_overlay_from_path(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise SynonymDictionaryError(f"overlay file must be a mapping: {path}")
    return payload


@lru_cache(maxsize=1)
def load_query_dictionary() -> SynonymDictionary:
    """Load once per process, mirroring `load_vocabularies`."""
    resource = files("jbg_ai.retrieval").joinpath(OVERLAY_RESOURCE)
    overlay = load_overlay_from_path(Path(str(resource)))
    return build_dictionary(load_vocabularies(), overlay)


def _surface(token: str) -> str:
    """Trim edge punctuation so a comma does not travel into the emitted group."""
    return _EDGE_PUNCTUATION.sub("", token) or token


def _match_at(
    tokens: list[str], start: int, dictionary: SynonymDictionary
) -> tuple[ClassKey | None, int]:
    """Longest phrase first, so `aro de dedo` -> anillo beats `aro` -> pendientes."""
    widest = min(dictionary.max_phrase_words, len(tokens) - start)
    for span in range(widest, 0, -1):
        phrase = " ".join(tokens[start : start + span])
        key = dictionary.resolve(fold(phrase))
        if key is not None:
            return key, span
    folded = fold(tokens[start])
    for candidate in singular_candidates(folded):
        key = dictionary.resolve(candidate)
        if key is not None:
            return key, 1
    return None, 1


def expand_query(
    text: str,
    *,
    enabled: bool,
    dictionary: SynonymDictionary | None = None,
) -> ExpandedQuery:
    """Expand the operator query into equivalence groups. Pure: no database, no provider.

    With `enabled` false every token becomes a single-element group carrying its own
    form, which is the ablation arm C24 needs and the rollback for this change.
    """
    tokens = text.split()
    if not enabled:
        return ExpandedQuery(
            original=text,
            groups=tuple((_surface(token),) for token in tokens),
            matched=(),
        )

    resolved = dictionary if dictionary is not None else load_query_dictionary()
    groups: list[tuple[str, ...]] = []
    matched: list[TermMatch] = []
    index = 0
    while index < len(tokens):
        key, span = _match_at(tokens, index, resolved)
        phrase = _surface(" ".join(tokens[index : index + span]))
        if key is None:
            groups.append((phrase,))
        else:
            groups.append(_dedup_surface([phrase, *resolved.forms_for(key)]))
            matched.append(TermMatch(term=phrase, field=key[0], canonical=key[1]))
        index += span
    return ExpandedQuery(original=text, groups=tuple(groups), matched=tuple(matched))
