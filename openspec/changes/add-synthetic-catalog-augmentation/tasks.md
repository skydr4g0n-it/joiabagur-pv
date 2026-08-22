> **Línea de corte.** Los grupos 1–6 son la mitad determinista y testeable **sin llamada real a OpenAI**: andamiaje, reservador de SKU, stem/tiers, contrato JSONL, cliente fake y tests de ingesta sobre fixture. Si la sesión se desborda (regla 5 del plan), se entrega esa mitad. Los grupos 7–9 son la pasada real, el JSONL commiteado, el informe y la ingesta Docker; necesitan clave OpenAI y Postgres en 5433. El grupo 10 cierra verificación y docs.

> **Guardarraíl de alcance.** Este change **no toca** `ai-service/openapi.json`, routers, `ai-service/migrations/`, entidades .NET ni `scripts/catalog/assist.py`. Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance, no hay que regenerar el contrato.

> **Guardarraíl de git.** La excepción de `.gitignore` es **solo** `data/catalog/synthetic/generated/`. Antes de cualquier commit del corpus, `git status` no debe listar secretos ni basura bajo `data/catalog/synthetic/`.

> **Guardarraíl de boot.** `LLM_*` / `OPENAI_*` son **opcionales** en `Settings`. `jbg_ai.api.main` no importa `jbg_ai.data`. Un test de health sin API key debe seguir verde.

## 1. Andamiaje de `jbg_ai.data` y visibilidad de `generated/`

- [ ] 1.1 Crear el paquete `ai-service/src/jbg_ai/data/` (`__init__.py` vacío o de reexport mínimo, `__main__.py` con CLI `generate|ingest` aún stub). Añadir el cliente OpenAI a `ai-service/pyproject.toml` **sin** tocar OpenAPI. README breve del CLI (comandos, `JPV_PG*`, `LLM_*`, semilla `20260822`, `generator_version` `c06b-synth/v1`, `prompt_version` `catalog-synth/v1`). **Validación:** `uv sync --system-certs` en `ai-service/` completa; `python -m jbg_ai.data --help` arranca; `git diff ai-service/openapi.json` vacío.
- [ ] 1.2 Añadir settings `LLM_*` / `OPENAI_API_KEY` / `LLM_MODEL` **opcionales** en `settings.py` (y en `canonical_openapi_settings` solo si no filtran al snapshot). El CLI las exigirá en 5.x; `/health` no. **Validación:** `test_settings_do_not_require_llm_key_to_boot` y el test existente de settings mínimas en verde; `GET /health` 200 sin esas vars.
- [ ] 1.3 Abrir en `.gitignore` la excepción para versionar `data/catalog/synthetic/generated/` **sin** des-ignorar el resto de `data/catalog/synthetic/`. Crear `data/catalog/synthetic/generated/.gitkeep`. **Validación:** `git check-ignore data/catalog/synthetic/generated/catalog-synthetic.jsonl` no lo ignora; un fichero basura fuera de `generated/` sigue ignorado si aplica.
- [ ] 1.4 Crear `ai-service/tests/data/` espejando el paquete y un fake de cliente LLM (sin sockets). **Validación:** `uv run --system-certs pytest tests/data -q` arranca (cero tests o `no tests collected` aún no es fallo si el árbol existe); `test_unit_suite_makes_no_provider_calls` se añade en 5.3.

## 2. Reservador de SKU

- [ ] 2.1 Implementar el esquema del real: literal `SKU` + 2/3/4 dígitos según magnitud; secuencia desde **437**; unique vs JSONL C06a (y vs un set inyectable de `"Products"."SKU"`). Sin prefijos `SYN-` / `JB-S-`. El LLM no asigna SKUs. **Validación:** `test_sku_follows_real_magnitude_scheme`; `test_skus_are_unique_across_real_and_synthetic` sobre el JSONL C06a real (436 líneas en git).
- [ ] 2.2 Hacer el reservador puro y determinista a igual semilla y mismo set de ocupados. **Validación:** `test_sku_allocator_is_deterministic_for_same_seed` corre dos veces y coincide.

