# QA — C13 `add-product-document-indexer`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-26 · **Rama:** `c13-add-product-document-indexer` · **Commit de artefactos (HEAD, sin commit de implementación aún):** `12c8e79`
> **Seguimiento verify:** misma fecha. WARNING de cobertura cerrados (3 tests de orquestador). SUGGESTION cerradas: helper `build_httpx_feed_client` eliminado; `httpx` solo en runtime; `tests/README.md` marca C13 landed; POST `/sync` feed caído → 503. Suite completa al cierre: **315 passed**. Ver §1, §7 y §8.
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11.15 |
| Gestor | `uv` 0.11.7 — **con `--system-certs` en todas las llamadas `uv run`**, según `CLAUDE.md`. `uv lock` en esta máquina exigió `UV_NATIVE_TLS=true` (ver §8.1) |
| httpx | `≥0.28.1` **solo** en dependencias de runtime (`pyproject.toml` + `uv.lock`). El grupo `dev` ya no lo duplica. El `Dockerfile` hace `uv sync --frozen --no-dev` |
| Docker | contenedor `pgvector/pgvector:pg15` vía Testcontainers; una base nueva por test. **41/41** de `tests/migrations` corrieron, no se omitieron |
| Contrato | `ai-service/openapi.json` — **este change SÍ lo regenera** (opción B: `since_id` / `cursor_id`). `test_openapi_snapshot_is_stable` verde **después** |
| Freeze C11 | `git diff -- ai-service/src/jbg_ai/indexing/embeddings.py` **vacío** |
| .NET | **No se ejecuta** `dotnet test`: C13 no cruza `backend/src/`. Ver §4 |

---

## 1. Suite automática de `ai-service`

> **Aquí el recuento sí es fiable**, a diferencia de la suite de .NET: la de Python parte de cero fallos en este alcance y no llama a proveedores ni a `:5056`. C13 no toca .NET; no hay línea base de `dotnet test` que comparar.

| Ejecución | Resultado |
|---|---|
| Alcance C13 sin migraciones (`tests/indexing` + `tests/api` + `tests/config`) | **158 passed, 0 failed** (1 warning Starlette/httpx ajeno a C13), 4,72 s |
| `tests/migrations` (pgvector, Docker alcanzable) | **41 passed, 0 failed**, 29,83 s |
| Re-pasada indexing + rutas de índice + snapshot, tras limpiar el `Table` muerto de `repository.py` | **59 passed, 0 failed** |
| Re-pasada `tests/indexing/test_orchestrator.py` tras los 3 tests de cobertura del verify | **19 passed, 0 failed** |
| Cierre SUGGESTION: suite completa `uv run --system-certs pytest` | **315 passed, 0 failed** (1 warning Starlette/httpx), 29,06 s |
| `openspec validate --all --strict` | **41 passed, 0 failed** |

Comando de la pasada de alcance (tarea 10.4):

```powershell
uv run --system-certs pytest tests/indexing tests/api tests/config -q --tb=short
uv run --system-certs pytest tests/migrations -q --tb=short
openspec validate --all --strict
```

No se concatenó en una sola invocación; la suma del alcance pedido por la tarea es **199 passed, 0 failed** (158 + 41). El snapshot OpenAPI entra en `tests/api`.

### Desglose de tests nuevos o ampliados

