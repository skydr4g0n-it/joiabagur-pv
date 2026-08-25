# catalog-source-text Specification

## Purpose
Canonical `source-text/v1` renderer and SHA-256 `source_hash` for catalog `doc_text`, plus an injectable LiteLLM embedding client (1536-d, in-process cache, batch, backoff) in `jbg_ai.indexing`. The HTTP app does not import the library; C13/C14/C23 reuse it without reimplementing.

## Requirements

### Requirement: Canonical source text is byte-stable for the same profile
The indexing library MUST render a catalog product into a canonical `doc_text` using the fixed template `source-text/v1`. The same input record MUST produce the same `doc_text` byte for byte on every call. Line separators MUST be `\n` with no `\r`. The text MUST be UTF-8. The template version MUST be a code constant, not a prompt file. Changing labels or field order MUST require a new template version.

#### Scenario: The same profile produces the same doc_text
- **GIVEN** a product record with the same canonical fields
- **WHEN** `build_source_text` is called twice
- **THEN** the two `doc_text` strings are identical byte for byte
- **AND** both use the `source-text/v1` layout

### Requirement: Source hash is SHA-256 of the rendered document
`hash_source_text` MUST return the SHA-256 digest of the exact UTF-8 `doc_text`, encoded as 64 lowercase hexadecimal characters. It MUST NOT hash a parallel field tuple. The digest MUST equal hashing the rendered `doc_text` independently.

#### Scenario: Hash matches the rendered UTF-8 document
- **GIVEN** a `doc_text` produced by `build_source_text`
- **WHEN** `hash_source_text` runs on that `doc_text`
- **THEN** the digest is 64 lowercase hexadecimal characters
- **AND** it equals `sha256(doc_text.encode("utf-8")).hexdigest()`

### Requirement: Material and tag order does not change the hash
`materials`, `color_tags`, `style_tags` and `occasion_tags` MUST be sorted alphabetically before they are joined. Two records that differ only in list order MUST emit the same line and the same `source_hash`. Empty lists MUST omit the line entirely.

#### Scenario: Reordered materials share a hash
- **GIVEN** one record with `materials = ["oro", "plata"]`
- **AND** another with `materials = ["plata", "oro"]` and the remaining fields equal
- **WHEN** both are rendered
- **THEN** both emit `Materiales: oro, plata`
- **AND** the `source_hash` values are equal

#### Scenario: Reordered commercial tags share a hash
- **GIVEN** two records that differ only in the order of `color_tags`, `style_tags` or `occasion_tags`
- **WHEN** both are rendered
- **THEN** the corresponding lines are alphabetically ordered
- **AND** the `source_hash` values are equal

### Requirement: A family name change changes the hash and the family UUID is absent
When `family_name` goes from absent to present, or is renamed, the reconstructed `doc_text` MUST change and the `source_hash` MUST change. The family identifier UUID MUST NOT appear in the text. The constructor MUST succeed when `family_name` is absent.

#### Scenario: Introducing a family name changes the hash
- **GIVEN** a product with no `family_name`
- **AND** the same product later with `family_name = "Anillo erizo de mar"`
- **WHEN** both `doc_text` values are hashed
- **THEN** the two digests differ
- **AND** the second text contains a `Familia:` line with the family name

#### Scenario: Family UUID is not written
- **GIVEN** a record that has both a family name and a family identifier UUID
- **WHEN** `build_source_text` runs
- **THEN** the `doc_text` does not contain the family identifier UUID

### Requirement: Absent fields are omitted not serialized as sentinels
Optional scalar fields that are null or empty, and list fields that are empty, MUST omit their labelled line. The renderer MUST NOT write sentinels such as `ninguna` or `n/a`.

#### Scenario: Empty optional fields leave no labelled line
- **GIVEN** `stone_type`, `size_label`, `family_name` and the three tag lists are empty or null
- **WHEN** `build_source_text` runs
- **THEN** the `doc_text` has no `Piedra:`, `Talla:`, `Familia:`, `Colores:`, `Estilo:` or `Ocasiones:` line
- **AND** the text does not contain `ninguna` or `n/a`

### Requirement: Price identifiers and provenance stay out of the source text
The source-text DTO MUST require `sku` and `name`. SKU MUST appear as a `SKU:` line. Commercial tags MUST appear when non-empty. The rendered text MUST NOT contain a numeric price, a `price_band`, a product identifier, `data_origin`, `text_provenance`, a confidence value, or a field `source`.

#### Scenario: SKU and tags enter and price does not
- **GIVEN** a record with a SKU, style tags and a numeric price
- **WHEN** `build_source_text` runs
- **THEN** the `doc_text` contains a `SKU:` line
- **AND** it contains an `Estilo:` line when style tags are present
- **AND** it contains no price figure and no `price_band`

