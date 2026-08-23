# jbg-ai

Python FastAPI microservice for the JoiaBagur Proyecto Final RAG.

- **C01** (HU-AIENG-001) shipped the runnable skeleton: settings, public health, structured `trace_id` logging, container and Compose wiring.
- **C02** (HU-AIENG-002) freezes the HTTP contract: eight `/v1` endpoints with complete Pydantic models, an internal HS256 service token, deterministic stubs, and a versioned `openapi.json`.
- **C05** (HU-AIENG-005) adds the persistence foundation: `vector` extension, schema `ai`, a dedicated database role, Alembic migrations and six empty index tables with their indexes. No data, no queries — see [Database and migrations](#database-and-migrations).
- **C08** (HU-AIENG-008) **renegotiates the enrichment contract** and opens catalog-wide auth. `POST /v1/enrich/products` now returns `source` (`rule` | `inferred`) on every proposed value, plus `piece_type`, `stone_type`, `size_label`, tags split into `color_tags` / `style_tags` / `occasion_tags`, and `prompt_version` on the response. Without per-field provenance the .NET side cannot tell a value a rule produced from one a model inferred, which is the whole of its hybrid review policy. Catalog-wide routes (`/v1/enrich/*`) authenticate through `get_catalog_principal`, which does **not** require `pos_id`; retrieval, assistance and inventory keep requiring it, and a token without it is still rejected there with 401.
- **C06a** (HU-AIENG-006a) ships the real-catalog corpus **outside this service**: offline scripts in `scripts/catalog/`, JSONL in `data/catalog/real/generated/`. No LLM client, no Alembic `text_provenance`, no writes to `public` from `jbg-ai`.
- **C06b** (HU-AIENG-006b) adds the **CLI** `python -m jbg_ai.data` (`generate` / `ingest`) under `jbg_ai.data`. `api.main` does not import it. Generate reads `JPV_CATALOG_LLM_API_KEY` from `backend/.env` (host only; not the RAG key). `GET /health` does not need it. See [`src/jbg_ai/data/README.md`](src/jbg_ai/data/README.md).
- **C09** (HU-AIENG-009) replaces the enrichment stub when `STUB_MODE=false`: closed vocabularies, size regex on `Name` then `Description` (never SKU), LiteLLM at temperature 0 (`JPV_RAG_LLM_*`), confidence by evidence span, `prompt_version = enrichment/v1`. Batch quality gates live in an auditor, not as HTTP 422. Compose and the OpenAPI snapshot stay on `STUB_MODE=true` until a RAG key exists. See [`prompts/enrichment/v1.md`](prompts/enrichment/v1.md).
- **C10** (HU-AIENG-010) adds nested CLI `python -m jbg_ai.data world simulate|ingest` under `jbg_ai.data.world`. Simulate is offline (YAML of 12 POS, no Postgres, no LLM). Ingest uses `JPV_PG*` against local Docker and does not touch `"Products"` / `"Collections"` / schema `ai`. Recipe: [`../data/world/pos-profiles.yaml`](../data/world/pos-profiles.yaml). See [`src/jbg_ai/data/README.md`](src/jbg_ai/data/README.md).

Boundary rule: *Python computes similarity and writes prose; .NET computes numbers and decides.* The service never emits a price or stock figure and never touches schema `public`.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker / Docker Compose (optional, for the full local stack)

## Required environment

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `APP_ENV` | yes | — | e.g. `local`, `dev`, `prod` |
| `SERVICE_VERSION` | yes | — | echoed by `GET /health` |
| `JWT_SECRET` | yes | — | HS256 secret shared with the .NET API; ≥ 32 bytes |
| `LOG_LEVEL` | no | `INFO` | standard Python logging level |
| `JWT_TTL_SECONDS` | no | `300` | documented TTL; the .NET API is the issuer |
| `STUB_MODE` | no | `true` | serve deterministic fixtures instead of real logic |
| `ENABLE_DEV_ENDPOINTS` | no | `true` unless `APP_ENV` is `prod`/`production` | mounts `GET /v1/evals/runs` |
| `DATABASE_URL` | no | — | `postgresql+psycopg://…`; its absence does not stop the service booting |
| `DB_POOL_SIZE` | no | `5` | hard ceiling on simultaneous connections; no overflow |
| `JPV_CATALOG_LLM_API_KEY` | no | — | C06b `generate` only (host `backend/.env`). Distinct from `JPV_RAG_LLM_API_KEY`. Absence does not block `/health` |
| `JPV_CATALOG_LLM_MODEL` | no | — | optional; CLI default `gpt-4o` |
| `JPV_CATALOG_LLM_BASE_URL` | no | — | optional OpenAI-compatible proxy; empty = api.openai.com |
| `JPV_PG*` | no | — | Host CLI ingest only (C06b catalog, C10 world). `backend/.env`, port 5433. Absence does not block `/health` |
| `JPV_RAG_LLM_API_KEY` | no | — | C09 runtime enrichment (LiteLLM). Distinct from `JPV_CATALOG_LLM_API_KEY`. Absence does not block `/health`; real enrich requires it |
| `JPV_RAG_LLM_MODEL` | no | — | provider-prefixed id (e.g. `openai/gpt-4o`) |
| `JPV_RAG_LLM_BASE_URL` | no | — | optional LiteLLM `api_base`; empty = provider default |
| `JPV_RAG_LLM_CONCURRENCY` | no | `8` | in-flight enrichment calls inside a batch of ≤ 50 |

Missing or blank `APP_ENV`, `SERVICE_VERSION` or `JWT_SECRET` aborts startup (fail-fast), so the process never serves `/v1` half-configured.

`DATABASE_URL` is **optional on purpose**. The service must boot with no database — that is a requirement of `ai-service-dev-compose`, not an accident — so the engine is built on first use and never at import time. Under `STUB_MODE` nothing asks for a session, so the container starts fine against a database that has not even been provisioned. LLM keys are not required to boot `/health`; the catalog CLI reads `JPV_CATALOG_LLM_*` from `backend/.env`. Real `POST /v1/enrich/products` (`STUB_MODE=false`) requires `JPV_RAG_LLM_API_KEY` and fails explicitly if it is missing — it does not invent profiles and does not return 501.

## Frozen endpoints (C02)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/health` | public | unchanged since C01 |
| `POST` | `/v1/retrieval/products` | Bearer | returns `min(top_k × 3, 60)` candidates, reported in `candidates_returned` |
| `POST` | `/v1/retrieval/substitutes` | Bearer | retrieval result shape plus `similarity_signals` |
| `POST` | `/v1/assist/sale` | Bearer | `groups[]` by `family_id`; `pitch` keeps `{{price}}` / `{{stock}}` unresolved |
| `POST` | `/v1/inventory/propose` | Bearer | prioritized proposals, never quantities |
| `POST` | `/v1/enrich/products` | Bearer | proposed profiles with per-field confidence |
| `POST` | `/v1/index/sync` | Bearer | `since` cursor, upsert counters |
| `GET` | `/v1/index/status` | Bearer | `drift_count`, `last_full_sync_at` |
| `GET` | `/v1/evals/runs` | Bearer | **development profile only** |

None of these is exposed through nginx: the SPA never talks to Python.

## Internal service token

The .NET API (C03) is the only issuer. Tokens are HS256, signed with `JWT_SECRET`, and must carry all four claims — names are frozen in `snake_case` on the wire:

| Claim | Meaning |
|---|---|
| `user_id` | acting user on the .NET side |
| `role` | `Admin` or `Operator` |
| `pos_id` | point-of-sale scope |
| `trace_id` | correlation id, preferred over the `X-Trace-Id` header |

Rules that C03 must rely on:

- **The token wins.** `pos_id` and `role` always come from the token. Requests may carry `pos_id` in the body for client compatibility; it is ignored, and a mismatch is neither an error nor a behavior change. Scoped responses echo the applied scope in `effective_pos_id`.
- Any missing, malformed, wrongly signed, expired or incomplete token gets a single opaque **401** that never says which check failed.
- `GET /health` is exempt.

## Stubs and 501

With `STUB_MODE=true` (the local and test default) every `/v1` route answers from deterministic fixtures: no LLM, no embeddings, no database, no clock. The same request always returns the same body, so the .NET client can assert its mapping against them.

With `STUB_MODE=false` a route whose real logic does not exist yet answers **501** naming the change that will deliver it (C13 index, C14 retrieval, C24 evals, C26 substitutes, C30 assist, C35 inventory). `POST /v1/enrich/products` is C09: the real pipeline, or 503 if `JPV_RAG_LLM_API_KEY` is missing — never 501. Later changes replace handlers one at a time; the contract frozen here is the one they must respect.

## OpenAPI snapshot

`ai-service/openapi.json` is the published contract, and `test_openapi_snapshot_is_stable` fails whenever the live schema drifts from it. `docs_url` stays disabled: the artifact is the snapshot, not a browsable UI.

**Canonical profile.** The snapshot is generated with `canonical_openapi_settings()` — `APP_ENV=local`, `SERVICE_VERSION=0.1.0`, stubs on and development endpoints **enabled**, so `/v1/evals/runs` is part of the published contract. A production deployment would not serve that path; that asymmetry is deliberate. Pinning one profile in code is what keeps the snapshot deterministic and stops the test and the regeneration below from using different settings.

**Regenerating is a contract negotiation, not a chore.** A failing snapshot test means the frozen boundary moved — agree the change with whoever owns the .NET client before regenerating:

```bash
cd ai-service
uv run python -c "import json; from pathlib import Path; from jbg_ai.api.main import create_app; from jbg_ai.config import canonical_openapi_settings; Path('openapi.json').write_text(json.dumps(create_app(canonical_openapi_settings()).openapi(), indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')"
```

On PowerShell, wrap the same one-liner in single quotes:

```powershell
cd ai-service
uv run python -c 'import json; from pathlib import Path; from jbg_ai.api.main import create_app; from jbg_ai.config import canonical_openapi_settings; Path("openapi.json").write_text(json.dumps(create_app(canonical_openapi_settings()).openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")'
```

## Run locally with uv

```bash
cd ai-service
uv sync --system-certs   # use --system-certs only if TLS to PyPI fails
export APP_ENV=local
export SERVICE_VERSION=0.1.0
export JWT_SECRET=local-dev-jwt-secret-0123456789abcdef
uv run uvicorn jbg_ai.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

On PowerShell:

```powershell
cd ai-service
uv sync --system-certs
$env:APP_ENV = "local"
$env:SERVICE_VERSION = "0.1.0"
$env:JWT_SECRET = "local-dev-jwt-secret-0123456789abcdef"
uv run uvicorn jbg_ai.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Smoke checks:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/v1/retrieval/products \
  -H "Content-Type: application/json" -d '{"query":"anillo","top_k":5}'
```

Health returns HTTP 200 with `{"status":"OK","version":"0.1.0"}`. The `/v1` call returns **401** without a token — that is the expected answer. To exercise it, sign a token with the same secret and the four claims, then send `Authorization: Bearer <token>`.

## Run with Docker Compose

From `backend/`:

```bash
docker compose up --build jbg-ai
```

```bash
curl http://127.0.0.1:8001/health
```

The Compose service supplies `JWT_SECRET` and `STUB_MODE` so the container boots with no extra setup. That secret is a **local placeholder**: production takes it from SSM `/jpv/prod/*` in C17 and must never reuse it. `jbg-ai` joins `jpv-network` and opens no database connection.

### Postgres image (pgvector) — volume recreate

Compose Postgres uses `pgvector/pgvector:pg15` instead of `postgres:15`. After pulling the new image, if the existing `postgres_data` volume was created with the old image, recreate it:

```bash
cd backend
docker compose down -v
docker compose up -d postgres
```

`-v` deletes local volume data. Acceptable in O0 when there is no real catalog. Bringing Compose up does **not** create schema `ai` or run `CREATE EXTENSION vector` — that is the one-off provisioning below.

## Database and migrations

Schema `ai` belongs to `jbg-ai`; schema `public` belongs to the .NET API. **Python never writes to `public` and never reads it by SQL** — it reads the business side over HTTP through the paginated feeds. That boundary is enforced by database grants, not by convention: the `jbg_ai` role gets `permission denied` on `public`.

### 1. Provision once, with administrator privileges

`migrations/bootstrap.sql` installs the extension, creates schema `ai`, creates the dedicated role and grants it the minimum it needs. It is **not** an Alembic migration, and deliberately so: roles are cluster-level objects, so creating one from a migration would demand role-creation privilege from whoever migrates and would make a clean revert impossible.

```bash
cd ai-service
docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv \
  -v ai_password=local-dev-ai-password < migrations/bootstrap.sql
```

Pass the password **raw, without quoting it yourself**: psql's `:'var'` already renders it as a quoted literal, so pre-quoting creates a password that literally contains apostrophes and then fails to authenticate.

Re-running it is safe: the extension and schema are `IF NOT EXISTS`, and an existing role keeps its password — so the script can never silently rotate a production credential. Change one deliberately with `ALTER ROLE jbg_ai PASSWORD '...'`.

In production this step belongs to **C17**, run by the RDS master user. Because the migration also declares the extension idempotently, the same `DATABASE_URL` works in both worlds — locally the extension gets installed, on RDS the migration finds it already there. No second admin connection string is needed.

### 2. Migrate

```bash
cd ai-service
export DATABASE_URL="postgresql+psycopg://jbg_ai:local-dev-ai-password@localhost:5433/joiabagur_pv"
uv run alembic upgrade head
```

```powershell
cd ai-service
$env:DATABASE_URL = "postgresql+psycopg://jbg_ai:local-dev-ai-password@localhost:5433/joiabagur_pv"
uv run alembic upgrade head
```

`alembic downgrade base` reverts it. The revert drops the six tables and **keeps** schema `ai` and the extension: the extension is shared database-wide, and the schema holds Alembic's own version table.

Two details worth knowing before editing anything here:

- **The version table lives in `ai`**, not in `public`. Alembic's default would break the ownership boundary in the project's first Python migration, silently.
- **The schema is provisioned in `env.py`, not in the first revision.** Alembic materialises its version table *before* running any revision, so a `CREATE SCHEMA` inside `upgrade()` would arrive after the failure it was meant to prevent.

### One driver, two callers

`postgresql+psycopg://` is psycopg 3, which speaks sync for Alembic and async for FastAPI, so a single connection string serves both. Choosing `asyncpg` would have meant two URL forms and someone remembering to translate between them in every environment.

> **Windows caveat.** psycopg's async mode does not work with `ProactorEventLoop`, Python's default event loop on Windows; it needs `WindowsSelectorEventLoopPolicy`. This does not affect production (Linux container) or the test suite (Alembic is sync), only running the app with uvicorn directly on a Windows host once a route actually touches the database.

## Tests

```bash
cd ai-service
uv run --system-certs pytest
```

Tests inject required env / settings in-process, sign their own tokens, and never call LLM providers, embedding APIs, or production RDS. The stub tests additionally block socket connections to prove it.

The suite mirrors the `src/jbg_ai/` package — `tests/api/`, `tests/config/`, `tests/data/`, `tests/migrations/`, and a
`tests/support/` for shared helpers (including `fake_llm.py`). [`tests/README.md`](tests/README.md) explains where a new test
goes and which folder each upcoming change lands in.

### Migration tests need Docker

`tests/migrations/` runs against a **throwaway pgvector container**, with a fresh database per test so the reversibility test cannot leak schema state into its neighbours. They are marked `db`:

```bash
uv run --system-certs pytest -m db        # only the database tests
uv run --system-certs pytest -m "not db"  # everything else
```

**Without a reachable Docker they are skipped, not failed.** There is no CI running the Python suite yet, so permanent red on a laptop would teach everyone to ignore red — which costs more than these four tests are worth. The flip side is real and worth saying out loud: a green run does not by itself prove the migration was exercised. Check that the `db` tests ran, not just that nothing failed.

These four tests exist to catch failures that produce **no error at all**: an HNSW index built with the wrong operator class is silently never used, Alembic's version table lands in `public` without complaint, and an orphaned type survives a revert to break the *next* upgrade weeks later.

## Explicit non-goals

- No real retrieval, indexing or agent loops — stubs are replaced route by route in later changes. Enrichment is real when `STUB_MODE=false` (C09)
- No `POST /v1/retrieval/complementary` or `POST /v1/families/suggest` — later OpenAPI negotiation
- No rows: the six `ai.*` tables ship empty and are populated by C13 (catalog), C22 (POS projection) and C23 (knowledge)
- No queries, no similarity search, no ORM models or repositories — typed access is born in C11/C13
- No `ai.eval_*` tables (C24) and no `ai.query_log` (unassigned; see the change's open questions)
- No SQL access to schema `public`, ever
- No production deploy, SSM, enriched health or `CREATE EXTENSION` on RDS (C17)
- No production tuning: `halfvec`, `hnsw.iterative_scan`, `CREATE INDEX CONCURRENTLY` and the `VACUUM`/`REINDEX` cycle are deliberate omissions at ~1,500 vectors, not oversights

## Layout

```
ai-service/
  src/jbg_ai/
    api/
      main.py       # app factory, /health, router mounting
      auth.py       # HS256 decode + ServicePrincipal
      deps.py       # auth dependency, settings access, 501 guard
      middleware.py # trace_id correlation
      routers/      # retrieval, assist, inventory, enrich, index, evals
      schemas/      # frozen request/response contracts
    config/         # pydantic-settings + canonical OpenAPI profile
    db/             # lazy async engine, bounded pool
    stubs/          # deterministic fixtures
    data/           # C06b generate/ingest + C10 world/; not imported by api.main
    enrichment/     # C09 extractor: vocabs, size regex, LiteLLM port, auditor
  prompts/          # versioned prompts: catalog-synth/v3 (C06b generate) + enrichment/v1 (C09 extract)
  migrations/
    bootstrap.sql   # one-off: extension, schema, dedicated role, grants
    env.py          # version table in `ai`; provisions before revisions run
    versions/       # hand-written revisions (no autogenerate)
  tests/            # mirrors src/jbg_ai — see tests/README.md
    api/            # contract, auth, stubs, OpenAPI snapshot
    config/         # settings and fail-fast validation
    data/           # C06b catalog CLI + C10 world/ (no provider sockets)
    migrations/     # schema, indexes, reversibility (marked `db`)
    support/        # shared helpers and injectable fakes
  alembic.ini       # no connection string: read from DATABASE_URL
  openapi.json      # versioned contract snapshot
  Dockerfile
  pyproject.toml
```
