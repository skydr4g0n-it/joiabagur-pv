# pos-projection

## ADDED Requirements

### Requirement: The POS availability feed is drained into ai.pos_projection by a CLI
The indexing package SHALL expose a typed client over the existing POS feed method that parses `kind` `upsert` | `tombstone` and maps camelCase fields onto `point_of_sale_id`, `product_id`, `qty_bucket`, `is_assigned_hint`, `sales_30d`, `sales_90d`, `last_sale_at`, `computed_as_of` and `watermark`. Draining MUST be reachable as `python -m jbg_ai.indexing sync-pos`, accepting `--full` to ignore the checkpoint. The command MUST load the local environment file exactly as the catalog `sync` command does. Upserts MUST be idempotent on `(pos_id, product_id)` and MUST set `refreshed_at`. This capability MUST NOT add a route under `/v1`, MUST NOT start an in-process scheduler or background task, MUST NOT open an EF Core migration, and Python MUST NOT read or write schema `public` by SQL. Its only schema change MUST be a single additive Alembic revision adding a nullable `computed_as_of` column to `ai.pos_projection`: no table may be created or dropped and no existing column may be altered.

#### Scenario: Draining the POS feed populates the projection
- **GIVEN** a POS availability feed with upsert items and `STUB_MODE` disabled
- **WHEN** `python -m jbg_ai.indexing sync-pos` is run
- **THEN** one row per `(pos_id, product_id)` exists in `ai.pos_projection`
- **AND** running the same command again produces the same rows without duplicating any
- **AND** no route was added under `/v1` and no scheduler was started

#### Scenario: The projection stores a bucket and never the exact quantity
- **GIVEN** a feed upsert whose `qtyBucket` is `0`, `1-2` or `3+`
- **WHEN** the projection row is written
- **THEN** `qty_bucket` holds that bucket
- **AND** no column of `ai.pos_projection` holds an exact quantity
- **AND** a value outside that vocabulary is rejected by the schema constraint

#### Scenario: The only schema change is one additive nullable column
- **GIVEN** the change is implemented
- **WHEN** the Alembic history and the .NET migrations are inspected
- **THEN** exactly one new revision exists and it only adds `computed_as_of` to `ai.pos_projection`
- **AND** that column is nullable and carries no default
- **AND** no table is created, altered or dropped, and no EF Core migration exists

### Requirement: The POS drain keeps its own keyset checkpoint
The POS drain SHALL persist its cursor in `ai.sync_checkpoint` under `feed` value `pos-availability`, recording `watermark`, `since_id`, `last_incremental_sync_at`, `last_full_sync_at`, `last_aggregate_hash` and `indexed_count`. A run without `--full` MUST resume from that cursor. The catalog checkpoint row MUST NOT be read or written by this drain. Batch failures MUST be recorded in `ai.sync_failure` without aborting the remaining pages.

#### Scenario: A second run resumes instead of restarting
- **GIVEN** a completed POS drain that stored a cursor
- **WHEN** `sync-pos` runs again without `--full`
- **THEN** the request carries the stored keyset cursor
- **AND** the `catalog` checkpoint row is unchanged

#### Scenario: A full run ignores the stored cursor
- **GIVEN** a stored POS cursor
- **WHEN** `sync-pos --full` is run
- **THEN** the first page is requested without cursor query parameters
- **AND** the catalog checkpoint row is still unchanged

### Requirement: An unassigned tombstone soft-deletes the projection row
A POS tombstone with reason `unassigned` MUST set `is_assigned_hint` to false and `qty_bucket` to `0` on the matching row and MUST NOT delete it. When no row exists for that pair, the tombstone MUST insert one in that state. Deleting the row is forbidden because the upsert branch of the feed reports `isAssignedHint` as true for every active assignment, so a delete would make the false value unreachable and would destroy the only record distinguishing a product never carried at a point of sale from one no longer carried there.

#### Scenario: Unassignment keeps the row and flips the hint
- **GIVEN** a projection row for a pair that the feed later reports as a tombstone with reason `unassigned`
- **WHEN** the drain processes that tombstone
- **THEN** the row still exists
- **AND** `is_assigned_hint` is false and `qty_bucket` is `0`
- **AND** `refreshed_at` has advanced

#### Scenario: A tombstone for an unknown pair inserts the soft-deleted row
- **GIVEN** a tombstone for a `(pos_id, product_id)` pair absent from the projection
- **WHEN** the drain processes it
- **THEN** a row is inserted with `is_assigned_hint` false and `qty_bucket` `0`

