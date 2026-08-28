# QA — C15 `add-dotnet-ai-search-endpoint`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-28 · **Rama:** `c15-add-dotnet-ai-search-endpoint` · **Commits de artefactos (HEAD, sin commit de implementación aún):** `52394b2` (HU + ticket + §0 del plan), `f733412` (proposal, design, specs, tasks)
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| .NET | 10.0.303 (`net10.0`) |
| Base de datos de integración | Testcontainers `postgres:15`, arrancado por `ApiWebApplicationFactory` |
| Docker | Disponible durante toda la pasada (`testcontainers-ryuk` levantado) |
| Proveedor EF | `Npgsql.EntityFrameworkCore.PostgreSQL` 10.0.0 |
| Servicio de IA | **No se levanta.** Sin gateway configurado el cliente falla y la petición degrada — que es justamente el camino que interesa probar contra base de datos real |
| Contrato Python | `ai-service/openapi.json` — **no se toca**. `git diff` vacío |
| `ai-service/` | **No se ejecuta** `uv run pytest`: C15 no cruza a Python. Ver §4 |
| Migraciones EF | **Ninguna nueva.** `git status` de `Migrations/` vacío |

---

## 1. Suite automática de .NET

> **Aquí el recuento no es fiable**, y CLAUDE.md lo dice explícitamente: la suite parte de decenas de fallos preexistentes y una parte de ellos es dependiente del orden, así que dos ejecuciones del mismo código discrepan. La comparación válida es **nombre a nombre**.

| Ejecución | Resultado |
|---|---|
| **Baseline** — suite completa sobre el árbol previo a la implementación | **829 tests · 775 passed · 54 failed** · 20 m 34 s |
| **Después** — suite completa con C15 implementado | **874 tests · 826 passed · 48 failed** · 20 m 50 s |
| Alcance C15, unitarios (`AssistedSearchServiceTests`) | **32 passed, 0 failed**, 1 s |
| Alcance C15, integración (`AiSearchControllerTests`) | **15 passed, 0 failed**, 52 s |
| `openspec validate --all --strict` | **43 passed, 0 failed** |

Comandos:

```powershell
# Baseline, medido antes de tocar código (tarea 1.2)
dotnet test src/JoiabagurPV.Tests/JoiabagurPV.Tests.csproj --logger "trx;LogFileName=baseline.trx"

# Después
dotnet test src/JoiabagurPV.Tests/JoiabagurPV.Tests.csproj --logger "trx;LogFileName=after.trx"

# Alcance
dotnet test ... --filter "FullyQualifiedName~AssistedSearchServiceTests"
dotnet test ... --filter "FullyQualifiedName~AiSearchControllerTests"

openspec validate --all --strict
```

El baseline no necesitó `git stash push -u`: en ese momento el árbol de trabajo era idéntico a `HEAD` —todo lo hecho hasta entonces era documentación ya commiteada— así que la propia pasada **es** la línea base. Los nombres se extrajeron de los `.trx`, no del stdout, que llega truncado.

### 1.1. Comparación nombre a nombre (tarea 8.8)

**Regresiones reales: cero.** El delta cae íntegramente dentro de `InventoryIntegrationTests`, más un test de `ReturnsControllerTests` que pasó a verde.

| Dirección | Nº | Clase |
|---|---|---|
| Fallan ahora y no antes | 4 | `InventoryIntegrationTests` (`ExcelImport_NegativeQuantityWithSufficientStock…`, `ExcelImport_ValidFile…`, `Operator_AccessCentralizedInventory…`, `ProductCatalog_AsAdmin…`) |
| Fallaban antes y ahora no | 10 | 9 de `InventoryIntegrationTests` + `ReturnsControllerTests.GetEligibleSales_WithValidProductAndPOS_ReturnsEligibleSales` |
| Ningún test de C15 en la lista de fallos | — | `grep -iE "AssistedSearch\|AiSearchController"` sobre `after-failures.txt` → vacío |

**No se dio por supuesto que fuera inestabilidad.** Se comprobó ejecutando esa clase **en aislamiento** sobre el código actual:

| Ejecución | Fallos en `InventoryIntegrationTests` | Conjunto de nombres |
|---|---|---|
| Baseline (suite completa) | 10 | A |
| Después (suite completa) | 4 | B |
| **Aislada, código actual** | **7** | **C — distinto de A y de B** |

