# QA — C16 `add-frontend-assisted-search-panel`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-29 · **Rama:** `c16-add-frontend-assisted-search-panel`
> **Commits:** `e7732bb` (HU + ticket + §0 del plan y ficha C16) · `742e419` (proposal, design, specs, tasks) · implementación, tests y este registro, pendientes de commit.
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| .NET | `net10.0` · `dotnet build` y `dotnet test` sobre `backend/src/JoiabagurPV.sln` |
| Node / frontend | Vite 6 · Vitest 4 · React Testing Library · jsdom |
| Base de datos de integración (.NET) | Testcontainers `postgres:15`, arrancado por `ApiWebApplicationFactory` |
| Base de datos de la verificación manual | `pgvector/pgvector:pg15`, volumen persistente `jpv-pv-postgres-data` con el mundo sembrado de C10 |
| Servicio de IA | **Levantado y con recuperación real** para la §6 (`STUB_MODE=false`, embeddings `openai/text-embedding-3-small`). No interviene en las suites automáticas |
| Contrato Python | `ai-service/openapi.json` — **no se toca**. `git diff` vacío |
| `ai-service/` | **No se ejecuta** `uv run pytest`: C16 no cruza a Python. Ver §5 |
| Migraciones EF | **Ninguna nueva.** `git status` de `Migrations/` vacío |

---

## 1. Suite automática de .NET

> **El recuento no es fiable y CLAUDE.md lo dice**: la suite parte de decenas de fallos preexistentes, una parte de ellos dependiente del orden. La comparación válida es **nombre a nombre**. Esta pasada además lo demuestra empíricamente (§1.2).

| Ejecución | Resultado |
|---|---|
| **Baseline** — árbol limpio en `HEAD`, antes de tocar código | **882 tests · 834 passed · 48 failed** · 21 m 38 s |
| **Después** — C16 implementado | **890 tests · 841 passed · 49 failed** · 8 m 54 s |
| Alcance C16 (`SaleAttributionTests` + `AssistedSearchServiceTests`) | **43 passed, 0 failed** · 21 s |
| `dotnet build` | **Compilación correcta** |

El baseline no necesitó `git stash push -u`: el árbol de trabajo era idéntico a `HEAD` —todo lo hecho hasta entonces estaba commiteado— así que la propia pasada **es** la línea base.

890 − 882 = **8 tests nuevos**, exactamente los añadidos (6 de integración + 2 unitarios).

### 1.1. Comparación nombre a nombre

| | Nombres |
|---|---|
| Fallan **después** y no antes | `InventoryIntegrationTests.Admin_AccessAllPOS_ShouldSucceed` · `.EndToEnd_AssignAdjustView_Workflow` · `.ExcelImport_NegativeQuantityExceedingStock_ShouldReturnErrorAndLeaveStockUnchanged` · `.ExcelImport_ValidFile_ShouldImportSuccessfully` · `.GetStock_WithNonExistentPOS_ShouldReturnEmpty` · `.Operator_ViewStock_ForUnassignedPOS_ShouldReturnEmpty` · `PaymentMethodsControllerTests.Update_WithValidData_ShouldReturnUpdatedPaymentMethod` |
| Fallaban **antes** y ya no | `InventoryIntegrationTests.Admin_ManageAllProducts_ShouldSucceed` · `.ExcelImport_DownloadTemplate_ShouldSucceed` · `.ExcelImport_InvalidSKU_ShouldReturnValidationErrors` · `.ProductSearch_AsOperator_ShouldOnlyFindAssignedProducts` · `.StockValidation_WithInsufficientStock_ShouldReturnError` · `ReturnsControllerTests.GetReturnsHistory_WithFilters_ReturnsFilteredResults` |
| **De C16** | **Ninguno.** Cero fallos en `SaleAttributionTests` y `AssistedSearchServiceTests` |

Los siete que entran y los seis que salen viven **en las mismas tres clases**: `InventoryIntegrationTests`, `PaymentMethodsControllerTests` y `ReturnsControllerTests`. Ninguna de ellas la toca este change.

