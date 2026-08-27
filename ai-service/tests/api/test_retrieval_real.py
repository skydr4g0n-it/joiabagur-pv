"""Real POST /v1/retrieval/products: stub vs vector, 503 vs abstention. Delivered by C14."""

from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.api.schemas.retrieval import RetrievalResponse
from jbg_ai.indexing.errors import EmbeddingError
from support.fake_embedding_client import FakeEmbeddingClient
from support.fake_product_search import FakeIndexedRow, FakeProductSearch
from support.settings import TOKEN_POS_ID, build_settings

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
FAMILY = UUID("11111111-1111-1111-1111-111111111111")


def _row(**kwargs) -> FakeIndexedRow:
    values = {
        "product_id": kwargs.pop("product_id", A),
        "sku": kwargs.pop("sku", "JBG-0001"),
        "distance": kwargs.pop("distance", 0.2),
        "materials": kwargs.pop("materials", ["plata"]),
        "family_id": kwargs.pop("family_id", FAMILY),
        "piece_type": kwargs.pop("piece_type", "anillo"),
    }
    values.update(kwargs)
    return FakeIndexedRow(**values)


def _real_app(
    *,
    search: FakeProductSearch | None = None,
    embed: FakeEmbeddingClient | None = None,
    **settings_overrides,
):
    settings = build_settings(stub_mode=False, **settings_overrides)
    app = create_app(settings)
    app.state.retrieval_embed = embed if embed is not None else FakeEmbeddingClient()
    app.state.retrieval_search = search if search is not None else FakeProductSearch([_row()])
    return app


def test_stub_mode_still_returns_fixtures(issue_token: Callable[..., str]) -> None:
    embed = FakeEmbeddingClient()
    search = FakeProductSearch([_row()])
    app = create_app(build_settings(stub_mode=True))
    app.state.retrieval_embed = embed
    app.state.retrieval_search = search
    token = issue_token()
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo de plata", "top_k": 2},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    parsed = RetrievalResponse.model_validate(body)
    assert parsed.candidates_returned == 6
    assert parsed.results[0].product_id.startswith("P-")
    assert embed.call_count == 0
    assert search.search_calls == []
    assert search.count_calls == []


def test_missing_embedding_key_is_503(issue_token: Callable[..., str]) -> None:
    settings = build_settings(
        stub_mode=False,
        jpv_embedding_api_key=None,
        database_url="postgresql+psycopg://u:p@db:5432/jpv",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )
        health = client.get("/health")

    assert response.status_code == 503
    assert "JPV_EMBEDDING_API_KEY" in response.json()["detail"]
    assert health.status_code == 200
    assert "low_confidence" not in response.json()


def test_missing_database_url_is_503(issue_token: Callable[..., str]) -> None:
    settings = build_settings(
        stub_mode=False,
        jpv_embedding_api_key="sk-test",
        database_url=None,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )
        health = client.get("/health")

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]
    assert health.status_code == 200
    assert "low_confidence" not in response.json()


def test_empty_compatible_index_is_503_not_abstention(
    issue_token: Callable[..., str],
) -> None:
    app = _real_app(search=FakeProductSearch(compatible_count=0))
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )

    assert response.status_code == 503
    assert response.json().get("low_confidence") is None


def test_real_mode_is_not_501(issue_token: Callable[..., str]) -> None:
    app = _real_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo de plata", "top_k": 5},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )

    assert response.status_code == 200
    parsed = RetrievalResponse.model_validate(response.json())
    assert parsed.results
    assert parsed.low_confidence is False
    assert parsed.effective_pos_id == TOKEN_POS_ID


def test_token_without_pos_id_is_401(issue_token: Callable[..., str]) -> None:
    app = _real_app()
    token = issue_token(pos_id=None)
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401


def test_body_pos_id_is_ignored(issue_token: Callable[..., str]) -> None:
    app = _real_app()
    token = issue_token(pos_id="POS-B")
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1, "pos_id": "POS-A"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["effective_pos_id"] == "POS-B"


def test_invalid_family_id_is_422(issue_token: Callable[..., str]) -> None:
    app = _real_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={
                "query": "anillo",
                "top_k": 1,
                "filters": {"family_id": "not-a-uuid"},
            },
            headers={"Authorization": f"Bearer {issue_token()}"},
        )

    assert response.status_code == 422


def test_hybrid_and_lexical_modes_are_not_501(issue_token: Callable[..., str]) -> None:
    app = _real_app()
    token = issue_token()
    with TestClient(app) as client:
        for body in (
            {"query": "anillo", "top_k": 1},
            {"query": "anillo", "top_k": 1, "mode": "hybrid"},
            {"query": "anillo", "top_k": 1, "mode": "lexical"},
        ):
            response = client.post(
                "/v1/retrieval/products",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code != 501, body
            assert response.status_code == 200, response.text
            notes = response.json()["results"][0]["debug"]["notes"]
            assert "vector_only_until_c21" in notes


def test_vector_mode_omits_until_c21_note(issue_token: Callable[..., str]) -> None:
    app = _real_app()
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1, "mode": "vector"},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )

    assert response.status_code == 200
    notes = response.json()["results"][0]["debug"]["notes"]
    assert "vector_only_until_c21" not in notes


def test_provider_failure_is_503(issue_token: Callable[..., str]) -> None:
    class _Boom(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            raise EmbeddingError("provider down")

    app = _real_app(embed=_Boom())
    with TestClient(app) as client:
        response = client.post(
            "/v1/retrieval/products",
            json={"query": "anillo", "top_k": 1},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )

    assert response.status_code == 503
    assert "low_confidence" not in response.json()


def test_trace_id_appears_in_stage_logs(
    issue_token: Callable[..., str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = _real_app()
    logging.getLogger().addHandler(caplog.handler)
    token = issue_token(trace_id="trace-c14")
    with caplog.at_level(logging.INFO, logger="jbg_ai.retrieval.orchestrator"):
        with TestClient(app) as client:
            response = client.post(
                "/v1/retrieval/products",
                json={"query": "anillo", "top_k": 1},
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert any("stage=embed" in msg and "trace-c14" in msg for msg in messages)
    assert any("stage=search" in msg and "trace-c14" in msg for msg in messages)
