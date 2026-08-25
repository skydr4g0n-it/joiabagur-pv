## Why

C05 dejó `ai.product_document` con `doc_text`, `source_hash` y `embedding vector(1536)` vacía; C09 extrae perfiles reales. Sin un texto canónico estable y un cliente que no vuelva a pagar el modelo si el hash no cambió, C13 tendría que inventar el `SourceText` dentro del *upsert* y C14/C23 reimplementarían el cliente. Se hace ahora porque C05 y C09 están archivados, el plan congela `indexing/embeddings.py` aquí, y prohíbe C11 ‖ C13.

## What Changes

- **Biblioteca `jbg_ai.indexing`**: constructor `build_source_text` con plantilla `source-text/v1` (orden fijo, etiquetas en español, materiales y tags ordenados alfabéticamente, ausentes omitidos) y `hash_source_text` SHA-256 del `doc_text` UTF-8. No hay HTTP, no hay SQL, `create_app` no importa el paquete.
- **Puerto `EmbeddingClient`** con adapter LiteLLM `aembedding`, default `openai/text-embedding-3-small`, assert `len(vector) == 1536`, *batching* (`JPV_EMBEDDING_BATCH_SIZE`, default 64), backoff en 429/5xx, caché in-memory por `(digest, model, version)`. `embed()` es `async`.
- **Dos claves de versión**: `document_version_key = {model}:1536:source-text/v1` (lo que C13 persistirá) y `model_version_key = {model}:1536` (lo que C14 usará para no mezclar modelos; la query no se persiste).
- **Settings `JPV_EMBEDDING_*`** (`API_KEY`, `MODEL`, `BASE_URL`, `BATCH_SIZE`) opcionales al boot; exigidas al embeber. **Sin fallback** a `JPV_RAG_LLM_API_KEY`. Pin en `canonical_openapi_settings`. Completar `backend/.env.example` (`BASE_URL`, `BATCH_SIZE`).
- **Tests** en `ai-service/tests/indexing/` con fake inyectable. Cero sockets a proveedores ni RDS. Sin marcador `db`.

**Fuera de alcance:** `POST /v1/index/sync` / `GET /v1/index/status` (C13); feed HTTP .NET (C12, **después**); escribir `ai.product_document`; ORM/SQLAlchemy de las tablas C05; `price` / `price_band` / UUID de familia / `source` / confianza en el texto; Redis o tabla de caché; *blue/green* de modelo; embeddings visuales 1280d; regenerar `openapi.json`; AutoBulk sobre los 1.200.

Sin breaking changes de contrato REST ni OpenAPI. C13 pasará de 501 a lógica real; C11 no lo hace.

## Capabilities

### New Capabilities

- `catalog-source-text`: constructor canónico `source-text/v1` del `doc_text` de catálogo, `source_hash` SHA-256 del texto renderizado, y cliente de embeddings inyectable (LiteLLM, dimensión 1536, *batch*, backoff, caché de proceso) que C13, C14 y C23 reutilizarán sin reimplementar.

### Modified Capabilities

- `ai-service-runtime`: las settings `JPV_EMBEDDING_*` (`API_KEY`, `MODEL`, `BASE_URL`, `BATCH_SIZE` con default 64) son opcionales al arrancar; `GET /health` no las exige. Embeber de verdad exige `JPV_EMBEDDING_API_KEY` y **no** cae a `JPV_RAG_LLM_API_KEY`. `canonical_openapi_settings` las pinna a ausentes / default de batch.

`ai-service-api-contracts` **no lleva delta**: no hay ruta nueva ni cambio de schema. `ai-vector-schema` no cambia: C11 no abre Alembic ni escribe filas; C05 ya fijó `vector(1536)` y el operator class de coseno. `product-ai-profile` no cambia: su `SourceHash` es el de las entradas del extractor, distinto propósito. `embedding-management` (reconocimiento visual 1280d) **no se toca**. `catalog-enrichment-pipeline` no cambia: C11 no llama al extractor.

## Impact

**`jbg-ai`** — paquete `indexing/` nuevo (`source_text.py`, `embeddings.py` congelado); settings `JPV_EMBEDDING_*`; tests en `tests/indexing/` y fake en `tests/support/`; pin en `canonical_openapi_settings`. `litellm==1.98.0` ya está en `pyproject.toml`; no hace falta dependencia nueva. `jbg_ai.api.main` **no** importa `indexing`. `/v1/index/*` sigue siendo el stub de C13.

**`ai-service/openapi.json`** — **no se regenera**. Si `test_openapi_snapshot_is_stable` se pone rojo, el change se ha salido de alcance.

**Backend .NET / frontend / terraform / migraciones** — sin cambios de código. Solo completar `backend/.env.example` con `JPV_EMBEDDING_BASE_URL` y `JPV_EMBEDDING_BATCH_SIZE`.

**Documentación** — `Documentos/epicas.md` (EP12) enlaza HU-AIENG-011.

**Dependientes desbloqueados:** C13 (indexador) y C23 (corpus de conocimiento). C12 no es prerrequisito de *este* código; sí del primer sync. El valor de producto no es visible: no hay pantalla ni ruta nueva.
