"""Project paths anchored once, so no test has to count parent directories.

`Path(__file__).parents[N]` in a test file breaks as soon as the test moves to a
different depth. This module never moves, so tests import from here instead.
"""

from __future__ import annotations

from pathlib import Path

#: `ai-service/` — this file is at `ai-service/tests/support/paths.py`.
AI_SERVICE_ROOT = Path(__file__).resolve().parents[2]

#: Repository root (parent of `ai-service/`).
REPO_ROOT = AI_SERVICE_ROOT.parent

#: C06a committed real corpus — occupied SKUs and collection names for C06b.
REAL_CATALOG_JSONL = (
    REPO_ROOT / "data" / "catalog" / "real" / "generated" / "catalog-real-enriched.jsonl"
)

#: The frozen contract snapshot shared with the .NET client.
OPENAPI_SNAPSHOT = AI_SERVICE_ROOT / "openapi.json"

#: Alembic configuration, so migration tests drive the real migrations rather
#: than a hand-written copy of the schema that could drift from them.
ALEMBIC_INI = AI_SERVICE_ROOT / "alembic.ini"

#: Revision scripts and the migration environment.
MIGRATIONS_DIR = AI_SERVICE_ROOT / "migrations"

#: One-off provisioning: extension, schema, dedicated role and grants. Executed
#: with psql rather than a driver, because it uses psql meta-commands.
BOOTSTRAP_SQL = MIGRATIONS_DIR / "bootstrap.sql"
