## ADDED Requirements

### Requirement: Corpus contains exactly the real catalog products
The offline catalog pipeline SHALL emit one JSONL record per product in the anonymised export and no other products. Every record MUST set `data_origin` to `real`. Each SKU from the export MUST appear exactly once. The committed corpus file MUST contain 436 lines when built from the 436-row export.

#### Scenario: JSONL matches the export cardinality
- **GIVEN** the anonymised xlsx export with 436 product rows
- **WHEN** corpus generation completes
- **THEN** `catalog-real-enriched.jsonl` contains 436 lines
- **AND** each line is a JSON object with `data_origin` equal to `real`
- **AND** each SKU from the xlsx appears exactly once

#### Scenario: Fixture generation does not invent SKUs
- **GIVEN** a fixture export with N product rows
- **WHEN** corpus generation runs against that fixture
- **THEN** the JSONL contains N lines
- **AND** the set of SKUs equals the set of SKUs in the fixture

### Requirement: Product identity fields are immutable
SKU, name, price and collection in the JSONL MUST match the export row for that SKU. Local ingestion into `public."Products"` MUST NOT change `Id`, `SKU`, `Name`, `Price` or `CollectionId`. Assisted text MAY replace only `Description` (and MAY bump `UpdatedAt`).

#### Scenario: JSONL identity matches the xlsx
- **GIVEN** an export row with SKU, Name, Description, Price and Collection
- **WHEN** the corresponding JSONL line is compared to that row
- **THEN** `sku`, `name`, `price` and `collection_name` equal the export values
- **AND** a difference in `description` does not fail this comparison

#### Scenario: Ingest leaves identity columns unchanged
- **GIVEN** a `public."Products"` row whose SKU exists in the JSONL
- **WHEN** the ingest script updates that row
- **THEN** `Id`, `SKU`, `Name`, `Price` and `CollectionId` equal their pre-update values
- **AND** `Description` equals the JSONL `description` for that SKU

#### Scenario: Ingest aborts when an identity invariant would break
- **GIVEN** an ingest run inside a single transaction
- **WHEN** a post-update read shows `Name`, `Price`, `CollectionId`, `SKU` or `Id` differing from the pre-update snapshot
- **THEN** the transaction is rolled back
- **AND** no product description from that run remains committed

### Requirement: Quality tiers are assigned per variant family
The pipeline MUST assign `text_quality_tier` (`rich` | `sparse` | `empty`) to each `variant_group_key`, not to a lone product and not by piece type. Every member of a group MUST share the same tier. Global product ratios MUST fall within 70 % / 20 % / 10 % with a tolerance of ±3 percentage points when measured on the 436-product corpus.

#### Scenario: A variant group does not mix tiers
- **GIVEN** a generated JSONL
- **WHEN** records are grouped by `variant_group_key`
- **THEN** no group contains two distinct `text_quality_tier` values

#### Scenario: Product-level ratios stay inside tolerance
- **GIVEN** the 436-product committed corpus
- **WHEN** products are counted by `text_quality_tier`
- **THEN** `rich` is between 67 % and 73 %
- **AND** `sparse` is between 17 % and 23 %
- **AND** `empty` is between 7 % and 13 %

#### Scenario: Fixture family shares a single tier
- **GIVEN** a fixture of three products that the grouping step places in one `variant_group_key`
- **WHEN** quality assignment runs with a fixed seed
- **THEN** the three records carry the same `text_quality_tier`

### Requirement: Text provenance matches the quality tier
Records with `text_quality_tier` `rich` or `sparse` MUST set `text_provenance` to `ai_assisted`. Records with `text_quality_tier` `empty` MUST set `text_provenance` to `merchant` and MUST have an empty or null `description`. The pipeline MUST NOT write `text_provenance` onto `public."Products"` or onto `ai.product_document`.

#### Scenario: Assisted tiers carry ai_assisted provenance
- **GIVEN** a generated JSONL
- **WHEN** records with `text_quality_tier` `rich` or `sparse` are selected
- **THEN** each has `text_provenance` equal to `ai_assisted`
- **AND** each has a non-empty `description`

#### Scenario: Empty tier carries merchant provenance and no copy
- **GIVEN** a generated JSONL
- **WHEN** records with `text_quality_tier` `empty` are selected
- **THEN** each has `text_provenance` equal to `merchant`
- **AND** each has `description` equal to `null` or an empty string

#### Scenario: Provenance is absent from the Products table
- **GIVEN** a completed local ingest
- **WHEN** the columns of `public."Products"` are inspected
- **THEN** no `text_provenance` column exists
- **AND** no other provenance column was added by this change

### Requirement: Variant grouping is emitted as a seed for families
Every JSONL record MUST include `variant_group_key`. Multi-member groups MUST include a `variant_label` on each member when a suffix was detected. Every record MUST include `family_seed` with `group_key` and the complete `member_skus` list for that group. The enrichment report MUST document the observed group count and multi-variant count. Those counts MUST NOT be required to equal any exploration reference.

#### Scenario: Each product carries family seed metadata
- **GIVEN** a generated JSONL
- **WHEN** any line is read
- **THEN** it contains `variant_group_key`
- **AND** it contains `family_seed.group_key` equal to `variant_group_key`
- **AND** `family_seed.member_skus` lists every SKU that shares that group key

#### Scenario: Multi-variant members expose a label
- **GIVEN** two fixture products whose normalised names share a stem and differ by a size suffix
- **WHEN** grouping runs
- **THEN** they share one `variant_group_key`
- **AND** each has a `variant_label` derived from its suffix

#### Scenario: Report records grouping counts without a numeric gate
- **GIVEN** generation has finished
- **WHEN** the enrichment report is read
- **THEN** it states the number of variant groups and the number of multi-member groups
- **AND** it does not treat an exploration reference of ~403 / ~23 as a pass/fail threshold

