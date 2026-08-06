## Why

After C01 (`init-ai-service-skeleton`) `jbg-ai` only exposes `GET /health`, so the Python ↔ .NET boundary is still undefined: the typed .NET client (C03) and the vertical slice (C14–C16) cannot start, and the two Proyecto Final developers block each other for weeks. Freezing the `/v1` HTTP contracts plus the internal service JWT now — behind deterministic stubs, with no LLM, embeddings or database — lets both sides advance in parallel and makes any later contract drift an explicit, test-enforced negotiation.

## What Changes

- Add domain routers under `/v1/`: `retrieval`, `assist`, `inventory`, `enrich`, `index` and `evals`, with complete Pydantic request/response models
- Freeze eight internal endpoints (JWT required): `POST /v1/retrieval/products`, `POST /v1/retrieval/substitutes`, `POST /v1/assist/sale`, `POST /v1/inventory/propose`, `POST /v1/enrich/products`, `POST /v1/index/sync`, `GET /v1/index/status`, `GET /v1/evals/runs` (development profile only)
- Adopt the v3 contract fields: `materials` as a list, `family_id` / `variant_label`, and observable over-retrieval (`top_k` requested vs `candidates_returned` returned)
- Add internal HS256 JWT validation (`PyJWT`) as a FastAPI dependency producing a `ServicePrincipal` from claims `user_id`, `role`, `pos_id`, `trace_id`; `/v1/*` answers 401 without a valid token, `GET /health` stays public and unchanged
- Establish the boundary rule **the token wins**: `pos_id` and `role` always come from the JWT; the optional `pos_id` in request bodies is accepted for OpenAPI compatibility and ignored
- Add deterministic stubs behind `STUB_MODE` (default `true`), with no external I/O; when `STUB_MODE=false` and no real implementation exists yet, the route answers HTTP 501 naming the change that will deliver it
- Extend settings with `JWT_SECRET` (required, fail-fast), `JWT_TTL_SECONDS` (default `300`), `STUB_MODE` (default `true`) and `ENABLE_DEV_ENDPOINTS` (derived from `APP_ENV`, gates the evals route)
- Prefer the JWT `trace_id` claim over the C01 `TraceIdMiddleware` value when the claim is present
- Version `ai-service/openapi.json`, generated from the documented canonical development profile, with a snapshot test that fails on any contract drift
- Update `backend/docker-compose.yml` (`JWT_SECRET`, `STUB_MODE`) and `ai-service/README.md` (required env table, canonical profile, manual snapshot regeneration one-liner)
- No breaking change for external consumers — there are none yet; local Compose does need the new variables or the container fails fast

## Capabilities

### New Capabilities
- `ai-service-api-contracts`: Frozen `/v1` HTTP surface of `jbg-ai` — domain routers, Pydantic request/response models, deterministic stub behavior (over-retrieval cap, family grouping, unresolved `{{price}}` / `{{stock}}` placeholders), 501 when stubs are off, development-only evals route, and the versioned OpenAPI snapshot
- `ai-service-auth`: Internal service authentication — HS256 JWT validation, required claims, `ServicePrincipal`, 401 semantics without leaking the cause, and token-over-body precedence for `pos_id` / `role`

### Modified Capabilities
- `ai-service-runtime`: Required settings now include `JWT_SECRET` (fail-fast when missing or empty) alongside `APP_ENV` / `SERVICE_VERSION`, plus optional `JWT_TTL_SECONDS`, `STUB_MODE` and `ENABLE_DEV_ENDPOINTS`; `trace_id` resolution prefers the JWT claim and falls back to the existing middleware behavior
- `ai-service-dev-compose`: The local Compose `jbg-ai` service MUST supply the new required environment (`JWT_SECRET`, `STUB_MODE`) so the container still boots locally

## Impact

- **Code:** `ai-service/src/jbg_ai/` — `api/auth.py`, `api/deps.py`, `api/routers/{retrieval,assist,inventory,enrich,index,evals}.py`, `api/schemas/`, `stubs/responses.py`, `config/settings.py`, `api/main.py` (router mounting)
- **Artifacts:** new versioned `ai-service/openapi.json`; new tests `tests/test_auth.py`, `test_retrieval_stub.py`, `test_assist_stub.py`, `test_stub_mode.py`, `test_openapi_snapshot.py`, `test_evals_gating.py`
- **Infra / docs:** `backend/docker-compose.yml` (`JWT_SECRET`, `STUB_MODE` for the `jbg-ai` service), `ai-service/README.md`
- **Dependencies:** add `PyJWT`; sync `uv.lock`. No DB driver, no LLM SDK, no embedding client
- **Consumers:** none today; C03 will issue the JWT and generate the typed .NET client against this snapshot. Browser and SPA are unaffected — they never call Python
- **Out of scope:** real retrieval / enrichment / indexing logic (C09, C13, C14+), JWT issuance and Polly client on .NET (C03), `POST /v1/retrieval/complementary` and `POST /v1/families/suggest` (later OpenAPI negotiation), schema `ai` / `vector` / Alembic (C05), SQL access to schema `public` (forbidden by design), production deploy, SSM and enriched health (C17)
- **Traceability:** HU-AIENG-002, ticket T-AIENG-002, plan change C02; design v3 §6.1–6.4, §7.6–7.7 and 3devs §6.8
