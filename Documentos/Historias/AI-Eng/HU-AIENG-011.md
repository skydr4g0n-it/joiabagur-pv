# HU-AIENG-011: SourceText canónico y cliente de embeddings con idempotencia por hash

## Formato estándar

Como **desarrollador del proyecto**, quiero **un constructor de `doc_text` con orden fijo, su `source_hash` SHA-256 y un cliente de embeddings con reintento, *batching* y caché por hash** **para** **que C13 (y C14/C23) reutilicen una pieza congelada, barata y determinista, y no recalculen vectores cuando el texto canónico no ha cambiado**.

---

## Descripción

Change OpenSpec `add-source-text-and-embedding-client` / **C11**, épica **EP12 — Corpus y Enriquecimiento del Catálogo**. Marcado 🔴 en la ruta crítica. Prerrequisitos de la ficha: **C05** y **C09** (archivados). C06b aporta volumen en `.NET` para cuando C13 indexe; **esta historia no embebe el catálogo**. C12 **no** se desarrolla en paralelo: va después.

Es el change que hace barato y determinista todo el reindexado posterior (§6.3 del diseño RAG): *sin cambio de `source_hash` no se recalcula el embedding*. No es el indexador. No tira del feed. No escribe `ai.product_document`. `/v1/index/sync` sigue siendo el stub que nombra **C13**.

El valor no es de operador: no hay pantalla ni ruta nueva. C13 hará *upsert* con esta biblioteca; C14 embeberá la consulta con el mismo puerto; C23 reutilizará el cliente y **no tocará** `indexing/embeddings.py` (congelado aquí). El plan marca C11 como uno de los pocos changes que **llevan `design.md`**: hay alternativas reales (qué entra en el texto, dónde vive la caché, cómo se versiona el vector).

Hay **dos SHA-256** con nombre casi idéntico. Esta historia no los unifica:

| Hash | Dónde | Sobre qué | Pregunta |
|---|---|---|---|
| `ProductAiProfile.SourceHash` (C08) | .NET | SKU + nombre + descripción + colección (`U+001F`) | ¿Hay que volver a **extraer**? ¿Se machaca una revisión? |
| `ai.product_document.source_hash` (C11) | Python | el `doc_text` canónico UTF-8 | ¿Hay que volver a **embeber**? |

C05 ya dejó `doc_text`, `source_hash char(64)`, `embedding vector(1536)` **nulable**, `embedding_model` y `embedding_version`. C11 **rellena el contrato de esas columnas** en el resultado del cliente; no abre Alembic. El acceso ORM/SQL nace en C13.

Estado verificado en Docker local (`jpv-pv-postgres`, `:5433`, `joiabagur_pv`, 2026-08-25): `"Products"` 1.200, mundo C10 ingerido (12 POS, 6.720 inventario, 22.961 ventas), `"ProductAiProfiles"` **0**, `"ProductFamilies"` **0**, esquema `ai` **ausente** en este volumen. No se ha corrido `enrich-batch` AutoBulk. C11 se prueba con fixtures.

**Alcance de esta historia (sí):**

