# QA — C40_FIX `c40-fix-all-shops-scope-unreachable`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados y su evidencia.
> **Fecha:** exploración y artefactos el **2026-09-26**, implementación el mismo día · **Rama:** `c40-fix-all-shops-scope-unreachable` · **Artefactos de partida:** `501c97c` (`proposal`, HU, ticket enriquecido y `epicas.md`), publicado en `origin` · **Implementación sin commitear** a petición del desarrollador.
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la [HU](../../../Documentos/Historias/AI-Eng/HU-AIENG-040-FIX.md).
> **Alcance:** **38/38 tareas**. La 10.2 —comprobación manual en el entorno— la ejecutó el desarrollador el 2026-09-26 sobre el entorno local; evidencia en el §6, **con una salvedad que se declara y no se disimula**.
> **Este change NO mueve el contrato:** `ai-service/openapi.json` sin diff y `ai-service/` sin tocar (§5).
> **Este change NO crea migraciones:** ninguna entidad, columna ni índice cambia (§5).
> **Este change SÍ llamó a un proveedor real**, una vez, en la verificación en vivo del §4: una consulta libre de ámbito global contra `jbg-ai` con `STUB_MODE=false`. Del orden de una milésima de dólar.
> **Lo que esta pasada encontró:** **tres defectos del método de medición, míos, los tres corregidos en el acto** (§8.1, §8.2, §8.3), **una segunda vía —no documentada— a la trampa del «`dotnet test` sale 0 sin ejecutar nada»** (§8.2), y una **medición que endurece lo que `CLAUDE.md` documenta** sobre la inestabilidad de `InventoryIntegrationTests` (§1.2).

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| .NET | SDK 10 · Windows 11 · Git Bash y PowerShell |
| Solución | `backend/src/JoiabagurPV.sln` — **no la raíz del repo**, ver §8.2 |
| PostgreSQL de integración | Testcontainers, el `ApiWebApplicationFactory` del repositorio |
| PostgreSQL de la verificación en vivo | `jpv-pv-postgres`, puerto **5433**, base `joiabagur_pv` sembrada: **11 tiendas activas**, 3 operarios, 1 administrador |
| API en la verificación en vivo | `dotnet run --launch-profile http` en `localhost:5056`, con **los tres interruptores activos** por variable de entorno |
| `jbg-ai` en la suite | **Nunca**: ni el frontend ni los tests .NET de este change lo alcanzan |
| `jbg-ai` en la verificación en vivo | Contenedor `jpv-pv-jbg-ai`, **`STUB_MODE=false`** y las tres claves de proveedor presentes — comprobado con `printenv`, no supuesto |
| Frontend | `vitest` sobre el árbol de la rama · verificación manual en `localhost:3000` |
| `ai-service` (pytest) | **No ejecutado**: el diff no toca `ai-service/` (§5). La suite de Python no puede haber cambiado |
| Contrato | `openapi.json` **no regenerado**; sin diff comprobado con `git status` |
| Migraciones | **Ninguna**: el diff no toca `JoiabagurPV.Infrastructure/Migrations/` |

---

## 1. Suites automáticas

**La línea base se midió antes de tocar una línea de código de aplicación**, sobre `501c97c`, y guardando los **nombres** de los fallos y no sólo los recuentos. Esa distinción no es ceremonia: el §1.2 documenta una medición en la que dos pasadas del **mismo binario** difieren en siete nombres.

