# QA — C14 `add-vector-retrieval-endpoint`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-27 · **Rama:** `c14-add-vector-retrieval-endpoint` · **Commit de artefactos (HEAD, sin commit de implementación aún):** `eb1fbdc`
> **Seguimiento verify:** misma fecha. `/opsx:verify` 0 CRITICAL, 0 WARNING, 2 SUGGESTION. SUGGESTION cerradas: SQL cosine `<=>` / no L2; caplog DEBUG de exclusiones malformadas. Alcance C14 al cierre: **144 passed**. Ver §1, §7 y §8.5.
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11.15 |
| Gestor | `uv` 0.11.7 — **con `--system-certs` en todas las llamadas `uv run`**, según `CLAUDE.md` |
| Contrato | `ai-service/openapi.json` — **no se regenera**. `test_openapi_snapshot_is_stable` verde **sin** tocar el snapshot |
| Freeze C11 | `git diff -- ai-service/src/jbg_ai/indexing/embeddings.py` **vacío** |
| Stub C26 | `POST /v1/retrieval/substitutes` intacto (`SUBSTITUTES_DELIVERED_BY = "C26 (add-substitutes-retrieval)"`) |
| .NET | **No se ejecuta** `dotnet test`: C14 no cruza `backend/src/`. Ver §4 |
| Docker / pgvector | **No se exige.** Los tests de `tests/retrieval/` inyectan fakes. Un pytest **no** pide 1.200 filas |

---

## 1. Suite automática de `ai-service`

> **Aquí el recuento sí es fiable**, a diferencia de la suite de .NET: la de Python parte de cero fallos en este alcance y no llama a proveedores ni a RDS. C14 no toca .NET; no hay línea base de `dotnet test` que comparar.

| Ejecución | Resultado |
|---|---|
| Primera pasada de alcance (`tests/retrieval` + `tests/api` + `tests/config`) | **14 failed** — `asyncio.run` en Windows abre `socketpair`/`connect` bajo `forbid_network` autouse (ver §8) |
| Misma alcance, tras quitar el autouse (mismo patrón C09/C11) | **144 passed, 0 failed** (1 warning Starlette/httpx ajeno a C14), 5,65 s |
| Re-pasada tras usar `status_code=422` literal (warning Starlette `HTTP_422_UNPROCESSABLE_ENTITY`) | **144 passed, 0 failed** (1 warning Starlette/httpx), 5,07 s |
| `/opsx:verify` (artefactos vs código) | Completeness 10/10, Correctness 10/10, Coherence seguida; **0 CRITICAL, 0 WARNING, 2 SUGGESTION** |
| Re-pasada de los dos tests endurecidos | **2 passed** (`test_search_sql_does_not_use_pos_id_as_a_predicate`, `test_malformed_exclusions_are_ignored`) |
| Alcance C14 tras cerrar SUGGESTION | **144 passed, 0 failed** (1 warning Starlette/httpx), 6,19 s |
| `openspec validate --all --strict` | **42 passed, 0 failed** |

No se corrió la suite completa de `ai-service` ni `tests/migrations`: C14 no añade revisión Alembic. No hay comparación nombre-a-nombre contra un baseline de pytest global.

Comando de la pasada de alcance (tarea 7.3):

```powershell
uv run --system-certs pytest tests/retrieval tests/api tests/config -q --tb=short
openspec validate --all --strict
```

El snapshot OpenAPI entra en `tests/api`.

### Desglose de tests nuevos o ampliados