### 1.2. La dependencia del orden, medida en vez de supuesta

La suite se ejecutó **dos veces sobre el mismo código** (la segunda tras corregir un test propio, ver §7.1). Excluyendo ese test, los conjuntos de fallos difieren en **13 nombres**, todos confinados a esas tres clases:

```
run 1 ∖ run 2 : Adjustment_ResultingInNegativeStock_ShouldBeRejected,
                Admin_AccessCentralizedInventory_ShouldSucceed,
                Admin_ManageAllProducts_ShouldSucceed,
                Operator_AssignProduct_ShouldBeForbidden,
                Operator_ViewStock_ForAssignedPOS_ShouldSucceed,
                GetReturnsHistory_WithExistingReturns_ReturnsPagedResults
run 2 ∖ run 1 : Admin_AccessAllPOS_ShouldSucceed, EndToEnd_AssignAdjustView_Workflow,
                ExcelImport_NegativeQuantityExceedingStock…, ExcelImport_ValidFile…,
                GetStock_WithNonExistentPOS…, Operator_ViewStock_ForUnassignedPOS…,
                PaymentMethodsControllerTests.Update_WithValidData…
```

Mismo código, distinto conjunto de rojos. Es la razón por la que comparar el número —48 contra 49— no habría dicho nada.

### 1.3. Desglose de los tests nuevos de .NET

| Test | Qué fija |
|---|---|
| `CreateSale_WithOwnSearchEvent_StoresAttribution` | El camino feliz de la atribución |
| `CreateSale_WithUnknownSearchEvent_StoresNullAttribution` | Identificador inexistente → nulo, y **201**, no error de validación |
| `CreateSale_WithSearchEventOfAnotherUser_StoresNullAttribution` | La comprobación de **propiedad**, que va más allá de la letra de B5 |
| `CreateSale_WithUnusableSearchEvent_LeavesTheRestOfTheSaleUntouched` | Precio, cantidad, override y **movimiento de inventario** idénticos con y sin atribución usable |
| `BulkSale_AttributesEachLineToItsOwnSearchEvent` | Atribución **por línea**, con una línea sin ninguna |
| `BulkSale_WithUnknownSearchEventOnOneLine_StillCompletesEveryLine` | Una atribución que degrada no revierte un checkout atómico |
| `Search_CarriesTheMaterialsTheRetrieverReported_NotHydratedOnes` | `materials` sale del candidato, no de la hidratación |
| `Search_WhenDegraded_ReturnsAnEmptyMaterialListRatherThanNone` | Vacío **y presente**, no ausente |

---

## 2. Suite automática de frontend

> La suite de frontend **también parte de rojo**, y esto **no está documentado en CLAUDE.md**, que sólo advierte del backend. Ver §7.6.

| Ejecución | Resultado |
|---|---|
| **Baseline** — árbol limpio en `HEAD` | **482 tests · 364 passed · 118 failed** · 40 ficheros (17 en rojo) · 252 s |
| **Después** — C16 implementado | **525 tests · 412 passed · 113 failed** · 44 ficheros (14 en rojo) |
| `npm run build` | **✓ built in 1 m 29 s** |

525 − 482 = **43 tests nuevos**, exactamente los añadidos.

### 2.1. Comparación nombre a nombre

| | Resultado |
|---|---|
| Fallan **después** y no antes | **Ninguno.** Cero regresiones |
| Fallaban **antes** y ya no | 5, todos en ficheros que este change **no toca**: `points-of-sale.test.tsx`, `products/create.test.tsx` (×2), `users.test.tsx`, `image-recognition.service.test.ts` |

Los cinco que dejan de fallar son el mismo fenómeno de orden que en .NET: añadir cuatro ficheros de test desplaza la ejecución. Ninguno está en la ruta de C16.

### 2.2. Desglose de los tests nuevos de frontend

