> **Línea de corte.** Los grupos 1–6 son la mitad determinista y testeable **sin llamada real a OpenAI**: andamiaje, reservador de SKU, stem/tiers, contrato JSONL, cliente fake y tests de ingesta sobre fixture. Si la sesión se desborda (regla 5 del plan), se entrega esa mitad. Los grupos 7–9 son la pasada real, el JSONL commiteado, el informe y la ingesta Docker; necesitan clave OpenAI y Postgres en 5433. El grupo 10 cierra verificación y docs.

> **Guardarraíl de alcance.** Este change **no toca** `ai-service/openapi.json`, routers, `ai-service/migrations/`, entidades .NET ni `scripts/catalog/assist.py`. Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance, no hay que regenerar el contrato.

> **Guardarraíl de git.** La excepción de `.gitignore` es **solo** `data/catalog/synthetic/generated/`. Antes de cualquier commit del corpus, `git status` no debe listar secretos ni basura bajo `data/catalog/synthetic/`.

> **Guardarraíl de boot.** `LLM_*` / `OPENAI_*` son **opcionales** en `Settings`. `jbg_ai.api.main` no importa `jbg_ai.data`. Un test de health sin API key debe seguir verde.

## 1. Andamiaje de `jbg_ai.data` y visibilidad de `generated/`

- [x] 1.1 Crear el paquete `ai-service/src/jbg_ai/data/` (`__init__.py` vacío o de reexport mínimo, `__main__.py` con CLI `generate|ingest` aún stub). Añadir el cliente OpenAI a `ai-service/pyproject.toml` **sin** tocar OpenAPI. README breve del CLI (comandos, `JPV_PG*`, `LLM_*`, semilla `20260822`, `generator_version` `c06b-synth/v1`, `prompt_version` `catalog-synth/v1`). **Validación:** `uv sync --system-certs` en `ai-service/` completa; `python -m jbg_ai.data --help` arranca; `git diff ai-service/openapi.json` vacío.
- [x] 1.2 Añadir settings `LLM_*` / `OPENAI_API_KEY` / `LLM_MODEL` **opcionales** en `settings.py` (y en `canonical_openapi_settings` solo si no filtran al snapshot). El CLI las exigirá en 5.x; `/health` no. **Validación:** `test_settings_do_not_require_llm_key_to_boot` y el test existente de settings mínimas en verde; `GET /health` 200 sin esas vars.
- [x] 1.3 Abrir en `.gitignore` la excepción para versionar `data/catalog/synthetic/generated/` **sin** des-ignorar el resto de `data/catalog/synthetic/`. Crear `data/catalog/synthetic/generated/.gitkeep`. **Validación:** `git check-ignore data/catalog/synthetic/generated/catalog-synthetic.jsonl` no lo ignora; un fichero basura fuera de `generated/` sigue ignorado si aplica.
- [x] 1.4 Crear `ai-service/tests/data/` espejando el paquete y un fake de cliente LLM (sin sockets). **Validación:** `uv run --system-certs pytest tests/data -q` arranca (cero tests o `no tests collected` aún no es fallo si el árbol existe); `test_unit_suite_makes_no_provider_calls` se añade en 5.3.

## 2. Reservador de SKU

- [x] 2.1 Implementar el esquema del real: literal `SKU` + 2/3/4 dígitos según magnitud; secuencia desde **437**; unique vs JSONL C06a (y vs un set inyectable de `"Products"."SKU"`). Sin prefijos `SYN-` / `JB-S-`. El LLM no asigna SKUs. **Validación:** `test_sku_follows_real_magnitude_scheme`; `test_skus_are_unique_across_real_and_synthetic` sobre el JSONL C06a real (436 líneas en git).
- [x] 2.2 Hacer el reservador puro y determinista a igual semilla y mismo set de ocupados. **Validación:** `test_sku_allocator_is_deterministic_for_same_seed` corre dos veces y coincide.

## 3. Stem de `Name` y reparto de calidad

- [x] 3.1 Implementar el stem mínimo (normalizar nombre, extraer sufijo de talla S/M/L u homologable) **en** `jbg_ai.data`, sin importar `scripts/catalog/`. **Validación:** fixture de «Colgante erizo S/M» comparte stem; unarios son grupos de un miembro; `test_name_stem_siblings_share_text_quality_tier`.
- [x] 3.2 Implementar `hash(stem, seed) → {rich, sparse, short}` con cortes 0.70 / 0.90, semilla por defecto `20260822`. Todos los miembros heredan el bucket. `text_provenance` **siempre** `synthetic`. No usar `empty` ni `original`. Rebalanceo determinista de stems enteros si los ratios por producto salen de ±5 pp. **Validación:** `test_name_stem_siblings_share_text_quality_tier`; test de ratios sobre un JSONL de prueba que cumple y otro que se sale y debe rebalancear o fallar la aserción.

