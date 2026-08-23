# catalog-pipeline (C06a)

Scripts offline para leer el export xlsx, agrupar variantes, sortear calidad
textual, validar el JSONL e ingerir solo `Description` en `public."Products"`.

No hay cliente LLM. `generator_version`: `c06a-assist/v2`. Semilla por defecto:
`20260822`. El JSONL no emite campos de familia. El tier `original` copia la
`Description` del xlsx. El corpus sintético (C06b) no vive aquí: CLI
`python -m jbg_ai.data` en [`ai-service/src/jbg_ai/data/`](../../ai-service/src/jbg_ai/data/README.md).

## Requisitos

Python ≥ 3.11. En esta máquina, `uv` necesita `--system-certs`.

```powershell
cd scripts/catalog
uv sync --system-certs
```

## Comandos

Desde `scripts/catalog/`:

```powershell
# Agrupar + sortear tiers + redactar (rich/sparse) y escribir JSONL + sidecar
uv run catalog-pipeline generate --source ..\..\data\catalog\real\product-JoiaBagur.xlsx --out ..\..\data\catalog\real\generated

# Solo validar un JSONL (y, si hay xlsx, invariantes de identidad)
uv run catalog-pipeline validate --jsonl ..\..\data\catalog\real\generated\catalog-real-enriched.jsonl --source ..\..\data\catalog\real\product-JoiaBagur.xlsx

# Spike de agrupación (conteos; no commitea)
uv run catalog-pipeline spike --source ..\..\data\catalog\real\product-JoiaBagur.xlsx

# Ingesta local: UPDATE Description por SKU.
# Preferible: las mismas JPV_PG* de backend/.env (copia de backend/.env.example).
$env:JPV_PGHOST = "localhost"
$env:JPV_PGPORT = "5433"
$env:JPV_PGDATABASE = "joiabagur_pv"
$env:JPV_PGUSER = "postgres"
$env:JPV_PGPASSWORD = "password"
uv run catalog-pipeline ingest --jsonl ..\..\data\catalog\real\generated\catalog-real-enriched.jsonl
```

`generate` no reescribe descripciones ya asistidas de un JSONL existente salvo
`--regenerate-text`.

## Variables `JPV_PG*`

| Variable | Uso |
|---|---|
| `JPV_PGHOST` | Host (local: `localhost`) |
| `JPV_PGPORT` | Puerto publicado (local: `5433`) |
| `JPV_PGDATABASE` | Base (`joiabagur_pv`) |
| `JPV_PGUSER` | Usuario |
| `JPV_PGPASSWORD` | Contraseña |

Nunca se commitean credenciales. El sitio canónico en local es `backend/.env`
(junto a `docker-compose.yml`; plantilla `backend/.env.example`). El compose
documenta `postgres` / `password`; eso no vive en el código de los scripts.

## Tests

```powershell
uv run pytest
```

Los tests usan fixtures bajo `tests/fixtures/`. El xlsx real no entra en la
suite. Si un test de Docker no tiene daemon, se omite con motivo legible.
