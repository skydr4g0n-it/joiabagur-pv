# QA — C09 `add-catalog-enrichment-pipeline`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-23 · **Rama:** `c09-add-catalog-enrichment-pipeline` · **Commit de base (HEAD, sin commit de implementación aún):** `a4b0457`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11.15 |
| Gestor | `uv` 0.11.7 — **con `--system-certs` en todas las llamadas**, según `CLAUDE.md` |
| LiteLLM | `1.98.0` (pin exacto en `ai-service/pyproject.toml`) |
| PyYAML | `6.0.3` (pin exacto; loader de vocabularios) |
| Contrato | `ai-service/openapi.json` — **no se toca**; verificado con `git diff` y `test_openapi_snapshot_is_stable` |
| Stub C08 | `enrich_products_stub` intacto; se sirve cuando `STUB_MODE=true` |

---

## 1. Suite automática de `ai-service`

| Ejecución | Resultado |
|---|---|
| Alcance C09 (`tests/enrichment` + `tests/config` + `test_contracts.py` + `test_health.py` + `test_openapi_snapshot.py` + `test_stub_mode.py`) | **81 passed, 0 failed** |
| Frontera C06b (`tests/data/test_scope.py` + `tests/data/test_envload.py`) | **3 passed, 0 failed** |
| `openspec validate --all --strict` | **37 passed, 0 failed** |

> **Aquí el recuento sí es fiable**, a diferencia de la suite de .NET: la de Python parte de cero fallos en este alcance y no llama a proveedores. C09 no toca .NET; no hay línea base de `dotnet test` que comparar.

Comando de la pasada de alcance (tarea 8.1):

```powershell
uv run --system-certs pytest tests/enrichment tests/config tests/api/test_contracts.py tests/api/test_health.py tests/api/test_openapi_snapshot.py tests/api/test_stub_mode.py -q --tb=short
```

### Desglose de tests nuevos o ampliados

| Fichero | Nº | Qué cubre |
|---|---|---|
| `tests/enrichment/test_vocabularies.py` | 4 | Carga YAML, OOV, sinónimos de material/piedra, hiperónimo de `piece_type` |
| `tests/enrichment/test_size.py` | 4 | Talla `rule` sobre el nombre, nombre gana a descripción, fallback a descripción, SKU ignorado |
| `tests/enrichment/test_pipeline.py` | 10 | Materiales múltiples, OOV, `[]` sin default, `piedra` residual, ámbar sin residual, OOV de piedra, title/familia nulos, hiperónimo, confianza por span, lista mixta (peor miembro) |
| `tests/enrichment/test_llm.py` | 6 | LiteLLM ≠ `OpenAICatalogLlm`, `prompt_version`, semáforo ≤ 8, cero sockets, modo real ≠ stub, 503 sin clave |
| `tests/enrichment/test_audit.py` | 6 | `original`/`short` vacíos válidos, `sparse` exige lista, cobertura por estrato, umbral 90 %, SKU duplicado, HTTP 200 con tags vacías |
| `tests/config/test_settings.py` (ampliado) | +3 | RAG key no bloquea boot, strings en blanco = unset, `canonical_openapi_settings` pinna RAG a `None` |
| `tests/api/test_health.py` (ampliado) | +1 | `GET /health` 200 sin `JPV_RAG_LLM_*` |
| `tests/api/test_stub_mode.py` (ajustado) | 0 nuevos | `/v1/enrich/products` **excluido** del 501; el resto de rutas congeladas siguen en 501 |

**Fake:** `tests/support/fake_enrich_llm.py` (`FakeEnrichLlm`). Ningún test de `tests/enrichment/` abre socket a un proveedor.

---

## 2. Escenarios de las specs, uno a uno

