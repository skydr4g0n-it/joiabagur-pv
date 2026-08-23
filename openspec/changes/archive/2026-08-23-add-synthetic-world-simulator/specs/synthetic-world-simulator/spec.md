## ADDED Requirements

### Requirement: YAML profiles describe the twelve-POS census
The committed world recipe SHALL list exactly the twelve point-of-sale codes `MAO-TALLER`, `CIU-CENTRE`, `MAO-AIR`, `FORNELLS`, `BINIBECA`, `HT-GALDANA`, `HT-SONBOU`, `PORT-MAO`, `PALMA-JAIME3`, `EIV-MARINA`, `HT-ALCUDIA`, and `HT-ARTRUTX`. Each `code` MUST be unique and at most 20 characters. Every profile MUST pin `phone` to `600123456`. Exactly one profile (`MAO-TALLER`) MUST set `is_supply_source` to true; the rest MUST set it to false. `HT-ARTRUTX` MUST set `is_active` to false and MUST declare a sales window that ends after summer 2025. The YAML (or its sidecar) MUST declare `seed` and `generator_version`. The YAML MUST NOT contain product or POS UUIDs. `is_supply_source` MUST exist only in YAML/sidecar; ingest MUST NOT write a SQL column of that name.

#### Scenario: Census codes, supply flag, closed hotel and pinned phone
- **GIVEN** the committed file `data/world/pos-profiles.yaml`
- **WHEN** the profiles are loaded
- **THEN** there are exactly those twelve `code` values
- **AND** each `code` is unique and length ≤ 20
- **AND** every phone is `600123456`
- **AND** `MAO-TALLER` has `is_supply_source` true and every other POS has `is_supply_source` false
- **AND** `HT-ARTRUTX` has `is_active` false and a `closed_after` date in or after September 2025
- **AND** `seed` and `generator_version` are present
- **AND** no UUID fields appear for products or POS

#### Scenario: Manual-price POS match the census
- **GIVEN** the committed profiles
- **WHEN** `allow_manual_price_edit` is read
- **THEN** it is true for `MAO-AIR`, `HT-GALDANA`, `HT-SONBOU`, `EIV-MARINA` and `HT-ALCUDIA`
- **AND** it is false for `MAO-TALLER` and the remaining POS

### Requirement: Simulate is offline and emits natural keys only
`world simulate` MUST NOT connect to PostgreSQL. Emitted JSONL MUST identify products, POS and users by `sku`, `pos_code` and `username` respectively, never by UUID. Simulate MAY read both catalog JSONL files to bias mix by `collection_name`. The simulated SKU universe MUST exclude the documented catalog holes (`SKU135`, `SKU400`, `SKU418` by default). Simulate MUST NOT call an LLM or require `JPV_CATALOG_LLM_*`.

#### Scenario: Simulate does not require Postgres
- **GIVEN** a valid profiles YAML and catalog JSONL fixtures
- **WHEN** `world simulate` runs
- **THEN** it writes JSONL under the output directory
- **AND** it does not open a PostgreSQL connection
- **AND** every sale and inventory line uses `sku` and `pos_code`
- **AND** no line contains a product, POS or user UUID

#### Scenario: Known catalog holes are not sold
- **GIVEN** catalog JSONL that includes `SKU135`, `SKU400` and `SKU418`
- **WHEN** simulate builds the SKU universe
- **THEN** those three SKUs are absent from emitted sales and inventory JSONL

### Requirement: Simulation never sells without sufficient active stock at that POS
The simulator MUST emit a sale of SKU S at POS P only when an active inventory row for (S, P) had sufficient quantity immediately before the sale. A `Sale` movement MUST set `QuantityChange < 0` and `QuantityAfter = QuantityBefore + QuantityChange`. No inventory quantity MUST become negative. Each sale MUST have exactly one `Sale`-type movement.

#### Scenario: No sale without stock at that POS
- **GIVEN** a simulated horizon of 14–18 months
- **WHEN** the simulator emits a sale of SKU S at POS P
- **THEN** an active inventory row of S at P existed with quantity ≥ sold units before the sale
- **AND** the Sale movement has `QuantityChange < 0`
- **AND** `QuantityAfter` equals `QuantityBefore + QuantityChange`
- **AND** no inventory quantity is negative

### Requirement: Seasonality and volume order follow POS profiles
Aggregated sales MUST follow each POS profile rather than uniform noise. Hotel and Fornells volume MUST concentrate in the high season declared by the profile (June–September or equivalent). `CIU-CENTRE` MUST NOT replicate that extreme curve. `MAO-TALLER` retail volume MUST be ~0. `HT-ARTRUTX` MUST have no sales after `closed_after`. Magnitude order MUST be Ciutadella > airport/Palma > … > Fornells retail > workshop > Artrutx; bit-identity is NOT required.

#### Scenario: Peaks match the profile
- **GIVEN** a completed simulation
- **WHEN** sales are aggregated by month and POS
- **THEN** `HT-GALDANA`, `HT-SONBOU` and `FORNELLS` concentrate volume in high season
- **AND** `CIU-CENTRE` does not replicate that extreme curve
- **AND** `MAO-TALLER` has ~0 retail sales
- **AND** `HT-ARTRUTX` has no sales after its closed_after date
- **AND** Ciutadella outsells Fornells retail, which outsells the workshop

