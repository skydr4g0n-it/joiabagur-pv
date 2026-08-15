## ADDED Requirements

### Requirement: Schema `ai` is the only namespace the AI service writes to
The vector index and all state owned by `jbg-ai` MUST live in PostgreSQL schema `ai`. The AI service MUST NOT create, modify or read by SQL any table in schema `public`, which belongs to the .NET API. The migration bookkeeping table MUST also live in schema `ai`, not in `public`. The only object the AI service MAY install outside `ai` is the `vector` extension itself, which resolves the column type and is installed in the default schema.

#### Scenario: Migration bookkeeping stays inside the AI schema
- **WHEN** migrations are applied to a clean database
- **THEN** the migration version table exists in schema `ai`
- **AND** no migration version table exists in schema `public`

#### Scenario: No tables are created outside the AI schema
- **WHEN** migrations are applied to a clean database
- **THEN** every table created by the migration belongs to schema `ai`
- **AND** no table in schema `public` has been created, altered or dropped

### Requirement: Extension and schema are provisioned before migrations run
The `vector` extension and schema `ai` MUST exist before the first migration executes, because migration bookkeeping is materialised before any migration script runs. Provisioning MUST be idempotent: applying migrations against a database where an administrator has already installed the extension MUST succeed without error, and re-applying migrations MUST NOT fail.

#### Scenario: Migration provisions extension and schema on a clean database
- **WHEN** migrations are applied to a database where the `vector` extension is available but not installed
- **THEN** the `vector` extension is installed and reported as installed by the catalog
- **AND** schema `ai` exists
- **AND** the tables of the vector index exist inside schema `ai`

#### Scenario: Provisioning is idempotent
- **WHEN** an administrator has already installed the `vector` extension and created schema `ai`
- **AND** migrations are applied
- **THEN** the migration completes without error
- **AND** applying migrations again produces no error and no change

#### Scenario: Insufficient privilege fails immediately and identifiably
- **WHEN** migrations are applied by a role that cannot install extensions against a database where the extension has not been provisioned
- **THEN** the migration fails immediately with an error identifying the cause
- **AND** the schema is not left partially migrated

### Requirement: A dedicated database role owns AI schema access with least privilege
A database role dedicated to `jbg-ai` MUST exist, distinct from the role used by the .NET API. It MUST hold usage and creation rights on schema `ai`. It MUST hold, on schema `public`, no more than the usage needed to resolve the `vector` type, and MUST NOT hold read or write privileges on any table in `public`. Role creation and grants MUST be performed by a privileged one-off provisioning step, not by a migration, because roles are cluster-level objects whose removal fails once they own objects.

#### Scenario: The service role can migrate and operate its own schema
- **WHEN** the dedicated role connects to the database
- **THEN** it can create, read and write tables in schema `ai`

#### Scenario: The service role cannot read business tables
- **WHEN** the dedicated role attempts to select from any table in schema `public`
- **THEN** the operation is refused

### Requirement: The initial migration is reversible without leaving orphaned objects
Applying and then reverting the migration MUST return the database to a state where the migration can be applied again successfully. Reverting MUST drop the tables it created. Reverting MUST NOT drop schema `ai` nor the `vector` extension, because the extension is shared database-wide and the schema holds the migration bookkeeping table itself.

#### Scenario: Revert removes the tables and keeps the shared objects
- **WHEN** the migration has been applied to a clean database
- **AND** the migration is reverted to the base revision
- **THEN** the tables of the vector index no longer exist
- **AND** schema `ai` still exists
- **AND** the `vector` extension is still installed

#### Scenario: Re-applying after a revert succeeds
- **WHEN** the migration has been applied and then reverted
- **AND** the migration is applied again
- **THEN** it completes without error
- **AND** no leftover type, index or constraint from the previous application causes a collision

### Requirement: Vector indexes use the cosine operator class
Every index over an embedding column MUST use the HNSW access method with the cosine operator class, matching the cosine distance operator used to query it. A mismatch between the index operator class and the query operator silently disables the index and degrades the query to a sequential scan without raising any error, so the alignment MUST be verifiable from the database catalog. Build parameters MUST be declared explicitly rather than inherited from engine defaults.

