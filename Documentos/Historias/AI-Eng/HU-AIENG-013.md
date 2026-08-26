# HU-AIENG-013: Indexador de `ai.product_document` desde el feed de catálogo

## Formato estándar

Como **desarrollador del proyecto**, quiero **poblar `ai.product_document` tirando del feed de catálogo, con upsert idempotente, tombstones, procedencia sellada y un status de deriva observable** **para** **que C14 recupere sobre un índice real, consultable y alineado con .NET, sin leer `public` por SQL**.

---

## Descripción

Change OpenSpec `add-product-document-indexer` / **C13**, épica **EP14 — Búsqueda Semántica Híbrida**. Marcado 🔴 en la ruta crítica. Prerrequisitos: **C11** y **C12** (archivados). AutoBulk de C08/C09 sobre los 1.200 **ya ejecutado** (2026-08-26): el feed de catálogo emite upserts; esta historia es la primera que los consume.

Es el change que cierra el contrato de sincronización del §6.3 del diseño RAG por el lado Python: *pull* HTTP, upsert por `product_id` guiado por `source_hash`, tombstones, detección de deriva, fallos aislados. C11 congeló el texto canónico y el cliente de embeddings; C12 congeló el feed. Aquí nace el escritor.

El valor no es de operador: no hay pantalla. C14 (retriever vectorial) queda desbloqueado. C22 reutilizará el cliente HTTP del feed para `pos_projection` y **no** tocará `indexing/embeddings.py` ni el upsert de catálogo más de lo necesario.

C12 no emite `data_origin` ni `text_provenance`. C05 exige `data_origin` NOT NULL. C06a adjudicó la columna `text_provenance` a este change. El `Dockerfile` de `jbg-ai` copia `src/`, no `data/catalog/`: la procedencia no se lee de los JSONL en runtime.

**Alcance de esta historia (sí):**

- `POST /v1/index/sync` y `GET /v1/index/status` reales cuando `STUB_MODE=false` (patrón C09). Con `STUB_MODE=true` siguen los fixtures C02.
- Cliente HTTP reutilizable del feed: header `X-Index-Feed-Key`, keyset `(since, sinceId)`, parseo de `kind`. C13 **solo drena el catálogo**. El cliente acepta el path POS; C13 no lo llama.
- Upsert por `product_id`. Idempotencia = **no llamar al proveedor de embeddings** si `source_hash` coincide y hay vector 1536; el UPSERT de columnas (precio, `price_band`, `family_id`, tags, `is_active`, `indexed_at`, procedencia) **corre siempre**. `skipped` cuenta embeber omitido, no fila ignorada.
- Tombstones: `DELETE` por `product_id`, idempotente si la fila no existe (Pending-de-nacimiento de C12).
- Mapa commiteado `src/jbg_ai/indexing/sku_provenance.json` (SKU → `{data_origin, text_provenance}`), generado una vez desde los dos JSONL. Alembic: `text_provenance` NOT NULL + CHECK + índice B-tree; tabla `ai.sync_checkpoint`; `sync_failure` gana `cursor_since_id` y `product_id`.
- Procedencia: mapa ausente → el sync real no escribe (error explícito; `/health` vive). SKU huérfano → ese ítem a `sync_failure`, `failed += 1`, el resto sigue. **Sin default** `synthetic`/`merchant`.
- Cero fila visible sin embedding. Aislamiento por **ítem**. Assert 1536 de C11 antes del UPSERT.
- Renegociación OpenAPI (**BREAKING** aditivo): `since_id` / `cursor_id` (uuid). `batch_size` se ignora (warning). Snapshot regenerado.
- Checkpoint keyset persistido. Un POST con `full=true` (o sin checkpoint) **drena** las páginas de catálogo (24 × 50 = 1.200). Tope de tiempo configurable (default **180 s**): si se agota, se persiste checkpoint y se devuelve cursor + contadores parciales, no un 500.
- CLI `python -m jbg_ai.indexing sync` sobre la misma función que el router.
- Auth de catálogo: `get_catalog_principal` (sin `pos_id`). Settings `JPV_INDEX_FEED_BASE_URL` y `JPV_INDEX_FEED_API_KEY` opcionales al boot; 503 al sync real si faltan. **Prohibido** caer a `JWT_SECRET`.
- Repositorio async + SQLAlchemy Core (mapped class no usado para autogen Alembic). Puertos inyectables (feed, embed, repositorio), patrón `request.app.state.enrich_llm`.
- Tests en `tests/indexing/` (y api/migrations) **sin** sockets a OpenAI ni al API .NET. Tests de migración sobre el contenedor pgvector existente. `tsv IS NOT NULL` tras upsert; **no** reassertar la config `spanish` (hecho de esquema C05).

