> **Línea de corte.** Los grupos 1-6 son la mitad determinista y testeable **sin el xlsx real**: andamiaje, lectura, agrupación, reparto, validadores y tests sobre fixtures. Si la sesión se desborda (regla 5 del plan), se entrega esa mitad. Los grupos 7-9 son la pasada asistida sobre los 436, el JSONL commiteado, el informe y la ingesta Docker; necesitan el xlsx local y Postgres en 5433. El grupo 10 cierra verificación y docs.

> **Guardarraíl de alcance.** Este change **no toca** `ai-service/openapi.json`, routers, `ai-service/pyproject.toml` (sin cliente LLM), migraciones Alembic ni entidades .NET. Si `test_openapi_snapshot_is_stable` se pone rojo, el trabajo se ha salido del alcance, no hay que regenerar el contrato.

> **Guardarraíl de git.** La excepción de `.gitignore` es **solo** `data/catalog/real/generated/`. Antes de cualquier commit del corpus, `git status` no debe listar el xlsx ni el backup SQL.

## 1. Andamiaje de `scripts/catalog/` y visibilidad de `generated/`

- [ ] 1.1 Crear `scripts/catalog/pyproject.toml` con dependencias de runtime (`openpyxl`, `psycopg[binary]`) y de test (`pytest`), Python ≥ 3.11, y un README mínimo (comandos de generar, validar e ingerir; variables `JPV_PG*`; semilla por defecto `20260822`; `generator_version` `c06a-assist/v1`). **Validación:** `uv sync --system-certs` en esa carpeta completa y `uv run pytest` arranca (cero tests aún, o `no tests collected`).
- [ ] 1.2 Abrir en `.gitignore` la excepción para versionar `data/catalog/real/generated/` **sin** des-ignorar el xlsx ni el backup SQL. Crear `data/catalog/real/generated/.gitkeep`. **Validación:** `git check-ignore -v data/catalog/real/product-JoiaBagur.xlsx` sigue ignorando; `git check-ignore data/catalog/real/generated/catalog-real-enriched.jsonl` no lo ignora.
- [ ] 1.3 Añadir fixtures de test bajo `scripts/catalog/tests/fixtures/`: un xlsx (o CSV leído por el mismo parser) con una familia de 3 tallas, varios unarios, un SKU pensado para unmatched, y una fila con descripción de 1001 caracteres. **Validación:** el parser de 2.1 las lee; ningún fixture es el export real.

## 2. Lectura del export e invariantes de identidad

- [ ] 2.1 Implementar la lectura de columnas `SKU`, `Name`, `Description`, `Price`, `Collection` alineadas con `ExcelImportService`. Rechazar filas sin SKU y SKUs duplicados. **Validación:** test de fixture `test_reader_rejects_duplicate_sku` y `test_reader_returns_all_fixture_rows`.
- [ ] 2.2 Implementar la comparación de identidad JSONL ↔ origen: `sku`, `name`, `price`, `collection_name` inmutables; `description` puede diferir. **Validación:** `test_sku_price_name_and_collection_are_never_modified` en verde sobre fixture.

## 3. Agrupación de variantes

- [ ] 3.1 Implementar la heurística del design (normalizar nombre, extraer sufijo de talla/material, stem → `variant_group_key`, `variant_label`, `family_seed.member_skus` ordenados). **Validación:** las 3 tallas del fixture comparten grupo; cada una tiene etiqueta; los unarios son grupos de un miembro.
- [ ] 3.2 Hacer la agrupación pura y determinista (misma entrada → mismos grupos). **Validación:** `test_grouping_is_deterministic` corre dos veces y compara mapas SKU → `variant_group_key`.
- [ ] 3.3 Spike sobre el xlsx real (cuando esté): imprimir conteo de grupos y multi-variante. Si el resultado es patológico (un solo grupo, o cero multi-variante con tallas visibles a ojo), ajustar sufijos **antes** de seguir. Anotar los conteos reales para el informe. **Validación:** el spike termina y los conteos quedan escritos; **no** se exige ~403/~23.

## 4. Reparto de calidad por familia

- [ ] 4.1 Implementar `hash(variant_group_key, seed) → {rich, sparse, empty}` con cortes 0.70 / 0.90, semilla por defecto `20260822`. Todos los miembros heredan el bucket. Mapear `rich`/`sparse` → `text_provenance: ai_assisted` y `empty` → `merchant` + descripción vacía. **Validación:** `test_variant_family_shares_text_quality` sobre el fixture de 3 tallas.
- [ ] 4.2 Medir ratios **por producto** y afirmar tolerancia ±3 pp solo sobre el corpus de 436 (validador de apply, no sobre el fixture pequeño). **Validación:** función de ratios testeada con un JSONL de prueba sintético que cumple 70/20/10 y otro que se sale y debe fallar.

## 5. Contrato JSONL, sidecar y tope de 1000

