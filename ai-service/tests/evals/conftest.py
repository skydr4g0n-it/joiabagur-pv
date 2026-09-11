"""Fixtures for the evaluation harness. Nothing here opens a socket or a database.

The whole battery runs offline: metric computation, golden-set validation, pooling, the
baselines' SQL composition and report generation are exercised against fixtures and doubles.
That is a requirement of the change and not a convenience — an evaluation suite that needed a
provider would be skipped on the machine that has no key, which is every machine but one.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest

from jbg_ai.evals.golden import GoldenSet, load_golden_set

#: Deterministic identifiers, ordered so a test about truncation can say which one survives.
P1 = UUID("11111111-1111-1111-1111-111111111111")
P2 = UUID("22222222-2222-2222-2222-222222222222")
P3 = UUID("33333333-3333-3333-3333-333333333333")
P4 = UUID("44444444-4444-4444-4444-444444444444")

HASH = "0" * 64


def _query(
    qid: str,
    text: str,
    category: str,
    **extra: object,
) -> dict:
    return {
        "id": qid,
        "text": text,
        "category": category,
        "in_tuning_set": extra.pop("in_tuning_set", False),
        "judged": extra.pop("judged", True),
        "judged_depth": 20,
        **extra,
    }


def _judgement(qid: str, product_id: str, grade: int, **extra: object) -> dict:
    return {
        "query_id": qid,
        "product_id": product_id,
        "grade": grade,
        "pooled_in": ["v2-hibrido"],
        "judged_at": "2026-09-07",
        "source_hash": HASH,
        "data_origin": extra.pop("data_origin", "real"),
        "lexically_reachable": extra.pop("lexically_reachable", True),
        **extra,
    }


def _minimal_set() -> tuple[list[dict], list[dict]]:
    """A golden set that satisfies every requirement, and only just.

    Built at the minimums on purpose: a fixture with comfortable margins would pass every test
    even after a requirement stopped being checked.
    """
    queries: list[dict] = []
    judgements: list[dict] = []

    # 12 unanchored: a maximum-grade document the lexical branch cannot reach.
    for index in range(12):
        qid = f"u{index:02d}"
        queries.append(_query(qid, f"consulta descriptiva {index}", "descripcion-sin-anclaje"))
        judgements.append(
            _judgement(qid, f"{index:08d}-0000-0000-0000-000000000000", 2, lexically_reachable=False)
        )

    # 5 subjective: resolve to a sparse field and to no high-coverage one.
    for index, text in enumerate(
        ["algo para una boda", "un regalo", "estilo marino", "para diario", "algo vintage"]
    ):
        qid = f"s{index:02d}"
        queries.append(_query(qid, text, "subjetiva"))
        judgements.append(_judgement(qid, f"a{index:07d}-0000-0000-0000-000000000000", 2))

    # 4 stones, four different ones, with a piece type that cannot be what selects the answer.
    for index, (text, stone) in enumerate(
        [
            ("anillo con onix", "onix"),
            ("colgante de lapislazuli", "lapislazuli"),
            ("pendientes de perla", "perla"),
            ("pulsera de coral", "coral"),
        ]
    ):
        qid = f"p{index:02d}"
        queries.append(_query(qid, text, "piedra", isolates_stone=stone))
        judgements.append(_judgement(qid, f"b{index:07d}-0000-0000-0000-000000000000", 2))

    # 6 synonyms, two per dictionary class.
    for index, (text, kind) in enumerate(
        [
            ("bano de oro", "stemmer"),
            ("anillo pequeno", "stemmer"),
            ("dije de plata", "commercial"),
            ("un choker de plata", "commercial"),
            ("gargantilla dorada", "bridge"),
            ("pulsera dorada", "bridge"),
        ]
    ):
        qid = f"y{index:02d}"
        queries.append(_query(qid, text, "sinonimos", synonym_kind=kind))
        judgements.append(_judgement(qid, f"c{index:07d}-0000-0000-0000-000000000000", 2))

    # 5 out of domain: plausible, and with nothing relevant at all.
    for index, text in enumerate(
        [
            "un reloj de plata sumergible",
            "piercing de ombligo de acero quirurgico",
            "un rosario de plata",
            "un dedal de plata de coleccion",
            "una hucha de plata para bautizo",
        ]
    ):
        qid = f"o{index:02d}"
        queries.append(_query(qid, text, "fuera-de-dominio"))
        judgements.append(_judgement(qid, f"d{index:07d}-0000-0000-0000-000000000000", 0))

    # 4 literals.
    for index, literal in enumerate(["SKU355", "SKU98", "Anillo Bruma simple", "Colgante ancla"]):
        qid = f"l{index:02d}"
        queries.append(_query(qid, literal, "lexico-exacto", literal_of=literal))
        judgements.append(_judgement(qid, f"e{index:07d}-0000-0000-0000-000000000000", 2))

    # Padding to the declared floor, with the categories the design leaves unconstrained.
    for index in range(45 - len(queries)):
        qid = f"v{index:02d}"
        queries.append(_query(qid, f"anillo talla {index}", "variante-talla"))
        judgements.append(_judgement(qid, f"f{index:07d}-0000-0000-0000-000000000000", 2))

    return queries, judgements


def _write(root: Path, queries: list[dict], judgements: list[dict]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "criterion.md").write_text("# criterio\n\n2 / 1 / 0\n", encoding="utf-8")
    (root / "queries.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in queries) + "\n",
        encoding="utf-8",
    )
    (root / "judgements.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in judgements) + "\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def golden_factory(tmp_path: Path) -> Callable[..., Path]:
    """Write a valid golden set, optionally mutated, and return its directory."""

    def _build(
        *,
        mutate_queries: Callable[[list[dict]], list[dict]] | None = None,
        mutate_judgements: Callable[[list[dict]], list[dict]] | None = None,
        criterion: bool = True,
    ) -> Path:
        queries, judgements = _minimal_set()
        if mutate_queries is not None:
            queries = mutate_queries(queries)
        if mutate_judgements is not None:
            judgements = mutate_judgements(judgements)
        root = _write(tmp_path / "golden", queries, judgements)
        if not criterion:
            (root / "criterion.md").unlink()
        return root

    return _build


@pytest.fixture
def valid_golden(golden_factory: Callable[..., Path]) -> GoldenSet:
    return load_golden_set(golden_factory())
