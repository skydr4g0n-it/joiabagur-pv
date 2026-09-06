## ADDED Requirements

### Requirement: Commercial knowledge is authored as versioned documents, never scoped to a product
The service SHALL read its commercial knowledge from Markdown documents versioned in the repository, one file per document. Each document MUST declare a knowledge type drawn from the closed vocabulary the schema already constrains, and MUST NOT be scoped to a product: no section may name a stock keeping unit, an individual product, or a price. Sales scripts MUST NOT be part of the corpus, because retrieved imperative text is indistinguishable from an instruction once it reaches a model context.

A section MUST also remain true when the catalogue changes. It MUST NOT state a count of the assortment nor a proportion of it, because such a claim expires silently the day a product is added or withdrawn while its citation keeps resolving and keeps locating — leaving a falsehood carrying a verified stamp. A proportion that is not about the assortment MUST NOT be rejected on the strength of its notation alone. Measured evidence MAY govern which documents exist and how deep each one goes, and MUST be recorded outside the citable text.

#### Scenario: A section naming a product or a price is rejected
- **WHEN** the corpus is validated and a section names a stock keeping unit, an individual product or a price
- **THEN** validation fails naming the file and the section
- **AND** nothing is indexed

#### Scenario: A section counting the assortment is rejected
- **WHEN** the corpus is validated and a section states how many products the catalogue holds, or what proportion of it a material or a piece type represents
- **THEN** validation fails naming the file and the section

#### Scenario: A proportion that is not about the assortment is kept
- **WHEN** a section states a proportion that belongs to the material world rather than to the catalogue
- **THEN** validation accepts it

#### Scenario: Adding or withdrawing a product invalidates no document
- **WHEN** the composition of the catalogue changes
- **THEN** every section of the corpus is still true
- **AND** no document has to be rewritten

#### Scenario: The corpus contains no sales scripts
- **WHEN** the corpus is validated
- **THEN** no document declares the sales script knowledge type

#### Scenario: Knowledge is general rather than product scoped
- **WHEN** an indexed knowledge chunk is inspected
- **THEN** it carries no product identifier
- **AND** it is retrievable without naming any product

### Requirement: Every canonical material has exactly one sheet
The corpus MUST contain exactly one material sheet per canonical material term of the enrichment closed vocabulary. Coverage MUST be derived from that vocabulary rather than chosen by hand, so that extending the vocabulary without extending the corpus is a detectable defect. Stone terms that appear in no catalogue product MUST NOT receive a section of their own.

#### Scenario: Coverage matches the vocabulary
- **WHEN** the corpus is validated against the enrichment vocabularies
- **THEN** every canonical material term has exactly one sheet

#### Scenario: A new vocabulary term without its sheet is a failure
- **WHEN** a canonical material term exists in the vocabulary with no corresponding sheet
- **THEN** validation fails naming the missing term

### Requirement: The size scale is documented as a piece scale with a single ring equivalence table
The corpus MUST document the catalogue letter scale as a measure of the size of the piece, applicable to several piece types, and MUST state that the ring is the only piece type where the letter also commits to a fit. Exactly one document MUST carry the ring equivalence table. That table MUST map each letter to a contiguous, non-overlapping range of whole national ring sizes, MUST cover every letter of the size vocabulary, and MUST satisfy the standard arithmetic relation between a national size and the inner circumference in millimetres. Letters of the vocabulary that appear in no catalogue product MUST be present in the table and marked as available to order rather than stocked. Words that describe the scale of a motif MUST NOT be used anywhere as a ring fit label.

#### Scenario: The table is arithmetically consistent
- **WHEN** the ring equivalence table is validated
- **THEN** each letter maps to whole national sizes
- **AND** the ranges of consecutive letters are contiguous and do not overlap
- **AND** the circumference stated for every national size satisfies the standard relation

#### Scenario: The table covers the vocabulary, including the unused rungs
- **WHEN** the ring equivalence table is compared against the size vocabulary
- **THEN** every letter of the vocabulary appears in the table
- **AND** the letters absent from the catalogue are marked as available to order

#### Scenario: Motif-scale words are never a fit label
- **WHEN** the corpus is validated
- **THEN** no section presents a motif-scale word as a ring fit measurement

#### Scenario: The arithmetic and the assignment carry different scopes
- **WHEN** the sections of the ring size document are inspected
- **THEN** the section stating the relation between national size and circumference is scoped as verifiable outside
- **AND** the section assigning letters to ranges is scoped as a commitment of the establishment

