# product-document-indexer Specification

## Purpose
Catalog indexer behind `POST /v1/index/sync` and `GET /v1/index/status` when `STUB_MODE` is off: HTTP pull of the catalog feed (keyset, time budget, no POS), committed SKU provenance map, upsert with skip-embed, tombstones, per-item `sync_failure`, set-hash drift, and a CLI on the same drain. No visible `product_document` row without a 1536-d embedding. Python does not read schema `public`.

## Requirements

### Requirement: Catalog sync drains the feed with a keyset and a time budget
When `STUB_MODE` is false, `POST /v1/index/sync` MUST pull `GET /api/ai/index-feed/catalog` until `nextCursor` is null or the configured time budget is exhausted. The feed page size MUST be the server-fixed 50 of the catalog feed; the request field `batch_size` MUST be ignored. Precedence of the starting cursor MUST be: `full=true` ignores body and checkpoint and starts without query params; a complete body keyset `(since, since_id)` overrides the checkpoint for that run; otherwise the stored checkpoint is used; an absent checkpoint MUST behave as a full drain. When the time budget (`JPV_INDEX_SYNC_TIME_BUDGET_SECONDS`, default 180) elapses, the service MUST persist the checkpoint of the last item processed successfully, return HTTP 200 with partial counters and the keyset cursor, and MUST NOT return 500. The same drain function MUST back `python -m jbg_ai.indexing sync [--full]`.

#### Scenario: A full sync pages until the feed is exhausted
- **GIVEN** `STUB_MODE` is false and the catalog feed emits upserts whose SKUs are in the provenance map
- **AND** embeddings and feed settings are present
- **WHEN** `POST /v1/index/sync` is called with `full` true (HTTP or CLI) and a catalog token
- **THEN** the client requests catalog pages until `nextCursor` is null
- **AND** each upsert produces a row in `ai.product_document` with `doc_text`, `source_hash`, a 1536-d embedding, `data_origin`, `text_provenance` and a non-null `tsv`
- **AND** the response reports `upserted`, `skipped`, `deleted` and `failed` plus a keyset `(cursor, cursor_id)`
- **AND** `GET /v1/index/status` reports `indexed_documents` equal to the written set and a non-null `last_full_sync_at`

#### Scenario: Time budget persists a resume cursor instead of failing
- **GIVEN** a full drain whose remaining work would exceed the configured time budget
- **WHEN** the budget elapses after at least one item has been processed successfully
- **THEN** the response status is 200
- **AND** the checkpoint stores the keyset of that last successful item
- **AND** the response `cursor` / `cursor_id` match that checkpoint
- **AND** a subsequent incremental sync continues from that keyset

#### Scenario: batch_size does not change the feed page
- **GIVEN** a real catalog sync
- **WHEN** the request body sets `batch_size` to a value other than 50
- **THEN** each feed request still receives a page of at most 50 items
- **AND** a warning is emitted that `batch_size` is ignored

#### Scenario: full ignores body and checkpoint
- **GIVEN** a stored checkpoint
- **AND** a request body that carries both `since` and `since_id`
- **WHEN** `POST /v1/index/sync` is called with `full` true
- **THEN** the first catalog GET omits both query parameters

#### Scenario: Body keyset overrides the checkpoint
- **GIVEN** a stored checkpoint
- **AND** a request body that carries both `since` and `since_id`
- **WHEN** `POST /v1/index/sync` is called with `full` false
- **THEN** that body keyset is sent as the feed cursor
- **AND** the stored checkpoint is not used as the start cursor

#### Scenario: Incremental without body uses the checkpoint
- **GIVEN** a stored checkpoint
- **AND** a request body that omits `since` and `since_id`
- **WHEN** `POST /v1/index/sync` is called with `full` false
- **THEN** the stored checkpoint is sent as `since` / `sinceId`

### Requirement: Same source hash skips embed and still updates columns
Idempotence of catalog upsert MUST mean the embedding provider is not called when the stored `source_hash` equals the new hash and a 1536-d embedding is already present. The row MUST still be updated for `price`, `price_band`, `family_id`, `family_name`, `variant_label`, tag arrays, `is_active`, `data_origin`, `text_provenance`, `indexed_at`, `doc_text` and `source_hash`. The counter `skipped` MUST increment for that item. A change that alters canonical `doc_text` (including a `family_name` rename) MUST change the hash and MUST call embed.

