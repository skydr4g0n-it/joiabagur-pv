> **Línea de corte.** Los grupos 1-6 son la mitad determinista y testeable **sin el xlsx real**: andamiaje, lectura, agrupación interna, reparto, validadores y tests sobre fixtures. Si la sesión se desborda (regla 5 del plan), se entrega esa mitad. Los grupos 7-9 son la pasada de vendedor sobre los 436, el JSONL commiteado, el informe y la ingesta Docker; necesitan el xlsx local y Postgres en 5433. El grupo 10 cierra verificación y docs.

> **Guardarraíl de alcance.** Este change **no toca** `ai-service/openapi.json`, routers, `ai-service/pyproject.toml` (sin cliente LLM), migraciones Alembic ni entidades .NET. Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance, no hay que regenerar el contrato.

> **Guardarraíl de git.** La excepción de `.gitignore` es **solo** `data/catalog/real/generated/`. Antes de cualquier commit del corpus, `git status` no debe listar el xlsx ni el backup SQL.

> **Revisión v2 (2026-08-22).** La pasada de texto es de **vendedor** (`catalog-assist/v2`). El JSONL **no** lleva `variant_group_key` / `variant_label` / `family_seed`. El tercer tier se llama **`original`** (no `empty`): conserva la `Description` del xlsx; no la vacía. Las tareas 4.1, 5.1–5.2, 7, 8 y 10.1/10.4 vuelven a abrirse para re-aplicar.

## 1. Andamiaje de `scripts/catalog/` y visibilidad de `generated/`

- [x] 1.1 Crear `scripts/catalog/pyproject.toml` con dependencias de runtime (`openpyxl`, `psycopg[binary]`) y de test (`pytest`), Python ≥ 3.11, y un README mínimo (comandos de generar, validar e ingerir; variables `JPV_PG*`; semilla por defecto `20260822`; `generator_version` `c06a-assist/v2`). **Validación:** `uv sync --system-certs` en esa carpeta completa y `uv run pytest` arranca (cero tests aún, o `no tests collected`).
- [x] 1.2 Abrir en `.gitignore` la excepción para versionar `data/catalog/real/generated/` **sin** des-ignorar el xlsx ni el backup SQL. Crear `data/catalog/real/generated/.gitkeep`. **Validación:** `git check-ignore -v data/catalog/real/product-JoiaBagur.xlsx` sigue ignorando; `git check-ignore data/catalog/real/generated/catalog-real-enriched.jsonl` no lo ignora.
- [x] 1.3 Añadir fixtures de test bajo `scripts/catalog/tests/fixtures/`: un xlsx (o CSV leído por el mismo parser) con una familia de 3 tallas, varios unarios, un SKU pensado para unmatched, y una fila con descripción de 1001 caracteres. **Validación:** el parser de 2.1 las lee; ningún fixture es el export real.

## 2. Lectura del export e invariantes de identidad

- [x] 2.1 Implementar la lectura de columnas `SKU`, `Name`, `Description`, `Price`, `Collection` alineadas con `ExcelImportService`. Rechazar filas sin SKU y SKUs duplicados. **Validación:** test de fixture `test_reader_rejects_duplicate_sku` y `test_reader_returns_all_fixture_rows`.
- [x] 2.2 Implementar la comparación de identidad JSONL ↔ origen: `sku`, `name`, `price`, `collection_name` inmutables; `description` puede diferir. **Validación:** `test_sku_price_name_and_collection_are_never_modified` en verde sobre fixture.

## 3. Agrupación interna de variantes (no se serializa)

- [x] 3.1 Implementar la heurística del design (normalizar nombre, extraer sufijo de talla; material solo si acompaña a talla) para el **sorteo interno**. **Validación:** las 3 tallas del fixture comparten familia interna; los unarios son grupos de un miembro.
- [x] 3.2 Hacer la agrupación pura y determinista (misma entrada → mismos grupos internos). **Validación:** `test_grouping_is_deterministic` corre dos veces.
- [x] 3.3 Spike sobre el xlsx real: la heurística no es patológica. Los conteos, si se anotan, van al sidecar o al informe, **nunca** a cada línea JSONL.

## 4. Reparto de calidad por familia

- [x] 4.1 Implementar `hash(stem interno, seed) → {rich, sparse, original}` con cortes 0.70 / 0.90, semilla por defecto `20260822`. Todos los miembros heredan el bucket. Mapear `rich`/`sparse` → `text_provenance: ai_assisted` (texto generado) y `original` → `merchant` + `description` **idéntica** a la del xlsx (no vaciar). El identificador `empty` no se usa. **Validación:** `test_variant_family_shares_text_quality`; `test_original_tier_keeps_source_description`.
- [x] 4.2 Medir ratios **por producto** y afirmar tolerancia ±3 pp solo sobre el corpus de 436 (validador de apply, no sobre el fixture pequeño). **Validación:** función de ratios testeada con un JSONL de prueba sintético que cumple 70/20/10 y otro que se sale y debe fallar.

## 5. Contrato JSONL, sidecar y tope de 1000

