"""Settings fail-fast tests (no LLM / embeddings / RDS)."""

import pytest
from pydantic import ValidationError

from jbg_ai.config.settings import Settings, get_settings


def test_settings_fail_fast_when_required_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("SERVICE_VERSION", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
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
    monkeypatch.setenv("JWT_SECRET", "secret")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_settings_fail_fast_when_jwt_secret_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    assert "jwt_secret" in str(exc_info.value)


def test_settings_fail_fast_when_jwt_secret_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    monkeypatch.setenv("JWT_SECRET", "   ")
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    assert "jwt_secret" in str(exc_info.value)


def test_settings_load_with_minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    monkeypatch.setenv("JWT_SECRET", "local-secret")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("JWT_TTL_SECONDS", raising=False)
    monkeypatch.delenv("STUB_MODE", raising=False)
    monkeypatch.delenv("ENABLE_DEV_ENDPOINTS", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.service_version == "0.1.0"
    assert settings.log_level == "INFO"
    assert settings.jwt_ttl_seconds == 300
    assert settings.stub_mode is True
    assert settings.enable_dev_endpoints is True


def test_dev_endpoints_default_off_for_production_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    monkeypatch.setenv("JWT_SECRET", "prod-secret")
    monkeypatch.delenv("ENABLE_DEV_ENDPOINTS", raising=False)
    get_settings.cache_clear()

    assert get_settings().enable_dev_endpoints is False


def test_dev_endpoints_can_be_overridden_by_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    monkeypatch.setenv("JWT_SECRET", "prod-secret")
    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "true")
    get_settings.cache_clear()

    assert get_settings().enable_dev_endpoints is True