| Fichero | Nº | Qué cubre |
|---|---|---|
| `tests/indexing/test_provenance_map.py` | 1 | 1.200 claves; 436/764 origen; 387/49/764 procedencia; unión JSONL; cero solapes |
| `tests/indexing/test_feed_client.py` | 10 | Mapeo camelCase upsert, tombstone `{kind, productId, reason, at}`, primera página sin query, keyset `since`/`sinceId`, header `X-Index-Feed-Key`, path POS presente, `kind` desconocido, `nextCursor`, 5xx/transporte → `IndexFeedConfigError`, 401 no se mapea |
| `tests/indexing/test_orchestrator.py` | 19 | Skip-embed + precio, rename de familia, tombstone idempotente, `tsv`/1536/`document_version_key`, aislamiento, embed fallido conserva fila previa, huérfano, mapa ausente, vector ≠ 1536, POS no llamado, precedencia de cursor, dreno de 2 páginas hasta `nextCursor` null, tope 180 s, hash C12, deriva, feed caído, `batch_size` ignorado |
| `tests/indexing/test_cli.py` | 2 | Misma función que el router; `--full` arranca sin cursor |
| `tests/api/test_index_routes.py` | 9 | Token de catálogo sin `pos_id`, 401 sin claim, 503 nombrando `JPV_INDEX_FEED_API_KEY`, no cae a `JWT_SECRET`, stub C02, puertos inyectados, status drift 0, body con `since_id`, feed caído → 503 y cero escrituras |
| `tests/migrations/test_c13_schema.py` | 6 | CHECK / NOT NULL de `text_provenance`, tabla `sync_checkpoint`, columnas nuevas de `sync_failure`, downgrade a `f46c55c056e2` deja las seis tablas C05, B-tree de procedencia |
| `tests/config/test_settings.py` (ampliado) | +3 | Feed key no bloquea boot, blank → unset / tope 180, pin canónico |
| `tests/api/test_health.py` (ampliado) | +1 | `GET /health` 200 sin `JPV_INDEX_FEED_*` |
| `tests/indexing/test_embeddings.py` (ajustado) | 0 nuevos | `test_index_routes_still_name_c13` **retirado**; sustituido por `test_index_routes_use_catalog_principal` (`get_catalog_principal`, sin `require_stub_mode`, el router sí importa `indexing`) |
| `tests/api/test_stub_mode.py` (ajustado) | 0 nuevos | `/v1/index/sync` y `/v1/index/status` **excluidos** del 501, igual que enrich C09 |
| `tests/api/test_contracts.py` (ampliado) | 0 nuevos | aserto de claves `since_id` / `cursor_id` en el stub |
| `tests/migrations/test_ai_schema_migration.py` (ampliado) | +1 caso | `EXPECTED_TABLES` incluye `sync_checkpoint`; B-tree parametrizado con `text_provenance` |
| `tests/migrations/test_ai_schema_invariants.py` (ajustado) | 0 nuevos | `_insert_product` escribe `text_provenance` (NOT NULL de C13) |

**51 tests nuevos** (1+10+19+2+9+6+3+1). **Fakes:** `tests/support/index_fakes.py` (`FakeIndexFeedClient`, `FakeEmbeddingClient`, `FakeProductDocumentRepo`). El feed HTTP de unidad usa `httpx.MockTransport`. Ningún test de `tests/indexing/` abre socket a OpenAI, LiteLLM, `:5056` ni RDS.

---

## 2. Escenarios de las specs, uno a uno

