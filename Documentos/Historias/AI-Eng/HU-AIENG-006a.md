# HU-AIENG-006a: Ingesta del catálogo real y corpus enriquecido versionado — texto asistido sin falsear identidad

## Formato estándar

Como **desarrollador del proyecto**, quiero **convertir el export real de 436 productos en un corpus enriquecido versionado, cargarlo en la base local y dejarlo listo para C09 y C10** **para** **desbloquear la ruta crítica del enriquecimiento y la simulación del mundo sin esperar al volumen sintético, sin falsear SKU, precio ni colección, y sin depender de un pipeline LLM en runtime**.

---

## Descripción

Primer tramo de C06 del Proyecto Final de IA (change OpenSpec `add-real-catalog-ingestion-and-text-assist` / **C06a**, épica **EP12 — Corpus y Enriquecimiento del Catálogo**). Marcado 🔴 en la ruta crítica. Prerrequisito: **C01** (archivado). C06 se partió en dos el 2026-08-17 porque C09 y C10 necesitan *un* corpus real antes que los 900-1.200 sintéticos de C06b.

El export llegó el 2026-08-17: **436 productos**, 28 colecciones — tamaño razonable, **texto casi vacío**. Media de 37,7 caracteres entre nombre y descripción; 51 productos sin descripción. Sobre ese dato, el enriquecimiento estructurado de C09 no puede demostrar sus puertas de calidad sin un corpus con descripciones utilizables. Esta historia produce ese corpus.

El valor no es de usuario final de tienda —no hay pantalla— sino de **desbloqueo**: C09 (extracción estructurada) y C10 (simulador POS/ventas) consumen lo que aquí se genera. **C18 no** toma semilla de familias de este JSONL: esos campos contaminarían el extractor. Sin C06a, C09 se construye solo sobre fixtures mínimos y C10 no tiene SKUs reales sobre los que simular.

**Desviación acordada respecto a la ficha C06a del plan (2026-08-22).** La ficha original incluye cliente LLM embebido en `ai-service`, migración Alembic de `text_provenance` y tests de generador Python. Esta historia adopta un camino operativo equivalente en resultado pero distinto en implementación:

- El texto enriquecido se produce en **una pasada de vendedor** (`catalog-assist/v2`) **solo** en los tiers `rich` y `sparse`. El agente se imagina la pieza como si la tuviera delante y escribe una descripción natural de producto. **No** menciona fotografías, fichas ni lagunas. Conserva `Name`/`Description` originales. **No inventa** piedras ni accesorios. `rich` se esmera más (3–5 frases); `sparse` es 1–2 frases. El tercer tier se llama **`original`** (no `empty`): **copia la `Description` del xlsx tal cual**, vacía o no; vaciar un texto que sí estaba es un error.
- `text_provenance` viaja en el **JSONL** (y en el informe); la **columna Alembic** en `ai.product_document` queda para **C13**.
- La ingesta operativa va a **`public."Products"`** en PostgreSQL local (Docker), por SKU, actualizando **solo `Description`**.

**Alcance de esta historia (sí):**

- Lectura del xlsx anonimizado [`data/catalog/real/product-JoiaBagur.xlsx`](../../data/catalog/real/product-JoiaBagur.xlsx) — columnas `SKU`, `Name`, `Description`, `Price`, `Collection`, alineadas con [`ExcelImportService`](../../../backend/src/JoiabagurPV.Application/Services/ExcelImportService.cs).
- Agrupación de variantes **solo interna** para el sorteo de calidad. El JSONL **no** emite `variant_group_key`, `variant_label` ni `family_seed`.
- Reparto de calidad **por familia de variantes** con **semilla fija**: ~70 % `rich`, ~20 % `sparse`, ~10 % `original` — **toda la familia comparte nivel** (§8.4). `original` = texto del comerciante, no «campo vacío».
- Redacción asistida de vendedor (`catalog-assist/v2`): describir lo que «se ve», sin aludir a la foto; limitación (0 fotos reales) **solo en el informe**.
- Salida versionada:
  - `data/catalog/real/generated/catalog-real-enriched.jsonl` — **versionado en git** (derivado anonimizado)
  - sidecar `.meta.json` (`generator_version` `c06a-assist/v2`, `seed`, `generated_at`, ratios)
  - informe [`Documentos/Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md`](../Proyecto%20Final%20AIEng/informes/c06a-catalog-enrichment-report.md)