## 3. Stem de `Name` y reparto de calidad

- [ ] 3.1 Implementar el stem mínimo (normalizar nombre, extraer sufijo de talla S/M/L u homologable) **en** `jbg_ai.data`, sin importar `scripts/catalog/`. **Validación:** fixture de «Colgante erizo S/M» comparte stem; unarios son grupos de un miembro; `test_name_stem_siblings_share_text_quality_tier`.
- [ ] 3.2 Implementar `hash(stem, seed) → {rich, sparse, short}` con cortes 0.70 / 0.90, semilla por defecto `20260822`. Todos los miembros heredan el bucket. `text_provenance` **siempre** `synthetic`. No usar `empty` ni `original`. Rebalanceo determinista de stems enteros si los ratios por producto salen de ±5 pp. **Validación:** `test_name_stem_siblings_share_text_quality_tier`; test de ratios sobre un JSONL de prueba que cumple y otro que se sale y debe rebalancear o fallar la aserción.

## 4. Contrato JSONL, validación y sidecar

- [ ] 4.1 Serializar líneas con `sku`, `name`, `description`, `price`, `collection_name`, `data_origin`, `text_provenance`, `text_quality_tier`. **Prohibidos:** `variant_group_key`, `variant_label`, `family_seed`, `materials`, `product_id`. **Validación:** `test_jsonl_omits_family_seed_fields` (cubre también `materials` y `product_id`); `data_origin` y `text_provenance` son `synthetic`.
- [ ] 4.2 Validador: `description` ≤ 1000; `0 < price < 50000` y cabe en `decimal(18,2)`; `name` ≤ 200; SKU único y con esquema; `collection_name` no es canal/POS ni colisiona con las 28 reales; ningún stem mezcla tier. **Validación:** `test_description_over_1000_is_rejected`; `test_price_at_or_above_50000_is_rejected`.
- [ ] 4.3 Escribir `.meta.json` con `generator_version` (`c06b-synth/v1`), `seed`, `model`, `prompt_version` (`catalog-synth/v1`), `generated_at`, `product_count`, ratios por tier, holgura vs ~1.200 totales. Opcional: mapa colección → público/POS pensado. **Validación:** test que lee el sidecar de fixture y comprueba las claves.

## 5. Prompt, cliente OpenAI y orquestación generate (fake)

- [ ] 5.1 Añadir `ai-service/prompts/catalog-synth/v1` (markdown + JSON schema). El prompt distingue nombre de diseño vs brief de público/POS; pide ~35 % multi-material **en la prosa**; prohíbe el molde `assist.py` y los nombres de colección reales/canal. **Validación:** el fichero existe y el orquestador lo versiona en el sidecar como `prompt_version`.
- [ ] 5.2 Implementar el cliente OpenAI detrás de un puerto inyectable. Generate: reserva SKUs → 8–12 briefs → llama al puerto → sella procedencia/tier → valida → escribe JSONL + sidecar. Sin `--regenerate-text`, no pisa un JSONL commiteado. **Validación:** tests con fake que devolvuelve piezas válidas; `test` de no-overwrite sin flag; el fake cubre un caso de descripción > 1000 y otro de precio ≥ 50000 que el validador rechaza.
- [ ] 5.3 Afirmar que la suite de `tests/data/` no abre sockets a proveedores y que `jbg_ai.api.main` no importa `jbg_ai.data`. **Validación:** `test_unit_suite_makes_no_provider_calls`; `test_api_main_does_not_import_jbg_ai_data`.

## 6. Ingesta INSERT sobre fixture (sin Docker real obligatorio en la unidad)

