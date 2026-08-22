## ADDED Requirements

### Requirement: Synthetic corpus reaches hybrid volume without cloning the real catalog
The offline synthetic catalog CLI SHALL emit one JSONL record per generated product and no other products. Every record MUST set `data_origin` to `synthetic` and `text_provenance` to `synthetic`. Together with the 436-line C06a corpus, the hybrid catalog MUST approach ~1.200 total products; the exact count is a documented slack, not an exact acceptance threshold. No synthetic SKU MUST appear in the C06a JSONL or twice in the synthetic JSONL.

#### Scenario: Hybrid volume is documented with slack
- **GIVEN** the committed C06a JSONL with 436 SKUs and `data_origin` equal to `real`
- **WHEN** synthetic generation completes
- **THEN** the synthetic JSONL product count plus 436 approaches 1.200
- **AND** the sidecar records `product_count` and the slack versus that target
- **AND** every synthetic line is a JSON object with `data_origin` equal to `synthetic`
- **AND** every synthetic line has `text_provenance` equal to `synthetic`

#### Scenario: Synthetic SKUs do not collide with the real corpus
- **GIVEN** the C06a JSONL SKU set and a generated synthetic JSONL
- **WHEN** SKUs are compared
- **THEN** the two sets are disjoint
- **AND** each synthetic SKU appears exactly once

### Requirement: SKUs follow the real numbering scheme and do not leak origin
The allocator MUST assign SKUs as the literal `SKU` plus 2 digits when n < 100 (`SKU01`…`SKU99`), 3 digits when n < 1000, and 4 digits from 1000. The numeric sequence MUST start after 436 (`SKU437`, …). The allocator MUST NOT use prefixes such as `SYN-` or `JB-S-` that do not exist on the real anchor. The same `seed` MUST yield the same reserved SKU sequence. The LLM MUST NOT invent SKUs.

#### Scenario: Reserved SKUs continue after 436 with magnitude padding
- **GIVEN** the real catalog ends at numeric SKU 436
- **WHEN** the allocator reserves the next identifiers
- **THEN** the first reserved SKU is `SKU437`
- **AND** values below 1000 use 3 digits
- **AND** values at or above 1000 use 4 digits

#### Scenario: SKUs do not carry a synthetic prefix
- **GIVEN** a reserved SKU list
- **WHEN** each identifier is inspected
- **THEN** it matches `SKU` plus 2, 3 or 4 digits
- **AND** it does not start with `SYN-`, `JB-S-`, or any prefix absent from the C06a corpus

#### Scenario: Allocator is deterministic for the same seed
- **GIVEN** a fixed seed and the C06a SKU set
- **WHEN** allocation runs twice
- **THEN** the reserved SKU sequences are identical

### Requirement: New collections use design names, not channel names
The generator MUST create 8–12 new collections whose names evoke piece design, not a sales channel or POS. Collection names MUST be unique against the C06a JSONL and against existing `"Collections"` rows. Synthetic products MUST NOT point at a collection that already exists on the real catalog. Hotel, airport, tourist and atelier MAY appear only as generation brief or report metadata, never as `Collection.Name`.

#### Scenario: Collection names do not collide with the real catalog
- **GIVEN** the 28 C06a collection names and a generated synthetic JSONL
- **WHEN** synthetic `collection_name` values are compared
- **THEN** none equals a C06a collection name
- **AND** the number of distinct synthetic collection names is between 8 and 12 inclusive

#### Scenario: Collection names are not channel or POS labels
- **GIVEN** the generated collection names
- **WHEN** they are inspected
- **THEN** none is Hotel, Aeropuerto, Turista, Atelier, or a synonym of those channel labels
- **AND** the report MAY list a thought audience or POS per collection as metadata separate from the name

#### Scenario: Synthetic products do not reuse a real collection
- **GIVEN** a generated synthetic JSONL
- **WHEN** each line's `collection_name` is read
- **THEN** it is one of the new design collections
- **AND** it is not a collection already present in the C06a JSONL

### Requirement: JSONL omits family, materials list and product_id
Every synthetic JSONL line MUST contain `sku`, `name`, `description`, `price`, `collection_name`, `data_origin`, `text_provenance` and `text_quality_tier`. The line MUST NOT contain `variant_group_key`, `variant_label`, `family_seed`, `materials`, or `product_id`. Local ingest MUST NOT insert rows into `"ProductFamilies"` or `"ProductFamilyMembers"`. An ingested synthetic SKU MUST remain an orphan: a family GET for that product MUST return 204, not 404.

#### Scenario: JSONL does not emit family or extraction fields
- **GIVEN** a generated synthetic JSONL
- **WHEN** any line is parsed
- **THEN** it does not contain `variant_group_key`
- **AND** it does not contain `variant_label`
- **AND** it does not contain `family_seed`
- **AND** it does not contain `materials`
- **AND** it does not contain `product_id`