- Metadatos por producto en JSONL: `data_origin: real`, `text_provenance` (`merchant` | `ai_assisted`), `text_quality_tier`, más campos de catálogo inmutables. **Sin** campos de familia.
- **`product_id` en JSONL:** opcional, por lookup de SKU.
- **Ingesta en BD local** (Docker, puerto host **5433**, BD `joiabagur_pv`): `UPDATE "Products"` **por SKU**, conservando `Id`, `SKU`, `Price`, `CollectionId` y **`Name`**; actualizar **únicamente `Description`**.
- Scripts en **`scripts/catalog/`**.
- xlsx crudo permanece gitignored en `data/catalog/real/`.

**Fuera de alcance (no):**

- **C06b** — ampliación sintética a 900-1.200 productos.
- **C09** — pipeline real `POST /v1/enrich/products`, vocabularios cerrados, puertas de lote sobre perfiles IA.
- **Cliente LLM** en `ai-service`, settings `LLM_*`, `prompts/` como servicio en runtime.
- **Migración Alembic `text_provenance`** — responsabilidad de **C13**, no de C06a.
- Cambios en **`ai-service/openapi.json`**, routers, backend API, frontend.
- **RDS / producción** — solo base local Docker.
- Columna **`text_provenance`** en entidad .NET `Product`.
- **C08** `ProductAiProfile` — este change no crea perfiles estructurados; solo enriquece texto de catálogo.
- **C18** — semilla de `ProductFamily`; no se emite en este JSONL.

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Dos ejes de procedencia (§8.1.1) | `data_origin: real` en los 436 · `text_provenance`: `ai_assisted` en `rich`/`sparse` · `merchant` en `original` (~10 %), **texto del xlsx sin reescribir** |
| Unidad del reparto de calidad | **Familia de variantes**, nunca producto suelto ni tipo de pieza (§8.4 advierte del sesgo 78 % en cuatro tipos) |
| Invariante .NET | **SKU, precio, colección y nombre nunca se modifican** — la asistencia solo toca `Description` en ingesta |
| Limitación multimodal | 0 fotos reales: el **informe** lo declara; el texto de producto es de vendedor, plausible, sin mencionar la foto |
| Dónde vive `text_provenance` | **JSONL + informe en C06a** · columna `ai.product_document` en **C13** · `public."Products"` **no** |
| Generación del texto | **Pasada de vendedor** `catalog-assist/v2`; scripts en `scripts/catalog/` |
| Agrupación de variantes | **Interna** para el sorteo; **prohibida** en cada línea JSONL |
| JSONL en git | **Sí** — derivado anonimizado commiteado; xlsx crudo sigue ignorado |
| Puerta C09 (§8.5) | Cobertura de tags ≥ 90 % sobre estrato `ai_assisted` — el reparto 70/20/10 existe para que esa puerta sea alcanzable (~77 % global teórico) |
| Corpus archivado | xlsx fuera de git; C24 podrá medir delta «con asistencia − sin asistencia» (§0 plan) |
| Honestidad del README | Resultado principal sobre `data_origin: real` declarando qué `text_provenance` lo compone — «catálogo **realista**», no «real» tal cual |

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C06a, §0 revisiones 2026-08-17, reglas transversales de testing),
[proyecto-final-diseno-rag-joiabagur.md](../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§8.1.1 corpus híbrido, §8.4 realismo dirigido, §8.5 puertas, §15 limitaciones),
[epicas.md](../../epicas.md) (EP12),
[modelo-de-datos.md](../../modelo-de-datos.md) (`Product`),
[HU-AIENG-001.md](HU-AIENG-001.md), [HU-AIENG-005.md](HU-AIENG-005.md) (`data_origin` en `ai.product_document`),
change OpenSpec [`openspec/changes/archive/2026-08-22-add-real-catalog-ingestion-and-text-assist/`](../../../openspec/changes/archive/2026-08-22-add-real-catalog-ingestion-and-text-assist/) y su [ticket técnico](../../../openspec/changes/archive/2026-08-22-add-real-catalog-ingestion-and-text-assist/ticket.md),
[`ExcelImportService`](../../../backend/src/JoiabagurPV.Application/Services/ExcelImportService.cs).

