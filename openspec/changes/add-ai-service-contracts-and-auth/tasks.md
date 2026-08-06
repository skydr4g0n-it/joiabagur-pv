## 1. Settings and dependencies

- [x] 1.1 Add `PyJWT` as a runtime dependency in `ai-service/pyproject.toml` and sync `uv.lock` with `uv`
- [x] 1.2 Extend `Settings` with `jwt_secret` (required, non-empty, fail-fast like `app_env` / `service_version`)
- [x] 1.3 Add `jwt_ttl_seconds` (default `300`) and `stub_mode` (default `true`) to `Settings`
- [x] 1.4 Add `enable_dev_endpoints` derived from `app_env`, resolving to false under a production profile and overridable by env
- [x] 1.5 Add `test_settings_fail_fast_when_jwt_secret_missing` covering both the absent and the blank secret

## 2. Internal service authentication

- [x] 2.1 Add `api/auth.py` with the HS256 decode routine (`PyJWT`), required claims `user_id`, `role`, `pos_id`, `trace_id`, and a `ServicePrincipal` model
- [x] 2.2 Add `api/deps.py` with the FastAPI dependency that reads `Authorization: Bearer`, validates the token and returns the `ServicePrincipal`
- [x] 2.3 Return HTTP 401 for missing, malformed, wrongly signed, wrong-algorithm, expired or incomplete tokens, with a body that reveals neither the secret nor the exact failing step
- [x] 2.4 Prefer the token `trace_id` claim over the `TraceIdMiddleware` value, keeping the C01 header-or-generated fallback for public and rejected requests
- [x] 2.5 Add `tests/test_auth.py` with `test_request_without_token_is_rejected` and `test_invalid_token_is_rejected` (bad signature, expired, missing claim)

## 3. Pydantic schemas

- [x] 3.1 Add `api/schemas/` package with a shared base (`trace_id`, optional `debug`, optional `usage`) reused across domains
- [x] 3.2 Define retrieval request (`query`, `top_k`, `filters` with `materials: list[str]`, `mode`, optional ignored `pos_id`) and result (`product_id`, `sku`, `score`, `match_reasons`, `materials`, `family_id`, `variant_label`, `debug?`)
- [x] 3.3 Define retrieval response (`results`, `candidates_returned`, `low_confidence`, `trace_id`) and the substitutes variant adding `similarity_signals`
- [x] 3.4 Define assist request and response (`intent`, `groups` with `family_id` and members exposing `variant_label`, `pitch`, `citations`, `warnings`, `clarification_question?`, `usage`)
- [x] 3.5 Define inventory propose request and prioritized proposal response
- [x] 3.6 Define enrich request (product batch) and response (proposed profiles with per-field confidence and `materials` as a list)
- [x] 3.7 Define index sync request (`since` cursor) with upsert counters, index status response (`drift_count`, `last_full_sync_at`) and the evals runs response
- [x] 3.8 Make `family_id` and `variant_label` nullable everywhere they appear, so unknown values serialize as null

## 4. Deterministic stubs

- [x] 4.1 Add `stubs/responses.py` with fixture builders per domain, pure and free of any external I/O
- [x] 4.2 Implement the retrieval stub with the over-retrieval rule `min(top_k * 3, 60)` reported in `candidates_returned`
- [x] 4.3 Implement the assist stub grouping members by `family_id` with `variant_label`, and a `pitch` carrying unresolved `{{price}}` and `{{stock}}` placeholders
- [x] 4.4 Implement the substitutes, inventory, enrich, index sync/status and evals stubs
- [x] 4.5 Guarantee determinism: same request produces the same response apart from correlation values

## 5. Routers and mounting

- [x] 5.1 Add `api/routers/retrieval.py` with `POST /v1/retrieval/products` and `POST /v1/retrieval/substitutes`
- [x] 5.2 Add `api/routers/assist.py` with `POST /v1/assist/sale`
- [x] 5.3 Add `api/routers/inventory.py` with `POST /v1/inventory/propose`
- [x] 5.4 Add `api/routers/enrich.py` with `POST /v1/enrich/products`
- [x] 5.5 Add `api/routers/index.py` with `POST /v1/index/sync` and `GET /v1/index/status`
- [x] 5.6 Add `api/routers/evals.py` with `GET /v1/evals/runs`
- [x] 5.7 Apply the authentication dependency to every `/v1` router and leave `GET /health` public and unchanged
- [x] 5.8 Read the effective `pos_id` and `role` only from the `ServicePrincipal`, ignoring any body value without raising an error
- [x] 5.9 Return HTTP 501 with a message naming the delivering change when `stub_mode` is disabled and no real implementation exists
- [x] 5.10 Mount all routers in `create_app()`, gating the evals router behind `enable_dev_endpoints`

## 6. Contract tests

- [x] 6.1 Extend `tests/conftest.py` with fixtures for required env, an app factory per profile, and a helper that signs valid and invalid tokens
- [x] 6.2 Add `test_retrieval_stub_matches_response_schema` asserting the contract fields and the absence of LLM, embedding and database calls
- [x] 6.3 Add `test_over_retrieval_returns_capped_candidates` covering `top_k = 5 → 15` and `top_k = 30 → 60`
- [x] 6.4 Add `test_assist_sale_groups_by_family` asserting `groups`, `variant_label` and the unresolved placeholders
- [x] 6.5 Add `test_pos_id_from_token_overrides_body_value`
- [x] 6.6 Add `test_health_is_public`
- [x] 6.7 Add `test_unimplemented_route_returns_501_when_stub_mode_off`
- [x] 6.8 Add `test_dev_only_evals_route_absent_in_prod_profile` plus its development-profile counterpart returning 200

## 7. OpenAPI snapshot

- [x] 7.1 Generate `ai-service/openapi.json` from `create_app(...).openapi()` using the canonical development profile and commit it
- [x] 7.2 Add `test_openapi_snapshot_is_stable` comparing the live schema against the committed file with strict equality
- [x] 7.3 Confirm `docs_url` and `redoc_url` stay `None` — the snapshot is the published artifact
- [x] 7.4 Verify the test fails when a model or route signature changes without regenerating, then restore

## 8. Environment and documentation

- [x] 8.1 Add `JWT_SECRET` (local development placeholder) and `STUB_MODE` to the `jbg-ai` service in `backend/docker-compose.yml`
- [x] 8.2 Update the required-environment table in `ai-service/README.md` with `JWT_SECRET`, `JWT_TTL_SECONDS`, `STUB_MODE` and `ENABLE_DEV_ENDPOINTS`
- [x] 8.3 Document the canonical development profile used to generate the snapshot and the manual regeneration one-liner, framing regeneration as a contract negotiation
- [x] 8.4 Document the frozen endpoint list, the snake_case claim names and the token-wins rule for the C03 consumer

## 9. Verification

- [x] 9.1 Run `uv run pytest` from `ai-service/` and confirm all tests green, including the eleven named in the ticket
- [x] 9.2 Confirm the suite makes no LLM, embedding or RDS calls and needs no database
- [x] 9.3 Smoke the stack with Compose when Docker is available: `GET /health` public, a `/v1` call rejected without a token and served with one
- [x] 9.4 Run `openspec validate add-ai-service-contracts-and-auth --strict` and confirm no `TODO` or `FIXME` is left without a follow-up task
