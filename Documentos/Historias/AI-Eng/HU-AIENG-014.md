# HU-AIENG-014: Recuperación vectorial real en `POST /v1/retrieval/products`

## Formato estándar

Como **desarrollador del proyecto**, quiero **embeber la consulta del operador, buscar por coseno sobre HNSW en `ai.product_document` y devolver candidatos sobre-recuperados con umbral y abstención** **para** **que C15 hidrate desde .NET sobre un retriever real, no sobre el stub C02 ni sobre un 501**.

---

## Descripción

Change OpenSpec `add-vector-retrieval-endpoint` / **C14**, épica **EP14 — Búsqueda Semántica Híbrida**. Marcado 🔴 en la ruta crítica. Nunca se recorta. Prerrequisito: **C13** (archivado). El índice local ya está poblado (2026-08-27): **1.200** filas en `ai.product_document`, todas con embedding 1536-d, `tsv` y procedencia.

Es la primera recuperación real del contrato congelado en C02: `POST /v1/retrieval/products`. C03 ya mapea el body y espera timeout **800 ms**. C15 hidratará precio, stock y permisos desde `public` y truncará a `top_k`. Aquí Python solo calcula parecido.

Hoy el router `retrieval.py` sigue el stub C02: con `STUB_MODE=true` fixtures; con `STUB_MODE=false` **501** nombrando este change. C14 sustituye el 501 por la rama vectorial. El stub **no se toca**.

El valor no es de operador: no hay pantalla. Desbloquea C15 (endpoint .NET), C20/C21 (híbrido/RRF), C22 (proyección POS) y C24 (evals).

**Alcance de esta historia (sí):**

- Zona nueva `ai-service/src/jbg_ai/retrieval/` y tests en `tests/retrieval/`.
- `POST /v1/retrieval/products` real cuando `STUB_MODE=false` (patrón stub/real de C09/C13). Con `STUB_MODE=true` siguen los fixtures C02.
- Embeber la `query` con el **mismo** `LiteLlmEmbeddingClient` de C11, **sin editar** `indexing/embeddings.py`. Instancia de retrieval con `max_attempts=1` (el indexador sigue en 3). Inyección por `app.state` (gemelo de `index_embed` / `enrich_llm`).
- SQL `<=>` cosine sobre HNSW (`vector_cosine_ops`). Umbral sobre **distancia** en SQL. Setting `JPV_RETRIEVAL_DISTANCE_THRESHOLD`, default **0,65**. Sin relajación dinámica. Calibración en C24.
- Score en el contrato: `score = clamp(1 − cosine_distance, 0, 1)` (el wire sigue 0–1).
- Sobre-recuperación **después** del filtro de distancia: `min(top_k × 3, 60)`, reutilizar `over_retrieval_count`. Orden por distancia ascendente.
- Filtros del **body**: `materials` (solape `&&`), `category` → `piece_type`, `family_id`, `exclude_product_ids`. Además `is_active` y `embedding IS NOT NULL`. Filas incompatibles con `model_version_key` del cliente vivo no entran.
- `mode=hybrid` y `mode=lexical` corren la **misma** rama vectorial hasta C21. `debug.notes` incluye `vector_only_until_c21`. No 501 por modo.
- Eco `effective_pos_id` del token (el body `pos_id` se ignora). **No** filtrar por POS — eso es C22 + hidratación C15.
- Índice vacío / sin bootstrap / sin `DATABASE_URL` / sin `JPV_EMBEDDING_API_KEY` / cero vectores compatibles → **503** nombrando el fallo.
- Abstención real (hay índice, nada pasa el umbral) → **200** + `results=[]` + `low_confidence=true`.
- `match_reasons` mínimo `["vector"]`. Logs estructurados por etapa (`stage=embed|search`) con `trace_id`, `distance_min`, `candidates`, `low_confidence`, `latency_ms`, `mode`. Query del operador solo en Debug.
- Handler **async**. Auth: `get_service_principal` (exige `pos_id`). `openapi.json` **no** se regenera.