#### Scenario: Product embedding index is HNSW with cosine operator class
- **WHEN** the catalog is queried for the index over the product document embedding column
- **THEN** its access method is HNSW
- **AND** its operator class is the cosine operator class for vectors

#### Scenario: Knowledge chunk embedding index is HNSW with cosine operator class
- **WHEN** the catalog is queried for the index over the knowledge chunk embedding column
- **THEN** its access method is HNSW
- **AND** its operator class is the cosine operator class for vectors

#### Scenario: A euclidean operator class is detected as a defect
- **WHEN** an embedding index is declared with the euclidean operator class instead of the cosine one
- **THEN** the catalog assertion fails
- **AND** the failure occurs even though index creation itself raised no error

### Requirement: Array and full-text filters are backed by GIN indexes
Columns queried by array overlap or containment, by full-text match, or by JSON containment MUST have a GIN index. This covers the materials array of product documents, the full-text vector of product documents and of knowledge chunks, and the metadata document of knowledge chunks.

#### Scenario: Materials array has a GIN index
- **WHEN** the catalog is queried for the indexes of the product document table
- **THEN** a GIN index exists over the materials array column

#### Scenario: Full-text and metadata columns have GIN indexes
- **WHEN** the catalog is queried for the indexes of the product document and knowledge chunk tables
- **THEN** a GIN index exists over each full-text vector column
- **AND** a GIN index exists over the knowledge chunk metadata column

### Requirement: Structural filter columns are backed by B-tree indexes
Columns used as structural filters or as reporting dimensions MUST have a B-tree index: the family identifier, the piece type, the price band and the data origin of product documents.

#### Scenario: Structural filter columns are indexed
- **WHEN** the catalog is queried for the indexes of the product document table
- **THEN** a B-tree index exists over the family identifier
- **AND** a B-tree index exists over the piece type
- **AND** a B-tree index exists over the price band
- **AND** a B-tree index exists over the data origin

### Requirement: Full-text vectors are produced by the schema with the Spanish configuration
Full-text search columns MUST be generated columns computed by the database from their source text using the Spanish text search configuration, named explicitly. They MUST NOT be populated by application code, so that no write path can store a vector built with a different configuration.

#### Scenario: Full-text column is generated with the Spanish configuration
- **WHEN** the definition of the full-text vector column of product documents is inspected
- **THEN** it is a stored generated column
- **AND** its expression names the Spanish text search configuration explicitly

#### Scenario: Knowledge chunks use the same guarantee
- **WHEN** the definition of the full-text vector column of knowledge chunks is inspected
- **THEN** it is a stored generated column over the chunk content
- **AND** its expression names the Spanish text search configuration explicitly

### Requirement: Product documents are stored one row per product with closed vocabularies
The product document table MUST hold exactly one row per product, keyed by the product identifier assigned by the .NET API, without chunking. It MUST carry the materials as an array so that overlap and containment filters are possible, the canonical document text and its content hash, an embedding column, the family identifier and variant label, the activity flag, and the data origin. Columns with a closed vocabulary — data origin, price band — MUST be constrained by a check constraint rather than by an enumerated type, because an enumerated type survives dropping its table and breaks the next application of the migration. The embedding column MUST accept nulls so that a document can be inserted before its embedding is computed.

#### Scenario: Data origin is restricted to the declared vocabulary
- **WHEN** a row is inserted with a data origin outside the declared vocabulary
- **THEN** the write is rejected by the check constraint

#### Scenario: Embedding may be absent
- **WHEN** a product document row is inserted without an embedding
- **THEN** the write succeeds
- **AND** the row is retained until an embedding is supplied

#### Scenario: Reverting leaves no vocabulary type behind
- **WHEN** the migration is reverted
- **THEN** no database type created for a closed vocabulary remains

### Requirement: Knowledge documents and chunks are stored separately with cascading deletes
Commercial knowledge MUST be stored as documents and their derived chunks in two tables related one-to-many. Deleting a knowledge document MUST delete its chunks through a foreign key with cascading delete, without application logic. The pair of document identifier and chunk index MUST be unique. Knowledge MUST NOT be scoped to a product.