Ninguno de los 4 «nuevos» fallos aparece al ejecutar la clase sola, y `Operator_ViewStock_ForAssignedPOS_ShouldSucceed` —que «dejó de fallar» en la suite— sí falla en aislamiento. Tres ejecuciones, tres conjuntos distintos. Es la inestabilidad por orden que documenta *Estado de la suite: fallos conocidos* en [testing-backend.md](../../../Documentos/testing-backend.md), y C15 no toca ningún servicio, repositorio ni tabla que esa clase use.

### 1.2. Desglose de tests nuevos

| Fichero | Nº | Qué cubre |
|---|---|---|
| `UnitTests/Application/AssistedSearchServiceTests.cs` | **32** | Hidratación autoritativa y deriva de SKU; ventana máxima en una llamada; página corta sin segunda llamada; orden de recuperación y truncado; abstención vs página vacía tras hidratar; stock cero conservado; una sola consulta de hidratación; degradación por los tres tipos de excepción; términos OR y ruido de un carácter; flag por POS y `Disabled`; telemetría con la lista mostrada; `RetrievalMs` en todos los orígenes; telemetría que falla; caché con POS en la clave, normalización y consulta no en claro; embudo; consulta fuera de logs de producción; permisos de operador, admin y POS inactivo; ámbito por token |
| `IntegrationTests/AiSearchControllerTests.cs` | **15** | Contra PostgreSQL real: degradación efectiva, coincidencia por término, tolerancia a caracteres reservados, búsqueda por SKU, precio y stock del catálogo, stock cero conservado, descarte de lo no asignado / inactivo, cantidad del POS y no la suma, evento registrado, 400 sin POS y con consulta en blanco, 403 de operador, admin sobre cualquier POS activo, POS inactivo, 401 anónimo |

**45 tests nuevos** (32 + 15 = 47 métodos ejecutados; 874 − 829 = 45 porque `[Theory]` con tres `InlineData` cuenta como tres y el desglose ya los incluye). Ningún test nuevo llama al servicio de IA, a un proveedor de embeddings ni a la red: el gateway es un doble en los unitarios y, en integración, simplemente no está configurado.

---

## 2. Escenarios de las specs, uno a uno

### `ai-assisted-search` (nueva, 12 requisitos, 38 escenarios)