| Fichero | Tests | Qué cubre |
|---|---|---|
| `pages/sales/__tests__/assisted.test.tsx` | **27** | Coste del disparo, filtros, orden recibido, los cuatro «sin resultados», página corta, episodio, selección, punto de venta y rol, embudo, respuesta obsoleta |
| `services/ai-search.service.test.ts` | **9** | Rutas relativas y mapeo de `429` / `403` / `400` (array y diccionario) / genérico; `reportSelection` que resuelve en vez de rechazar |
| `lib/materials-vocabulary.test.ts` | **4** | Fijación de los nueve términos canónicos y los ocho tipos de pieza |
| `pages/sales/__tests__/new-attribution.test.tsx` | **3** | El arrastre hasta la línea del carrito, y que no se atribuye si el producto cambió |

---

## 3. Escenarios de las specs, uno a uno

### `assisted-search-panel` (nueva, 13 requisitos, 38 escenarios)

| Requisito | Cubierto por |
|---|---|
| Entrada del flujo de venta, ruta propia | `sales/index.tsx` (tercera tarjeta), `routes.tsx`, `app-routing-setup.tsx`; escenario de entrega verificado en `new-attribution.test.tsx` |
| Una búsqueda sólo cuando se pide | `should not issue a search request when the operator types without submitting`, `…when the operator submits`, `…when an example query is activated`, `…when a quick filter is toggled`, `should clear the results when the point of sale changes` |
| Filtros sobre el vocabulario cerrado | `should allow selecting multiple materials in quick filters` (comprueba término canónico, no etiqueta), `should clear every active filter…`, más los 4 de fijación del vocabulario |
| Ámbito de punto de venta por rol | `should hide the point of sale selector when the operator has a single assignment`, `should offer only active points of sale…`, `should report a forbidden point of sale as an access problem` |
| Orden recibido y verdad del backend | `should render results in the order received` (fixture cuyo orden por precio **y** por nombre difiere del de llegada), `should mark a result as out of stock when it has none` |
| Explicación con lo que hay | `should render results with reason when search succeeds` (comprueba además que `vector` **no** aparece), `should not render a size when the variant label is absent` |
| Los cuatro «sin resultados» | `should distinguish abstention from empty assortment`, `should say the shop carries none of it…`, `should show legacy results banner when ai is unavailable`, `should show a rate limit message when the server answers 429` |
| Página corta declarada | `should declare a short page when fewer results survive than requested` |
| Embudo sólo para administradores | `should show the funnel block to an administrator`, `should hide the funnel block from an operator` |
| Un episodio por visita | `should keep the search session id across reformulations in one panel visit` |
| Selección inmediata y no bloqueante | `should emit search event when a result is selected`, `should not block navigation when reporting the selection fails`, `should skip the selection report when no search event id was returned` |
| La búsqueda viaja hasta la caja | `should carry the search event id into the sale flow…`, `should carry the search event id into the cart line…`, `should carry no attribution when the product did not come from assisted search` |
| Respuesta obsoleta descartada | `should ignore a stale response when the point of sale changed` |

### `sales-management` (delta: 1 ADDED con 6 escenarios, 1 MODIFIED)

| Escenario | Cubierto por |
|---|---|
| Venta atribuida a su búsqueda | `CreateSale_WithOwnSearchEvent_StoresAttribution` · §6.4 real |
| Cada línea masiva con la suya | `BulkSale_AttributesEachLineToItsOwnSearchEvent` · §6.5 real |
| Referencia desconocida → sin atribución | `CreateSale_WithUnknownSearchEvent_StoresNullAttribution` · §6.4 real |
| Referencia de otro usuario → sin atribución | `CreateSale_WithSearchEventOfAnotherUser_StoresNullAttribution` · §6.4 real |
| La atribución nunca cambia el resto de la venta | `CreateSale_WithUnusableSearchEvent_LeavesTheRestOfTheSaleUntouched` · §6.4 real |
| Venta sin búsqueda sigue siendo válida | El mismo test, cuarta fila de §6.4 |
| **MODIFIED** — tres métodos de entrada | Tercera tarjeta en `sales/index.tsx`; escenario nuevo *Create sale from an assisted search selection* cubierto por `new-attribution.test.tsx` + §6.4 |