- [x] 5.1 Serializar JSONL **sin** `variant_group_key`, `variant_label` ni `family_seed`. Campos: `sku`, `name`, `description`, `price`, `collection_name`, `data_origin`, `text_provenance`, `text_quality_tier`; `product_id` ausente salvo lookup opcional. **Validación:** cada línea del fixture parsea; `data_origin` es `real`; SKU único; `test_jsonl_omits_family_seed_fields`.
- [x] 5.2 Validador: `description` ≤ 1000 caracteres; `original` ⇒ `merchant` y texto **igual al export** (vacío solo si el xlsx lo estaba); `rich`/`sparse` ⇒ `ai_assisted` y texto generado no vacío; ningún grupo interno mezcla tiers; `rich`/`sparse` no mencionan foto/ficha/laguna; no se inventan piedras/accesorios ausentes del original. **Validación:** `test_description_over_1000_is_rejected`; `test_original_tier_keeps_source_description`; `test_every_product_has_data_origin_and_text_provenance`; `test_assisted_copy_does_not_mention_photos_or_source_sheet`.
- [x] 5.3 Escribir `.meta.json` con `generator_version` (`c06a-assist/v2`), `seed`, `generated_at`, ratios por tier y por `text_provenance`. `model` omitido o `null`. Conteos de agrupación, si existen, son traza de pipeline, no campos de línea. **Validación:** test que lee el sidecar del fixture y comprueba las claves.

## 6. Ingesta SQL sobre fixture (sin Docker real obligatorio en la unidad)

- [x] 6.1 Implementar el `UPDATE` por SKU (`Description`, `UpdatedAt`) leyendo `JPV_PG*` del entorno. Transacción única; rollback si el post-check de `Id`/`SKU`/`Name`/`Price`/`CollectionId` falla; unmatched **sin INSERT**. **Validación:** tests con base de prueba (testcontainers Postgres **o** fake de conexión si no hay Docker).
- [x] 6.2 Cubrir unmatched y aborto por invariante. **Validación:** `test_ingest_lists_unmatched_without_insert`; `test_ingest_rolls_back_when_identity_would_change`.

## 7. Pasada de vendedor y corpus de 436

- [x] 7.1 Redactar las descripciones `rich` y `sparse` del export real con `catalog-assist/v2` (voz de vendedor como si se viera la pieza; conservar Name/Description; no inventar piedras/accesorios; no mencionar fotos ni fichas; `rich` más inventiva, `sparse` 1–2 frases). En `original`, copiar la `Description` del xlsx **sin modificarla**. **Validación:** validador de 5.2 en verde sobre el JSONL real; ninguna línea > 1000; ningún `original` distinto del xlsx.
- [x] 7.2 Reescribir `data/catalog/real/generated/catalog-real-enriched.jsonl` y el sidecar (`generator_version` `c06a-assist/v2`). **Validación:** 436 líneas; SKUs = xlsx; ratios ±3 pp; cero campos de familia; `git status` no muestra el xlsx.
- [x] 7.3 Re-ejecutar el sorteo de tiers con la misma semilla y comprobar que el mapa SKU → tier coincide con el JSONL. **Validación:** `test_generator_is_deterministic_for_same_seed` (sobre fixture) sigue verde; el check del real se anota en el informe.

## 8. Informe de enriquecimiento

- [x] 8.1 Actualizar `Documentos/Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md` con ratios, unmatched (o «pendiente de ingesta»), muestras **antes/después** (mínimo 5 `rich`, 3 `sparse`, 2 `original`) que sean descripciones de producto — en `original`, antes y después coinciden con el xlsx —, y el párrafo de limitación **solo en el informe**. **Validación:** las muestras salen del JSONL v2; ningún `original` aparece vaciado si el xlsx tenía texto.

## 9. Ingesta local contra Docker

- [x] 9.1 Snapshot CSV o `pg_dump` parcial de `public."Products"` (`SKU, Name, Description, Price, CollectionId`). **Validación:** el fichero de snapshot existe en local y **no** se commitea.
- [x] 9.2 Ejecutar la ingesta contra `localhost:5433` / `joiabagur_pv` **después** de regenerar el JSONL v2. **Validación:** coincidentes tienen la `Description` del JSONL; `Name`/`Price`/`CollectionId`/`SKU` iguales al snapshot; unmatched documentados en el informe.
- [x] 9.3 (Opcional) Reescribir `product_id` en el JSONL vía lookup de SKU. **Validación:** si no se hace, el JSONL sigue válido sin el campo.

## 10. Verificación de alcance y documentación

- [x] 10.1 `uv run pytest` en `scripts/catalog/` en verde tras el recorte de campos y la voz v2. **Validación:** salida sin fallos.
- [x] 10.2 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/pyproject.toml`, `ai-service/migrations/`, `backend/src/`, `frontend/`.
- [x] 10.3 Alinear docs de contexto si el entregable cambia (EP12 / HU-AIENG-006a / nota de zona en el plan): el lector llega al JSONL **sin** campos de familia y al informe v2.
- [x] 10.4 Ejecutar **`openspec validate --all --strict`**. **Validación:** la salida reporta `0 failed`.