| Ejecución | Resultado |
|---|---|
| **Línea base frontend** (`npm run test`, árbol limpio de código) | **113 en rojo · 721 en verde · 834 tests · 14 de 57 ficheros** · 253 s |
| **Línea base backend** (`dotnet test JoiabagurPV.sln`) | **45 con error · 1.284 superados · 1.329 tests** · 28 m 4 s |
| `assisted.test.tsx` **al empezar** | **verde entero**, 0 de 57 en rojo — la señal más limpia posible para el área propia |
| Clases .NET del área propia **al empezar** | **0 fallos** — ninguna de `AssistedSearch*`, `AiSearch*`, `FreeQuery*` ni `Availability*` en los 45 nombres |
| `dotnet build JoiabagurPV.sln` tras los grupos 2 y 3 | **Compilación correcta · 0 errores** |
| Clases afectadas, filtradas (`~AssistedSearchServiceTests`, `~AiSearchControllerTests`, `~FreeQuery`) | **122 / 0** en 2 m 4 s, con los 10 nuevos dentro |
| `assisted.test.tsx` tras los cambios de producción, **antes** de escribir tests nuevos | **80 / 80** junto a `assisted-search-result-row.test.tsx` — cero regresiones de producción |
| `assisted.test.tsx` **al cierre** | **71 / 71**, con los 14 nuevos |
| **Cierre frontend** (suite completa) | **114 en rojo · 734 en verde · 848 tests · 15 de 57 ficheros** |
| **Cierre backend** (suite completa) | **52 con error · 1.287 superados · 1.339 tests** · 28 m 19 s |
| `tsc --noEmit` filtrado a los ficheros propios | **sin errores**, en cada paso del frontend |
| `openspec validate c40-fix-all-shops-scope-unreachable --strict` | `Change '…' is valid` |
| `openspec validate --all --strict` | **63 passed · 0 failed**, al escribir las deltas y al cerrar |

### 1.1. La comparación por nombres del frontend: un solo nombre, y es el documentado

| Entra en rojo al cierre | Sale del rojo al cierre |
|---|---|
| `admin/__tests__/family-review.test.tsx :: family review screen should create a family with its members from the review screen` | — (ninguno) |

Ese nombre es **literalmente** el que `CLAUDE.md` registra como el que refutó la afirmación de que aquí el conjunto de fallos es estable entre corridas: *«failed at baseline and passed at close with nothing touching it or its production code»*. No se dio por bueno citando el documento. Dos comprobaciones:

1. **Ejecutado su fichero solo: `22 / 22` en verde.** Dependiente del orden, como está documentado.
2. **Cero dependencias de importación** entre `family-review` —test y producción— y cualquiera de los cinco ficheros de frontend tocados. `grep` de `ai-search`, `assisted`, `search-route-toggle` y `ai-availability` sobre los dos ficheros: sin resultados. No existe camino causal.

**El área propia queda verde**: `assisted.test.tsx` no aparece en los 114 nombres. Estaba verde al empezar y está verde al cerrar, con 14 tests más dentro.

### 1.2. La comparación del backend, y la medición que endurece lo que `CLAUDE.md` dice

**Once nombres difieren: nueve entran y dos salen.** El salto de recuento —45 → 52— es **mayor que el ±1 que documenta `CLAUDE.md`**, así que no se aceptó por analogía.

| Entran en rojo al cierre | Salen del rojo al cierre |
|---|---|
| `InventoryIntegrationTests.Adjustment_ResultingInNegativeStock_ShouldBeRejected` | `InventoryIntegrationTests.MovementHistory_WithPagination_ShouldReturnPagedResults` |
| `InventoryIntegrationTests.AssignProduct_WithNonExistentPOS_ShouldReturnNotFound` | `InventoryIntegrationTests.SaleMovement_ResultingInNegativeStock_ShouldBeRejected` |
| `InventoryIntegrationTests.AssignProduct_WithValidProduct_ShouldSucceed` | |
| `InventoryIntegrationTests.CreateSaleMovement_WithInsufficientStock_ShouldRollback` | |
| `InventoryIntegrationTests.EndToEnd_AssignAdjustView_Workflow` | |
| `InventoryIntegrationTests.ExcelImport_NegativeQuantityExceedingStock_ShouldReturnErrorAndLeaveStockUnchanged` | |
| `InventoryIntegrationTests.Operator_AccessCentralizedInventory_ShouldBeForbidden` | |
| `InventoryIntegrationTests.ProductSearch_AsOperator_ShouldOnlyFindAssignedProducts` | |
| `ProductsControllerTests.Update_WithValidData_ShouldReturnUpdatedProduct` | |

**Diez de los once están en `InventoryIntegrationTests`**, la primera de las tres clases que `CLAUDE.md` nombra como inestables. El undécimo está en `ProductsControllerTests`, que ya traía **cinco** fallos en la línea base.

Tres evidencias, en orden creciente de fuerza:

**a) No existe camino causal.** `grep` recursivo de los seis símbolos que el change modifica —`AiScopeSwitchExtensions`, `AiSearchAvailabilityResponse`, `IAssistedSearchService`, `AssistedSearchService`, `FreeQuerySearchService`, `AiSearchController`— sobre todos los ficheros de `Application`, `API` e `Infrastructure` cuyo nombre contiene `Inventor` o `Product`: **cero referencias** en los seis casos.

