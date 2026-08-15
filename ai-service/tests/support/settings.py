"""In-process settings builder and token constants for tests.

Lives here rather than in `conftest.py` because tests import these directly:
`conftest.py` is pytest's fixture mechanism, not an importable module, and the
flat import only ever worked while every test sat in one directory.
"""

from __future__ import annotations

from typing import Any

from jbg_ai.config.settings import Settings

# HS256 keys shorter than 32 bytes make PyJWT warn; keep fixtures above the bar.
TEST_JWT_SECRET = "test-jwt-secret-0123456789abcdefghij"
TOKEN_POS_ID = "POS-B"
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
    }
    values.update(overrides)
    return Settings(**values)
