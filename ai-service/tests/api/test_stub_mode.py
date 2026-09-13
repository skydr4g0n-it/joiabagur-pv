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
#: C26 delivered substitutes; **C30a delivered sale assistance**, which really is the last
#: closeable 501 of the service. `/v1/inventory/propose` also answers 501 and stays there —
#: its branch was cancelled on 2026-08-31 and that is declared as a limitation rather than
#: as pending work — as do the two family routes, which have never had a non-stub path.
_REAL_WHEN_STUBS_OFF = {
    "/v1/enrich/products",
    "/v1/index/sync",
    "/v1/index/status",
    "/v1/retrieval/products",
    "/v1/retrieval/substitutes",
    "/v1/assist/sale",
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
    """Re-homed twice now, and the property has never changed.

    C26 moved it off `/v1/retrieval/substitutes` when that route started answering, onto
    `/v1/assist/sale`, which was then waiting on C30. **C30a serves that route**, so it moves
    again — to `/v1/inventory/propose`, the last route of the service whose real logic does
    not exist. Each move is the same reasoning: what is under test is that a route still
    waiting on a change SAYS WHICH ONE, and leaving the assertion on a route that now answers
    would quietly delete the property instead of re-homing it.
    """
    response = stubs_off_client.post(
        "/v1/inventory/propose", json={"horizon_days": 30, "limit": 1}
    )

    assert response.status_code == 501
    assert "C35" in response.json()["detail"]


def test_the_assistance_route_is_no_longer_left_answering_501(
    stubs_off_client: TestClient,
) -> None:
    """The obligation C30a lifts, asserted in the negative — the shape C26 used.

    Without a database and without an embedding credential this client cannot assist
    anything, so 503 is the honest answer and the one asserted. What must never come back is
    a 501 deferring the work to a change that has already happened.
    """
    response = stubs_off_client.post(
        "/v1/assist/sale", json={"query": "regalo", "top_k": 1}
    )

    assert response.status_code != 501
    detail = str(response.json().get("detail", ""))
    assert "later change" not in detail
    assert "C30" not in detail


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