**b) Dos de los once ya están registrados como intermitentes en el QA de C34.** `ProductsControllerTests.Update_WithValidData_ShouldReturnUpdatedProduct` tiene su propio apartado allí —*«es intermitente — hallazgo, no registrado antes»*— y `InventoryIntegrationTests.MovementHistory_WithPagination_ShouldReturnPagedResults` figura en su tabla de rotación. Los otros nueve son nombres nuevos **en las mismas dos clases**.

**c) La medición que lo cierra: dos pasadas aisladas del mismo binario dan conjuntos distintos.**

| Pasada | Comando | Resultado |
|---|---|---|
| Aislada nº 1 | `--filter "FullyQualifiedName~InventoryIntegrationTests"` | **9 con error de 34** · 2 m 0 s |
| Aislada nº 2 | idéntico, más **`--no-build`** | **9 con error de 34** · 1 m 57 s |

Mismo recuento, y **siete de los nueve nombres difieren** entre las dos. Sólo dos son estables. Y los **tres** que en la pasada nº 1 «seguían rojos en aislamiento» —`AssignProduct_WithNonExistentPOS_ShouldReturnNotFound`, `Operator_AccessCentralizedInventory_ShouldBeForbidden` y `ProductSearch_AsOperator_ShouldOnlyFindAssignedProducts`, los dos últimos de autorización de operario, que eran los que más inquietaban— **pasaron en la pasada nº 2**.

Además, la clase falla **4** dentro de la corrida completa y **9** corriendo sola: el mismo binario da respuestas distintas según el contexto, en las dos direcciones.

**Conclusión:** `InventoryIntegrationTests` no es «a veces inestable» — es **no determinista de una pasada a la siguiente sobre el mismo binario**. `CLAUDE.md` lo describe para el conjunto de clases rotatorias; esta pasada lo mide **dentro de una sola clase y sin recompilar**, que es una afirmación más fuerte y merece quedar escrita.

### 1.3. Desglose de los nuevos, y la aritmética cierra

| Fichero | Declaraciones | Casos ejecutados | Tipo |
|---|---:|---:|---|
| `AssistedSearchServiceTests` | 5 | **8** | unitario; una es `[Theory]` de 4 casos |
| `AiSearchControllerTests` | 2 | **2** | integración con Testcontainers |
| `assisted.test.tsx` | 14 | **14** | página, con `vi.mock` de los servicios |
| | **21** | **24** | |

Backend: 1.329 → 1.339 = **+10** ✓ (8 + 2). Frontend: 834 → 848 = **+14** ✓.

### 1.4. Los tests nuevos no pasan en vacío

Contra el código anterior **los 14 de página fallarían todos** en `findByRole('option', { name: 'Todas las tiendas' })`, porque la opción no existía: no hay forma de que pasen sin el cambio. De los .NET, `GetAvailability_WithoutPointOfSale_IgnoresThePerShopAllowlist` asserta **las dos direcciones** —el ámbito global apagado y la tienda de la lista encendida, con la misma configuración—, así que discrimina en vez de confirmar un interruptor que casualmente está a false.

---

## 2. La puerta de entrada (grupo 1)

- **1.1** Línea base de las dos suites medida antes de tocar código de aplicación, **con nombres**. Tres tropiezos de método por el camino, todos míos: §8.1, §8.2 y §8.3.
- **1.2** Las **cuatro afirmaciones que dimensionan el change**, reconfirmadas contra el árbol antes de escribir nada:

| Afirmación | Comprobación | Resultado |
|---|---|---|
| `AssistedSearchRequestValidator` lleva `.NotEmpty()` en `PointOfSaleId` | `grep -A2` | ✅ presente, con su mensaje |
| `GetAvailability` vive en `AssistedSearchService` y consulta **tres** clases de opciones | `grep` en `Services/*.cs` + recuento de `IsEnabledFor` | ✅ un solo sitio, **3** llamadas |
| `compose.demo.yaml` **no** declara `AiFreeQuerySearch__EnabledByDefault` | `grep -c` | ✅ **0 ocurrencias** |
| `SearchLexicalAsync` acepta `Guid?` **sin** agrupar por producto | `grep -c GroupBy` en su cuerpo | ✅ **0** `GroupBy` |

