# jbg-ai

Python FastAPI microservice for the JoiaBagur Proyecto Final RAG.

- **C01** (HU-AIENG-001) shipped the runnable skeleton: settings, public health, structured `trace_id` logging, container and Compose wiring.
- **C02** (HU-AIENG-002) freezes the HTTP contract: eight `/v1` endpoints with complete Pydantic models, an internal HS256 service token, deterministic stubs, and a versioned `openapi.json`.

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

Missing or blank `APP_ENV`, `SERVICE_VERSION` or `JWT_SECRET` aborts startup (fail-fast), so the process never serves `/v1` half-configured.

`DATABASE_URL` and LLM keys are still **not** required: C02 has no database access and calls no model.

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

With `STUB_MODE=false` a route whose real logic does not exist yet answers **501** naming the change that will deliver it (C09 enrich, C13 index, C14 retrieval, C24 evals, C26 substitutes, C30 assist, C35 inventory). Later changes replace handlers one at a time; the contract frozen here is the one they must respect.

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

`-v` deletes local volume data. Acceptable in O0 when there is no real catalog. This change does **not** create schema `ai` or run `CREATE EXTENSION vector` (reserved for C05).

## Tests

```bash
cd ai-service
uv run --system-certs pytest
```

Tests inject required env / settings in-process, sign their own tokens, and never call LLM providers, embedding APIs, or production RDS. The stub tests additionally block socket connections to prove it.

The suite mirrors the `src/jbg_ai/` package — `tests/api/`, `tests/config/`, and a
`tests/support/` for shared helpers. [`tests/README.md`](tests/README.md) explains where a new test
goes and which folder each upcoming change lands in.

## Explicit non-goals (C02)

- No real retrieval, enrichment, indexing or agent loops — stubs are replaced route by route in later changes
- No JWT issuance or typed .NET client with Polly (C03)
- No `POST /v1/retrieval/complementary` or `POST /v1/families/suggest` — later OpenAPI negotiation
- No DB client, Alembic, schema `ai`, or `CREATE EXTENSION vector` (C05)
- No SQL access to schema `public`, ever
- No production deploy, SSM or enriched health (C17)

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
    stubs/          # deterministic fixtures
  tests/            # mirrors src/jbg_ai — see tests/README.md
    api/            # contract, auth, stubs, OpenAPI snapshot
    config/         # settings and fail-fast validation
    support/        # shared helpers and injectable fakes
  openapi.json      # versioned contract snapshot
  Dockerfile
  pyproject.toml
```
