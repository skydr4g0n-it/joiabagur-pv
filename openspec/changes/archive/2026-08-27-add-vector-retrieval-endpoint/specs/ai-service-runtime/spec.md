## ADDED Requirements

### Requirement: Retrieval distance threshold does not block process boot
`JPV_RETRIEVAL_DISTANCE_THRESHOLD` MUST be optional when settings load. When omitted or supplied as a blank string it MUST default to 0.65. A configured value MUST be greater than 0 and MUST NOT exceed 2 (the cosine distance domain of pgvector `<=>`). Absence of this setting MUST NOT prevent the process from starting or from serving `GET /health`. The setting MUST stay distinct from `JWT_SECRET`, `JPV_EMBEDDING_*`, `JPV_RAG_LLM_*`, `JPV_INDEX_FEED_*` and `JPV_CATALOG_LLM_*`. `/health` MUST NOT perform a retrieval query. `canonical_openapi_settings` MUST pin the threshold to 0.65 so a process environment value does not leak into the committed OpenAPI snapshot.

#### Scenario: Health starts without a retrieval threshold
- **GIVEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** `JPV_RETRIEVAL_DISTANCE_THRESHOLD` is omitted
- **WHEN** settings load and a client calls `GET /health`
- **THEN** settings load successfully
- **AND** `JPV_RETRIEVAL_DISTANCE_THRESHOLD` is 0.65
- **AND** the response status is 200

#### Scenario: Blank retrieval threshold is treated as the default
- **GIVEN** `JPV_RETRIEVAL_DISTANCE_THRESHOLD` is present as an empty or whitespace string
- **WHEN** settings load
- **THEN** the threshold is 0.65
- **AND** the process can serve `GET /health`

#### Scenario: Canonical OpenAPI settings pin the retrieval threshold
- **WHEN** `canonical_openapi_settings` is built
- **THEN** the retrieval distance threshold is 0.65
- **AND** no process environment value leaks into the committed OpenAPI snapshot
