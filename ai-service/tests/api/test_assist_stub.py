"""Sale assistance stub contract tests (no LLM / embeddings / RDS)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from jbg_ai.api.schemas.assist import AssistResponse
from jbg_ai.api.schemas.common import PRICE_PLACEHOLDER, STOCK_PLACEHOLDER

#: Any bare number followed by a currency mark would mean Python resolved a price.
PRICE_LIKE = re.compile(r"\d+[.,]?\d*\s*(€|eur|euros)", re.IGNORECASE)


def test_assist_sale_groups_by_family(
    client: TestClient, auth_headers: dict[str, str], forbid_network: None
) -> None:
    response = client.post(
        "/v1/assist/sale",
        json={"query": "regalo para mi madre", "top_k": 3},
        headers=auth_headers,
    )

    assert response.status_code == 200
    parsed = AssistResponse.model_validate(response.json())

    assert parsed.groups
    for group in parsed.groups:
        assert group.family_id
        assert group.members
        for member in group.members:
            # variant_label may be null, but the field is always part of the contract.
            assert "variant_label" in member.model_dump()

    assert PRICE_PLACEHOLDER in parsed.pitch
    assert STOCK_PLACEHOLDER in parsed.pitch


def test_pitch_never_resolves_price_or_stock(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/assist/sale",
        json={"query": "anillo de compromiso", "top_k": 2},
        headers=auth_headers,
    )

    pitch = response.json()["pitch"]

    assert PRICE_LIKE.search(pitch) is None


def test_assist_asks_for_clarification_when_several_families_match(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/assist/sale",
        json={"query": "pendientes", "top_k": 3},
        headers=auth_headers,
    )
    body = response.json()

    assert len(body["groups"]) > 1
    assert body["clarification_question"]


def test_assist_stub_is_deterministic(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {"query": "regalo para mi madre", "top_k": 2}

    first = client.post("/v1/assist/sale", json=payload, headers=auth_headers).json()
    second = client.post("/v1/assist/sale", json=payload, headers=auth_headers).json()

    assert first == second