### `ai-assisted-search` (delta: 1 ADDED con 3 escenarios)

| Escenario | Cubierto por |
|---|---|
| El resultado lleva sus materiales | `Search_CarriesTheMaterialsTheRetrieverReported_NotHydratedOnes` · §6.3 real (`materials: ["plata"]`) |
| No vienen de la hidratación | El mismo test (el candidato los aporta, la fila hidratada no) |
| Degradado → lista vacía y presente | `Search_WhenDegraded_ReturnsAnEmptyMaterialListRatherThanNone` · §6.2 real (`materials: []`) |

---

## 4. Nombres exigidos por `tasks.md`

Los 18 nombres de la sección 8 de `tasks.md` existen y pasan. Comprobación de los que la ficha C16 pedía literalmente:

| Nombre de la ficha | Estado |
|---|---|
| `should render results with reason when search succeeds` | ✅ |
| `should show legacy results banner when ai is unavailable` | ✅ |
| `should allow selecting multiple materials in quick filters` | ✅ |
| `should emit search event when a result is selected` | ✅ |

Y los cuatro de .NET que el ticket exigía: `CreateSale_WithUnknownSearchEvent_StoresNullAttribution`, `CreateSale_WithSearchEventOfAnotherUser_StoresNullAttribution`, `BulkSale_AttributesEachLineToItsOwnSearchEvent` ✅, más `CreateSale_WithOwnSearchEvent_StoresAttribution` como control positivo.

---

## 5. Alcance negativo

Comprobado que **no** se ha tocado lo que el change declara fuera:

| Zona | Comprobación |
|---|---|
| `ai-service/` | `git status` sin cambios |
| `ai-service/openapi.json` | `git diff` vacío |
| `IAiGatewayClient` | Sin diff |
| Migraciones EF | `git status backend/.../Migrations/` vacío |
| `/api/v1/products/search` | `ProductService.SearchProductsAsync` sin diff |
| Buscador por SKU de `new.tsx` | Sin diff; sólo se añaden lectura del estado y dos campos |
| Dependencias nuevas | Ninguna. `package.json` y `.csproj` sin diff |

El diff final son **24 ficheros**: 13 modificados y 11 nuevos, repartidos en las tres zonas que el §0 del plan declaró.

---

## 6. Verificación con el mundo sembrado (tarea 9.5) — **ejecutada**

Ejecutada el 2026-08-29 sobre el código de esta rama, con recuperación **real** contra el proveedor de embeddings, no en modo stub.

### 6.1. Montaje

| Pieza | Estado |
|---|---|
| PostgreSQL | `pgvector/pgvector:pg15`, volumen `jpv-pv-postgres-data` |
| Mundo sembrado | **1.200 productos · 12 puntos de venta · 6.720 filas de inventario · 4 usuarios · 22.961 ventas** |
| Índice vectorial | `ai.product_document`: **1.200 documentos, 1.200 con embedding** |
| `jbg-ai` | Contenedor efímero con `STUB_MODE=false` y `openai/text-embedding-3-small` |
| Backend | `dotnet run` en `:5056`, con `AiSearch__EnabledPointOfSaleIds` para Ciutadella, Aeroport y Fornells |

Cobertura real por punto de venta, contra la que el diseño de C15 predijo:

| Punto de venta | Inventario activo | Predicción del diseño |
|---|---|---|
| CIU-CENTRE | **871** | ~861 |
| MAO-AIR | **416** | ~420 |
| FORNELLS | **241** | ~243 |

### 6.2. El presupuesto de 800 ms degrada **todas** las búsquedas

Primera tanda, con la configuración del diseño (§6.4):

```
[WRN] ai_gateway_call_failed timeout 1956 2 http://localhost:8001
[WRN] Assisted search degraded: the AI service is unavailable.
[INF] Assisted search funnel. Origin=LexicalFallback Candidates=0 Survived=60 Displayed=10
```

