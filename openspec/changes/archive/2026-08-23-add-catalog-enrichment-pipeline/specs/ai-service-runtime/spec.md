## ADDED Requirements

### Requirement: RAG LLM settings do not block process boot
`JPV_RAG_LLM_API_KEY`, `JPV_RAG_LLM_MODEL`, `JPV_RAG_LLM_BASE_URL` and `JPV_RAG_LLM_CONCURRENCY` MUST be optional when settings load. Their absence or a blank string MUST NOT prevent the process from starting or from serving `GET /health`. `JPV_RAG_LLM_CONCURRENCY` MUST default to 8 when omitted. These settings MUST stay distinct from `JPV_CATALOG_LLM_*`. The real enrichment pipeline MUST require `JPV_RAG_LLM_API_KEY` at call time and MUST fail explicitly if it is missing; `/health` MUST NOT perform that check.

#### Scenario: Health starts without a RAG LLM key
- **GIVEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** `JPV_RAG_LLM_API_KEY`, `JPV_RAG_LLM_MODEL`, `JPV_RAG_LLM_BASE_URL` and `JPV_RAG_LLM_CONCURRENCY` are omitted
- **WHEN** settings load and a client calls `GET /health`
- **THEN** settings load successfully
- **AND** `JPV_RAG_LLM_CONCURRENCY` is 8
- **AND** the response status is 200

#### Scenario: Blank RAG LLM strings are treated as unset
- **GIVEN** `JPV_RAG_LLM_API_KEY` is present as an empty or whitespace string
- **WHEN** settings load
- **THEN** the key is treated as absent
- **AND** the process can serve `GET /health`

#### Scenario: Canonical OpenAPI settings pin RAG keys to absent
- **WHEN** `canonical_openapi_settings` is built
- **THEN** the RAG LLM key, model and base URL are unset
- **AND** no process environment value leaks into the committed OpenAPI snapshot
