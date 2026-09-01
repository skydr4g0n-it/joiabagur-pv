# query-expansion Specification

## Purpose
Query-time synonym expansion for the retrieval pipeline: a pure function that returns equivalence groups of surface forms plus what it resolved, never a rewritten query string and never `tsquery` syntax. The dictionary is two layers — the enrichment closed vocabularies read as base equivalence classes and never modified, plus a query-only overlay versioned in the repository — with folded matching and surface-form emission, plural reduction, longest-phrase-first matching, directional bridges between vocabularies and unknown-term pass-through. `JPV_QUERY_EXPANSION_ENABLED` supplies only the default; the effective flag travels as a parameter of the orchestration call and is not part of the request schema. `stage=expand` logs beside embed and search, and the result is not consumed until the lexical branch of C21, so the HTTP response is unchanged. Entries and exclusions are justified against the corpus, and a CLI command writes a versioned reach report. No PostgreSQL extension, no text-search configuration, no re-indexing, no OpenAPI regeneration.

## Requirements

### Requirement: Query expansion is a pure function returning equivalence groups
The service MUST expose a query expansion function that takes the operator query text and an enable flag and returns a structure carrying three things: the `original` text unchanged, `groups` — one list of surface forms per query token, in the order the tokens appear — and `matched` — one entry per resolved token as `(typed term, vocabulary field, canonical term)`. It MUST NOT return a rewritten query string, MUST NOT build or return PostgreSQL `tsquery` syntax, and MUST NOT decide the boolean structure of any search: composing groups into a query is the consumer's responsibility. The function MUST be pure: it MUST NOT open a database session, MUST NOT call an embedding or LLM provider, and MUST NOT open a socket.

#### Scenario: A known term expands to its class and reports what it resolved to
- **GIVEN** the dictionary is loaded and expansion is enabled
- **WHEN** the query `sortija de plata` is expanded
- **THEN** one group contains both the typed form `sortija` and the canonical `anillo`
- **AND** another group contains `plata`
- **AND** `matched` contains an entry mapping `sortija` to the `piece_type` field and the canonical `anillo`
- **AND** `original` equals the query text unchanged

#### Scenario: The output is groups, not a rewritten query
- **GIVEN** expansion is enabled
- **WHEN** any query is expanded
- **THEN** the result exposes a list of groups of surface forms
- **AND** the result contains no rewritten query string built by joining terms
- **AND** the result contains no `tsquery` operator characters produced by this function

#### Scenario: Expansion performs no input or output
- **WHEN** the expansion function runs in the unit test suite
- **THEN** no database session is opened
- **AND** no embedding or LLM provider is called
- **AND** no socket is opened

### Requirement: The dictionary is layered over the enrichment vocabulary without modifying it
The dictionary MUST be built from two sources: the closed vocabularies of the enrichment pipeline, read as base equivalence classes, and a query-only overlay file versioned in the repository. The enrichment vocabulary file MUST NOT be modified by this capability. The overlay MAY add surface forms to an existing base class. Every overlay anchor MUST name a canonical the base already defines — a term the base does not know is a vocabulary gap and not a synonym — and the overlay MUST NOT reassign a term that the base already maps to a canonical. Both MUST fail at load time, naming the offending term. The dictionary MUST be loaded once per process and cached.

#### Scenario: The base vocabulary file is not modified
- **WHEN** the change is applied
- **THEN** the enrichment closed-vocabulary file has no diff
- **AND** no product is re-enriched and no prompt version is bumped

#### Scenario: A base class reaches expansion without being restated in the overlay
- **GIVEN** the enrichment vocabulary maps `gargantilla` to the canonical `collar`
- **AND** the overlay does not restate that mapping
- **WHEN** the query `gargantilla` is expanded
- **THEN** the group contains both `gargantilla` and `collar`

#### Scenario: The overlay cannot reassign a base canonical
- **GIVEN** the base maps a term to a canonical
- **WHEN** the overlay declares a different canonical for that same term
- **THEN** loading the dictionary fails with an error naming the conflicting term
- **AND** the base mapping is not silently replaced

### Requirement: Matching folds the query while emission preserves indexed surface forms
Term lookup MUST be performed on folded text — lowercased, accent-stripped, with `ñ` reduced — so that a query typed without diacritics resolves. The forms emitted in a group MUST be surface forms as they appear in the indexed documents, with their diacritics intact, because the Spanish text-search configuration folds acute accents but does not fold `ñ`. The folded phrase list of the enrichment vocabulary MUST NOT be used as the emission source.