| Requisito · escenario | Comprobación | Resultado |
|---|---|---|
| Single authenticated endpoint · A valid request is served | `Search_HydratesPriceAndStockFromDatabase_NotFromAiResponse` (integración y unitario) | ✅ |
| Single authenticated endpoint · An invalid request is rejected before any work is done | `Search_WithBlankQuery_ReturnsBadRequest` · `Search_WithoutPointOfSale_ReturnsBadRequest` | ✅ |
| Single authenticated endpoint · An unauthenticated request is refused | `Search_WhenUnauthenticated_Returns401` (cliente nuevo de la factoría) | ✅ |
| Scoped to one point of sale · A request without a point of sale is invalid | `Search_WithoutPointOfSale_ReturnsBadRequest` | ✅ |
| Scoped to one point of sale · An operator cannot search on a point of sale they are not assigned to | `Search_OperatorCannotChooseUnassignedPos` (unitario: 0 llamadas al gateway y 0 eventos; integración: 403) | ✅ |
| Scoped to one point of sale · An administrator may search on any active point of sale | `Search_AdminMayChooseAnyActivePos` (unitario e integración) | ✅ |
| Scoped to one point of sale · An inactive point of sale is refused for every role | `Search_WhenPointOfSaleInactive_IsRefused` | ✅ |
| Candidate window · One retrieval call per search | `Search_RequestsTheMaximumCandidateWindowInASingleCall` (`TopK == 20`, `Times.Once`) | ✅ |
| Candidate window · A short page does not trigger a second call | `Search_WhenPosCoverageIsLow_ReturnsFewerThanTopK_WithoutASecondCall` (60 candidatos → 3 supervivientes, `Times.Once`) | ✅ |
| Candidate window · The requested window is configured, not hard-coded | mismo test, la ventana sale de `AiSearchOptions`; `AiSearchRequest.OverRetrievalCount(20) == OverRetrievalCap` asertado en el propio test | ✅ |
| Backend is the authority · Price and stock come from the catalog | `Search_HydratesPriceAndStockFromDatabase_NotFromAiResponse` (48,00 € y 5 unidades desde la tabla; SKU del catálogo gana al del índice y la deriva se registra) | ✅ |
| Backend is the authority · A candidate no longer available at the point of sale is dropped | `Search_WhenCandidateNoLongerAssigned_DropsItAfterHydration` · `Search_DropsWhatThisPointOfSaleDoesNotCarry` (los tres motivos: otro POS, producto inactivo, asignación inactiva) | ✅ |
| Backend is the authority · A candidate with no stock is kept and marked | `Search_KeepsAssignedProductWithZeroStock` (unitario e integración) | ✅ |
| Backend is the authority · The quantity is the one at that point of sale | `Search_QuantityIsTheOneAtThatPointOfSale` (5 y no 104, con stock en dos POS) | ✅ |
| Backend is the authority · Hydration does not query per candidate | `Search_HydratesInASingleQuery` (60 candidatos, `Times.Once`) | ✅ |
| Results truncated in retrieval order · More survivors than the page size | `Search_PreservesRetrievalOrder_AndTruncatesToPageSize` (hidratación devuelve orden invertido; salen los tres primeros del retriever) | ✅ |
| Failing AI degrades · An unavailable AI service falls back | `Search_WhenAiUnavailable_FallsBackToLexicalSearch` `[Theory]` sobre los tres tipos de excepción | ✅ |
| Failing AI degrades · A credential failure degrades and is logged | `Search_WhenCredentialsRejected_LogsAtErrorLevel` | ✅ |
| Degraded searcher · A natural-language query returns results | `Fallback_MatchesAnyQueryTerm_NotTheWholeString` (unitario e **integración contra PostgreSQL**: «quiero un collar bonito para un regalo» encuentra `SKU-NECK-1`) | ✅ |
| Degraded searcher · The degraded searcher is scoped to the point of sale | `Fallback_IsScopedToTheSearchPointOfSale` · `Search_DropsWhatThisPointOfSaleDoesNotCarry` | ✅ |
| Degraded searcher · The pre-existing catalog search is untouched | `git diff` vacío en `ProductService.cs` y `ProductsController.cs` (§4) | ✅ |
| Switched off per point of sale · A disabled point of sale never reaches the AI service | `Search_WhenFeatureFlagOff_UsesLegacySearch` (`Times.Never` sobre el gateway) · `Search_WhenFeatureFlagOn_ForThatPointOfSaleOnly_UsesAssistedPath` | ✅ |
| Switched off per point of sale · The disabled path is distinguishable from the degraded one | `Search_WhenFeatureFlagOff_RecordsOriginDisabled` | ✅ |
| Three empty outcomes · Abstention is reported as such | `Search_WhenRetrieverAbstains_ReportsLowConfidenceAndStaysAvailable` | ✅ |
| Three empty outcomes · An empty page after hydration is not abstention | `Search_WhenNothingSurvivesHydration_IsNotReportedAsAbstention` (`LowConfidence` false, `CandidatesReturned` 1, `SurvivedHydration` 0) | ✅ |
| Three empty outcomes · A degraded empty page is neither | `Search_WhenAiUnavailable_FallsBackToLexicalSearch` con `LexicalReturns()` vacío → `AiAvailable` false | ✅ |
| Every search recorded · The displayed list is what gets recorded | `Search_RecordsTheSearch_WithTheDisplayedListNotTheCandidateWindow` (30 candidatos, 10 registrados) | ✅ |
| Every search recorded · The recorded duration excludes the recording | mismo test: `TotalMs` no nulo, capturado antes de la llamada (`ElapsedMs` invocado antes de `RecordAsync` en el servicio) | ⚠️ parcial — ver §8.3 |
| Every search recorded · A telemetry failure does not fail the search | `Search_WhenTelemetryFails_StillReturnsResults` | ✅ |
| Every search recorded · An episode identifier always exists | cubierto por la capability de telemetría (C04), que genera el identificador cuando el llamante no lo aporta; C15 sólo lo propaga | ⚠️ delegado — ver §8.3 |
| Cost is bounded · A repeated query does not pay for a second embedding | `Search_RepeatedQueryHitsCandidateCache_WithoutSecondEmbedding` (`Times.Once` gateway) | ✅ |
| Cost is bounded · A cache hit still hydrates | mismo test: `HydrateAsync` `Times.Exactly(2)` | ✅ |
| Cost is bounded · The cache key separates points of sale | `Search_CacheKeyIncludesPointOfSale` | ✅ |
| Cost is bounded · The rate policy is partitioned by user | inspección de código; la política usa `ClaimTypes.NameIdentifier` | ⚠️ **sin test** — ver §8.4 |
| Cost is bounded · Exceeding the rate policy is not reported as AI unavailability | inspección de código; `RejectionStatusCode = 429` global | ⚠️ **sin test** — ver §8.4 |
| Funnel observable · The funnel is emitted per search | `Search_EmitsTheFunnelPerSearch` (nivel Information, `PointOfSaleId`, `Candidates` 30, `Survived` 12, `Displayed` 10, `TraceId`) | ✅ |
| Funnel observable · No new columns are added | `git status` de `Migrations/` vacío (§4) | ✅ |
| Funnel observable · The query stays out of production logs | `Search_QueryStaysOutOfProductionLogs` (ausente en ≥ Information, presente en Debug) | ✅ |

