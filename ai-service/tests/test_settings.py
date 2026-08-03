"""Settings fail-fast tests (no LLM / embeddings / RDS)."""

import pytest
from pydantic import ValidationError

from jbg_ai.config.settings import Settings, get_settings


def test_settings_fail_fast_when_required_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("SERVICE_VERSION", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    error_text = str(exc_info.value)
    assert "app_env" in error_text or "service_version" in error_text


def test_settings_fail_fast_when_app_env_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_settings_load_with_minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.service_version == "0.1.0"
    assert settings.log_level == "INFO"
