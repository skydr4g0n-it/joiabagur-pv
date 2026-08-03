# jbg-ai (C01 skeleton)

Python FastAPI microservice for the JoiaBagur Proyecto Final RAG. This change (Ola 0 / C01 / HU-AIENG-001) ships an empty-but-runnable skeleton: settings, public health, structured `trace_id` logging, container, and Compose wiring.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker / Docker Compose (optional, for the full local stack)

## Required environment (C01)

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `APP_ENV` | yes | — | e.g. `local`, `dev` |
| `SERVICE_VERSION` | yes | — | echoed by `GET /health` |
| `LOG_LEVEL` | no | `INFO` | standard Python logging level |

Missing `APP_ENV` or `SERVICE_VERSION` aborts startup (fail-fast).

`DATABASE_URL`, JWT secrets, and LLM keys are **not** required in C01.

## Run locally with uv

```bash
cd ai-service
uv sync --system-certs   # use --system-certs only if TLS to PyPI fails
set APP_ENV=local
set SERVICE_VERSION=0.1.0
uv run uvicorn jbg_ai.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

On PowerShell:

```powershell
cd ai-service
uv sync --system-certs
$env:APP_ENV = "local"
$env:SERVICE_VERSION = "0.1.0"
uv run uvicorn jbg_ai.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Smoke check:

```bash
curl http://127.0.0.1:8000/health
```

Expected: HTTP 200 with `{"status":"OK","version":"0.1.0"}` (version matches `SERVICE_VERSION`). Optional: send `X-Trace-Id`; the same value is returned on the response.

## Run with Docker Compose

From `backend/`:

```bash
docker compose up --build jbg-ai
```

Health from the host (local DX port only — not a production exposure):

```bash
curl http://127.0.0.1:8001/health
```

`jbg-ai` joins `jpv-network` with the rest of the stack. It does **not** open a database connection in C01.

### Postgres image (pgvector) — volume recreate

Compose Postgres uses `pgvector/pgvector:pg15` instead of `postgres:15`. After pulling the new image, if the existing `postgres_data` volume was created with the old image, recreate it:

```bash
cd backend
docker compose down -v
docker compose up -d postgres
```

`-v` deletes local volume data. Acceptable in O0 when there is no real catalog. This change does **not** create schema `ai` or run `CREATE EXTENSION vector` (reserved for C05).

## Tests

```bash
cd ai-service
uv run --system-certs pytest
```

Tests inject required env / settings in-process and never call LLM providers, embedding APIs, or production RDS.

## Explicit non-goals (C01)

- No JWT / internal auth (C02)
- No domain routers or OpenAPI contract snapshot (C02)
- No DB client, Alembic, schema `ai`, or `CREATE EXTENSION vector` (C05)
- No laptop connections to production RDS
- No enrichment, feeds, indexing, or production deploy (C17)

## Layout

```
ai-service/
  src/jbg_ai/
    api/          # FastAPI factory, middleware, /health
    config/       # pydantic-settings
  tests/
  Dockerfile
  pyproject.toml
```