| Fichero | Nº | Qué cubre |
|---|---|---|
| `tests/retrieval/test_search_port.py` | 3 | Fake `count_compatible` / `search`; SQL de búsqueda sin `pos_id` / `public` / precio / stock; **`<=>` presente, `<->` ausente** (SUGGESTION del verify) |
| `tests/retrieval/test_orchestrator.py` | 13 | Abstención 200, overfetch 15, no relleno sobre umbral, orden por distancia, count 0 → error de dependencia, `max_attempts=1` + freeze `MAX_EMBED_ATTEMPTS=3`, filtros del body, `family_id` inválido, exclusiones malformadas **con caplog DEBUG**, hybrid/lexical, `mode=vector` sin nota, `trace_id` en logs, embed fallido |
| `tests/api/test_retrieval_real.py` | 12 | Stub C02 cero I/O, 503 key / `DATABASE_URL` / índice vacío, real ≠ 501, 401 sin `pos_id`, body `pos_id` ignorado, 422, hybrid/lexical HTTP, vector sin nota, provider 503, logs HTTP |
| `tests/config/test_settings.py` (ampliado) | +4 | Umbral no bloquea boot, blank → 0,65, fuera de `(0, 2]` rechazado, pin canónico 0,65 |
| `tests/api/test_health.py` (ampliado) | +1 | `GET /health` 200 con default 0,65 |
| `tests/api/test_stub_mode.py` (ajustado) | 0 nuevos | `/v1/retrieval/products` **excluido** del 501; `test_501_message_names_the_delivering_change` apunta a substitutes (C26) |

**33 tests nuevos** (3+13+12+4+1). **Fakes:** `tests/support/fake_product_search.py` (`FakeProductSearch`, `FakeIndexedRow`); embed reutiliza `tests/support/fake_embedding_client.py` (`FakeEmbeddingClient` de C11). Ningún test de `tests/retrieval/` construye `SqlAlchemyProductSearch` ni abre socket a OpenAI / LiteLLM / RDS.

---

## 2. Escenarios de las specs, uno a uno

### `vector-retrieval`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Real product retrieval replaces the stub · Stub mode keeps the C02 fixtures | `test_stub_mode_still_returns_fixtures` (200, `candidates_returned == 6`, cero llamadas a embed/search) | ✅ |
| Real product retrieval replaces the stub · Real mode is not 501 | `test_real_mode_is_not_501` (200, `RetrievalResponse`, `low_confidence is False`) | ✅ |
| Real product retrieval replaces the stub · Substitutes stay unimplemented | `test_unimplemented_route_returns_501_when_stub_mode_off` (substitutes sigue en `STUB_ONLY_REQUESTS`) · `test_501_message_names_the_delivering_change` (`C26` en el detalle) | ✅ |
| Real product retrieval replaces the stub · OpenAPI snapshot stays frozen | `test_openapi_snapshot_is_stable` · `git diff` de `openapi.json` vacío | ✅ |
| Query embedding uses the C11 client with a single attempt · Retrieval embed client does not retry | `test_retrieval_embed_client_uses_max_attempts_one` (`max_attempts == 1`, `MAX_EMBED_ATTEMPTS == 3`) · `git diff` de `embeddings.py` vacío | ✅ |
| Query embedding uses the C11 client with a single attempt · Missing embedding key is 503 | `test_missing_embedding_key_is_503` (503 nombra `JPV_EMBEDDING_API_KEY`; `/health` 200; sin `low_confidence`) | ✅ |
| Query embedding uses the C11 client with a single attempt · Provider failure is not an empty success | `test_embed_failure_is_a_dependency_error` · `test_provider_failure_is_503` (503, no body de abstención) | ✅ |
| Search uses cosine distance · Results are ordered by ascending distance | `test_results_ordered_by_ascending_distance` (score = `1 − d`, `match_reasons` contiene `"vector"`, no `"lexical"`) | ✅ |
| Search uses cosine distance · Distance above the threshold is excluded | `test_returns_empty_with_low_confidence_when_all_above_threshold` (200, `results=[]`, `low_confidence=true`, umbral 0,65, sin segundo intento) | ✅ |
| Search uses cosine distance · Incompatible embeddings do not count as abstention | `test_empty_compatible_index_raises_dependency_error` · `test_empty_compatible_index_is_503_not_abstention` | ✅ |
| Over-retrieval applies after the distance filter · Overfetch is capped after the threshold | `test_returns_overfetched_candidate_count` (`top_k=5` → 15) | ✅ |
| Over-retrieval applies after the distance filter · Overfetch does not refill from rows above the threshold | `test_overfetch_does_not_refill_from_rows_above_threshold` (2 hits bajo 0,65, no se rellena a 15) | ✅ |
| Over-retrieval applies after the distance filter · Token pos_id is echoed and body pos_id is ignored | `test_body_pos_id_is_ignored` (`effective_pos_id` = claim) · `test_search_sql_does_not_use_pos_id_as_a_predicate` (`<=>` presente; `<->` / `pos_id` ausentes) | ✅ |
| Body filters restrict the candidate set · The four body predicates are applied | `test_body_filters_materials_category_family_and_exclusions` | ✅ |
| Body filters restrict the candidate set · Invalid family_id is 422 | `test_invalid_family_id_raises_before_search` · `test_invalid_family_id_is_422` | ✅ |
| Body filters restrict the candidate set · Malformed exclusions are ignored | `test_malformed_exclusions_are_ignored` (UUID válido excluido; `"nope"` / `"also-bad"` no tumban; caplog DEBUG nombra `exclude_product_id`) | ✅ |
| Hybrid and lexical modes run the vector branch · Default hybrid is not 501 | `test_hybrid_and_lexical_modes_run_vector_branch` · `test_hybrid_and_lexical_modes_are_not_501` (nota `vector_only_until_c21`) | ✅ |
| Hybrid and lexical modes run the vector branch · Explicit vector mode needs no until-C21 note | `test_vector_mode_omits_until_c21_note` (orquestador y HTTP) | ✅ |
| Missing database configuration is 503 · Absent DATABASE_URL is 503 | `test_missing_database_url_is_503` (503 nombra `DATABASE_URL`; `/health` 200) | ✅ |
| Stage logs carry trace_id · trace_id appears in stage logs | `test_trace_id_appears_in_stage_logs` (orquestador + HTTP; `stage=embed` y `stage=search`) | ✅ |
| Retrieval unit tests make no provider or database calls · Unit suite stays offline | fakes inyectados; `tests/retrieval/` no instancia el puerto SQL; ningún test exige 1.200 filas | ✅ |