#### Scenario: Provenance metadata is not rendered
- **GIVEN** a record that also carries `data_origin`, `text_provenance`, confidence or `source` outside the DTO
- **WHEN** `build_source_text` runs
- **THEN** those values do not appear in the `doc_text`

### Requirement: Embedding is not recomputed when the cache key is unchanged
The embedding client MUST cache vectors in process memory under the key `(sha256(text), model, version)` with no TTL and no external store. A second `embed` of the same texts with the same model and version MUST NOT call the provider. The returned vectors MUST be identical. An injected fake MUST observe the call count.

#### Scenario: Unchanged text is served from cache
- **GIVEN** an `EmbeddingClient` that has already embedded a text with a model and version
- **WHEN** `embed` is called again with the same text, model and version
- **THEN** the provider is not called
- **AND** the returned vector is the same
- **AND** an injected fake reports a cache hit

### Requirement: Vectors whose dimension is not 1536 are rejected
After every provider response the adapter MUST assert that each vector has length 1536. A vector of any other length MUST raise an identifiable error. The client MUST NOT return a vector that a later writer could insert into `vector(1536)`.

#### Scenario: A mismatched dimension fails loudly
- **GIVEN** a provider or fake that returns 384 or 3072 dimensions
- **WHEN** the adapter validates the result
- **THEN** an identifiable error is raised
- **AND** no vector is returned to the caller

### Requirement: Embedding uses LiteLLM with batching retry and distinct version keys
The runtime adapter MUST call LiteLLM embeddings (`aembedding` or the stable equivalent in the pinned `litellm` version), not the catalog OpenAI SDK client and not the enrichment completion port. `embed` MUST be asynchronous. Texts MUST be split into batches of `JPV_EMBEDDING_BATCH_SIZE` (default 64). The adapter MUST retry with backoff on HTTP 429 and 5xx and MUST NOT retry validation 4xx. The default model MUST be `openai/text-embedding-3-small`. The client MUST expose `document_version_key` as `{model}:1536:source-text/v1` and `model_version_key` as `{model}:1536`. Document embedding results MUST carry `document_version_key` as `embedding_version`. The adapter MUST NOT apply an extra L2 normalisation step.

#### Scenario: A batch larger than the setting is split
- **GIVEN** `JPV_EMBEDDING_BATCH_SIZE` is 64
- **AND** `embed` is called with more than 64 texts
- **WHEN** the adapter talks to the provider
- **THEN** no single provider call contains more than 64 texts

#### Scenario: Version keys distinguish document preprocess from model space
- **WHEN** the embedding client is constructed with the default model
- **THEN** `document_version_key` is `{model}:1536:source-text/v1`
- **AND** `model_version_key` is `{model}:1536`
- **AND** a document `EmbedResult` reports `document_version_key` as `embedding_version`

### Requirement: Embedding without its own key fails and does not use the RAG LLM key
Calling `embed` without `JPV_EMBEDDING_API_KEY` MUST fail with an explicit domain or configuration error. The client MUST NOT substitute `JPV_RAG_LLM_API_KEY` or `JPV_CATALOG_LLM_API_KEY`.

#### Scenario: Embed without the embedding key fails explicitly
- **GIVEN** `JPV_EMBEDDING_API_KEY` is absent
- **AND** `JPV_RAG_LLM_API_KEY` is present
- **WHEN** `embed` is called on the real adapter
- **THEN** the call fails with an explicit error
- **AND** the RAG LLM key is not used

### Requirement: The HTTP application does not import the indexing library
`jbg_ai.api.main` MUST NOT import `jbg_ai.indexing`. `POST /v1/index/sync` and `GET /v1/index/status` MUST remain the C13 stub (or HTTP 501 when `STUB_MODE` is false). The OpenAPI snapshot MUST NOT be regenerated. The library MUST NOT write rows to `ai.product_document` and MUST NOT add an Alembic or EF Core migration.

#### Scenario: The service HTTP surface is unchanged
- **WHEN** this change is implemented
- **THEN** `jbg_ai.api.main` does not import `jbg_ai.indexing`
- **AND** `POST /v1/index/sync` is still the C13 stub or 501
- **AND** `ai-service/openapi.json` is unchanged

### Requirement: The indexing unit suite makes no provider or database calls
Tests under `ai-service/tests/indexing/` MUST inject a fake `EmbeddingClient`. They MUST NOT open sockets to embedding providers, LLM providers or RDS. They MUST NOT use a database marker or Testcontainers.

#### Scenario: Unit suite stays offline
- **WHEN** the indexing unit tests run
- **THEN** they use an injected fake rather than LiteLLM
- **AND** no socket is opened to an embedding provider, LLM provider or RDS