### `product-document-indexer`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Catalog sync drains the feed · A full sync pages until the feed is exhausted | `test_full_sync_pages_until_next_cursor_is_null` (2 GET; segundo con el cursor de la página 1; ambos ítems upserted) | ✅ |
| Catalog sync drains the feed · Time budget persists a resume cursor instead of failing | `test_time_budget_persists_resume_cursor` (HTTP 200 implícito en el result; checkpoint del último ítem OK; el segundo ítem no se escribe) | ✅ |
| Catalog sync drains the feed · batch_size does not change the feed page | `test_batch_size_is_ignored` (warning una vez; `page_size` del fake = 50) | ✅ |
| Catalog sync drains the feed · full ignores body and checkpoint | `test_full_ignores_body_and_checkpoint` | ✅ |
| Catalog sync drains the feed · Body keyset overrides the checkpoint | `test_body_keyset_overrides_checkpoint` | ✅ |
| Catalog sync drains the feed · Incremental without body uses the checkpoint | `test_incremental_without_body_uses_checkpoint` | ✅ |
| Same source hash skips embed · Unchanged text is not re-embedded and price is updated | `test_upsert_is_idempotent_for_same_source_hash` (1 sola llamada al fake; `price` / `price_band` nuevos; `skipped == 1`) | ✅ |
| Same source hash skips embed · A family name rename re-embeds | `test_family_name_rename_re_embeds` (`source_hash` cambia; 2ª llamada a embed; `upserted == 1`) | ✅ |
| Tombstones delete the document · A tombstone removes an indexed document | `test_tombstone_removes_document_from_index` (`deleted == 1`) | ✅ |
| Tombstones delete the document · A repeated tombstone is a no-op | misma función, segunda pasada (`deleted == 0`, `failures == []`) | ✅ |
| Status reports set drift · Matching set hashes report zero drift | `test_status_reports_drift_when_counts_diverge` (rama igual) · `test_real_status_reports_zero_drift_when_hashes_match` (exactamente un GET) | ✅ |
| Status reports set drift · Divergent set hashes report a positive drift | `test_status_reports_drift_when_counts_diverge` (`drift_count >= 1`, un GET) · `test_status_feed_down_is_explicit_error` (`IndexFeedConfigError`, no drift 0) | ✅ |
| A failed item is recorded · An orphan SKU fails and siblings succeed | `test_orphan_sku_is_sync_failure` | ✅ |
| A failed item is recorded · An embed failure keeps the previous row | `test_embed_failure_keeps_previous_row` (re-embed de fila indexada; vector 0.42 intacto; sibling upserted) | ✅ |
| Missing map or feed settings refuse · Absent feed key is a named 503 | `test_missing_feed_key_returns_503` · `test_missing_feed_key_does_not_fall_back_to_jwt` · `test_health_starts_without_index_feed_key` | ✅ |
| Missing map or feed settings refuse · Absent provenance map writes nothing | `test_missing_map_writes_nothing` | ✅ |
| Missing map or feed settings refuse · Stub mode still returns fixtures | `test_stub_mode_still_returns_fixtures` (200, cero llamadas a feed/embed/repo) | ✅ |
| Provenance map is committed in src · Map cardinality matches the corpus | `test_provenance_map_matches_jsonl_union` (1.200 / 436 / 764 / 387 / 49 / 764) | ✅ |
| Provenance map is committed in src · Origin is not guessed from SKU shape | `test_orphan_sku_is_sync_failure` (SKU999 no se defaulta a `synthetic`) | ✅ |
| Index routes accept a catalog token · Catalog token without pos_id is accepted | `test_catalog_token_without_pos_is_accepted_on_index` · `test_index_token_missing_required_claim_is_401` | ✅ |
| Index routes accept a catalog token · Feed requests carry the service API key | `test_first_catalog_page_omits_query_params` (`X-Index-Feed-Key` = la key inyectada, no JWT) | ✅ |
| Feed client is reusable · POS feed is not called during catalog sync | `test_catalog_sync_does_not_call_pos_feed` · `test_pos_path_is_present_on_the_client` | ✅ |
| Feed client is reusable · embeddings.py stays frozen | `git diff` de `embeddings.py` vacío · `test_main_does_not_import_indexing` | ✅ |
| No visible row without 1536-d embedding · Upsert leaves tsv and embedding present | `test_upsert_leaves_tsv_not_null` (`embedding_version == document_version_key`) | ✅ |
| No visible row without 1536-d embedding · A non-1536 vector is not persisted | `test_non_1536_vector_is_not_persisted` (384 → `failed == 1`, sin fila) | ✅ |
| Indexer tests inject fakes · Indexer unit suite stays offline | fakes + `MockTransport`; `test_unit_suite_makes_no_provider_calls` (fuente de `main.py`) | ✅ |
| Indexer tests inject fakes · Suite does not demand a live 1200-row index | ningún test de esta pasada exige 1.200 filas en Docker/proveedor | ✅ |

### `ai-vector-schema`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Synchronization checkpoint · Catalog checkpoint round-trips a keyset | `test_time_budget_persists_resume_cursor` (watermark + `since_id`) · `test_sync_checkpoint_table_exists` | ✅ |
| Synchronization checkpoint · Revert drops the checkpoint table | `test_c13_downgrade_drops_new_objects_and_keeps_c05_tables` | ✅ |
| Structural filter columns are indexed · text provenance B-tree | `test_text_provenance_has_btree_index` · `test_structural_filter_column_has_btree_index[text_provenance]` | ✅ |
| Product documents closed vocabularies · Text provenance is restricted | `test_text_provenance_check_rejects_unknown_value` | ✅ |
| Product documents closed vocabularies · Text provenance cannot be null | `test_text_provenance_is_not_null` | ✅ |
| Product documents closed vocabularies · Data origin is restricted | `test_product_document_rejects_data_origin_outside_vocabulary` (C05, sigue verde) | ✅ |
| Product documents closed vocabularies · Embedding may be absent | `test_product_document_accepts_row_without_embedding` (esquema C05; el **escritor** C13 no usa esa ventana — `test_non_1536_vector_is_not_persisted`) | ✅ |
| Product documents closed vocabularies · Reverting leaves no vocabulary type behind | `test_upgrade_downgrade_is_reversible` (sin ENUM; CHECK) | ✅ |
| Synchronization failures · A failure is recorded with enough context | `test_orphan_sku_is_sync_failure` (`product_id`) · `test_sync_failure_has_cursor_since_id_and_product_id` · `test_sync_failure_records_enough_context_to_retry` | ✅ |
| Synchronization failures · Retry queue is indexed | `test_retry_queue_is_indexed` (C05, sigue verde) | ✅ |

