# product-document-indexer

## MODIFIED Requirements

### Requirement: The feed client is reusable and the catalog indexer does not drain POS
The indexing package MUST expose an injectable async catalog feed client that parses `kind` `upsert` | `tombstone`, maps camelCase upsert fields onto `ProductSourceText` plus `product_id`, `family_id`, `price`, `price_band`, `is_active` and `watermark`, and accepts a POS path/method. **The catalog sync** MUST NOT invoke the POS availability feed and MUST NOT write `ai.pos_projection`; draining that feed belongs to the separate POS drain defined by `pos-projection`, which keeps its own checkpoint and MUST NOT read or write the `catalog` checkpoint row. `indexing/embeddings.py` MUST NOT be modified. The catalog indexer MUST NOT open an EF Core migration, MUST NOT add a .NET client operation toward `/v1/index/sync`, and MUST NOT start a 5–10 minute scheduler. Python MUST NOT read or write schema `public` by SQL.

#### Scenario: POS feed is not called during catalog sync
- **GIVEN** a real catalog sync and an injected feed client that records calls
- **WHEN** the sync completes
- **THEN** only catalog pages were requested
- **AND** the POS method was not invoked
- **AND** `ai.pos_projection` is untouched by the catalog sync

#### Scenario: The two drains do not share a checkpoint
- **GIVEN** a stored `catalog` checkpoint row
- **WHEN** the POS drain runs to completion
- **THEN** the `catalog` checkpoint row is unchanged
- **AND** the POS cursor is stored under its own `feed` value

#### Scenario: embeddings.py stays frozen
- **WHEN** the change is implemented
- **THEN** `ai-service/src/jbg_ai/indexing/embeddings.py` has no diff against the C11 freeze
- **AND** `jbg_ai.api.main` source does not mention `jbg_ai.indexing`