### Requirement: Inventory and sales volumes stay inside agreed bands
Default horizon MUST be 16 months (allowed band 14–18). Ingested (or simulated) inventory rows MUST fall between 6.500 and 8.000 inclusive; the cartesian 1.200 × 12 MUST NOT be materialised. Sales MUST fall between 15.000 and 25.000 inclusive. Coverage MUST be biased: workshop ≈ full catalog; flagship/Palma ~60–70 %; airport/ports/hotels ~25–40 % mix-biased; Fornells a small assortment; Artrutx a handful.

#### Scenario: Counts sit in the bands
- **GIVEN** a full-catalog simulation (or its ingested tables)
- **WHEN** rows are counted
- **THEN** there are 12 POS
- **AND** inventory rows are between 6.500 and 8.000
- **AND** sales rows are between 15.000 and 25.000
- **AND** the inventory row count is less than 1.200 × 12

#### Scenario: About fifteen percent of checkouts are multi-line
- **GIVEN** a completed simulation
- **WHEN** checkouts (distinct operations) are counted
- **THEN** about 15 % of operations share a `BulkOperationId` across 2–3 lines
- **AND** those multi-line operations use distinct name stems or collections when possible

### Requirement: Collection mix follows intention-not-evolution weights
Each POS profile MUST carry `collection_weights` so simulate does not treat a C06b collection as an exclusive channel. Mix MUST follow the HU matrix (e.g. El Jaleo sells at airport/port but also leaks to Ciutadella; atelier collections almost never sell at the airport).

#### Scenario: Airport is not an atelier channel
- **GIVEN** simulated sales and catalog `collection_name`
- **WHEN** mix is aggregated for `MAO-AIR` versus `CIU-CENTRE`
- **THEN** airport volume is biased toward tourist/airport collections such as El Jaleo and Marea viva
- **AND** atelier collections such as Cielo estrellado / Filigrana are rare at the airport relative to Ciutadella

### Requirement: Sale and movement share date and user
For every sale-type movement, `MovementDate` MUST equal `SaleDate`, and `UserId` MUST equal the sale's `UserId`. `CreatedAt` / `UpdatedAt` (and inventory `LastUpdatedAt` where written) MUST be set to the simulated timestamptz, not left to `NOW()` at ingest. Reconstructing `QuantityAfter` from the last movement MUST equal ingested `"Inventories"."Quantity"`. Initial stock MUST use `MovementType` Import (4). The simulator MUST NOT emit `Return` (2) movements.

#### Scenario: Pair sale and movement
- **GIVEN** ingested or simulated sales and movements
- **WHEN** each sale is joined to its unique Sale movement
- **THEN** `SaleDate` equals `MovementDate`
- **AND** both share the same `UserId`
- **AND** `CreatedAt` / `UpdatedAt` align with that simulated instant, not the ingest clock
- **AND** the last movement `QuantityAfter` equals inventory `Quantity`

### Requirement: Co-occurrence is ephemeral and BulkOperationId-scoped
After `BulkOperationId` assignment, simulate MUST write an ephemeral JSONL of pairs `{product_sku_a, product_sku_b, co_sales_count, last_seen_at}` with `sku_a < sku_b`. A pair MUST count only when lines share `BulkOperationId`; same POS and day is NOT sufficient. Ingest MUST NOT insert into schema `ai` or table `ai.co_occurrence`.

#### Scenario: Pairs require the same bulk operation
- **GIVEN** two sale lines at the same POS on the same day with distinct `BulkOperationId` (or one null)
- **WHEN** co-occurrence JSONL is derived
- **THEN** that pair is not counted
- **AND** two lines that share a `BulkOperationId` are counted once in canonical `sku_a < sku_b` order
- **AND** no row is written to schema `ai`

### Requirement: Ingest resolves foreign keys in one transaction and never touches catalog or ai
`world ingest` MUST use `JPV_PG*` against local Docker (host 5433, database `joiabagur_pv`) and MUST run in a single transaction. PostgreSQL MUST assign POS, user, inventory, sale and movement `Id` values. Ingest MUST resolve `sku → ProductId`, `pos_code → PointOfSaleId`, `username → UserId`. `Sale.Price` MUST be the snapshot of `"Products"."Price"` at ingest. If any world SKU is missing from `"Products"`, ingest MUST abort, list unmatched SKUs, and `ROLLBACK`. Ingest MUST NOT `INSERT` or `UPDATE` `"Products"`, `"Collections"`, `"ProductFamilies"`, `"ProductFamilyMembers"`, `"ProductAiProfiles"`, or any `ai.*` table. Ingest MUST NOT target RDS. Ingest MUST NOT add or populate an `IsSupplySource` column. If census POS codes already exist, ingest MUST abort rather than upsert or delete unrelated rows. Bulk insert (`COPY` or executemany) MUST be used rather than one round-trip per sale.

