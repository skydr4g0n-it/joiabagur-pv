> **Línea de corte.** Los grupos 1–6 son la mitad que **desbloquea C11**: andamiaje, vocabularios, regex de talla, puerto LiteLLM, pipeline y router real. Si la sesión se desborda (ficha C09 / regla 5 del plan), se entrega esa mitad. Los grupos 7–8 son el auditor de puertas y el cierre de docs/validate; no bloquean el HTTP.

> **Guardarraíl de contrato.** Este change **no toca** `ai-service/openapi.json`, `ai-service/migrations/`, entidades .NET ni el stub de C08. Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance: no se regenera el snapshot.

> **Guardarraíl de boot.** `JPV_RAG_LLM_*` son **opcionales** en `Settings`. `/health` no las exige. `jbg_ai.api.main` no importa `jbg_ai.data`. Compose y el perfil de snapshot se quedan en `STUB_MODE=true` hasta que haya clave RAG.

> **Guardarraíl de tests.** La suite de `tests/enrichment/` usa un `EnrichLlm` falso. Cero sockets a proveedores. Los tests de contrato existentes corren contra el stub (`STUB_MODE=true`) y **siguen verdes**.

## 1. Andamiaje, dependencia y settings

- [ ] 1.1 Crear el paquete `ai-service/src/jbg_ai/enrichment/` (`__init__.py` de reexport mínimo) y `ai-service/tests/enrichment/`. Añadir `litellm` a `ai-service/pyproject.toml` con **versión exacta fijada** (no rango abierto). **Validación:** `uv sync --system-certs` en `ai-service/` completa; `git diff ai-service/openapi.json` vacío.
- [ ] 1.2 Añadir settings opcionales `JPV_RAG_LLM_API_KEY` / `MODEL` / `BASE_URL` / `CONCURRENCY` (default **8**) en `settings.py`. String vacío = unset, igual que `JPV_CATALOG_LLM_*`. Pinnarlas a `None` en `canonical_openapi_settings`. Documentar en `backend/.env.example`. **Validación:** `test_settings_do_not_require_rag_llm_key_to_boot`; el test existente de settings mínimas en verde; `GET /health` 200 sin esas vars; `test_openapi_snapshot_is_stable` verde.

## 2. Vocabularios cerrados y normalización

- [ ] 2.1 Versionar YAML (o JSON) de vocabularios en `jbg_ai/enrichment/`: `piece_type` padres, `materials` (con `hilo`), `stone_type` (semilla del corpus + residual `piedra` + sinónimos), `size_label`, y listas cortas de `color_tags` / `style_tags` / `occasion_tags`. Sin `ENUM` de PostgreSQL. **Validación:** los ficheros existen y se cargan en tests; un valor fuera de lista no está en el set canónico.
- [ ] 2.2 Implementar normalización de sinónimos como función pura (plata de ley / 925 / sterling → `plata`; 18k → `oro`; hilo encerado → `hilo`; ámbar/amber → `ambar`; sortija/alianza → `anillo`; gargantilla → `collar`; brazalete/esclava → `pulsera`; criollas/aro → `pendientes`). `colgante` no colapsa a `collar`. **Validación:** `test_material_synonym_normalized_to_canonical_term`; `test_rejects_value_outside_closed_vocabulary`; `test_piece_type_stores_hypernym_not_hyponym`.

## 3. Regex de talla

- [ ] 3.1 Implementar la regex de talla en `jbg_ai.enrichment` (tokens C06a/C06b: `xxs`…`xxl`, `mini`, `extramini`, S/M/L, mm/cm, anillo 5–48). Preferencia `Name` > `Description`. El SKU no se inspecciona. **No** importar `jbg_ai.data` ni `scripts/catalog/`. Acierto → `source=rule`, confianza `1.0`. **Validación:** `test_size_regex_marks_field_source_as_rule`; `test_size_prefers_name_over_description`; `test_size_is_never_read_from_sku`.

## 4. Confianza por span

- [ ] 4.1 Implementar la heurística de evidencia: span de canónico o sinónimo en name/description → `0.85`; sin span → `0.45`; ausente/`[]` → `0.20`; regex de talla → `1.0`. El `confidence` del modelo no se copia. En listas, el campo toma el miembro peor evidenciado. **Validación:** `test_confidence_follows_evidence_span`; `test_empty_materials_flags_review_not_default_value`.