Las cuatro se confirmaron, así que el plan del `design.md` se ejecutó sin desvíos.

---

## 3. Las deltas de spec

| Fichero | Requisitos | Escenarios |
|---|---:|---:|
| `specs/assisted-search-panel/spec.md` | **5** (2 `ADDED` + 3 `MODIFIED`) | **21** |
| `specs/ai-free-query-search/spec.md` | **1** (`MODIFIED`) | **4** |

### 3.1. Cada `## MODIFIED` reproduce el requisito vivo entero

Comprobado con `awk`, extrayendo los `#### Scenario:` de cada requisito en la spec viva y en la delta, y restando conjuntos:

| Requisito modificado | Escenarios vivos | Conservados |
|---|---:|---|
| `The search is scoped to one point of sale, chosen according to role` | 3 | ✅ los 3, **+1 nuevo** |
| `The availability of each AI path is stated before any search is issued` | 3 | ✅ los 3, **+1 nuevo** |
| `The stock label names the shop, and says so plainly when there is no shop to name` | 4 | ✅ 3 literales **+1 renombrado a propósito**, **+1 nuevo** |

**El renombrado es deliberado y es el fondo del asunto.** La spec viva tiene `#### Scenario: Changing shop calls no model`, cuyo primer `THEN` dice *«the stock figures are refreshed»* — y el panel **limpia** los resultados, así que esa cláusula nunca fue verdad y el test de C40 sólo comprobó el segundo `AND`. La delta lo deja como `Changing shop clears rather than refreshes, and calls no model`: mismo `WHEN`, el `THEN` falso sustituido por el verdadero y el `AND` intacto. Renombrarlo es el punto: el nombre viejo describía sólo la mitad que se sostenía.

### 3.2. La regla de la primera línea física, en los 6 requisitos

El validador lee **sólo la primera línea física** de la descripción que sigue a `### Requirement:`. Comprobado con `awk` sobre los seis: **los seis llevan `SHALL` en ella**, y las seis líneas van sin ajustar —entre **228 y 346 caracteres**—, como las archivadas.

### 3.3. Se descartó `RENAMED`, y no por comodidad

El requisito de ámbito conserva su título —*«The search is scoped to one point of sale…»*— aunque ya no lo describa bien. La alternativa era `## RENAMED Requirements`, y se descartó al medir que **no existe un solo precedente en los 71 changes archivados** (`grep -rln "## RENAMED Requirements" openspec/changes/archive/` → vacío). Estrenar una vía del validador en la puerta del proyecto es el riesgo que este repositorio ya ha pagado tres veces. En su lugar: el `MODIFIED` corrige el `SHALL` falso y **el control va como `ADDED` con título propio**, que además es lo que la propia instrucción del artefacto recomienda —*«If adding new concerns without changing existing behavior, use ADDED instead»*—.

### 3.4. El `proposal.md` se puso al día, porque la delta creció

El `proposal.md` enumeraba **dos** requisitos modificados. Al escribir la delta salieron **dos nuevos y tres corregidos**: el control y el estado del toggle son concerns nuevos, y los enunciados falsos son tres —el de ámbito, el de disponibilidad y la cláusula del refresco— y no dos. Se corrigió el `proposal.md` en el mismo acto: **dejar que los artefactos de un change se contradigan entre sí es la misma deriva que este change persigue en las specs vivas.**

---

## 4. La verificación en vivo del backend (tarea 10.2, mitad servidor)

Entorno del §1 levantado, login real (`admin` / token JWT de 436 caracteres), `curl` contra `localhost:5056`.

| Caso | Esperado | Medido |
|---|---|---|
| `GET /api/ai/search/availability` **sin** `pointOfSaleId` | 200 · identificador **nulo** | ✅ `HTTP 200` · `{"pointOfSaleId":null,"semanticSearchAvailable":true,"assistedAnswerAvailable":true,"assistedAnswerUnavailableReason":null}` |
| `GET …?pointOfSaleId=43da2f6a-…` | 200, como antes | ✅ `HTTP 200` · identificador devuelto |
| `GET …?pointOfSaleId=00000000-0000-0000-0000-000000000000` | **400** | ✅ `HTTP 400` · `{"errors":["El punto de venta no es válido. Omítelo para consultar todas las tiendas."]}` |
| `POST /api/ai/search/assisted` **sin** punto de venta | 200, sin cantidades | ✅ `HTTP 200` · grupos con `"quantityAtPointOfSale":null,"hasStock":null` · pieza real del catálogo (`SKU143 Anillo rama`, `Colección Suspiro`) |
| `POST /api/ai/search` **sin** punto de venta | **400** | ✅ `HTTP 400` · `{"errors":["La búsqueda asistida requiere un punto de venta."]}` |

