# QA — C10 `add-synthetic-world-simulator`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-23 · **Rama:** `c10-add-synthetic-world-simulator` · **Commit de implementación:** `f5d1948`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11 (ai-service) |
| Gestor | `uv` — **con `--system-certs` en todas las llamadas**, según `CLAUDE.md` |
| `bcrypt` | `>=4.2.0` (nuevo en `ai-service/pyproject.toml`); hash `$2a$12$` |
| Contrato | `ai-service/openapi.json` — **no se toca**; `test_openapi_snapshot_is_stable` verde |
| Postgres local | `jpv-pv-postgres`, host **5433**, BD `joiabagur_pv` (`JPV_PG*`, solo ingest) |
| Receta | `data/world/pos-profiles.yaml` — `generator_version` `c10-world/v1`, seed `20260823` |
| JSONL / dump | **gitignored**; no viajan en `f5d1948` |

---

## 1. Suite automática de `ai-service`

| Ejecución | Resultado |
|---|---|
| World + alcance C06b (`tests/data/world` + `tests/data/test_scope.py`) | **22 passed, 0 failed** |
| Alcance 10.1 (`tests/data` + `tests/config` + `test_health.py` + `test_openapi_snapshot.py`) | **86 passed, 0 failed** (1 warning Starlette/httpx ajeno a C10) |
| `openspec validate --all --strict` | **38 passed, 0 failed** |

> **Aquí el recuento sí es fiable**, a diferencia de la suite de .NET: la de Python parte de cero fallos en este alcance y no llama a proveedores. C10 no toca `.NET` ni routers; no hay línea base de `dotnet test` que comparar.

Comando de la pasada de alcance (tarea 10.1):

```powershell
uv run --system-certs pytest tests/data tests/config tests/api/test_health.py tests/api/test_openapi_snapshot.py -q --tb=short
```

### Desglose de tests nuevos

| Fichero | Nº | Qué cubre |
|---|---|---|
| `tests/data/world/test_cli.py` | 1 | Flags C06b de `generate`/`ingest` intactos; `world simulate` / `world ingest` anidados |
| `tests/data/world/test_profiles.py` | 5 | Censo 12 códigos, teléfono pinado, `Code` ≤ 20, rechazo de YAML inválido |
| `tests/data/world/test_simulate.py` | 9 | Huecos SKU, simulate sin Postgres, stock no negativo, fechas, estacionalidad, mix aeropuerto, bulk ~15 %, no cartesiano |
| `tests/data/world/test_cooccurrence.py` | 1 | Pares solo con el mismo `BulkOperationId` |
| `tests/data/world/test_ingest.py` | 5 | Fake store: no toca catálogo/`ai`, operadores D6, Artrutx tombstone, rollback SKU, BCrypt `$2a$12$` |
| `tests/data/world/test_scope.py` | 1 | Fixture `forbid_network`; `api.main` no importa `jbg_ai.data` |

**Fake:** `FakeWorldStore` en `jbg_ai/data/world/ingest.py`. Ningún test de `tests/data/world/` abre socket a un proveedor ni exige Docker.

**No existe** `test_simulation_is_deterministic_for_same_seed` (D1 / guardarraíl de tests).

---

## 2. Escenarios de las specs, uno a uno

### `synthetic-world-simulator`

