## Why

C06a+C06b dejaron 1.200 productos y 38 colecciones en Docker, pero `"PointOfSales"`, `"Inventories"` y `"Sales"` están a cero. C19, C22 y C27 no pueden demostrar ranking ni proyección POS sobre un mundo vacío. Se hace ahora porque el catálogo híbrido ya está ingerido, C10 no compite por migración EF y no es un servicio de producto: es el dataset D6/D7/D8.

## What Changes

- **YAML curado de 12 POS** + semilla + `generator_version`, **commiteado** en `data/world/pos-profiles.yaml`. Censo cerrado (Baleares, centro Menorca): `MAO-TALLER` (único `is_supply_source`), `CIU-CENTRE`, `MAO-AIR`, `FORNELLS`, `BINIBECA`, `HT-GALDANA`, `HT-SONBOU`, `PORT-MAO`, `PALMA-JAIME3`, `EIV-MARINA`, `HT-ALCUDIA`, `HT-ARTRUTX` (`is_active: false`, cerró tras verano 2025). Teléfono pinado `600123456`. Pesos de colección por POS (intención C06b ≠ canal exclusivo).
- **CLI nuevo** `jbg_ai.data.world`, invocado como `python -m jbg_ai.data world simulate|ingest`. No altera el contrato de `generate`/`ingest` de catálogo. `jbg_ai.api.main` **no** importa `jbg_ai.data`. Cero LLM. Cero ruta HTTP.
- **Simulación Poisson** 16 meses (banda 14–18): inventario sesgado **6.500–8.000** filas (no el cartesiano 1.200×12), ventas **15.000–25.000**, movimientos derivados, ~15 % de checkouts con `BulkOperationId` multi-línea. Generate trabaja con `SKU`/`Code`/`username`; **no** habla con Postgres.
- **Ingesta local transaccional** (Docker `:5433`, `joiabagur_pv`, `JPV_PG*`): INSERT de POS, 3 operadores (`op-ciutadella`, `op-fornells`, `op-aeroport`, BCrypt cost 12, `Operator123!`), 3 `UserPointOfSales`, pagos en 11 POS activas, inventario, ventas y movimientos. Un SKU unmatched → lista + `ROLLBACK`. **No** toca `"Products"` ni `"Collections"` ni el schema `ai`.
- **`is_supply_source` solo en YAML.** La columna SQL es C19; este change **no** abre migración EF.
- **Co-ocurrencia** como JSONL efímero derivado de `Sales.BulkOperationId`. **No** se ingiere en `ai.co_occurrence`.
- **JSONL de ~20k ventas y `pg_dump` gitignored.** El seguro del volumen Docker es el dump local, no un corpus bit-idéntico en git.
- **Informe** `Documentos/Proyecto Final AIEng/informes/c10-synthetic-world-report.md`.

**Desviación respecto a la ficha v3 del plan (acordada 2026-08-23, documentada en `design.md`):** no hay generador en `jbg_ai.data.generators/` como pieza de servicio; no se commitea el JSONL; se retira `test_simulation_is_deterministic_for_same_seed`; co-ocurrencia **no** se escribe a `ai`; no se parte el change (D8); hotel Artrutx cerrado en lugar de un pop-up de Navidad.

**Fuera de alcance:** C19 (`IsSupplySource` SQL, señales), C22 (`ai.pos_projection`), C27 (`ai.co_occurrence` persistida), ruta HTTP, regenerar `openapi.json`, seeder `DatabaseSeeder`, RDS, LLM, `generate.py`/`ingest.py` de catálogo, `"Products"`/`"Collections"`/`"ProductFamily*"`/`"ProductAiProfiles"`, devoluciones, fotos, search events.

Sin breaking changes: no hay contrato HTTP nuevo ni modificación de contratos existentes.

## Capabilities

### New Capabilities

- `synthetic-world-simulator`: CLI offline en `jbg_ai.data.world` que, a partir de un YAML curado de 12 POS, simula inventario sesgado y un histórico Poisson coherente con el catálogo local (claves naturales, stock no negativo, co-ocurrencia derivada) y lo inserta en PostgreSQL Docker sin tocar catálogo, schema `ai`, OpenAPI ni el runtime de `jbg-ai`.

### Modified Capabilities

Ninguna. `synthetic-catalog-corpus` describe el generate/ingest de productos C06b y no cambia de requisitos: este change añade subcomandos `world` **al lado**, sin alterar ese contrato. `point-of-sale-management`, `inventory-management`, `sales-management` y `user-management` son el CRUD .NET; el CLI hace `INSERT` directo y no modifica esas APIs. `ai-service-runtime` ya exige solo `APP_ENV` / `SERVICE_VERSION` / `JWT_SECRET`; no hay settings nuevas de boot. `ai-service-api-contracts` no gana rutas. `ai-vector-schema` / ingest de `ai.co_occurrence` es **C22/C27**. `IsSupplySource` en SQL es **C19**.

## Impact

**Nuevo**

- `ai-service/src/jbg_ai/data/world/`: perfiles, Poisson, movimientos, co-ocurrencia, simulate e ingest.
- `data/world/pos-profiles.yaml` y semilla (commiteados).
- `Documentos/Proyecto Final AIEng/informes/c10-synthetic-world-report.md`.
- Tests en `ai-service/tests/data/world/` (invariantes; cero LLM).

**Modificado**

- `ai-service/src/jbg_ai/data/cli.py`: subcomandos `world simulate|ingest` sin cambiar `generate`/`ingest` de catálogo.
- `ai-service/src/jbg_ai/data/README.md`: documentar mundo, `JPV_PG*`, `pg_dump` / restore.
- `.gitignore`: ignorar `data/world/generated/` y `data/world/backups/`; exceptuar el YAML.
- `ai-service/pyproject.toml`: dependencia `bcrypt` (work factor 12, compatible con BCrypt.Net). `pyyaml` ya está.

**PostgreSQL local (Docker)** — `INSERT` en `"PointOfSales"`, `"Users"` (×3), `"UserPointOfSales"`, `"PointOfSalePaymentMethods"`, `"Inventories"`, `"Sales"`, `"InventoryMovements"`. Transacción única; rollback si SKU unmatched o `Code` duplicado. Cero escrituras a `"Products"`, `"Collections"`, `"ProductFamily*"`, `"ProductAiProfiles"`, schema `ai`. No toca RDS.

**Sin cambios** — `backend/` (código, migraciones EF, entidades), `frontend/`, `ai-service/openapi.json`, `ai-service/migrations/`, `ai-service/src/jbg_ai/api/main.py`, `terraform/`, `jbg_ai.data.generate` / `ingest` de catálogo.

**Frontera §6.3.** El rol de runtime de `jbg-ai` no gana `INSERT` sobre `public`. El CLI de desarrollo usa `JPV_PG*` igual que C06a/C06b.

**Dependientes desbloqueados:** C19 (filas Sales+Inventory+POS; marca supply en YAML), C22 (inventario sesgado), C27 (`BulkOperationId` + JSONL derivado). C12 podrá leer POS e inventario cuando exista el feed. C16/C36 ganan 3 logins Operator de demo.