---

## Criterios de Aceptación

### Escenario 1: El corpus contiene exactamente los 436 productos reales
**Dado que** existe el xlsx anonimizado con 436 filas de producto
**Cuando** se completa la generación del corpus
**Entonces** el JSONL contiene **436 líneas**, una por SKU
**Y** cada línea lleva `data_origin: real`
**Y** cada SKU del xlsx aparece una sola vez

### Escenario 2: SKU, precio, colección y nombre son inmutables
**Dado que** el xlsx es la fuente autoritativa de identidad de producto
**Cuando** se compara cualquier línea del JSONL con su fila de origen
**Entonces** `sku`, `price`, `collection_name` y `name` coinciden con el xlsx
**Y** la ingesta en `public."Products"` no altera `Price`, `CollectionId` ni `Name`

### Escenario 3: El reparto de calidad respeta la unidad familia
**Dado que** el diseño §8.4 exige sortear calidad **por familia de variantes**
**Cuando** se inspecciona el JSONL junto a los nombres de origen
**Entonces** ninguna familia interna mezcla dos `text_quality_tier` distintos
**Y** el JSONL **no** contiene `variant_group_key`, `variant_label` ni `family_seed`
**Y** los ratios globales por producto están dentro de ~70 % / ~20 % / ~10 % con tolerancia razonable (±3 pp)

### Escenario 4: Los estratos `text_provenance` cuadran con el reparto
**Dado que** el tier `original` (~10 %) debe aportar texto de comerciante sin castigar la puerta C09 sobre asistidos
**Cuando** se agrupan productos por `text_provenance`
**Entonces** los tiers `rich` y `sparse` llevan `text_provenance: ai_assisted`
**Y** los del tier `original` llevan `text_provenance: merchant` y la `Description` **idéntica** a la del xlsx (no se vacía si había texto)

### Escenario 5: El JSONL no contamina fases posteriores con semilla de familias
**Dado que** C09 extrae sobre el texto y C18 no debe leer agrupación de este corpus
**Cuando** se inspecciona cualquier línea del JSONL
**Entonces** no existen las claves `variant_group_key`, `variant_label` ni `family_seed`

### Escenario 6: La redacción es de vendedor, no de ficha
**Dado que** no hay fotos reales y el texto debe servir a C09 como descripción de producto
**Cuando** se revisan muestras del informe (mínimo 5 `rich`, 3 `sparse`, 2 `original`)
**Entonces** las descripciones `rich` y `sparse` leen como catálogo (pieza, motivo, metal), no como comentario sobre el export
**Y** no mencionan fotografías, fichas de origen ni que «no se cuentan piedras»
**Y** no inventan piedras ni accesorios que no estén en `Name` o `Description` originales
**Y** las muestras `original` coinciden con la `Description` del xlsx (no se vacían ni se reescriben)
**Y** el informe, no el producto, declara que el reconocimiento visual es plausible

### Escenario 7: El corpus es determinista para la misma semilla
**Dado que** el diseño §8.5 exige trazabilidad con `seed` fija
**Cuando** se regenera el corpus con la misma semilla y la misma versión del generador
**Entonces** agrupación, tiers y metadatos `.meta.json` son idénticos
**Y** las descripciones asistidas son reproducibles bajo las mismas reglas acordadas