#### Scenario: Unchanged text is not re-embedded and price is updated
- **GIVEN** an indexed product whose stored `source_hash` is H and whose embedding is present
- **AND** the feed re-emits it with the same canonical text and a different `price` / `priceBand`
- **WHEN** an incremental sync processes that upsert
- **THEN** the embedding provider is not called for that `doc_text`
- **AND** the row's `price` and `price_band` match the feed
- **AND** `skipped` increases by one

#### Scenario: A family name rename re-embeds
- **GIVEN** an indexed product
- **AND** the feed re-emits it with a renamed `familyName` and otherwise the same profile
- **WHEN** the sync processes that upsert
- **THEN** `source_hash` changes
- **AND** the embedding provider is called
- **AND** `upserted` increases by one

### Requirement: Tombstones delete the document and are idempotent
A catalog feed item with `kind = tombstone` MUST delete the `ai.product_document` row keyed by `product_id`. `deleted` MUST equal the number of rows actually removed. A tombstone for a missing row (never indexed, or already deleted) MUST be a no-op: it MUST NOT increment `deleted` and MUST NOT fail the item.

#### Scenario: A tombstone removes an indexed document
- **GIVEN** an indexed `product_id`
- **WHEN** the sync processes a catalog tombstone for that id (`deactivated` or `unapproved`)
- **THEN** the row is absent from `ai.product_document`
- **AND** `deleted` increases by one

#### Scenario: A repeated tombstone is a no-op
- **GIVEN** a `product_id` that is not in `ai.product_document`
- **WHEN** the sync processes a tombstone for that id
- **THEN** `deleted` does not increase
- **AND** the item is not recorded as a `sync_failure`

### Requirement: Status reports set drift with a single catalog GET
`GET /v1/index/status` in real mode MUST compute the SHA-256 of the `product_id` values in `ai.product_document` using the same algorithm as `IndexFeedAggregateHash.OfProductIds` (canonical UUID `D` format, sorted, UTF-8 concatenation, 64 lowercase hex characters). It MUST compare that digest to `aggregateHash` from **one** GET of the first catalog feed page. Equal hashes MUST yield `drift_count = 0`. Distinct hashes MUST yield `drift_count = max(1, abs(indexed_documents − checkpoint.indexed_count))`. The handler MUST NOT walk subsequent feed pages. If the feed GET fails, the status call MUST fail explicitly (HTTP 503 or an equivalent documented error) and MUST NOT report `drift_count = 0`.

#### Scenario: Matching set hashes report zero drift
- **GIVEN** the SHA-256 of indexed `product_id` values equals the feed `aggregateHash`
- **WHEN** `GET /v1/index/status` runs in real mode
- **THEN** `drift_count` is 0
- **AND** the feed client is invoked exactly once

#### Scenario: Divergent set hashes report a positive drift
- **GIVEN** the two hashes differ
- **WHEN** `GET /v1/index/status` runs in real mode
- **THEN** `drift_count` is `max(1, abs(indexed_documents − checkpoint.indexed_count))`
- **AND** the feed client is invoked exactly once
- **AND** the remaining catalog pages are not requested

### Requirement: A failed item is recorded and does not block others
Synchronization MUST isolate failures per item. An upsert whose SKU is absent from the provenance map, or whose embed call fails, or whose vector dimension is not 1536, MUST write `ai.sync_failure` with `feed`, `product_id`, payload, error and the keyset cursor (`cursor_since`, `cursor_since_id`), increment `failed`, and continue with the remaining items of the page. The failed item MUST NOT leave a visible `product_document` row without a 1536-d embedding. A previous good row MUST NOT be overwritten with a null embedding.

#### Scenario: An orphan SKU fails and siblings succeed
- **GIVEN** a catalog page that contains one SKU missing from the provenance map and other SKUs that are present
- **WHEN** the sync processes that page
- **THEN** the orphan is recorded in `ai.sync_failure` with its `product_id`
- **AND** `failed` increases by one
- **AND** the other items of the page are upserted
- **AND** no `product_document` row exists for the orphan

