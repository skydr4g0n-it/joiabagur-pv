# Runbook C12 — AutoBulk del catálogo (1.200 perfiles)

Procedimiento, no acta. **No se ejecuta en el merge de C12.** Es la puerta de un C13 *útil*: sin 1.200 `Approved`, el primer `POST /v1/index/sync` deja `ai.product_document` a 0 (fallo mudo de S11).

## Para qué

Poblar `ProductAiProfile` de los 1.200 productos ingeridos con `reviewMode: AutoBulk` y `force: false`, para que `GET /api/ai/index-feed/catalog` emita upserts y C13 tenga algo que indexar.

## Quién y cuándo

Una persona, en local (y más adelante en demo), **después de archivar C12 y antes del apply de C13**. No es criterio de merge de este change.

## Condiciones (todas obligatorias)

API .NET en `http://localhost:5056` (`dotnet run` en `backend/src/JoiabagurPV.API`, perfil `http`). Postgres publicado en `:5433`. `jbg-ai` publicado en `:8001`.

Compose fija `STUB_MODE=true` y **no** inyecta `JPV_RAG_LLM_*`. Hay que **recrear** el contenedor. Descomentar `JPV_RAG_LLM_API_KEY` en `backend/.env` (no usar `env_file: .env` en el servicio: metería la clave de generate C06b).

### Modelo y concurrencia de *esta* corrida

Los defaults de código **no se cambian**: `openai/gpt-4o` y `JPV_RAG_LLM_CONCURRENCY=8`. Esta tabla elige el override del contenedor según el TPM de la cuenta OpenAI (tier 1 de `gpt-4o` = 30.000 TPM aborta el lote entero).

| TPM observado de `gpt-4o` | Override en el contenedor |
|---|---|
| ≥ ~80.000 | `JPV_RAG_LLM_MODEL=openai/gpt-4o`, `JPV_RAG_LLM_CONCURRENCY=8` |
| ~30.000 (tier 1) | `JPV_RAG_LLM_MODEL=openai/gpt-4o-mini`, `JPV_RAG_LLM_CONCURRENCY=2` |
| desconocido | un lote de 5; si 429, bajar a mini / conc. 2 |

`gpt-4o-mini` es el override de **este** AutoBulk local, no el default del servicio (C30 assist sigue apuntando a `gpt-4o`).

```powershell
# Desde backend/, con JPV_RAG_LLM_API_KEY ya en el entorno (leída de .env, no echo).
docker rm -f jpv-pv-jbg-ai 2>$null
docker compose run -d --name jpv-pv-jbg-ai --service-ports --use-aliases `
  -e STUB_MODE=false `
  -e JPV_RAG_LLM_API_KEY=$env:JPV_RAG_LLM_API_KEY `
  -e JPV_RAG_LLM_MODEL=openai/gpt-4o-mini `
  -e JPV_RAG_LLM_CONCURRENCY=2 `
  jbg-ai
```

```powershell
# 1) Productos ingeridos
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -c "SELECT COUNT(*) FROM public.""Products"";"
# esperar 1200

# 2) Perfiles (antes deben ser 0; después Approved = 1200)
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -c "SELECT ""ReviewStatus"", COUNT(*) FROM public.""ProductAiProfiles"" GROUP BY 1;"

# 3) jbg-ai NO está en stub; modelo y conc. son los del override
docker exec jpv-pv-jbg-ai printenv STUB_MODE
docker exec jpv-pv-jbg-ai printenv JPV_RAG_LLM_MODEL
docker exec jpv-pv-jbg-ai printenv JPV_RAG_LLM_CONCURRENCY
# STUB_MODE debe ser false. No imprimir la API key; sí su longitud:
docker exec jpv-pv-jbg-ai sh -c "printenv JPV_RAG_LLM_API_KEY | wc -c"

# 4) Salud
curl.exe -s http://localhost:8001/health
curl.exe -s http://localhost:5056/api/health
```

Un 503 de `enrich-batch` con mensaje *AI service is unavailable* no significa que el contenedor esté caído: `jbg-ai` contestó 5xx, casi siempre `RateLimitError` (TPM). Ver `docker logs jpv-pv-jbg-ai`. El cliente ahora reintenta 429 con backoff; un 429 que sobreviva al retry en un solo SKU **no** debe tumbar el lote entero.

## Ejecución

Lote 50 = `AiEnrichRequest.MaxBatchSize`. 1.200 / 50 = **24 llamadas**. Login admin (`admin` / `Admin123!` según `backend/api-tests/README.md`); cookie `access_token`. IDs desde SQL, no desde `GET /api/products` (máximo 100 por página).

`reviewMode` acepta `"AutoBulk"` (nombre del miembro) y `2`. UTF-8 **sin BOM**. `--max-time 150` (techo de servidor `EnrichTimeoutMs = 120_000`).

```powershell
$cookie = Join-Path $env:TEMP "jpv-c12-cookies.txt"
$idsFile = Join-Path $env:TEMP "jpv-c12-product-ids.txt"
$utf8 = New-Object System.Text.UTF8Encoding $false