#### Scenario: Ingest does not write family tables
- **GIVEN** a successful local ingest of the synthetic JSONL
- **WHEN** `"ProductFamilies"` and `"ProductFamilyMembers"` are counted
- **THEN** this change inserted zero rows in either table

#### Scenario: Ingested synthetic products are orphans
- **GIVEN** a synthetic SKU ingested into `public."Products"`
- **WHEN** a family GET is issued for that product
- **THEN** the response is 204
- **AND** the response is not 404

### Requirement: Quality tiers are assigned per name stem
The pipeline MUST assign `text_quality_tier` (`rich` | `sparse` | `short`) by the stem of `Name` (size siblings such as S and M), not by piece type and not per lone product when siblings share a stem. Every member of a stem group MUST share the same tier. The identifier `empty` MUST NOT be used. Global product ratios MUST fall within ~70 % / ~20 % / ~10 % (`rich` / `sparse` / `short`) with a tolerance of ±5 percentage points. All three tiers MUST carry `text_provenance` equal to `synthetic`.

#### Scenario: Name-stem siblings do not mix tiers
- **GIVEN** two synthetic products that share a `Name` stem and differ by a size suffix
- **WHEN** quality assignment completes
- **THEN** both records carry the same `text_quality_tier`

#### Scenario: Product-level ratios stay inside slack
- **GIVEN** a generated synthetic JSONL
- **WHEN** products are counted by `text_quality_tier`
- **THEN** `rich` is between 65 % and 75 %
- **AND** `sparse` is between 15 % and 25 %
- **AND** `short` is between 5 % and 15 %

#### Scenario: Fixture stem group shares a single tier
- **GIVEN** a fixture of three products that the stem step places in one group
- **WHEN** quality assignment runs with a fixed seed
- **THEN** the three records carry the same `text_quality_tier`

#### Scenario: Tiers are deterministic for a fixed seed
- **GIVEN** a fixture of names and seed `20260822`
- **WHEN** stem grouping and quality assignment run twice
- **THEN** `text_quality_tier` per SKU is identical in both outputs

### Requirement: Generated copy is imaginative jewelry within validation bounds
Names and descriptions MUST read as jewelry a maker could sell, not as the C06a `assist.py` template. About one third of descriptions MUST name two or more materials in the prose. The JSONL MUST NOT carry a `materials` array. Descriptions MUST NOT exceed 1000 characters. Price MUST be greater than 0, fit `decimal(18,2)`, and be strictly less than 50.000. Validation MUST reject overlong copy and prices at or above 50.000 before ingest.

#### Scenario: Copy is not the C06a assist template
- **GIVEN** generated synthetic descriptions
- **WHEN** report samples are reviewed
- **THEN** they do not follow the mold "El anillo con X, en talla Y, en plata de ley…"
- **AND** they read as invented jewelry copy

#### Scenario: Multi-material mention appears in prose only
- **GIVEN** a generated synthetic JSONL
- **WHEN** descriptions are scanned for material mentions
- **THEN** about 35 % name two or more materials in the prose
- **AND** no line contains a `materials` array

#### Scenario: Overlong copy is rejected before ingest
- **GIVEN** a JSONL line whose `description` is longer than 1000 characters
- **WHEN** validation or ingest runs
- **THEN** the run fails
- **AND** no `INSERT` from that run is committed

#### Scenario: Price at or above 50000 is rejected
- **GIVEN** a JSONL line whose `price` is 50000 or greater
- **WHEN** validation or ingest runs
- **THEN** the run fails
- **AND** no `INSERT` from that run is committed

#### Scenario: Valid price is stored as a decimal string
- **GIVEN** a generated line with a reasoned price
- **WHEN** the line is validated
- **THEN** `price` is greater than 0
- **AND** it fits `decimal(18,2)`
- **AND** it is strictly less than 50000

### Requirement: Local ingest inserts new collections and products without touching the real anchor
Against the local Docker PostgreSQL (host port 5433, database `joiabagur_pv`), ingest MUST `INSERT` the new collections and the new products with `IsActive` equal to true inside a single transaction. It MUST NOT `UPDATE` rows whose SKU appears in the C06a JSONL. PostgreSQL MUST assign each new product `Id`; the JSONL MUST NOT be rewritten with that UUID. A colliding synthetic SKU or collection name MUST abort the transaction with no partial inserts. The CLI MUST use `JPV_PG*` environment settings, not committed secrets. This change MUST NOT target RDS or any production database.

