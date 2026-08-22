## Why

El export real de 436 productos cubre el volumen de ancla del golden set, pero es **textualmente casi vacío**: ~38 caracteres de media entre nombre y descripción, 51 productos sin descripción, y cero etiquetas de estilo, color u ocasión. C09 no puede demostrar las puertas de cobertura de tags sobre ese input, y C10 no tiene SKUs reales con semántica creíble sobre los que simular ventas. Se hace ahora porque C06a está en la ruta crítica de la Ola 1: desbloquea C09 y C10 **sin esperar** a los 900–1.200 sintéticos de C06b, y su único prerrequisito (C01) ya está archivado.

## What Changes

- **Corpus JSONL versionado** de los 436 productos reales, una línea por SKU, con `data_origin: real` y los dos ejes de procedencia del diseño §8.1.1. El derivado anonimizado se **commitea** en `data/catalog/real/generated/`; el xlsx crudo sigue gitignored.
- **Agrupación determinista de variantes** emitida en el JSONL (`variant_group_key`, `variant_label`, `family_seed`) como semilla para C18. El conteo de exploración (~403 grupos, ~23 multi-variante) es **referencia orientativa con tolerancia**, no un requisito numérico.
- **Reparto de calidad sorteado por familia de variantes** con semilla fija: ~70 % rico / ~20 % escueto / ~10 % vacío. Toda la familia comparte `text_quality_tier`. Los tiers `rich` y `sparse` llevan `text_provenance: ai_assisted`; el `empty` lleva `merchant` y descripción vacía.
- **Redacción asistida en una pasada** (agente + reglas deterministas + criterios del diseño §15): expande evidencia del nombre/descripción original, acota por banda de precio lo que no consta, y **no inventa** piedras, acabados ni conteos visuales. No hay cliente LLM en runtime ni llamadas API en tests.
- **Ingesta local** contra PostgreSQL Docker (`localhost:5433`, BD `joiabagur_pv`): `UPDATE public."Products"` **por SKU**, tocando **únicamente `Description`** (y `UpdatedAt`). `Id`, `SKU`, `Name`, `Price` y `CollectionId` son invariantes.
- **Sidecar `.meta.json`** (`generator_version`, `seed`, `generated_at`, ratios por tier y por `text_provenance`, conteos de agrupación) e **informe** `Documentos/Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md` con estadísticas, muestras y la limitación multimodal declarada.
- **Scripts deterministas** en `scripts/catalog/` (lectura xlsx, agrupación, reparto, validación, ingesta). Tests sin LLM ni proveedores externos.

**Desviación respecto a la ficha C06a del plan (acordada 2026-08-22, documentada en `design.md`):** no hay cliente LLM embebido en `ai-service`, no hay migración Alembic de `text_provenance` (queda para **C13**), y la ingesta operativa va a `public."Products"`, no a `ai.product_document`.

**Fuera de alcance:** C06b, C09, C08 (`ProductAiProfile`), cliente LLM / `prompts/` como servicio, migración `text_provenance`, cambios en `ai-service/openapi.json`, routers, backend API, frontend, RDS/producción, columna de procedencia en la entidad .NET `Product`.

Sin breaking changes: no hay contrato HTTP nuevo ni modificación de contratos existentes.

## Capabilities

### New Capabilities

- `real-catalog-corpus`: pipeline offline que convierte el export xlsx de 436 productos en un corpus JSONL versionado con procedencia dual, agrupación de variantes, reparto de calidad por familia y texto asistido bajo la limitación §15; más la ingesta local que actualiza solo `Description` en `public."Products"` por SKU, con invariantes de identidad y trazabilidad en sidecar e informe.

### Modified Capabilities

Ninguna. `product-management` describe el catálogo .NET (CRUD, import Excel, listados) y no cambia de requisitos: este change no toca API ni entidad. `product-family` es la entidad de negocio de C07/C18; aquí solo se emite una semilla en JSONL. `ai-vector-schema` ya tiene `data_origin` desde C05; `text_provenance` en `ai.product_document` es de **C13**. `product-ai-profile` es C08 y no se toca.

## Impact

**Nuevo**

- `scripts/catalog/`: lectura xlsx, agrupación, reparto, validación de invariantes, ingesta SQL.
- `data/catalog/real/generated/catalog-real-enriched.jsonl` y sidecar `.meta.json` (commiteados).
- `Documentos/Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md`.
- Excepción en `.gitignore` para versionar `data/catalog/real/generated/` sin levantar el xlsx crudo.

**PostgreSQL local (Docker)** — `UPDATE` de `Description` en `public."Products"` por SKU. Transacción única; rollback si un invariante se rompe. SKUs sin fila → lista *unmatched* en el informe. No toca RDS.

**Sin cambios** — `backend/` (código, migraciones EF, entidad `Product`), `frontend/`, `ai-service/src/`, `ai-service/migrations/`, `ai-service/openapi.json`, `ai-service/pyproject.toml` (sin cliente LLM), `terraform/`.

**Cota dura de texto:** `Product.Description` es `varchar(1000)`. Las descripciones asistidas deben caber; el validador del JSONL lo afirma antes de la ingesta.

**Dependientes desbloqueados:** C09 (extractor sobre texto utilizable), C10 (simulador sobre SKUs reales), y más adelante C18 (semilla de familias) y C13 (columna `text_provenance` al indexar).
