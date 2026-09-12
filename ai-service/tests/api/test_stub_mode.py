"""With stubs disabled and no real implementation, frozen routes answer 501."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from support.sample_requests import V1_REQUESTS
from support.settings import build_settings

#: C09 delivered enrich; C13 delivered index; C14 delivered product retrieval; C24 delivered
#: the evaluation runs, whose placeholder had named it in writing as the change that would;
#: C26 delivered substitutes, which is the last 501 of the retrieval domain and the last
#: CLOSEABLE one of the service — `/v1/inventory/propose` also answers 501, but its branch
#: was cancelled on 2026-08-31 and that is declared as a limitation rather than pending.
_REAL_WHEN_STUBS_OFF = {
    "/v1/enrich/products",
    "/v1/index/sync",
    "/v1/index/status",
    "/v1/retrieval/products",
    "/v1/retrieval/substitutes",
    "/v1/evals/runs",
}
STUB_ONLY_REQUESTS = [item for item in V1_REQUESTS if item[1] not in _REAL_WHEN_STUBS_OFF]


@pytest.fixture
def stubs_off_client(issue_token: Callable[..., str]) -> TestClient:
    app = create_app(build_settings(stub_mode=False))
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {issue_token()}"})
    return client


@pytest.mark.parametrize(("method", "path", "body"), STUB_ONLY_REQUESTS)
def test_unimplemented_route_returns_501_when_stub_mode_off(
    stubs_off_client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = (
        stubs_off_client.get(path)
        if method == "GET"
        else stubs_off_client.post(path, json=body)
    )

    assert response.status_code == 501, path
    assert "later change" in response.json()["detail"]


def test_501_message_names_the_delivering_change(stubs_off_client: TestClient) -> None:
    """Moved off substitutes by C26, which implemented it. The property is unchanged.

    It used to be asserted against `/v1/retrieval/substitutes` and the string "C26". That
    route now answers, so keeping the assertion there would have quietly deleted the
    property instead of re-homing it: what is being tested is that a route still waiting
    on a change SAYS WHICH ONE, and `/v1/assist/sale` is waiting on C30.
    """
    response = stubs_off_client.post(
        "/v1/assist/sale", json={"query": "regalo", "top_k": 1}
    )

    assert response.status_code == 501
    assert "C30" in response.json()["detail"]


def test_no_retrieval_route_is_left_answering_501(stubs_off_client: TestClient) -> None:
    """The obligation C26 lifted from `vector-retrieval`, asserted in the negative.

    Without a database this client cannot retrieve anything, so 503 is the honest answer
    and the one asserted. What must never come back is a 501 deferring the work to a
    change that has already happened.
    """
    response = stubs_off_client.post(
        "/v1/retrieval/substitutes", json={"product_id": "P-0001", "top_k": 1}
    )

    assert response.status_code != 501
    detail = str(response.json().get("detail", ""))
    assert "later change" not in detail
    assert "C26" not in detail


def test_authentication_still_precedes_the_stub_guard(stubs_off_client: TestClient) -> None:
    stubs_off_client.headers.pop("Authorization")

    response = stubs_off_client.post(
        "/v1/retrieval/products", json={"query": "anillo", "top_k": 1}
    )

    assert response.status_code == 401
