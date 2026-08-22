## Why

C06a dejó 436 productos reales con texto utilizable y desbloqueó C09, pero C11 y C24 necesitan **volumen ya ingerido** en `.NET`: el índice nace del feed C12, no del JSONL. Se hace ahora porque C06a está archivado, el change admite correr en paralelo a C09, y un JSONL sintético sin `INSERT` no llega al índice.

## What Changes

- **Corpus JSONL sintético versionado** (~1.200 productos **totales** junto al real; holgura, no umbral exacto): una línea por pieza imaginada, con `data_origin: synthetic` y `text_provenance: synthetic`. Commiteado en `data/catalog/synthetic/generated/`.
- **CLI en `jbg_ai.data`** (orquestador + cliente OpenAI + prompt versionado). `jbg_ai.api.main` **no** lo importa. Sin ruta HTTP en FastAPI ni en la API .NET. Settings `LLM_*` / clave OpenAI **opcionales** al arrancar `GET /health`; el CLI las exige.
- **SKU reservados por código** con el esquema del real (`SKU` + 2/3/4 dígitos según magnitud), continuando **después de 436** (`SKU437`…). Sin prefijo `SYN-` ni otra marca que delate origen a C09. Unique vs JSONL C06a y vs `"Products"."SKU"`.
- **8–12 colecciones nuevas** con nombre de **diseño** (p. ej. «El Jaleo», «Fuego»). Hotel / aeropuerto / turista / atelier son **brief de público o POS pensado** para el prompt y el informe, no `Collection.Name` ni columna en `Product`. Ningún sintético reutiliza una colección real.
- **Texto y precio razonados por OpenAI** (temperatura > 0). El código sella procedencia, asigna `text_quality_tier` (~70 `rich` / ~20 `sparse` / ~10 corto o vacío) por **stem del `Name`** (hermanos de talla no mezclan tier), valida `Description` ≤ 1000 y `0 < price < 50000`. ~35 % de las descripciones nombran dos o más materiales **en la prosa**; el JSONL **no** lleva `materials[]`.
- **Sin pistas a C18 ni a C09:** el JSONL no emite `variant_group_key`, `variant_label`, `family_seed`, `materials` ni `product_id`. La ingesta no escribe `"ProductFamilies"` / `"ProductFamilyMembers"`. Todos los sintéticos nacen huérfanos.
- **Ingesta local** (Docker, host **5433**, BD `joiabagur_pv`): transacción con `INSERT` de colecciones nuevas y productos (`IsActive = true`). **No** `UPDATE` de filas reales. Credenciales solo por `JPV_PG*`. El `Id` lo genera PostgreSQL; el JSONL no se reescribe.
- **Sidecar** (`.meta.json`: `generator_version`, `seed`, `model`, `prompt_version`, `generated_at`, recuentos y ratios) e **informe** `Documentos/Proyecto Final AIEng/informes/c06b-synthetic-catalog-report.md`. Regenerar texto exige flag explícito.

**Desviación respecto a la ficha v3 del plan (acordada 2026-08-22, documentada en `design.md`):** no hay generador determinista que calibre precio/SKU/familias al real; no se preasignan ~350 familias ni un 15 % de huérfanos (todos huérfanos; familias = C18); las colecciones no se nombran por canal; hay `INSERT`, no solo JSONL.

**Fuera de alcance:** C09, C10, C18, C13 (`text_provenance` en `ai.product_document`), reutilizar `scripts/catalog/assist.py`, ruta HTTP, regenerar `openapi.json`, RDS/producción, migración EF/Alembic, columna de procedencia o de canal en `Product`, papelería u otros no-joyería.

Sin breaking changes: no hay contrato HTTP nuevo ni modificación de contratos existentes.

## Capabilities

### New Capabilities

- `synthetic-catalog-corpus`: CLI offline en `jbg_ai.data` que genera un corpus JSONL de productos sintéticos de joyería vendible (SKU reservado por código, texto y precio por OpenAI, procedencia sellada, tiers por stem de nombre, colecciones de diseño nuevas) y lo inserta en PostgreSQL local sin tocar el ancla real ni las tablas de familia.

### Modified Capabilities

Ninguna. `real-catalog-corpus` describe el pipeline C06a (xlsx → JSONL real + `UPDATE` de `Description`) y no cambia de requisitos. `product-management` es el CRUD .NET y no se toca. `product-family` es la entidad de C07/C18; este change **no** escribe miembros. `ai-service-runtime` ya exige solo `APP_ENV` / `SERVICE_VERSION` / `JWT_SECRET`; las claves OpenAI se añaden como opcionales y no alteran el boot de `/health`. `ai-service-api-contracts` no gana rutas. `text_provenance` en `ai.product_document` es de **C13**.

## Impact

**Nuevo**

- `ai-service/src/jbg_ai/data/`: orquestador, reservador de SKU, cliente OpenAI, validación, CLI de generate e ingest.
- `ai-service/prompts/` (p. ej. `catalog-synth/v1`): prompt versionado; distingue brief de público vs nombre de colección.
- `data/catalog/synthetic/generated/catalog-synthetic.jsonl` y sidecar `.meta.json` (commiteados).
- `Documentos/Proyecto Final AIEng/informes/c06b-synthetic-catalog-report.md`.
- Excepción en `.gitignore` para versionar `data/catalog/synthetic/generated/`.

**Modificado**

- `ai-service/src/jbg_ai/config/settings.py`: `LLM_*` / clave OpenAI **opcionales**.
- `ai-service/pyproject.toml`: dependencia del cliente OpenAI (u HTTP equivalente).

**PostgreSQL local (Docker)** — `INSERT` en `"Collections"` y `"Products"`. Transacción única; rollback si colisiona SKU o `Collection.Name`. Cero escrituras a `"ProductFamily*"`. No toca RDS.

**Sin cambios** — `backend/` (código, migraciones EF, entidad `Product`), `frontend/`, `ai-service/openapi.json`, `ai-service/migrations/`, `ai-service/src/jbg_ai/api/main.py` (no importa `jbg_ai.data`), `terraform/`, `scripts/catalog/`.

**Frontera §6.3.** El rol de runtime de `jbg-ai` no gana `INSERT` sobre `public`. El CLI de desarrollo usa `JPV_PG*` igual que C06a.

**Dependientes desbloqueados:** C11 y C24 por volumen ingerido. C09 **no** espera este change. C10 **no** lo necesita. C18 posterior para familias.
