## Why

C11 dejó una biblioteca que `api.main` no importa y C12 un feed HTTP que Python aún no consume. `/v1/index/sync` y `/v1/index/status` son el stub C02: con `STUB_MODE=false` responden 501. Sin este change, C14 consulta HNSW sobre cero filas (fallo mudo de S11) o bien viola el §6.3 leyendo `public`. Se hace ahora porque C11 y C12 están archivados, AutoBulk de los 1.200 ya corrió, y C13 nunca se recorta.

## What Changes

- **`POST /v1/index/sync` y `GET /v1/index/status` reales** cuando `STUB_MODE=false` (patrón C09). Con `STUB_MODE=true` siguen los fixtures C02. Auth de catálogo: `get_catalog_principal` (sin `pos_id`), alineado con `ai-service-auth`.
- **Cliente HTTP reutilizable del feed** (C22 lo importará): header `X-Index-Feed-Key`, keyset `(since, sinceId)`, parseo de `kind`. C13 **solo drena el catálogo**. El cliente acepta el path POS; este change no lo llama.
- **Upsert por `product_id`**. Idempotencia = no llamar al proveedor de embeddings si `source_hash` coincide y hay vector 1536; el UPSERT de columnas (precio, `price_band`, familia, tags, `is_active`, procedencia, `indexed_at`) corre siempre. `skipped` cuenta embeber omitido, no fila ignorada. Tombstone = `DELETE` idempotente.
- **Mapa commiteado** `src/jbg_ai/indexing/sku_provenance.json` (SKU → `{data_origin, text_provenance}`), generado una vez desde los JSONL. Mapa ausente → el sync real no escribe. SKU huérfano → ese ítem a `sync_failure`, el resto sigue. **Sin default** `synthetic`/`merchant`.
- **Alembic (una revisión, a mano):** `ai.product_document.text_provenance` NOT NULL + CHECK + índice B-tree; tabla `ai.sync_checkpoint`; `sync_failure` gana `cursor_since_id` y `product_id`.
- **BREAKING (aditivo, OpenAPI):** `since_id` / `cursor_id` (uuid) en request/response de sync. `batch_size` se ignora (warning; la página es 50 de C12). Snapshot regenerado.
- **Checkpoint keyset persistido.** Un POST con `full=true` (o sin checkpoint) drena las páginas de catálogo. Tope de tiempo configurable (default **180 s**): si se agota, se persiste checkpoint y se devuelve cursor + contadores parciales (HTTP 200). CLI `python -m jbg_ai.indexing sync` sobre la misma función.
- **`drift_count`:** SHA-256 del conjunto de `product_id` en `ai.product_document` vs `aggregateHash` de **una** GET a la primera página del feed. Status no pagina 24 veces.
- **Settings `JPV_INDEX_FEED_BASE_URL` / `JPV_INDEX_FEED_API_KEY`** (y tope de tiempo) opcionales al boot; 503 al sync real si faltan, nombrando la setting. `/health` no las exige. **Prohibido** caer a `JWT_SECRET`.

**Fuera de alcance:** sincronizar `ai.pos_projection` ni drenar el feed POS (C22); scheduler 5–10 min (C22); HTTP *push* .NET → Python; migración EF Core; columna `DataOrigin` en `Product`; `POST /v1/retrieval/products` real (C14); tocar `indexing/embeddings.py`; `ai.query_log`; chunking de catálogo; regenerar JSONL; reejecutar AutoBulk; UI / frontend / RDS (C17). Un pytest **no** exige 1.200 filas reales.

## Capabilities

### New Capabilities

- `product-document-indexer`: orquestador de sync de catálogo — cliente HTTP del feed (API Key, keyset, `kind`), mapa de procedencia en `src/`, upsert por hash con skip-embed, tombstones, aislamiento por ítem, checkpoint keyset, tope de tiempo, CLI, y status de deriva por hash de conjunto. Cero fila visible sin embedding 1536. Python no lee `public`.

### Modified Capabilities

- `ai-vector-schema`: columna `text_provenance` NOT NULL + CHECK (`merchant` | `ai_assisted` | `synthetic`) + índice B-tree; tabla `ai.sync_checkpoint` (una fila por feed, cursor keyset); `ai.sync_failure` gana `cursor_since_id` y `product_id`. Sin ENUM. Sin FK a `public`.
- `ai-service-api-contracts`: **BREAKING** aditivo — `IndexSyncRequest`/`Response` llevan `since_id` / `cursor_id`; `batch_size` se ignora. Con `STUB_MODE=false` las rutas de índice dejan de ser 501 y ejecutan el pipeline. El snapshot `openapi.json` se regenera.
- `ai-service-runtime`: settings `JPV_INDEX_FEED_BASE_URL`, `JPV_INDEX_FEED_API_KEY` y `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` (default 180) opcionales al arrancar; `GET /health` no las exige. El sync real sí las exige (junto con `JPV_EMBEDDING_API_KEY` y el mapa) y, si faltan, responde 503 nombrando la setting. Pin en `canonical_openapi_settings`.
- `catalog-source-text`: se levanta el no-objetivo C11 de que `/v1/index/*` siga en stub y de que `openapi.json` no se regenerue. `jbg_ai.api.main` **sigue** sin importar `indexing`; el router de índice sí. `embeddings.py` permanece congelado.

`ai-service-auth` **no lleva delta**: ya exige token de catálogo sin `pos_id` en las rutas de índice; C13 implementa `get_catalog_principal` para cumplirlo. `index-feed` no cambia: C13 consume, no modifica el API .NET. `embedding-management` (visual 1280d) **no se toca**. `catalog-enrichment-pipeline` no cambia.

## Impact

**`jbg-ai`** — cliente de feed, orquestador, mapa `sku_provenance.json`, CLI y repositorio Core bajo `indexing/` (**sin** editar `embeddings.py`); router `/v1/index/*` sustituye el stub cuando `stub_mode` es falso; schemas Pydantic con keyset; settings de feed; una revisión Alembic a mano; `openapi.json` **regenerado**; tests en `tests/indexing/`, `tests/api/` y `tests/migrations/` con fakes (cero sockets a OpenAI ni al API .NET). El HTTP **sí** importa `indexing` desde el router.

**Backend .NET / frontend / terraform / migraciones EF** — sin cambios de código. Completar `backend/.env.example` y Compose con URL/key de feed (placeholder; contenedor: `host.docker.internal:5056`). Producción: SSM en **C17**. `IAiGatewayClient` **no** gana operación de índice.

**Documentación** — `Documentos/epicas.md` (EP14) enlaza HU-AIENG-013 en el apply; `Documentos/modelo-de-datos.md` menciona `text_provenance`, `sync_checkpoint` y deriva.

**Dependientes desbloqueados:** C14 (retriever vectorial) y, en cascada, C18. C22 reutiliza el cliente HTTP. No paralelizar con C23. El valor de producto no es visible: no hay pantalla. El smoke `indexed_documents = 1200` / `drift_count = 0` es verificación **posterior**, no criterio de merge.
