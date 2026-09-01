## ADDED Requirements

### Requirement: Query expansion flag does not block process boot
`JPV_QUERY_EXPANSION_ENABLED` MUST be optional when settings load. When omitted or supplied as a blank string it MUST default to `true`. Absence of this setting MUST NOT prevent the process from starting or from serving `GET /health`, and `GET /health` MUST NOT load the synonym dictionary. The setting MUST stay distinct from `JWT_SECRET`, `JPV_EMBEDDING_*`, `JPV_RAG_LLM_*`, `JPV_INDEX_FEED_*`, `JPV_CATALOG_LLM_*` and `JPV_RETRIEVAL_DISTANCE_THRESHOLD`. It MUST supply only the default: the effective value MUST travel as a parameter of the retrieval orchestration call, so that several configurations can be evaluated in one process without restarting it, and it MUST NOT be added to the retrieval request schema. `canonical_openapi_settings` MUST pin the flag to its default so a process environment value does not leak into the committed OpenAPI snapshot.

#### Scenario: Health starts without the expansion flag
- **GIVEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** `JPV_QUERY_EXPANSION_ENABLED` is omitted
- **WHEN** settings load and a client calls `GET /health`
- **THEN** settings load successfully
- **AND** `JPV_QUERY_EXPANSION_ENABLED` is `true`
- **AND** the response status is 200
- **AND** no synonym dictionary is loaded to answer the health request

#### Scenario: Blank expansion flag is treated as the default
- **GIVEN** `JPV_QUERY_EXPANSION_ENABLED` is present as an empty or whitespace string
- **WHEN** settings load
- **THEN** the flag is `true`
- **AND** the process can serve `GET /health`

#### Scenario: The flag can be turned off by environment
- **GIVEN** `JPV_QUERY_EXPANSION_ENABLED` is set to a false value
- **WHEN** settings load
- **THEN** the flag is `false`
- **AND** the retrieval endpoint keeps answering with the same response shape

#### Scenario: Canonical OpenAPI settings pin the expansion flag
- **WHEN** `canonical_openapi_settings` is built
- **THEN** the query expansion flag is `true`
- **AND** no process environment value leaks into the committed OpenAPI snapshot
- **AND** `ai-service/openapi.json` is unchanged by this change
