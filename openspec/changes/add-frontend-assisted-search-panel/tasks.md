## 1. Verificación previa

- [ ] 1.1 Medir el baseline de la suite backend con `git stash push -u` y guardar el **conjunto de nombres** que fallan, no el número — la comparación posterior se hace por nombres, porque varios de esos fallos dependen del orden
- [ ] 1.2 Ejecutar `npm run test` en `frontend/` y guardar el conjunto de nombres que fallan, por el mismo motivo
- [ ] 1.3 Confirmar sobre el código que el servicio de ventas tiene un punto único donde se construye la entidad `Sale` en el camino individual y otro en el masivo; si hubiera más de uno, anotarlos todos para no dejar un camino sin atribución

## 2. Tramo de servidor: atribución de la venta

- [ ] 2.1 Añadir `Guid? SearchEventId` a `CreateSaleRequest` y a `BulkSaleLineRequest`, documentando en el propio DTO que es opcional y que un valor inválido degrada a nulo en lugar de rechazar la venta
- [ ] 2.2 Añadir al repositorio o servicio de eventos de búsqueda una comprobación de **existencia y propiedad** que devuelva un booleano y no lance; sin excepción de administrador, por coherencia con el registro de la selección
- [ ] 2.3 Asignar `Sale.SearchEventId` en el camino de venta individual tras esa comprobación; identificador ausente, desconocido o de otro usuario → `null`
- [ ] 2.4 Asignar la atribución **línea a línea** en el camino de venta masiva, de modo que dos líneas puedan llevar búsquedas distintas y una tercera ninguna
- [ ] 2.5 Verificar que el validador de la petición de venta **no** rechaza un identificador desconocido: la degradación es silenciosa y no produce error de validación
- [ ] 2.6 Tests unitarios: `CreateSale_WithUnknownSearchEvent_StoresNullAttribution`, `CreateSale_WithSearchEventOfAnotherUser_StoresNullAttribution`, `CreateSale_WithOwnSearchEvent_StoresAttribution`
- [ ] 2.7 Test de integración: `BulkSale_AttributesEachLineToItsOwnSearchEvent`, con una línea sin atribución. Fijar `.WithPhone("600123456")` en los objetos madre — el generador de Bogus desborda `PointOfSale.Phone`
- [ ] 2.8 Test que fija que una atribución inválida no altera precio, movimiento de inventario ni existencias
- [ ] 2.9 `dotnet build` y suite backend: comparar el conjunto de nombres que fallan contra el baseline de 1.1. Confirmar que **no** se ha generado migración

## 3. Tramo de servidor: materiales en el resultado

- [ ] 3.1 Añadir `List<string> Materials` a `AssistedSearchResultDto`, inicializado a lista vacía, documentando que no es hidratado ni autoritativo
- [ ] 3.2 Propagar `candidate?.Materials ?? []` al construir el resultado en el servicio de búsqueda asistida, sin tocar nada más de ese método
- [ ] 3.3 Test que fija que el camino degradado y el desactivado devuelven la lista **vacía y presente**, no ausente
- [ ] 3.4 Test que fija que los materiales proceden del candidato y no de la hidratación

## 4. Frontend: contratos y vocabulario

- [ ] 4.1 Tipos en `frontend/src/types/ai-search.types.ts`, espejo de la petición, la respuesta y el resultado del endpoint, incluidos `aiAvailable`, `lowConfidence`, `candidatesReturned`, `survivedHydration`, `searchEventId` y `materials`
- [ ] 4.2 Añadir `searchEventId?: string` a `CartLine`, `CreateSaleRequest` y `BulkSaleLineRequest` en `frontend/src/types/sales.types.ts`
- [ ] 4.3 Constante del vocabulario cerrado de materiales con etiqueta mostrada y término canónico, con comentario que apunta a `ai-service/src/jbg_ai/enrichment/vocabularies.yaml`
- [ ] 4.4 Test de fijación de esa constante: los nueve términos canónicos, en su forma exacta. Una deriva no da error en ejecución, devuelve cero resultados
- [ ] 4.5 `frontend/src/services/ai-search.service.ts` con `search()` y `reportSelection()`, rutas **relativas** (`/ai/search`, `/ai/search-events/{id}/selection`) porque `VITE_API_BASE_URL` ya trae `/api`
- [ ] 4.6 Mapeo en el servicio de los códigos `429`, `403` y `400` a un resultado tipado que el panel pueda distinguir, sin perder los mensajes que devuelve el backend
- [ ] 4.7 Tests del servicio con MSW, con **manejadores declarados explícitamente**: el simulador corre en modo aviso y una petición sin manejador no rompe el test

## 5. Frontend: fila de resultado

- [ ] 5.1 Componente aislado de fila en `frontend/src/components/sales/`, para que el change del argumentario lo amplíe en vez de reescribir la página
- [ ] 5.2 Renderizado de foto con `getImageUrl` y reserva cuando no hay, SKU, nombre y precio en EUR con formato es-ES
- [ ] 5.3 Cantidad del punto de venta y marca de agotado **por texto además de por color**, conservando la fila
- [ ] 5.4 Insignia de origen desde un mapa ampliable, y chips de materiales
- [ ] 5.5 Etiqueta de variante **sólo cuando existe**, sin hueco ni valor de relleno cuando es nula
- [ ] 5.6 Tests: `should render results with reason when search succeeds`, `should mark a result as out of stock when it has none`, `should not render a size when the variant label is absent`

