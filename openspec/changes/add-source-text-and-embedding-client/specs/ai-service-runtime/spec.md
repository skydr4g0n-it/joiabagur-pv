## ADDED Requirements

### Requirement: Embedding settings do not block process boot
`JPV_EMBEDDING_API_KEY`, `JPV_EMBEDDING_MODEL`, `JPV_EMBEDDING_BASE_URL` and `JPV_EMBEDDING_BATCH_SIZE` MUST be optional when settings load. Their absence or a blank string MUST NOT prevent the process from starting or from serving `GET /health`. `JPV_EMBEDDING_BATCH_SIZE` MUST default to 64 when omitted or blank. These settings MUST stay distinct from `JPV_RAG_LLM_*` and `JPV_CATALOG_LLM_*`. The real embedding adapter MUST require `JPV_EMBEDDING_API_KEY` at call time and MUST fail explicitly if it is missing; `/health` MUST NOT perform that check. `canonical_openapi_settings` MUST pin the embedding key, model and base URL to unset and the batch size to 64.

#### Scenario: Health starts without an embedding key
- **GIVEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** `JPV_EMBEDDING_API_KEY`, `JPV_EMBEDDING_MODEL`, `JPV_EMBEDDING_BASE_URL` and `JPV_EMBEDDING_BATCH_SIZE` are omitted
- **WHEN** settings load and a client calls `GET /health`
- **THEN** settings load successfully
- **AND** `JPV_EMBEDDING_BATCH_SIZE` is 64
- **AND** the response status is 200

#### Scenario: Blank embedding strings are treated as unset
- **GIVEN** `JPV_EMBEDDING_API_KEY` is present as an empty or whitespace string
- **WHEN** settings load
- **THEN** the key is treated as absent
- **AND** the process can serve `GET /health`

#### Scenario: Canonical OpenAPI settings pin embedding keys to absent
- **WHEN** `canonical_openapi_settings` is built
- **THEN** the embedding key, model and base URL are unset
- **AND** the embedding batch size is 64
- **AND** no process environment value leaks into the committed OpenAPI snapshot