- Paquete `ai-service/src/jbg_ai/indexing/` — biblioteca. `jbg_ai.api.main` **no** la importa. Sin router, sin SQL, sin regenerar `openapi.json`.
- Constructor `build_source_text(record)` → `doc_text` con plantilla **`source-text/v1`** (constante en código, no un markdown de prompts). Orden de campos fijo. Materiales y tags **ordenados alfabéticamente**. Campos ausentes o listas vacías: **se omite la línea** (no sentinela `ninguna`).
- `source_hash`: SHA-256 del `doc_text` UTF-8 exacto, hex minúsculas de 64 caracteres (mismo formato que C08).
- Puerto `EmbeddingClient` inyectable. Adapter LiteLLM `aembedding` (mismo runtime que C09; **no** el SDK OpenAI directo; **no** `OpenAICatalogLlm` ni `EnrichLlm`).
- Settings `JPV_EMBEDDING_*` (prefijo **ya reservado** en `backend/.env.example`): `API_KEY`, `MODEL` (default `openai/text-embedding-3-small`), `BASE_URL` opcional, `BATCH_SIZE` opcional (default **64**). **Distintas** de `JPV_RAG_LLM_*`. **Sin fallback** a la clave de chat. Opcionales en `/health`; exigidas al embeber de verdad.
- Puerto **`async embed(texts)`**. Resultado: vectores + `embedding_model` + `document_version_key` `{model}:1536:source-text/v1` (lo que C13 persiste) y `model_version_key` `{model}:1536` (lo que C14 usa para no mezclar modelos; la query no se persiste). Assert `len(vector) == 1536`; si no, fallo ruidoso.
- Caché **en memoria** del proceso, clave `(sha256(text), model, version)` → vector. Sirve intra-lote y reintentos. **No** tabla Alembic. La persistencia entre arranques es `ai.product_document` en **C13**.
- Reintento con backoff en 429/5xx; *batching* vía `JPV_EMBEDDING_BATCH_SIZE` (default 64 textos por llamada al proveedor).
- Tests en `ai-service/tests/indexing/` (carpeta reservada) con cliente **falso**. Cero sockets a embeddings, LLM o RDS.
- `canonical_openapi_settings` pina las claves de embeddings a ausentes (mismo criterio que C09).

**Fuera de alcance (no):**

- `POST /v1/index/sync`, `GET /v1/index/status`, *upsert*, *tombstones*, `drift_count`, `ai.sync_failure` → **C13**.
- Feed HTTP .NET → **C12** (después de este change).
- Ejecutar `enrich-batch` AutoBulk sobre los 1.200 → verificación **entre C12 y C13**, no entrega de esta HU.
- Escribir filas en `ai.product_document` o provisionar el esquema `ai` en Docker.
- Modelos ORM / SQLAlchemy de las tablas C05. C05 dejó el acceso tipado para C11/C13; **C11 no lo inaugura**.
- `price` / `price_band` en `doc_text`. Bandas = C12 o C13.
- `product_id`, `family_id` (UUID), `data_origin`, `text_provenance`, confianzas, `source` en el texto.
- Columna nueva de embedding, *blue/green*, migración de modelo 1536 → otra dimensión.
- Redis, caché semántica de consultas, renormalización L2.
- Embeddings visuales (`ProductPhotoEmbeddings`, MobileNet 1280d, spec `embedding-management`).
- Chunking de catálogo. Diccionario de sinónimos (C20: expansión en consulta, nunca en indexación).
- Instructor, RDS, UI, `openapi.json`, migración EF Core o Alembic.

**Decisiones de diseño ya acordadas** (exploración 2026-08-25):

