## Why

El export real de 436 productos cubre el volumen de ancla del golden set, pero es **textualmente casi vacío**: ~38 caracteres de media entre nombre y descripción, 51 productos sin descripción, y cero etiquetas de estilo, color u ocasión. C09 no puede demostrar las puertas de cobertura de tags sobre ese input, y C10 no tiene SKUs reales con semántica creíble sobre los que simular ventas. Se hace ahora porque C06a está en la ruta crítica de la Ola 1: desbloquea C09 y C10 **sin esperar** a los 900–1.200 sintéticos de C06b, y su único prerrequisito (C01) ya está archivado.

## What Changes

- **Corpus JSONL versionado** de los 436 productos reales, una línea por SKU, con `data_origin: real` y los dos ejes de procedencia del diseño §8.1.1. El derivado anonimizado se **commitea** en `data/catalog/real/generated/`; el xlsx crudo sigue gitignored.
- **Reparto de calidad** con semilla fija: ~70 % `rich` / ~20 % `sparse` / ~10 % `original`. Internamente el sorteo sigue siendo **por familia de variantes** (para que dos tallas no divergjan de riqueza), pero el JSONL **no emite** `variant_group_key`, `variant_label` ni `family_seed`: contaminarían C09/C10. C18 no consume semilla de este corpus.
- **Redacción asistida de vendedor** (`catalog-assist/v2`), **solo** en `rich` y `sparse`: el agente se imagina la pieza como si la tuviera delante y escribe una descripción **natural de producto**. El texto describe solo lo que «se ve»; **no menciona** fotografías, fichas, lagunas ni el hecho de imaginar. Conserva todo lo que ya está en `Name` y `Description` originales. **No inventa** piedras ni accesorios que no consten. `rich` se esmera más (3–5 frases); `sparse` es 1–2 frases, más contenido. El tier **`original`** (antes mal llamado `empty`) **no redacta**: copia la `Description` del xlsx **byte a byte** (vacía o no). Vaciar un texto que sí existía es un error, no el comportamiento del tier.
- **Ingesta local** contra PostgreSQL Docker (`localhost:5433`, BD `joiabagur_pv`): `UPDATE public."Products"` **por SKU**, tocando **únicamente `Description`** (y `UpdatedAt`). `Id`, `SKU`, `Name`, `Price` y `CollectionId` son invariantes.
- **Sidecar `.meta.json`** (`generator_version` `c06a-assist/v2`, `seed`, `generated_at`, ratios por tier y por `text_provenance`) e **informe** `Documentos/Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md` con estadísticas y muestras. La limitación (0 fotos reales; el texto es plausiblemente visual) se declara **solo en el informe**, nunca en las descripciones de producto.
- **Scripts** en `scripts/catalog/` (lectura xlsx, agrupación interna, reparto, validación, ingesta). Tests sin LLM ni proveedores externos.

**Desviación respecto a la ficha C06a del plan (acordada 2026-08-22, documentada en `design.md`):** no hay cliente LLM embebido en `ai-service`, no hay migración Alembic de `text_provenance` (queda para **C13**), la ingesta operativa va a `public."Products"`, y **no** se emite semilla de familias en el JSONL.

**Fuera de alcance:** C06b, C09, C08 (`ProductAiProfile`), C18 (semilla de familias), cliente LLM / `prompts/` como servicio, migración `text_provenance`, cambios en `ai-service/openapi.json`, routers, backend API, frontend, RDS/producción, columna de procedencia en la entidad .NET `Product`.

Sin breaking changes: no hay contrato HTTP nuevo ni modificación de contratos existentes.

## Capabilities

### New Capabilities

- `real-catalog-corpus`: pipeline offline que convierte el export xlsx de 436 productos en un corpus JSONL versionado con procedencia dual, reparto de calidad y texto asistido de vendedor (como si se viera la pieza, sin contaminar con metadatos de familia); más la ingesta local que actualiza solo `Description` en `public."Products"` por SKU, con invariantes de identidad y trazabilidad en sidecar e informe.

### Modified Capabilities

Ninguna. `product-management` describe el catálogo .NET (CRUD, import Excel, listados) y no cambia de requisitos: este change no toca API ni entidad. `product-family` es la entidad de negocio de C07/C18; este change **no** emite semilla en JSONL. `ai-vector-schema` ya tiene `data_origin` desde C05; `text_provenance` en `ai.product_document` es de **C13**. `product-ai-profile` es C08 y no se toca.

## Impact

**Nuevo**

- `scripts/catalog/`: lectura xlsx, agrupación interna para el sorteo, reparto, validación de invariantes, ingesta SQL.
- `data/catalog/real/generated/catalog-real-enriched.jsonl` y sidecar `.meta.json` (commiteados).
- `Documentos/Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md`.
- Excepción en `.gitignore` para versionar `data/catalog/real/generated/` sin levantar el xlsx crudo.

**PostgreSQL local (Docker)** — `UPDATE` de `Description` en `public."Products"` por SKU. Transacción única; rollback si un invariante se rompe. SKUs sin fila → lista *unmatched* en el informe. No toca RDS.

**Sin cambios** — `backend/` (código, migraciones EF, entidad `Product`), `frontend/`, `ai-service/src/`, `ai-service/migrations/`, `ai-service/openapi.json`, `ai-service/pyproject.toml` (sin cliente LLM), `terraform/`.

**Cota dura de texto:** `Product.Description` es `varchar(1000)`. Las descripciones asistidas deben caber; el validador del JSONL lo afirma antes de la ingesta.

**Dependientes desbloqueados:** C09 (extractor sobre texto de catálogo utilizable) y C10 (simulador sobre SKUs reales). C13 copiará procedencia al indexar. **C18 no** toma semilla de este JSONL.
