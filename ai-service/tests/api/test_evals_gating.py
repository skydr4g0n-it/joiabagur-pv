"""`GET /v1/evals/runs`: mounted only in development, and no longer a placeholder."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.api.schemas.evals import EvalRunsResponse
from support.settings import build_settings


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


def _stubs_off(rows: list[dict], monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client with stubs disabled and the repository doubled.

    Doubled rather than driven against a real database, and the reason is a Windows one: the
    test client runs the route on a proactor event loop, which psycopg refuses to use in async
    mode. What belongs here is that the ROUTE serves what the repository returns; that the
    repository reads the table is a database test, and it lives with the rest of them.
    """
    from jbg_ai.evals import repository

    async def _read_runs(*, settings: object, limit: int) -> list[dict]:  # noqa: ARG001
        return rows

    monkeypatch.setattr(repository, "read_runs", _read_runs)
    app = create_app(build_settings(stub_mode=False, database_url="postgresql+psycopg://x/y"))
    return TestClient(app)


def _row(run_id: str, config_id: str, hour: int) -> dict:
    return {
        "run_id": run_id,
        "suite": config_id,
        "status": "completed",
        "started_at": datetime(2026, 9, 7, hour, tzinfo=UTC),
        "finished_at": datetime(2026, 9, 7, hour, 1, tzinfo=UTC),
        "metrics": [{"name": "global.ndcg_at_5", "value": 0.603}],
    }


def test_the_route_no_longer_answers_501_with_stubs_disabled(
    monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
) -> None:
    """Its placeholder named C24 in writing. C24 delivered it, so the placeholder is gone."""
    with _stubs_off([_row("r-1", "v2-hibrido", 10)], monkeypatch) as client:
        response = client.get("/v1/evals/runs", headers=auth_headers)

    assert response.status_code == 200
    assert "later change" not in response.text


def test_an_empty_history_is_an_empty_list_and_not_an_error(
    monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
) -> None:
    """"Nothing has been evaluated here" is a valid answer: persistence is opt-in."""
    with _stubs_off([], monkeypatch) as client:
        response = client.get("/v1/evals/runs", headers=auth_headers)

    assert response.status_code == 200
    assert EvalRunsResponse.model_validate(response.json()).runs == []


def test_the_route_serves_the_runs_it_is_given_with_their_metrics(
    monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
) -> None:
    rows = [_row("r-2", "v2-hibrido", 10), _row("r-1", "v0-nombre", 9)]

    with _stubs_off(rows, monkeypatch) as client:
        response = client.get("/v1/evals/runs", headers=auth_headers)

    parsed = EvalRunsResponse.model_validate(response.json())
    assert [run.run_id for run in parsed.runs] == ["r-2", "r-1"]
    assert parsed.runs[0].suite == "v2-hibrido"
    assert parsed.runs[0].metrics[0].name == "global.ndcg_at_5"


def test_the_route_says_what_it_needs_instead_of_failing_opaquely(
    auth_headers: dict[str, str]
) -> None:
    app = create_app(build_settings(stub_mode=False))

    with TestClient(app) as client:
        response = client.get("/v1/evals/runs", headers=auth_headers)

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]