### `ai-service-api-contracts`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Index sync contract carries a keyset · Sync request and response expose the keyset | `test_sync_request_accepts_since_id` · `test_index_sync_and_status_expose_counters_and_drift` | ✅ |
| Index sync contract carries a keyset · Snapshot matches the live schema after regeneration | `test_openapi_snapshot_is_stable` (verde **después** del one-liner del README) | ✅ |
| Inventory / enrichment contracts frozen | `test_inventory_proposals_are_prioritized` · tests de enrich en stub (C08/C09) — siguen en 200 | ✅ |
| Index sync and status expose counters and drift | `test_index_sync_and_status_expose_counters_and_drift` (`since_id` / `cursor_id` presentes) | ✅ |

### `ai-service-runtime`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Index feed settings do not block boot · Health starts without a feed key | `test_settings_do_not_require_index_feed_key_to_boot` · `test_health_starts_without_index_feed_key` (tope 180) | ✅ |
| Index feed settings do not block boot · Blank feed strings are treated as unset | `test_blank_index_feed_strings_are_treated_as_unset` | ✅ |
| Index feed settings do not block boot · Canonical OpenAPI settings pin feed keys to absent | `test_canonical_openapi_settings_pin_index_feed_keys_to_absent` · `test_openapi_snapshot_is_stable` | ✅ |
| Index feed settings do not block boot · Real sync does not use JWT_SECRET as the feed key | `test_missing_feed_key_does_not_fall_back_to_jwt` | ✅ |

### `catalog-source-text`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| HTTP application does not import the indexing library · The application factory stays decoupled | `test_main_does_not_import_indexing` (lee el **fuente** de `main.py`) | ✅ |
| HTTP application does not import the indexing library · embeddings.py stays frozen | `git diff` vacío · `test_adapter_does_not_import_data_or_enrich_llm` | ✅ |

**Totales de escenarios `#### Scenario:` en los deltas:** 26 (`product-document-indexer`) + 10 (`ai-vector-schema`) + 8 (`ai-service-api-contracts`, 2 ADDED + 6 MODIFIED) + 4 (`ai-service-runtime`) + 2 (`catalog-source-text`) = **50**. Los 50 tienen test nombrado. Tres se añadieron tras `/opsx:verify` (§8.2).

---

## 3. Nombres exigidos por `tasks.md` / ticket

Lista de la ficha C13. Todos existen como `def test_…` y están en verde.

