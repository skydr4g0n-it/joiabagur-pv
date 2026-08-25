# QA — C11 `add-source-text-and-embedding-client`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-25 · **Rama:** `c11-add-source-text-and-embedding-client` · **Commit de implementación:** `a076709`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11.15 |
| Gestor | `uv` 0.11.7 — **con `--system-certs` en todas las llamadas**, según `CLAUDE.md` |
| LiteLLM | `1.98.0` (ya pinado en `ai-service/pyproject.toml`; **no** se añadió dependencia) |
| Contrato | `ai-service/openapi.json` — **no se toca**; verificado con `git diff` y `test_openapi_snapshot_is_stable` |
| Stub C13 | `POST /v1/index/sync` y `GET /v1/index/status` intactos (`DELIVERED_BY = "C13 (add-product-document-indexer)"`) |

---

## 1. Suite automática de `ai-service`

| Ejecución | Resultado |
|---|---|
| Alcance C11 (`tests/indexing` + `tests/config` + `test_health.py` + `test_openapi_snapshot.py`) | **48 passed, 0 failed** (1 warning Starlette/httpx ajeno a C11) |
| Primera pasada del mismo alcance, **antes** de quitar el `forbid_network` autouse | **8 failed** — `asyncio.run` en Windows abre `socketpair`/`connect` (ver §8) |
| `openspec validate --all --strict` | **39 passed, 0 failed** |

> **Aquí el recuento sí es fiable**, a diferencia de la suite de .NET: la de Python parte de cero fallos en este alcance y no llama a proveedores. C11 no toca .NET; no hay línea base de `dotnet test` que comparar.

Comando de la pasada de alcance (tarea 5.1):

```powershell
uv run --system-certs pytest tests/indexing tests/config tests/api/test_health.py tests/api/test_openapi_snapshot.py -q
```

### Desglose de tests nuevos o ampliados

| Fichero | Nº | Qué cubre |
|---|---|---|
| `tests/indexing/test_source_text.py` | 9 | Constante `source-text/v1`, DTO (sku/name, `extra=forbid`), estabilidad byte a byte, orden de materiales/tags, familia, ausentes, precio fuera, UUID de familia fuera |
| `tests/indexing/test_embeddings.py` | 11 | Version keys, caché, dimensión 384/3072, batch 64, LiteLLM ≠ data/enrich, clave propia, 4xx sin retry, retry 429, `api.main` sin import, stub C13, cero sockets |
| `tests/config/test_settings.py` (ampliado) | +3 | Embedding key no bloquea boot, strings en blanco = unset, `canonical_openapi_settings` pinna embeddings a `None` / batch 64 |
| `tests/api/test_health.py` (ampliado) | +1 | `GET /health` 200 sin `JPV_EMBEDDING_*` |

**Fake:** `tests/support/fake_embedding_client.py` (`FakeEmbeddingClient`). Reutiliza `LiteLlmEmbeddingClient` con `embed_batch` inyectado: cuenta llamadas al «proveedor», comparte caché y assert 1536. Ningún test de `tests/indexing/` llama a LiteLLM de verdad.

---

## 2. Escenarios de las specs, uno a uno

### `catalog-source-text`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Canonical source text is byte-stable · The same profile produces the same doc_text | `test_source_text_is_stable_for_same_profile` · `test_source_text_version_constant` | ✅ |
| Source hash is SHA-256 of the rendered document · Hash matches the rendered UTF-8 document | `test_source_text_is_stable_for_same_profile` (`digest == sha256(doc_text.encode("utf-8")).hexdigest()`, 64 hex minúsculas) | ✅ |
| Material and tag order · Reordered materials share a hash | `test_material_order_does_not_change_hash` (`Materiales: oro, plata`) | ✅ |
| Material and tag order · Reordered commercial tags share a hash | misma función, rama de `color_tags` / `style_tags` | ✅ |
| Family name change · Introducing a family name changes the hash | `test_hash_changes_when_family_changes` | ✅ |
| Family name change · Family UUID is not written | `test_family_id_uuid_is_not_in_source_text` · `test_dto_forbids_price_and_provenance_fields` (`family_id` rechazado por `extra=forbid`) | ✅ |
| Absent fields omitted · Empty optional fields leave no labelled line | `test_absent_fields_are_omitted_not_sentinel` (sin `Piedra:`/`Talla:`/`Familia:`/`Colores:`/`Estilo:`/`Ocasiones:`/`Materiales:`; sin `ninguna`/`n/a`) | ✅ |
| Price identifiers and provenance · SKU and tags enter and price does not | `test_price_is_not_in_source_text` | ✅ |
| Price identifiers and provenance · Provenance metadata is not rendered | `test_dto_forbids_price_and_provenance_fields` (`source` / `price` / `family_id` rechazados) | ✅ |
| Embedding is not recomputed · Unchanged text is served from cache | `test_embedding_not_recomputed_when_hash_unchanged` (`call_count == 1`, `cache_hits == 1`) | ✅ |
| Vectors whose dimension is not 1536 · A mismatched dimension fails loudly | `test_vector_dimension_mismatch_is_rejected` (384 y 3072 → `EmbeddingDimensionError`) | ✅ |
| LiteLLM batching retry and version keys · A batch larger than the setting is split | `test_embedding_batch_is_split_by_setting` (70 textos → 64 + 6) | ✅ |
| LiteLLM batching retry and version keys · Version keys distinguish document preprocess from model space | `test_embedding_client_exposes_distinct_version_keys` | ✅ |
| Embedding without its own key · Embed without the embedding key fails explicitly | `test_embed_without_key_fails_without_using_rag_llm_key` (`JPV_RAG_LLM_API_KEY` en el entorno; `embed_batch` no se llama) | ✅ |
| HTTP application does not import indexing · The service HTTP surface is unchanged | `test_main_does_not_import_indexing` · `test_index_routes_still_name_c13` · `test_openapi_snapshot_is_stable` · `git diff` de `openapi.json` vacío | ✅ |
| Unit suite makes no provider calls · Unit suite stays offline | `test_unit_suite_makes_no_provider_calls` (`forbid_network` + aserto de import; **sin** `asyncio.run`, ver §8) · `test_adapter_does_not_import_data_or_enrich_llm` | ✅ |