### `ai-service-runtime`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Retrieval distance threshold does not block process boot · Health starts without a retrieval threshold | `test_settings_do_not_require_retrieval_threshold_to_boot` · `test_health_starts_without_retrieval_threshold` (default 0,65; `/health` 200) | ✅ |
| Retrieval distance threshold does not block process boot · Blank retrieval threshold is treated as the default | `test_blank_retrieval_threshold_is_treated_as_default` | ✅ |
| Retrieval distance threshold does not block process boot · Canonical OpenAPI settings pin the retrieval threshold | `test_canonical_openapi_settings_pin_retrieval_threshold` · `test_openapi_snapshot_is_stable` | ✅ |

**Totales de escenarios `#### Scenario:` en los deltas:** 21 (`vector-retrieval`) + 3 (`ai-service-runtime`) = **24**. Los 24 tienen test o comprobación nombrada. Extra de rango: `test_settings_reject_retrieval_threshold_outside_cosine_domain` (`0` y `2.1` → `ValidationError`); no es un escenario de spec, cubre el `Field(gt=0, le=2)`.

---

## 3. Nombres exigidos por `tasks.md` / ticket

Lista de la ficha C14. Todos existen como `def test_…` (o el `git diff` / validate de la tarea) y están en verde.

| Nombre | Fichero |
|---|---|
| `test_settings_do_not_require_retrieval_threshold_to_boot` | `test_settings.py` |
| `test_canonical_openapi_settings_pin_retrieval_threshold` | `test_settings.py` |
| `test_openapi_snapshot_is_stable` | `test_openapi_snapshot.py` |
| `test_returns_empty_with_low_confidence_when_all_above_threshold` | `test_orchestrator.py` |
| `test_returns_overfetched_candidate_count` | `test_orchestrator.py` |
| `test_results_ordered_by_ascending_distance` | `test_orchestrator.py` |
| `test_retrieval_embed_client_uses_max_attempts_one` | `test_orchestrator.py` |
| `test_stub_mode_still_returns_fixtures` | `test_retrieval_real.py` |
| `test_missing_embedding_key_is_503` | `test_retrieval_real.py` |
| `test_empty_compatible_index_is_503_not_abstention` | `test_retrieval_real.py` |
| `test_unimplemented_route_returns_501_when_stub_mode_off` | `test_stub_mode.py` (ya no incluye products) |
| `test_501_message_names_the_delivering_change` | `test_stub_mode.py` (ahora `/v1/retrieval/substitutes`, `C26`) |
| `test_body_filters_materials_category_family_and_exclusions` | `test_orchestrator.py` |
| `test_hybrid_and_lexical_modes_run_vector_branch` | `test_orchestrator.py` |
| `test_trace_id_appears_in_stage_logs` | `test_orchestrator.py` y `test_retrieval_real.py` |

