"""With stubs disabled and no real implementation, frozen routes answer 501."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from support.sample_requests import V1_REQUESTS
from support.settings import build_settings

#: C09 delivered enrich; C13 delivered index. Remaining frozen routes still 501.
_REAL_WHEN_STUBS_OFF = {"/v1/enrich/products", "/v1/index/sync", "/v1/index/status"}
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
    response = stubs_off_client.post(
        "/v1/retrieval/products", json={"query": "anillo", "top_k": 1}
    )

    assert "C14" in response.json()["detail"]


def test_authentication_still_precedes_the_stub_guard(stubs_off_client: TestClient) -> None:
    stubs_off_client.headers.pop("Authorization")

    response = stubs_off_client.post(
        "/v1/retrieval/products", json={"query": "anillo", "top_k": 1}
    )

    assert response.status_code == 401
