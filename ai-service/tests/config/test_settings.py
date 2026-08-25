"""Settings fail-fast tests (no LLM / embeddings / RDS)."""

import pytest
from pydantic import ValidationError

from jbg_ai.config.settings import Settings, canonical_openapi_settings, get_settings


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
    assert settings.jpv_rag_llm_concurrency == 8


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


def _minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_VERSION", "0.1.0")
    monkeypatch.setenv("JWT_SECRET", "local-secret")


def test_settings_load_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent database configuration must not stop the service booting.

    `ai-service-dev-compose` guarantees local runs need no database, and the
    Compose service is started without this variable. Making it required would
    turn an accepted scenario false and leave the container dead on arrival.
    """
    _minimal_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url is None
    assert settings.db_pool_size == 5


def test_settings_accept_database_url_when_supplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/jpv")
    monkeypatch.setenv("DB_POOL_SIZE", "3")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg://u:p@db:5432/jpv"
    assert settings.db_pool_size == 3


def test_blank_database_url_is_treated_as_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose files and shell profiles export empty strings very easily.

    Failing later on an unparseable URL would be a worse error than behaving as
    though the variable had never been set.
    """
    _minimal_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "   ")
    get_settings.cache_clear()

    assert get_settings().database_url is None


def test_settings_do_not_require_llm_key_to_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.delenv("JPV_CATALOG_LLM_API_KEY", raising=False)
    monkeypatch.delenv("JPV_RAG_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.jpv_catalog_llm_api_key is None
    assert settings.jpv_catalog_llm_model is None
    assert settings.jpv_rag_llm_api_key is None
    assert settings.jpv_rag_llm_model is None
    assert settings.jpv_rag_llm_base_url is None
    assert settings.jpv_rag_llm_concurrency == 8


def test_settings_do_not_require_rag_llm_key_to_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.delenv("JPV_RAG_LLM_API_KEY", raising=False)
    monkeypatch.delenv("JPV_RAG_LLM_MODEL", raising=False)
    monkeypatch.delenv("JPV_RAG_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("JPV_RAG_LLM_CONCURRENCY", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.jpv_rag_llm_api_key is None
    assert settings.jpv_rag_llm_model is None
    assert settings.jpv_rag_llm_base_url is None
    assert settings.jpv_rag_llm_concurrency == 8


def test_blank_rag_llm_strings_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.setenv("JPV_RAG_LLM_API_KEY", "   ")
    monkeypatch.setenv("JPV_RAG_LLM_MODEL", "")
    monkeypatch.setenv("JPV_RAG_LLM_BASE_URL", " ")
    monkeypatch.setenv("JPV_RAG_LLM_CONCURRENCY", "")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.jpv_rag_llm_api_key is None
    assert settings.jpv_rag_llm_model is None
    assert settings.jpv_rag_llm_base_url is None
    assert settings.jpv_rag_llm_concurrency == 8


def test_settings_reject_non_positive_pool_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.setenv("DB_POOL_SIZE", "0")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()


def test_canonical_openapi_settings_pin_rag_keys_to_absent() -> None:
    settings = canonical_openapi_settings()

    assert settings.jpv_rag_llm_api_key is None
    assert settings.jpv_rag_llm_model is None
    assert settings.jpv_rag_llm_base_url is None
    assert settings.jpv_rag_llm_concurrency == 8


def test_settings_do_not_require_embedding_key_to_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.delenv("JPV_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("JPV_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("JPV_EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("JPV_EMBEDDING_BATCH_SIZE", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.jpv_embedding_api_key is None
    assert settings.jpv_embedding_model is None
    assert settings.jpv_embedding_base_url is None
    assert settings.jpv_embedding_batch_size == 64


def test_blank_embedding_strings_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.setenv("JPV_EMBEDDING_API_KEY", "   ")
    monkeypatch.setenv("JPV_EMBEDDING_MODEL", "")
    monkeypatch.setenv("JPV_EMBEDDING_BASE_URL", " ")
    monkeypatch.setenv("JPV_EMBEDDING_BATCH_SIZE", "")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.jpv_embedding_api_key is None
    assert settings.jpv_embedding_model is None
    assert settings.jpv_embedding_base_url is None
    assert settings.jpv_embedding_batch_size == 64


def test_canonical_openapi_settings_pin_embedding_keys_to_absent() -> None:
    settings = canonical_openapi_settings()

    assert settings.jpv_embedding_api_key is None
    assert settings.jpv_embedding_model is None
    assert settings.jpv_embedding_base_url is None
    assert settings.jpv_embedding_batch_size == 64
