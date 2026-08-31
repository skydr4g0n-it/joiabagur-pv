# C18a — Verificación

**Fecha:** 2026-08-31 · **Rama:** `c18a-add-family-suggestion-and-approval` desde `ai-eng` en `f5212a7`

---

## 1. Suites, comparadas por nombre y no por recuento

### `ai-service`

| | Fallos | Pasan | Total |
|---|---|---|---|
| Baseline (antes de tocar nada) | 2 | 356 | 358 |
| Tras C18a | **2** | 436 | 438 |

Los dos son **los mismos nombres**: `tests/retrieval/test_orchestrator.py::test_malformed_exclusions_are_ignored` y `::test_trace_id_appears_in_stage_logs`. **Sin regresión.** 80 tests nuevos.

### Backend

| | Fallos | Pasan | Total |
|---|---|---|---|
| Baseline | 47 | 850 | 897 |
| Tras C18a | 50 | 857 | **907** |

**El recuento no dice nada aquí, y compararlo habría sido el error.** Diferencia por nombres: seis fallos nuevos y tres que dejan de fallar, **los nueve en `InventoryIntegrationTests`**. Ejecutada esa clase en aislamiento falla **ocho**, con nombres distintos otra vez — `AssignProduct_WithValidProduct_ShouldSucceed` y `EndToEnd_AssignAdjustView_Workflow` aparecen sólo ahí.

Es la dependencia de orden que `CLAUDE.md` advierte (*«dos ejecuciones de código idéntico discrepan»*), agitada porque la clase de test nueva entra en la misma colección y cambia el orden de ejecución. **Ninguna regresión es de C18a**, y los diez tests nuevos pasan.

## 2. Puertas del proyecto

- `openspec validate --all --strict` → **46 passed, 0 failed**
- `dotnet build JoiabagurPV.sln` → sin errores
- `uv run pytest` → 2 failed / 436 passed, los del baseline
- `test_openapi_snapshot_is_stable` → **en rojo antes de regenerar** (la frontera se movió de verdad) y en verde después
- **Sin migración** de EF Core ni de Alembic — verificado explícitamente

## 3. Lo que se ejecutó sobre datos reales

Por el camino completo `.NET → jbg-ai`, con respaldo previo (`pre-c18a.dump`, 12 MB):

| | |
|---|---|
| Familias / miembros creados | **156 / 486**, cero conflictos |
| `Origin = AiApproved` con aprobador e instante | 156 / 156 |
| Entradas retiradas del índice | **32**, con `ReviewStatus = Rejected` y **las 32 siguen `IsActive`** |
| Sincronización incremental | `upserted 486 · deleted 32 · skipped 0 · failed 0` |
| Índice final | 1.168 documentos · 486 con `family_id` · 0 sin embedding |
| `embedding_version` | sin cambios: `openai/text-embedding-3-small:1536:source-text/v1` |

## 4. Lo que este change **no** deja hecho

- **Sin interfaz.** La pantalla de revisión es C18b, y sin ella la cola de 15 miembros marcados, 4 grupos rechazados y 37 productos excluidos sólo se lee en el informe.
- **Un rechazo no se recuerda.** Al repetir `suggest`, una propuesta descartada reaparece. Es el precio de no persistir propuestas, y la lista de descartes es de C18b.
- **La alerta de huérfanos no existe.** Necesita familias ya creadas; ahora que existen, C18b puede construirla.
- **Las lagunas del vocabulario de enriquecimiento** que el informe destapa quedan anotadas en el §0 del plan como **un solo change propuesto**, `fix-enrichment-vocabulary-gaps`: ampliar `piece_type.terms` y decirle al prompt que el catálogo contiene cosas que no son joyería. Al costearlo aparecieron dos correcciones a lo que este informe decía — el problema afecta a **once** productos y no a treinta y siete, porque la limpieza de C18a se llevó los demás; y la salida «no es una pieza» **ya existe** en el prompt (*«o null»*), de modo que lo que falta es advertir al modelo, no ampliar el contrato. La escala métrica en las tallas queda **descartada**: `Cadena Barbara 40/42/45 cm` son tres cadenas de longitud distinta, no variantes de una pieza.

## 5. Dos obstáculos de entorno, ninguno del producto

Ambos son de desarrollo local en Windows y **no tocan el repositorio**, pero conviene que estén escritos porque cuestan una tarde si aparecen sin aviso.

**Uvicorn instala el `ProactorEventLoop`**, y psycopg no puede usarlo. La ruta real contra base de datos falla con `Psycopg cannot use the 'ProactorEventLoop'` y el `/health` reporta `database: unavailable` sin más pistas. Se resuelve cediendo el control del bucle (`uvicorn.Config(..., loop="none")` dentro de un `asyncio.run` con `WindowsSelectorEventLoopPolicy`). En producción el servicio corre en un contenedor Linux y no aplica.

**`litellm` verifica TLS contra `certifi`**, que no lleva el CA raíz corporativo de esta máquina. El síntoma engaña: `curl` con la misma clave devuelve **200** y `httpx` devuelve `CERTIFICATE_VERIFY_FAILED`, y el indexador lo traduce a `OpenAIException - Connection error` en `ai.sync_failure`. Se resuelve combinando el almacén de Windows con el bundle de `certifi` y apuntando `SSL_CERT_FILE` al resultado. **Es la hermana en tiempo de ejecución del `--system-certs` que el README ya documenta para `uv`**, y merece una línea allí.
