"""Design-collection briefs (name ≠ thought audience / POS). Delivered by C06b."""

from __future__ import annotations

from dataclasses import dataclass

from jbg_ai.data.constants import UNASSIGNED_RATIO
from jbg_ai.data.quality import unit_interval

# Ten lines: inside the 8–12 window. Two menorquin/marine, the rest diverge.
# Audiences are prompt + report metadata only — never Collection.Name.
# Theme conditions copy; it is not Collection.Name.
DEFAULT_BRIEFS: tuple[tuple[str, str, str], ...] = (
    (
        "El Jaleo",
        "turista",
        "Jaleo de cavalls de Menorca: caballos negros menorquines, fiesta "
        "ecuestre, riendas y plata de montura. No flamenco, no tablao, no lunares.",
    ),
    ("Fuego", "hotel", "Brasas, lava, ámbar y metal caliente."),
    ("Cielo estrellado", "atelier clásico", "Noche, constelaciones y plata fría."),
    ("La Pomada", "tienda clásica", "Bote de pomada, farmacia antigua, latón y vidrio."),
    ("Tramontana", "diseño menorquín", "Viento norte, acantilado y cielo limpio."),
    ("Caliza", "diseño menorquín / marino", "Piedra blanca, cala y salitre."),
    ("Umbra", "hotel", "Sombra, crepúsculo y oro oscuro."),
    ("Filigrana", "atelier clásico", "Hilo de plata, encaje y calado."),
    ("Marea viva", "aeropuerto / turista", "Marea, algas y espuma."),
    ("Coral negro", "hotel", "Coral negro, fondo marino y oro rosa."),
)

UNASSIGNED_AUDIENCE = "catálogo general"
UNASSIGNED_THEME = "Piezas sueltas sin línea editorial. No inventes una colección."


@dataclass(frozen=True)
class CollectionBrief:
    name: str
    audience: str
    theme: str = ""


def default_briefs() -> list[CollectionBrief]:
    return [
        CollectionBrief(name=name, audience=audience, theme=theme)
        for name, audience, theme in DEFAULT_BRIEFS
    ]


def unassigned_brief() -> CollectionBrief:
    return CollectionBrief(name="", audience=UNASSIGNED_AUDIENCE, theme=UNASSIGNED_THEME)


def unassigned_count(total: int, *, ratio: float = UNASSIGNED_RATIO) -> int:
    if total <= 0:
        return 0
    return min(total, round(ratio * total))


def distribute_uneven(total: int, bucket_count: int, seed: str) -> list[int]:
    """Split `total` across `bucket_count` with expressly unequal positive counts.

    When `total` is large enough for a strictly decreasing sequence of `bucket_count`
    positives (triangular number), every bucket gets a distinct count. Otherwise
    each bucket gets at least one if `total >= bucket_count`, and leftover is
    piled on the heaviest buckets (seed permutes which those are).
    """
    if bucket_count <= 0 or total <= 0:
        return [0] * max(bucket_count, 0)
    if total < bucket_count:
        counts = [0] * bucket_count
        for index in range(total):
            counts[index] = 1
        return _permute_counts(counts, seed)

    min_strict = bucket_count * (bucket_count + 1) // 2
    order = _bucket_order(bucket_count, seed)
    counts = [0] * bucket_count
    if total >= min_strict:
        base = list(range(bucket_count, 0, -1))
        surplus = total - min_strict
        weights = [(bucket_count - index) ** 2 for index in range(bucket_count)]
        extras = _largest_remainder(surplus, weights)
        ranked = [base[index] + extras[index] for index in range(bucket_count)]
    else:
        ranked = [1] * bucket_count
        extras = _largest_remainder(total - bucket_count, list(range(bucket_count, 0, -1)))
        ranked = [ranked[index] + extras[index] for index in range(bucket_count)]
    for rank, bucket_index in enumerate(order):
        counts[bucket_index] = ranked[rank]
    return counts


def _largest_remainder(total: int, weights: list[int]) -> list[int]:
    if total <= 0 or not weights:
        return [0] * len(weights)
    weight_sum = sum(weights)
    raw = [total * weight / weight_sum for weight in weights]
    result = [int(value) for value in raw]
    leftover = total - sum(result)
    order = sorted(range(len(weights)), key=lambda i: (raw[i] - result[i], -i), reverse=True)
    for index in order[:leftover]:
        result[index] += 1
    return result


def _bucket_order(bucket_count: int, seed: str) -> list[int]:
    return sorted(range(bucket_count), key=lambda i: (unit_interval(f"{seed}\0bucket\0{i}"), i))


def _permute_counts(counts: list[int], seed: str) -> list[int]:
    order = _bucket_order(len(counts), seed)
    ranked = sorted(counts, reverse=True)
    result = [0] * len(counts)
    for rank, bucket_index in enumerate(order):
        result[bucket_index] = ranked[rank]
    return result