### Requirement: The point-of-sale scope is the retriever's only hard filter
When the prefilter is enabled and the projection is usable, product retrieval MUST restrict candidates to rows of `ai.pos_projection` whose `pos_id` equals the token's point of sale and whose `is_assigned_hint` is true, applied in SQL to every branch that produces candidates. The scope MUST be taken from the token claim and never from the request body. A `pos_id` claim that does not parse as a UUID MUST cause the request to be rejected and MUST NOT be treated as an absent scope or widened to the whole catalogue. Restricting by assignment mirrors the .NET hydration predicate, which excludes the same rows; no other predicate added by this capability may exclude a candidate.

#### Scenario: Candidates come only from the point of sale's assortment
- **GIVEN** a token whose point of sale carries a strict subset of the indexed catalogue
- **WHEN** a product retrieval is served with the prefilter enabled and a fresh projection
- **THEN** every returned candidate is assigned to that point of sale in the projection
- **AND** products assigned only to other points of sale are absent
- **AND** the over-retrieval window is filled from the scoped subset rather than from the whole catalogue

#### Scenario: A soft-deleted assignment is out of scope
- **GIVEN** a projection row whose `is_assigned_hint` is false
- **WHEN** a retrieval is served for that point of sale
- **THEN** that product is not among the candidates
- **AND** the row remains in the projection

#### Scenario: A malformed point of sale claim never widens the search
- **GIVEN** a valid service token whose `pos_id` claim is not a UUID
- **WHEN** a product retrieval is requested
- **THEN** the request is rejected
- **AND** no retrieval is served over the unscoped catalogue

### Requirement: Availability demotes a candidate and never removes it
A candidate whose projection row reports `qty_bucket` of `0` MUST be ordered after otherwise comparable candidates and MUST remain inside the over-retrieval window. The demotion MUST be applied as an additional component of the single stable ordering key that already demotes on constraints read from the query text, and MUST rank below all of them, so a constraint the operator expressed outranks a signal they did not ask for. The distinction MUST be binary between `0` and any other bucket; `1-2` and `3+` MUST NOT be ordered against each other by this capability. No stock value may reach the response as an exact quantity.

#### Scenario: An out-of-stock product is demoted, not removed
- **GIVEN** a point of sale holding both in-stock and zero-stock assigned products that match a query
- **WHEN** a product retrieval is served
- **THEN** the zero-stock products are still present among the results
- **AND** they are ordered after comparable in-stock products
- **AND** removing them from the response never occurs

#### Scenario: A typed constraint outranks the stock signal
- **GIVEN** a query expressing a price ceiling and results that differ in both price and stock
- **WHEN** the candidates are ordered
- **THEN** candidates within the ceiling precede candidates above it regardless of their stock
- **AND** stock decides the order only between candidates that the typed constraints rank equally

#### Scenario: The two non-zero buckets are not ordered against each other
- **GIVEN** two candidates whose buckets are `1-2` and `3+` and which the other blocks rank equally
- **WHEN** the candidates are ordered
- **THEN** their relative order is the one the fusion produced

### Requirement: The response reports projection freshness taken from the checkpoint
The retrieval response SHALL carry an optional `projection_age_seconds`, computed as the elapsed time since `ai.sync_checkpoint.last_incremental_sync_at` for `feed` value `pos-availability`. It MUST NOT be derived from `ai.pos_projection.refreshed_at` in any form, because the feed is incremental and an assignment that never changes is never re-emitted, so that column records when an assignment last changed rather than when the projection was last read. The value MUST be read through a short-lived cache so repeated retrievals do not consume the connection pool. Adding the field regenerates `ai-service/openapi.json`.

#### Scenario: Freshness reflects the last synchronisation, not the last change
- **GIVEN** a projection whose rows were last written long ago and whose feed was drained moments ago
- **WHEN** a product retrieval is served
- **THEN** `projection_age_seconds` reports seconds and not the age of the rows
- **AND** the value derives from the `pos-availability` checkpoint

#### Scenario: The regenerated contract is committed
- **GIVEN** the response model carries the new optional field
- **WHEN** the OpenAPI snapshot test runs
- **THEN** it passes against the committed `ai-service/openapi.json`
- **AND** that file contains `projection_age_seconds`