| Nombre | Fichero |
|---|---|
| `test_settings_do_not_require_index_feed_key_to_boot` | `test_settings.py` |
| `test_canonical_openapi_settings_pin_index_feed_keys_to_absent` | `test_settings.py` |
| `test_text_provenance_check_rejects_unknown_value` | `test_c13_schema.py` |
| `test_text_provenance_is_not_null` | `test_c13_schema.py` |
| `test_sync_checkpoint_table_exists` | `test_c13_schema.py` |
| `test_sync_failure_has_cursor_since_id_and_product_id` | `test_c13_schema.py` |
| `test_provenance_map_matches_jsonl_union` | `test_provenance_map.py` |
| `test_upsert_is_idempotent_for_same_source_hash` | `test_orchestrator.py` |
| `test_tombstone_removes_document_from_index` | `test_orchestrator.py` |
| `test_upsert_leaves_tsv_not_null` | `test_orchestrator.py` |
| `test_failed_item_recorded_and_does_not_block_others` | `test_orchestrator.py` |
| `test_orphan_sku_is_sync_failure` | `test_orchestrator.py` |
| `test_missing_map_writes_nothing` | `test_orchestrator.py` |
| `test_non_1536_vector_is_not_persisted` | `test_orchestrator.py` |
| `test_full_ignores_body_and_checkpoint` | `test_orchestrator.py` |
| `test_body_keyset_overrides_checkpoint` | `test_orchestrator.py` |
| `test_incremental_without_body_uses_checkpoint` | `test_orchestrator.py` |
| `test_time_budget_persists_resume_cursor` | `test_orchestrator.py` |
| `test_set_hash_matches_known_vector` | `test_orchestrator.py` |
| `test_catalog_token_without_pos_is_accepted_on_index` | `test_index_routes.py` |
| `test_missing_feed_key_returns_503` | `test_index_routes.py` |
| `test_stub_mode_still_returns_fixtures` | `test_index_routes.py` |
| `test_main_does_not_import_indexing` | `test_embeddings.py` |
| `test_batch_size_is_ignored` | `test_orchestrator.py` |
| `test_openapi_snapshot_is_stable` | `test_openapi_snapshot.py` |
| `test_cli_sync_invokes_same_orchestrator` | `test_cli.py` |
| `test_status_reports_drift_when_counts_diverge` | `test_orchestrator.py` |
| `test_catalog_sync_does_not_call_pos_feed` | `test_orchestrator.py` |

`test_index_routes_still_name_c13` se **retiró** a propósito (tarea 7.1: actualizar o retirar). El reemplazo es `test_index_routes_use_catalog_principal`.

Extras que cubren escenarios o validaciones de tarea no nombrados en la ficha: `test_blank_index_feed_strings_are_treated_as_unset`, `test_health_starts_without_index_feed_key`, `test_catalog_upsert_maps_camel_case_onto_source_text`, `test_catalog_tombstone_parses_kind_product_reason_at`, `test_first_catalog_page_omits_query_params`, `test_subsequent_catalog_page_sends_since_and_since_id`, `test_pos_path_is_present_on_the_client`, `test_c13_downgrade_drops_new_objects_and_keeps_c05_tables`, `test_text_provenance_has_btree_index`, `test_missing_feed_key_does_not_fall_back_to_jwt`, `test_index_token_missing_required_claim_is_401`, `test_real_sync_uses_injected_ports`, `test_real_status_reports_zero_drift_when_hashes_match`, `test_sync_request_accepts_since_id`, `test_status_feed_down_is_explicit_error`, `test_cli_full_flag_parses`, `test_full_sync_pages_until_next_cursor_is_null`, `test_family_name_rename_re_embeds`, `test_embed_failure_keeps_previous_row`, `test_sync_feed_down_returns_503_and_writes_nothing`, `test_catalog_5xx_is_feed_unavailable`, `test_catalog_401_is_not_mapped_to_unavailable`, `test_catalog_transport_error_is_feed_unavailable`.

---

## 4. Alcance negativo (tarea 10.3)

```powershell
git diff --stat -- ai-service/src/jbg_ai/indexing/embeddings.py frontend/ backend/src/JoiabagurPV.Application/Interfaces/IAiGatewayClient.cs backend/src/JoiabagurPV.Infrastructure/Data/Migrations/
```

Salida **vacía**.

| Guardarraíl | Comprobación | Resultado |
|---|---|---|
| `indexing/embeddings.py` | `git diff` vacío contra HEAD | ✅ |
| `jbg_ai.api.main` no menciona `jbg_ai.indexing` | `test_main_does_not_import_indexing` (fuente, no el grafo de imports del proceso) | ✅ |
| Feed POS no se llama | `test_catalog_sync_does_not_call_pos_feed`; `fetch_pos_page` existe y el orquestador no lo invoca | ✅ |
| `ai.pos_projection` | ninguna escritura en `jbg_ai/indexing/` (`rg pos_projection` vacío salvo el método POS del cliente) | ✅ |
| Migración EF | `git diff` de `Infrastructure/Data/Migrations/` vacío | ✅ |
| `IAiGatewayClient` | `git diff` vacío; no hay operación nueva hacia `/v1/index/sync` | ✅ |
| `frontend/` | `git diff` vacío | ✅ |
| TODO/FIXME sin seguimiento | `rg TODO\|FIXME` en `jbg_ai/indexing/` vacío | ✅ |
| Tres secretos | `JPV_INDEX_FEED_API_KEY` ≠ `JWT_SECRET` ≠ `JPV_EMBEDDING_API_KEY`; Compose usa `local-dev-index-feed-key-0123456789ab` | ✅ |

