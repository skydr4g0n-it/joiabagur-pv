> **Línea de corte.** Los grupos 1–6 son la mitad **archivable** si la sesión desborda (ficha C13 / regla 5): settings de feed, Alembic (`text_provenance`, `sync_checkpoint`, `sync_failure`), mapa `sku_provenance.json`, cliente HTTP del feed, repositorio Core y orquestador upsert/tombstone con fakes. Los grupos 7–10 son router real + OpenAPI + CLI + status/drift. Sin ellos C14 no tiene disparo HTTP; esa segunda mitad sigue siendo 🔴. El usuario pidió no partir; esta línea solo aplica si el apply no cabe.

> **Guardarraíl de freeze.** `git diff` de `ai-service/src/jbg_ai/indexing/embeddings.py` **vacío**. El orquestador **no** llama al feed POS. Sin migración EF Core. Sin operación nueva en `IAiGatewayClient`. `jbg_ai.api.main` **no** menciona `jbg_ai.indexing` en su fuente (el router sí importa).

> **Guardarraíl de contrato.** Este change **sí** regenera `ai-service/openapi.json` (opción B: `since_id` / `cursor_id`). `test_openapi_snapshot_is_stable` debe quedar verde **después** de esa regeneración, no antes. El stub rellena los campos nuevos. `batch_size` se ignora (página = 50 de C12).

> **Guardarraíl de boot y secretos.** `JPV_INDEX_FEED_*` y el tope 180 s son **opcionales** en `Settings`. `/health` no las exige. Sync real sin key/URL/mapa/embed key → **503** nombrando la setting, no 501. **Prohibido** caer a `JWT_SECRET`. Pin en `canonical_openapi_settings`. Tres secretos distintos; la key de feed no se loguea.

> **Guardarraíl de tests.** Nombres `test_<unidad>_<escenario>_<esperado>`. Fakes de feed, embed y repo. Cero sockets a OpenAI, LLM ni `:5056`. Tests de esquema en `tests/migrations/` con el contenedor pgvector; omitir (no fallar) si Docker no responde. Un pytest **no** exige 1.200 filas reales. `uv run` lleva `--system-certs`.

## 1. Settings de feed y pin del snapshot

- [ ] 1.1 Añadir `JPV_INDEX_FEED_BASE_URL`, `JPV_INDEX_FEED_API_KEY` y `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` (default **180**) en `settings.py`. String vacío = unset. Blank del tope → 180. Pinnar URL/key a `None` y tope a 180 en `canonical_openapi_settings`. Completar `backend/.env.example` y Compose (`jbg-ai` → `http://host.docker.internal:5056`, placeholder de key ≠ `JWT_SECRET`). **Validación:** `test_settings_do_not_require_index_feed_key_to_boot`; blank → unset; `GET /health` 200 sin esas vars; `test_canonical_openapi_settings_pin_index_feed_keys_to_absent`.

## 2. Alembic (revisión a mano)

- [ ] 2.1 Nueva revisión hija de `f46c55c056e2` (escribir a mano; **no** `--autogenerate`). `ai.product_document.text_provenance text NOT NULL` + CHECK `IN ('merchant','ai_assisted','synthetic')` + índice B-tree `ix_product_document_text_provenance`. Sin ENUM. Sin backfill (tabla vacía). Downgrade drop de columna e índice. **Validación:** `test_text_provenance_check_rejects_unknown_value`; `test_text_provenance_is_not_null`; skip si Docker no responde.

- [ ] 2.2 En la misma revisión: tabla `ai.sync_checkpoint` (PK `feed` texto; `watermark`, `since_id`, `last_full_sync_at`, `last_incremental_sync_at`, `last_aggregate_hash char(64)`, `indexed_count`). Ampliar `ai.sync_failure` con `cursor_since_id uuid` y `product_id uuid` nullable. Sin FK a `public`. **Validación:** `test_sync_checkpoint_table_exists`; `test_sync_failure_has_cursor_since_id_and_product_id`; downgrade drop de tabla y columnas nuevas; las seis tablas C05 siguen.