Extras que cubren validaciones de tarea no homónimas en la ficha: `test_blank_retrieval_threshold_is_treated_as_default`, `test_health_starts_without_retrieval_threshold`, `test_settings_reject_retrieval_threshold_outside_cosine_domain`, `test_overfetch_does_not_refill_from_rows_above_threshold`, `test_empty_compatible_index_raises_dependency_error`, `test_missing_database_url_is_503`, `test_token_without_pos_id_is_401`, `test_body_pos_id_is_ignored`, `test_invalid_family_id_raises_before_search`, `test_invalid_family_id_is_422`, `test_malformed_exclusions_are_ignored`, `test_search_sql_does_not_use_pos_id_as_a_predicate`, `test_hybrid_and_lexical_modes_are_not_501`, `test_vector_mode_omits_until_c21_note`, `test_provider_failure_is_503`, `test_embed_failure_is_a_dependency_error`, `test_real_mode_is_not_501`, `test_fake_count_compatible_ignores_inactive_and_incompatible_rows`, `test_fake_search_applies_threshold_overfetch_and_body_filters`.

---

## 4. Alcance negativo (tarea 7.2)

```powershell
git diff --stat -- ai-service/src/jbg_ai/indexing/embeddings.py ai-service/openapi.json backend/src frontend
```

Salida **vacía**.

| Guardarraíl | Comprobación | Resultado |
|---|---|---|
| `indexing/embeddings.py` | `git diff` vacío contra HEAD | ✅ |
| `ai-service/openapi.json` | `git diff` vacío + `test_openapi_snapshot_is_stable` | ✅ |
| 503 no se declara en `responses` del router | `retrieval.py` usa `V1_RESPONSES` (401/501); 503 se lanza, no se documenta | ✅ |
| `jbg_ai.api.main` no menciona `jbg_ai.retrieval` | `rg` sobre `main.py` vacío; el router importa el paquete | ✅ |
| Substitutes sigue 501 en real mode | `require_stub_mode` + `SUBSTITUTES_DELIVERED_BY`; tests de stub_mode | ✅ |
| Alembic | ninguna revisión nueva (`migrations/versions/` intacto: `f46c55c056e2`, `b8e3c1a4d7f0`) | ✅ |
| `backend/src/` / `frontend/` / `IAiGatewayClient` | `git diff` de esas rutas vacío | ✅ |
| `ai.query_log` | `rg query_log` en `jbg_ai/retrieval/` vacío; no hay `INSERT` | ✅ |
| Filtro por `pos_id` | `test_search_sql_does_not_use_pos_id_as_a_predicate` (`pos_id` / `public.` / `price` / `stock` ausentes; `<=>` presente; `<->` ausente) | ✅ |
| TODO/FIXME sin seguimiento | `rg TODO\|FIXME` en `jbg_ai/retrieval/` vacío | ✅ |

---

