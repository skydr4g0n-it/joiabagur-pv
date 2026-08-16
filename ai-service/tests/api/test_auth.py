"""Internal service token tests (no LLM / embeddings / RDS)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.auth import decode_service_token
from support.sample_requests import V1_REQUESTS
from support.settings import TEST_JWT_SECRET


def _call(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    headers: dict[str, str] | None = None,
) -> Any:
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=body, headers=headers)


@pytest.mark.parametrize(("method", "path", "body"), V1_REQUESTS)
def test_request_without_token_is_rejected(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = _call(client, method, path, body)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "token_kwargs",
    [
        pytest.param({"secret": "wrong-secret-0123456789abcdefghijkl"}, id="bad-signature"),
        pytest.param({"expires_in": -60}, id="expired"),
        pytest.param({"pos_id": None}, id="missing-pos-id"),
        pytest.param({"user_id": None}, id="missing-user-id"),
        pytest.param({"role": None}, id="missing-role"),
        pytest.param({"trace_id": None}, id="missing-trace-id"),
        pytest.param({"pos_id": "   "}, id="blank-pos-id"),
    ],
)
def test_invalid_token_is_rejected(
    client: TestClient, issue_token: Callable[..., str], token_kwargs: dict[str, Any]
) -> None:
    token = issue_token(**token_kwargs)

    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo", "top_k": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert "test-jwt-secret-0123456789abcdefghij" not in response.text
    assert "signature" not in response.text.lower()
    assert "expired" not in response.text.lower()


def test_malformed_authorization_header_is_rejected(client: TestClient) -> None:
    for header in ("Bearer not-a-jwt", "Basic dXNlcjpwYXNz", "token-without-scheme"):
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers={"Authorization": header},
        )

        assert response.status_code == 401, header


def test_token_signed_with_unexpected_algorithm_is_rejected(client: TestClient) -> None:
    import jwt

    unsigned = jwt.encode(
        {"user_id": "u-1", "role": "Admin", "pos_id": "POS-B", "trace_id": "t-1"},
        key="",
        algorithm="none",
    )

    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo", "top_k": 1},
        headers={"Authorization": f"Bearer {unsigned}"},
    )

    assert response.status_code == 401


def test_valid_token_is_accepted(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo", "top_k": 1},
        headers=auth_headers,
    )

    assert response.status_code == 200


def test_decode_service_token_exposes_every_claim(issue_token: Callable[..., str]) -> None:
    """The principal is the seam: user_id and role reach it even if no route reads them yet."""
    token = issue_token(user_id="u-42", role="Admin", pos_id="POS-Z", trace_id="t-9")

    principal = decode_service_token(token, TEST_JWT_SECRET)

    assert principal.user_id == "u-42"
    assert principal.role == "Admin"
    assert principal.pos_id == "POS-Z"
    assert principal.trace_id == "t-9"


def test_pos_id_from_token_overrides_body_value(
    client: TestClient, issue_token: Callable[..., str]
) -> None:
    token = issue_token(pos_id="POS-B")

    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo", "top_k": 1, "pos_id": "POS-A"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["effective_pos_id"] == "POS-B"


def test_role_in_body_is_inert(client: TestClient, auth_headers: dict[str, str]) -> None:
    """A body role cannot escalate anything: the response is byte-identical without it."""
    payload = {"query": "anillo", "top_k": 1}

    baseline = client.post("/v1/retrieval/products", json=payload, headers=auth_headers)
    with_role = client.post(
        "/v1/retrieval/products", json={**payload, "role": "Admin"}, headers=auth_headers
    )

    assert with_role.status_code == 200
    assert with_role.content == baseline.content


def test_token_trace_id_wins_over_header(
    client: TestClient, issue_token: Callable[..., str]
) -> None:
    token = issue_token(trace_id="trace-from-token")

    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo", "top_k": 1},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Trace-Id": "trace-from-header",
        },
    )

    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace-from-token"
    assert response.headers["X-Trace-Id"] == "trace-from-token"


def test_token_trace_id_reaches_structured_logs(
    client: TestClient,
    issue_token: Callable[..., str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = issue_token(trace_id="trace-in-logs")

    with caplog.at_level(logging.INFO, logger="jbg_ai"):
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Trace-Id": "trace-from-header",
            },
        )

    assert response.status_code == 200
    logged = [getattr(record, "trace_id", None) for record in caplog.records]
    assert "trace-in-logs" in logged


def test_rejected_request_still_carries_a_trace_id(client: TestClient) -> None:
    response = client.post("/v1/retrieval/products", json={"query": "anillo"})

    assert response.status_code == 401
    assert response.headers.get("X-Trace-Id")


ENRICH_BODY = {"products": [{"product_id": "P-1", "sku": "JBG-1"}]}


def test_catalog_token_without_pos_is_accepted_on_enrich(
    client: TestClient, issue_token: Callable[..., str]
) -> None:
    """Enriching the catalog belongs to no point of sale.

    Requiring `pos_id` here would force the caller to invent one, and the only
    values available to invent are wildcards — which is precisely what must never
    exist, since that claim is the retriever's only hard filter.
    """
    token = issue_token(pos_id=None)

    response = client.post(
        "/v1/enrich/products", json=ENRICH_BODY, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200, response.text


def test_catalog_token_is_rejected_on_retrieval(
    client: TestClient, issue_token: Callable[..., str]
) -> None:
    """The second of the two independent closures on this boundary.

    The .NET client already refuses to send a catalog scope to retrieval. This
    asserts the service refuses it too, so that relaxing one side by accident
    does not open the door.
    """
    token = issue_token(pos_id=None)

    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo", "top_k": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("claim", ["user_id", "role", "trace_id"])
def test_catalog_route_still_rejects_a_token_missing_the_other_claims(
    client: TestClient, issue_token: Callable[..., str], claim: str
) -> None:
    token = issue_token(pos_id=None, **{claim: None})

    response = client.post(
        "/v1/enrich/products", json=ENRICH_BODY, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_catalog_route_still_reports_pos_scope_when_the_token_carries_one(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A point-of-sale token is not rejected on a catalog route — it is just not required."""
    response = client.post("/v1/enrich/products", json=ENRICH_BODY, headers=auth_headers)

    assert response.status_code == 200