#### Scenario: A query typed without the enye reaches the accented indexed form
- **GIVEN** the indexed documents contain the material `baño de oro`
- **WHEN** the query `bano de oro` is expanded
- **THEN** the group contains the accented form `baño de oro`
- **AND** the group is not limited to the unaccented form the operator typed

#### Scenario: Both legitimate size forms are emitted
- **GIVEN** the corpus uses `pequeño` in prose and `pequeno` in the canonical size line
- **WHEN** the query `pequeño` is expanded
- **THEN** the group contains both `pequeño` and `pequeno`
- **AND** neither form is dropped in favour of the other

### Requirement: Stemmer-split terms are expanded as dictionary content
A query term whose Spanish stem does not match the stem of its own canonical form MUST still produce a group containing both surface forms, because the text-search configuration cannot relate them. Whether that comes from an overlay entry or from the plural reduction below is an implementation detail; the emitted group is what matters. This MUST cover at least the singular and plural of the piece types whose stems diverge, and the unaccented spellings of canonical terms containing `ñ`. The capability MUST NOT install a PostgreSQL extension and MUST NOT create or alter a text-search configuration to solve this.

#### Scenario: A plural whose stem diverges from its singular is expanded
- **GIVEN** the Spanish configuration stems `collar` and `collares` to different lexemes
- **WHEN** the query `collares de plata` is expanded
- **THEN** the first group contains both `collares` and `collar`

#### Scenario: No extension or text-search configuration is introduced
- **WHEN** the change is applied
- **THEN** no PostgreSQL extension is installed
- **AND** no custom text-search configuration is created
- **AND** the generated document vector column and its index are not rebuilt

### Requirement: Bridges between vocabularies are directional
The overlay MAY declare that one equivalence class is widened with the surface forms of another. Such a bridge MUST apply in the declared direction only and MUST NOT be inferred symmetrically. Donations MUST be taken from the classes as they stood before any bridge was applied, so that a direction cannot leak transitively through a second bridge.

#### Scenario: The colour reaches solid gold and the plating does not
- **GIVEN** the overlay widens the gold colour with the plating and the solid metal
- **AND** it widens the plating with the colour only
- **WHEN** the query `dorado` is expanded
- **THEN** the group contains the plating and the solid metal
- **WHEN** the query `baño de oro` is expanded
- **THEN** the group contains the colour
- **AND** the group does not contain the solid metal

#### Scenario: Direction does not leak through a second bridge
- **GIVEN** one bridge widens the colour towards the solid metal
- **AND** a second bridge widens the plating towards the colour
- **WHEN** the query naming the plating is expanded
- **THEN** the group does not contain the solid metal

### Requirement: Inflections resolve without one entry per form and the longest phrase wins
The dictionary loader MUST reduce plural forms on both the dictionary keys and the query tokens, and MUST apply the reduction only when the reduced form already exists in the dictionary, so that no canonical is invented for an unknown word. When more than one dictionary entry matches at a position, the entry spanning the most words MUST win.

#### Scenario: A plural resolves with no dedicated entry
- **GIVEN** the overlay contains no entry for `gargantillas`
- **WHEN** the query `gargantillas doradas` is expanded
- **THEN** the first group contains the canonical `collar`

#### Scenario: The longer phrase wins over a shorter token inside it
- **GIVEN** the dictionary maps `aro` to `pendientes` and `aro de dedo` to `anillo`
- **WHEN** the query `aro de dedo de plata` is expanded
- **THEN** the group contains the canonical `anillo`
- **AND** the canonical `pendientes` is not present

### Requirement: Unknown terms pass through unchanged
A token the dictionary does not recognise MUST be emitted as a group containing exactly that token in the form the operator typed. The function MUST NOT drop unknown tokens, MUST NOT guess a canonical for them, and MUST NOT fail.

#### Scenario: An unknown proper noun survives beside a known term
- **WHEN** the query `anillo Ses Salines` is expanded
- **THEN** `Ses` and `Salines` are each a group of one element with the typed form
- **AND** the group for `anillo` carries its class
- **AND** `matched` contains no entry for the unknown tokens

