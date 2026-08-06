"""Shared pytest fixtures for jbg-ai tests.

Tests set required env in-process and never call LLM, embeddings, or RDS.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from jbg_ai.api.main import create_app
from jbg_ai.config.settings import Settings, get_settings

# HS256 keys shorter than 32 bytes make PyJWT warn; keep fixtures above the bar.
TEST_JWT_SECRET = "test-jwt-secret-0123456789abcdefghij"
TOKEN_POS_ID = "POS-B"
TOKEN_TRACE_ID = "trace-from-token"


def build_settings(**overrides: Any) -> Settings:
    """In-process settings — no external services."""
    values: dict[str, Any] = {
        "app_env": "test",
        "service_version": "0.1.0-test",
        "log_level": "WARNING",
        "jwt_secret": TEST_JWT_SECRET,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def minimal_settings() -> Settings:
    return build_settings()


@pytest.fixture
def client(minimal_settings: Settings) -> Iterator[TestClient]:
    """Client for the default profile: stubs on, development endpoints mounted."""
    with TestClient(create_app(minimal_settings)) as test_client:
        yield test_client


@pytest.fixture
def issue_token() -> Callable[..., str]:
    """Sign an internal service token; override claims or drop them with None."""

    def _issue(
        *,
        secret: str = TEST_JWT_SECRET,
        expires_in: int = 300,
        **claims: Any,
    ) -> str:
        now = datetime.now(tz=UTC)
        payload: dict[str, Any] = {
            "user_id": "u-1",
            "role": "Operator",
            "pos_id": TOKEN_POS_ID,
            "trace_id": TOKEN_TRACE_ID,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        }
        payload.update(claims)
        return jwt.encode(
            {key: value for key, value in payload.items() if value is not None},
            secret,
            algorithm="HS256",
        )

    return _issue


@pytest.fixture
def auth_headers(issue_token: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token()}"}


@pytest.fixture
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn any socket connection into a failure: stubs must do no external I/O."""

    def _fail(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("stub mode must not open a network connection")

    monkeypatch.setattr(socket.socket, "connect", _fail)
    monkeypatch.setattr(socket, "create_connection", _fail)