### Escenario 8: La ingesta local actualiza solo Description por SKU
**Dado que** PostgreSQL local (Docker) contiene filas en `public."Products"` con los SKUs del xlsx
**Cuando** se ejecuta el script de ingesta en `scripts/catalog/` contra el JSONL enriquecido
**Entonces** cada SKU coincidente recibe la nueva `Description`
**Y** los SKUs sin fila en BD quedan listados en el informe como *unmatched*
**Y** ninguna fila pierde su `SKU`, `Price`, `CollectionId` ni `Name`

### Escenario 9: El sidecar documenta trazabilidad y el JSONL está en git
**Dado que** el corpus debe regenerarse con un comando y auditarse en el repositorio
**Cuando** se lee `.meta.json` y el estado del repositorio
**Entonces** incluye `generator_version`, `seed`, `generated_at` y ratios por tier y `text_provenance`
**Y** `catalog-real-enriched.jsonl` está versionado en git (xlsx crudo no)

### Escenario 10: Fuera de alcance explícito
**Dado que** esta historia está implementada según el alcance acordado
**Cuando** se revisa el entregable
**Entonces** **no** existe cliente LLM en `ai-service/pyproject.toml` por este change
**Y** **no** hay migración Alembic de `text_provenance` en C06a (queda para **C13**)
**Y** `ai-service/openapi.json` **no** ha cambiado
**Y** **no** se ha implementado C09 ni C06b

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final (change Python 🔴). No hay rol Admin/Operador de tienda en la generación; la ingesta local es operación de desarrollo.

- **Por qué está en la ruta crítica.** C06a desbloquea **C09 y C10** sin esperar C06b. C09 construye el extractor; C10 simula ventas sobre SKUs reales. Ambos necesitan *un* corpus, no *el* corpus de 1.200.

- **Relación con C08.** C08 enriquece **perfiles IA estructurados** en .NET. C06a enriquece **texto de catálogo** en `Product.Description` y metadatos en JSONL. Son capas distintas: C09 leerá el texto enriquecido para proponer `piece_type`, `materials[]`, etc.

- **Estado del export.** El xlsx vive en `data/catalog/real/` (gitignored). El backup SQL local es **solo esquema**, sin datos — el `product_id` de .NET se obtiene por **lookup de SKU** en ingesta.

- **Relación con C18.** C18 no lee agrupación de este JSONL. La familia es interna al sorteo de calidad de C06a.

**Entregable.** Corpus: [`data/catalog/real/generated/catalog-real-enriched.jsonl`](../../../data/catalog/real/generated/catalog-real-enriched.jsonl). Informe: [`c06a-catalog-enrichment-report.md`](../../Proyecto%20Final%20AIEng/informes/c06a-catalog-enrichment-report.md). Pipeline: [`scripts/catalog/`](../../../scripts/catalog/).

---

## Tareas

1. Completar artefactos OpenSpec del change `add-real-catalog-ingestion-and-text-assist` (proposal, design, specs, tasks).
2. Implementar scripts en `scripts/catalog/`: lectura xlsx, agrupación de variantes, reparto de calidad por semilla, ingesta SQL.
3. Generar JSONL enriquecido (436 productos) e informe con estadísticas y muestras; commitear JSONL.
4. Ejecutar ingesta contra Docker local (solo `Description`) y verificar invariantes post-update.
5. Documentar desviaciones respecto a la ficha C06a original en `design.md`.
6. Verificar `openspec validate --all --strict` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 5 — desbloquea cadena C09 → C11 → C13 → hito 19 agosto
- **Urgencia:** 5 — 🔴 ruta crítica Ola 1
- **Complejidad:** 4 — mezcla datos reales, reglas de calidad, redacción asistida e ingesta SQL; sin contrato HTTP nuevo
- **Riesgos y dependencias:** C01 archivado; requiere xlsx local y Postgres Docker con productos importados; desviación de ficha original documentada en design