### `ai-search-telemetry` (delta MODIFIED, 4 escenarios)

| Requisito · escenario | Comprobación | Resultado |
|---|---|---|
| Degraded searches are recorded and distinguishable · A degraded search is recorded with its own origin | `Search_WhenAiUnavailable_FallsBackToLexicalSearch` asserta `Origin == LexicalFallback` | ✅ |
| ídem · A search with assisted retrieval switched off is recorded as disabled | `Search_WhenFeatureFlagOff_RecordsOriginDisabled` | ✅ |
| ídem · The origins are separable in analysis | `SearchOrigin` con tres valores explícitos y estables (1/2/3); los dos previos conservan su número | ✅ |
| ídem · Adding the third origin needs no schema change | `git status` de `Migrations/` vacío; la columna es entera y no cambia de tipo | ✅ |

**Totales:** 38 (`ai-assisted-search`) + 4 (`ai-search-telemetry`) = **42 escenarios**. **38 con test directo**, 2 verificados por diff, **2 sin test** (§8.4) y 2 parciales o delegados (§8.3).

---

## 3. Nombres exigidos por `tasks.md` / ticket

| Nombre de la ficha | Fichero | Estado |
|---|---|---|
| `Search_HydratesPriceAndStockFromDatabase_NotFromAiResponse` | unitario + integración | ✅ |
| `Search_WhenCandidateNoLongerAssigned_DropsItAfterHydration` | unitario | ✅ |
| `Search_RequestsTheMaximumCandidateWindowInASingleCall` | unitario | ✅ |
| `Search_WhenPosCoverageIsLow_ReturnsFewerThanTopK_WithoutASecondCall` | unitario | ✅ |
| `Search_KeepsAssignedProductWithZeroStock` | unitario + integración | ✅ |
| `Search_HydratesInASingleQuery` | unitario | ✅ |
| `Search_WhenAiUnavailable_FallsBackToLexicalSearch` | unitario (`[Theory]`, 3 casos) + integración | ✅ |
| `Fallback_MatchesAnyQueryTerm_NotTheWholeString` | unitario + integración | ✅ |
| `Fallback_IsScopedToTheSearchPointOfSale` | unitario | ✅ |
| `Search_WhenFeatureFlagOff_UsesLegacySearch` | unitario | ✅ |
| `Search_WhenFeatureFlagOff_RecordsOriginDisabled` | unitario | ✅ |
| `Search_RepeatedQueryHitsCandidateCache_WithoutSecondEmbedding` | unitario | ✅ |
| `Search_CacheKeyIncludesPointOfSale` | unitario | ✅ |
| `Search_AdminMayChooseAnyActivePos` | unitario + integración | ✅ |
| `Search_OperatorCannotChooseUnassignedPos` | unitario + integración | ✅ |
| `Search_WhenTelemetryFails_StillReturnsResults` | unitario | ✅ |
| Integración con Testcontainers | `AiSearchControllerTests`, 15 tests | ✅ |