### `catalog-enrichment-pipeline`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Real enrichment replaces the stub · Stub mode keeps the C08 fixture cycle | `test_enrich_stub_exercises_both_provenances` · `test_enrich_stub_is_deterministic` · `test_enrich_reports_prompt_version` (todos contra stub, `STUB_MODE=true`) | ✅ |
| Real enrichment replaces the stub · Real mode produces extracted profiles | `test_real_mode_does_not_use_stub_cycle` (`prompt_version = enrichment/v1`, `usage.model = fake:c09`, `title` nulo) | ✅ |
| Real enrichment replaces the stub · Real mode without a key fails explicitly | `test_real_mode_without_key_fails_explicitly` (503, detalle nombra `JPV_RAG_LLM_API_KEY`, no 501) | ✅ |
| Real enrichment replaces the stub · OpenAPI snapshot stays frozen | `test_openapi_snapshot_is_stable` · `git diff -- ai-service/openapi.json` vacío | ✅ |
| Size is read from name then description · Size on the name is marked rule | `test_size_regex_marks_field_source_as_rule` (`Colgante erizo de mar S` → `S` / `rule` / `1.0`) | ✅ |
| Size is read from name then description · Name wins over a conflicting description | `test_size_prefers_name_over_description` | ✅ |
| Size is read from name then description · Description is used when the name has no size | `test_size_falls_back_to_description_when_name_has_none` | ✅ |
| Size is read from name then description · Size is never read from the SKU | `test_size_is_never_read_from_sku` (`SKU06-S` no aporta talla) | ✅ |
| Closed vocabularies · Several materials become a canonical list | `test_extracts_multiple_materials_from_description` (`plata de ley` + `baño de oro`) | ✅ |
| Closed vocabularies · A material synonym is normalized and an invented value is rejected | `test_material_synonym_normalized_to_canonical_term` · `test_rejects_value_outside_closed_vocabulary` | ✅ |
| Closed vocabularies · No material evidence yields an empty list | `test_empty_materials_flags_review_not_default_value` (`[]`, confianza `0.20`) | ✅ |
| Closed vocabularies · Piece type stores the hypernym | `test_piece_type_stores_hypernym_not_hyponym` (gargantilla → `collar`; `colgante` no colapsa) | ✅ |
| Stone type · A generic gem mention stores residual piedra | `test_generic_stone_when_gem_mentioned_without_type` | ✅ |
| Stone type · A specific stone does not also write the residual | `test_specific_stone_does_not_also_write_generic` (`ambar`, no `piedra`, no en `materials`) | ✅ |
| Stone type · An unlisted stone type becomes residual or null | `test_stone_outside_closed_list_becomes_residual_or_null` (mithril + gema → `piedra`; relieve/brillo → `null`) | ✅ |
| Stone type · Ornament language without a gem leaves stone type null | misma función, rama `absent` de `test_stone_outside_closed_list_becomes_residual_or_null` | ✅ |
| Confidence follows an evidence span · A literal span scores above the C08 tag threshold | `test_confidence_follows_evidence_span` (`plata` → `0.85`; ocasión sin span → `0.45`) | ✅ |
| Confidence follows an evidence span · Empty materials use the absent-evidence confidence | `test_empty_materials_flags_review_not_default_value` (`0.20`, `inferred`) | ✅ |
| Confidence follows an evidence span · A mixed list uses the least-evidenced member confidence | `test_mixed_list_uses_least_evidenced_member_confidence` (`plata`+`oro`, solo `plata` en texto → `0.45`) | ✅ |
| Real profiles leave title, description and family null · Real extractor omits copy and family | `test_title_description_and_family_are_null` · `test_real_mode_does_not_use_stub_cycle` | ✅ |
| Dedicated LiteLLM port · The enrich client is LiteLLM, not the catalog generate client | `test_enrich_llm_uses_litellm_not_openai_catalog_client` | ✅ |
| Dedicated LiteLLM port · Concurrency caps in-flight calls | `test_concurrency_setting_caps_in_flight_calls` (50 productos, `max_in_flight ≤ 8`) | ✅ |
| Dedicated LiteLLM port · The unit suite makes no provider calls | `test_unit_suite_makes_no_provider_calls` · `tests/data/test_scope.py::test_api_main_does_not_import_jbg_ai_data` | ✅ |
| Batch quality gates · HTTP accepts empty tags on a batch of original products | `test_http_batch_with_empty_tags_returns_200_not_422` | ✅ |
| Batch quality gates · The auditor measures tag coverage per text provenance | `test_tag_coverage_gate_is_evaluated_per_text_provenance` · `test_original_or_short_may_have_empty_tags` · `test_sparse_requires_at_least_one_tag_list` | ✅ |
| Batch quality gates · Coverage below threshold fails the auditor, not the POST | `test_batch_fails_when_tag_coverage_below_threshold` | ✅ |
| Batch quality gates · Duplicate SKUs fail the auditor | `test_batch_fails_when_sku_is_duplicated` | ✅ |

### `ai-service-runtime`

| Requisito · escenario | Test | Resultado |
|---|---|---|
| RAG LLM settings do not block process boot · Health starts without a RAG LLM key | `test_settings_do_not_require_rag_llm_key_to_boot` · `test_health_starts_without_rag_llm_key` · `test_settings_load_with_minimal_env` (concurrencia 8) | ✅ |
| RAG LLM settings do not block process boot · Blank RAG LLM strings are treated as unset | `test_blank_rag_llm_strings_are_treated_as_unset` | ✅ |
| RAG LLM settings do not block process boot · Canonical OpenAPI settings pin RAG keys to absent | `test_canonical_openapi_settings_pin_rag_keys_to_absent` · `test_openapi_snapshot_is_stable` | ✅ |