### Requirement: The enable flag turns expansion off without changing the response
Expansion MUST be controlled by a flag whose default is supplied by settings and whose effective value is passed as a parameter of the retrieval orchestration call, so that a caller can evaluate several configurations in one process. The flag MUST NOT be added to the retrieval request schema. When expansion is disabled every token MUST become a single-element group carrying its original form, `matched` MUST be empty, and the HTTP response of the retrieval endpoint MUST be unchanged.

#### Scenario: Disabled expansion yields the original tokens
- **GIVEN** the expansion flag is disabled
- **WHEN** a query containing a known synonym is expanded
- **THEN** every group has exactly one element equal to the typed token
- **AND** `matched` is empty

#### Scenario: The flag is not part of the request contract
- **WHEN** the change is applied
- **THEN** the retrieval request schema has no expansion field
- **AND** the committed OpenAPI snapshot is not regenerated

#### Scenario: Two configurations run in one process
- **GIVEN** the settings default enables expansion
- **WHEN** the orchestration call is made once with expansion enabled and once disabled
- **THEN** both calls succeed without restarting the process
- **AND** neither call mutates the settings object

### Requirement: Expansion applies at query time only and never reaches indexing or the vector query
Expansion MUST NOT modify any indexed document: document text, its generated search vector and its source hash MUST be identical before and after this change, and no document may be re-indexed. The embedding used by the vector branch MUST be computed on the original query text, not on any expanded form.

#### Scenario: Indexed documents are untouched
- **WHEN** the change is applied
- **THEN** no row of the product document table has a changed document text, search vector or source hash
- **AND** no re-indexing run is required to deploy the change

#### Scenario: The vector branch embeds the original text
- **GIVEN** expansion is enabled and the query contains a known synonym
- **WHEN** the retrieval pipeline runs
- **THEN** exactly one embedding is requested
- **AND** the embedded text is the original query, not an expanded form

### Requirement: Expansion emits a stage log and is not consumed until the lexical branch exists
The retrieval pipeline MUST emit a structured log entry for the expansion stage alongside the existing embed and search stages, carrying the request trace identifier, whether expansion was enabled, the token count and the number of resolved terms. The operator query MUST be logged only at Debug level, and the full expanded classes MUST NOT be logged at Information level. Until the lexical branch exists, the expansion result MUST NOT alter the retrieval response in any way.

#### Scenario: The expansion stage is traceable
- **GIVEN** a request whose token carries a trace identifier
- **WHEN** the real retrieval pipeline runs
- **THEN** a structured log entry for the expansion stage carries that trace identifier
- **AND** it reports whether expansion was enabled and how many terms resolved

#### Scenario: The response is unchanged while no consumer exists
- **GIVEN** expansion is enabled
- **WHEN** an authenticated client calls the retrieval endpoint
- **THEN** the response body is the same as it would be with expansion disabled
- **AND** the match reasons of each result are unchanged

### Requirement: Dictionary entries and exclusions are justified against the corpus
Every overlay entry MUST be accompanied in the file by the reason it exists. Terms measured to be false friends, terms that are vocabulary gaps rather than synonyms, and terms that already reach their documents without expansion MUST be recorded as explicit exclusions with their reason, so a later editor sees the rule where the temptation is.

#### Scenario: A measured false friend is absent from the dictionary
- **WHEN** the dictionary is loaded
- **THEN** no class for the leather material contains the term `piel`
- **AND** the overlay records that exclusion together with its reason

#### Scenario: Vocabulary gaps are not smuggled in as synonyms
- **WHEN** the dictionary is loaded
- **THEN** it contains no class introducing a piece type absent from the enrichment vocabulary
- **AND** those terms are recorded as belonging to the vocabulary-gap change

### Requirement: A measurement command produces a versioned report of the dictionary reach
The service MUST provide a command-line entry point that measures, against the live index, how many documents a curated list of operator queries reaches with and without expansion, and how many documents each overlay entry gains. It MUST write a versioned report into the repository. It MUST NOT be part of the unit test suite, MUST skip cleanly rather than fail when no database is reachable, and MUST NOT write to the database.

#### Scenario: The report is produced and versioned
- **GIVEN** the index is reachable
- **WHEN** the measurement command runs
- **THEN** it writes a report file into the repository
- **AND** the report states, per query, the document count with and without expansion

#### Scenario: No database means a skip, not a failure
- **GIVEN** no database is reachable
- **WHEN** the measurement command runs
- **THEN** it reports that it is skipping and exits without error
- **AND** no unit test depends on the index containing any particular number of rows
