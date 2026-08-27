# vector-retrieval Specification

## Purpose
Vector retriever behind `POST /v1/retrieval/products` when `STUB_MODE` is off: embed query with C11 client (`max_attempts=1`), pgvector cosine `<=>` with SQL distance threshold, overfetch after the threshold, body filters, score 0–1, 200 abstention vs 503 dependency failure, hybrid/lexical modes run as vector until C21, stage logs. Stub C02 remains when `STUB_MODE` is true. Python does not read schema `public`. OpenAPI snapshot is not regenerated.

## Requirements

### Requirement: Real product retrieval replaces the stub when stub mode is off
When `STUB_MODE` is disabled, `POST /v1/retrieval/products` MUST run the vector retrieval pipeline and MUST return a body that validates against the frozen `RetrievalResponse` model. It MUST NOT return HTTP 501 naming a later change and MUST NOT return the C02 fixture cycle. When `STUB_MODE` is enabled, the existing C02 stub MUST remain the handler so committed contract tests stay green. `POST /v1/retrieval/substitutes` MUST keep returning 501 when stubs are off. The OpenAPI snapshot MUST NOT be regenerated. The products handler MUST be asynchronous.

#### Scenario: Stub mode keeps the C02 fixtures
- **GIVEN** `STUB_MODE` is enabled
- **WHEN** an authenticated client with `pos_id` calls `POST /v1/retrieval/products` with a valid body
- **THEN** the response is produced by the existing retrieval stub
- **AND** no embedding provider is called
- **AND** no database session is opened

#### Scenario: Real mode is not 501
- **GIVEN** `STUB_MODE` is disabled and retrieval dependencies are available
- **WHEN** an authenticated client with `pos_id` calls `POST /v1/retrieval/products` with a valid body
- **THEN** the response status is 200 or 503 according to index and dependency state
- **AND** the status is not 501 claiming the implementation has not arrived
- **AND** a 200 body validates against `RetrievalResponse`

#### Scenario: Substitutes stay unimplemented
- **GIVEN** `STUB_MODE` is disabled
- **WHEN** an authenticated client with `pos_id` calls `POST /v1/retrieval/substitutes`
- **THEN** the response status is 501
- **AND** the message indicates the implementation is delivered in a later change

#### Scenario: OpenAPI snapshot stays frozen
- **WHEN** `test_openapi_snapshot_is_stable` runs against this change
- **THEN** the live schema equals the committed `ai-service/openapi.json`
- **AND** the snapshot file has not been regenerated

### Requirement: Query embedding uses the C11 client with a single attempt
The real products handler MUST embed the request `query` with `LiteLlmEmbeddingClient` from `indexing/embeddings.py`, constructed with `max_attempts=1`. It MUST NOT edit `indexing/embeddings.py`. It MUST prefer an instance injected on `app.state` (distinct from the indexer client that retries three times). A missing `JPV_EMBEDDING_API_KEY` with no injected fake MUST produce HTTP 503 naming `JPV_EMBEDDING_API_KEY`. A provider failure or a vector whose dimension is not 1536 MUST produce HTTP 503, not HTTP 200 with an empty result list. `/health` MUST NOT require the embedding key.

#### Scenario: Retrieval embed client does not retry
- **GIVEN** `STUB_MODE` is disabled
- **WHEN** the retrieval embedding client is constructed
- **THEN** `max_attempts` is 1
- **AND** `indexing/embeddings.py` is unchanged relative to the C11 freeze

#### Scenario: Missing embedding key is 503
- **GIVEN** `STUB_MODE` is disabled
- **AND** `JPV_EMBEDDING_API_KEY` is absent
- **AND** no retrieval embed fake is injected
- **WHEN** an authenticated client calls `POST /v1/retrieval/products`
- **THEN** the response status is 503
- **AND** the detail names `JPV_EMBEDDING_API_KEY`
- **AND** `GET /health` remains HTTP 200

#### Scenario: Provider failure is not an empty success
- **GIVEN** `STUB_MODE` is disabled and the embedding port raises a non-recoverable error
- **WHEN** an authenticated client calls `POST /v1/retrieval/products`
- **THEN** the response status is 503
- **AND** the body is not a `RetrievalResponse` with `low_confidence`

