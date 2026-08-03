## Why

The Proyecto Final RAG service (`jbg-ai`) does not exist yet, so contracts, pgvector schema work, and corpus tooling cannot proceed in parallel. We need an empty-but-runnable Python FastAPI skeleton (config, health, logging, container, compose) as the Ola 0 foundation that unlocks C02, C05, and C06 without touching business rules or production RDS from laptops.

## What Changes

- Add new `ai-service/` Python package (`jbg_ai`) managed with `uv`, FastAPI, and pydantic-settings
- Expose public `GET /health` returning OK status and service version
- Fail fast on missing required env vars (`APP_ENV`, `SERVICE_VERSION`); `LOG_LEVEL` may default
- Add structured request logging with `trace_id` (from `X-Trace-Id` or generated)
- Add `Dockerfile` for `jbg-ai` and a `jbg-ai` service entry in `backend/docker-compose.yml` on `jpv-network` (local port published for DX only)
- **BREAKING (local dev only):** replace Compose Postgres image `postgres:15` with a pgvector-enabled PG 15 image so `vector` is available later; do not create schema `ai` or run `CREATE EXTENSION` in this change
- Add pytest smoke tests via FastAPI `TestClient` (no LLM, embeddings, or production RDS)
- Document how to run the service locally (`uv` / Compose) and which env vars are required for this change

## Capabilities

### New Capabilities
- `ai-service-runtime`: Runnable `jbg-ai` process — settings fail-fast, public health with version, structured logging with `trace_id`
- `ai-service-dev-compose`: Local container wiring for `jbg-ai` plus pgvector-ready Postgres image on the existing Compose network

### Modified Capabilities
- _(none)_ — no existing OpenSpec capability requirements change; Compose Postgres image swap is covered by the new `ai-service-dev-compose` capability

## Impact

- **New code:** `ai-service/` (`pyproject.toml`, `src/jbg_ai/`, `tests/`, `Dockerfile`, README)
- **Infra:** `backend/docker-compose.yml` (new service + Postgres image); may require recreating the local `postgres_data` volume
- **APIs:** only `GET /health` on `jbg-ai` (not exposed via nginx; frontend still does not talk to Python)
- **Dependencies:** Python/`uv`, FastAPI, pydantic-settings, pytest; no JWT, DB client, or LLM SDK required yet
- **Out of scope:** JWT/auth and domain routers (C02), `CREATE EXTENSION vector` / schema `ai` / Alembic (C05), enrichment/feeds/indexing, ECR/EC2 deploy and enriched health (C17), any SQL access to `public`
- **Traceability:** HU-AIENG-001; plan change C01 `init-ai-service-skeleton`
