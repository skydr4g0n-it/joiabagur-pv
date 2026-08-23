> **Línea de corte.** Los grupos 1–6 son la mitad determinista y testeable **sin Docker y sin LLM**: andamiaje, YAML, simulate en memoria, co-ocurrencia e ingest sobre store fake. Si la sesión se desborda (regla 5 del plan), se entrega esa mitad. **No se parte el change** (D8): los grupos 7–9 (pasada real, ingest Docker, informe, verify) siguen en el mismo `add-synthetic-world-simulator`. El grupo 10 cierra docs y `openspec validate --all --strict`.

> **Guardarraíl de alcance.** Este change **no toca** `ai-service/openapi.json`, routers, `ai-service/migrations/`, entidades .NET, `jbg_ai.data.generate` / `ingest` de catálogo ni `scripts/catalog/assist.py`. Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance, no hay que regenerar el contrato.

> **Guardarraíl de git.** Se ignora `data/world/generated/` y `data/world/backups/`. Se commitea `data/world/pos-profiles.yaml`. `git status` no debe listar JSONL de ventas ni dumps SQL.

> **Guardarraíl de boot.** No hay settings nuevas en `Settings`. `jbg_ai.api.main` no importa `jbg_ai.data`. Cero LLM. Cero `JPV_CATALOG_LLM_*` en simulate.

> **Guardarraíl de tests.** Nomenclatura `test_<unidad>_<escenario>_<esperado>`. **No** implementar `test_simulation_is_deterministic_for_same_seed`. Reutilizar `test_api_main_does_not_import_jbg_ai_data` de C06b; no romperlo.

## 1. Andamiaje de `jbg_ai.data.world` y visibilidad de artefactos

- [ ] 1.1 Crear el paquete `ai-service/src/jbg_ai/data/world/` (`__init__.py`, módulos stub `profiles`, `simulate`, `ingest`, `cooccurrence`, `records`). Añadir `bcrypt` a `ai-service/pyproject.toml` **sin** tocar OpenAPI. Extender `cli.py` con subparser anidado `world simulate|ingest` **sin** cambiar flags de `generate`/`ingest` de catálogo. README del CLI: comandos, `JPV_PG*` (solo ingest), semilla `20260823`, `generator_version` `c10-world/v1`, `pg_dump` / restore. **Validación:** `uv sync --system-certs` en `ai-service/` completa; `python -m jbg_ai.data world --help` arranca; `python -m jbg_ai.data generate --help` conserva flags C06b; `git diff ai-service/openapi.json` vacío; `test_world_cli_does_not_change_catalog_generate_ingest_flags`.

- [ ] 1.2 Abrir en `.gitignore` `data/world/generated/` y `data/world/backups/` **sin** ignorar el YAML. Crear `data/world/.gitkeep` (y `generated/.gitkeep` / `backups/.gitkeep` si hace falta que existan los dirs). **Validación:** `git check-ignore -v data/world/pos-profiles.yaml` no lo ignora (cuando exista); un `*.jsonl` bajo `generated/` sí; un `*.sql` bajo `backups/` sí.

- [ ] 1.3 Crear `ai-service/tests/data/world/` espejando el paquete. Afirmar que la suite world no abre sockets a proveedores. **Validación:** `uv run --system-certs pytest tests/data/world tests/data/test_scope.py -q` arranca; `test_api_main_does_not_import_jbg_ai_data` sigue verde; `test_unit_suite_makes_no_provider_calls` (o equivalente world) no abre red.

## 2. YAML de 12 POS y validador de perfiles

- [ ] 2.1 Escribir `data/world/pos-profiles.yaml` con cabecera (`generator_version`, `seed`, `horizon_months: 16`, `phone: "600123456"`, `inactive_inventory_ratio_live_pos: 0.08`, `bulk_checkout_ratio: 0.15`, `catalog_sku_holes`) + 12 POS del censo + 3 operadores. Pesos de colección según la matriz intención ≠ evolución de la HU. `MAO-TALLER` único `is_supply_source: true`; `HT-ARTRUTX` `is_active: false` y `closed_after` fin de verano 2025; precio manual en los 5 del ticket. **Validación:** `test_yaml_census_has_twelve_codes`; `test_phone_is_pinned_and_code_fits_varchar20`; cada `code` ≤ 20.

