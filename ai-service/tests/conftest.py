"""Shared pytest fixtures for jbg-ai smoke tests.

Tests set required env in-process and never call LLM, embeddings, or RDS.
"""

from __future__ import annotations

import pytest

from jbg_ai.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def minimal_settings() -> Settings:
    """In-process settings — no external services."""
    return Settings(
        app_env="test",
        service_version="0.1.0-test",
        log_level="WARNING",
    )
