## ADDED Requirements

### Requirement: Synchronization checkpoint stores a keyset per feed
Schema `ai` MUST contain table `sync_checkpoint` with one row per feed identifier (text, for catalog the value `catalog`). The row MUST store the keyset cursor (`watermark timestamptz`, `since_id uuid`), `last_full_sync_at`, `last_incremental_sync_at`, `last_aggregate_hash char(64)` and `indexed_count int`. `sync_failure` MUST NOT be used as the bookmark. The table MUST live in schema `ai` with no foreign key into `public`. Downgrade MUST drop this table without dropping the C05 tables.

#### Scenario: Catalog checkpoint round-trips a keyset
- **GIVEN** the C13 migration has been applied
- **WHEN** a catalog sync persists progress after a successful item
- **THEN** `ai.sync_checkpoint` holds feed `catalog` with that item's watermark and `since_id`
- **AND** `indexed_count` reflects the number of documents in `ai.product_document`

#### Scenario: Revert drops the checkpoint table
- **WHEN** the C13 migration is reverted
- **THEN** table `ai.sync_checkpoint` does not exist
- **AND** the six C05 tables still exist except for the dropped `text_provenance` column

## MODIFIED Requirements

### Requirement: Structural filter columns are backed by B-tree indexes
Columns used as structural filters or as reporting dimensions MUST have a B-tree index: the family identifier, the piece type, the price band, the data origin and the text provenance of product documents.

#### Scenario: Structural filter columns are indexed
- **WHEN** the catalog is queried for the indexes of the product document table
- **THEN** a B-tree index exists over the family identifier
- **AND** a B-tree index exists over the piece type
- **AND** a B-tree index exists over the price band
- **AND** a B-tree index exists over the data origin
- **AND** a B-tree index exists over the text provenance

### Requirement: Product documents are stored one row per product with closed vocabularies
The product document table MUST hold exactly one row per product, keyed by the product identifier assigned by the .NET API, without chunking. It MUST carry the materials as an array so that overlap and containment filters are possible, the canonical document text and its content hash, an embedding column, the family identifier and variant label, the activity flag, the data origin, and the text provenance. Columns with a closed vocabulary — data origin, price band, text provenance — MUST be constrained by a check constraint rather than by an enumerated type, because an enumerated type survives dropping its table and breaks the next application of the migration. `text_provenance` MUST be NOT NULL and MUST accept only `merchant`, `ai_assisted` or `synthetic`. The embedding column MUST accept nulls so that a document can be inserted before its embedding is computed.

#### Scenario: Data origin is restricted to the declared vocabulary
- **WHEN** a row is inserted with a data origin outside the declared vocabulary
- **THEN** the write is rejected by the check constraint

#### Scenario: Text provenance is restricted to the declared vocabulary
- **WHEN** a row is inserted with a text provenance outside `merchant`, `ai_assisted` or `synthetic`
- **THEN** the write is rejected by the check constraint

#### Scenario: Text provenance cannot be null
- **WHEN** a product document row is inserted without `text_provenance`
- **THEN** the write is rejected

#### Scenario: Embedding may be absent
- **WHEN** a product document row is inserted without an embedding
- **THEN** the write succeeds
- **AND** the row is retained until an embedding is supplied

#### Scenario: Reverting leaves no vocabulary type behind
- **WHEN** the migration is reverted
- **THEN** no database type created for a closed vocabulary remains

### Requirement: Synchronization failures are recorded for retry
Failed synchronization items MUST be recorded with the feed they came from, the keyset cursor in use (`cursor_since` and `cursor_since_id`), the product identifier when known, the payload, the error, the attempt count and the next retry instant, so that a failed item neither blocks the others nor is lost. The next retry instant MUST be indexed so the retry queue can be read without a sequential scan. This table MUST NOT be used as the sync bookmark.

#### Scenario: A failure is recorded with enough context to retry it
- **WHEN** a synchronization item fails
- **THEN** a row is recorded with the feed, the cursor (`cursor_since` and `cursor_since_id` when known), the `product_id` when known, the payload, the error, the attempt count and the next retry instant

#### Scenario: Retry queue is indexed
- **WHEN** the catalog is queried for the indexes of the synchronization failure table
- **THEN** an index exists over the next retry instant