## 5. Prompt, schema y puerto LiteLLM

- [ ] 5.1 Escribir `ai-service/prompts/enrichment/v1.md`. El prompt pide solo valores de los vocabularios, prohíbe title/description/familia, distingue `stone_type` concreto / `piedra` / null, y no usa `style_tags` como taxonomía de subtipo. **Validación:** el fichero existe; el pipeline reporta `prompt_version = enrichment/v1`.
- [ ] 5.2 Definir el schema Pydantic de extracción y el puerto `EnrichLlm`. Implementar el adaptador LiteLLM (`acompletion` / `completion`, temp 0, `response_format`, `JPV_RAG_LLM_*`). Retry **una vez** si el JSON no parsea; segunda falla → excepción. **No** Instructor. **No** reutilizar `OpenAICatalogLlm`. **Validación:** `test_enrich_llm_uses_litellm_not_openai_catalog_client`.
- [ ] 5.3 Fake inyectable en `tests/enrichment/` y semáforo `JPV_RAG_LLM_CONCURRENCY`. **Validación:** `test_concurrency_setting_caps_in_flight_calls`; `test_unit_suite_makes_no_provider_calls`.

## 6. Pipeline y router

- [ ] 6.1 Ensamblar el pipeline: regex talla → LLM (1 producto / llamada) → normalizar vocabularios → `stone_type` (tipo / `piedra` / null) → confianza por span → `ProposedProfile` con `title` / `description` / `family_id` / `variant_label` **nulos**. Valor OOV → warning + descarte. `materials: []` sin evidencia. **Validación:** `test_extracts_multiple_materials_from_description`; `test_generic_stone_when_gem_mentioned_without_type`; `test_specific_stone_does_not_also_write_generic`; `test_stone_outside_closed_list_becomes_residual_or_null`; `test_title_description_and_family_are_null`.
- [ ] 6.2 Sustituir `require_stub_mode` en `POST /v1/enrich/products` por: stub si `stub_mode`, pipeline si no. Handler `async def` para el semáforo. Sin clave RAG en modo real → error explícito, no 501 y no perfiles inventados. **Validación:** tests de contrato existentes verdes con `STUB_MODE=true`; un test de modo real con fake no recorre el ciclo del stub; `test_openapi_snapshot_is_stable` verde; `jbg_ai.api.main` sigue sin importar `jbg_ai.data`.

## 7. Auditor de puertas (segunda mitad)

- [ ] 7.1 Función pura de auditoría: unicidad de SKU, membresía de vocabulario, cobertura de tags por estrato (`original`/`short` no castigan; `sparse` ≥ 1 lista; 90 % sobre `ai_assisted`; 70 % global sin contar `original`/`short` como fallo). **No** se engancha al POST. Sin CLI. **Validación:** `test_batch_fails_when_tag_coverage_below_threshold`; `test_tag_coverage_gate_is_evaluated_per_text_provenance`; `test_original_or_short_may_have_empty_tags`; `test_sparse_requires_at_least_one_tag_list`. Un test HTTP de lote con tags vacías responde 200, no 422.

## 8. Verificación de alcance y documentación

- [ ] 8.1 `uv run --system-certs pytest tests/enrichment tests/config tests/api/test_contracts.py tests/api/test_health.py tests/api/test_openapi_snapshot.py` en verde **sin** sockets a proveedores. **Validación:** salida sin fallos **nuevos**; comparar nombres si la suite global ya tenía rojos ajenos.
- [ ] 8.2 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/migrations/`, `backend/src/` (salvo `.env.example` de `JPV_RAG_LLM_*`), `frontend/`. El stub de C08 sigue intacto. No hay TODO/FIXME sin tarea de seguimiento.
- [ ] 8.3 Alinear docs de contexto: `Documentos/epicas.md` (EP12 enlaza HU-AIENG-009); README de `ai-service` actualiza el marcador C09; coherencia de la HU y el ticket con el entregable. **Validación:** un lector de la épica llega al extractor real, al prompt `enrichment/v1` y a la frontera «puertas fuera del HTTP».
- [ ] 8.4 Ejecutar **`openspec validate --all --strict`**. **Validación:** la salida reporta `0 failed`.