### Requirement: Search uses cosine distance with a SQL threshold and model compatibility
The search MUST use the pgvector cosine operator `<=>` aligned with the HNSW `vector_cosine_ops` index. It MUST NOT use L2. Rows MUST be excluded unless `embedding IS NOT NULL`, `is_active IS TRUE`, and the stored embedding is compatible with the live client's `model_version_key` (`{model}:1536`): `embedding_version` starts with that key or `embedding_model` equals the live `model_id`. Compatible rows whose cosine distance is greater than `JPV_RETRIEVAL_DISTANCE_THRESHOLD` MUST be excluded in SQL. The default threshold MUST be 0.65. The threshold MUST NOT be relaxed when few rows remain. Python MUST NOT read schema `public`.

#### Scenario: Results are ordered by ascending distance
- **GIVEN** `STUB_MODE` is disabled and at least two compatible rows pass the threshold
- **WHEN** an authenticated client calls `POST /v1/retrieval/products`
- **THEN** `results` are ordered by non-increasing `score`
- **AND** each `score` equals `clamp(1 − cosine_distance, 0, 1)`
- **AND** each `score` is inside `[0, 1]`
- **AND** each item's `match_reasons` contains `"vector"`

#### Scenario: Distance above the threshold is excluded
- **GIVEN** `STUB_MODE` is disabled and the index has compatible embeddings
- **AND** every cosine distance to the query embedding is greater than the configured threshold
- **WHEN** an authenticated client calls `POST /v1/retrieval/products`
- **THEN** the response status is 200
- **AND** `results` is empty
- **AND** `candidates_returned` is 0
- **AND** `low_confidence` is true
- **AND** the threshold is not raised for a second attempt

#### Scenario: Incompatible embeddings do not count as abstention
- **GIVEN** `STUB_MODE` is disabled
- **AND** the count of rows compatible with the live `model_version_key` is 0
- **WHEN** an authenticated client calls `POST /v1/retrieval/products`
- **THEN** the response status is 503
- **AND** the status is not 200 with `low_confidence`

### Requirement: Over-retrieval applies after the distance filter
`top_k` MUST remain the page size the .NET caller wants after hydrating. The real retriever MUST return at most `min(top_k × 3, 60)` hits, using the same `over_retrieval_count` helper as the stub, applied as a `LIMIT` on the set already filtered by the distance threshold. `candidates_returned` MUST equal the length of `results`. `effective_pos_id` MUST be the token claim, not the body `pos_id`. `low_confidence` MUST be false when at least one result is returned.

#### Scenario: Overfetch is capped after the threshold
- **GIVEN** `STUB_MODE` is disabled and more than 15 compatible rows pass the threshold
- **WHEN** an authenticated client calls `POST /v1/retrieval/products` with `top_k = 5`
- **THEN** `results` has length 15
- **AND** `candidates_returned` is 15

#### Scenario: Overfetch does not refill from rows above the threshold
- **GIVEN** `STUB_MODE` is disabled and only 2 compatible rows pass the threshold while many more exist above it
- **WHEN** an authenticated client calls `POST /v1/retrieval/products` with `top_k = 5`
- **THEN** `results` has length 2
- **AND** `candidates_returned` is 2
- **AND** no row with distance greater than the threshold is present

#### Scenario: Token pos_id is echoed and body pos_id is ignored
- **GIVEN** `STUB_MODE` is disabled and at least one hit is returned
- **WHEN** an authenticated client calls with token `pos_id = B` and body `pos_id = A`
- **THEN** `effective_pos_id` is B
- **AND** the search SQL does not filter by `pos_id`

### Requirement: Body filters restrict the candidate set
When the request carries retrieval filters, the search MUST apply them in SQL. Non-empty `filters.materials` MUST require array overlap (`&&`) with `product_document.materials`. A non-null `filters.category` MUST equal `piece_type`. A non-null `filters.family_id` that parses as a UUID MUST equal `product_document.family_id`. A `family_id` that does not parse as a UUID MUST produce HTTP 422 without changing the frozen request schema. Malformed entries in `filters.exclude_product_ids` MUST be ignored (logged at Debug) and MUST NOT fail the request; well-formed UUIDs MUST be excluded from `results`. The search MUST NOT filter by price or stock.

#### Scenario: The four body predicates are applied
- **GIVEN** `STUB_MODE` is disabled and the index contains rows that both match and miss each filter
- **WHEN** an authenticated client calls with `filters.materials`, `filters.category`, a valid `filters.family_id` and `filters.exclude_product_ids`
- **THEN** every returned row overlaps the requested materials
- **AND** every returned row has `piece_type` equal to `category`
- **AND** every returned row has `family_id` equal to the requested family
- **AND** no excluded `product_id` appears in `results`

