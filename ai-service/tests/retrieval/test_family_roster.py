"""`family_roster`, the port method C30a adds. Delivered for the variants warning and C32.

Offline over `FakeProductSearch`, plus one Testcontainers test that runs the real statement
and skips itself when no Docker daemon is reachable.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
import sqlalchemy as sa

from jbg_ai.assist.constants import FAMILY_ROSTER_CAP
from jbg_ai.retrieval.search import FAMILY_ROSTER_SQL, SqlAlchemyProductSearch
from support.async_db import run_db
from support.fake_product_search import FakeIndexedRow, FakeProductSearch
from support.settings import build_settings

FAMILY = UUID("11111111-1111-1111-1111-111111111111")
OTHER = UUID("22222222-2222-2222-2222-222222222222")


def _run(coro):
    return asyncio.run(coro)


def _row(suffix: int, **kwargs) -> FakeIndexedRow:
    values = {
        "product_id": UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-{suffix:012d}"),
        "sku": f"JBG-{suffix:04d}",
        "distance": 0.2,
        "family_id": FAMILY,
        "variant_label": f"{16 + suffix} mm",
        "materials": ["plata"],
        "size_label": "M",
    }
    values.update(kwargs)
    return FakeIndexedRow(**values)


def test_family_roster_returns_only_the_members_of_that_family() -> None:
    search = FakeProductSearch([_row(1), _row(2), _row(3, family_id=OTHER), _row(4, family_id=None)])

    members = _run(search.family_roster(FAMILY, cap=FAMILY_ROSTER_CAP))

    assert [member.sku for member in members] == ["JBG-0001", "JBG-0002"]


def test_family_roster_carries_the_variant_label_and_the_family_name() -> None:
    search = FakeProductSearch([_row(1, family_name="Aro Menorca")])

    member = _run(search.family_roster(FAMILY, cap=FAMILY_ROSTER_CAP))[0]

    assert member.variant_label == "17 mm"
    assert member.family_name == "Aro Menorca"
    assert member.size_label == "M"
    assert member.materials == ["plata"]


def test_family_roster_drops_inactive_members() -> None:
    """A discontinued variant is not one the operator can offer, so it must not be counted."""
    search = FakeProductSearch([_row(1), _row(2, is_active=False)])

    assert [member.sku for member in _run(search.family_roster(FAMILY, cap=10))] == ["JBG-0001"]


def test_family_roster_respects_the_declared_cap() -> None:
    search = FakeProductSearch([_row(index) for index in range(1, 9)])

    assert len(_run(search.family_roster(FAMILY, cap=3))) == 3
    assert len(_run(search.family_roster(FAMILY, cap=FAMILY_ROSTER_CAP))) == 8


def test_family_roster_cap_is_a_declared_value_with_measured_slack() -> None:
    """Measured 2026-09-13 on the live index: 156 families, largest holds 8 members."""
    assert FAMILY_ROSTER_CAP == 24
    assert FAMILY_ROSTER_CAP >= 3 * 8


def test_family_roster_truncates_under_the_statement_order() -> None:
    """Unlabelled variants sort last, so a cap drops them before a labelled sibling."""
    search = FakeProductSearch([_row(1), _row(2, variant_label=None), _row(3)])

    members = _run(search.family_roster(FAMILY, cap=2))

    assert [member.variant_label for member in members] == ["17 mm", "19 mm"]


def test_family_roster_of_an_unknown_family_is_empty_and_not_an_error() -> None:
    search = FakeProductSearch([_row(1)])

    assert _run(search.family_roster(OTHER, cap=10)) == []


# --- 4.4 · the statement reads the index schema and nothing else -------------------------


def test_family_roster_sql_reads_only_the_index_schema() -> None:
    assert "ai.product_document" in FAMILY_ROSTER_SQL
    assert "public." not in FAMILY_ROSTER_SQL
    # The projection is not read here at all, so no availability can leak through this door.
    assert "pos_projection" not in FAMILY_ROSTER_SQL
    assert "pos_id" not in FAMILY_ROSTER_SQL


def test_family_roster_sql_selects_neither_price_nor_stock() -> None:
    assert "price" not in FAMILY_ROSTER_SQL
    assert "stock" not in FAMILY_ROSTER_SQL
    assert "qty_bucket" not in FAMILY_ROSTER_SQL


def test_family_roster_sql_is_one_statement_with_a_bound_cap() -> None:
    assert FAMILY_ROSTER_SQL.count("SELECT") == 1
    assert FAMILY_ROSTER_SQL.strip().count(";") == 0
    assert "LIMIT :cap" in FAMILY_ROSTER_SQL


def test_family_roster_rejects_a_cap_below_one() -> None:
    port = SqlAlchemyProductSearch(build_settings(database_url=None))

    with pytest.raises(ValueError):
        _run(port.family_roster(FAMILY, cap=0))


# --- the real statement, against a real PostgreSQL ---------------------------------------


@pytest.mark.db
def test_family_roster_against_postgres(migrated: sa.Engine, database_url: str) -> None:
    """The real statement, the real ordering and the real cap. Skips without Docker."""
    with migrated.begin() as connection:
        for index, (family, label, active) in enumerate(
            [
                (FAMILY, "18 mm", True),
                (FAMILY, "20 mm", True),
                (FAMILY, None, True),
                (FAMILY, "22 mm", False),
                (OTHER, "18 mm", True),
            ]
        ):
            connection.execute(
                sa.text(
                    "INSERT INTO ai.product_document "
                    "(product_id, sku, name, doc_text, source_hash, materials, "
                    " family_id, family_name, variant_label, size_label, is_active, "
                    " data_origin, text_provenance) "
                    "VALUES (:pid, :sku, :name, :doc, :hash, CAST(:materials AS text[]), "
                    " :family, :family_name, :label, :size, :active, 'synthetic', 'synthetic')"
                ),
                {
                    "pid": UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-{index:012d}"),
                    "sku": f"JBG-{index:04d}",
                    "name": f"Pieza {index}",
                    "doc": f"Pieza {index} de plata.",
                    "hash": f"{index:064d}",
                    "materials": ["plata"],
                    "family": family,
                    "family_name": "Aro Menorca",
                    "label": label,
                    "size": "M",
                    "active": active,
                },
            )

    port = SqlAlchemyProductSearch(build_settings(database_url=database_url))

    async def scenario():
        # Both reads inside ONE loop: the engine is process-wide and its pooled
        # connections belong to the loop that opened them.
        return (
            await port.family_roster(FAMILY, cap=FAMILY_ROSTER_CAP),
            await port.family_roster(FAMILY, cap=2),
        )

    members, capped = run_db(scenario)

    # Inactive dropped, the other family never seen, and `NULLS LAST` honoured.
    assert [member.variant_label for member in members] == ["18 mm", "20 mm", None]
    assert {member.family_name for member in members} == {"Aro Menorca"}
    assert all(member.materials == ["plata"] for member in members)
    assert [member.variant_label for member in capped] == ["18 mm", "20 mm"]