## 3. Mapa de procedencia

- [ ] 3.1 Script o comando documentado que lee `data/catalog/real/generated/catalog-real-enriched.jsonl` y `data/catalog/synthetic/generated/catalog-synthetic.jsonl` y escribe `ai-service/src/jbg_ai/indexing/sku_provenance.json` (`SKU → {data_origin, text_provenance}`). Correrlo **una vez** y commitear el JSON. Runtime solo carga ese fichero (el `Dockerfile` ya copia `src/`). **Validación:** el fichero existe bajo `src/`; no se lee `data/` en el camino de sync.

- [ ] 3.2 Test de invariante en el repo (lee `data/`): `test_provenance_map_matches_jsonl_union`. **Validación:** 1.200 claves; 436 `real` / 764 `synthetic`; 387 `ai_assisted` / 49 `merchant` / 764 `synthetic`; cero solapes; toda clave JSONL presente.

## 4. Cliente HTTP del feed

- [ ] 4.1 Puerto async `IndexFeedClient` + DTOs de página/ítem. `fetch_catalog_page(since, since_id)`; primera página omite query params. Header `X-Index-Feed-Key`. Mapear camelCase → `ProductSourceText` + `product_id`, `family_id`, `price`, `price_band`, `is_active`, `watermark`. Parsear `kind` `upsert` | `tombstone`. Método `fetch_pos_page` presente. Adapter `httpx.AsyncClient`. **Validación:** fake sin sockets; test de mapeo upsert; test de tombstone `{kind, productId, reason, at}`; POS no se invoca desde el orquestador (aserto en 6.x).

## 5. Repositorio Core

- [ ] 5.1 Puerto inyectable (get by `product_id`, upsert atómico fila+vector, delete, list ids para hash, count, get/put checkpoint, insert `sync_failure`). Implementación SQLAlchemy **Core** sobre el engine existente (`pool 5`, `max_overflow=0`). **No** mapped class. **No** segundo engine. Fake para tests. **Validación:** el fake cubre upsert/delete/checkpoint; ningún test de `tests/indexing/` abre RDS.

## 6. Orquestador (primera mitad 🔴)

- [ ] 6.1 Sync de una página: lookup de mapa (A3 al cargar; B4 por ítem); `build_source_text` / `hash_source_text`; skip-embed si hash igual y hay vector; UPDATE de columnas siempre; embed + UPSERT si no; tombstone DELETE idempotente; aislamiento por ítem → `sync_failure`. `skipped` = embed omitido. `embedding_version` = `document_version_key`. Cero INSERT con embedding NULL. **Validación:** `test_upsert_is_idempotent_for_same_source_hash` (cero llamadas al fake de embed; precio sí cambia); `test_tombstone_removes_document_from_index` (segundo tombstone no-op); `test_upsert_leaves_tsv_not_null`; `test_failed_item_recorded_and_does_not_block_others`; `test_orphan_sku_is_sync_failure`; `test_missing_map_writes_nothing`; `test_non_1536_vector_is_not_persisted`.

- [ ] 6.2 Dreno multi-página con precedencia `full` > body keyset > checkpoint; tope `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` consultado **tras cada ítem**; persistir checkpoint del último ítem OK; HTTP 200 con cursor parcial. Hash de conjunto (algoritmo `OfProductIds`: UUID `D`, ordenados, UTF-8, hex minúsculas). **Validación:** `test_full_ignores_body_and_checkpoint`; `test_body_keyset_overrides_checkpoint`; `test_incremental_without_body_uses_checkpoint`; `test_time_budget_persists_resume_cursor`; `test_set_hash_matches_known_vector` alineado con C12.

## 7. Router, auth y stub vs real