**Fuera de alcance (no):**

- Sincronizar `ai.pos_projection` ni drenar el feed POS → **C22**.
- Scheduler cada 5–10 min → cadencia de la proyección, **C22**.
- HTTP *push* .NET → Python, outbox, migración EF Core, columna `DataOrigin` en `Product`.
- `POST /v1/retrieval/products` real → **C14**.
- Tocar `indexing/embeddings.py` (congelado en C11 para C23).
- `ai.query_log` (sigue sin dueño; no se cuela aquí ni en C14).
- Chunking de catálogo. Diccionario de sinónimos (C20). Embeddings visuales.
- Regenerar el corpus JSONL. Reejecutar AutoBulk (ya corrido). UI, frontend, RDS de producción (C17).
- Test de CI/pytest que exija 1.200 filas reales en Docker ni llamadas al proveedor.

**Decisiones de diseño ya acordadas** (exploración 2026-08-26):

| # | Tema | Decisión |
|---|---|---|
| 1 | OpenAPI | **Renegociar** (opción B). Añadir `since_id` / `cursor_id`. Regenerar snapshot |
| 2 | Idempotencia | Skip **embed**, no skip de fila. `skipped` = embeber omitido |
| 3 | Procedencia | Mapa en `src/` + Alembic `text_provenance`. **A3:** sin mapa no se escribe. **B4:** SKU huérfano = fallo ruidoso del ítem |
| 4 | Alcance del feed | Cliente reutilizable; C13 solo catálogo. Sin scheduler |
| 5 | Disparo | POST drena + checkpoint + settings de feed + CLI + `get_catalog_principal`. Tope 180 s |
| 6.1 | Fallos | Aislamiento por **ítem** |
| 6.2 | Embedding NULL | Cero fila visible sin vector 1536 |
| 6.3 | Estado | `ai.sync_checkpoint` + ampliar `sync_failure` (`cursor_since_id`, `product_id`) |
| 6.4 | `drift_count` | Hash de conjunto (1 GET de la 1ª página del feed vs hash de ids en `ai`). No paginar 24 veces en `/status` |
| 6.DoD | Merge | Tests con fakes. Smoke local 1.200 = **verificación posterior**, no criterio de merge |
| 7 | Acceso a datos | Repositorio async + Core; fakes; `tsv` no null |
| 8 | Corpus | 1.200 SKU congelados; **no** hay altas a mano en .NET |

**Cursor.** Bookmark keyset `(watermark, id)`, no un `datetime` suelto. Tres capas: query del feed C12, body OpenAPI de `/v1/index/sync`, fila de `sync_checkpoint`.