## 5. Decisiones de diseño, verificadas en código

| Decisión | Evidencia |
|---|---|
| 1 · Stub vs real en el handler, como C09/C13 | `routers/retrieval.py`: `stub_mode` → fixtures; si no, orquestador o 503. `async def retrieve_products` (nombre conservado: `operationId` del snapshot). `get_service_principal`. Import de `retrieval` **solo** desde el router. 503 **no** entra en `responses` |
| 2 · Embed C11 con `max_attempts=1` | `build_retrieval_embed_client`; instancia distinta de `index_embed`; `embeddings.py` sin diff |
| 3 · Compatibilidad `model_version_key`, no `document_version_key` | SQL `embedding_version LIKE :version_prefix OR embedding_model = :model_id`; count 0 → `RetrievalDependencyError` / 503 |
| 4 · Umbral sobre distancia en SQL; score en el handler | `embedding <=> CAST(:q AS vector) <= :threshold`; `clamp_score`; default 0,65; overfetch **después** del `WHERE` |
| 5 · Filtros del body; `family_id` 422; exclusiones tolerantes | `parse_body_filters` + `compile_search_sql` (`&&`, `piece_type`, `family_id`, `<> ALL`); HTTP 422 desde el handler |
| 6 · hybrid/lexical ejecutan vector hasta C21 | misma rama; `debug.notes` incluye `vector_only_until_c21`; `match_reasons` no inventa `"lexical"` |
| 7 · Abstención 200 vs índice caído 503 | umbral → 200 + `low_confidence`; count 0 / key / `DATABASE_URL` / embed → 503 nombrando el fallo |
| 8 · Query propia en `retrieval/`; no hinchar el repo C13 | `SqlAlchemyProductSearch` + `ProductSearchPort`; Core + `session_scope`; fake in-memory |
| 9 · Logs de etapa, no `query_log` | `stage=embed` / `stage=search` con `trace_id`; query solo Debug |

El `operationId` `retrieve_products_v1_retrieval_products_post` se conservó a propósito: el handler se llama `retrieve_products` y el orquestador se importa como `run_product_retrieval`. Renombrarlo habría regenerado el snapshot.

---

## 6. Documentación de contexto (tarea 7.1)

| Documento | Qué se alineó |
|---|---|
| `Documentos/epicas.md` (EP14) | HU-AIENG-014 + bloque C14: retriever vectorial, umbral 0,65, hybrid=vector hasta C21, **sin** `query_log` / **sin** OpenAPI / **sin** `embeddings.py` |
| `ai-service/README.md` | Marcador C14 (ya no es 501); 503 vs 501; layout de `retrieval/`; non-goals actualizados |
| `ai-service/tests/README.md` | `retrieval/` poblada; C14 landed en `api/` |
| [ticket.md](ticket.md) / [tasks.md](tasks.md) | 10/10 tareas marcadas; DoD cubierto por los tests de §3 |

Completar Compose / `.env.example` **no** era obligatorio: el umbral tiene default; `JPV_EMBEDDING_*` ya existen (C11).

---

## 7. OpenSpec

```powershell
openspec validate --all --strict
```

**42 passed, 0 failed.** Incluye el change `add-vector-retrieval-endpoint` y todas las specs vivas. Ejecutado en la forma `--all --strict`, no en la de un solo change (`CLAUDE.md`).

`openspec status --change add-vector-retrieval-endpoint` (al arrancar el apply): artefactos proposal/design/specs/tasks **done**. Al cierre: 10/10 tareas marcadas.

`/opsx:verify` se ejecutó el 2026-08-27. Scorecard: Completeness 10/10, Correctness 10/10, Coherence seguida. Cero CRITICAL, cero WARNING, 2 SUGGESTION (cerradas en §8.5). El informe va en el chat de verify, no se duplica aquí.

---

## 8. Incidencias y huecos de esta pasada

### 8.1. `forbid_network` autouse rompe `asyncio.run` en Windows