### `ai-service-runtime`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Embedding settings do not block process boot · Health starts without an embedding key | `test_settings_do_not_require_embedding_key_to_boot` · `test_health_starts_without_embedding_key` (batch 64) | ✅ |
| Embedding settings do not block process boot · Blank embedding strings are treated as unset | `test_blank_embedding_strings_are_treated_as_unset` | ✅ |
| Embedding settings do not block process boot · Canonical OpenAPI settings pin embedding keys to absent | `test_canonical_openapi_settings_pin_embedding_keys_to_absent` · `test_openapi_snapshot_is_stable` | ✅ |

**Totales:** 13 requisitos, 19 escenarios (`#### Scenario:`: 16 en `catalog-source-text` + 3 en `ai-service-runtime`). Todos tienen test nombrado y pasaron en la pasada de alcance.

---

## 3. Nombres exigidos por `tasks.md` / ticket

Lista de la ficha C11 y de [ticket.md](ticket.md). Todos existen como `def test_…` y están en verde.

| Nombre | Fichero |
|---|---|
| `test_source_text_is_stable_for_same_profile` | `test_source_text.py` |
| `test_material_order_does_not_change_hash` | `test_source_text.py` |
| `test_hash_changes_when_family_changes` | `test_source_text.py` |
| `test_embedding_not_recomputed_when_hash_unchanged` | `test_embeddings.py` |
| `test_absent_fields_are_omitted_not_sentinel` | `test_source_text.py` |
| `test_price_is_not_in_source_text` | `test_source_text.py` |
| `test_family_id_uuid_is_not_in_source_text` | `test_source_text.py` |
| `test_vector_dimension_mismatch_is_rejected` | `test_embeddings.py` |
| `test_settings_do_not_require_embedding_key_to_boot` | `test_settings.py` |
| `test_embed_without_key_fails_without_using_rag_llm_key` | `test_embeddings.py` |
| `test_unit_suite_makes_no_provider_calls` | `test_embeddings.py` |
| `test_openapi_snapshot_is_stable` | `test_openapi_snapshot.py` |

Extras que cubren escenarios de spec no nombrados en la ficha: `test_source_text_version_constant`, `test_dto_rejects_blank_sku_and_name`, `test_dto_forbids_price_and_provenance_fields`, `test_embedding_client_exposes_distinct_version_keys`, `test_embedding_batch_is_split_by_setting`, `test_adapter_does_not_import_data_or_enrich_llm`, `test_validation_4xx_is_not_retried`, `test_retry_on_429`, `test_main_does_not_import_indexing`, `test_index_routes_still_name_c13`, `test_blank_embedding_strings_are_treated_as_unset`, `test_canonical_openapi_settings_pin_embedding_keys_to_absent`, `test_health_starts_without_embedding_key`.

---

## 4. Alcance negativo (tarea 5.2)

```powershell
git diff --name-only -- ai-service/openapi.json ai-service/migrations backend/src frontend
```

Salida **vacía** respecto al alcance de C11 (`a076709` no toca esos paths). `backend/.env.example` sí documenta `JPV_EMBEDDING_*`, fuera de `src/`.