- [ ] 7.1 `index.py`: `get_catalog_principal`; si `stub_mode` → fixtures C02 (rellenar `since_id`/`cursor_id` nulos o deterministas); si no → orquestador. Importar `indexing` **desde el router**, no desde `api.main`. 503 si faltan feed URL/key, embed key o mapa, `detail` nombra la setting. Inyección `request.app.state` (feed, embed, repo) como `enrich_llm`. Documentar 503 en `V1_RESPONSES` de estas rutas. Actualizar o retirar `test_index_routes_still_name_c13`. **Validación:** `test_catalog_token_without_pos_is_accepted_on_index`; token sin `user_id`/`role`/`trace_id` → 401; `test_missing_feed_key_returns_503`; `test_stub_mode_still_returns_fixtures`; `test_main_does_not_import_indexing` sigue verde (fuente de `main.py`).

- [ ] 7.2 `batch_size` se ignora: warning una vez por proceso. **Validación:** `test_batch_size_is_ignored`.

## 8. OpenAPI keyset (BREAKING aditivo)

- [ ] 8.1 Ampliar `IndexSyncRequest` / `IndexSyncResponse` con `since_id` / `cursor_id` (uuid, opcionales). Regenerar `ai-service/openapi.json` con `canonical_openapi_settings` (one-liner del README). Alinear `sample_requests.py` si hace falta. **Validación:** `test_openapi_snapshot_is_stable` verde **después**; el schema incluye `since_id` y `cursor_id`; tests de contrato `/v1/index/*` en stub siguen en 200.

## 9. CLI

- [ ] 9.1 `python -m jbg_ai.indexing sync [--full]` llama a la **misma** función que el router. Reutiliza settings, engine y puertos. Sin cron. Sin segundo pool. **Validación:** test del entrypoint con fakes (`test_cli_sync_invokes_same_orchestrator`); `--full` arranca sin cursor.

## 10. Status, deriva, docs y verificación de alcance

- [ ] 10.1 `GET /v1/index/status` real: count + set-hash vs **un** GET de la primera página del feed (`aggregateHash`); `drift_count = 0` si iguales, si no `max(1, abs(indexed_documents − checkpoint.indexed_count))`. Feed caído → 503, no drift 0. Stub C02 intacto. **Validación:** `test_status_reports_drift_when_counts_diverge` (hashes distintos → `drift_count >= 1`; exactamente un GET al fake); hashes iguales → 0.

- [ ] 10.2 Enlazar HU-AIENG-013 en `Documentos/epicas.md` (EP14). Mencionar `text_provenance`, `sync_checkpoint` y deriva por hash en `Documentos/modelo-de-datos.md`. Actualizar el README de `ai-service` si el marcador C13 existe. **Validación:** un lector de la épica llega al pull del feed, al mapa en `src/`, al keyset OpenAPI y a «sin POS / sin `embeddings.py`».

- [ ] 10.3 Confirmar alcance negativo: `git diff` de `embeddings.py` vacío; no hay escritura a `ai.pos_projection` ni llamada POS; no hay migración EF ni cambios en `frontend/` / `IAiGatewayClient`. No hay TODO/FIXME sin tarea de seguimiento. **Validación:** diffs vacíos en esas rutas; `test_catalog_sync_does_not_call_pos_feed`.

- [ ] 10.4 `uv run --system-certs pytest tests/indexing tests/api tests/config tests/migrations` (y el snapshot OpenAPI) en verde **sin** sockets a proveedores ni al API .NET. Comparar **nombres** de fallos contra el baseline global si se corre `dotnet test` / la suite completa. Ejecutar **`openspec validate --all --strict`**. **Validación:** sin fallos **nuevos** en pytest de ai-service; la salida OpenSpec reporta `0 failed`.

Smoke local `indexed_documents = 1200` / `drift_count = 0` es **verificación posterior**, no una tarea de merge.