`backend/.env.example` y `backend/docker-compose.yml` **sí** se documentan (URL/key de feed, `extra_hosts`). Fuera de `backend/src/`. `ai-service/openapi.json` **sí** cambia: es el breaking aditivo del change, no un escape del freeze.

---

## 5. Decisiones de diseño, verificadas en código

| Decisión | Evidencia |
|---|---|
| 1 · Stub vs real en el handler, como C09 | `routers/index.py`: `stub_mode` → fixtures; si no, orquestador o 503. `get_catalog_principal`. Import de `indexing` **solo** desde el router. `INDEX_RESPONSES` documenta 503 |
| 2 · OpenAPI keyset (opción B) | `IndexSyncRequest.since_id` / `IndexSyncResponse.cursor_id`; snapshot regenerado con `canonical_openapi_settings`; stub rellena los campos (null) |
| 3 · Precedencia `full` > body keyset > checkpoint | `resolve_start_cursor`; tres tests dedicados; tope consultado tras cada ítem |
| 4 · Cliente reutilizable; C13 solo drena catálogo | `IndexFeedClient.fetch_catalog_page` + `fetch_pos_page`; orquestador no llama POS |
| 5 · Mapa en `src/` (A3 + B4) | `sku_provenance.json` (1.200 claves, generado una vez); runtime `load_provenance_map`; A3 = 503 / cero escrituras; B4 = `sync_failure` y el resto sigue |
| 6 · Alembic a mano | revisión `b8e3c1a4d7f0` hija de `f46c55c056e2`; CHECK no ENUM; downgrade deja las seis tablas C05 |
| 7 · Skip-embed ≠ skip-fila; cero vector NULL visible | `test_upsert_is_idempotent_for_same_source_hash`; `test_non_1536_vector_is_not_persisted` |
| 8 · `drift_count` por hash de conjunto, un GET | `of_product_ids` (UUID `D`, orden .NET `Guid.CompareTo`, SHA-256); `report_index_status` llama `fetch_catalog_page` una vez |
| 9 · Core + un solo pool | `SqlAlchemyProductDocumentRepo` sobre `session_scope` / engine existente; fake en tests; **no** mapped class |
| 10 · Settings opcionales; tercer secreto; pin | `jpv_index_feed_*` blank→unset; tope blank→180; `canonical_openapi_settings` pinna URL/key a `None` |

CLI: `python -m jbg_ai.indexing sync [--full]` → `run_cli_sync` → `sync_catalog` (la misma función que el POST).

---

## 6. Documentación de contexto (tarea 10.2)

| Documento | Qué se alineó |
|---|---|
| `Documentos/epicas.md` (EP14) | HU-AIENG-013 + bloque C13: pull del feed, mapa en `src/`, OpenAPI keyset, **sin POS / sin `embeddings.py`** |
| `Documentos/modelo-de-datos.md` | `text_provenance` NOT NULL + CHECK; tabla `sync_checkpoint`; `sync_failure` gana `cursor_since_id` / `product_id`; deriva por hash de conjunto (un GET); B-tree de procedencia |
| `ai-service/README.md` | Marcador C13 (ya no es stub); tabla `JPV_INDEX_FEED_*`; 503 vs 501; CLI; layout de `indexing/` |
| `ai-service/tests/README.md` | C13 landed en `indexing/` (drain + `sku_provenance.json`); también anotado en `api/`, `config/` y `migrations/` |
| `backend/.env.example` | `JPV_INDEX_FEED_BASE_URL` / `API_KEY` / tope 180; placeholder ≠ `JWT_SECRET` |
| `backend/docker-compose.yml` | `jbg-ai` → `http://host.docker.internal:5056` + `extra_hosts` `host-gateway` |
| [ticket.md](ticket.md) / [tasks.md](tasks.md) | 17/17 tareas marcadas; DoD cubierto por los tests de §3 |

---

## 7. OpenSpec

```powershell
openspec validate --all --strict
```

