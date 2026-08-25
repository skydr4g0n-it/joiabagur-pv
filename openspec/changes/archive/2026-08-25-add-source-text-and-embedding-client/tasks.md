> **Línea de corte.** Los grupos 1–2 son la mitad que **desbloquea diseñar C13**: settings, DTO, constructor `source-text/v1` y tests de estabilidad del hash. Si la sesión se desborda (ficha C11 / regla 5 del plan), se entrega esa mitad. Los grupos 3–4 son el cliente LiteLLM (puerto, fake, caché, assert 1536, batch, backoff). Sin ellos C13 no puede llamar al proveedor, así que esa segunda mitad sigue siendo 🔴.

> **Guardarraíl de contrato.** Este change **no toca** `ai-service/openapi.json`, `ai-service/migrations/`, entidades .NET, routers `/v1/index/*` ni `jbg_ai.api.main` (salvo que un test demuestre que **no** importa `indexing`). Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance: no se regenera el snapshot.

> **Guardarraíl de boot.** `JPV_EMBEDDING_*` son **opcionales** en `Settings`. `/health` no las exige. No hay fallback a `JPV_RAG_LLM_API_KEY`. `canonical_openapi_settings` las pinna a ausentes / batch 64.

> **Guardarraíl de tests.** La suite de `tests/indexing/` usa un `EmbeddingClient` falso. Cero sockets a proveedores ni RDS. Sin marcador `db`. Sin Testcontainers. Nombres `test_<unidad>_<escenario>_<esperado>`.

## 1. Andamiaje y settings

- [x] 1.1 Crear el paquete `ai-service/src/jbg_ai/indexing/` (`__init__.py` de reexport mínimo) y `ai-service/tests/indexing/`. **No** añadir dependencia nueva: `litellm==1.98.0` ya está en `pyproject.toml`. **Validación:** los directorios existen; `git diff ai-service/openapi.json` vacío; `git diff ai-service/pyproject.toml` vacío.

- [x] 1.2 Añadir settings opcionales `JPV_EMBEDDING_API_KEY` / `MODEL` / `BASE_URL` / `BATCH_SIZE` (default **64**) en `settings.py`. String vacío = unset, igual que `JPV_RAG_LLM_*`. Blank de `BATCH_SIZE` → 64. Pinnar key/model/base URL a `None` y batch a 64 en `canonical_openapi_settings`. Completar `backend/.env.example` (`BASE_URL`, `BATCH_SIZE`; default de `MODEL` = `openai/text-embedding-3-small`). **Validación:** `test_settings_do_not_require_embedding_key_to_boot`; blank → unset; `GET /health` 200 sin esas vars; `test_canonical_openapi_settings_pin_embedding_keys_to_absent`; `test_openapi_snapshot_is_stable` verde.

## 2. Constructor canónico y hash (primera mitad)

- [x] 2.1 Definir el DTO `ProductSourceText` (o equivalente) con `sku` y `name` obligatorios; listas `materials` / tags que pueden ser `[]`; opcionales el resto. **Sin** `source`, `confidence`, `product_id`, `family_id`, `price`, `price_band`, `data_origin`, `text_provenance`. Constante `SOURCE_TEXT_VERSION = "source-text/v1"`. **Validación:** el DTO rechaza `sku`/`name` vacíos; no tiene esos campos fuera de alcance.

- [x] 2.2 Implementar `build_source_text` con el orden y etiquetas en español de `source-text/v1`. `\n`, UTF-8, sin `\r`. Materiales y tags ordenados alfabéticamente y unidos por `", "`. Línea omitida si el valor falta o la lista está vacía. **No** sentinela `ninguna` / `n/a`. Familia por **nombre**. **Validación:** `test_source_text_is_stable_for_same_profile`; `test_material_order_does_not_change_hash`; `test_absent_fields_are_omitted_not_sentinel`; `test_price_is_not_in_source_text`; `test_family_id_uuid_is_not_in_source_text`.