**Todos los nombres de la ficha existen y están en verde.** Extras no exigidos por la ficha: `Search_PreservesRetrievalOrder_AndTruncatesToPageSize`, `Search_WhenRetrieverAbstains_ReportsLowConfidenceAndStaysAvailable`, `Search_WhenNothingSurvivesHydration_IsNotReportedAsAbstention`, `Search_WhenCredentialsRejected_LogsAtErrorLevel`, `Fallback_DropsSingleCharacterNoise`, `Search_WhenFeatureFlagOn_ForThatPointOfSaleOnly_UsesAssistedPath`, `Search_RecordsTheSearch_WithTheDisplayedListNotTheCandidateWindow`, `Search_RecordsRetrievalDuration_OnEveryOrigin`, `Search_CacheKeyIgnoresTriviallyDifferentSpellings`, `Search_CacheKeyDoesNotCarryTheQueryInClear`, `Search_EmitsTheFunnelPerSearch`, `Search_QueryStaysOutOfProductionLogs`, `Search_WithoutPointOfSale_ReturnsBadRequest`, `Search_WhenPointOfSaleInactive_IsRefused`, `Search_SendsThePointOfSaleThroughTheScope_NotTheBody`, `Fallback_ToleratesReservedCharactersInTheQuery`, `Fallback_FindsByExactSku`, `Search_DropsWhatThisPointOfSaleDoesNotCarry`, `Search_QuantityIsTheOneAtThatPointOfSale`, `Search_RecordsTheSearchEvent`, `Search_WithBlankQuery_ReturnsBadRequest`, `Search_WhenUnauthenticated_Returns401`.

---

## 4. Alcance negativo (tarea 9.4)

```powershell
git status -s -- ai-service/ frontend/
git status -s -- backend/src/JoiabagurPV.Infrastructure/Data/Migrations/
git diff --stat backend/src/JoiabagurPV.Application/Interfaces/IAiGatewayClient.cs ai-service/openapi.json
git diff --stat backend/src/JoiabagurPV.Application/Services/ProductService.cs backend/src/JoiabagurPV.API/Controllers/ProductsController.cs
```

Todas las salidas **vacías**.

| Guardarraíl | Comprobación | Resultado |
|---|---|---|
| `ai-service/` sin tocar | `git status` vacío | ✅ |
| `ai-service/openapi.json` | `git diff` vacío | ✅ |
| `IAiGatewayClient` | `git diff` vacío | ✅ |
| `frontend/` | `git status` vacío | ✅ |
| **Sin migración EF** | `Migrations/` sin ficheros nuevos ni modificados | ✅ |
| **Sin índice nuevo** | ninguna llamada a `HasIndex`, ninguna columna generada | ✅ |
| `/api/v1/products/search` intacto | `git diff` vacío en `ProductService.cs` y `ProductsController.cs` | ✅ |
| `ai.query_log` | no se crea; la telemetría es `ProductSearchEvent` (C04) | ✅ |
| .NET no lee el esquema `ai` | el repositorio nuevo sólo usa `_context.Inventories`, `Products`, `PointOfSales`, `Collections`, `ProductPhotos` | ✅ |
| TODO/FIXME sin seguimiento | `grep` sobre los ficheros nuevos vacío | ✅ |

---

## 5. Decisiones de diseño, verificadas en código

| Decisión | Evidencia |
|---|---|
| **D1** · Ventana máxima en una llamada, sin repetición | `AssistedSearchService.RetrieveAsync` con `Math.Clamp(options.CandidateWindow, 1, AiSearchRequest.MaxTopK)`; no existe camino que emita una segunda llamada. `Search_RequestsTheMaximumCandidateWindowInASingleCall` y `Search_WhenPosCoverageIsLow_…` lo fijan |
| **D2** · Asignación decide, cantidad cero no | `AssistedSearchRepository.Carried` filtra `inventory.IsActive && inventory.Product.IsActive` y **no** filtra `Quantity`. `Search_KeepsAssignedProductWithZeroStock` y `Search_DropsWhatThisPointOfSaleDoesNotCarry` |
| **D3** · Buscador degradado propio, full-text en consulta | `SearchLexicalAsync` con `to_tsvector('spanish', …)` y `websearch_to_tsquery`, términos unidos por `OR`, orden por `Rank`. Sin índice, sin columna generada. Probado contra PostgreSQL real |
| **D4** · Flag en configuración y tercer origen | `AiSearchOptions.IsEnabledFor` vía `IOptionsMonitor`; `SearchOrigin.Disabled = 3`; sin migración |
| **D5** · Caché de candidatos y rate limit | `AssistedSearchCandidateCache` guarda `AiSearchResponse` (ids y scores), nunca precio ni stock; clave con `posId`, hasheada; `RateLimitPolicies.AiSearch` particionada por `ClaimTypes.NameIdentifier` |
| **D6** · Punto de venta obligatorio; admin elige | `AssistedSearchRequestValidator` exige `PointOfSaleId`; `AuthoriseAsync` comprueba actividad antes que permisos, de modo que un POS cerrado se rechaza para todos los roles |
| **D7** · Embudo en log, no en columnas | `LogFunnel` a nivel Information con `Candidates`/`Survived`/`Displayed`/`TraceId`; `Migrations/` intacto |