- [ ] 6.1 Implementar `INSERT` de `"Collections"` (nombres de diseño, unique) y `"Products"` (`SKU`, `Name`, `Description`, `Price`, `CollectionId`, `IsActive=true`, `Id` DEFAULT) leyendo `JPV_PG*` del entorno. Transacción única. **Nunca** `UPDATE` de SKUs del JSONL C06a. **Nunca** `"ProductFamily*"`. **Nunca** reescribir el JSONL con `product_id`. **Validación:** `test_ingest_inserts_new_products_without_touching_real_skus`; `test_ingest_creates_new_collections_with_unique_names` (testcontainers **o** fake de conexión).
- [ ] 6.2 Cubrir rollback por colisión de SKU o de `Collection.Name`. **Validación:** `test_ingest_rolls_back_on_sku_or_collection_collision`; tras el fallo, recuentos iguales al snapshot del fixture.

## 7. Pasada real y corpus commiteable

- [ ] 7.1 Ejecutar `generate` contra OpenAI (clave solo en esta pasada) con semilla `20260822` y presupuesto ~1.200 − 436. 8–12 colecciones de diseño; un par pueden ser menorquinas; el resto divergen. **Validación:** validador de 4.2 en verde; ningún SKU del real; ningún campo prohibido; tiers ±5 pp; `name`/`description` no huelen a `assist.py` en un muestreo del informe.
- [ ] 7.2 Escribir `data/catalog/synthetic/generated/catalog-synthetic.jsonl` y el sidecar. **Validación:** holgura documentada vs ~1.200 totales; sidecar con `model` OpenAI y `prompt_version`; `git check-ignore` no oculta el JSONL.
- [ ] 7.3 Re-ejecutar el reservador y el sorteo de tiers con la misma semilla y comprobar que el mapa SKU → SKU/tier coincide. **Validación:** tests de 2.2 y 3.2 siguen verdes; el check del corpus real se anota en el informe.

## 8. Informe de ampliación

- [ ] 8.1 Redactar `Documentos/Proyecto Final AIEng/informes/c06b-synthetic-catalog-report.md` con recuentos, ratios, nombres de colección **separados** del público/POS pensado, muestras por tier (`rich` / `sparse` / `short`), y la nota de honestidad §15 (LLM, no clon estadístico; C24 desglosa por `data_origin`). **Validación:** las muestras salen del JSONL commiteado; ningún nombre de colección es canal/POS.

## 9. Ingesta local contra Docker

- [ ] 9.1 Snapshot CSV o `pg_dump` parcial de `public."Products"` y `"Collections"` (`SKU, Name, Description, Price, CollectionId` y nombres de colección). **Validación:** el fichero existe en local y **no** se commitea.
- [ ] 9.2 Ejecutar `ingest` contra `localhost:5433` / `joiabagur_pv`. **Validación:** colecciones nuevas + productos `IsActive`; los 436 reales intactos (SKU/precio/nombre/recuento); cero filas nuevas en `"ProductFamily*"`; el JSONL no ganó `product_id`.
- [ ] 9.3 (Manual / .NET) Un `GET` de familia sobre un SKU sintético ingerido responde 204, no 404. **Validación:** anotado en el informe o en la salida del apply; no se implementa C18.

## 10. Verificación de alcance y documentación

- [ ] 10.1 `uv run --system-certs pytest tests/data tests/config tests/api/test_health.py tests/api/test_openapi_snapshot.py` en verde (más el resto de `ai-service` si se tocó settings). **Validación:** salida sin fallos **nuevos**; comparar nombres si la suite global ya tenía rojos ajenos.
- [ ] 10.2 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/migrations/`, `backend/src/`, `frontend/`, `scripts/catalog/assist.py`. `jbg_ai.api.main` sigue sin importar `jbg_ai.data`.
- [ ] 10.3 Alinear docs de contexto: `Documentos/epicas.md` (EP12 / HU-AIENG-006b), coherencia de la HU y el ticket con el entregable, nota breve en el plan si hace falta registrar `generator_version` / zona CLI. **Validación:** un lector de la épica llega al JSONL sintético, al informe y a la frontera §6.3.
- [ ] 10.4 Ejecutar **`openspec validate --all --strict`**. **Validación:** la salida reporta `0 failed`.