**Totales:** 9 requisitos, 30 escenarios (`#### Scenario:`: 27 en `catalog-enrichment-pipeline` + 3 en `ai-service-runtime`). Todos tienen test nombrado y pasaron en la pasada de alcance.

---

## 3. Nombres exigidos por `tasks.md` / ticket

Lista de la ficha C09 y de [ticket.md](ticket.md). Todos existen como `def test_…` y están en verde.

| Nombre | Fichero |
|---|---|
| `test_extracts_multiple_materials_from_description` | `test_pipeline.py` |
| `test_material_synonym_normalized_to_canonical_term` | `test_vocabularies.py` |
| `test_rejects_value_outside_closed_vocabulary` | `test_vocabularies.py` y `test_pipeline.py` |
| `test_empty_materials_flags_review_not_default_value` | `test_pipeline.py` |
| `test_size_regex_marks_field_source_as_rule` | `test_size.py` |
| `test_size_prefers_name_over_description` | `test_size.py` |
| `test_size_is_never_read_from_sku` | `test_size.py` |
| `test_generic_stone_when_gem_mentioned_without_type` | `test_pipeline.py` |
| `test_specific_stone_does_not_also_write_generic` | `test_pipeline.py` |
| `test_stone_outside_closed_list_becomes_residual_or_null` | `test_pipeline.py` |
| `test_piece_type_stores_hypernym_not_hyponym` | `test_vocabularies.py` y `test_pipeline.py` |
| `test_title_description_and_family_are_null` | `test_pipeline.py` |
| `test_confidence_follows_evidence_span` | `test_pipeline.py` |
| `test_mixed_list_uses_least_evidenced_member_confidence` | `test_pipeline.py` |
| `test_batch_fails_when_sku_is_duplicated` | `test_audit.py` |
| `test_batch_fails_when_tag_coverage_below_threshold` | `test_audit.py` |
| `test_tag_coverage_gate_is_evaluated_per_text_provenance` | `test_audit.py` |
| `test_original_or_short_may_have_empty_tags` | `test_audit.py` |
| `test_sparse_requires_at_least_one_tag_list` | `test_audit.py` |
| `test_unit_suite_makes_no_provider_calls` | `test_llm.py` |
| `test_settings_do_not_require_rag_llm_key_to_boot` | `test_settings.py` |
| `test_enrich_llm_uses_litellm_not_openai_catalog_client` | `test_llm.py` |
| `test_concurrency_setting_caps_in_flight_calls` | `test_llm.py` |
| `test_openapi_snapshot_is_stable` | `test_openapi_snapshot.py` |

Extras que cubren escenarios de spec no nombrados en la ficha: `test_size_falls_back_to_description_when_name_has_none`, `test_vocabularies_load_from_versioned_file`, `test_prompt_version_is_enrichment_v1`, `test_real_mode_does_not_use_stub_cycle`, `test_real_mode_without_key_fails_explicitly`, `test_http_batch_with_empty_tags_returns_200_not_422`, `test_blank_rag_llm_strings_are_treated_as_unset`, `test_canonical_openapi_settings_pin_rag_keys_to_absent`, `test_health_starts_without_rag_llm_key`.

---

## 4. Alcance negativo (tarea 8.2)

```powershell
git diff --name-only -- ai-service/openapi.json ai-service/migrations backend/src frontend
```

Salida **vacía**.

| Guardarraíl | Comprobación | Resultado |
|---|---|---|
| `ai-service/openapi.json` | `git diff` vacío + snapshot estable | ✅ |
| `ai-service/migrations/` | `git diff` vacío | ✅ |
| `backend/src/` | `git diff` vacío (`.env.example` sí se documentó, fuera de `src/`) | ✅ |
| `frontend/` | `git diff` vacío | ✅ |
| Stub C08 | `enrich_products_stub` sigue en `jbg_ai/stubs/responses.py`; tests de contrato verdes con `STUB_MODE=true` | ✅ |
| TODO/FIXME sin seguimiento | `rg TODO\|FIXME` en `jbg_ai/enrichment/` vacío | ✅ |
| `jbg_ai.api.main` no importa `jbg_ai.data` | `test_api_main_does_not_import_jbg_ai_data` | ✅ |

---

## 5. Decisiones de diseño, verificadas en código