**La primera fila es el cambio: antes de este change era un 400.** Y la última es **el hallazgo que dimensionó el change**, demostrado contra el sistema real: es la razón de que el panel fije la ruta asistida en cuanto se elige el ámbito global. Sin eso, el primer *Buscar* del administrador escribiría ese error justo debajo del control que se lo acaba de ofrecer.

---

## 5. El contrato y el alcance negativo, demostrados

| Afirmación | Comprobación | Resultado |
|---|---|---|
| `ai-service/openapi.json` sin diff | `git diff --stat` y `git status` sobre `ai-service/` | ✅ vacío |
| `ai-service/` sin tocar | `git status --short ai-service/` | ✅ vacío |
| Ninguna migración creada | `git status --short …/Migrations/` | ✅ vacío |
| La fila de resultado sin tocar | `git status` — `assisted-search-result-row.tsx` no aparece | ✅ y sus 23 tests siguen verdes |
| `FreeQuerySearchService` y `AiCallScope` sin cambio funcional | diff leído: en el primero sólo se **retira** el `IsEnabled` privado y se llama al extraído; el segundo no aparece | ✅ |
| La autorización **no** se endurece | los tests `FreeQuery_ForOperatorWithAllPointsOfSale_IsServed` y `FreeQuery_WhenNamingAnUnassignedPointOfSale_IsRefused` siguen en verde en la corrida filtrada de 122 | ✅ |
| Sin TODO/FIXME/HACK/XXX | `grep` sobre los 14 ficheros del diff | ✅ ninguno |

**14 ficheros tocados** (6 backend de producción y test, 5 frontend, `compose.demo.yaml`, `DEFERRED_TASKS.md`, `proposal.md`), más los 3 artefactos nuevos del change y el `qa.md`.

---

## 6. La verificación manual del desarrollador (tarea 10.2, mitad pantalla)

Ejecutada por el desarrollador el **2026-09-26** sobre `localhost:3000`, con la API del §1 y `jbg-ai` con proveedor real.

**Como administrador:**

| Comprobación | Resultado |
|---|---|
| Con una tienda concreta, **las dos** vías de búsqueda siguen habilitadas | ✅ |
| Con «Todas las tiendas»: sale *«Verás piezas de todo el catálogo. Para leer existencias, elige una tienda.»*, se **deshabilita la búsqueda rápida** y la **respuesta asistida sigue habilitada** | ✅ — es el escenario que cierra el change |
| Buscando «un anillo de plata para regalar»: **ni un número** en las filas, sin nombre de tienda, botón de ficha deshabilitado, y **cada producto una sola vez** | ✅ |

**Como operario:** no puede escoger punto de venta.

**Y aquí va la salvedad, que se declara en vez de disimularse.** Ese resultado satisface el requisito —*«no se ofrece al operario ninguna opción para buscar en todas las tiendas»*— pero **lo satisface por la vía de la asignación única**, no por la que el escenario tenía en mente. Comprobado en la base:

```
 admin         | Administrator | 0 tiendas
 op-aeroport   | Operator      | 1 tienda
 op-ciutadella | Operator      | 1 tienda
 op-fornells   | Operator      | 1 tienda
```

Los tres operarios sembrados tienen **exactamente una** tienda, así que el selector **no se renderiza** por la regla previa de C16 —`pointsOfSale.length > 1 || isAdmin`, que este change no toca a propósito—. De modo que la comprobación manual confirma el camino de la asignación única y **no ejercita el del operario con varias tiendas**, que es el que enseña un selector **con** tiendas y **sin** la opción global. Ese camino queda cubierto por el test de página `should not offer the every-shop scope when the caller is an operator`, que simula dos tiendas justamente para que la ausencia de la opción no pueda achacarse a la ausencia del selector.

