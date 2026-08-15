"""The service must run with no database at all. Delivered by C05.

`ai-service-dev-compose` states that local runs need no database and that boot
must not require a connection. Adding a persistence layer is exactly the change
that could quietly break that, so it is asserted here rather than assumed.

Note the fixture order: `client` comes before `forbid_network` on purpose. The
socket ban has to be installed *after* the test client exists, because building
it opens the event loop's own internal socket pair — the same ordering every
other stub test in this suite relies on.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jbg_ai.config.settings import Settings
from jbg_ai.db import engine as engine_module


@pytest.fixture(autouse=True)
def _no_engine_built_yet():
    """The engine is process-wide; start from nothing and leave nothing behind."""
    engine_module._engine = None
    engine_module._sessionmaker = None
    yield
    engine_module._engine = None
    engine_module._sessionmaker = None


def test_service_boots_without_database_url(minimal_settings: Settings) -> None:
    """The default local profile carries no connection string at all."""
    assert minimal_settings.database_url is None


def test_health_answers_without_a_database(
    client: TestClient, forbid_network: None
) -> None:
    """No connection string, no engine, no socket — and still HTTP 200."""
    response = client.get("/health")

    assert response.status_code == 200
    assert engine_module._engine is None, (
        "serving the app must not build a database engine: boot has to work "
        "against an environment where no database exists yet"
    )


def test_stub_routes_answer_without_a_database(
    client: TestClient, auth_headers: dict[str, str], forbid_network: None
) -> None:
    """Under STUB_MODE nothing requests a session, so `/v1` is unaffected."""
    response = client.post(
        "/v1/retrieval/products",
        json={"query": "anillo de plata", "top_k": 5},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert engine_module._engine is None
