# Runbook C12 — AutoBulk del catálogo (1.200 perfiles)

Procedimiento, no acta. **No se ejecuta en el merge de C12.** Es la puerta de un C13 *útil*: sin 1.200 `Approved`, el primer `POST /v1/index/sync` deja `ai.product_document` a 0 (fallo mudo de S11).

## Para qué

Poblar `ProductAiProfile` de los 1.200 productos ingeridos con `reviewMode: AutoBulk` y `force: false`, para que `GET /api/ai/index-feed/catalog` emita upserts y C13 tenga algo que indexar.

## Quién y cuándo

Una persona, en local (y más adelante en demo), **después de archivar C12 y antes del apply de C13**. No es criterio de merge de este change.

## Condiciones (todas obligatorias)

API .NET en `http://localhost:5056`. Postgres publicado en `:5433`. jbg-ai publicado en `:8001`.

```powershell
# 1) Productos ingeridos
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -c "SELECT COUNT(*) FROM public.""Products"";"
# esperar 1200

# 2) Perfiles (antes deben ser 0; después Approved = 1200)
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -c "SELECT ""ReviewStatus"", COUNT(*) FROM public.""ProductAiProfiles"" GROUP BY 1;"

# 3) jbg-ai NO está en stub
docker exec jpv-pv-jbg-ai printenv STUB_MODE
# debe ser false — Compose lo fija a true; recrear el servicio con
# STUB_MODE=false y JPV_RAG_LLM_API_KEY (y JPV_RAG_LLM_MODEL, default openai/gpt-4o)

# 4) Salud
curl -s http://localhost:8001/health
curl -s http://localhost:5056/api/health
```

## Ejecución

Lote 50 = `AiEnrichRequest.MaxBatchSize`. 1.200 / 50 = **24 llamadas**. Login admin (`admin` / `Admin123!` según `backend/api-tests/README.md`); cookie `access_token`. IDs desde SQL, no desde `GET /api/products` (máximo 100 por página).

```powershell
curl -s -c cookies.txt -X POST http://localhost:5056/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"Admin123!"}'

# $ids = lista de Guid desde psql COPY o un script.
# Trocear de 50 en 50:
curl -s -b cookies.txt -X POST http://localhost:5056/api/ai/catalog/enrich-batch `
  -H "Content-Type: application/json" `
  -d '{"productIds":["..."],"reviewMode":"AutoBulk","force":false}'
```

`force: false` — reejecutar es barato (C08 salta por `SourceHash`). No mezclar con `Routed` (eso es C28).

## Verificación posterior al lote

Sigue sin ser C13. `ProfileReviewStatus.Approved = 2` (`Pending = 1`, `Rejected = 3`).

```powershell
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -c "SELECT COUNT(*) FROM public.""ProductAiProfiles"" WHERE ""ReviewStatus"" = 2;"
# esperar 1200

# Smoke del feed C12 (key de appsettings / .env.example):
curl -s -H "X-Index-Feed-Key: local-dev-index-feed-key-0123456789ab" `
  "http://localhost:5056/api/ai/index-feed/catalog"
```

La primera página debe traer upserts (`kind: upsert`), `pageSize: 50`, `hasMore: true` y un `aggregateHash` de 64 hex.

## Tiempo estimado

C09 extrae **un producto por llamada LLM**, concurrencia 8 (`JPV_RAG_LLM_CONCURRENCY`). 50 productos/lote ≈ 7 oleadas. A ~1–3 s/oleada → ~10–20 s/lote; 24 lotes **secuenciales** (un HTTP .NET espera al batch) → **15–40 min** de reloj. Techo: `EnrichTimeoutMs = 120_000` por lote; si el proveedor se ahoga, acercarse a 24×2 min.

## Coste estimado

Default `openai/gpt-4o`. Prompt `enrichment/v1` + vocabularios ~1,5–2,5 k tokens in; salida JSON ~150–250 out; hasta 1 reintento de parseo. Orden de magnitud **1.200–1.500 completions** → **≈ 6–12 USD** (tarifas gpt-4o ~2,50 USD/1M in y ~10 USD/1M out, agosto 2026). Si el modelo configurado es `gpt-4o-mini`, recalcular: entonces &lt; 1 USD. Esta cifra es estimación a priori; no hace falta pegar factura.

## Qué no hacer

- No correrlo con `STUB_MODE=true` si el objetivo es C14/C24.
- No marcarlo `ReviewOrigin = Human`.
- No tomarlo como criterio de merge de C12.
- No regenerar `ai-service/openapi.json` ni llamar a `POST /v1/index/sync` (sigue siendo el stub de C13).