#### Scenario: Happy-path ingest fills public tables
- **GIVEN** Docker with ~1.200 products and 0 POS, and a valid generated directory
- **WHEN** `world ingest` runs
- **THEN** one transaction inserts 12 POS, 3 operators, 3 `UserPointOfSales`, payment methods on the 11 active POS, inventories, sales and movements
- **AND** `"Products"` count and SKUs are unchanged
- **AND** `"Collections"` is unchanged
- **AND** PostgreSQL assigned the Ids
- **AND** `Sale.Price` equals the catalog price at ingest

#### Scenario: Unmatched SKU rolls back
- **GIVEN** a world JSONL that contains a SKU absent from `"Products"`
- **WHEN** ingest runs
- **THEN** the transaction is rolled back
- **AND** unmatched SKUs are listed
- **AND** no POS, user, inventory, sale or movement from that run remains committed

#### Scenario: Catalog and ai tables stay untouched
- **GIVEN** snapshots of `"Products"`, `"Collections"`, family tables and schema `ai` (absent or empty)
- **WHEN** ingest commits successfully
- **THEN** those catalog and family snapshots match
- **AND** no `ai.*` writes occurred
- **AND** `"PointOfSales"` has no `IsSupplySource` column

### Requirement: Demo operators, payments and Sale.UserId follow assignment rules
Ingest MUST create exactly three users `op-ciutadella`, `op-fornells` and `op-aeroport` with `Role` the string `Operator`, BCrypt password hash of `Operator123!` at work factor 12, and exactly one active `UserPointOfSales` row each (`CIU-CENTRE`, `FORNELLS`, `MAO-AIR`). Sales at those three POS MUST use that operator's `UserId`. Sales at other active POS MUST use the existing `admin` user. `MAO-TALLER` and `HT-ARTRUTX` MUST have no operator assignment. Sale-type movements MUST copy the sale `UserId`; Import movements MUST use `admin`. The eleven active POS MUST each have the six seeder payment methods active; `HT-ARTRUTX` MUST have none.

#### Scenario: Operator sales only on assigned POS
- **GIVEN** an ingested world
- **WHEN** sales are grouped by POS
- **THEN** `CIU-CENTRE` / `FORNELLS` / `MAO-AIR` sales use `op-ciutadella` / `op-fornells` / `op-aeroport`
- **AND** other active POS sales use `admin`
- **AND** `HT-ARTRUTX` has no `UserPointOfSales` row
- **AND** each operator has `Role` equal to `Operator` and verifies against `Operator123!`

#### Scenario: Payments on eleven live POS only
- **GIVEN** an ingested world
- **WHEN** `PointOfSalePaymentMethods` are counted
- **THEN** each of the eleven active POS has the six seeder methods
- **AND** `HT-ARTRUTX` has zero active payment-method assignments

### Requirement: Closed hotel and idle inventory provide tombstones
After ingest, `"PointOfSales"` for `HT-ARTRUTX` MUST have `IsActive = false`. All residual Artrutx inventory MUST have `IsActive = false`. About 8 % of inventory rows on **live** POS MUST also have `IsActive = false`, in addition to 100 % of Artrutx inventory.

#### Scenario: Artrutx is inactive with inactive stock
- **GIVEN** a completed ingest
- **WHEN** `HT-ARTRUTX` is read
- **THEN** the POS `IsActive` is false
- **AND** every inventory row at that POS has `IsActive` false
- **AND** a non-zero fraction (~8 %) of inventory rows at live POS has `IsActive` false

### Requirement: CLI stays outside the HTTP runtime and does not commit world JSONL
The world CLI MUST be invoked as `python -m jbg_ai.data world simulate|ingest` without changing the contract of catalog `generate` / `ingest`. `jbg_ai.api.main` MUST NOT import `jbg_ai.data`. `ai-service/openapi.json` MUST NOT change. This change MUST NOT add EF Core or Alembic migrations. Pytest for the simulator MUST NOT open sockets to LLM providers. World sales JSONL and SQL dumps MUST be gitignored; the YAML profiles and seed MUST be committed. Module README MUST document `pg_dump` / restore against `jpv-pv-postgres`. No FastAPI or .NET sales/simulation endpoint MUST be added.

#### Scenario: HTTP service does not import the data package
- **GIVEN** this change's code
- **WHEN** `jbg_ai.api.main` is inspected
- **THEN** it does not import `jbg_ai.data`
- **AND** `openapi.json` is unchanged
- **AND** there is no new EF or Alembic migration
- **AND** the world unit suite makes no LLM provider calls

#### Scenario: Git keeps YAML and ignores generated world files
- **GIVEN** `data/world/pos-profiles.yaml` and files under `data/world/generated/` and `data/world/backups/`
- **WHEN** git ignore rules are applied
- **THEN** the YAML is not ignored
- **AND** generated JSONL and SQL dumps are ignored

#### Scenario: Catalog CLI flags stay intact
- **GIVEN** `python -m jbg_ai.data --help`
- **WHEN** the parser is built
- **THEN** `generate` and `ingest` still exist with their C06b flags
- **AND** `world simulate` and `world ingest` are additional nested commands
