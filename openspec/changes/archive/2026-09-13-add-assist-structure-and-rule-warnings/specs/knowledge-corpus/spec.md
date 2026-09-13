## ADDED Requirements

### Requirement: Knowledge search can exclude named documents, and the caller states which

Knowledge search SHALL accept an optional set of documents to exclude, identified by the same deterministic document identity the indexer derives from the document slug. When the set is empty or absent, the search MUST behave exactly as before, so the parameter is additive and its rollback is passing nothing.

The exclusion MUST be applied in **both** branches of the search, so a fragment the vector branch was told to exclude cannot re-enter the answer through the lexical one.

The service MUST NOT decide the exclusion set itself from the wording of the question: deciding it is the caller's, for the same reason the caller states its intent.

#### Scenario: An excluded document contributes no fragment
- **GIVEN** a question whose best fragments live in a document named in the exclusion set
- **WHEN** the search runs with that set
- **THEN** no fragment of that document is returned

#### Scenario: The exclusion reaches the lexical branch too
- **GIVEN** a question that matches an excluded document lexically
- **WHEN** the search runs with that document excluded
- **THEN** no fragment of it is returned by either branch

#### Scenario: An empty exclusion set changes nothing
- **GIVEN** the same question searched twice
- **WHEN** one search passes no exclusion set and the other passes an empty one
- **THEN** both return the same fragments in the same order

#### Scenario: The exclusion is addressed by document identity
- **WHEN** an exclusion set is built for a document slug
- **THEN** it is expressed with the deterministic identity the indexer derives from that slug
- **AND** no new column and no schema change is required to apply it

### Requirement: A caller scoping a question to one piece excludes only the material sheets that piece does not declare

When a caller scopes a knowledge question to a concrete product, the exclusion set it builds SHALL contain the sheets of the canonical materials that the product does **not** declare, and **nothing else**. Every other document of the corpus MUST remain reachable.

Restricting the corpus to the declared materials' sheets alone MUST NOT be done: the topical, policy, size and stone documents are not specific to a material, and removing them would silence questions the corpus can answer, which is the more expensive failure.

Documents that share the material prefix but are not the sheet of a canonical material MUST remain reachable, because a question about hallmarks or about mixed pieces is answerable whatever the piece is made of.

#### Scenario: The sheet of an undeclared material is unreachable
- **GIVEN** a product declaring one canonical material
- **WHEN** a question about it is searched with the piece-scoped exclusion set
- **THEN** no fragment comes from the sheet of any other canonical material

#### Scenario: The declared material's own sheet stays reachable
- **GIVEN** a product declaring one canonical material
- **WHEN** a care question about that material is searched with the piece-scoped exclusion set
- **THEN** fragments of that material's sheet are returned normally

#### Scenario: The rest of the corpus stays reachable
- **GIVEN** a product declaring one canonical material
- **WHEN** a question is searched with the piece-scoped exclusion set
- **THEN** documents of the topical, policy, size and stone types are not excluded

#### Scenario: The prefixed documents that are not material sheets stay reachable
- **GIVEN** a product declaring one canonical material
- **WHEN** a question about hallmarks or about mixed pieces is searched with the piece-scoped exclusion set
- **THEN** the documents about hallmarks and about mixed pieces are not excluded

### Requirement: A fragment can be addressed directly by its citation identity, without searching

The service SHALL allow a caller to obtain fragments by addressing them directly with the deterministic chunk identity the indexer derives from the document and section slugs, without running any search and without calling an embedding provider.

An address that names a section a document does not have MUST return nothing for that address rather than failing the whole call, because the sheets of the corpus do not all carry the same sections and an absent section is normal.

A fragment obtained this way MUST carry the same citation fields as one obtained by searching, so a consumer cannot tell which path produced it and both are equally verifiable.

#### Scenario: An addressed fragment comes back with its full citation
- **WHEN** a fragment is addressed by its document and section slugs
- **THEN** it is returned with its citation identifier, its titles, its document type and its claim scope

#### Scenario: Addressing runs no search and no provider call
- **WHEN** fragments are addressed by identity
- **THEN** no vector search is performed
- **AND** no embedding provider call is made

#### Scenario: An absent section is not an error
- **GIVEN** a sheet that does not carry one of the addressed sections
- **WHEN** the set of addresses is resolved
- **THEN** the absent one yields no fragment
- **AND** the remaining addresses are resolved normally