## 4. Contrato JSONL, validación y sidecar

- [x] 4.1 Serializar líneas con `sku`, `name`, `description`, `price`, `collection_name`, `data_origin`, `text_provenance`, `text_quality_tier`. **Prohibidos:** `variant_group_key`, `variant_label`, `family_seed`, `materials`, `product_id`. **Validación:** `test_jsonl_omits_family_seed_fields` (cubre también `materials` y `product_id`); `data_origin` y `text_provenance` son `synthetic`.
- [x] 4.2 Validador: `description` ≤ 1000; `0 < price < 50000` y cabe en `decimal(18,2)`; `name` ≤ 200; SKU único y con esquema; `collection_name` no es canal/POS ni colisiona con las 28 reales; ningún stem mezcla tier. **Validación:** `test_description_over_1000_is_rejected`; `test_price_at_or_above_50000_is_rejected`.
- [x] 4.3 Escribir `.meta.json` con `generator_version` (`c06b-synth/v1`), `seed`, `model`, `prompt_version` (`catalog-synth/v1`), `generated_at`, `product_count`, ratios por tier, holgura vs ~1.200 totales. Opcional: mapa colección → público/POS pensado. **Validación:** test que lee el sidecar de fixture y comprueba las claves.

## 5. Prompt, cliente OpenAI y orquestación generate (fake)

- [x] 5.1 Añadir `ai-service/prompts/catalog-synth/v1` (markdown + JSON schema). El prompt distingue nombre de diseño vs brief de público/POS; pide ~35 % multi-material **en la prosa**; prohíbe el molde `assist.py` y los nombres de colección reales/canal. **Validación:** el fichero existe y el orquestador lo versiona en el sidecar como `prompt_version`.
- [x] 5.2 Implementar el cliente OpenAI detrás de un puerto inyectable. Generate: reserva SKUs → 8–12 briefs → llama al puerto → sella procedencia/tier → valida → escribe JSONL + sidecar. Sin `--regenerate-text`, no pisa un JSONL commiteado. **Validación:** tests con fake que devolvuelve piezas válidas; `test` de no-overwrite sin flag; el fake cubre un caso de descripción > 1000 y otro de precio ≥ 50000 que el validador rechaza.
- [x] 5.3 Afirmar que la suite de `tests/data/` no abre sockets a proveedores y que `jbg_ai.api.main` no importa `jbg_ai.data`. **Validación:** `test_unit_suite_makes_no_provider_calls`; `test_api_main_does_not_import_jbg_ai_data`.

## 6. Ingesta INSERT sobre fixture (sin Docker real obligatorio en la unidad)

- [x] 6.1 Implementar `INSERT` de `"Collections"` (nombres de diseño, unique) y `"Products"` (`SKU`, `Name`, `Description`, `Price`, `CollectionId`, `IsActive=true`, `Id` DEFAULT) leyendo `JPV_PG*` del entorno. Transacción única. **Nunca** `UPDATE` de SKUs del JSONL C06a. **Nunca** `"ProductFamily*"`. **Nunca** reescribir el JSONL con `product_id`. **Validación:** `test_ingest_inserts_new_products_without_touching_real_skus`; `test_ingest_creates_new_collections_with_unique_names` (testcontainers **o** fake de conexión).
- [x] 6.2 Cubrir rollback por colisión de SKU o de `Collection.Name`. **Validación:** `test_ingest_rolls_back_on_sku_or_collection_collision`; tras el fallo, recuentos iguales al snapshot del fixture.

## 7. Pasada real y corpus commiteable

- [x] 7.1 Ejecutar `generate` contra OpenAI (clave solo en esta pasada) con semilla `20260822` y presupuesto ~1.200 − 436. 8–12 colecciones de diseño; un par pueden ser menorquinas; el resto divergen. **Validación:** validador de 4.2 en verde; ningún SKU del real; ningún campo prohibido; tiers ±5 pp; `name`/`description` no huelen a `assist.py` en un muestreo del informe.
- [x] 7.2 Escribir `data/catalog/synthetic/generated/catalog-synthetic.jsonl` y el sidecar. **Validación:** holgura documentada vs ~1.200 totales; sidecar con `model` OpenAI y `prompt_version`; `git check-ignore` no oculta el JSONL.
- [x] 7.3 Re-ejecutar el reservador y el sorteo de tiers con la misma semilla y comprobar que el mapa SKU → SKU/tier coincide. **Validación:** tests de 2.2 y 3.2 siguen verdes; el check del corpus real se anota en el informe.

## 8. Informe de ampliación