- [ ] 2.2 Implementar carga y validación de perfiles (códigos exactos, unique, teléfono, un solo supply, Artrutx cerrado, sin UUID). Rechazar YAML incompleto antes de simular. **Validación:** fixture válida pasa; fixture con `Code` de 21 chars o teléfono largo falla; fixture con dos `is_supply_source: true` falla.

## 3. Simulate: cobertura de inventario y stock no negativo

- [ ] 3.1 Construir el universo de SKU desde ambos JSONL de catálogo **menos** `catalog_sku_holes`. Asignar inventario sesgado (taller ≈ catálogo; flagship/Palma ~60–70 %; aeropuerto/hoteles ~25–40 %; Fornells poco; Artrutx puñado). No materializar 1.200×12. **Validación:** sobre fixture pequeña, el cartesiano no se emite; los tres huecos no aparecen; `test_known_catalog_holes_are_not_sold`.

- [ ] 3.2 Emitir stock inicial + movimientos `Import=4` (`UserId` lógico `admin`). Marcar ~8 % de filas en POS vivas `IsActive=false` y el 100 % de Artrutx. Simulate **no** conecta a Postgres. JSONL con `sku` / `pos_code` / `username`. **Validación:** `test_simulate_does_not_require_postgres` (mock/spy de conexión); ningún UUID en la salida.

- [ ] 3.3 Recorrer el horizonte (defecto 16 meses) con Poisson POS×día (λ × estacionalidad × propensión). Qty típica 1. Nunca vender sin fila activa con qty suficiente. Movimiento `Sale=1` 1:1, `QuantityChange < 0`, `QuantityAfter = QuantityBefore + QuantityChange`. Cero `Return=2`. **Validación:** `test_no_sale_without_stock_at_that_pos`; fixture que intentaría vender de más no emite la venta (o falla el generate, no deja qty negativa).

## 4. Estacionalidad, mix, tickets multi-línea y fechas (D11)

- [ ] 4.1 Aplicar seasonality del YAML. Taller λ retail ~0. Artrutx sin ventas después de `closed_after`. Orden de magnitud Ciutadella > aeropuerto/Palma > Fornells retail > taller. **Validación:** `test_seasonality_peaks_match_pos_profile` sobre agregados mensuales de fixture o de una simulación reducida.

- [ ] 4.2 Sesgar SKU por `collection_weights` (El Jaleo en aeropuerto/puerto, atelier raro en `MAO-AIR`). ~15 % de *operaciones* con `BulkOperationId` y 2–3 líneas de distinto stem/colección. **Validación:** test de mix aeropuerto vs Ciutadella sobre fixture de colecciones; test de ratio ~15 % ± holgura razonable en simulación de tamaño medio.

- [ ] 4.3 Escribir `SaleDate` = `MovementDate` = `CreatedAt`/`UpdatedAt` simulados (UTC), no el reloj del proceso. Reconciliar stock final con último `QuantityAfter`. `SearchEventId` null, `PriceWasOverridden` false, `Notes` null. Precio en JSONL puede ir vacío o placeholder: el snapshot real es del ingest. **Validación:** `test_sale_and_movement_share_date_and_user`; `test_inventory_movements_reconcile_with_final_stock`.

## 5. Co-ocurrencia efímera

- [ ] 5.1 Tras asignar `BulkOperationId`, derivar JSONL `{product_sku_a, product_sku_b, co_sales_count, last_seen_at}` con `sku_a < sku_b`. Contar **solo** mismo `BulkOperationId`. No escribir `ai.*`. **Validación:** `test_co_occurrence_only_counts_same_bulk_operation` (mismo POS y día con Ids distintos **no** cuenta; mismo bulk sí).

## 6. Ingesta transaccional sobre store fake (sin Docker obligatorio)