**Fuera de alcance (no):**

- Búsqueda léxica, RRF, sinónimos → **C20 / C21**. Extraer filtros **desde el texto** de la query → **C21**.
- Proyección / prefiltro POS (`ai.pos_projection`) → **C22**.
- `POST /v1/retrieval/substitutes` real → **C26**.
- Hidratación, truncado a `top_k`, feature flag, fallback léxico .NET → **C15**. Cliente gateway → ya es **C03**.
- `ai.query_log` (sigue sin dueño; C05 no la creó a propósito). Telemetría de producto = `ProductSearchEvent` (C04) **después** de hidratar.
- Tocar `indexing/embeddings.py` (congelado en C11 para C23). Regenerar snapshot OpenAPI. Alembic. Migración EF. Frontend. UI.
- Reformulación LLM de la query (S9 no aplica: queries cortas + presupuesto 800 ms).
- Relajar el umbral si hay pocos hits. Filtrar precio o stock en Python.

**Decisiones de diseño ya acordadas** (exploración 2026-08-27):

| # | Tema | Decisión |
|---|---|---|
| 1 | `mode` por defecto `hybrid` | Opción A: hybrid y lexical corren **vector** hasta C21. Nota en `debug`. No 501 |
| 2 | Score 0–1 vs distancia 0–2 | Umbral sobre **distancia** en SQL. Score = `clamp(1 − d, 0, 1)`. Setting default **0,65**. Sin relajación. Overfetch **después** del umbral. Cero hits → 200 + `low_confidence` |
| 3 | Filtros del body | C14 los **honra** (`materials`, `category`→`piece_type`, `family_id`, exclusiones). C21 extrae desde el texto. **No** `pos_id` |
| 4 | 800 ms vs reintentos de embed | Misma clase C11; retrieval con `max_attempts=1`. Indexador intacto (3). Caché RAM C11 por texto exacto sigue |
| 5 | Índice vacío vs abstención | Vacío / sin bootstrap / sin key → **503**. Abstención real → **200 + `low_confidence`**. Stub C02 intacto si `STUB_MODE=true` |
| 6 | `ai.query_log` | **No** en C14. Logs por etapa + `trace_id`. Cruce con C04 vía `trace_id`. Tabla si hace falta: change propio o C24 |