#### Scenario: Deleting a document removes its chunks
- **WHEN** a knowledge document with chunks is deleted
- **THEN** its chunks are deleted as well
- **AND** no orphaned chunk remains

#### Scenario: Chunk index is unique within a document
- **WHEN** two chunks of the same document are inserted with the same chunk index
- **THEN** the second write is rejected

### Requirement: Point-of-sale projection stores availability buckets, never exact quantities
The projection table MUST be keyed by the pair of point-of-sale identifier and product identifier, and MUST store availability as a bucket constrained to a closed vocabulary, never as an exact quantity. It MUST carry the assignment hint, the sales windows, the last sale instant and the refresh instant. Exact stock quantities remain the authority of the .NET API.

#### Scenario: Bucket vocabulary is enforced
- **WHEN** a projection row is written with an availability value outside the declared bucket vocabulary
- **THEN** the write is rejected

#### Scenario: Projection carries its own freshness
- **WHEN** a projection row is written
- **THEN** the refresh instant is stored on the row so that consumers can report projection age

### Requirement: Co-occurrence pairs are stored in a single orientation
The co-occurrence table MUST be keyed by the pair of product identifiers and MUST enforce, by check constraint, that the first identifier is strictly lower than the second. Without that constraint the same pair can be stored twice and any downstream complementary-recommendation signal is doubled.

#### Scenario: Reversed pair is rejected
- **WHEN** a co-occurrence row is written with the identifiers in descending order
- **THEN** the write is rejected by the check constraint

#### Scenario: The same pair cannot be stored twice
- **WHEN** a co-occurrence row already exists for a pair
- **AND** the same pair is inserted again in the canonical orientation
- **THEN** the write is rejected by the primary key

### Requirement: Synchronization failures are recorded for retry
Failed synchronization batches MUST be recorded with the feed they came from, the cursor in use, the payload, the error, the attempt count and the next retry instant, so that a failed batch neither blocks the others nor is lost. The next retry instant MUST be indexed so the retry queue can be read without a sequential scan.

#### Scenario: A failure is recorded with enough context to retry it
- **WHEN** a synchronization batch fails
- **THEN** a row is recorded with the feed, the cursor, the payload, the error, the attempt count and the next retry instant

#### Scenario: Retry queue is indexed
- **WHEN** the catalog is queried for the indexes of the synchronization failure table
- **THEN** an index exists over the next retry instant

### Requirement: The AI schema declares no foreign keys into the business schema
Columns of schema `ai` that reference entities owned by the .NET API — products, points of sale, families — MUST be plain identifier columns without a foreign key constraint into schema `public`. Coupling the two schemas by referential integrity would make migrations of one fail on the other and would contradict the ownership boundary. Foreign keys between tables inside schema `ai` are permitted and expected.

#### Scenario: No constraint crosses the schema boundary
- **WHEN** the catalog is queried for foreign key constraints of the tables in schema `ai`
- **THEN** no constraint references a table in schema `public`

#### Scenario: Intra-schema referential integrity is preserved
- **WHEN** the catalog is queried for foreign key constraints of the knowledge chunk table
- **THEN** a constraint references the knowledge document table inside schema `ai`

### Requirement: Database access uses a bounded connection pool created on demand
The AI service MUST access PostgreSQL through a connection pool whose total number of simultaneous connections is capped at the configured pool size, with no additional overflow, so the cap is effective rather than nominal. The default cap MUST be 5, within the project-wide budget shared with the .NET API. Waiting for a free connection MUST time out well below the latency budget the .NET API allows for a retrieval call. The pool MUST be created on first use, not at import time, so that importing the module opens no connection.

#### Scenario: The pool cap is effective
- **WHEN** the database engine is built with the default configuration
- **THEN** the maximum number of simultaneous connections is 5
- **AND** no overflow connections beyond that cap are permitted

#### Scenario: The engine is not created at import time
- **WHEN** the database module is imported
- **THEN** no connection is opened
- **AND** no engine is constructed until a session is first requested

#### Scenario: Requesting a session without configuration fails clearly
- **WHEN** a session is requested and no database connection string is configured
- **THEN** the call fails with an error identifying the missing configuration
- **AND** the failure occurs at that point, not at service startup