La primera pasada de `tests/retrieval` falló **14 tests** con `AssertionError: stub mode must not open a network connection` dentro de `socket.socketpair` → `connect`, disparado al crear el `ProactorEventLoop`. No era una llamada a un proveedor: era el event loop.

C09 y C11 ya lo habían resuelto: `tests/enrichment/conftest.py` y `tests/indexing/conftest.py` **no** auto-aplican `forbid_network`. C14 copia ese patrón.

**Corrección:** `tests/retrieval/conftest.py` queda como comentario. Los tests del orquestador usan `asyncio.run` **sin** `forbid_network`. El gate de sockets es de construcción: fakes inyectados, cero `SqlAlchemyProductSearch` en `tests/retrieval/`. Tras el arreglo: **144 passed**.

### 8.2. `operationId` y el handler async

Un primer borrador del router se llamó `retrieve_products_route`. FastAPI deriva el `operationId` del nombre de la función (`retrieve_products_v1_retrieval_products_post` en el snapshot). Se revirtió **antes** de la pasada verde: el handler se llama `retrieve_products`; el orquestador entra como `run_product_retrieval`. `test_openapi_snapshot_is_stable` quedó verde **sin** regenerar.

### 8.3. Warning `HTTP_422_UNPROCESSABLE_ENTITY`

Starlette depreca la constante. El handler pasa a `status_code=422` literal. La re-pasada de 144 tests ya no emite ese warning; queda el de `httpx`/`TestClient`, ajeno a C14.

### 8.4. `caplog` y `configure_logging`

`create_app` hace `root.handlers.clear()`, así que un test HTTP que construye la app **después** de montar el fixture `caplog` pierde el handler. `test_trace_id_appears_in_stage_logs` de `test_retrieval_real.py` reengancha `caplog.handler` al root. El test homónimo del orquestador no pasa por `create_app` y no lo necesita.

### 8.5. SUGGESTION del verify — **cerradas**

| SUGGESTION | Corrección |
|---|---|
| El test del SQL no fija el operador cosine | `test_search_sql_does_not_use_pos_id_as_a_predicate` exige `"<=>" in sql` y `"<->" not in sql` |
| El log Debug de exclusiones malformadas no está asertado | `test_malformed_exclusions_are_ignored` captura DEBUG del orquestador: nombra `exclude_product_id`, incluye `nope` / `also-bad`, no registra el UUID válido |

No se añadieron tests nuevos (siguen 3 + 13 en `tests/retrieval/`). La re-pasada de alcance tras el cierre: **144 passed**.

---

## 9. Fuera de esta pasada (no DoD)

- Smoke local `POST /v1/retrieval/products` contra los 1.200 con `STUB_MODE=false` (query obvia → 200 con candidatos; query absurda → 200 + `low_confidence`). La ficha lo deja como **verificación posterior**.
- Suite global de `ai-service` (`tests/migrations`, `tests/indexing`, …) y `dotnet test` nombre-a-nombre: C14 no toca Alembic ni `backend/src/`.
- Búsqueda léxica / RRF / sinónimos (C20/C21). Proyección POS (C22). Substitutes real (C26). Hidratación .NET (C15).
- Regenerar `openapi.json`: **prohibido** por el change; el snapshot está verde sin regenerar.
- Editar `indexing/embeddings.py` (congelado para C23).
- `ai.query_log` / Alembic de telemetría de queries.

---

## Veredicto

**Sin problemas críticos.** Alcance C14 al cierre: **144 passed, 0 failed** (`uv run --system-certs pytest tests/retrieval tests/api tests/config`, 6,19 s). Snapshot OpenAPI verde **sin** regenerar, `openspec validate --all --strict` 42/0, diffs vacíos en `embeddings.py` / `openapi.json` / `backend/src/` / `frontend/`, 10/10 tareas, 24/24 escenarios, 2/2 SUGGESTION del verify cerradas.

**Listo para archivar.** El smoke contra los 1.200 sigue siendo verificación posterior.