**Cortes que no se reabren:** el contrato C02 (campos, score 0–1, overfetch, `low_confidence`) no se renegocia. Python no lee `public`. `source-text/v1` no se modifica. El umbral no se mueve a .NET.

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C14, §0 `ai.query_log`, §6 nunca se recorta),
[proyecto-final-diseno-rag-joiabagur.md](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.2 frontera, §7.6 sobre-recuperación),
[Retrieval que no es solo cosine](../Sesiones%20Master%20AIEng/S9_Fundamentos_RAG/Retrieval%20que%20no%20es%20solo%20cosine%20-%20top-K,%20threshold%20y%20filtros%20sobre%20pgvector.md) (guía: umbral + filtros; no dogma),
[epicas.md](../../epicas.md) (EP14),
[modelo-de-datos.md](../../modelo-de-datos.md) (`ai.product_document`, HNSW cosine, GIN `materials`),
[HU-AIENG-002.md](HU-AIENG-002.md), [HU-AIENG-003.md](HU-AIENG-003.md), [HU-AIENG-013.md](HU-AIENG-013.md),
specs vivas `ai-service-api-contracts`, `ai-service-auth`, `ai-service-runtime`, `ai-vector-schema`, `catalog-source-text`, `product-document-indexer`, `ai-gateway-client`,
change OpenSpec [`openspec/changes/add-vector-retrieval-endpoint/`](../../../openspec/changes/add-vector-retrieval-endpoint/) y su [ticket técnico](../../../openspec/changes/add-vector-retrieval-endpoint/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: Una query con índice poblado devuelve candidatos ordenados
**Dado que** `ai.product_document` tiene documentos activos con embedding 1536 compatible con `model_version_key` del cliente vivo
**Y** `STUB_MODE=false` y hay `JPV_EMBEDDING_API_KEY` y `DATABASE_URL`
**Cuando** un cliente autenticado (JWT con `pos_id`) llama a `POST /v1/retrieval/products` con `query` no vacía y `top_k = 10`
**Entonces** se embebe la query (un vector 1536) y se busca con `<=>` cosine
**Y** solo entran filas con distancia **≤** el umbral configurado
**Y** se devuelven como máximo `min(30, 60)` resultados, ordenados por distancia ascendente
**Y** cada ítem tiene `score` en `[0, 1]`, `match_reasons` conteniendo `"vector"`, `sku`, `materials`, `family_id` / `variant_label` nulos si se desconocen
**Y** `candidates_returned` es la longitud de `results`
**Y** `effective_pos_id` es el del token, no el del body
**Y** `low_confidence` es `false` si hay al menos un resultado

### Escenario 2: Nada supera el umbral → abstención, no error
**Dado que** el índice tiene vectores compatibles
**Y** todas las distancias al embedding de la query son **> 0,65** (o el valor del setting)
**Cuando** corre `POST /v1/retrieval/products` en modo real
**Entonces** la respuesta es HTTP **200**
**Y** `results` es `[]`, `candidates_returned` es 0, `low_confidence` es `true`
**Y** no se relaja el umbral ni se reintenta el embed

### Escenario 3: Los filtros del body recortan el conjunto
**Dado que** el body lleva `filters.materials`, `filters.category`, `filters.family_id` y `filters.exclude_product_ids`
**Cuando** corre la búsqueda real
**Entonces** `materials` exige solape de arrays (`&&`)
**Y** `category` se aplica como igualdad a `piece_type`
**Y** `family_id` (UUID válido) filtra `product_document.family_id`
**Y** los `exclude_product_ids` no aparecen en `results`
**Y** no se filtra por `pos_id` ni por precio ni por stock

### Escenario 4: `mode=hybrid` (default) y `lexical` no son 501
**Dado que** C21 aún no existe
**Cuando** el body envía `mode` ausente, `hybrid` o `lexical`
**Entonces** se ejecuta la rama **vectorial**
**Y** `debug.notes` incluye `vector_only_until_c21` (cuando `debug` viaja)
**Y** la respuesta no es 501

### Escenario 5: Índice vacío o dependencia ausente es 503, no abstención
**Dado que** `STUB_MODE=false` y falta `JPV_EMBEDDING_API_KEY`, o `DATABASE_URL`, o el recuento de embeddings compatibles es 0, o no hay esquema `ai` / extensión `vector`
**Cuando** se llama a `POST /v1/retrieval/products`
**Entonces** la respuesta es HTTP **503** con detalle que nombra el fallo
**Y** no es 200 con `low_confidence` (eso reservado a «hay índice y nada pasó el umbral»)
**Y** `GET /health` sigue en 200
**Y** con `STUB_MODE=true` el stub C02 sigue contestando 200 con fixtures, sin tocar la BD ni el proveedor

### Escenario 6: El embed de retrieval no reintenta; el contrato no se mueve
**Dado que** el cliente de embeddings de retrieval se instancia con `max_attempts=1`
**Cuando** el proveedor falla o tarda
**Entonces** no hay segundo intento que coma el presupuesto de 800 ms de C03
**Y** `indexing/embeddings.py` no tiene diff
**Y** `ai-service/openapi.json` no se regenera
**Y** `test_openapi_snapshot_is_stable` sigue verde sin tocar el snapshot

### Escenario 7: Fuera de alcance explícito
**Dado que** C14 entrega el retriever vectorial
**Cuando** se revisa el entregable
**Entonces** **no** hay RRF, léxico ni diccionario de sinónimos
**Y** **no** se ha escrito ni leído `ai.pos_projection`
**Y** `/v1/retrieval/substitutes` sigue en stub/501
**Y** **no** existe `ai.query_log`
**Y** **no** hay migración Alembic ni EF Core ni cambio en .NET/frontend
**Y** un pytest **no** exige 1.200 filas contra Docker/OpenAI

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final. Nada visible para el operador hasta C16.

- **Score vs umbral.** pgvector `<=>` con `vector_cosine_ops` es distancia en `[0, 2]`. El contrato C02 publica `score` en `[0, 1]`. Convertir en el handler; filtrar en SQL por distancia. Default 0,65 ≈ score 0,35. C24 calibra; C14 no adivina el recall del estrato `real`.

- **Overfetch después del umbral.** Si se sobre-recuperara *antes*, el top-60 podría estar lleno de vecinos peores que el umbral y C15 hidrataría basura. `candidates_returned` es lo que realmente se envía, no `top_k × 3` teórico.

- **`mode=hybrid`.** El default del schema es hybrid porque C02 diseñó el destino. Mentir con 501 rompería a C03/C15 el día que enciendan `STUB_MODE=false`. La nota en `debug` deja rastro para C21.

- **C14 compara `model_version_key`.** Comentario congelado en `embeddings.py` (C11). Un índice de otra dimensión/modelo no debe degradar a «abstención». Cero compatibles = 503.

- **Carga de `JPV_EMBEDDING_API_KEY`.** Vive en `backend/.env`. `Settings` lee el `.env` del *cwd* (`ai-service/.env`, que no existe). Compose `jbg-ai` **no** inyecta `JPV_EMBEDDING_*`. El CLI de C13 tampoco llama a `jbg_ai.data.envload`. Operativa de real mode: vars en el proceso o `ai-service/.env`. C14 **no** añade `envload` al boot HTTP (mismo corte que C13).

- **`skipped=487` del sync C13** no son productos sin vector: skip-embed de una segunda pasada `--full` tras el tope de 180 s. Tabla: 1.200/1.200.

- **Par de zona.** No solapar con C21 (híbrido en `retrieval/`) más de lo que C13 evitó solapar con C23. Una capability nueva de retrieval; deltas de runtime/settings si el umbral entra en spec.

- **`design.md` obligatorio** en el change. El plan v3 no se lo asignaba; las decisiones de coste asimétrico (umbral, 503 vs 200, `max_attempts`, filtros vs C21) no caben solo en tasks.

- **Verificación posterior (no DoD de merge):** un `POST /v1/retrieval/products` local con `STUB_MODE=false` contra los 1.200 ya indexados, comprobando 200, `candidates_returned > 0` en una query obvia («anillo plata») y 200+`low_confidence` en una query absurda.

---

## Tareas

1. Completar artefactos OpenSpec (`proposal`, **`design.md` obligatorio**, specs — capability nueva de retrieval + deltas `ai-service-runtime` / contratos si el 503 queda en spec —, `tasks`).
2. Setting `JPV_RETRIEVAL_DISTANCE_THRESHOLD` (default 0,65); pin en `canonical_openapi_settings`.
3. Módulo `jbg_ai/retrieval/`: handler async, SQL `<=>` + filtros, score, overfetch, `low_confidence`.
4. Router: patrón stub/real C09; 503 de dependencias; instancia embed `max_attempts=1` inyectable.
5. Logs por etapa con `trace_id`. `debug.notes` para hybrid/lexical.
6. Tests en `tests/retrieval/` (y api) **sin** sockets a OpenAI. Fakes de embed y de repo. Enlazar HU en `epicas.md` (EP14) en el apply.
7. `openspec validate --all --strict` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 5 — sin retriever real, C15 no tiene a quién hidratar
- **Urgencia (mercado / feedback):** **5** — 🔴; nunca se recorta; desbloquea C15, C21, C22, C24
- **Complejidad / esfuerzo:** 4 — SQL + umbral + stub/real; sin Alembic ni OpenAPI
- **Riesgos y dependencias:** C13 archivado e índice local poblado (si se recrea el volumen, el índice vuelve a 0 y el real mode es 503); no tocar `embeddings.py`; presupuesto 800 ms vs LiteLLM; no colar `query_log`; `mode=hybrid` no debe 501
