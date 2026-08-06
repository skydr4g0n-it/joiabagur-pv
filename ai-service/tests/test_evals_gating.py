"""`GET /v1/evals/runs` exists only under a development profile."""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import build_settings
from jbg_ai.api.main import create_app
from jbg_ai.api.schemas.evals import EvalRunsResponse


def test_evals_route_returns_runs_in_dev_profile(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/v1/evals/runs", headers=auth_headers)

    assert response.status_code == 200
    parsed = EvalRunsResponse.model_validate(response.json())
    assert parsed.runs
    assert [run.run_id for run in parsed.runs] == ["run-0001", "run-0002"]


def test_dev_only_evals_route_absent_in_prod_profile(auth_headers: dict[str, str]) -> None:
    app = create_app(build_settings(app_env="prod"))

    with TestClient(app) as prod_client:
        response = prod_client.get("/v1/evals/runs", headers=auth_headers)

    # Not mounted at all: a generic 404, never a documented business answer.
    assert response.status_code == 404
    assert "/v1/evals/runs" not in app.openapi()["paths"]


def test_other_v1_routes_stay_mounted_in_prod_profile(auth_headers: dict[str, str]) -> None:
    app = create_app(build_settings(app_env="prod"))

    with TestClient(app) as prod_client:
        response = prod_client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers=auth_headers,
        )

    assert response.status_code == 200
