from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from catalog_pipeline.models import FamilySeed, Grouping, SourceRow

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
_MATERIAL_TOKENS = frozenset(
    {
        "oro",
        "plata",
        "dorado",
        "dorados",
        "dorada",
        "dorado",
    }
)
_COMPOUND_SUFFIXES = (("plata", "y", "oro"),)
_MEASURE_RE = re.compile(r"^\d+(?:mm|cm)$")
_NUMERIC_RE = re.compile(r"^\d+$")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_name(name: str) -> str:
    folded = strip_accents(name).casefold()
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return " ".join(folded.split())


def _slug(tokens: list[str]) -> str:
    return "-".join(tokens) if tokens else "producto"


def _is_size_token(token: str) -> bool:
    if token in _SIZE_TOKENS:
        return True
    if _MEASURE_RE.match(token):
        return True
    if _NUMERIC_RE.match(token) and 5 <= int(token) <= 48:
        return True
    return False


def _is_material_token(token: str) -> bool:
    return token in _MATERIAL_TOKENS


def _is_suffix_token(token: str) -> bool:
    return _is_size_token(token) or _is_material_token(token)


def extract_variant_suffix(normalized: str) -> tuple[str, str | None]:
    """Split a normalised name into (stem, variant_label).

    Peel a trailing run of size / material tokens. Material-only tails stay
    in the stem so «oro» / «plata» of the same motif do not collapse unless
    a size token is also present (e.g. ``S oro``).
    """
    tokens = normalized.split()
    if not tokens:
        return "", None

    cut = len(tokens)
    while cut > 0:
        if cut >= 3 and tuple(tokens[cut - 3 : cut]) in _COMPOUND_SUFFIXES:
            cut -= 3
            continue
        if _is_suffix_token(tokens[cut - 1]):
            cut -= 1
            continue
        break

    stem_tokens = tokens[:cut]
    suffix = tokens[cut:]
    suffix_has_size = any(_is_size_token(token) for token in suffix)
    if suffix and not suffix_has_size:
        stem_tokens = tokens
        suffix = []

    if not stem_tokens:
        restored = suffix[:1] or ["producto"]
        leftover = suffix[1:]
        return _slug(restored), " ".join(leftover) if leftover else None
    label = " ".join(suffix) if suffix else None
    return _slug(stem_tokens), label


def group_products(rows: list[SourceRow]) -> dict[str, Grouping]:
    """Deterministic stem + suffix grouping. Same input → same maps."""
    stems: dict[str, tuple[str, str | None]] = {}
    buckets: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        stem, label = extract_variant_suffix(normalize_name(row.name))
        stems[row.sku] = (stem, label)
        buckets[stem].append(row.sku)

    result: dict[str, Grouping] = {}
    for sku, (stem, label) in stems.items():
        members = tuple(sorted(buckets[stem]))
        if len(members) == 1:
            emitted_label = None
        else:
            emitted_label = label
        result[sku] = Grouping(
            variant_group_key=stem,
            variant_label=emitted_label,
            family_seed=FamilySeed(group_key=stem, member_skus=members),
        )
    return result


def grouping_counts(groupings: dict[str, Grouping]) -> dict[str, int]:
    keys = {item.variant_group_key for item in groupings.values()}
    multi = {
        item.variant_group_key
        for item in groupings.values()
        if len(item.family_seed.member_skus) > 1
    }
    return {
        "group_count": len(keys),
        "multi_variant_count": len(multi),
        "unary_count": len(keys) - len(multi),
        "product_count": len(groupings),
    }
