## MODIFIED Requirements

### Requirement: The HTTP application does not import the indexing library
`jbg_ai.api.main` MUST NOT import `jbg_ai.indexing`. Catalog index synchronisation MAY import the package from the index router. The source-text renderer and the embedding adapter MUST remain free of HTTP and SQL. `indexing/embeddings.py` MUST NOT be edited by the catalog indexer. Writing `ai.product_document`, adding the C13 Alembic revision, and regenerating `ai-service/openapi.json` are the catalog indexer's responsibility, not the source-text library's.

#### Scenario: The application factory stays decoupled from indexing
- **WHEN** `jbg_ai.api.main` is inspected
- **THEN** its source does not mention `jbg_ai.indexing`

#### Scenario: embeddings.py stays frozen
- **WHEN** the catalog indexer is implemented
- **THEN** `indexing/embeddings.py` is unchanged relative to the C11 freeze
- **AND** `build_source_text` / `hash_source_text` still have no HTTP or SQL dependency
