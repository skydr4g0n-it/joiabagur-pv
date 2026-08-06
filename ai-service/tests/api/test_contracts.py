"""Every frozen `/v1` route answers with its declared model (no LLM / RDS)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from support.sample_requests import RESPONSE_MODELS, V1_REQUESTS


@pytest.mark.parametrize(("method", "path", "body"), V1_REQUESTS)
def test_frozen_route_answers_with_its_declared_model(
    client: TestClient,
    auth_headers: dict[str, str],
    forbid_network: None,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    response = (
        client.get(path, headers=auth_headers)
        if method == "GET"
        else client.post(path, json=body, headers=auth_headers)
    )

    assert response.status_code == 200, response.text
    RESPONSE_MODELS[path].model_validate(response.json())


def test_inventory_proposals_are_prioritized(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/inventory/propose",
        json={"horizon_days": 30, "limit": 4},
        headers=auth_headers,
    )

    proposals = response.json()["proposals"]

    assert len(proposals) == 4
    assert [item["priority"] for item in proposals] == sorted(
        item["priority"] for item in proposals
    )
    # Quantities belong to .NET; Python only points at what deserves attention.
    assert all("quantity" not in item for item in proposals)


def test_enrichment_returns_one_profile_per_product_with_confidence(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/enrich/products",
        json={
            "products": [
                {"product_id": "P-1", "sku": "JBG-1", "name": "Anillo"},
                {"product_id": "P-2", "sku": "JBG-2"},
            ]
        },
        headers=auth_headers,
    )

    profiles = response.json()["profiles"]

    assert [profile["product_id"] for profile in profiles] == ["P-1", "P-2"]
    for profile in profiles:
        assert isinstance(profile["materials"]["value"], list)
        assert 0.0 <= profile["materials"]["confidence"] <= 1.0
        for field in ("title", "description", "family_id"):
            assert profile[field] is None or "confidence" in profile[field]


def test_index_sync_and_status_expose_counters_and_drift(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    sync = client.post(
        "/v1/index/sync",
        json={"since": "2026-08-05T03:00:00Z", "batch_size": 50},
        headers=auth_headers,
    ).json()

    assert sync["upserted"] >= 0
    assert sync["skipped"] >= 0
    assert sync["cursor"]

    status = client.get("/v1/index/status", headers=auth_headers).json()

    assert status["drift_count"] >= 0
    assert status["last_full_sync_at"]


def test_scoped_responses_echo_the_token_scope(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for path, body in (
        ("/v1/retrieval/products", {"query": "anillo", "top_k": 1}),
        ("/v1/assist/sale", {"query": "anillo", "top_k": 1}),
        ("/v1/inventory/propose", {"limit": 1}),
    ):
        response = client.post(path, json=body, headers=auth_headers)

        assert response.json()["effective_pos_id"] == "POS-B", path