| Requisito · escenario | Test / evidencia | Resultado |
|---|---|---|
| YAML profiles · Census codes, supply flag, closed hotel and pinned phone | `test_yaml_census_has_twelve_codes` · `test_phone_is_pinned_and_code_fits_varchar20` | ✅ |
| YAML profiles · Manual-price POS match the census | `test_yaml_census_has_twelve_codes` (assert `allow_manual_price_edit is (row.code in MANUAL_PRICE_CODES)`) | ✅ |
| Simulate is offline · Simulate does not require Postgres | `test_simulate_does_not_require_postgres` (spy de conexión) | ✅ |
| Simulate is offline · Known catalog holes are not sold | `test_known_catalog_holes_are_not_sold` | ✅ |
| Never sells without stock · No sale without stock at that POS | `test_no_sale_without_stock_at_that_pos` | ✅ |
| Seasonality · Peaks match the profile | `test_seasonality_peaks_match_pos_profile` | ✅ |
| Volumes in bands · Counts sit in the bands | Pasada real 7.1 + ingest 9.2: POS 12, inventario **6720**, ventas **22961** (informe C10). `test_cartesian_inventory_is_not_emitted` sobre fixture | ✅ |
| Volumes in bands · About fifteen percent of checkouts are multi-line | `test_bulk_ratio_is_about_fifteen_percent` | ✅ |
| Collection mix · Airport is not an atelier channel | `test_airport_mix_is_not_atelier` | ✅ |
| Sale and movement · Pair sale and movement | `test_sale_and_movement_share_date_and_user` · `test_inventory_movements_reconcile_with_final_stock` | ✅ |
| Co-occurrence · Pairs require the same bulk operation | `test_co_occurrence_only_counts_same_bulk_operation` | ✅ |
| Ingest transaction · Happy-path ingest fills public tables | Ingest Docker 9.2: 12 POS, 3 operadores, 3 UPOS, 66 pagos, catálogo 1200/38 intacto (informe C10). Recuentos 12/3/3/66 también en `test_ingest_does_not_touch_products_or_collections` | ✅ |
| Ingest transaction · Unmatched SKU rolls back | `test_ingest_rolls_back_on_unmatched_sku` | ✅ |
| Ingest transaction · Catalog and ai tables stay untouched | `test_ingest_does_not_touch_products_or_collections` (`ai_rows == 0`). INSERT POS **sin** columna `IsSupplySource` (`ingest.py:593`) | ✅ |
| Operators · Operator sales only on assigned POS | `test_operator_sales_only_on_assigned_pos` · `test_operator_password_hash_verifies_with_bcrypt` | ✅ |
| Operators · Payments on eleven live POS only | `test_artrutx_is_inactive_without_active_payments` + `counts.payments == 11 * 6` | ✅ |
| Tombstones · Artrutx is inactive with inactive stock | `test_artrutx_is_inactive_without_active_payments` | ✅ |
| CLI / git · HTTP service does not import the data package | `tests/data/test_scope.py::test_api_main_does_not_import_jbg_ai_data` · `tests/data/world/test_scope.py::test_unit_suite_makes_no_provider_calls` · `test_openapi_snapshot_is_stable` | ✅ |
| CLI / git · Git keeps YAML and ignores generated world files | `git check-ignore -v`: YAML **no** ignorado; `sales.jsonl` y `c10-world.sql` sí (`.gitignore:283–286`) | ✅ |
| CLI / git · Catalog CLI flags stay intact | `test_world_cli_does_not_change_catalog_generate_ingest_flags` | ✅ |

**Totales:** 12 requisitos, 20 escenarios (`#### Scenario:`). Todos tienen test nombrado **o** pasada real documentada (bandas 7.1 / ingest Docker 9.2 / `git check-ignore`).

---

## 3. Nombres exigidos por `tasks.md` / ticket

Lista de la ficha C10 y de [ticket.md](ticket.md). Todos existen como `def test_…` y están en verde, salvo los que el diseño retira a propósito.

