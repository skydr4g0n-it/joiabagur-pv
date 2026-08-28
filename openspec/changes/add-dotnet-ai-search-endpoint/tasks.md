## 1. Verificación previa y configuración

- [x] 1.1 Spike: comprobar que Npgsql 10 traduce `EF.Functions.ToTsVector("spanish", …)`, `WebSearchToTsQuery` y `ts_rank` a SQL sobre `public."Products"` sin materializar el catálogo en memoria. Dejar constancia del resultado en `design.md` (sección *Open Questions*). Si no traduce, aplicar la caída prevista en D3 sin cambiar contrato ni tests
- [x] 1.2 Medir el baseline de la suite backend con `git stash push -u` y guardar el **conjunto de nombres** que fallan, no el número — la comparación posterior se hace por nombres
- [x] 1.3 Opciones `AiSearchOptions` en `Application/Configuration/`: puntos de venta habilitados, activación por defecto, ventana de candidatos, tamaño de página por defecto y máximo, TTL y tamaño de la caché, límites de la política de peticiones
- [x] 1.4 Validación de las opciones al arranque: ventana dentro del máximo del contrato congelado, página máxima ≤ 50, TTL y límites positivos; el fallo nombra la clave de configuración
- [x] 1.5 Registrar las opciones con `IOptionsMonitor` para que la lista de puntos de venta se recargue sin redesplegar

## 2. Dominio y contratos internos

- [x] 2.1 Añadir `SearchOrigin.Disabled = 3` con la documentación de su significado en el propio enumerado
- [x] 2.2 DTO de petición en `Application/DTOs/Ai/`: consulta, punto de venta, tamaño de página, identificador de episodio opcional y filtros de catálogo
- [x] 2.3 DTO de resultado y de respuesta: identificadores, nombre, precio, cantidad en el punto de venta, marca de sin existencias, foto principal, colección, puntuación, razones de coincidencia, familia y variante; más identificador del evento, disponibilidad de la vía asistida, baja confianza, punto de venta y contadores del embudo
- [x] 2.4 Validador FluentValidation de la petición: consulta no vacía y acotada al máximo del contrato congelado, punto de venta obligatorio, tamaño de página entre 1 y el máximo configurado

## 3. Hidratación autoritativa

- [x] 3.1 Consulta conjunta única sobre `Product` ⋈ `Inventory` (del punto de venta) ⋈ foto principal ⋈ colección, filtrada por lista de identificadores candidatos
- [x] 3.2 Reglas de descarte: producto inactivo, sin fila de inventario en el punto de venta, o inventario inactivo. **Conservar** cantidad cero marcándola
- [x] 3.3 Resolución de las URL de foto en lote, sin una llamada por candidato
- [x] 3.4 Registrar la divergencia cuando el identificador de producto que reporta el índice no coincide con el del catálogo, tomando el del catálogo

## 4. Buscador degradado

- [x] 4.1 Método nuevo, en la zona de este change, que tokeniza la consulta y construye la búsqueda de texto completo en español con **semántica de alternativa**, ordenando por `ts_rank`
- [x] 4.2 Acotarlo a los productos con inventario activo en el punto de venta de la búsqueda
- [x] 4.3 Verificar que `ProductService.SearchProductsAsync` y `/api/v1/products/search` quedan sin modificar

## 5. Orquestación

- [x] 5.1 Servicio de aplicación que resuelve y valida el punto de venta, construye el `AiCallScope` y decide la vía: desactivada, caché, asistida o degradada
- [x] 5.2 Excepción de administrador acotada a puntos de venta activos, siguiendo el patrón `isAdmin` de `SalesService`; operador validado con `HasAccessAsync`
- [x] 5.3 Llamada única al gateway con la ventana configurada; cronometrar la obtención de candidatos
- [x] 5.4 Mapeo de los tres tipos de excepción del gateway a la vía degradada, con el fallo de configuración en nivel de error
- [x] 5.5 Hidratar, truncar a la página pedida preservando el orden recibido, y capturar el tiempo total **antes** de la telemetría
- [x] 5.6 Invocar `RecordSearchAsync` con la lista mostrada, el origen, el identificador de correlación, ambas duraciones y el identificador de episodio —generándolo si no viene—, tolerando el nulo
- [x] 5.7 Emitir el evento estructurado del embudo con identificador de correlación, punto de venta, candidatos recibidos, supervivientes y mostrados; la consulta del operador sólo en nivel de depuración