#### Scenario: Invalid family_id is 422
- **GIVEN** `STUB_MODE` is disabled
- **WHEN** an authenticated client sends `filters.family_id` that is not a UUID
- **THEN** the response status is 422
- **AND** `ai-service/openapi.json` is unchanged

#### Scenario: Malformed exclusions are ignored
- **GIVEN** `STUB_MODE` is disabled
- **WHEN** an authenticated client sends `filters.exclude_product_ids` containing one well-formed UUID and one malformed string
- **THEN** the well-formed id is absent from `results`
- **AND** the request is not rejected because of the malformed string

### Requirement: Hybrid and lexical modes run the vector branch until C21
Until hybrid search exists, `mode` absent, `hybrid` or `lexical` MUST execute the same vector pipeline as `mode=vector`. The response MUST NOT be HTTP 501 because of `mode`. When `debug` is present and `mode` is `hybrid` or `lexical`, `debug.notes` MUST include `vector_only_until_c21`. `match_reasons` MUST NOT include `"lexical"` solely because the request asked for that mode.

#### Scenario: Default hybrid is not 501
- **GIVEN** `STUB_MODE` is disabled and retrieval dependencies are available
- **WHEN** an authenticated client omits `mode` or sends `hybrid` or `lexical`
- **THEN** the vector pipeline runs
- **AND** the response is not 501
- **AND** `debug.notes` includes `vector_only_until_c21` when `debug` is present

#### Scenario: Explicit vector mode needs no until-C21 note
- **GIVEN** `STUB_MODE` is disabled and at least one hit is returned
- **WHEN** an authenticated client sends `mode=vector`
- **THEN** the vector pipeline runs
- **AND** `debug.notes` does not include `vector_only_until_c21`

### Requirement: Missing database configuration is 503 not abstention
When `STUB_MODE` is disabled, a missing `DATABASE_URL`, a missing `ai` schema, a missing `vector` extension, or a failure to open a session MUST cause `POST /v1/retrieval/products` to respond HTTP 503 with a detail that names the failure. `GET /health` MUST remain HTTP 200. The handler MUST NOT insert into `ai.query_log`.

#### Scenario: Absent DATABASE_URL is 503
- **GIVEN** `STUB_MODE` is disabled and `DATABASE_URL` is unset
- **AND** no search fake is injected
- **WHEN** an authenticated client calls `POST /v1/retrieval/products`
- **THEN** the response status is 503
- **AND** the detail names `DATABASE_URL`
- **AND** `GET /health` remains HTTP 200
- **AND** the body is not a successful empty retrieval with `low_confidence`

### Requirement: Stage logs carry trace_id and do not dump vectors
The real pipeline MUST emit structured logs for at least `stage=embed` and `stage=search`. Both MUST include the request `trace_id` (token claim when present). Embed logs MUST include `latency_ms`, `model` and `cache_hits`. Search logs MUST include `latency_ms`, `distance_min` (null when there are zero hits), `candidates`, `low_confidence`, `mode` and `threshold`. The operator query MUST be logged only at Debug. Embedding vectors MUST NOT be logged at Information. `JPV_EMBEDDING_API_KEY` MUST NOT be logged.

#### Scenario: trace_id appears in stage logs
- **GIVEN** `STUB_MODE` is disabled and a token carries `trace_id`
- **WHEN** an authenticated client calls `POST /v1/retrieval/products`
- **THEN** structured logs for `stage=embed` include that `trace_id`
- **AND** structured logs for `stage=search` include that `trace_id`

### Requirement: Retrieval unit tests make no provider or database calls
Tests under `ai-service/tests/retrieval/` MUST inject a fake embedding client and a fake search port (in-memory rows with distance). They MUST NOT open sockets to embedding providers, LLM providers or RDS. Optional pgvector tests MAY exist and MUST be skipped, not failed, when Docker is unreachable. A pytest MUST NOT require 1.200 indexed rows.

#### Scenario: Unit suite stays offline
- **WHEN** the retrieval unit tests run
- **THEN** they use injected fakes rather than LiteLLM or PostgreSQL
- **AND** no socket is opened to an embedding provider, LLM provider or RDS