- [x] 8.1 Redactar `Documentos/Proyecto Final AIEng/informes/c06b-synthetic-catalog-report.md` con recuentos, ratios, nombres de colección **separados** del público/POS pensado, muestras por tier (`rich` / `sparse` / `short`), y la nota de honestidad §15 (LLM, no clon estadístico; C24 desglosa por `data_origin`). **Validación:** las muestras salen del JSONL commiteado; ningún nombre de colección es canal/POS.

## 9. Ingesta local contra Docker

- [x] 9.1 Snapshot CSV o `pg_dump` parcial de `public."Products"` y `"Collections"` (`SKU, Name, Description, Price, CollectionId` y nombres de colección). **Validación:** el fichero existe en local y **no** se commitea.
- [x] 9.2 Ejecutar `ingest` contra `localhost:5433` / `joiabagur_pv`. **Validación:** colecciones nuevas + productos `IsActive`; los 436 reales intactos (SKU/precio/nombre/recuento); cero filas nuevas en `"ProductFamily*"`; el JSONL no ganó `product_id`.
- [x] 9.3 (Manual / .NET) Un `GET` de familia sobre un SKU sintético ingerido responde 204, no 404. **Validación:** anotado en el informe o en la salida del apply; no se implementa C18.

## 10. Verificación de alcance y documentación

- [x] 10.1 `uv run --system-certs pytest tests/data tests/config tests/api/test_health.py tests/api/test_openapi_snapshot.py` en verde (más el resto de `ai-service` si se tocó settings). **Validación:** salida sin fallos **nuevos**; comparar nombres si la suite global ya tenía rojos ajenos.
- [x] 10.2 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/migrations/`, `backend/src/`, `frontend/`, `scripts/catalog/assist.py`. `jbg_ai.api.main` sigue sin importar `jbg_ai.data`.
- [x] 10.3 Alinear docs de contexto: `Documentos/epicas.md` (EP12 / HU-AIENG-006b), coherencia de la HU y el ticket con el entregable, nota breve en el plan si hace falta registrar `generator_version` / zona CLI. **Validación:** un lector de la épica llega al JSONL sintético, al informe 8.1 y a la frontera §6.3.
- [x] 10.4 Ejecutar **`openspec validate --all --strict`**. **Validación:** la salida reporta `0 failed`.

## 11. Recalibración v2 (desigualdad, sin colección, familias léxicas)

- [x] 11.1 Versionar prompt a `catalog-synth/v2` (v1 se conserva). El Jaleo = jaleo de cavalls de Menorca. Pieza base sin talla. `generator_version` `c06b-synth/v2`. **Validación:** `test_prompt_file_exists_and_is_versioned`.
- [x] 11.2 Planner: cupos de colección **desiguales**; ~20 % ±5 pp sin colección (`CollectionId` NULL). **Validación:** `test_distribute_uneven_is_unequal_for_full_budget`; `test_ingest_leaves_unassigned_products_without_collection`.
- [x] 11.3 Familias léxicas por código (no por LLM): ~40 % de sintéticos en familia; de esos, ~60 % en S/M/L/XL completa y ~40 % incompleta. Misma descripción y colección; solo talla y precio. **Validación:** `test_family_shapes_hit_60_40_on_full_budget`; `test_family_copy_consistency_and_completeness_ratios`.
- [x] 11.4 Regenerar JSONL con `--regenerate-text` (pasada real, no en esta sesión). **Validación:** validador 4.2 + mix 11.2/11.3 en verde; sidecar `prompt_version` `catalog-synth/v2`.

## 12. El `text_quality_tier` coincide con la longitud del copy

- [x] 12.1 Prompt `catalog-synth/v3`: el lote declara el tier y el modelo lo obedece. El código recorta `short`/`sparse`. 70/20/10 ±5 pp. **Validación:** `test_fit_description_matches_declared_tier`; generate fake 80 en verde.
- [x] 12.2 Realinear el JSONL commiteado (sin nueva llamada OpenAI): los textos más largos quedan `rich`; el resto se recorta a sparse/short. **Validación:** 0 mismatches; ratios ~70/20/10.
- [x] 12.3 Recalibrar bandas a las medias del catálogo real (`rich` ≥150 / `sparse` objetivo ≤115 con techo de frase entera 140 / `short` ≤32) y vaciar ~20 % de los `short`. El recorte solo deja frases enteras; si no caben, vacío o redraft. **Validación:** `test_fit_description_matches_declared_tier`; `test_fit_does_not_leave_half_a_sentence`; `test_about_one_fifth_of_short_descriptions_are_emptied`.
- [x] 12.4 Regenerar el JSONL con `--regenerate-text` (`catalog-synth/v3`, frases enteras, ~20 % de `short` vacíos). **Validación:** 764 líneas; sidecar `c06b-synth/v3` + `catalog-synth/v3`; 0 mismatches; 0 descripciones a medias.