| # | Tema | Decisión |
|---|---|---|
| 1 | Forma | **Biblioteca pura.** Sin HTTP, sin SQL, sin OpenAPI |
| 2 | `doc_text` | SKU + prosa + colección + perfil aprobado + `family_name`/`variant_label` si existen + tags comerciales ordenados. Etiquetas en español alineadas al ejemplo v2 §4.7 |
| 3 | Precio / `price_band` | **Fuera.** Cada cambio de PVP no debe reembeber; el filtro de techo es de C21; la autoridad es .NET |
| 4 | Caché | RAM por `(hash, model, version)`. Recalcular el SHA-256 es gratis. Los vectores duraderos los escribe **C13** |
| 5 | Clave | `JPV_EMBEDDING_API_KEY` **separada**, sin caer a `JPV_RAG_LLM_API_KEY`. Prefijo ya esbozado en `.env.example` |
| 6 | Ausentes | Omitir la línea; no `Piedra: ninguna` |
| 7 | Orden de changes | C12 **después** de C11. El DTO de C11 es el contrato que C13 mapeará desde el feed |
| 8 | Corpus local | 1.200 productos, mundo C10, **0 perfiles IA**, sin esquema `ai` en este volumen |
| 9 | Hash | SHA-256 del `doc_text` renderizado (no tupla paralela). Cambiar la plantilla = `source-text/v2` = reembed de corpus |
| 10 | Cliente | LiteLLM `aembedding`; default `openai/text-embedding-3-small`; assert 1536 |
| 11 | `embedding_version` de documento | `document_version_key = {model}:1536:source-text/v1`. C11 no implementa índice sombra |
| 12 | Superficie | `build_source_text` / `hash_source_text` / **`async`** `embed(texts)`. C14 y C23 no reimplementan el cliente |
| 13 | DTO | No es `ProposedProfile` (lleva `source` y confianza). No es el JSON de C12 (aún no existe) |
| 14 | Query embed (C14) | La query **no** lleva `source-text/v1`. Helper `model_version_key = {model}:1536` para no mezclar modelos |
| 15 | Tamaño de batch | **64** textos por llamada al proveedor |
| 16 | Dónde vive el batch | Setting opcional `JPV_EMBEDDING_BATCH_SIZE`, default 64 (mismo patrón que `JPV_RAG_LLM_CONCURRENCY`) |
| 17 | Sync vs async | **`async embed()`**, alineado a C09 `acompletion` y al C13 async |

**Plantilla `source-text/v1` (orden fijo; línea omitida si el valor falta o la lista está vacía):**

```text
SKU: {sku}
Nombre: {name}
Descripción: {description}
Colección: {collection_name}
Tipo: {piece_type}
Materiales: {materials unidos por ", ", orden alfabético}
Piedra: {stone_type}
Talla: {size_label}
Familia: {family_name}
Variante: {variant_label}
Colores: {color_tags, orden alfabético}
Estilo: {style_tags, orden alfabético}
Ocasiones: {occasion_tags, orden alfabético}
```

