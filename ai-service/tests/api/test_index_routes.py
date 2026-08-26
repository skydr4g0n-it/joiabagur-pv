"""Index routes: catalog auth, stub vs real, named 503, keyset fields."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.indexing.orchestrator import CatalogSyncRequest, sync_catalog
from jbg_ai.indexing.set_hash import of_product_ids
from support.index_fakes import (
    FakeEmbeddingClient,
    FakeIndexFeedClient,
    FakeProductDocumentRepo,
    make_page,
    make_upsert,
)
from support.settings import build_settings

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
MAP = {"SKU01": {"data_origin": "real", "text_provenance": "ai_assisted"}}


def _real_app(**overrides):
    settings = build_settings(
        stub_mode=False,
        jpv_index_feed_base_url="http://feed.test",
        jpv_index_feed_api_key="feed-key",
        jpv_embedding_api_key="embed-key",
        **overrides,
    )
    app = create_app(settings)
    return app


def test_catalog_token_without_pos_is_accepted_on_index(
    issue_token: Callable[..., str],
) -> None:
    token = issue_token(pos_id=None)
    with TestClient(create_app(build_settings())) as client:
        sync = client.post(
            "/v1/index/sync",
            json={"full": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        status = client.get(
            "/v1/index/status",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert sync.status_code == 200, sync.text
    assert status.status_code == 200, status.text


def test_index_token_missing_required_claim_is_401(
    issue_token: Callable[..., str],
) -> None:
    token = issue_token(pos_id=None, user_id=None)
    with TestClient(create_app(build_settings())) as client:
        response = client.post(
            "/v1/index/sync",
            json={"full": True},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401


def test_missing_feed_key_returns_503(issue_token: Callable[..., str]) -> None:
    settings = build_settings(
        stub_mode=False,
        jpv_index_feed_base_url="http://feed.test",
        jpv_index_feed_api_key=None,
        jpv_embedding_api_key="embed-key",
    )
    token = issue_token()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/index/sync",
            json={"full": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        health = client.get("/health")
    assert response.status_code == 503
    assert "JPV_INDEX_FEED_API_KEY" in response.json()["detail"]
    assert health.status_code == 200


def test_missing_feed_key_does_not_fall_back_to_jwt(
    issue_token: Callable[..., str],
) -> None:
    settings = build_settings(
        stub_mode=False,
        jpv_index_feed_base_url="http://feed.test",
        jpv_index_feed_api_key=None,
        jpv_embedding_api_key="embed-key",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/index/sync",
            json={"full": True},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )
    assert response.status_code == 503
    assert "JPV_INDEX_FEED_API_KEY" in response.json()["detail"]
    assert "JWT_SECRET" not in response.json()["detail"]


def test_stub_mode_still_returns_fixtures(issue_token: Callable[..., str]) -> None:
    feed = FakeIndexFeedClient([])
    embed = FakeEmbeddingClient()
    repo = FakeProductDocumentRepo()
    app = create_app(build_settings(stub_mode=True))
    app.state.index_feed = feed
    app.state.index_embed = embed
    app.state.index_repo = repo
    token = issue_token()
    with TestClient(app) as client:
        sync = client.post(
            "/v1/index/sync",
            json={"full": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        status = client.get(
            "/v1/index/status",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert sync.status_code == 200
    body = sync.json()
    assert "since_id" in body
    assert "cursor_id" in body
    assert status.status_code == 200
    assert feed.catalog_calls == []
    assert embed.calls == []
    assert repo.documents == {}


def test_real_sync_uses_injected_ports(issue_token: Callable[..., str]) -> None:
    item = make_upsert(sku="SKU01", product_id=A)
    feed = FakeIndexFeedClient([make_page([item])])
    embed = FakeEmbeddingClient()
    repo = FakeProductDocumentRepo()
    app = _real_app()
    app.state.index_feed = feed
    app.state.index_embed = embed
    app.state.index_repo = repo
    app.state.index_provenance = MAP
    with TestClient(app) as client:
        response = client.post(
            "/v1/index/sync",
            json={"full": True, "batch_size": 17},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["upserted"] == 1
    assert body["failed"] == 0
    assert "since_id" in body
    assert "cursor_id" in body
    assert feed.pos_calls == []


def test_real_status_reports_zero_drift_when_hashes_match(
    issue_token: Callable[..., str],
) -> None:
    item = make_upsert(sku="SKU01", product_id=A)
    repo = FakeProductDocumentRepo()
    embed = FakeEmbeddingClient()
    import asyncio

    asyncio.run(
        sync_catalog(
            CatalogSyncRequest(full=True),
            feed=FakeIndexFeedClient([make_page([item])]),
            embed=embed,
            repo=repo,
            provenance_map=MAP,
        )
    )
    local = of_product_ids(list(repo.documents))
    feed = FakeIndexFeedClient([make_page([], aggregate_hash=local)])
    app = _real_app()
    app.state.index_feed = feed
    app.state.index_embed = embed
    app.state.index_repo = repo
    app.state.index_provenance = MAP
    with TestClient(app) as client:
        response = client.get(
            "/v1/index/status",
            headers={"Authorization": f"Bearer {issue_token()}"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["drift_count"] == 0
    assert len(feed.catalog_calls) == 1


def test_sync_request_accepts_since_id(issue_token: Callable[..., str]) -> None:
    with TestClient(create_app(build_settings())) as client:
        response = client.post(
            "/v1/index/sync",
            json={
                "since": "2026-08-05T03:00:00Z",
                "since_id": str(A),
                "full": False,
            },
            headers={"Authorization": f"Bearer {issue_token()}"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "since_id" in body
    assert "cursor_id" in body


def test_sync_feed_down_returns_503_and_writes_nothing(
    issue_token: Callable[..., str],
) -> None:
    repo = FakeProductDocumentRepo()
    app = _real_app()
    app.state.index_feed = FakeIndexFeedClient(fail=True)
    app.state.index_embed = FakeEmbeddingClient()
    app.state.index_repo = repo
    app.state.index_provenance = MAP
    with TestClient(app) as client:
        response = client.post(
            "/v1/index/sync",
            json={"full": True},
            headers={"Authorization": f"Bearer {issue_token()}"},
        )
        health = client.get("/health")
    assert response.status_code == 503, response.text
    assert "catalog feed is unavailable" in response.json()["detail"]
    assert repo.documents == {}
    assert repo.failures == []
    assert health.status_code == 200