| Decisión | Evidencia |
|---|---|
| 1 · LiteLLM, no `OpenAICatalogLlm` | `jbg_ai/enrichment/llm.py` (`from litellm import acompletion`, temp 0); import perezoso |
| 2 · Una llamada por producto; semáforo default 8 | `pipeline.enrich_products` usa `asyncio.Semaphore(concurrency)` |
| 3 · Vocabularios YAML, nunca `ENUM` | `jbg_ai/enrichment/vocabularies.yaml` |
| 4 · Talla Name > Description, nunca SKU | `extract_size(name, description)` — el SKU no es argumento |
| 5 · Confianza por span, no por el número del modelo | `confidence.py`: `0.85` / `0.45` / `0.20`; regex `1.0`; listas = `min` de miembros (`test_mixed_list_uses_least_evidenced_member_confidence`) |
| 6 · Title / description / familia `null` en el extractor real | `assemble_profile` fija `title=None`, `description=None`, `family_id=None`, `variant_label=None` |
| 7 · Puertas de lote en auditor, no en el POST | `audit.audit_batch` no se llama desde el router; SKU duplicado → `duplicate SKUs` |
| 8 · `STUB_MODE=true` conserva stub; `false` exige clave | `routers/enrich.py`: stub si `stub_mode`; 503 si falta `JPV_RAG_LLM_API_KEY` |

Retry de parse: un reintento en `LiteLlmEnrichClient.extract` (`for _attempt in range(2)`); la segunda falla levanta `EnrichParseError`. Instructor no entra.

---

## 6. Documentación de contexto (tarea 8.3)

| Documento | Qué se alineó |
|---|---|
| `Documentos/epicas.md` (EP12) | Enlace a HU-AIENG-009 + bloque **Entregable C09** (extractor, prompt `enrichment/v1`, puertas fuera del HTTP) |
| `ai-service/README.md` | Marcador C09; tabla `JPV_RAG_LLM_*`; nota de 503 vs 501 |
| `ai-service/tests/README.md` | `enrichment/` poblada |
| `backend/.env.example` | `JPV_RAG_LLM_MODEL=openai/gpt-4o`, `BASE_URL`, `CONCURRENCY=8` |
| `prompts/enrichment/v1.md` | Única fuente de `enrichment/v1`. Distinto de `prompts/catalog-synth/v3.md` (generate C06b). El Dockerfile copia `prompts/` a `/app/prompts/` |
| [ticket.md](ticket.md) | Estado del código y DoD marcados tras el apply |

### Prompts: dos familias, una ficha cada una

| Ruta | Change | Qué hace el modelo |
|---|---|---|
| `ai-service/prompts/catalog-synth/v3.md` | C06b | **Inventa** piezas (nombre, descripción, precio). CLI `python -m jbg_ai.data generate`. Temp 0,8. No lo usa el router |
| `ai-service/prompts/enrichment/v1.md` | C09 | **Extrae** atributos de un `name` + `description` ya existentes. `POST /v1/enrich/products`. Temp 0 |

No hay segunda copia de `enrichment/v1` dentro de `jbg_ai/enrichment/`. El runtime resuelve el fichero en el árbol `prompts/` (layout `src/` en el host, `cwd` o `/app` en Docker). Un symlink Git se descartó: en Windows el checkout no materializa enlaces de forma fiable.

---

## 7. OpenSpec

```powershell
openspec validate --all --strict
```

**37 passed, 0 failed.** Incluye el change `add-catalog-enrichment-pipeline` y todas las specs vivas.

---

## 8. Sugerencias del verify, aplicadas

Las tres sugerencias del `/opsx:verify` (ninguna era CRITICAL/WARNING) quedan así:

| # | Sugerencia | Estado |
|---|---|---|
| 1 | Lista mixta: `materials=["plata","oro"]` con solo `plata` en el texto → campo `0.45` | **Hecho.** `test_mixed_list_uses_least_evidenced_member_confidence`; escenario de spec homónimo |
| 2 | Unicidad de SKU con test dedicado | **Hecho.** `test_batch_fails_when_sku_is_duplicated`; escenario de spec homónimo. `audit_batch` ya evaluaba duplicados |
| 3 | Prompt duplicado `prompts/enrichment/v1.md` vs `prompt_v1.md` en el paquete | **Hecho antes.** Una sola ficha en `prompts/enrichment/v1.md`; el paquete no lleva copia |

---

## 9. Fuera de esta pasada (no DoD)

- `enrich-batch` AutoBulk sobre los 1.200 del catálogo Docker (hace falta clave RAG).
- Suite global de .NET: C09 no la toca; no se midió línea base.
- Regenerar `openapi.json`: **prohibido** por el change; el snapshot está verde sin regenerar.