### Requirement: Assisted copy respects the multimodal limitation
Assisted descriptions MUST expand only evidence present in the original name or description. They MUST NOT assert stone counts, verified finishes, or visual details that require a photograph. Descriptions MUST NOT exceed 1000 characters. The enrichment report MUST include at least five `rich`, three `sparse` and two `empty` before/after samples and MUST declare that multimodal recognition is simulated.

#### Scenario: Report samples cover all three tiers
- **GIVEN** the committed corpus and its report
- **WHEN** the report is reviewed
- **THEN** it includes at least five rich, three sparse and two empty samples with original and assisted text
- **AND** it states that there are no product photos and that non-derivable attributes are plausible, not verified

#### Scenario: Overlong copy is rejected before ingest
- **GIVEN** a JSONL line whose `description` is longer than 1000 characters
- **WHEN** validation or ingest runs
- **THEN** the run fails
- **AND** no `UPDATE` from that run is committed

#### Scenario: Empty tier is not filled to look complete
- **GIVEN** a product assigned `text_quality_tier` `empty`
- **WHEN** assisted copy is applied
- **THEN** its `description` remains empty or null

### Requirement: Grouping and tiers are deterministic for a fixed seed
The same export, the same grouping rules, the same `generator_version` and the same `seed` MUST produce the same `variant_group_key` assignments and the same `text_quality_tier` per group. The sidecar MUST record `generator_version`, `seed`, `generated_at`, product ratios by tier and by `text_provenance`, and grouping counts.

#### Scenario: Rerunning assignment with the same seed repeats tiers
- **GIVEN** a fixture export and seed `20260822`
- **WHEN** grouping and quality assignment run twice
- **THEN** `variant_group_key` and `text_quality_tier` per SKU are identical in both outputs

#### Scenario: A different seed may change tier assignment
- **GIVEN** a fixture export
- **WHEN** quality assignment runs with two distinct seeds
- **THEN** the per-SKU `text_quality_tier` map is allowed to differ
- **AND** no `variant_group_key` mixes tiers in either run

#### Scenario: Sidecar carries traceability fields
- **GIVEN** a completed generation
- **WHEN** the `.meta.json` sidecar is read
- **THEN** it contains `generator_version`, `seed` and `generated_at`
- **AND** it contains product counts or ratios for `rich`, `sparse` and `empty`
- **AND** it contains product counts or ratios for `ai_assisted` and `merchant`

### Requirement: Local ingest updates Description by SKU only
Against the local Docker PostgreSQL (host port 5433, database `joiabagur_pv`), the ingest script MUST match JSONL `sku` to `public."Products"."SKU"` and MUST update only `Description` and `UpdatedAt`. SKUs present in the JSONL and absent from the table MUST be listed as unmatched in the enrichment report and MUST NOT be inserted. The script MUST use connection settings from the environment, not from committed secrets. This change MUST NOT target RDS or any production database.

#### Scenario: Matching SKUs receive the new description
- **GIVEN** local `public."Products"` rows whose SKUs exist in the JSONL
- **WHEN** ingest runs successfully
- **THEN** each matching row has `Description` equal to the JSONL description
- **AND** unmatched JSONL SKUs are listed in the enrichment report
- **AND** no new `Products` row was inserted for an unmatched SKU

#### Scenario: Ingest is a no-insert operation
- **GIVEN** a JSONL SKU that does not exist in `public."Products"`
- **WHEN** ingest runs
- **THEN** the table row count is unchanged
- **AND** the SKU appears in the unmatched list

### Requirement: Generated corpus is versioned; raw export is not
`data/catalog/real/generated/catalog-real-enriched.jsonl` MUST be tracked in git. The raw xlsx under `data/catalog/real/` MUST remain gitignored. `.gitignore` MUST allow the `generated/` directory without un-ignoring the xlsx. `product_id` in the JSONL is optional and, when present, MUST come from a SKU lookup against `public."Products"`, not from the xlsx.

#### Scenario: Git tracks the derived corpus only
- **GIVEN** a completed generation
- **WHEN** `git status` and `.gitignore` are inspected
- **THEN** `catalog-real-enriched.jsonl` is not ignored
- **AND** `product-JoiaBagur.xlsx` remains ignored

#### Scenario: product_id is optional and not taken from the xlsx
- **GIVEN** the xlsx has no UUID column
- **WHEN** a JSONL line is produced without a database lookup
- **THEN** the line is valid without `product_id`
- **AND** when a post-ingest lookup runs, `product_id` equals `public."Products"."Id"` for that SKU

### Requirement: This change does not add runtime LLM, schema provenance or API surface
This change MUST NOT add an LLM client or `LLM_*` settings to `ai-service`. It MUST NOT add an Alembic revision for `text_provenance`. It MUST NOT modify `ai-service/openapi.json`, backend HTTP APIs, the `Product` entity shape, or the frontend. Structured AI profiles (`ProductAiProfile`) and synthetic catalog expansion remain out of scope.

#### Scenario: OpenAPI snapshot stays still
- **GIVEN** the change is implemented
- **WHEN** `ai-service/openapi.json` is compared to the pre-change snapshot
- **THEN** the file is unmodified

#### Scenario: No LLM client is introduced
- **GIVEN** the change is implemented
- **WHEN** `ai-service/pyproject.toml` is inspected for this change
- **THEN** no LLM provider client was added
- **AND** no `LLM_*` setting was added to the service configuration

#### Scenario: No Alembic provenance migration in this change
- **GIVEN** the change is implemented
- **WHEN** `ai-service/migrations/` is inspected
- **THEN** no revision added by this change introduces `text_provenance`