## 6. Caché y acotación del coste

- [x] 6.1 Caché de candidatos sobre el `IMemoryCache` ya registrado: guarda únicamente identificadores y puntuaciones, con TTL y tamaño acotados
- [x] 6.2 Clave compuesta que **incluye el punto de venta** desde el primer día, más consulta normalizada, filtros y ventana
- [x] 6.3 Rehidratar siempre en los aciertos de caché
- [x] 6.4 Política `AiSearchRateLimit` particionada por identificador de usuario, con límite alto en entorno de test como hace `LoginRateLimit`

## 7. Endpoint

- [x] 7.1 `AiSearchController` en `api/ai/search`, sin versión, `[Authorize]`, siguiendo el patrón de `AiSearchEventsController`
- [x] 7.2 Invocar el validador explícitamente y tratar el cuerpo nulo, dado que `SuppressModelStateInvalidFilter` está activo
- [x] 7.3 Mapear los resultados: 400 sin punto de venta o petición inválida, 403 punto de venta no permitido, 429 por exceso de peticiones, 200 en el resto
- [x] 7.4 Registrar los servicios nuevos en `Application/Extensions/ServiceCollectionExtensions.cs` y la política en la capa de API

## 8. Tests

- [x] 8.1 Unitarios de orquestación con `IAiGatewayClient` falso y `TimeProvider` inyectado: `Search_HydratesPriceAndStockFromDatabase_NotFromAiResponse`, `Search_RequestsTheMaximumCandidateWindowInASingleCall`, `Search_WhenPosCoverageIsLow_ReturnsFewerThanTopK_WithoutASecondCall`
- [x] 8.2 Hidratación: `Search_WhenCandidateNoLongerAssigned_DropsItAfterHydration`, `Search_KeepsAssignedProductWithZeroStock`, `Search_HydratesInASingleQuery`
- [x] 8.3 Degradación: `Search_WhenAiUnavailable_FallsBackToLexicalSearch`, `Fallback_MatchesAnyQueryTerm_NotTheWholeString`, `Fallback_IsScopedToTheSearchPointOfSale`
- [x] 8.4 Bandera y telemetría: `Search_WhenFeatureFlagOff_UsesLegacySearch`, `Search_WhenFeatureFlagOff_RecordsOriginDisabled`, `Search_WhenTelemetryFails_StillReturnsResults`, y un test que verifica que `RecordSearchAsync` **se invoca** (obligación cuyo incumplimiento no tiene síntoma)
- [x] 8.5 Coste: `Search_RepeatedQueryHitsCandidateCache_WithoutSecondEmbedding`, `Search_CacheKeyIncludesPointOfSale`, y que un acierto de caché rehidrata
- [x] 8.6 Permisos: `Search_AdminMayChooseAnyActivePos`, `Search_OperatorCannotChooseUnassignedPos`, `Search_WithoutPointOfSale_ReturnsBadRequest`, `Search_WhenPointOfSaleInactive_IsRefused`
- [x] 8.7 Integración con Testcontainers del flujo completo. Pedir cliente nuevo a la factoría para las aserciones de no autenticado, y fijar `.WithPhone("600123456")` en los objetos madre
- [x] 8.8 Comparar el resultado de la suite contra el baseline de 1.2 **por nombres**, no por número

## 9. Cierre

- [x] 9.1 `openspec validate --all --strict` → 0 failed (el delta toca una spec ya activa, así que no basta validar este change)
- [x] 9.2 Enlazar HU-AIENG-015 en `Documentos/epicas.md` (EP14)
- [ ] 9.3 Verificación posterior, fuera del DoD de merge: búsqueda real desde `op-ciutadella` y desde `op-fornells` con el índice local poblado, comprobando que la segunda devuelve página corta y que el embudo lo refleja
- [x] 9.4 Revisar que no queda TODO ni FIXME sin tarea de seguimiento, y que no hay diff en `ai-service/`, `ai-service/openapi.json`, `IAiGatewayClient`, `frontend/` ni migraciones