#### Scenario: Resizing limits agree across the documents that state them
- **WHEN** the corpus states which rings can be resized
- **THEN** the materials it excludes are the same ones the corresponding material sheets exclude
- **AND** the same limits appear in the repairs and adjustments policy

### Requirement: Each section declares the scope of what it claims
Every section MUST declare, as authored metadata, whether its claim is verifiable outside the jewellery — chemistry, allergens, measurements, geography — or is a commitment of the establishment. A section without that declaration MUST be rejected at ingestion. The declaration MUST travel with the chunk that section produces, so a consumer can present a commitment differently from a verifiable fact. The declaration MUST be recorded per section and not per document, because a single document can carry claims of both kinds. A section MAY additionally carry a reference stating where its claim can be checked.

#### Scenario: A section without a declared scope is rejected
- **WHEN** the corpus is validated and a section carries no claim scope
- **THEN** validation fails naming the file and the section

#### Scenario: The declared scope travels with the retrieved chunk
- **WHEN** a knowledge search returns a chunk
- **THEN** the result reports the claim scope of the section it came from

#### Scenario: One document carries sections of both kinds
- **WHEN** a document contains a claim verifiable outside and a commitment of the establishment
- **THEN** each section carries its own scope
- **AND** the document itself carries no single scope value

### Requirement: Documents are chunked by section, without overlap, carrying their titles into the indexed content
The service MUST produce exactly one chunk per second-level section. Chunks MUST NOT overlap. The indexed content of a chunk MUST begin with the document title and the section title, so that both take part in the embedding and in the full-text vector the schema generates. Authored metadata markers MUST be stripped before the content is assembled, so they enter neither the embedding nor the full-text vector. A document MUST NOT carry text before its first section, because such text would produce a chunk with no locator. A section longer than the configured maximum MUST fail ingestion rather than being split automatically.

#### Scenario: Section titles are preserved in chunk metadata
- **WHEN** a document is chunked
- **THEN** each chunk records its document title and its section title as metadata
- **AND** the indexed content of the chunk begins with both titles

#### Scenario: Metadata markers do not reach the index
- **WHEN** a section declaring its claim scope is chunked
- **THEN** the marker is absent from the indexed content

#### Scenario: Text before the first section is rejected
- **WHEN** a document carries text between its title and its first section
- **THEN** validation fails naming the file

#### Scenario: An oversized section fails ingestion
- **WHEN** a section exceeds the configured maximum size
- **THEN** ingestion fails naming the file and the section
- **AND** the section is not split automatically

### Requirement: Chunk identity is deterministic and citations resolve to the repository
The identifier of a knowledge document MUST be derived deterministically from its slug, and the identifier of a chunk MUST be derived deterministically from the pair of document slug and section slug. Each chunk MUST additionally carry a human-readable citation identifier composed of those same two slugs. Chunk identity MUST NOT be derived from the position of the section within the document, because inserting a section would then silently repoint every later citation. Every indexed citation identifier MUST resolve to a file and a heading that exist in the versioned corpus.

#### Scenario: Every chunk is traceable to its document
- **WHEN** an indexed chunk is inspected
- **THEN** it reports the document it belongs to
- **AND** it reports a citation identifier naming its document and its section

#### Scenario: Identity survives reindexing
- **WHEN** the corpus is indexed twice without the content changing
- **THEN** each chunk keeps the identifier and the citation identifier it had

#### Scenario: Inserting a section does not repoint existing citations
- **WHEN** a new section is inserted between two existing sections and the corpus is reindexed
- **THEN** the citation identifiers of the sections that follow it are unchanged

#### Scenario: A citation that no longer resolves is detected
- **WHEN** an indexed citation identifier names a heading that no longer exists in the corpus
- **THEN** the traceability check fails naming that identifier

### Requirement: Indexing is idempotent and does not re-embed unchanged content
Indexing MUST be repeatable: running it twice over an unchanged corpus MUST leave the same rows. The service MUST record a content hash per chunk and MUST NOT recompute an embedding when neither that hash nor the recorded embedding version has changed. Chunks that a run no longer produces MUST be removed. The service MUST reuse the existing embedding client without modifying it, and MUST NOT create any database table, column or index.

#### Scenario: Unchanged content is not re-embedded
- **WHEN** the corpus is indexed twice with no change
- **THEN** no embedding is requested on the second run

#### Scenario: Chunks no longer produced are removed
- **WHEN** a section is deleted from a document and the corpus is reindexed
- **THEN** its chunk is no longer indexed
- **AND** the remaining chunks of that document are still indexed