| Nombre | Fichero |
|---|---|
| `test_world_cli_does_not_change_catalog_generate_ingest_flags` | `test_cli.py` |
| `test_yaml_census_has_twelve_codes` | `test_profiles.py` |
| `test_phone_is_pinned_and_code_fits_varchar20` | `test_profiles.py` |
| `test_known_catalog_holes_are_not_sold` | `test_simulate.py` |
| `test_simulate_does_not_require_postgres` | `test_simulate.py` |
| `test_no_sale_without_stock_at_that_pos` | `test_simulate.py` |
| `test_seasonality_peaks_match_pos_profile` | `test_simulate.py` |
| `test_sale_and_movement_share_date_and_user` | `test_simulate.py` |
| `test_inventory_movements_reconcile_with_final_stock` | `test_simulate.py` |
| `test_co_occurrence_only_counts_same_bulk_operation` | `test_cooccurrence.py` |
| `test_ingest_does_not_touch_products_or_collections` | `test_ingest.py` |
| `test_operator_sales_only_on_assigned_pos` | `test_ingest.py` |
| `test_artrutx_is_inactive_without_active_payments` | `test_ingest.py` |
| `test_ingest_rolls_back_on_unmatched_sku` | `test_ingest.py` |
| `test_unit_suite_makes_no_provider_calls` | `test_scope.py` (world) |
| `test_api_main_does_not_import_jbg_ai_data` | `tests/data/test_scope.py` (C06b, reutilizado) |
| `test_openapi_snapshot_is_stable` | `tests/api/test_openapi_snapshot.py` |

**Retirado a propósito:** `test_simulation_is_deterministic_for_same_seed` — no existe en el árbol.

Extras que cubren escenarios de spec no nombrados en la ficha: `test_profiles_reject_long_code`, `test_profiles_reject_wrong_phone`, `test_profiles_reject_two_supply_sources`, `test_airport_mix_is_not_atelier`, `test_bulk_ratio_is_about_fifteen_percent`, `test_cartesian_inventory_is_not_emitted`, `test_operator_password_hash_verifies_with_bcrypt`.

---

## 4. Alcance negativo (tarea 10.2)

```powershell
git diff --name-only -- ai-service/openapi.json ai-service/migrations backend/src frontend
```

Salida **vacía** respecto al alcance de C10 (el commit `f5d1948` no toca esos paths). `backend/.env.example` sí documenta `JPV_PG*` también para C10, fuera de `src/`.

| Guardarraíl | Comprobación | Resultado |
|---|---|---|
| `ai-service/openapi.json` | no está en el commit de implementación + snapshot estable | ✅ |
| `ai-service/migrations/` | no tocado | ✅ |
| `backend/src/` | no tocado | ✅ |
| `frontend/` | no tocado | ✅ |
| `jbg_ai.data.generate` / `ingest.py` de catálogo | ingest de catálogo solo se **importa** `pg_connect_kwargs_from_env`; flags C06b intactos | ✅ |
| `jbg_ai.api.main` no importa `jbg_ai.data` | test C06b verde | ✅ |
| TODO/FIXME sin seguimiento | no hay en `jbg_ai/data/world/` | ✅ |
| Sin test de bit-identidad | `Get-ChildItem` de `*deterministic*` vacío | ✅ |

---

## 5. Decisiones de diseño, verificadas en código

| Decisión | Evidencia |
|---|---|
| 1 · Módulo `jbg_ai.data.world`, no `generators/` ni seeder .NET | `ai-service/src/jbg_ai/data/world/`; `cli.py` subparser anidado `world` |
| 2 · YAML+semilla en git; JSONL y dump gitignored | `pos-profiles.yaml` en `f5d1948`; `.gitignore` `data/world/generated/*` y `data/world/backups/*` |
| 3 · Simulate sin Postgres; ingest autoriza contra `"Products"` | `test_simulate_does_not_require_postgres`; unmatched → `IngestAborted` + rollback |
| 4 · Poisson, cobertura sesgada, matriz intención ≠ evolución | YAML `lambda_retail` / `coverage` / `collection_weights`; tests de mix y estacionalidad |
| 5 · Fechas escritas, no `DEFAULT NOW()` | `test_sale_and_movement_share_date_and_user` |
| 6 · 3 operadores, Role string, BCrypt cost 12 prefijo `$2a$` | `hash_operator_password`; `test_operator_password_hash_verifies_with_bcrypt` |
| 7 · Transacción única; nunca `IsSupplySource` SQL | INSERT POS columnas existentes (`ingest.py:593`); `NEVER` schema `ai` |
| 8 · Co-ocurrencia JSONL efímera, solo `BulkOperationId` | `cooccurrence.py`; test dedicado |
| 9 · Tests de invariantes en `tests/data/world/` | 22 tests; fake store, no Testcontainers obligatorio |
| 10 · Informe + `pg_dump` local | `c10-synthetic-world-report.md`; dump `data/world/backups/c10-world.sql` |