---

## 6. Documentación de contexto (tarea 9.2)

| Documento | Qué se alineó |
|---|---|
| [proyecto-final-plan-changes-openspec.md](../../../Documentos/Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) | Entrada §0 de 2026-08-28; ficha C15 corregida en el sitio; fila `C15 ‖ C34` de §5; obligación **B6** heredada por C16 |
| `Documentos/epicas.md` (EP14) | Bloque C15 + enlace a HU-AIENG-015 |
| [HU-AIENG-015](../../../Documentos/Historias/AI-Eng/HU-AIENG-015.md) | Creada antes del apply, con las siete decisiones cerradas |
| [ticket.md](ticket.md) / [tasks.md](tasks.md) | 42/43 tareas marcadas; la restante es verificación posterior (§9) |

---

## 7. OpenSpec

```powershell
openspec validate --all --strict
openspec status --change add-dotnet-ai-search-endpoint
```

**43 passed, 0 failed.** Ejecutado en la forma `--all --strict` y no en la de un solo change, porque este change lleva un `## MODIFIED` sobre una spec ya activa: validar sólo el change dejaría sin comprobar la spec viva en la que va a sincronizarse.

`openspec status`: 4/4 artefactos completos (proposal, design, specs, tasks).

`/opsx:verify` **no se ha ejecutado todavía** en este change.

---

## 8. Incidencias y huecos de esta pasada

### 8.1. El spike de texto completo cambió el diseño

La tarea 1.1 confirmó que el proveedor traduce ambas construcciones a SQL servidor —sin evaluación en cliente y sin materializar el catálogo— así que la caída prevista en D3 no hizo falta. Pero destapó algo que el diseño no había anticipado y que se incorporó a D3: existen **dos** conversiones de texto a consulta, y la estricta **lanza excepción** ante un carácter reservado. Los términos vienen de texto que escribe el operador, así que usar la estricta convertiría el único camino en pie cuando la IA cae en un error del servidor. Se usa la tolerante, en las dos posiciones —coincidencia y ordenación—, y `Fallback_ToleratesReservedCharactersInTheQuery` lo fija con la consulta `anillo & plata | (oro`.

El SQL verificado quedó recogido en `design.md`, sección *Open Questions*.

### 8.2. Tres correcciones durante el apply

| Qué | Dónde se corrigió |
|---|---|
| **`RetrievalMs` quedaba nulo en el camino degradado**, incumpliendo el requisito de la propia spec de que la duración mida la obtención de candidatos *sea cual sea el origen*. Sin eso los orígenes dejan de ser comparables, que es lo único para lo que existe esa columna | **Código.** El camino no asistido se cronometra igual. `Search_RecordsRetrievalDuration_OnEveryOrigin` |
| La spec decía que la vía desactivada usa **«el buscador de catálogo preexistente»**. Ése suma stock de todos los puntos de venta y no está acotado a uno: rompería la garantía del propio endpoint, y sólo en las tiendas con el flag apagado — la inconsistencia más difícil de notar | **Spec.** Ahora exige el mismo buscador no asistido que usa la vía degradada, con el motivo escrito |
| Un test exigía filtrar *stopwords* en C#. No procede: la configuración `spanish` de PostgreSQL ya las elimina, y una lista paralela derivaría de la que la base aplica de verdad | **Test.** Y se documentó la delegación en `Tokenize`. Se dejó `Fallback_DropsSingleCharacterNoise`, que sí es cosa nuestra |