**41 passed, 0 failed.** Incluye el change `add-product-document-indexer` y todas las specs vivas. Ejecutado en la forma `--all --strict`, no en la de un solo change (`CLAUDE.md`).

`openspec status --change add-product-document-indexer` (al arrancar el apply): artefactos proposal/design/specs/tasks **done**. Al cierre: 17/17 tareas marcadas.

`/opsx:verify` se ejecutó el 2026-08-26. Scorecard inicial: Completeness 17/17, Correctness 47/50 escenarios, 3 WARNING + 4 SUGGESTION. Misma fecha: WARNING cerrados (50/50); SUGGESTION cerradas (§8.4). Cero CRITICAL. El informe va en el chat de verify, no se duplica aquí.

---

## 8. Incidencias y huecos de esta pasada

### 8.1. `uv lock` y el certificado de PyPI

`uv lock` sin TLS nativo falló con `invalid peer certificate: UnknownIssuer` (el mismo síntoma que `CLAUDE.md` documenta para `uv sync` / `uv run`). **Corrección de entorno, no de código:** `$env:UV_NATIVE_TLS = "true"; uv lock`. El lock resultante mueve `httpx` a las dependencias de runtime del paquete `jbg-ai`, necesario porque el `Dockerfile` instala con `--no-dev`.

### 8.2. Tres escenarios de spec sin test homónimo — **cerrados tras verify**

Los tres WARNING del verify se cubrieron en `tests/indexing/test_orchestrator.py` (19 passed):

| Escenario | Test | Aserto |
|---|---|---|
| Full sync pages until `nextCursor` is null | `test_full_sync_pages_until_next_cursor_is_null` | 2 GET; segundo `(TS, A)`; ambos ítems con embedding |
| Family name rename re-embeds | `test_family_name_rename_re_embeds` | `source_hash` cambia; `len(embed.calls) == 2`; `upserted == 1` |
| Embed failure keeps the previous row | `test_embed_failure_keeps_previous_row` | vector 0.42 y hash previos intactos; sibling upserted; `sync_failure` del rename |

### 8.3. `Table` muerto en el primer borrador del repo

La primera versión de `repository.py` declaraba un `Table("product_document")` con tipos de array incorrectos y no lo usaba: los writes van por `text()` SQL. Se eliminó antes del cierre. La re-pasada de 59 tests siguió verde. No es un fallo de schema: Alembic va a mano y los tests de migraciones no pasan por ese `Table`.

### 8.4. SUGGESTION del verify — **cerradas**

| SUGGESTION | Corrección |
|---|---|
| Helper `build_httpx_feed_client` | Eliminado. Filtraba un `AsyncClient` sin `async with`. Router y CLI siguen construyendo el cliente en un context manager |
| `httpx` duplicado en `dev` | Quitado del grupo `dev`; `uv lock` deja `httpx` solo en runtime (`[package.dev-dependencies]` = pytest + testcontainers) |
| `tests/README.md` sin C13 landed | Celda `indexing/` y filas `api/` / `config/` / `migrations/`; párrafo «Populated after C13» |
| POST `/sync` feed caído → 500 | Adapter mapea transporte/5xx a `IndexFeedConfigError`; 4xx no. Router POST → 503. `test_sync_feed_down_returns_503_and_writes_nothing` |

---

## 9. Fuera de esta pasada (no DoD)

- Smoke local `POST /v1/index/sync {"full": true}` contra `:5056` + OpenAI hasta `indexed_documents = 1200` / `drift_count = 0`. La ficha lo deja como **verificación posterior**.
- Suite global de .NET / `dotnet test` nombre-a-nombre: C13 no toca `backend/src/`.
- Scheduler 5–10 min, dreno POS, `ai.pos_projection` (C22).
- `POST /v1/retrieval/products` real (C14).
- Editar `indexing/embeddings.py` (congelado para C23).

---

## Veredicto

**Sin problemas críticos.** Suite completa al cierre: **315 passed, 0 failed** (`uv run --system-certs pytest`, 29,06 s). Snapshot OpenAPI verde **después** de regenerar, `openspec validate --all --strict` 41/0, diffs vacíos en `embeddings.py` / EF / `frontend/` / `IAiGatewayClient`, 17/17 tareas, 50/50 escenarios, 4/4 SUGGESTION del verify cerradas.

**Listo para archivar.**