#### Scenario: New collections and products are inserted
- **GIVEN** local Docker has the 436 C06a products
- **WHEN** ingest of the synthetic JSONL succeeds
- **THEN** the new collections exist in `"Collections"`
- **AND** the new products exist in `"Products"` with `IsActive` true
- **AND** each new product `Id` was assigned by PostgreSQL

#### Scenario: Real rows are unchanged
- **GIVEN** a pre-ingest snapshot of the 436 real products
- **WHEN** ingest succeeds
- **THEN** the real row count, SKUs, prices and names equal the snapshot

#### Scenario: Collision rolls back the whole transaction
- **GIVEN** a synthetic SKU that already exists in `"Products"`, or a collection name that already exists in `"Collections"`
- **WHEN** ingest runs
- **THEN** the transaction is rolled back
- **AND** no collection or product from that run remains committed

#### Scenario: JSONL is not rewritten with product_id
- **GIVEN** a successful ingest
- **WHEN** the synthetic JSONL is read afterwards
- **THEN** no line gained a `product_id`
- **AND** the file content is unchanged by ingest

### Requirement: Committed corpus is versioned with sidecar traceability
`data/catalog/synthetic/generated/catalog-synthetic.jsonl` MUST be tracked in git. `.gitignore` MUST allow `data/catalog/synthetic/generated/` without un-ignoring unrelated files under `data/catalog/synthetic/`. The sidecar MUST include `generator_version`, `seed`, `model` (OpenAI provider and model id), `prompt_version` and `generated_at`. Regenerating descriptions MUST require an explicit flag; without it the committed text MUST NOT be overwritten.

#### Scenario: Git tracks the synthetic derived corpus
- **GIVEN** a completed generation
- **WHEN** `git status` and `.gitignore` are inspected
- **THEN** `catalog-synthetic.jsonl` is not ignored
- **AND** the ignore exception is limited to `data/catalog/synthetic/generated/`

#### Scenario: Sidecar carries OpenAI traceability fields
- **GIVEN** a completed generation
- **WHEN** the `.meta.json` sidecar is read
- **THEN** it contains `generator_version`, `seed`, `model`, `prompt_version` and `generated_at`
- **AND** it contains product counts or ratios for `rich`, `sparse` and `short`

#### Scenario: Regeneration requires an explicit flag
- **GIVEN** a committed synthetic JSONL
- **WHEN** generate runs without `--regenerate-text`
- **THEN** the committed descriptions are left unchanged

### Requirement: The HTTP service does not import the data package or require LLM keys
`jbg_ai.api.main` MUST NOT import `jbg_ai.data`. `GET /health` MUST start without `LLM_*` or `OPENAI_*` settings. `ai-service/openapi.json` MUST remain unchanged. The generator unit suite MUST NOT open sockets to LLM providers.

#### Scenario: API factory does not import the data package
- **GIVEN** this change is implemented
- **WHEN** `jbg_ai.api.main` is inspected
- **THEN** it does not import `jbg_ai.data`

#### Scenario: Health boots without an LLM key
- **GIVEN** `APP_ENV`, `SERVICE_VERSION` and `JWT_SECRET` are set
- **AND** `LLM_*` and `OPENAI_*` are omitted
- **WHEN** settings load and `GET /health` is called
- **THEN** settings load successfully
- **AND** the response status is 200

#### Scenario: OpenAPI snapshot stays still
- **GIVEN** the change is implemented
- **WHEN** `ai-service/openapi.json` is compared to the pre-change snapshot
- **THEN** the file is unmodified

#### Scenario: Unit suite makes no provider calls
- **GIVEN** the generator unit tests
- **WHEN** the suite runs
- **THEN** no test opens a network socket to an LLM provider

### Requirement: This change does not add API surface, family writes or provenance columns
This change MUST NOT add a generation HTTP endpoint or modify backend or frontend APIs. It MUST NOT implement C09, C10 or C18. It MUST NOT add an Alembic revision for `text_provenance` or a provenance or channel column on `Product`. It MUST NOT write `text_provenance` onto `public."Products"` or onto `ai.product_document`.

#### Scenario: No generation endpoint is added
- **GIVEN** the change is implemented
- **WHEN** FastAPI routes and the .NET API surface are inspected
- **THEN** no generation endpoint was added
- **AND** backend and frontend API code is unmodified by this change

#### Scenario: Provenance stays off Products and ai.product_document
- **GIVEN** a completed local ingest
- **WHEN** the columns of `public."Products"` and `ai.product_document` are inspected
- **THEN** no `text_provenance` column exists on either
- **AND** no Alembic revision added by this change introduces `text_provenance`

#### Scenario: C09 C10 and C18 remain out of scope
- **GIVEN** the change is implemented
- **WHEN** the deliverable is reviewed
- **THEN** there is no catalog extractor, no POS/sales simulator, and no family proposal flow
