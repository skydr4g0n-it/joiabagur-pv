# real-catalog-corpus Specification

## Purpose
Offline pipeline that turns the shop's anonymised product export into a versioned JSONL corpus of 436 real SKUs, with dual provenance (`data_origin` and `text_provenance`), quality tiers assigned per internal variant family, salesperson-style assisted copy on `rich` and `sparse` only, and a local ingest that updates `public."Products"."Description"` by SKU without touching identity columns, runtime LLM, or API surface. The raw xlsx stays gitignored; the derived JSONL is the artefact C09 and C10 consume.

## Requirements

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
The pipeline MUST assign `text_quality_tier` (`rich` | `sparse` | `original`) to each internal variant family (stem of the product name plus size suffix), not to a lone product and not by piece type. Every member of a family MUST share the same tier. The JSONL MUST NOT carry `variant_group_key`, `variant_label` or `family_seed`. Global product ratios MUST fall within 70 % / 20 % / 10 % (`rich` / `sparse` / `original`) with a tolerance of ±3 percentage points when measured on the 436-product corpus. The former name `empty` MUST NOT be used: it was read as “blank the description”.

#### Scenario: An internal variant family does not mix tiers
- **GIVEN** a generated JSONL and the source names used to build it
- **WHEN** products are grouped by the internal stem-and-size heuristic
- **THEN** no family contains two distinct `text_quality_tier` values

#### Scenario: JSONL does not emit family seed fields
- **GIVEN** a generated JSONL
- **WHEN** any line is parsed
- **THEN** it does not contain `variant_group_key`
- **AND** it does not contain `variant_label`
- **AND** it does not contain `family_seed`

#### Scenario: Product-level ratios stay inside tolerance
- **GIVEN** the 436-product committed corpus
- **WHEN** products are counted by `text_quality_tier`
- **THEN** `rich` is between 67 % and 73 %
- **AND** `sparse` is between 17 % and 23 %
- **AND** `original` is between 7 % and 13 %

#### Scenario: Fixture family shares a single tier
- **GIVEN** a fixture of three products that the internal grouping step places in one family
- **WHEN** quality assignment runs with a fixed seed
- **THEN** the three records carry the same `text_quality_tier`

### Requirement: Text provenance matches the quality tier
Records with `text_quality_tier` `rich` or `sparse` MUST set `text_provenance` to `ai_assisted`. Records with `text_quality_tier` `original` MUST set `text_provenance` to `merchant` and MUST set `description` to the export `Description` for that SKU, unchanged. The pipeline MUST NOT blank a non-empty original description. The pipeline MUST NOT write `text_provenance` onto `public."Products"` or onto `ai.product_document`.

#### Scenario: Assisted tiers carry ai_assisted provenance
- **GIVEN** a generated JSONL
- **WHEN** records with `text_quality_tier` `rich` or `sparse` are selected
- **THEN** each has `text_provenance` equal to `ai_assisted`
- **AND** each has a non-empty `description`

#### Scenario: Original tier keeps merchant provenance and source copy
- **GIVEN** an export row whose Description is "plata de ley"
- **WHEN** that SKU is assigned `text_quality_tier` `original`
- **THEN** the JSONL line has `text_provenance` equal to `merchant`
- **AND** `description` equals "plata de ley"

#### Scenario: Original tier does not wipe a present description
- **GIVEN** an export row with a non-empty Description
- **WHEN** that SKU is assigned `text_quality_tier` `original`
- **THEN** the JSONL `description` is not empty
- **AND** it equals the export Description

#### Scenario: Original tier may stay blank if the export was blank
- **GIVEN** an export row whose Description is empty
- **WHEN** that SKU is assigned `text_quality_tier` `original`
- **THEN** the JSONL `description` is empty or null
- **AND** `text_provenance` is `merchant`

#### Scenario: Provenance is absent from the Products table
- **GIVEN** a completed local ingest
- **WHEN** the columns of `public."Products"` are inspected
- **THEN** no `text_provenance` column exists
- **AND** no other provenance column was added by this change

### Requirement: Assisted copy reads as a salesperson describing the piece
Assisted descriptions (`rich` and `sparse` only) MUST read as natural product copy, written as if a seller were looking at the piece. They MUST restate information already present in the original `Name` or `Description` (motif, metal, size, finish named there). They MUST NOT invent stones or accessories that those fields do not mention. They MUST NOT mention photographs, source sheets, missing evidence, or the act of imagining. `rich` copy MUST be more generative (3–5 sentences). `sparse` copy MUST be shorter and more restrained (1–2 sentences). Records with `text_quality_tier` `original` MUST NOT receive assisted copy: their `description` MUST equal the export `Description`. Descriptions MUST NOT exceed 1000 characters. The enrichment report MUST include at least five `rich`, three `sparse` and two `original` before/after samples. The report, not the product text, MAY declare that there are no real photos and that visual detail is plausible.

#### Scenario: Copy does not talk about photos or the source sheet
- **GIVEN** a generated JSONL
- **WHEN** records with `text_quality_tier` `rich` or `sparse` are read
- **THEN** no description mentions a photograph, image, ficha de origen, missing evidence, or that stones were not counted

#### Scenario: Original name and description facts are kept
- **GIVEN** a fixture product whose name contains a motif and whose original description names a metal
- **WHEN** assisted copy is applied at `rich` or `sparse`
- **THEN** the description still conveys that motif
- **AND** the description still conveys that metal

#### Scenario: Stones and accessories are not invented
- **GIVEN** a product whose name and original description do not mention a gemstone or an extra accessory
- **WHEN** assisted copy is applied
- **THEN** the description does not introduce diamonds, pearls as added stones, extra chains, boxes, or other accessories absent from the source

#### Scenario: Report samples cover all three tiers
- **GIVEN** the committed corpus and its report
- **WHEN** the report is reviewed
- **THEN** it includes at least five rich, three sparse and two original samples with original and resulting text
- **AND** the assisted samples read as product descriptions, not as commentary on the export

#### Scenario: Overlong copy is rejected before ingest
- **GIVEN** a JSONL line whose `description` is longer than 1000 characters
- **WHEN** validation or ingest runs
- **THEN** the run fails
- **AND** no `UPDATE` from that run is committed

#### Scenario: Original tier is not rewritten to look complete or blank
- **GIVEN** a product assigned `text_quality_tier` `original`
- **WHEN** corpus generation runs
- **THEN** its `description` equals the export Description for that SKU

### Requirement: Tiers are deterministic for a fixed seed
The same export, the same internal grouping rules, the same `generator_version` and the same `seed` MUST produce the same `text_quality_tier` per product. The sidecar MUST record `generator_version`, `seed`, `generated_at`, and product ratios by tier and by `text_provenance`.

#### Scenario: Rerunning assignment with the same seed repeats tiers
- **GIVEN** a fixture export and seed `20260822`
- **WHEN** grouping and quality assignment run twice
- **THEN** `text_quality_tier` per SKU is identical in both outputs

#### Scenario: A different seed may change tier assignment
- **GIVEN** a fixture export
- **WHEN** quality assignment runs with two distinct seeds
- **THEN** the per-SKU `text_quality_tier` map is allowed to differ
- **AND** no internal family mixes tiers in either run

#### Scenario: Sidecar carries traceability fields
- **GIVEN** a completed generation
- **WHEN** the `.meta.json` sidecar is read
- **THEN** it contains `generator_version`, `seed` and `generated_at`
- **AND** it contains product counts or ratios for `rich`, `sparse` and `original`
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
