## Why

C13 dejó `ai.product_document` consultable (1.200 filas, embedding 1536-d, HNSW cosine). C02 congeló el contrato y C03 ya llama `POST /v1/retrieval/products` con timeout **800 ms**. La ruta sigue siendo el stub: `STUB_MODE=true` → fixtures; `false` → **501**. Sin este change C15 hidrata aire o se queda en el circuito abierto. Se hace ahora porque C13 está archivado, el índice local está poblado, y C14 nunca se recorta.

## What Changes

- **`POST /v1/retrieval/products` real** cuando `STUB_MODE=false` (patrón stub/real de C09/C13). Con `STUB_MODE=true` siguen los fixtures C02, cero I/O. Quitar `require_stub_mode` **solo** de `/products`. Handler **async**. Substitutes intacto (sigue stub/501, C26).
- **Zona nueva `jbg_ai/retrieval/`**: embebe la query con el mismo `LiteLlmEmbeddingClient` de C11 (**sin editar** `indexing/embeddings.py`), instancia de retrieval con `max_attempts=1`, inyección `app.state.retrieval_embed` (no reutilizar `index_embed` si ese lleva 3 intentos). SQL `<=>` cosine sobre HNSW, umbral de **distancia** en SQL, overfetch **después** del umbral, filtros del body, score `clamp(1 − d, 0, 1)`.
- **Setting `JPV_RETRIEVAL_DISTANCE_THRESHOLD`** (default **0,65**), opcional al boot; pin en `canonical_openapi_settings`. Sin relajación dinámica. Calibración en C24.
- **`mode=hybrid` y `lexical`** ejecutan la rama vectorial hasta C21. `debug.notes` incluye `vector_only_until_c21`. No 501 por modo.
- **503 vs abstención:** índice vacío / cero vectores compatibles con `model_version_key` / sin `DATABASE_URL` / sin `JPV_EMBEDDING_API_KEY` / embed no recuperable → **503** nombrando el fallo. Hay índice y nada pasa el umbral → **200** + `results=[]` + `low_confidence=true`.
- **Logs estructurados** `stage=embed|search` con `trace_id`. **No** `INSERT` en `ai.query_log` (C05 no la creó; C04 cubre el lado .NET después de hidratar).
- **`openapi.json` no se regenera.** `test_openapi_snapshot_is_stable` verde sin tocar el snapshot.

**Fuera de alcance:** búsqueda léxica / RRF / sinónimos (C20/C21); extraer filtros desde el texto (C21); proyección POS (C22); `/v1/retrieval/substitutes` real (C26); hidratación, truncado a `top_k`, feature flag, fallback léxico .NET (C15); cliente gateway (C03); `ai.query_log`; tocar `embeddings.py`; Alembic; migración EF; frontend; UI; reformulación LLM de la query; filtrar precio/stock/`pos_id` en Python. Un pytest **no** exige 1.200 filas contra Docker/OpenAI.

Sin breaking de OpenAPI ni de EF. El único breaking de *comportamiento* es que `STUB_MODE=false` deja de ser 501 y pasa a 200/503 reales — eso **es** este change.

## Capabilities

### New Capabilities

- `vector-retrieval`: retriever vectorial de `POST /v1/retrieval/products` — embed de query (`max_attempts=1`), `<=>` HNSW cosine, umbral de distancia, overfetch tras el umbral, filtros del body, score 0–1, abstención 200 vs 503 de índice caído, `mode` hybrid/lexical como vector hasta C21, logs de etapa. Python no lee `public`. El stub C02 permanece cuando `STUB_MODE=true`.

### Modified Capabilities

- `ai-service-runtime`: setting `JPV_RETRIEVAL_DISTANCE_THRESHOLD` (default 0,65) opcional al arrancar; `GET /health` no la exige. Pin en `canonical_openapi_settings` para que el entorno no se cuele en el snapshot. Distinct de `JPV_EMBEDDING_*` / `JPV_RAG_LLM_*` / `JPV_INDEX_FEED_*`.

`ai-service-api-contracts` **no lleva delta**: la forma del JSON no cambia (C02 ya fijó `results`, `score` 0–1, overfetch, `low_confidence`, `filters`). El requisito de 501 sigue valiendo para las rutas que aún no tienen implementación (substitutes, assist, inventory). El over-retrieval del stub (`min(top_k × 3, 60)` siempre) no se renegocia; el camino real puede devolver menos tras el umbral y eso vive en `vector-retrieval`.

`ai-service-auth` no cambia: ya exige `pos_id` en retrieval y el body `pos_id` se ignora. `ai-vector-schema` no cambia: C14 consulta HNSW/GIN, no altera el esquema. `catalog-source-text` no cambia: C14 **instancia** el cliente C11, no edita `embeddings.py`. `product-document-indexer` no cambia: el escritor C13 no se hincha con `ORDER BY embedding <=>`. `ai-gateway-client` no cambia: C03 ya mapea 200/503/501.

## Impact

**`jbg-ai`** — paquete `retrieval/` nuevo (handler, SQL de búsqueda, mapeo score/filtros, logs); router `/v1/retrieval/products` sustituye `require_stub_mode` por la rama real cuando `stub_mode` es falso (async); settings de umbral; tests en `tests/retrieval/`, `tests/api/` y `tests/config/` con fakes de embed y de puerto de búsqueda (cero sockets a OpenAI). Substitutes, `indexing/embeddings.py` y `openapi.json` **sin diff**.

**Backend .NET / frontend / terraform / Alembic / EF** — sin cambios. C03 ya consume el schema con timeout 800 ms y no trunca el overfetch. Completar Compose / `.env.example` no es obligatorio: el umbral tiene default; `JPV_EMBEDDING_*` ya existen. Producción: SSM en **C17**.

**Documentación** — `Documentos/epicas.md` (EP14) enlaza HU-AIENG-014 en el apply.

**Dependientes desbloqueados:** C15 (hidratación .NET) y, en cascada, C20/C21/C22/C24. No paralelizar con un change que edite `embeddings.py` (C23). El valor de producto no es visible: no hay pantalla.
