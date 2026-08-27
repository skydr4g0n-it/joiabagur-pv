> **Línea de corte.** Los grupos 1–4 son la mitad **archivable** si la sesión desborda (ficha C14 / regla 5): settings de umbral, puerto de búsqueda, orquestador embed+`<=>`+score, router stub/real con 200/503 y stub intacto. Los grupos 5–7 son filtros del body, nota de `mode`, logs de etapa y cierre de docs/validate. Sin el grupo 4 C15 sigue viendo 501.

> **Guardarraíl de freeze.** `git diff` de `ai-service/src/jbg_ai/indexing/embeddings.py` **vacío**. `ai-service/openapi.json` **no se regenera**. Si `test_openapi_snapshot_is_stable` se pone rojo, el change se ha salido de alcance. Substitutes intacto (`require_stub_mode` + C26). Sin Alembic. Sin migración EF. Sin `ai.query_log`. Sin filtro por `pos_id`.

> **Guardarraíl de boot y secretos.** `JPV_RETRIEVAL_DISTANCE_THRESHOLD` es **opcional** en `Settings` (default 0,65). `/health` no la exige. Real mode sin key/DB/índice compatible → **503** nombrando el fallo, no 501 ni 200 con `low_confidence`. Pin en `canonical_openapi_settings`. La key de embeddings no se loguea. 503 se **lanza**, no se declara en `responses` del router (eso alteraría el snapshot).

> **Guardarraíl de tests.** Nombres `test_<unidad>_<escenario>_<esperado>`. Fakes de embed y de puerto de búsqueda. Cero sockets a OpenAI. Tests de BD pgvector: opcionales y *skip* si Docker no responde. Un pytest **no** exige 1.200 filas. `uv run` lleva `--system-certs`. Actualizar `tests/api/test_stub_mode.py`: `/v1/retrieval/products` entra en `_REAL_WHEN_STUBS_OFF`; el 501 que nombra el change pasa a `/v1/retrieval/substitutes` (C26).

## 1. Settings de umbral y pin del snapshot

- [ ] 1.1 Añadir `JPV_RETRIEVAL_DISTANCE_THRESHOLD` en `settings.py` (float, default **0,65**). String vacío → 0,65. Rango `0 < x ≤ 2`. Pinnar a `0.65` en `canonical_openapi_settings`. **Validación:** `test_settings_do_not_require_retrieval_threshold_to_boot`; blank → 0,65; `GET /health` 200 sin esa var; `test_canonical_openapi_settings_pin_retrieval_threshold`; `test_openapi_snapshot_is_stable` verde **sin** regenerar.

## 2. Puerto de búsqueda

- [ ] 2.1 Crear `ai-service/src/jbg_ai/retrieval/` (`__init__.py` de reexport mínimo) y `ai-service/tests/retrieval/`. Puerto inyectable (p.ej. `ProductSearchPort`): `count_compatible(model_version_key / model_id)` y `search(query_vec, threshold, overfetch, filters) → hits` con `product_id`, `sku`, `distance`, `materials`, `family_id`, `variant_label`. Implementación SQLAlchemy **Core** async sobre `session_scope` / engine existentes. Predicados fijos: `embedding IS NOT NULL`, `is_active IS TRUE`, compatibilidad `model_version_key` (prefijo de `embedding_version` o igualdad de `embedding_model`), `embedding <=> :q <= :threshold`. `ORDER BY embedding <=> :q ASC` + `LIMIT :overfetch`. **No** hinchar `indexing/repository.py`. **No** mapped class. **No** segundo engine. **No** `SELECT` en `public`. Fake in-memory para tests. **Validación:** el fake cubre count/search; ningún test de `tests/retrieval/` abre RDS ni sockets.

## 3. Orquestador (embed, score, overfetch, abstención)

- [ ] 3.1 Orquestador async en `retrieval/`: embebe `query` con `LiteLlmEmbeddingClient(..., max_attempts=1)` (instancia distinta de `index_embed`); `overfetch = over_retrieval_count(top_k)`; score `clamp(1 − distance, 0, 1)`; `match_reasons` mínimo `["vector"]`; `candidates_returned = len(results)`; `low_confidence` true solo si hay índice compatible y 0 hits; `effective_pos_id` del token. Count compatible = 0 o fallo de embed/dimensión → error de dependencia (el router lo traduce a 503). **Validación:** `test_returns_empty_with_low_confidence_when_all_above_threshold`; `test_returns_overfetched_candidate_count` (`top_k=5` → como mucho 15, y no más que los que pasaron el umbral); `test_results_ordered_by_ascending_distance`; `test_retrieval_embed_client_uses_max_attempts_one`; `git diff` de `embeddings.py` vacío.