**Cortes que no se reabren:** `price-band/v1` sigue siendo autoridad .NET (viaja en el upsert del feed). `source-text/v1` no se modifica. Python no lee `public`.

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C13, §0 C06a/`text_provenance`, §0 C12 archivado, §6 nunca se recorta, par C13 ‖ C23),
[proyecto-final-diseno-rag-joiabagur.md](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.2, **§6.3**, §7.2, §8.1.1 ejes de procedencia),
[informes/c12-catalog-autobulk-runbook.md](../Proyecto%20Final%20AIEng/informes/c12-catalog-autobulk-runbook.md),
[Diseño del esquema y búsqueda semántica](../Sesiones%20Master%20AIEng/S8_BBDD_Vectoriales/Diseño%20del%20esquema%20y%20busqueda%20semantica.md) (guía: no mezclar dimensión; el catálogo **no** se trocea),
[Del CAG estático al flujo RAG](../Sesiones%20Master%20AIEng/S9_Fundamentos_RAG/Del%20CAG%20estatico%20al%20flujo%20RAG%20-%20Las%20cuatro%20etapas%20y%20por%20que%20el%20Retrievel%20domina.md) (frescura = indexar sin redesplegar; índice vacío = fallo mudo),
[epicas.md](../../epicas.md) (EP14),
[modelo-de-datos.md](../../modelo-de-datos.md) (`ai.product_document`, `ai.sync_failure`),
[HU-AIENG-011.md](HU-AIENG-011.md), [HU-AIENG-012.md](HU-AIENG-012.md),
specs vivas `catalog-source-text`, `index-feed`, `ai-vector-schema`, `ai-service-api-contracts`, `ai-service-auth`, `ai-service-runtime`,
change OpenSpec [`openspec/changes/add-product-document-indexer/`](../../../openspec/changes/add-product-document-indexer/) y su [ticket técnico](../../../openspec/changes/add-product-document-indexer/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: Un sync completo drena el catálogo e indexa
**Dado que** el feed de catálogo emite upserts de productos con perfil `Approved` y el mapa de procedencia cubre sus SKU
**Y** `STUB_MODE=false` y hay clave de embeddings y de feed
**Cuando** se llama a `POST /v1/index/sync` con `full: true` (HTTP o CLI) y un token de catálogo (sin `pos_id`)
**Entonces** Python pagina el feed hasta `nextCursor` nulo (24 páginas de 50 sobre 1.200)
**Y** cada upsert produce una fila en `ai.product_document` con `doc_text`, `source_hash`, embedding 1536, `data_origin`, `text_provenance` y `tsv` no nulo
**Y** la respuesta reporta `upserted` / `skipped` / `deleted` / `failed` y un cursor keyset `(cursor, cursor_id)`
**Y** `GET /v1/index/status` reporta `indexed_documents` igual al conjunto escrito y `last_full_sync_at` no nulo

### Escenario 2: Mismo `source_hash` no reembebe y sí actualiza columnas
**Dado que** un producto ya indexado tiene vector y `source_hash` H
**Y** el feed vuelve a emitirlo con el mismo texto canónico pero otro `price` / `priceBand` (o `family_id` / tags / `isActive`)
**Cuando** corre un sync incremental
**Entonces** no se llama al proveedor de embeddings para ese `doc_text`
**Y** la fila se actualiza (precio, banda, familia, tags, `is_active`, `indexed_at`)
**Y** `skipped` se incrementa en uno
**Y** un rename de `family_name` **sí** cambia el hash y reembebe (obligación C07/C11)

### Escenario 3: Un tombstone saca el documento; uno repetido no falla
**Dado que** el feed emite `kind = tombstone` para un `productId` indexado (`deactivated` o `unapproved`)
**Cuando** el sync procesa ese ítem
**Entonces** la fila desaparece de `ai.product_document`
**Y** `deleted` se incrementa
**Y** un segundo tombstone del mismo id (o de un producto nunca indexado) es no-op y no incrementa `deleted`

### Escenario 4: Status reporta deriva de conjunto sin drenar el feed
**Dado que** el hash agregado de la primera página del feed no coincide con el SHA-256 de los `product_id` de `ai.product_document`
**Cuando** se llama a `GET /v1/index/status`
**Entonces** `drift_count = max(1, abs(indexed_documents − checkpoint.indexed_count))`
**Y** no se recorren las 24 páginas del feed
**Y** si los hashes coinciden, `drift_count = 0`

### Escenario 5: Un ítem fallido no bloquea a los demás
**Dado que** en una página de 50 un SKU no está en el mapa, o el embed de uno falla
**Cuando** corre el sync
**Entonces** ese ítem queda en `ai.sync_failure` con `product_id` / payload / error
**Y** `failed` se incrementa
**Y** los otros ítems de la página se escriben
**Y** no queda una fila visible sin embedding

### Escenario 6: Sin mapa o sin settings de feed el sync real no escribe
**Dado que** `STUB_MODE=false` y falta `sku_provenance.json`, o `JPV_INDEX_FEED_API_KEY`, o `JPV_EMBEDDING_API_KEY`
**Cuando** se llama a `POST /v1/index/sync`
**Entonces** la respuesta es un error explícito (503 o equivalente documentado), no 501 ni 200 con ceros silenciosos
**Y** `ai.product_document` no gana filas
**Y** `GET /health` sigue en 200
**Y** con `STUB_MODE=true` el stub C02 sigue contestando 200 con fixtures

### Escenario 7: El contrato OpenAPI lleva el keyset y el token de catálogo entra
**Dado que** el snapshot se ha regenerado
**Cuando** un cliente autentica `POST /v1/index/sync` con `since` + `since_id` y un token **sin** `pos_id`
**Entonces** la petición se acepta (no 401 por falta de POS)
**Y** `batch_size` en el body no cambia el tamaño de página del feed (sigue siendo 50)
**Y** `test_openapi_snapshot_is_stable` está verde **después** de la regeneración acordada
**Y** un token sin `user_id` / `role` / `trace_id` sigue siendo 401

### Escenario 8: Fuera de alcance explícito
**Dado que** C13 entrega el indexador de catálogo
**Cuando** se revisa el entregable
**Entonces** **no** se ha escrito `ai.pos_projection` ni se ha llamado al feed POS
**Y** **no** hay scheduler de 5–10 min
**Y** `indexing/embeddings.py` no ha cambiado
**Y** **no** hay migración EF Core ni cliente .NET nuevo hacia `/v1/index/sync`
**Y** un pytest de la suite **no** exige 1.200 filas contra Docker/OpenAI

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final. Nada visible para el operador hasta C16.

- **Por qué Python tira y no .NET empuja.** C12 cerró el push: la invalidación es el watermark. `/v1/index/sync` es el disparo (HTTP o CLI), no el transporte del catálogo.

- **Dos hashes.** `ProductAiProfile.SourceHash` (C08) pregunta «¿reextraer?». `product_document.source_hash` (C11/C13) pregunta «¿reembeber?». No se unifican.

- **`skipped` vs no-op.** Un cambio de PVP no cambia `doc_text`. Si se ignorara la fila, C21 filtraría por una banda obsoleta. Fallo mudo.

- **Imagen Docker.** Sin el mapa en `src/` un deploy indexaría a ciegas o fallaría al abrir JSONL inexistente. El test de invariante (mapa = unión de JSONL) corre en el repo, donde `data/` sí existe.

- **Tope 180 s.** 1.200 embeddings `text-embedding-3-small` + 24 GET caben en decenas de segundos. El tope evita un HTTP colgado; no es la política de páginas.

- **Par de zona.** No solapar con C23 (`indexing/`). Alembic no tiene slot único de EF; aun así una sola revisión en este change.

- **Verificación posterior (no DoD de merge):** un `POST /v1/index/sync {full: true}` local y `GET /status` con `indexed_documents = 1200` y `drift_count = 0`, con AutoBulk ya corrido y claves presentes.

---

## Tareas

1. Completar artefactos OpenSpec (`proposal`, **`design.md` obligatorio**, specs — capability nueva de indexación + deltas `ai-vector-schema`, `ai-service-api-contracts`, `ai-service-runtime` —, `tasks`).
2. Alembic: `text_provenance` + CHECK + índice; `sync_checkpoint`; columnas nuevas en `sync_failure`.
3. Generar y commitear `sku_provenance.json`; test de invariante contra los JSONL.
4. Cliente HTTP del feed (API Key, keyset, `kind`) inyectable.
5. Repositorio async + Core; upsert / delete / hash de conjunto / checkpoint.
6. Orquestador de sync: dreno, skip-embed, aislamiento por ítem, tope de tiempo.
7. Router: `get_catalog_principal`, `STUB_MODE` como C09, settings de feed, 503 si faltan secretos.
8. Renegociar Pydantic + regenerar `openapi.json`.
9. CLI `python -m jbg_ai.indexing sync`.
10. Tests (fakes; migración en contenedor pgvector). Enlazar HU en `epicas.md` (EP14) en el apply. Mencionar `text_provenance` / checkpoint en `modelo-de-datos.md`.
11. `openspec validate --all --strict` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 5 — sin índice, C14 no recupera nada
- **Urgencia (mercado / feedback):** **5** — 🔴; nunca se recorta; desbloquea C14 y C18
- **Complejidad / esfuerzo:** 5 — feed + embed + Alembic + OpenAPI + CLI en una sesión
- **Riesgos y dependencias:** C11 y C12 archivados; AutoBulk ya corrido (si el volumen local se recrea, el índice vuelve a 0); no tocar `embeddings.py`; no drenar POS; el snapshot OpenAPI **sí** cambia y hay que acordarlo en el apply; `host.docker.internal:5056` desde el contenedor
