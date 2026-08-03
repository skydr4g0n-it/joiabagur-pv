## Context

Proyecto Final RAG introduces a Python FastAPI microservice (`jbg-ai`) beside the existing .NET API. Today there is no `ai-service/` tree and local Compose uses `postgres:15` without pgvector. Production already runs RDS PostgreSQL **15.17** (same DB `jpv`); vectors will later live in schema `ai` while business data stays in `public`. This change is Ola 0 / C01 / HU-AIENG-001: ship an empty-but-runnable skeleton so C02 (contracts/auth), C05 (pgvector schema), and C06 (corpus) can proceed in parallel.

Stakeholders: the two PF developers. End users do not see this service yet; the SPA never calls Python directly.

## Goals / Non-Goals

**Goals:**

- Runnable `jbg-ai` with `uv`, FastAPI, pydantic-settings, public `GET /health` (status + version)
- Fail-fast for minimal required env (`APP_ENV`, `SERVICE_VERSION`); `LOG_LEVEL` may default
- Structured logging with `trace_id` (header `X-Trace-Id` or generated UUID)
- Dockerfile + Compose service on `jpv-network`; local port published for DX only
- Local Postgres image switched to pgvector-ready PG 15 so C05 can `CREATE EXTENSION vector` without another image migration
- Pytest + `TestClient` smoke tests with no LLM/RDS calls

**Non-Goals:**

- JWT internal auth, domain routers, OpenAPI snapshot (C02)
- `CREATE EXTENSION vector`, schema `ai`, dedicated DB role, Alembic tables (C05)
- Any SQL read/write to `public`; enrichment, feeds, indexing
- Production deploy (ECR/EC2/nginx/SSM) or enriched health (DB/provider/index) (C17)
- Laptop connections to production RDS

## Decisions

### 1. Same production database, schema split later — not a second RDS

- **Choice:** Keep one RDS instance / DB `jpv`; introduce schema `ai` in C05.
- **Why:** Design §6 — one ops surface, SQL filters beside vectors, ~1.5k embeddings do not justify a second engine.
- **Alternatives discarded:** Second RDS or second database on same instance (extra sync/ops with no isolation win). Plan-B container Postgres on EC2 only if `vector` were unavailable (not the case on 15.17).

### 2. Minimal required settings in C01

- **Choice:** Require `APP_ENV` and `SERVICE_VERSION`; allow `LOG_LEVEL` default (`INFO`). Defer `DATABASE_URL`, JWT secret, LLM keys.
- **Why:** Skeleton must boot and pass `TestClient` without Postgres or secrets; fail-fast still demonstrable.
- **Alternatives discarded:** Full production env from day one (blocks smoke); zero required vars (silent misconfig).

### 3. Compose lives under `backend/`; publish port only locally

- **Choice:** Extend `backend/docker-compose.yml`; map e.g. `8001:8000` for local DX; do not wire nginx.
- **Why:** Repo already owns Compose under `backend/`; “no published port” applies to prod exposure (C17), not local curl.
- **Alternatives discarded:** New root `docker-compose.yml` (split DX); no local ports (poor DX); full prod deploy in C01 (belongs to C17).

### 4. Adopt pgvector Postgres image in C01; defer extension/schema to C05

- **Choice:** Replace `postgres:15` with `pgvector/pgvector:pg15` (or equivalent). Do not run `CREATE EXTENSION` or create `ai` here.
- **Why:** Unblocks C05 immediately; avoids spending the schema session on image/volume churn.
- **Alternatives discarded:** Leave image change to C05 (friction on critical path); compile pgvector onto stock Postgres; point laptops at RDS.

### 5. Package layout: settings inside `jbg_ai`

- **Choice:** `ai-service/src/jbg_ai/config/settings.py` with src-layout + `uv`.
- **Why:** Importable package path; ready for C02 routers and C05 Alembic siblings.
- **Alternatives discarded:** Top-level `ai-service/config/` outside the package (PYTHONPATH hacks).

### 6. `trace_id` without JWT

- **Choice:** Middleware reads `X-Trace-Id` or generates UUID; bind into structured logs; echo on response when practical.
- **Why:** C14 already expects stage logs with `trace_id`; C02 will prefer JWT claim later without rewriting the logging seam.
- **Alternatives discarded:** Wait for JWT before any correlation id (blind logs for O0).

### 7. Capability split

- **Choice:** `ai-service-runtime` (process behavior) + `ai-service-dev-compose` (local containers/image).
- **Why:** Specs stay testable and separable; runtime tests vs Compose concerns.

## Risks / Trade-offs

- **[Risk] Recreating local `postgres_data` after image swap loses local DB state** → Mitigation: document `docker compose down -v`; acceptable in O0 without real catalog.
- **[Risk] Developers forget new required env vars** → Mitigation: README + fail-fast error naming missing keys; Compose `environment:` supplies defaults for local.
- **[Risk] Residual doubt on RDS `vector` availability** → Mitigation: 15.17 is supported per AWS; optional live `pg_available_extensions` check before C05; `CREATE EXTENSION` remains C05.
- **[Trade-off] Local port published vs prod “internal only”** → Accepted asymmetry; nginx exposure stays C17.
- **[Trade-off] No DB client in C01** → Health cannot check Postgres yet; intentional (enriched health in C17).

## Migration Plan

1. Land `ai-service/` and Compose updates on branch; run `uv sync` / pytest.
2. Locally: pull new Postgres image; recreate volume if needed; `docker compose up` and hit `/health`.
3. No production deploy in this change; no RDS migration; no EF changes.
4. Rollback: revert Compose service + image pin; remove `ai-service/` tree. No data migration to undo in prod.

## Open Questions

- Exact Compose host port for `jbg-ai` (proposal default **8001**) — confirm with teammate if 8001 conflicts.
- Pin exact pgvector image tag (`pg15` vs digest) for reproducible CI — decide at apply time from current Hub tags.