**No existe en los datos sembrados un operario con varias tiendas**, así que ese camino no es verificable a mano en este entorno sin crear uno. Queda anotado como lo que es: cobertura de test, no de pantalla.

---

## 7. El DoD del ticket, casilla a casilla

| Casilla | Evidencia |
|---|---|
| Código según las capas de `modelo-c4.md` y las convenciones de `project.md` | Domain intacto · Infrastructure intacto · el predicado en `Application/Configuration` · el controlador en `API` |
| Backend: xUnit + Moq + FluentAssertions, nomenclatura `Método_Escenario_ResultadoEsperado` | 10 casos nuevos, los diez con esa forma (§1.3) |
| Frontend: Vitest + RTL, nomenclatura `should … when …`, queries accesibles | 14 casos nuevos; `getByLabelText`, `findByRole('option')`, `getByRole('button')` |
| Cobertura ≥ 70 % sobre el código nuevo | **No medida con `coverlet`** — se declara en el §9. El código nuevo es un método de extensión ×3, una rama de nulo y seis condicionales de interfaz, y todos tienen test nominal |
| `ai-service`: sin cambios y `openapi.json` sin diff | §5, comprobado |
| Sin migración de EF Core | §5, comprobado |
| Deltas de spec y `openspec validate --all --strict` en `0 failed` | **63 passed · 0 failed** (§1) |
| Las tres specs dejan de afirmar algo falso, **leído y no sólo validado** | §3.1: el `SHALL` de ámbito, la disponibilidad *«for the selected point of sale»* y la cláusula del refresco |
| Suites comparadas por **nombres** contra la línea base del propio commit | §1.1 y §1.2 |
| `dotnet build` y `tsc --noEmit` filtrado en verde | §1 |
| Comprobación manual en el entorno | §4 y §6, con la salvedad del §6 |
| Documentación actualizada | `epicas.md` (EP15 + resumen), `frontend/README.md`, `backend/README.md`, `DEFERRED_TASKS.md` |
| Compatibilidad hacia atrás del contrato REST | `PointOfSaleId` anulable es **adición de tolerancia**: un cliente que leía un valor sigue leyéndolo cuando hay tienda. Único consumidor: el panel |
| Sin TODO/FIXME sin tarea asociada | §5 |
| UI en español y EUR | Las seis cadenas nuevas, en es-ES |

---

## 8. Incidencias de esta pasada

### 8.1. Medí dos veces con `tail` y me quedé sin los nombres — **defecto mío de método; corregido**

Las dos primeras corridas de línea base se pipearon por `tail -40` y `tail -30`, que devuelven los recuentos y **borran la lista de nombres**. Como el juicio de este repositorio se toma por nombres —el §1.2 mide siete nombres distintos entre dos pasadas del mismo binario—, el recuento solo no vale nada. Se repitieron las dos con captura completa: el frontend con `--reporter=json` y un script de extracción, el backend redirigiendo todo a fichero. **Coste: unos 35 minutos de reloj.**

### 8.2. `dotnet test` desde la raíz del repo falla y **sale 0** — **segunda vía a una trampa documentada a medias**

`CLAUDE.md` advierte de que si algo bloquea `bin/Debug` —un `JoiabagurPV.API.exe` vivo— el build falla, **no se ejecuta ni un test y `dotnet test` sale 0**. Hay una segunda vía al mismo desenlace, que no está escrita: **desde la raíz del repositorio no hay solución** —vive en `backend/src/JoiabagurPV.sln`—, así que MSBuild imprime `MSBUILD : error MSB1003: Especifique un archivo de proyecto o de solución` y **también sale 0**.

La lección de `CLAUDE.md` es la correcta y basta —*medir la línea de resumen y no el código de salida*—, pero su ejemplo cubre una sola causa. Se propone añadir la segunda al documento.

Y de paso: **había un `JoiabagurPV.API.exe` vivo (PID 25020) al empezar**, exactamente la primera vía. Se paró para poder medir y se volvió a levantar para el §4.

### 8.3. Dos heredoc de Bash reventaron por longitud — **defecto mío de herramienta; corregido**