### Requirement: An empty projection fails loudly and a stale one degrades openly
When the prefilter is enabled and the projection holds no assigned row for the token's point of sale, product retrieval MUST respond HTTP 503 with a detail naming the cause, and MUST NOT respond 200 with an empty result list, which would be indistinguishable from a legitimate abstention. When the projection age exceeds the configured ceiling, the point-of-sale scope MUST NOT be applied for that request, the degradation MUST be logged, and the response MUST still report the projection age. `GET /health` MUST remain HTTP 200 in both cases.

#### Scenario: An unsynchronised projection is 503 and not an abstention
- **GIVEN** the prefilter is enabled and `ai.pos_projection` holds no assigned row for the token's point of sale
- **WHEN** a product retrieval is requested
- **THEN** the response status is 503
- **AND** the detail names the projection as the cause
- **AND** the body is not a successful retrieval with an empty result list
- **AND** `GET /health` remains HTTP 200

#### Scenario: A stale projection stops filtering instead of hiding products
- **GIVEN** a projection whose age exceeds the configured ceiling
- **WHEN** a product retrieval is requested
- **THEN** candidates are not restricted by the point of sale for that request
- **AND** the response reports the projection age
- **AND** the degradation is recorded in the logs
- **AND** the page may be shorter than requested rather than omitting a valid product

### Requirement: The prefilter is switchable without moving the frozen request schema
The point-of-sale prefilter SHALL be governed by a setting that supplies only a default, with the effective value travelling as a parameter of the retrieval orchestration call, so configurations can be swept inside one process without restarting. The staleness ceiling SHALL be configurable in the same way. Neither value may be added to the retrieval request schema. With the prefilter disabled, retrieval MUST behave as it did before this capability existed.

#### Scenario: Disabling the prefilter restores the previous behaviour
- **GIVEN** the prefilter is disabled
- **WHEN** a product retrieval is served
- **THEN** candidates are drawn from the whole indexed catalogue
- **AND** no point-of-sale restriction is applied in SQL
- **AND** the request schema of `POST /v1/retrieval/products` is unchanged

#### Scenario: A sweep overrides the default without restarting
- **GIVEN** a caller that passes the prefilter value as a parameter of the orchestration call
- **WHEN** two retrievals are served with opposite values in the same process
- **THEN** each behaves according to its parameter
- **AND** the setting default is not mutated

### Requirement: The scoped pipeline is observable and its cardinality is recorded
The drain and the retrieval MUST emit structured logs carrying `trace_id`. Retrieval MUST log a projection stage reporting the projection age, the number of rows in the point-of-sale scope, and whether the hard filter was applied. The search stage MUST report the candidate count produced under the scope. Vectors MUST NOT be written to logs.

#### Scenario: Every scoped retrieval records what the scope admitted
- **GIVEN** a product retrieval served with the prefilter enabled
- **WHEN** the request completes
- **THEN** a projection stage entry carries `trace_id`, the projection age, the scope size and whether the filter was applied
- **AND** the search stage entry reports the candidates produced under that scope
- **AND** no embedding vector appears in any log entry

### Requirement: Sales aggregates are stored by this capability and read by none of it
The projection SHALL persist `sales_30d`, `sales_90d`, `last_sale_at` and the reference instant reported by the feed. This capability MUST NOT use any of them to order, filter or score candidates; they exist for the business-signals ranking that follows. The reference instant MUST be stored **on each row** so a later consumer can tell what clock produced that row's figures. Storing it once per synchronisation instead is insufficient, because the feed is incremental: a pair the feed does not re-emit keeps the figures the run that wrote it computed, so one projection can hold rows counted against different instants.

#### Scenario: Sales figures are persisted without influencing the ranking
- **GIVEN** two assigned candidates identical except for their sales figures
- **WHEN** a product retrieval is served
- **THEN** their relative order is the one produced by fusion and the demotion blocks
- **AND** both rows carry their sales figures and the reference instant in the projection

### Requirement: Retrieval unit tests reach no provider, no public schema and no network
Tests for this capability MUST run offline with injected fakes. They MUST NOT call an embedding provider, an LLM or a remote database, and MUST NOT read schema `public` by SQL. Database-backed tests MUST use an ephemeral PostgreSQL with pgvector and skip when it is unreachable.

#### Scenario: The offline suite makes no external call
- **GIVEN** the retrieval and indexing test suites for this capability
- **WHEN** they run without credentials configured
- **THEN** they pass
- **AND** no provider call, no network call and no query against schema `public` is made