## 6. Frontend: el panel

- [ ] 6.1 Página `frontend/src/pages/sales/assisted.tsx` con el identificador de episodio generado **al montar**, en una referencia estable
- [ ] 6.2 Caja de consulta con **envío explícito** (Enter y botón). Prohibido `useDebouncedCallback` sobre la consulta
- [ ] 6.3 Tres a cinco consultas de ejemplo que rellenan la caja **y** lanzan la búsqueda en un solo acto
- [ ] 6.4 Filtros rápidos: materiales en multi-selección y categoría de pieza; **no disparan búsqueda**; acción visible de quitar todos
- [ ] 6.5 Selector de punto de venta: oculto con una única asignación, visible con varias o con rol de administrador, sólo activos; cambiarlo **limpia resultados y no relanza**
- [ ] 6.6 Guardia de petición vigente (identificador monótono o `AbortController`) para descartar respuestas obsoletas
- [ ] 6.7 Estado de carga con esqueletos, y renderizado de resultados **en el orden recibido**, sin `sort()`
- [ ] 6.8 Los cuatro estados sin resultados: abstención, sin surtido con acción de quitar filtros, degradado o desactivado, y cuota agotada — este último **nunca** como indisponibilidad del servicio
- [ ] 6.9 Aviso de página corta con los contadores de la respuesta, sin degradar la lista a estado de error
- [ ] 6.10 Bloque de embudo plegable, colapsado, **sólo para administradores**, con identificador de correlación y los tres contadores
- [ ] 6.11 Acción «Seleccionar para venta»: reporte de la selección **sin esperar respuesta y sin toast de error**, omitido en silencio si el identificador de evento es nulo, y navegación con producto e identificador de búsqueda

## 7. Frontend: ruta, entrada y arrastre hasta la caja

- [ ] 7.1 `ROUTES.SALES.NEW_ASSISTED = '/sales/new/assisted'` y ruta perezosa bajo `ProtectedRoute` + `Layout8`, como el resto de páginas de venta
- [ ] 7.2 Tercera tarjeta «Buscar con ayuda» en `pages/sales/index.tsx`, sin desplazar «Escanear código» de la posición primaria
- [ ] 7.3 `new.tsx`: leer `searchEventId` del estado de navegación junto al `productId` ya soportado, y conservarlo mientras dure la edición del formulario
- [ ] 7.4 `new.tsx`: enviarlo en `createSale` y pasarlo a `addLine`
- [ ] 7.5 `cart.tsx`: enviarlo **por línea** en `createBulkSales`
- [ ] 7.6 Verificar que una venta iniciada por escaneo, por SKU o por reconocimiento de imagen sigue enviando el campo ausente y se crea igual

## 8. Tests del panel

- [ ] 8.1 `should not issue a search request when the operator types without submitting`
- [ ] 8.2 `should issue exactly one search request when the operator submits`
- [ ] 8.3 `should fill the field and search when an example query is activated`
- [ ] 8.4 `should allow selecting multiple materials in quick filters`
- [ ] 8.5 `should not issue a search request when a quick filter is toggled`
- [ ] 8.6 `should render results in the order received` — con un fixture cuyo orden por precio o por nombre sea **distinto** del de llegada, o el test no prueba nada
- [ ] 8.7 `should distinguish abstention from empty assortment`
- [ ] 8.8 `should show legacy results banner when ai is unavailable`
- [ ] 8.9 `should show a rate limit message when the server answers 429`
- [ ] 8.10 `should declare a short page when fewer results survive than requested`
- [ ] 8.11 `should keep the search session id across reformulations in one panel visit`
- [ ] 8.12 `should emit search event when a result is selected`
- [ ] 8.13 `should not block navigation when reporting the selection fails`
- [ ] 8.14 `should skip the selection report when no search event id was returned`
- [ ] 8.15 `should carry the search event id into the cart line`
- [ ] 8.16 `should ignore a stale response when the point of sale changed`
- [ ] 8.17 `should hide the funnel block from an operator` y `should show the funnel block to an administrator`
- [ ] 8.18 `should clear the results when the point of sale changes`

## 9. Cierre

- [ ] 9.1 `npm run build` sin errores y ruta perezosa confirmada; `npm run test` comparando el conjunto de nombres que fallan contra el baseline de 1.2
- [ ] 9.2 `dotnet build` y suite backend comparada por nombres contra el baseline de 1.1
- [ ] 9.3 `openspec validate --all --strict` → **0 failed**: hay dos `MODIFIED`/`ADDED` sobre specs archivadas y no basta con validar la forma de este change
- [ ] 9.4 Enlazar HU-AIENG-016 en `Documentos/epicas.md` (EP14)
- [ ] 9.5 Verificación manual con el mundo sembrado: buscar desde `op-ciutadella` y desde `op-fornells`, comprobar que la segunda declara página corta, que el embudo lo refleja, y que la venta resultante guarda `SearchEventId` en base de datos
- [ ] 9.6 Comprobar que no hay TODO/FIXME sin tarea de seguimiento y que toda la interfaz nueva está en español con moneda EUR