Escribir bloques grandes con `cat > fichero <<'EOF'` falló dos veces: una con `ENAMETOOLONG: uv_spawn` y otra con `unexpected EOF while looking for matching`. Para bloques largos, la vía fiable en este entorno es escribir a un fichero con la herramienta de escritura y anexar con `cat >>`. Sin consecuencia sobre el resultado.

### 8.4. `SearchLexicalAsync` tiene un **HTTP 500 dormido** — hallazgo, anotado y **no arreglado a propósito**

`HydrateAsync` acepta `Guid?` **y agrupa** por producto con nulo, con un comentario que explica el peligro. `SearchLexicalAsync` acepta `Guid?` y **no agrupa**: `Carried(null)` suelta el filtro de tienda, así que un producto que tres tiendas llevan vuelve tres veces, y `BuildResultsAsync` hace `rows.ToDictionary(row => row.ProductId)` **incondicionalmente, en las dos ramas** → `ArgumentException` → **500**.

Hoy es código muerto: su único llamante pasa siempre una tienda concreta. Se activaría en cuanto la ruta rápida aceptara la ausencia, y **primero en desarrollo local**, donde `AiSearch__EnabledByDefault` no está declarado en ningún `appsettings` y la ruta degradada es la que corre siempre. **Queda anotado en `DEFERRED_TASKS.md` como una sola tarea con la extensión de la ruta rápida, y con el orden obligatorio: primero la agrupación y su test, después el DTO.**

### 8.5. El interruptor de la consulta libre no estaba en el compose de la demo — hallazgo, **corregido en este change**

`compose.demo.yaml` declaraba `AiSearch__EnabledByDefault` (C17) y `AiSalesAssist__EnabledByDefault` (C34) y **no** `AiFreeQuerySearch__EnabledByDefault` (C40). Con el valor por defecto a `false` y la lista vacía, en la demo `GET availability` respondía `switched_off` para **todas** las tiendas: el panel generativo de C40, apagado en el entorno cuyo único trabajo es enseñarlo. Es el fallo que el comentario situado tres líneas más arriba en ese mismo fichero describe palabra por palabra. Añadido con su comentario de clase.

---

## 9. Lo que esta pasada **no** verifica, dicho aquí

- **Cobertura con `coverlet`.** No se midió. El QA de C34 documenta que `coverlet` **no instrumenta el ensamblado `Application`** en este repositorio, que es donde cae casi todo el código nuevo, así que la cifra habría descrito la herramienta y no el cambio.
- **El operario con varias tiendas, en pantalla.** §6: no existe tal usuario en los datos sembrados. Cubierto por test de página.
- **El callejón sin salida, en pantalla.** El texto *«La búsqueda en todas las tiendas usa la respuesta asistida, y está desactivada»* tiene su test de página y **no se comprobó a ojo**: exigiría reiniciar la API sin `AiFreeQuerySearch__EnabledByDefault`.
- **La ruta rápida con ámbito global.** Fuera de alcance por decisión (§8.4). Lo que sí se verificó es que **responde 400**, que es la premisa de la decisión (§4).
- **`ai-service`.** Ni la suite de Python ni el contrato: el diff no los toca (§5).
- **La demo desplegada.** Este change añade su interruptor al compose, pero **no se desplegó** el entorno de demostración para comprobarlo allí. La verificación del §4 y del §6 es sobre el entorno local.
- **Telemetría del ámbito global.** Sigue siendo tarea diferida de C40: una búsqueda global **no se registra**, así que su uso no es medible. El recorte al administrador la vuelve marginal, y eso refuerza el motivo para diferirla en vez de erosionarlo.
- **La suite del frontend no se ejecutó con `npm run build`** al cierre; sí `tsc --noEmit` filtrado, que es la puerta que este repositorio documenta como la única que ve un error de tipos.

---

## 10. Estado final

| | |
|---|---|
| Tareas | **38 / 38** |
| `openspec validate --all --strict` | **63 passed · 0 failed** |
| Frontend | 113 → **114** en rojo · **1** nombre nuevo, el documentado como rotatorio · área propia **verde** |
| Backend | 45 → **52** con error · **11** nombres difieren, 10 en la clase no determinista · área propia **verde** |
| Tests nuevos | **24 casos** de 21 declaraciones · la aritmética de las dos suites cierra |
| Contrato · migraciones | sin diff · ninguna |
| Commit | **ninguno**, a petición del desarrollador |
