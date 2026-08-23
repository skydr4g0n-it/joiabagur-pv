## Why

C08 dejó listo el perfil, el enrutado híbrido y `POST /api/ai/catalog/enrich-batch`, pero `POST /v1/enrich/products` sigue siendo el stub de C02: marca talla `rule` por índice del lote y dice que la lee del SKU, cuando en este catálogo la talla está en el nombre. C11 no puede construir un `SourceText` honesto sobre ese ciclo. Se hace ahora porque C06a y C08 están archivados, el contrato ya exige `source` y `prompt_version`, y C09 es prerrequisito 🔴 de C11.

## What Changes

- **Extractor real** detrás de `POST /v1/enrich/products` cuando `STUB_MODE=false`: vocabularios cerrados, talla por regex (`Name` > `Description`, nunca SKU), LiteLLM a temperatura 0, confianza por span en el texto de entrada, `prompt_version` real (`enrichment/v1`).
- **Paquete `jbg_ai.enrichment/`** importado por el router. Puerto propio `EnrichLlm` sobre LiteLLM. **No** se importa `jbg_ai.data` ni se reutiliza `OpenAICatalogLlm` (otra clave, otra temperatura, otro schema).
- **Una llamada de modelo por producto** y semáforo `JPV_RAG_LLM_CONCURRENCY` (default 8) dentro del lote de 50. Retry solo si el JSON no parsea. Sin Instructor.
- **Settings `JPV_RAG_LLM_*`** (`API_KEY`, `MODEL` con prefijo de proveedor, `BASE_URL` opcional, `CONCURRENCY`) opcionales al boot; exigidas al enriquecer de verdad. Sin clave → error explícito, no perfiles inventados.
- **Auditor de puertas de lote fuera del HTTP**: unicidad de SKU, vocabulario, cobertura de tags por estrato (`original`/`short` no castigan; `sparse` exige ≥ 1 lista; 90 % sobre `ai_assisted`; 70 % global sin contar `original`/`short` como fallo). El POST de 50 nunca responde 422 por esas cifras.
- **`title` / `description` / `family_id` / `variant_label` nulos** en el extractor real. El stub de C08 sigue rellenándolos bajo `STUB_MODE=true` para no romper los tests de contrato.
- **Dependencia `litellm` con versión fijada** en `pyproject.toml`. C06b no se migra.

**Fuera de alcance:** ejecutar `enrich-batch` AutoBulk sobre los 1.200 (verificación posterior); persistir perfiles (C08); escribir `Product`; renegociar el contrato ni regenerar `openapi.json`; `piece_subtype` / diccionario de consulta (C20); Instructor (C30+); UI, cola, RDS, migración EF/Alembic; C11, C12, C13, C18, C28.

Sin breaking changes de contrato. Cambio de comportamiento: con `STUB_MODE=false` la ruta deja de ser 501/stub y llama al modelo.

## Capabilities

### New Capabilities

- `catalog-enrichment-pipeline`: extractor de `POST /v1/enrich/products` — vocabularios cerrados versionados en el repo, talla por regex con `source: rule`, extracción estructurada vía LiteLLM a temperatura 0, normalización de sinónimos, confianza por evidencia en el texto, perfil propuesto sin title/description/familia, y auditor de puertas de lote fuera del request HTTP.

### Modified Capabilities

- `ai-service-runtime`: las settings `JPV_RAG_LLM_*` (incluida `CONCURRENCY` con default 8) son opcionales al arrancar; `GET /health` no exige clave de proveedor. El enriquecimiento real sí la exige y, si falta, falla de forma explícita.

`ai-service-api-contracts` **no lleva delta**: la forma del JSON no cambia (C08 ya exigió `source`, campos sensibles, tags desglosadas y `prompt_version`). El requisito de 501 sigue valiendo para las rutas que aún no tienen implementación. `product-ai-profile` no cambia: C08 ya consume `source` y confianza. `real-catalog-corpus` y `synthetic-catalog-corpus` no cambian: C09 lee `name` + `description` y no toca el JSONL.

## Impact

**`jbg-ai`** — paquete `enrichment/` nuevo (YAML de vocabularios, regex, puerto LiteLLM, pipeline, auditor); prompt `prompts/enrichment/v1.md`; el router `/v1/enrich/products` sustituye `require_stub_mode` por el pipeline cuando `stub_mode` es falso; settings `JPV_RAG_LLM_*`; `litellm` fijada en `pyproject.toml`; tests en `tests/enrichment/` con LLM falso.

**`ai-service/openapi.json`** — **no se regenera**. Si `test_openapi_snapshot_is_stable` se pone rojo, el change se ha salido de alcance.

**Backend .NET / frontend / terraform / migraciones** — sin cambios. C08 ya envía `product_id`, `sku`, `name`, `description` y aplica el enrutado. C09 no abre conexión a `public`.

**Documentación** — `Documentos/epicas.md` (EP12) enlaza HU-AIENG-009; el README de `ai-service` actualiza el marcador C09.

**Dependientes desbloqueados:** C11 (y, en cascada, C13). El valor de producto no es visible hasta que un administrador ejecute `enrich-batch` (fuera de este ticket).