#### Scenario: An embed failure keeps the previous row
- **GIVEN** an indexed product
- **AND** a re-embed is required and the embedding client raises
- **WHEN** the sync processes that upsert
- **THEN** a `sync_failure` row is written
- **AND** the previous `product_document` row still has its embedding
- **AND** later items of the page are processed

### Requirement: Missing map or feed settings refuse the real sync without writing
When `STUB_MODE` is false, a missing or unreadable `sku_provenance.json`, or a missing `JPV_INDEX_FEED_API_KEY`, `JPV_INDEX_FEED_BASE_URL` or `JPV_EMBEDDING_API_KEY`, MUST cause `POST /v1/index/sync` to respond HTTP 503 with a detail that names the missing setting or artefact. The handler MUST NOT write any `product_document` row. `GET /health` MUST remain HTTP 200. When `STUB_MODE` is true the C02 fixtures MUST still answer HTTP 200. The feed API key MUST NOT be substituted with `JWT_SECRET` or `JPV_EMBEDDING_API_KEY`.

#### Scenario: Absent feed key is a named 503
- **GIVEN** `STUB_MODE` is false and `JPV_INDEX_FEED_API_KEY` is unset
- **WHEN** `POST /v1/index/sync` is called
- **THEN** the response status is 503
- **AND** the detail names `JPV_INDEX_FEED_API_KEY`
- **AND** `ai.product_document` gains no rows
- **AND** `GET /health` is 200

#### Scenario: Absent provenance map writes nothing
- **GIVEN** `STUB_MODE` is false and `sku_provenance.json` is missing or unreadable
- **WHEN** `POST /v1/index/sync` is called
- **THEN** the response status is 503
- **AND** no `product_document` row is inserted

#### Scenario: Stub mode still returns fixtures
- **GIVEN** `STUB_MODE` is true
- **WHEN** `POST /v1/index/sync` and `GET /v1/index/status` are called with a catalog token
- **THEN** both responses are HTTP 200 from fixtures
- **AND** no feed, embedding or database call is made

### Requirement: Provenance map is committed in src and matches the JSONL corpus
The service MUST load SKU provenance from `jbg_ai/indexing/sku_provenance.json` shipped under `src/`. Each entry MUST map a SKU to `data_origin` (`real` | `synthetic`) and `text_provenance` (`merchant` | `ai_assisted` | `synthetic`). The map MUST NOT be read from `data/catalog/` at runtime. Tests that run in the repository MUST assert the map equals the union of the real and synthetic JSONL files: 1.200 keys, 436 `real` / 764 `synthetic`, 387 `ai_assisted` / 49 `merchant` / 764 `synthetic`, no overlapping SKUs, every JSONL SKU present. The indexer MUST NOT default a missing SKU to `synthetic` or infer origin from a SKU numeric range. `text_quality_tier` MUST NOT be persisted on `ai.product_document`.

#### Scenario: Map cardinality matches the corpus
- **GIVEN** the committed `sku_provenance.json` and both generated JSONL files
- **WHEN** the invariant test runs in the repository
- **THEN** the map has 1.200 keys
- **AND** it contains 436 `real` and 764 `synthetic` origins
- **AND** it contains 387 `ai_assisted`, 49 `merchant` and 764 `synthetic` provenances
- **AND** every JSONL SKU is present and no SKU appears twice

#### Scenario: Origin is not guessed from SKU shape
- **GIVEN** a feed upsert whose SKU is absent from the map
- **WHEN** the sync processes it
- **THEN** the item is recorded as a failure
- **AND** `data_origin` is not defaulted to `synthetic`
- **AND** no heuristic over `SKU01`–`SKU436` is applied

### Requirement: Index routes accept a catalog token and send the feed API key outbound
`POST /v1/index/sync` and `GET /v1/index/status` MUST authenticate with `get_catalog_principal`: `user_id`, `role` and `trace_id` required, `pos_id` not required. The token MUST be the internal HS256 JWT (`JWT_SECRET`), not the feed API key. Calls from Python to the .NET catalog feed MUST send `X-Index-Feed-Key` with `JPV_INDEX_FEED_API_KEY`. A token missing `user_id`, `role` or `trace_id` MUST still be HTTP 401.

