"""Every frozen `/v1` route answers with its declared model (no LLM / RDS)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from support.sample_requests import RESPONSE_MODELS, V1_REQUESTS
from support.settings import TOKEN_POS_ID


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


SENSITIVE_FIELDS = ("piece_type", "materials", "stone_type", "size_label")
TAG_FIELDS = ("color_tags", "style_tags", "occasion_tags")


def _enrich(client: TestClient, auth_headers: dict[str, str], count: int) -> list[dict[str, Any]]:
    response = client.post(
        "/v1/enrich/products",
        json={
            "products": [
                {"product_id": f"P-{index}", "sku": f"JBG-{index}", "name": f"Pieza {index}"}
                for index in range(count)
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["profiles"]


def test_enrich_profile_carries_source_per_field(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Provenance is what the whole hybrid review policy turns on.

    A sensitive field a model inferred needs a person; the same field produced by
    a deterministic rule does not. Without `source` on the wire that distinction
    cannot be made at all, so this asserts it on every proposed value rather than
    only on the ones a particular fixture happens to fill.
    """
    profiles = _enrich(client, auth_headers, count=4)

    for profile in profiles:
        for field in (*SENSITIVE_FIELDS, *TAG_FIELDS, "title", "description"):
            proposed = profile[field]
            if proposed is None:
                continue
            assert proposed["source"] in {"rule", "inferred"}, field
            assert 0.0 <= proposed["confidence"] <= 1.0, field


def test_enrich_profile_exposes_sensitive_fields_and_split_tags(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    profiles = _enrich(client, auth_headers, count=2)

    for profile in profiles:
        for field in SENSITIVE_FIELDS:
            assert field in profile
        for field in TAG_FIELDS:
            assert isinstance(profile[field]["value"], list)
        # The flat list is gone: collapsing the three would force whoever needed
        # the split downstream to reinvent the partition criterion.
        assert "tags" not in profile


def test_enrich_stub_exercises_both_provenances(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A fixture where everything is inferred cannot catch a broken policy.

    Routing to review is what such a policy does by default, so a batch with no
    rule-sourced field would let an implementation that exempts nothing pass.
    """
    profiles = _enrich(client, auth_headers, count=4)

    sources = {
        profile[field]["source"]
        for profile in profiles
        for field in SENSITIVE_FIELDS
        if profile[field] is not None
    }

    assert sources == {"rule", "inferred"}


def test_enrich_stub_straddles_a_tag_threshold(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    profiles = _enrich(client, auth_headers, count=4)

    confidences = [profile["color_tags"]["confidence"] for profile in profiles]

    assert max(confidences) >= 0.80
    assert min(confidences) < 0.80


def test_enrich_reports_prompt_version(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/v1/enrich/products",
        json={"products": [{"product_id": "P-1", "sku": "JBG-1"}]},
        headers=auth_headers,
    )

    assert response.json()["prompt_version"]


def test_enrich_stub_is_deterministic(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    first = _enrich(client, auth_headers, count=4)
    second = _enrich(client, auth_headers, count=4)

    assert first == second


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
    assert "since_id" in sync
    assert "cursor_id" in sync

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

        assert response.json()["effective_pos_id"] == TOKEN_POS_ID, path


def test_query_expansion_is_not_part_of_the_request_contract() -> None:
    """C20's flag supplies a default in settings and travels by parameter, never by body.

    Putting it on the request would move `openapi.json`, which is frozen with the .NET
    side. `test_openapi_snapshot_is_stable` guards the file; this guards the intent.
    """
    from jbg_ai.api.schemas.retrieval import RetrievalRequest

    fields = set(RetrievalRequest.model_fields)
    assert not {name for name in fields if "expan" in name or "synonym" in name}
    assert fields == {"query", "top_k", "filters", "mode", "pos_id"}