- [ ] 5.1 Definir el esquema de línea (campos del ticket) y serializar JSONL (una línea por producto). `product_id` ausente salvo lookup opcional posterior. **Validación:** cada línea del fixture parsea; `data_origin` es `real`; SKU único.
- [ ] 5.2 Validador: `description` ≤ 1000 caracteres; `empty` ⇒ texto vacío y `merchant`; `rich`/`sparse` ⇒ `ai_assisted` y texto no vacío; ningún grupo mezcla tiers. **Validación:** `test_description_over_1000_is_rejected`; `test_empty_tier_has_merchant_provenance_and_blank_text`; `test_every_product_has_data_origin_and_text_provenance`.
- [ ] 5.3 Escribir `.meta.json` con `generator_version`, `seed`, `generated_at`, ratios por tier y por `text_provenance`, conteos de agrupación. `model` omitido o `null`. **Validación:** test que lee el sidecar del fixture y comprueba las claves.

## 6. Ingesta SQL sobre fixture (sin Docker real obligatorio en la unidad)

- [ ] 6.1 Implementar el `UPDATE` por SKU (`Description`, `UpdatedAt`) leyendo `JPV_PG*` del entorno. Transacción única; rollback si el post-check de `Id`/`SKU`/`Name`/`Price`/`CollectionId` falla; unmatched **sin INSERT**. **Validación:** tests con base de prueba (testcontainers Postgres **o** SQLite no: la tabla se llama `"Products"` en PostgreSQL). Si Docker no está, omitir con motivo legible — mismo criterio que `ai-service` — y dejar un test de la lógica de invariantes sobre un fake de conexión.
- [ ] 6.2 Cubrir unmatched y aborto por invariante. **Validación:** `test_ingest_lists_unmatched_without_insert`; `test_ingest_rolls_back_when_identity_would_change`.

## 7. Pasada asistida y corpus de 436

- [ ] 7.1 Redactar las descripciones `rich` y `sparse` del export real siguiendo los criterios `catalog-assist/v1` del design §7 (evidencia, banda de precio, sin piedras/acabados inventados, ≤ 1000 caracteres). Dejar `empty` vacío. **Validación:** validador de 5.2 en verde sobre el JSONL real; ninguna línea > 1000.
- [ ] 7.2 Escribir `data/catalog/real/generated/catalog-real-enriched.jsonl` y el sidecar. **Validación:** 436 líneas; SKUs = xlsx; ratios ±3 pp; cero grupos mixtos; `git status` no muestra el xlsx.
- [ ] 7.3 Re-ejecutar agrupación + tiers con la misma semilla y comprobar que el mapa SKU → grupo/tier coincide con el JSONL commiteado. **Validación:** `test_generator_is_deterministic_for_same_seed` (sobre fixture) sigue verde; el check del real se anota en el informe.

## 8. Informe de enriquecimiento

- [ ] 8.1 Publicar `Documentos/Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md` con: conteos de agrupación, ratios por tier y `text_provenance`, lista unmatched (o «pendiente de ingesta»), muestras **antes/después** (mínimo 5 rich, 3 sparse, 2 empty), y el párrafo de limitación §15 (0 fotos; atributos no derivables plausibles no verificados; afirmación «catálogo realista»). **Validación:** el informe existe y las muestras salen del JSONL real, no inventadas.

## 9. Ingesta local contra Docker

- [ ] 9.1 Snapshot CSV o `pg_dump` parcial de `public."Products"` (`SKU, Name, Description, Price, CollectionId`). **Validación:** el fichero de snapshot existe en local y **no** se commitea (queda bajo `data/catalog/real/` gitignored, o fuera del repo).
- [ ] 9.2 Ejecutar la ingesta contra `localhost:5433` / `joiabagur_pv`. **Validación:** coincidentes tienen la `Description` del JSONL; `Name`/`Price`/`CollectionId`/`SKU` iguales al snapshot; unmatched documentados en el informe; transacción no dejó a medias.
- [ ] 9.3 (Opcional) Reescribir `product_id` en el JSONL vía lookup de SKU. **Validación:** si se hace, cada `product_id` coincide con `"Id"`; si no, el JSONL sigue válido sin el campo.

## 10. Verificación de alcance y documentación

- [ ] 10.1 `uv run pytest` en `scripts/catalog/` en verde. **Validación:** salida sin fallos; tests que necesitan Docker se omiten si no hay daemon, no se ponen rojos.
- [ ] 10.2 Confirmar alcance negativo: `git diff` no toca `ai-service/openapi.json`, `ai-service/pyproject.toml`, `ai-service/migrations/`, `backend/src/`, `frontend/`. **Validación:** `test_openapi_snapshot_is_stable` sigue verde si se corre la suite de `ai-service`; el diff del change no incluye esos árboles.
- [ ] 10.3 Actualizar docs de contexto: `Documentos/epicas.md` (EP12 / HU-AIENG-006a), nota breve en `Documentos/Proyecto Final AIEng/proyecto-final-plan-changes-openspec.md` si hace falta registrar la desviación de zona (`scripts/catalog/` vs `jbg_ai.data`), y coherencia de HU-AIENG-006a con el entregable. **Validación:** un lector de la épica llega al JSONL y al informe.
- [ ] 10.4 Ejecutar **`openspec validate --all --strict`** (el gate del proyecto, no solo el change). **Validación:** la salida reporta `0 failed`.