Separador de líneas `\n`. Sin `\r`. `sku` y `name` son obligatorios en el DTO.

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C11, §0 C05/C07/C08, §7 `design.md`),
[proyecto-final-diseno-rag-joiabagur.md](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.3 sincronización, §7.1 pipeline, §7.2 esquema, D3),
[joiabagur-ia-especificaciones-funcionales-v2.md](../Proyecto%20Final%20AIEng/joiabagur-ia-especificaciones-funcionales-v2.md) (§4.7 ejemplo de `SourceText`),
[Reindexación y versionado de embeddings](../Sesiones%20Master%20AIEng/S11_RAG_avanzado/Reindexacion%20y%20Versionado%20Embeddings.md) (guía, no dogma: hash + versión de proceso; *blue/green* es C13+),
[Abstracción de proveedores](../Sesiones%20Master%20AIEng/S3_Patrones_Diseños_Wrappers_Modelos/Abstracci%C3%B3n%20de%20proveedores%20y%20estrategias%20de%20fallback.md) (LiteLLM),
[epicas.md](../../epicas.md) (EP12),
[modelo-de-datos.md](../../modelo-de-datos.md) (`ai.product_document`),
[HU-AIENG-005.md](HU-AIENG-005.md), [HU-AIENG-008.md](HU-AIENG-008.md), [HU-AIENG-009.md](HU-AIENG-009.md),
specs vivas `openspec/specs/ai-vector-schema/spec.md`, `openspec/specs/ai-service-runtime/spec.md`, `openspec/specs/catalog-enrichment-pipeline/spec.md`, `openspec/specs/product-ai-profile/spec.md`,
change OpenSpec [`openspec/changes/add-source-text-and-embedding-client/`](../../../openspec/changes/add-source-text-and-embedding-client/) y su [ticket técnico](../../../openspec/changes/add-source-text-and-embedding-client/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: El mismo perfil produce el mismo `doc_text` y el mismo hash
**Dado que** un registro de producto tiene los mismos campos en el mismo orden canónico
**Cuando** se llama dos veces a `build_source_text` y a `hash_source_text`
**Entonces** las dos cadenas `doc_text` son idénticas byte a byte
**Y** el digest es SHA-256 en hex minúsculas de 64 caracteres
**Y** coincide con hashear el `doc_text` UTF-8 (no una tupla paralela)

### Escenario 2: El orden de materiales no cambia el hash
**Dado que** un perfil trae `materials = ["oro", "plata"]` y otro `["plata", "oro"]` con el resto igual
**Cuando** se construye el `doc_text`
**Entonces** ambos emiten `Materiales: oro, plata` (orden alfabético)
**Y** los `source_hash` coinciden
**Y** el mismo criterio aplica a `color_tags`, `style_tags` y `occasion_tags`

### Escenario 3: Un cambio de familia cambia el hash
**Dado que** un producto pasa de no tener familia a `family_name = "Anillo erizo de mar"` (o se renombra la familia)
**Cuando** se reconstruye el `doc_text`
**Entonces** el hash **cambia**
**Y** no se escribe el UUID `family_id` en el texto
**Y** esto cubre la obligación heredada de C07: un rename de familia debe invalidar el documento indexado

### Escenario 4: Los campos ausentes no se serializan con sentinela
**Dado que** `stone_type`, `size_label`, `family_name` y las tres listas de tags están vacíos o nulos
**Cuando** se construye el `doc_text`
**Entonces** no aparece la línea `Piedra:`, ni `Talla:`, ni `Familia:`, ni `Colores:` / `Estilo:` / `Ocasiones:`
**Y** no se escribe `ninguna` ni `n/a`

### Escenario 5: SKU y tags comerciales sí entran; precio no
**Dado que** el registro trae SKU, tags de estilo y un precio numérico
**Cuando** se construye el `doc_text`
**Entonces** hay una línea `SKU:` y, si hay tags, las líneas de color/estilo/ocasión
**Y** no hay cifra de precio ni `price_band`
**Y** no hay `data_origin`, `text_provenance`, confianza ni `source`

### Escenario 6: El embedding no se recomputa si el hash y la versión no cambian
**Dado que** un `EmbeddingClient` real (o el adapter) ya embebió un texto con un modelo y una `embedding_version`
**Cuando** se pide embeber el mismo texto con el mismo modelo y versión
**Entonces** no se llama al proveedor (la caché in-memory cuenta un *hit*)
**Y** el vector devuelto es el mismo
**Y** un fake inyectado afirma el recuento de llamadas

### Escenario 7: Un vector con dimensión distinta de 1536 falla en voz alta
**Dado que** el proveedor (o un fake) devuelve 384 o 3072 dimensiones
**Cuando** el adapter valida el resultado
**Entonces** se lanza un error identificable
**Y** no se entrega un vector que C13 podría insertar en `vector(1536)` y romper HNSW en silencio

### Escenario 8: Arranque y tests no llaman al proveedor
**Dado que** Compose y C17 no inyectan `JPV_EMBEDDING_API_KEY` en todos los perfiles
**Cuando** se arranca `GET /health` y se ejecuta pytest
**Entonces** `/health` no exige esa clave ni `JPV_EMBEDDING_MODEL`
**Y** la suite usa un cliente falso y no abre sockets a embeddings, LLM ni RDS
**Y** embeber de verdad sin `JPV_EMBEDDING_API_KEY` falla de forma explícita
**Y** **no** se usa `JPV_RAG_LLM_API_KEY` como sustituto

### Escenario 9: El servicio HTTP y el índice no se enteran
**Dado que** esta historia está implementada según el alcance acordado
**Cuando** se inspecciona el entregable
**Entonces** `jbg_ai.api.main` no importa `jbg_ai.indexing`
**Y** `POST /v1/index/sync` sigue siendo el stub de C13 (o 501 con `STUB_MODE=false`)
**Y** `ai-service/openapi.json` no ha cambiado
**Y** no hay migración Alembic ni EF Core
**Y** no se ha escrito ninguna fila en `ai.product_document`

### Escenario 10: Fuera de alcance explícito
**Dado que** C11 entrega la biblioteca
**Cuando** se revisa el entregable
**Entonces** **no** hay feed C12, ni *upsert* C13, ni lote AutoBulk sobre los 1.200
**Y** **no** hay tabla `ai.embedding_cache` ni Redis
**Y** **no** se mezclan embeddings visuales (1280d) con los semánticos (1536)
**Y** **no** se ha implementado el *blue/green* de cambio de modelo

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final. Nada visible para el operador hasta C16.

- **Por qué la caché RAM no “pierde los hashes”.** El hash es una función pura del texto: al reiniciar se recalcula. Lo caro es el vector. Hasta que C13 lo persista en Postgres, C11 no es un job reanudable de indexación del catálogo, y no debe serlo: no hay feed ni perfiles aprobados.

- **Por qué SKU entra en un embedding.** Semánticamente no aporta. El `tsv` de C05 se genera de `doc_text`; sin SKU en el documento la rama léxica de C21 no lo ve. El boost de SKU exacto nace de ese texto.

- **Familias hoy.** El catálogo nace huérfano (C18 no ha pasado; Docker tiene 0 familias). El constructor debe ser correcto con `family_name` nulo **y** cambiar el hash el día que exista.

- **`ProposedProfile` no es la entrada.** C09/C08 viajan con `source` y confianza; meterlos en el texto reembebería al cambiar un metadato de revisión. C13 mapeará el feed aprobado al DTO de C11.

- **Spec `embedding-management`.** Es el reconocimiento visual (C# / TF.js). No se modifica.

- **S11 vs §6.3.** El máster versiona en la misma columna con `WHERE embedding_version`. El diseño dice “columna nueva”. C11 solo **etiqueta** modelo+versión+plantilla. Cambiar a 3072 es otra migración, fuera del PF.

- **Par de zona.** El plan prohíbe C11 ‖ C13. C23 no toca `indexing/embeddings.py`.

---

## Tareas

1. Completar artefactos OpenSpec del change (`proposal`, **`design.md` obligatorio**, specs, tasks).
2. DTO + `build_source_text` / `hash_source_text` (`source-text/v1`) en `jbg_ai/indexing/`.
3. Puerto `EmbeddingClient` + adapter LiteLLM **async** + caché in-memory + assert 1536 + backoff + batch (`JPV_EMBEDDING_BATCH_SIZE`, default 64).
4. Settings `JPV_EMBEDDING_*` opcionales al boot (`API_KEY`, `MODEL`, `BASE_URL`, `BATCH_SIZE` default 64); pin en `canonical_openapi_settings`; documentar en `.env.example` (`BASE_URL` si falta).
5. Tests en `tests/indexing/` (estabilidad, orden de materiales, familia, skip de recompute, dimensión, boot sin clave). Fake inyectable en `tests/support/`.
6. `openspec validate --all --strict` antes de archivar. **No** regenerar OpenAPI.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 4 — habilitador; sin esto C13 reembebe a ciegas o inventa el texto
- **Urgencia (mercado / feedback):** **5** — 🔴; nunca se recorta; desbloquea C13 y C23
- **Complejidad / esfuerzo:** 3 — biblioteca + cliente, sin HTTP ni migración; las decisiones de texto ya están cerradas
- **Riesgos y dependencias:** C05 (esquema y 1536) y C09 (vocabularios / perfiles) archivados; C12 posterior; 0 perfiles en Docker hasta el AutoBulk; no mezclar con `ProductAiProfile.SourceHash`; no mezclar con embeddings visuales; LiteLLM ya en `pyproject.toml` (`==1.98.0`)