#### Scenario: Catalog token without pos_id is accepted on index routes
- **GIVEN** a correctly signed token with `user_id`, `role` and `trace_id` and no `pos_id`
- **WHEN** `POST /v1/index/sync` or `GET /v1/index/status` is called in stub mode
- **THEN** the response is not 401
- **AND** the handler runs

#### Scenario: Feed requests carry the service API key
- **GIVEN** a real sync with `JPV_INDEX_FEED_API_KEY` set
- **WHEN** the feed client requests a catalog page
- **THEN** the request includes header `X-Index-Feed-Key` equal to that setting
- **AND** the value is not written to Information logs

### Requirement: The feed client is reusable and the catalog indexer does not drain POS
The indexing package MUST expose an injectable async catalog feed client that parses `kind` `upsert` | `tombstone`, maps camelCase upsert fields onto `ProductSourceText` plus `product_id`, `family_id`, `price`, `price_band`, `is_active` and `watermark`, and accepts a POS path/method. This change MUST NOT invoke the POS availability feed and MUST NOT write `ai.pos_projection`. `indexing/embeddings.py` MUST NOT be modified. The indexer MUST NOT open an EF Core migration, MUST NOT add a .NET client operation toward `/v1/index/sync`, and MUST NOT start a 5–10 minute scheduler. Python MUST NOT read or write schema `public` by SQL.

#### Scenario: POS feed is not called during catalog sync
- **GIVEN** a real catalog sync and an injected feed client that records calls
- **WHEN** the sync completes
- **THEN** only catalog pages were requested
- **AND** the POS method was not invoked
- **AND** `ai.pos_projection` is untouched

#### Scenario: embeddings.py stays frozen
- **WHEN** the change is implemented
- **THEN** `ai-service/src/jbg_ai/indexing/embeddings.py` has no diff against the C11 freeze
- **AND** `jbg_ai.api.main` source does not mention `jbg_ai.indexing`

### Requirement: No visible product document is stored without a 1536-d embedding
The catalog writer MUST embed `doc_text` and assert dimension 1536 before inserting or replacing a `product_document` row that did not already have a vector. `embedding_model` and `embedding_version` MUST equal C11 `document_version_key` (`{model}:1536:source-text/v1`). `doc_text` MUST be written on every successful upsert so the generated `tsv` is non-null. The schema MAY still allow a null embedding column; this writer MUST NOT use that window for a row that retrieval could see.

#### Scenario: Upsert leaves tsv and embedding present
- **GIVEN** a catalog upsert whose SKU is in the map and whose embed fake returns 1536 dimensions
- **WHEN** the sync persists the row
- **THEN** `embedding` is not null
- **AND** `tsv` is not null
- **AND** `embedding_version` equals the client's `document_version_key`

#### Scenario: A non-1536 vector is not persisted
- **GIVEN** an embed fake that returns 384 or 3072 dimensions
- **WHEN** the sync processes a new upsert
- **THEN** no `product_document` row is written for that product
- **AND** a `sync_failure` row is recorded

### Requirement: Indexer tests inject fakes and make no provider or .NET sockets
Tests under `ai-service/tests/indexing/` and the new API tests for `/v1/index/*` MUST inject fakes for the feed client, the embedding client and the repository. They MUST NOT open sockets to embedding providers, LLM providers, `:5056` or production RDS. Schema tests MAY use the existing pgvector Testcontainers database and MUST skip (not fail) when Docker is unreachable. A pytest in this change MUST NOT require 1.200 real rows against Docker or a live provider.

#### Scenario: Indexer unit suite stays offline
- **WHEN** the indexing and index-route tests run
- **THEN** they use injected fakes for feed and embed
- **AND** no socket is opened to an embedding provider, LLM provider or the .NET API

#### Scenario: Suite does not demand a live 1200-row index
- **WHEN** the pytest suite of this change runs
- **THEN** no test fails solely because `ai.product_document` does not contain 1.200 rows
