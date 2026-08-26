## ADDED Requirements

### Requirement: Index feed settings do not block process boot
`JPV_INDEX_FEED_BASE_URL`, `JPV_INDEX_FEED_API_KEY` and `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` MUST be optional when settings load. Their absence or a blank string MUST NOT prevent the process from starting or from serving `GET /health`. `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` MUST default to 180 when omitted or blank. These settings MUST stay distinct from `JWT_SECRET`, `JPV_EMBEDDING_*`, `JPV_RAG_LLM_*` and `JPV_CATALOG_LLM_*`. The real catalog sync MUST require `JPV_INDEX_FEED_BASE_URL`, `JPV_INDEX_FEED_API_KEY` and `JPV_EMBEDDING_API_KEY` at call time and MUST fail with HTTP 503 naming the missing setting if any is absent; `/health` MUST NOT perform that check. The feed API key MUST NOT fall back to `JWT_SECRET`. `canonical_openapi_settings` MUST pin the feed base URL and API key to unset and the time budget to 180.

#### Scenario: Health starts without a feed key
- **GIVEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** `JPV_INDEX_FEED_BASE_URL`, `JPV_INDEX_FEED_API_KEY` and `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` are omitted
- **WHEN** settings load and a client calls `GET /health`
- **THEN** settings load successfully
- **AND** `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` is 180
- **AND** the response status is 200

#### Scenario: Blank feed strings are treated as unset
- **GIVEN** `JPV_INDEX_FEED_API_KEY` is present as an empty or whitespace string
- **WHEN** settings load
- **THEN** the key is treated as absent
- **AND** the process can serve `GET /health`

#### Scenario: Canonical OpenAPI settings pin feed keys to absent
- **WHEN** `canonical_openapi_settings` is built
- **THEN** the index feed base URL and API key are unset
- **AND** the sync time budget is 180
- **AND** no process environment value leaks into the committed OpenAPI snapshot

#### Scenario: Real sync does not use JWT_SECRET as the feed key
- **GIVEN** `STUB_MODE` is false
- **AND** `JPV_INDEX_FEED_API_KEY` is absent
- **AND** `JWT_SECRET` is present
- **WHEN** `POST /v1/index/sync` is called
- **THEN** the response status is 503
- **AND** the detail names `JPV_INDEX_FEED_API_KEY`
- **AND** `JWT_SECRET` is not sent as `X-Index-Feed-Key`