curl.exe -s -c $cookie -X POST http://localhost:5056/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"Admin123!"}' | Out-Null

docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -t -A `
  -c "SELECT ""Id"" FROM public.""Products"" ORDER BY ""Id"";" |
  Set-Content -Path $idsFile -Encoding ascii
$ids = @(Get-Content $idsFile | Where-Object { $_.Trim() -ne "" })
if ($ids.Count -ne 1200) { throw "Se esperaban 1200 IDs, hay $($ids.Count)" }

$batchSize = 50
for ($start = 0; $start -lt $ids.Count; $start += $batchSize) {
  $n = [int]($start / $batchSize) + 1
  $end = [Math]::Min($start + $batchSize - 1, $ids.Count - 1)
  $chunk = @($ids[$start..$end])
  $bodyFile = Join-Path $env:TEMP ("jpv-c12-batch-{0}.json" -f $n)
  $body = [ordered]@{ productIds = $chunk; reviewMode = "AutoBulk"; force = $false }
  [System.IO.File]::WriteAllText($bodyFile, ($body | ConvertTo-Json -Compress -Depth 5), $utf8)

  $raw = (curl.exe -s -w "HTTP_CODE:%{http_code}" -b $cookie `
    -X POST http://localhost:5056/api/ai/catalog/enrich-batch `
    -H "Content-Type: application/json" `
    --data-binary "@$bodyFile" --max-time 150 | Out-String)
  $code = if ($raw -match "HTTP_CODE:(\d+)") { $Matches[1] } else { "?" }
  $json = ($raw -replace "HTTP_CODE:\d+\s*$", "").Trim()
  if ($code -eq "401") { throw "lote $n : 401 (re-login)" }
  if ($code -ne "200") { throw "lote $n : HTTP $code $json" }
  $resp = $json | ConvertFrom-Json
  Write-Host ("LOTE {0}/24 HTTP=200 requested={1} enriched={2} skippedUnchanged={3} failed={4}" -f `
    $n, $resp.requested, $resp.enriched, $resp.skippedUnchanged, $resp.failed)
}
```

`force: false` — reejecutar es barato (C08 salta por `SourceHash`). No mezclar con `Routed` (eso es C28). Si un lote queda a medias (`failed` > 0), repetir el mismo rango: los ya escritos salen en `skippedUnchanged`.

## Verificación posterior al lote

Sigue sin ser C13. `ProfileReviewStatus.Approved = 2` (`Pending = 1`, `Rejected = 3`). `ReviewOrigin.AutoBulk = 1` (no `Human = 2`).

```powershell
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -c "SELECT COUNT(*) FROM public.""ProductAiProfiles"" WHERE ""ReviewStatus"" = 2;"
# esperar 1200

docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -c "SELECT ""ReviewStatus"", ""ReviewOrigin"", COUNT(*) FROM public.""ProductAiProfiles"" GROUP BY 1, 2;"
# esperar ReviewStatus=2, ReviewOrigin=1, count=1200

curl.exe -s -H "X-Index-Feed-Key: local-dev-index-feed-key-0123456789ab" `
  "http://localhost:5056/api/ai/index-feed/catalog"
```

La primera página debe traer upserts (`kind: upsert`), `pageSize: 50`, `hasMore: true` y un `aggregateHash` de 64 hex.

## Tiempo estimado

C09 extrae **un producto por llamada LLM**. Defaults de código: concurrencia 8, `gpt-4o` → ~10–20 s/lote, 24 lotes **15–40 min**, si el TPM lo aguanta.

Corrida local medida (agosto 2026, `gpt-4o-mini`, conc. 2, 30.000 TPM de `gpt-4o`): **~27–30 s/lote, ~12–15 min** de reloj. Techo: `EnrichTimeoutMs = 120_000` por lote. No bajar la concurrencia a 1 en lotes de 50: se acerca a ese techo.

## Coste estimado

Default de código `openai/gpt-4o`. Prompt `enrichment/v1` + vocabularios ~1,5–2,5 k tokens in; salida JSON ~150–250 out; hasta 1 reintento de parseo más backoff de 429. Orden de magnitud **1.200–1.500 completions** → **≈ 6–12 USD** con `gpt-4o`. Con el override `gpt-4o-mini` de esta corrida local: **&lt; 1 USD**. Estimación a priori; no hace falta pegar factura.

## Qué no hacer

- No correrlo con `STUB_MODE=true` si el objetivo es C14/C24.
- No marcarlo `ReviewOrigin = Human`.
- No tomarlo como criterio de merge de C12.
- No regenerar `ai-service/openapi.json` ni llamar a `POST /v1/index/sync` (sigue siendo el stub de C13).
- No bajar en código `DEFAULT_RAG_LLM_MODEL` ni `DEFAULT_RAG_LLM_CONCURRENCY`: el override es de contenedor / `.env` para *esta* pasada.
- No imprimir cookies ni JWT en el log.
