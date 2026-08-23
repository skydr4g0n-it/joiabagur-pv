# `jbg_ai.data` — CLI C06b

Genera el corpus sintético e inserta colecciones/productos en Postgres **local**.
`jbg_ai.api.main` **no** importa este paquete. `GET /health` arranca sin clave de proveedor.

`generate` corre **en el host**, no dentro del contenedor `jbg-ai`. Docker solo entra
en `ingest` (Postgres en `:5433`).

## Secretos locales

Un solo fichero, junto al compose: [`backend/.env.example`](../../../backend/.env.example)
→ copia a `backend/.env` (gitignored).

```powershell
cd backend
copy .env.example .env
# rellena JPV_CATALOG_LLM_API_KEY (no uses la clave del RAG)
```

El CLI carga ese `.env` solo. Compose interpola `${VAR}` desde el mismo fichero
pero **no** lo inyecta entero en `jbg-ai` (la clave de catálogo no debe entrar
al runtime). Producción: SSM `/jpv/prod/*` (C17), otro nombre.

| Variable | Quién | Distinta de |
|---|---|---|
| `JPV_CATALOG_LLM_API_KEY` | solo `generate` | `JPV_RAG_LLM_API_KEY` (C09, contenedor + SSM) |
| `JPV_CATALOG_LLM_MODEL` | `generate` | default `gpt-4o` (OpenAI) |
| `JPV_PGHOST` `JPV_PGPORT` `JPV_PGDATABASE` `JPV_PGUSER` `JPV_PGPASSWORD` | `ingest` | host **5433**, BD `joiabagur_pv` |

## Comandos

```powershell
cd ai-service
uv sync --system-certs
uv run --system-certs python -m jbg_ai.data --help
uv run --system-certs python -m jbg_ai.data generate --out ../data/catalog/synthetic/generated
uv run --system-certs python -m jbg_ai.data ingest --jsonl ../data/catalog/synthetic/generated/catalog-synthetic.jsonl
```

- `generator_version`: `c06b-synth/v3`
- `prompt_version`: `catalog-synth/v3` (`ai-service/prompts/catalog-synth/v3.md`; `v1` y `v2` se conservan)
- Tiers 70/20/10 calibrados al JSONL real: `rich` ≥150 (media real ~290), `sparse` objetivo ~115 (techo de frase entera 140), `short` ≤32 o vacío (~20 % de los `short`, stem entero). El recorte solo deja frases enteras; si no caben, vacío o redraft.
- Sidecar: `empty_short_count` / `empty_short_ratio_of_short` además de ratios, unassigned y familias léxicas.
- semilla por defecto: `20260822`
- ~20 % de sintéticos sin `collection_name`; el resto en 8–12 colecciones **desiguales**
- Familias léxicas S/M/L/XL: ~40 % de productos; de esos, ~60 % en familia completa y ~40 % incompleta. Misma descripción y colección; solo cambian talla y precio.
- Sin `--regenerate-text` no se pisa un JSONL ya escrito.
- La ingesta es un `INSERT` transaccional. No toca SKUs reales ni `ProductFamily*`.
  El rol de runtime de `jbg-ai` no gana `INSERT` sobre `public` (§6.3).