### 8.3. Dos escenarios cubiertos de forma indirecta

- **«The recorded duration excludes the recording».** El servicio captura `TotalMs` antes de llamar a la telemetría, y el test comprueba que `TotalMs` no es nulo — pero no aísla el coste de la escritura, que con un doble es de microsegundos. La garantía es estructural (orden de las sentencias), no medida.
- **«An episode identifier always exists».** C15 propaga el identificador que llega y no genera ninguno: generarlo es responsabilidad de la capability de telemetría, que ya lo tiene probado en C04. No se duplicó el test.

### 8.4. Dos escenarios **sin test** — la política de peticiones

`The rate policy is partitioned by user` y `Exceeding the rate policy is not reported as AI unavailability` están verificados **por inspección de código**, no por test:

- La partición usa `ClaimTypes.NameIdentifier` con caída a la dirección de red, y `RejectionStatusCode` es 429 global del `RateLimiter`.
- Probarlo requiere emitir más peticiones que el límite, y el entorno de test fija el límite en **10.000** —igual que hace `LoginRateLimit`— precisamente para que la política no interfiera con el resto de la suite. Un test real exigiría una configuración de host distinta.

Es un hueco reconocido, no un olvido. `RateLimitingTests` ya existe en el repositorio y sería el sitio natural si se decide cubrirlo.

### 8.5. `CreateClient()` en el constructor es carga estructural

La primera pasada de integración falló las 15 con `No tables found. Ensure your target database has at least one non-ignored table to reset`. El motivo: `ResetDatabaseAsync()` corre en `InitializeAsync`, **antes** de que ninguna petición haya construido el host — y construir el host es lo que aplica las migraciones. Las clases existentes lo evitan porque llaman a `factory.CreateClient()` en el constructor, cosa que parece un campo sin usar.

**Corrección:** el constructor crea un cliente anónimo, con el motivo escrito al lado para que nadie lo retire por parecer muerto. Es además el cliente que usa `Search_WhenUnauthenticated_Returns401`, que necesita uno sin cookies.

### 8.6. El spike se ejecutó como test temporal y se retiró

La verificación de traducción se hizo con dos tests que fuerzan un fallo para volcar el SQL generado (`ToQueryString()` sobre un contexto sin conexión). Se eliminaron tras registrar el resultado en `design.md`. No quedan en el árbol.

---

## 9. Fuera de esta pasada (no DoD)

- **Tarea 9.3 · verificación manual con el mundo sembrado.** Búsqueda real desde `op-ciutadella` (cobertura 0,78) y `op-fornells` (0,22) con el índice local poblado, comprobando que la segunda devuelve página corta y que el embudo lo refleja. Requiere `jbg-ai` levantado y los datos de C10 en la base local. La ficha la declara **fuera del DoD de merge**; es la que enseñaría el corte de recall en vivo.
- `/opsx:verify` sobre este change.
- Panel del operador (C16) y despliegue del servicio (C17).
- Rama léxica del híbrido, RRF y sinónimos (C20/C21); prefiltro por punto de venta (C22).
- Arreglar el singleton del cliente de embeddings en `ai-service` — **deuda anotada** para C21/C22, que ya trabajan en esa zona. C15 no cruza a Python.
- Índice invertido sobre el catálogo transaccional: sólo tendrá sentido si el catálogo crece un orden de magnitud.

---

## Veredicto

**Sin regresiones.** Comparación nombre a nombre contra el baseline: **cero** tests rotos por este change; el delta cae íntegramente en una clase cuya inestabilidad por orden se verificó ejecutándola en aislamiento y obteniendo un tercer conjunto de fallos distinto. Alcance C15: **32 + 15 = 47 métodos, 0 fallos**. `openspec validate --all --strict` **43/0**. Diffs vacíos en `ai-service/`, `openapi.json`, `IAiGatewayClient`, `frontend/`, migraciones y buscador preexistente. **42/43 tareas**; 38 de 42 escenarios con test directo.

**Dos escenarios de la política de peticiones quedan sin test** por la razón escrita en §8.4, y la verificación manual con el mundo sembrado sigue pendiente. Con eso declarado, listo para `/opsx:verify` y archivado.
