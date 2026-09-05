"""In-process settings builder and token constants for tests.

Lives here rather than in `conftest.py` because tests import these directly:
`conftest.py` is pytest's fixture mechanism, not an importable module, and the
flat import only ever worked while every test sat in one directory.
"""

from __future__ import annotations

from typing import Any

from jbg_ai.config.settings import FUSION_DEFAULTS, Settings

# HS256 keys shorter than 32 bytes make PyJWT warn; keep fixtures above the bar.
TEST_JWT_SECRET = "test-jwt-secret-0123456789abcdefghij"

#: The point of sale the fixture token is issued for. A canonical UUID because
#: `AiServiceTokenFactory` signs `pointOfSaleId.ToString()`, and because the retriever now
#: parses this claim: a placeholder like `POS-B` was accepted for as long as nothing read
#: it, and would have started producing 422 the day the scope landed.
TOKEN_POS_ID = "b0000000-0000-4000-8000-000000000002"

#: A different, equally valid point of sale. Used where a test has to show the body value
#: being ignored, which needs two identifiers that are both plausible.
OTHER_POS_ID = "a0000000-0000-4000-8000-000000000001"

TOKEN_TRACE_ID = "trace-from-token"


def build_settings(**overrides: Any) -> Settings:
    """In-process settings — no external services.

    `database_url` is pinned to `None` rather than left to its default: pydantic
    reads unset fields from the environment, so a developer with `DATABASE_URL`
    exported would otherwise see tests build engines against their own database
    and the "absent configuration" cases would stop failing as they should.
    """
    values: dict[str, Any] = {
        "app_env": "test",
        "service_version": "0.1.0-test",
        "log_level": "WARNING",
        "jwt_secret": TEST_JWT_SECRET,
        "database_url": None,
        "jpv_catalog_llm_api_key": None,
        "jpv_catalog_llm_model": None,
        "jpv_catalog_llm_base_url": None,
        "jpv_rag_llm_api_key": None,
        "jpv_rag_llm_model": None,
        "jpv_rag_llm_base_url": None,
        "jpv_rag_llm_concurrency": 8,
        "jpv_embedding_api_key": None,
        "jpv_embedding_model": None,
        "jpv_embedding_base_url": None,
        "jpv_embedding_batch_size": 64,
        "jpv_index_feed_base_url": None,
        "jpv_index_feed_api_key": None,
        "jpv_index_sync_time_budget_seconds": 180,
        "jpv_retrieval_distance_threshold": 0.65,
        "jpv_query_expansion_enabled": True,
        "jpv_pos_prefilter_enabled": True,
        "jpv_pos_projection_max_age_seconds": 3600,
        **FUSION_DEFAULTS,
    }
    values.update(overrides)
    return Settings(**values)