La recuperación **funciona** —`jbg-ai` recibe la petición y embebe la consulta— pero tarda más de 800 ms en frío, así que el reintento único agota el presupuesto y se degrada. **Siempre.** El camino degradado, eso sí, se comportó exactamente como su spec: 60 supervivientes (la misma ventana que el asistido), 10 mostrados, `materials: []`, `searchEventId` presente.

Este es el defecto que la ficha no podía anticipar y que sólo aparece ejecutando: la funcionalidad habría llegado a producción **pareciendo sana** —HTTP 200, resultados en pantalla— respondiendo siempre desde el buscador léxico. Es exactamente el modo de fallo que la columna de origen de C15 existe para hacer visible.

**Acción tomada:** `RetrievalTimeoutMs` de 800 a **2500 ms**, en `appsettings.json` y en el valor por defecto de `AiGatewayOptions`, con la instrucción de volver a 800 ms cuando se arregle la caché. Registrado en [`openspec/DEFERRED_TASKS.md`](../../DEFERRED_TASKS.md). La causa no se arregla aquí: `retrieval.py` construye un `LiteLlmEmbeddingClient` por petición, deuda anotada por C15 y asignada a C21/C22.

### 6.3. Recuperación real, y el corte por punto de venta medido

Misma consulta —*«un anillo de plata para regalar»*— desde los dos operadores, con 2500 ms:

| Punto de venta | Cobertura | Candidatos | Supervivientes | Mostrados | Tiempo |
|---|---|---|---|---|---|
| CIU-CENTRE | 0,78 | 60 | **32** | 10 — página llena | 0,86 s |
| FORNELLS | 0,22 | 60 | **8** | **8 — página corta** | 0,31 s |

Embudo en log estructurado, tal cual:

```
Assisted search funnel. PointOfSaleId=bdc0c24e-… Origin=Assisted Candidates=60 Survived=32 Displayed=10 LowConfidence=False TraceId=3d77ba78…
Assisted search funnel. PointOfSaleId=59ceef96-… Origin=Assisted Candidates=60 Survived=8  Displayed=8  LowConfidence=False TraceId=e76f5953…
```

La aritmética del diseño de C15 (43 y 12 supervivientes de 60) se confirma en orden de magnitud y, sobre todo, en la conclusión: **Fornells no llena página**. Es el caso que B7 obliga a declarar en pantalla.

Primera fila de Fornells, tal como llega al panel:

```json
{ "sku": "SKU1085", "name": "Anillo Hilo de Plata Antigua", "price": 220,
  "quantityAtPointOfSale": 11, "hasStock": true,
  "materials": ["plata"], "score": 0.5828…,
  "variantLabel": null, "matchReasons": ["vector"] }
```

Tres cosas quedan confirmadas con datos reales: `materials` **funciona de extremo a extremo** y es lo único explicativo disponible; `matchReasons` es **literalmente** la constante `["vector"]`, que es el argumento para no pintarlo; y `variantLabel` es nulo, como se anticipó, hasta que C18 lo pueble.

### 6.4. Atribución de venta, los cuatro casos

Cuatro ventas del mismo producto desde Fornells:

| Caso | HTTP | `Sale.SearchEventId` | Precio | Cantidad | Movimientos |
|---|---|---|---|---|---|
| Evento propio | 201 | `1a4f7707-…` | 220,00 | 1 | 1 |
| Identificador desconocido | 201 | **NULL** | 220,00 | 1 | 1 |
| Evento de **otro usuario** (op-ciutadella) | 201 | **NULL** | 220,00 | 1 | 1 |
| Sin referencia | 201 | **NULL** | 220,00 | 1 | 1 |

Precio, cantidad y movimiento de inventario **idénticos en los cuatro**: la atribución no altera nada más, y una imposible nunca hace fallar la venta.

### 6.5. Atribución por línea en el checkout masivo

```
atribucion                           | lineas
-------------------------------------+--------
1a4f7707-63aa-4516-8104-a283d84ddde5 |      1
NULL                                 |      2
```