## 4. Router stub vs real (primera mitad 🔴)

- [ ] 4.1 `retrieval.py` `/products`: `async def`; si `stub_mode` → `retrieval_products_stub` (cero I/O); si no → orquestador. Quitar `require_stub_mode` **solo** de products. Substitutes intacto. Auth `get_service_principal`. Importar `retrieval` **desde el router**, no desde `api.main`. 503 si faltan `JPV_EMBEDDING_API_KEY` (sin fake), `DATABASE_URL` (sin fake) o count compatible = 0; `detail` nombra el fallo. Inyección `request.app.state.retrieval_embed` / `retrieval_search`. **No** añadir 503 al diccionario `responses` del router. Actualizar `test_stub_mode.py`: products en `_REAL_WHEN_STUBS_OFF`; `test_501_message_names_the_delivering_change` apunta a `/v1/retrieval/substitutes` (C26). **Validación:** `test_stub_mode_still_returns_fixtures`; `test_missing_embedding_key_is_503`; `test_empty_compatible_index_is_503_not_abstention`; token sin `pos_id` → 401; `test_unimplemented_route_returns_501_when_stub_mode_off` ya no incluye products; `test_openapi_snapshot_is_stable` verde; tests de contrato `/v1/retrieval/products` en stub siguen en 200.

## 5. Filtros del body y `mode`

- [ ] 5.1 Predicados opcionales: `materials` no vacío → `&&`; `category` → igualdad `piece_type`; `family_id` UUID válido → igualdad; string que no parsea → **422** desde el handler (schema Pydantic intacto). `exclude_product_ids`: UUIDs malformados se ignoran (log Debug); los válidos salen de `results`. **No** filtrar `pos_id`, precio ni stock. **Validación:** `test_body_filters_materials_category_family_and_exclusions`; `family_id` inválido → 422; exclusión malformada no tumba la query; aserto de que el SQL de búsqueda no menciona `pos_id` como predicado.

- [ ] 5.2 Cualquier `mode` (`hybrid` default, `lexical`, `vector`) ejecuta la rama vectorial. Rellenar `debug.vector_score`; si `mode` es hybrid o lexical, `debug.notes` incluye `vector_only_until_c21`. No inventar `"lexical"` en `match_reasons`. **Validación:** `test_hybrid_and_lexical_modes_run_vector_branch` (no 501; nota presente); `mode=vector` sin esa nota.

## 6. Logs de etapa

- [ ] 6.1 Logs estructurados `stage=embed` (`trace_id`, `latency_ms`, `model`, `cache_hits`) y `stage=search` (`trace_id`, `latency_ms`, `distance_min` null si 0 hits, `candidates`, `low_confidence`, `mode`, `threshold`). Query de operador solo Debug. Sin dump del vector a Information. Sin `INSERT` en `query_log`. **Validación:** `test_trace_id_appears_in_stage_logs` (caplog: `trace_id` en embed y search).

## 7. Docs, alcance negativo y validate

- [ ] 7.1 Enlazar HU-AIENG-014 en `Documentos/epicas.md` (EP14). Actualizar el README de `ai-service` si el marcador C14 existe. **Validación:** un lector de la épica llega al retriever vectorial, al umbral 0,65, a «hybrid=vector hasta C21» y a «sin `query_log` / sin OpenAPI / sin `embeddings.py`».

- [ ] 7.2 Confirmar alcance negativo: `git diff` de `embeddings.py` y `openapi.json` vacío; substitutes sigue 501 en real mode; no hay Alembic ni cambios en `backend/src/` / `frontend/` / `IAiGatewayClient`; no hay tabla `query_log`; no hay TODO/FIXME sin tarea de seguimiento. **Validación:** diffs vacíos en esas rutas; `test_unimplemented_route_returns_501_when_stub_mode_off` sigue cubriendo substitutes.

- [ ] 7.3 `uv run --system-certs pytest tests/retrieval tests/api tests/config` (y el snapshot OpenAPI) en verde **sin** sockets a proveedores. Comparar **nombres** de fallos contra el baseline si se corre la suite completa. Ejecutar **`openspec validate --all --strict`**. **Validación:** sin fallos **nuevos** en pytest de ai-service; la salida OpenSpec reporta `0 failed`.

Smoke local contra los 1.200 (query obvia → 200 con candidatos; query absurda → 200 + `low_confidence`) es **verificación posterior**, no una tarea de merge.