#### Scenario: Indexing adds no schema object
- **WHEN** the corpus is indexed
- **THEN** no table, column or index has been created, altered or dropped

### Requirement: Knowledge embeddings are versioned in their own namespace
The embedding version recorded on a knowledge chunk MUST identify the knowledge preprocessing rules, and MUST NOT be the version key that identifies the canonical product text. The two corpora share the embedding model, the vector dimension and the distance operator, but a change to the chunking rules MUST invalidate knowledge embeddings without touching product documents, and a change to the product text renderer MUST NOT invalidate knowledge chunks.

#### Scenario: Knowledge chunks carry their own preprocessing version
- **WHEN** an indexed knowledge chunk is inspected
- **THEN** its embedding version names the knowledge preprocessing rules
- **AND** it differs from the version key recorded on product documents

#### Scenario: Changing the chunking rules invalidates knowledge embeddings only
- **WHEN** the knowledge preprocessing version changes
- **THEN** knowledge chunks are recomputed on the next indexing run
- **AND** no product document is marked stale

### Requirement: Knowledge search returns chunks with their citation and abstains outside the corpus
The service MUST expose knowledge search as a callable of the service itself, not as an HTTP route, and MUST NOT classify a query to decide where to search: the caller states its intent. The search MUST combine a vector branch and a lexical branch over the knowledge chunks and MUST fuse them by rank using the existing fusion function, never by combining raw branch scores. The lexical branch MUST compose its query from the equivalence groups the existing query expansion produces. Terms resolved from the query MUST NOT exclude candidates. Each result MUST carry its citation identifier, its claim scope, its document title and its section title. The distance threshold governing abstention MUST be configured separately from the one used for product retrieval, and below it the search MUST return no result at all.

#### Scenario: A search result carries a resolvable citation
- **WHEN** a knowledge question is searched and a chunk is returned
- **THEN** the result carries its citation identifier, its claim scope and both titles

#### Scenario: A question about one material does not answer with another
- **WHEN** a care question naming one canonical material is searched
- **THEN** the first result comes from the sheet of that material

#### Scenario: An out-of-domain question returns nothing
- **WHEN** a question the corpus does not cover is searched
- **THEN** no chunk is returned
- **AND** the abstention is explicit rather than an empty best-effort list

#### Scenario: Fusion consumes ranks and not raw scores
- **WHEN** the two branches are fused
- **THEN** the fusion receives ordered identifiers and weights only
- **AND** no cosine distance or text rank value takes part in the computation

#### Scenario: The lexical branch can be disabled to measure it
- **WHEN** hybrid search is disabled by configuration
- **THEN** the search behaves as a purely vector retrieval
- **AND** the effective value travels as a parameter of the call

#### Scenario: Knowledge search opens no HTTP surface
- **WHEN** the published endpoint surface is inspected
- **THEN** it contains no knowledge route
- **AND** the committed OpenAPI snapshot is unchanged

### Requirement: The corpus declares how it was produced
The corpus MUST be accompanied by a machine-readable record stating the generator version, the model, the prompt version, the generation instant, and the counts of documents by knowledge type and of sections by claim scope. Those counts MUST be the figures published when the composition of the corpus is declared. Provenance of authorship MUST be recorded there rather than per row, because it does not vary between documents.

#### Scenario: The record accompanies the corpus
- **WHEN** the corpus is generated
- **THEN** a record states the generator version, the model, the prompt version and the instant
- **AND** it reports the counts by knowledge type and by claim scope

### Requirement: Knowledge retrieval quality is measured against a fixture, without the evaluation tables
The service MUST provide a reproducible measurement over a versioned fixture of questions: one per document, plus a group of out-of-domain questions whose expected result is no citation. It MUST report recall at three, mean reciprocal rank and the abstention rate, and MUST compare the vector-only configuration against the fused one. The measurement MUST NOT read or write the evaluation run, case and result tables, which belong to a later change. It MUST run offline, without calling an embedding or language model provider.

#### Scenario: The measurement runs offline and is reproducible
- **WHEN** the measurement runs over the fixture
- **THEN** it reports recall at three, mean reciprocal rank and the abstention rate
- **AND** no provider is called

#### Scenario: Out-of-domain questions are part of the measurement
- **WHEN** the measurement runs
- **THEN** the out-of-domain questions are scored as abstentions
- **AND** a returned citation for one of them counts as a failure

#### Scenario: The evaluation tables are untouched
- **WHEN** the measurement runs
- **THEN** no evaluation run, case or result row is read or written