Tres líneas: una con evento propio, una con identificador desconocido (degradada) y una sin referencia. HTTP 201.

### 6.6. El endpoint de selección

| Acción | Resultado |
|---|---|
| Selección del tercer resultado por su dueño | **204**, y `SelectedFromRank = 3` derivado por el servidor |
| La misma selección desde otro operador | **403** |

Evento almacenado, tal cual:

```
SearchText                      | ResultsCount | SearchOrigin | SelectedFromRank | RetrievalMs | TotalMs
un anillo de plata para regalar |            8 |            1 |                3 |         269 |     280
```

`ResultsCount = 8` es la página corta de Fornells persistida, que es la línea base «antes» de la ablation de C22.

### 6.7. Confirmación incidental: el stock cero se conserva y se marca

Un primer intento de checkout masivo fue rechazado con **400 · `Line 3: Stock insuficiente. Disponible: 0, Solicitado: 1`**. La tercera pieza era un resultado con `hasStock: false` y `quantityAtPointOfSale: 0` — es decir, el panel **la mostró marcada como agotada** (decisión D2 de C15) y la venta la rechazó. Correcto en ambos lados; anotado para C36, que al añadir selección múltiple deberá impedir arrastrar al carrito una fila sin existencias.

### 6.8. Limpieza

Entorno devuelto a su estado previo: API terminada, contenedor efímero de `jbg-ai` eliminado (llevaba la clave del proveedor en su entorno), fichero temporal con el secreto borrado, PostgreSQL detenido, volumen conservado.

**La verificación escribió en la base de datos de desarrollo 7 ventas y 2 eventos de búsqueda reales.** Sobre 22.961 ventas preexistentes es ruido, pero queda constancia.

---

## 7. Incidencias y huecos de esta pasada

### 7.1. Un test propio fallaba, y por una razón que valía la pena

`CreateSale_WithUnusableSearchEvent_LeavesTheRestOfTheSaleUntouched` borraba las ventas entre sus dos mitades para observar la segunda aislada. Una venta está referenciada por su `InventoryMovement`, así que el borrado violaba `FK_InventoryMovements_Sales_SaleId`. Reescrito como dos ventas consecutivas del mismo producto comparadas entre sí — sin borrar nada, y de paso comprueba también que la atribución degradada **no se salta el movimiento de inventario**, que la versión anterior no verificaba.

### 7.2. Tres correcciones menores durante el apply

| Qué | Corrección |
|---|---|
| `Product.Sku` no existe; la propiedad es `Product.SKU` | Corregido en `SaleAttributionTests` |
| `attributedSearchEventId` quedó declarado antes que `selectedProduct` en `new.tsx` — zona muerta temporal | Movido detrás del bloque de estado |
| Una aserción propia buscaba «búsqueda por texto», que aparece en el aviso **y** en la insignia de origen | Acotada al texto exacto del aviso, más una aserción específica sobre la insignia de la fila |

### 7.3. `ApiError.errors` tiene dos formas reales

Está tipado como `Record<string, string[]>` porque es lo que devuelven la mayoría de controladores, pero los endpoints de IA responden con un **array plano** de mensajes. Ambas llegan al cliente. `ai-search.service.ts` normaliza las dos en vez de asumir una, con un test por forma. No se toca el tipo compartido: cambiarlo tocaría a todos los servicios.

### 7.4. La atribución caduca si el operador cambia de producto

Añadido durante el apply, no estaba en el ticket: si el operador llega del panel con el producto X y su `searchEventId`, y luego elige otro producto por SKU, esa venta **no** viene de la búsqueda. `attributedSearchEventId` sólo vale mientras el producto seleccionado siga siendo el que entregó el panel. Sin eso, el indicador de conversión se inflaría con ventas que el panel no produjo. Fijado por `should carry no attribution when the product did not come from assisted search`.

### 7.5. La comprobación de propiedad va más allá de la letra de B5