- [x] 2.3 Implementar `hash_source_text` como SHA-256 del `doc_text` UTF-8 exacto, hex minúsculas de 64 caracteres. **Validación:** `test_source_text_is_stable_for_same_profile` (el digest coincide con hashear el `doc_text`, no una tupla); `test_hash_changes_when_family_changes`.

## 3. Puerto, fake, caché y dimensión

- [x] 3.1 Definir el puerto `EmbeddingClient` (`async embed(texts) -> EmbedResult`) con `model_id`, `document_version_key = "{model}:1536:source-text/v1"` y `model_version_key = "{model}:1536"`. `EmbedResult` lleva `vectors`, `embedding_model`, `embedding_version` (= `document_version_key` para documentos) y `cache_hits`. **Validación:** un test de construcción del puerto (fake) expone las dos claves; `embedding_version` del resultado de documento es `document_version_key`.

- [x] 3.2 Fake inyectable en `tests/support/` (el README ya lo nombra) que cuenta llamadas y puede devolver dimensión configurable. Implementar la caché in-memory `(digest, model, version) → vector` en el cliente (o un wrapper que el adapter y el fake compartan). Sin TTL. Sin Redis. Sin tabla. **Validación:** `test_embedding_not_recomputed_when_hash_unchanged`; `test_unit_suite_makes_no_provider_calls`.

- [x] 3.3 Assert `len(vector) == 1536` tras cada respuesta del puerto real (y del fake cuando se configura mal). Dimensión distinta → excepción identificable. **No** L2 extra. **Validación:** `test_vector_dimension_mismatch_is_rejected`.

## 4. Adapter LiteLLM (segunda mitad, sigue 🔴)

- [x] 4.1 Implementar el adapter LiteLLM (`litellm.aembedding` o equivalente estable en `1.98.0`). Default model `openai/text-embedding-3-small`. Trocear `texts` en bloques de `JPV_EMBEDDING_BATCH_SIZE` (default 64). Retry con backoff en 429 y 5xx; **no** reintentar 4xx de validación. **No** reutilizar `LiteLlmEnrichClient` ni `OpenAICatalogLlm`. **Validación:** test de *batching* con fake/spy (ninguna llamada > 64 textos); el adapter no importa `jbg_ai.data` ni `jbg_ai.enrichment.llm`.

- [x] 4.2 Al llamar `embed` sin `JPV_EMBEDDING_API_KEY`: excepción de dominio explícita. **No** fallback a `JPV_RAG_LLM_API_KEY`. La key no se loguea. **Validación:** `test_embed_without_key_fails_without_using_rag_llm_key`.

## 5. Verificación de alcance y documentación

- [x] 5.1 `uv run --system-certs pytest tests/indexing tests/config tests/api/test_health.py tests/api/test_openapi_snapshot.py` en verde **sin** sockets a proveedores. **Validación:** salida sin fallos **nuevos**; comparar nombres si la suite global ya tenía rojos ajenos.

- [x] 5.2 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/migrations/`, `backend/src/` (salvo `.env.example` de `JPV_EMBEDDING_*`), `frontend/`. `jbg_ai.api.main` no importa `jbg_ai.indexing`. `/v1/index/*` sigue siendo el stub C13. No hay TODO/FIXME sin tarea de seguimiento. **Validación:** test o aserto de import; `test_openapi_snapshot_is_stable` verde.

- [x] 5.3 Alinear docs de contexto: `Documentos/epicas.md` (EP12 enlaza HU-AIENG-011); README de `ai-service` actualiza el marcador C11 si existe. **Validación:** un lector de la épica llega a la biblioteca `indexing/`, a `source-text/v1` y a la frontera «sin HTTP ni SQL».

- [x] 5.4 Ejecutar **`openspec validate --all --strict`**. **Validación:** la salida reporta `0 failed`.