| Guardarraíl | Comprobación | Resultado |
|---|---|---|
| `ai-service/openapi.json` | no está en el commit de implementación + snapshot estable | ✅ |
| `ai-service/pyproject.toml` | no tocado (`litellm==1.98.0` ya estaba) | ✅ |
| `ai-service/migrations/` | no tocado | ✅ |
| `backend/src/` | no tocado (`.env.example` sí se documentó, fuera de `src/`) | ✅ |
| `frontend/` | no tocado | ✅ |
| Stub C13 | `routers/index.py` sigue nombrando C13; `test_index_routes_still_name_c13` | ✅ |
| `jbg_ai.api.main` no importa `jbg_ai.indexing` | `test_main_does_not_import_indexing` | ✅ |
| TODO/FIXME sin seguimiento | `rg TODO\|FIXME` en `jbg_ai/indexing/` vacío | ✅ |

---

## 5. Decisiones de diseño, verificadas en código

| Decisión | Evidencia |
|---|---|
| 1 · Biblioteca pura; el HTTP no se entera | `jbg_ai/indexing/`; `api.main` no importa el paquete; no hay router nuevo |
| 2 · DTO propio, no `ProposedProfile` | `ProductSourceText` con `extra="forbid"`; sin `source`/`confidence`/`price`/`family_id` |
| 3 · Plantilla `source-text/v1`; hash del texto renderizado | `SOURCE_TEXT_VERSION` en `constants.py`; `hash_source_text` = SHA-256 UTF-8 del `doc_text` |
| 4 · Caché RAM por `(digest, model, version)` | `InMemoryEmbeddingCache` en `embeddings.py`; sin TTL, sin Redis, sin tabla |
| 5 · LiteLLM `aembedding`; clave propia; assert 1536 | import perezoso de `aembedding`; `num_retries=0` (el retry es nuestro); `require_embedding_dimension` |
| 6 · Settings opcionales al boot; pin del snapshot | `jpv_embedding_*` default `None` / batch 64; `canonical_openapi_settings` las pinna |

Retry de proveedor: backoff `0.25 * 2**attempt` en 429/5xx (`test_retry_on_429`); 4xx de validación no se reintenta (`test_validation_4xx_is_not_retried`). **No** L2 extra.

---

## 6. Documentación de contexto (tarea 5.3)

| Documento | Qué se alineó |
|---|---|
| `Documentos/epicas.md` (EP12) | Enlace a HU-AIENG-011 + bloque **Entregable C11** (biblioteca `indexing/`, `source-text/v1`, sin HTTP ni SQL) |
| `ai-service/README.md` | Marcador C11; tabla `JPV_EMBEDDING_*`; nota de clave propia vs RAG |
| `ai-service/tests/README.md` | `indexing/` poblada |
| `backend/.env.example` | `JPV_EMBEDDING_MODEL=openai/text-embedding-3-small`, `BASE_URL`, `BATCH_SIZE=64` |
| [ticket.md](ticket.md) | DoD cubierto por tests; el change no escribe filas ni regenera OpenAPI |

---

## 7. OpenSpec

```powershell
openspec validate --all --strict
```

**39 passed, 0 failed.** Incluye el change `add-source-text-and-embedding-client` y todas las specs vivas. Ejecutado en la forma `--all --strict`, no en la de un solo change (`CLAUDE.md`).

---

## 8. Defecto encontrado durante la implementación

**`forbid_network` autouse rompe `asyncio.run` en Windows.** La primera pasada de `tests/indexing` falló 8 tests con `AssertionError: stub mode must not open a network connection` dentro de `socket.socketpair` → `connect`, disparado al crear el `ProactorEventLoop`. No era una llamada a un proveedor: era el event loop.

C09 ya lo había resuelto: `tests/enrichment/conftest.py` **no** auto-aplica `forbid_network`; el test `test_unit_suite_makes_no_provider_calls` lo pide como fixture y **no** llama a `asyncio.run`. C11 copia ese patrón.

**Corrección:** `tests/indexing/conftest.py` queda como comentario (igual que enrichment). Los tests de `embed()` usan `asyncio.run` **sin** `forbid_network`. El gate de sockets se queda en `test_unit_suite_makes_no_provider_calls` (aserto de import, sin loop). Tras el arreglo: **48 passed**.

No se cambia el event loop global del servicio: es el mismo hallazgo de plataforma que C05 documentó para psycopg async, y este change no abre sesiones.

---

## 9. Fuera de esta pasada (no DoD)

- Feed C12, *upsert* C13, AutoBulk sobre los 1.200, filas en `ai.product_document`.
- Suite global de .NET: C11 no la toca; no se midió línea base.
- Regenerar `openapi.json`: **prohibido** por el change; el snapshot está verde sin regenerar.
- Llamada real a un proveedor de embeddings: **prohibida** en la suite; el adapter se prueba con `embed_batch` inyectado.
- `/opsx:verify` formal: no se invocó en esta sesión; el cruce escenario ↔ test está en §2.