B5 pedía degradar a nulo un `searchEventId` **desconocido**. El apply añade el evento **de otro usuario**, por coherencia con el endpoint de selección, que exige propiedad sin excepción de administrador. Sin ello un cliente podría colgar su venta de la búsqueda de un compañero y ensuciar el indicador sin dejar rastro. Verificado en §6.4, tercera fila.

### 7.6. La suite de frontend parte de rojo y **CLAUDE.md no lo dice**

118 tests fallan en 17 ficheros antes de tocar nada. `CLAUDE.md` documenta con detalle el baseline del backend y sus dos trampas, pero no menciona que el frontend tenga el suyo. Merece una entrada equivalente; sin ella, quien mida la suite por primera vez concluirá que la ha roto.

### 7.7. `sales/__tests__/new.test.tsx` falla 11/11, y es preexistente

Renderiza `ManualSalesPage` sin `CartProvider` ni mock de `useCart`, así que lanza `useCart must be used within a CartProvider`. Es un defecto anterior a este change y ajeno a él. Por eso la prueba del arrastre vive en `new-attribution.test.tsx`, con su propio mock: construir sobre un fichero que no puede pasar habría hecho inverificables las aserciones nuevas.

### 7.8. `tsc --noEmit` no sirve como puerta

Decenas de errores preexistentes en las plantillas de Metronic (`lucide-react` sin exportar `ShieldUser`, módulos ausentes, `chart.tsx`). Filtrado a los ficheros de C16: **cero errores en los nuevos**; los seis que aparecen en ficheros tocados están en líneas que este change no modifica. La puerta real es `npm run build`, que pasa.

### 7.9. Dos desviaciones deliberadas respecto a `tasks.md`

| `tasks.md` decía | Se hizo | Por qué |
|---|---|---|
| Constante del vocabulario en `frontend/src/config/` | `frontend/src/lib/materials-vocabulary.ts` | `config/` es el área de plantillas de Metronic; `lib/` ya aloja utilidades de dominio con test colocado (`image-url.ts`) |
| Tests con MSW y manejadores explícitos | `vi.mock` del servicio | Es la idiomática de los tests de servicio de este repo, y elimina de raíz la trampa del modo `warn`: la preocupación de fondo —un test que pasa sin probar nada— queda mejor cubierta con `toHaveBeenCalledWith` explícito |

---

## 8. OpenSpec

| Comprobación | Resultado |
|---|---|
| `openspec validate add-frontend-assisted-search-panel --strict` | **valid** |
| `openspec validate --all --strict` | **44 passed, 0 failed** |
| `openspec status --change …` | **4/4 artefactos completos** |
| `tasks.md` | **70/70 tareas marcadas** |

El `--all --strict` es obligatorio y no basta la forma de un solo change: hay dos deltas sobre specs archivadas (`sales-management` y `ai-assisted-search`).

---

## 9. Fuera de esta pasada (no DoD)

- **Vídeo o captura del panel.** El comportamiento está cubierto por 27 tests de componente y por la §6 contra datos reales, pero nadie ha mirado la pantalla renderizada en un navegador.
- **Verificación de la política de peticiones en caliente.** Superar el límite exige 31 búsquedas, es decir 31 embeddings facturados. Queda cubierta por `AiSearchRateLimitTests` y por el test de panel del `429`.
- **Prueba E2E con Playwright.** No la pedía el change.
- **El arreglo de la caché de embeddings de `retrieval.py`.** Es de otro servicio y de otro change (C21/C22). Aquí sólo se mitiga subiendo el presupuesto, con la instrucción de revertirlo.

---

## Veredicto

**Listo para archivar**, con dos salvedades que no bloquean y quedan registradas:

1. **`RetrievalTimeoutMs` está en 2500 ms y debe volver a 800 ms** cuando C21 o C22 conviertan el cliente de embeddings en singleton. Anotado en `appsettings.json`, en `AiGatewayOptions` y en `DEFERRED_TASKS.md`. Dejarlo así indefinidamente convierte el presupuesto en decorado.
2. **El baseline rojo del frontend no está documentado** en `CLAUDE.md`. No es de este change arreglarlo, pero quien venga detrás lo va a tropezar.