- [ ] 6.1 Puerto `WorldStore` (análogo a `CatalogStore` C06b): INSERT POS / Users / UPOS / pagos / Inventories / Sales / Movements; SELECT mapa Products; begin/commit/rollback. Resolver `sku`/`pos_code`/`username`. `Sale.Price` del mapa. Batch/`executemany`, no un roundtrip por venta. Abortar si ya existen códigos del censo. **Nunca** tocar Products/Collections/Family/ai. **Nunca** columna `IsSupplySource`. **Validación:** `test_ingest_does_not_touch_products_or_collections` sobre fake; recuentos 12 POS / 3 users / 3 UPOS / 11×6 pagos.

- [ ] 6.2 Operadores: BCrypt cost 12 de `Operator123!`; `Role` literal `Operator`; D6 de `UserId` (3 POS → operador, resto → `admin`; Import → admin). Artrutx sin pagos ni operador. **Validación:** `test_operator_sales_only_on_assigned_pos`; `test_artrutx_is_inactive_without_active_payments`; el hash verifica `Operator123!` con `bcrypt.checkpw`.

- [ ] 6.3 Rollback por SKU unmatched (lista) y por `Code` duplicado. Tras el fallo, recuentos iguales al snapshot del fake. **Validación:** `test_ingest_rolls_back_on_unmatched_sku`.

## 7. Pasada simulate a tamaño real (JSONL local gitignored)

- [ ] 7.1 Ejecutar `world simulate --profiles ../data/world/pos-profiles.yaml --out ../data/world/generated` contra los JSONL C06a+C06b commiteados. Sidecar de recuentos (gitignored o solo en el informe). **Validación:** inventario 6.500–8.000; ventas 15.000–25.000; 12 POS; invariantes de 3.x–5.x en verde sobre esa salida; `git status` no propone el JSONL.

## 8. Informe C10

- [ ] 8.1 Redactar `Documentos/Proyecto Final AIEng/informes/c10-synthetic-world-report.md` con censo, recuentos, operadores (password de demo), marca supply solo YAML, nota de backup/`pg_dump`, huecos SKU135/400/418, y que no hay test de bit-identidad. **Validación:** las cifras salen del sidecar/salida de 7.1; ningún UUID en el YAML citado.

## 9. Ingesta local contra Docker

- [ ] 9.1 Snapshot o dump previo de `"PointOfSales"` / `"Inventories"` / `"Sales"` (deben estar vacías). **Validación:** el fichero existe en local y **no** se commitea.

- [ ] 9.2 Ejecutar `world ingest --dir ../data/world/generated` contra `localhost:5433` / `joiabagur_pv` (`JPV_PG*`). **Validación:** 12 POS, 3 operadores, 3 asignaciones, pagos en 11 activas, inventario y ventas en banda, movimientos que cuadran, `"Products"` intacto, `"Collections"` intacto, `HT-ARTRUTX.IsActive=false`, cero escrituras `ai`, login local `op-ciutadella` / `Operator123!` (smoke manual o script anotado en el informe).

- [ ] 9.3 `pg_dump` a `data/world/backups/c10-world.sql` (gitignored). Documentar restore en el README de 1.1. **Validación:** `git check-ignore` oculta el dump; el README tiene el one-liner de restore.

## 10. Verificación de alcance y documentación

- [ ] 10.1 `uv run --system-certs pytest tests/data tests/config tests/api/test_health.py tests/api/test_openapi_snapshot.py` en verde (más el resto de `ai-service` si se tocó `pyproject.toml`). **Validación:** sin fallos **nuevos**; comparar nombres si la suite global ya tenía rojos ajenos.

- [ ] 10.2 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/migrations/`, `backend/src/`, `frontend/`, `jbg_ai.data.generate` / `ingest.py` de catálogo (salvo `cli.py` anidando `world`). `jbg_ai.api.main` sigue sin importar `jbg_ai.data`. No existe `test_simulation_is_deterministic_for_same_seed`.

- [ ] 10.3 Alinear docs de contexto: `Documentos/epicas.md` (EP12 / HU-AIENG-010), coherencia HU + ticket con el entregable, nota breve en el plan si hace falta registrar `generator_version` / zona `jbg_ai.data.world`. **Validación:** un lector de la épica llega al YAML, al informe 8.1 y a la frontera §6.3.

- [ ] 10.4 Ejecutar **`openspec validate --all --strict`**. **Validación:** la salida reporta `0 failed`.
