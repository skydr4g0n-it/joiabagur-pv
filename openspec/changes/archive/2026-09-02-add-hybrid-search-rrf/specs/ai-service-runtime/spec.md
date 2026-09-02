## ADDED Requirements

### Requirement: Fusion settings do not block process boot
The smoothing constant, the per-list weights and the branch depth used by the hybrid fusion MUST be optional when settings load. When omitted or supplied as blank strings they MUST fall back to their documented defaults, and their absence MUST NOT prevent the process from starting or from serving `GET /health`. `GET /health` MUST NOT run a retrieval or load the synonym dictionary in order to answer.

The default weight of the vector list MUST be lower than the default weight of either lexical list, and the two lexical weights MUST sum to the weight of a single lexical list. The default branch depth MUST be of the same order as the smoothing constant. Each setting MUST stay distinct from `JWT_SECRET`, `JPV_EMBEDDING_*`, `JPV_RAG_LLM_*`, `JPV_INDEX_FEED_*`, `JPV_CATALOG_LLM_*`, `JPV_RETRIEVAL_DISTANCE_THRESHOLD` and `JPV_QUERY_EXPANSION_ENABLED`.

These settings MUST supply only the defaults: the effective values MUST travel as parameters of the retrieval orchestration call, so that several configurations can be evaluated in one process without restarting it, and they MUST NOT be added to the retrieval request schema. `canonical_openapi_settings` MUST pin every one of them to its default so that a process environment value cannot leak into the committed OpenAPI snapshot.

#### Scenario: Health starts without the fusion settings
- **GIVEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** every fusion setting is omitted
- **WHEN** settings load and a client calls `GET /health`
- **THEN** settings load successfully
- **AND** each fusion setting holds its documented default
- **AND** the response status is 200
- **AND** no retrieval is run and no synonym dictionary is loaded to answer the health request

#### Scenario: Blank fusion settings are treated as the defaults
- **GIVEN** the fusion settings are present as empty or whitespace strings
- **WHEN** settings load
- **THEN** each holds its documented default
- **AND** the process can serve `GET /health`

#### Scenario: The measured default weighting is preserved
- **WHEN** settings load with no fusion setting supplied
- **THEN** the vector list weight is lower than the typed lexical list weight
- **AND** it is lower than the expanded lexical list weight
- **AND** the two lexical weights sum to the weight of a single lexical list

#### Scenario: Branch depth is coupled to the smoothing constant
- **WHEN** settings load with no fusion setting supplied
- **THEN** the branch depth is of the same order as the smoothing constant
- **AND** it is a single value shared by every fused list

#### Scenario: The settings can be overridden by environment
- **GIVEN** the fusion settings are set to values other than their defaults
- **WHEN** settings load
- **THEN** those values are used
- **AND** the retrieval endpoint keeps answering with the same response shape

#### Scenario: Canonical OpenAPI settings pin the fusion settings
- **WHEN** `canonical_openapi_settings` is built
- **THEN** every fusion setting holds its default
- **AND** no process environment value leaks into the committed OpenAPI snapshot
- **AND** `ai-service/openapi.json` is unchanged by this change
