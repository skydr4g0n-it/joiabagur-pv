"""Retrieval stub contract tests (no LLM / embeddings / RDS)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.schemas.retrieval import RetrievalResponse, SubstitutesResponse


def test_retrieval_stub_matches_response_schema(
    client: TestClient, auth_headers: dict[str, str], forbid_network: None
) -> None:
    response = client.post(
        "/v1/retrieval/products",
        json={
            "query": "anillo de plata",
            "top_k": 3,
            "filters": {"materials": ["plata"]},
            "mode": "hybrid",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    parsed = RetrievalResponse.model_validate(body)

    assert parsed.results
    for index, result in enumerate(parsed.results):
        raw = body["results"][index]
        assert isinstance(raw["materials"], list)
        # Unknown family / variant must serialize as null, never be dropped.
        assert "family_id" in raw
        assert "variant_label" in raw
        assert result.product_id and result.sku


def test_over_retrieval_returns_capped_candidates(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for top_k, expected in ((5, 15), (30, 60)):
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "pulsera", "top_k": top_k},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["candidates_returned"] == expected, top_k
        assert len(body["results"]) == expected, top_k


@pytest.mark.parametrize(("top_k", "expected"), [(1, 3), (10, 30), (20, 60), (50, 60)])
def test_over_retrieval_rule_holds_across_the_range(
    client: TestClient, auth_headers: dict[str, str], top_k: int, expected: int
) -> None:
    response = client.post(
        "/v1/retrieval/products",
        json={"query": "collar", "top_k": top_k},
        headers=auth_headers,
    )

    assert response.json()["candidates_returned"] == expected


def test_retrieval_stub_is_deterministic(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {"query": "anillo de plata", "top_k": 4}

    first = client.post("/v1/retrieval/products", json=payload, headers=auth_headers).json()
    second = client.post("/v1/retrieval/products", json=payload, headers=auth_headers).json()

    assert first == second


def test_substitutes_expose_similarity_signals(
    client: TestClient, auth_headers: dict[str, str], forbid_network: None
) -> None:
    response = client.post(
        "/v1/retrieval/substitutes",
        json={"product_id": "P-0001", "top_k": 2, "reason": "out_of_stock"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    parsed = SubstitutesResponse.model_validate(response.json())

    assert parsed.candidates_returned == 6
    assert parsed.results
    for result in parsed.results:
        assert result.similarity_signals.material_overlap >= 0.0
        assert isinstance(result.materials, list)


def test_invalid_top_k_is_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo", "top_k": 999},
        headers=auth_headers,
    )

    assert response.status_code == 422
