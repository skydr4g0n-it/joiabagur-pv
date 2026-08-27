"""Health endpoint smoke tests (no LLM / embeddings / RDS)."""

from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.config.settings import Settings


def test_health_returns_ok_with_version(minimal_settings: Settings) -> None:
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert body["version"] == minimal_settings.service_version


def test_health_echoes_incoming_trace_id(minimal_settings: Settings) -> None:
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Trace-Id": "trace-from-client"})

    assert response.status_code == 200
    assert response.headers["X-Trace-Id"] == "trace-from-client"


def test_health_is_public(minimal_settings: Settings) -> None:
    """Health stays exempt from the internal token that guards every /v1 route."""
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert response.json()["version"] == minimal_settings.service_version


def test_health_starts_without_rag_llm_key(minimal_settings: Settings) -> None:
    assert minimal_settings.jpv_rag_llm_api_key is None
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_health_starts_without_embedding_key(minimal_settings: Settings) -> None:
    assert minimal_settings.jpv_embedding_api_key is None
    assert minimal_settings.jpv_embedding_model is None
    assert minimal_settings.jpv_embedding_batch_size == 64
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_health_starts_without_index_feed_key(minimal_settings: Settings) -> None:
    assert minimal_settings.jpv_index_feed_base_url is None
    assert minimal_settings.jpv_index_feed_api_key is None
    assert minimal_settings.jpv_index_sync_time_budget_seconds == 180
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_health_starts_without_retrieval_threshold(minimal_settings: Settings) -> None:
    assert minimal_settings.jpv_retrieval_distance_threshold == 0.65
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_health_generates_trace_id_when_missing(minimal_settings: Settings) -> None:
    app = create_app(minimal_settings)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Trace-Id")