---

## 6. Pasada real (tareas 7.1 y 9.x) — no es pytest

Horizonte sidecar: `2025-04-23` … `2026-08-23`. `generated_at`: `2026-08-23T17:29:17Z`.

| Métrica | Valor | Banda |
|---|---|---|
| POS | 12 | censo |
| Inventario | **6720** | 6500–8000 |
| Ventas | **22961** | 15000–25000 |
| Movimientos | 29681 (6720 Import + 22961 Sale) | cuadran |
| Pares co-ocurrencia | 4075 | solo bulk |
| Products / Collections | 1200 / 38 | intactos |
| UserPointOfSales | 3 | — |
| PointOfSalePaymentMethods | 66 (11×6) | Artrutx = 0 |
| `HT-ARTRUTX.IsActive` | false | — |

Snapshot previo al ingest (gitignored): `data/world/backups/pre-ingest-counts.txt` — PointOfSales/Inventories/Sales = 0; Products 1200; Collections 38.

---

## 7. Backup de base de datos

**Sí, se hizo** (tarea 9.3). **Sí, está en `.gitignore`.**

| Pieza | Valor |
|---|---|
| Fichero | `data/world/backups/c10-world.sql` |
| Tamaño | 15 108 177 bytes |
| Fecha | 2026-08-23 19:31:05 |
| Comando | `docker exec jpv-pv-postgres pg_dump -U postgres joiabagur_pv > data/world/backups/c10-world.sql` |
| Restore | documentado en `ai-service/src/jbg_ai/data/README.md` |

```
.gitignore:283:data/world/generated/*
.gitignore:284:!data/world/generated/.gitkeep
.gitignore:285:data/world/backups/*
.gitignore:286:!data/world/backups/.gitkeep
```

`git check-ignore -v data/world/backups/c10-world.sql` → ignorado. El YAML **no** se ignora. `git status` tras `f5d1948` no lista dumps ni JSONL.

---

## 8. Documentación de contexto (tarea 10.3)

| Documento | Qué se alineó |
|---|---|
| `Documentos/epicas.md` (EP12 / HU-AIENG-010) | Entregable C10: YAML, CLI world, informe |
| `Documentos/Proyecto Final AIEng/proyecto-final-plan-changes-openspec.md` | Zona `jbg_ai.data.world`; nota hecho |
| `Documentos/Proyecto Final AIEng/informes/c10-synthetic-world-report.md` | Censo, recuentos, operadores, backup |
| `ai-service/src/jbg_ai/data/README.md` | `world simulate\|ingest`, `JPV_PG*`, `pg_dump` / restore |
| `backend/.env.example` | `JPV_PG*` también para C10 |

---

## 9. OpenSpec

```powershell
openspec validate --all --strict
```

**38 passed, 0 failed.** Incluye el change `add-synthetic-world-simulator` y todas las specs vivas.

---

## 10. Fuera de esta pasada (no DoD)

- C19 (`IsSupplySource` SQL), C22 (`ai.pos_projection`), C27 (`ai.co_occurrence` persistida).
- Suite global de .NET: C10 no la toca; no se midió línea base.
- Regenerar `openapi.json`: **prohibido** por el change; el snapshot está verde sin regenerar.
- Commitear JSONL de ventas o el `pg_dump`: **prohibido**; viven en local gitignored.
- Test de bit-identidad a igual semilla: **retirado** a propósito.
