# QA — C04 `add-product-search-event-tracking`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-11 · **Rama:** `c04-add-product-search-event-tracking` · **Commit previo a la implementación:** `e107c1a`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| SDK | .NET 10.0.302 |
| Proyecto de test | `backend/src/JoiabagurPV.Tests/JoiabagurPV.Tests.csproj` |
| Base de datos | PostgreSQL 15 en Testcontainers, con Docker levantado |
| Herramienta nueva en la máquina | `dotnet-ef` 10.0.0 como herramienta global — no existía y el README del backend la asume |
| Contrato | `ai-service/openapi.json`, **leído** para derivar la longitud del texto de consulta, no modificado |

---

## 1. Suite automática

| Ejecución | Total | Fallos |
|---|---|---|
| **Línea base** (`git stash push -u`, sin código de C04) | 585 | **52** |
| Tras la implementación | 628 | **46** |

**43 tests nuevos, todos en verde.** `dotnet build`: **0 errores**.

La línea base se **midió**, no se supuso: se guardó el árbol completo con `git stash push -u`, se ejecutó la suite sobre `e107c1a` y se recuperó con `git stash pop`. Los fallos bajaron de 52 a 46 al añadir el change, lo que por sí solo descarta una regresión y revela que parte del conjunto es no determinista.

### Desglose de los 43 tests nuevos

| Fichero | Nº | Qué cubre |
|---|---|---|
| `UnitTests/Application/ProductSearchEventServiceTests` | 15 | Proyección, truncado, contador real, origen degradado, episodio, derivación de rank, producto ausente, última escritura, propiedad, no propagación de fallos, confidencialidad del texto |
| `IntegrationTests/ProductSearchEventSchemaTests` | 20 | Tipos `jsonb`, longitud del texto, orden del índice compuesto, nulabilidad de doce columnas, las cuatro reglas de borrado |
| `UnitTests/Persistence/MigrationModelDriftTests` | 1 | Desfase entre el modelo y el snapshot de migraciones, **sin base de datos** |
| `IntegrationTests/AiSearchEventsControllerTests` | 7 | 204 con rank derivado, 403 ajeno, 403 administrador, 404, 401, `SET NULL` real, ciclo completo |

### Los escenarios del spec, uno a uno

| Escenario | Test | Resultado |
|---|---|---|
| 1 · Búsqueda registrada con los campos del servidor | `RecordSearch_WithValidScope_PersistsEventWithServerKnownFields` | ✅ |
| 2 · Búsqueda degradada distinguible | `RecordSearch_WhenOriginIsLexicalFallback_PersistsDistinguishableOrigin` | ✅ |
| 3 · Búsqueda sin resultados | `RecordSearch_WithNoResults_PersistsZeroCountAndEmptyArray` | ✅ |
| 4 · Fallo de telemetría no propaga | `RecordSearch_WhenPersistenceFails_DoesNotThrowAndReturnsNull` | ✅ |
| 5 · Rank derivado en el servidor | `RecordSelection_WithProductInResults_DerivesRankFromStoredList` | ✅ |
| 6 · Producto ausente con rank nulo | `RecordSelection_WhenProductNotInResults_PersistsSelectionWithNullRank` | ✅ |
| 7 · Selección repetida, última gana | `RecordSelection_WhenCalledTwice_KeepsLastSelection` | ✅ |
| 8 · 403 por propiedad, sin excepción de administrador | `RecordSelection_WhenEventBelongsToAnotherUser_Returns403` · `..._WhenCallerIsAdminButNotOwner_Returns403` | ✅ |
| 9 · Truncado por entradas, contador real | `RecordSearch_WithMoreResultsThanCap_StoresOnlyTheCap` · `..._RecordsTrueDisplayedCount` | ✅ |
| 10 · Episodio agrupable | `RecordSearch_WithSessionId_KeepsTheCallerEpisode` | ✅ |
| 11 · Venta declara su búsqueda | `FullCycle_ProjectingARealGatewayResponse_RoundTripsThroughJsonbIntact` | ✅ |
| 12 · Purgar telemetría no destruye ventas | `DeletingSearchEvent_NullsSaleAttribution_WithoutDeletingSale` | ✅ |
| 13 · Texto de consulta no sube de `Debug` | `RecordSearch_QueryTextNeverRisesAboveDebug` | ✅ |
| 14 · Esquema verificado | `Migration_JsonColumnsAreJsonbNotText` · `..._CompositeIndexOrdersPointOfSaleBeforeCreatedAt` · `..._BusinessEntitiesDoNotCascadeIntoTelemetry` · `Model_HasNoPendingMigrationDifferences` | ✅ |
| 15 · Fuera de alcance explícito | Revisión de alcance (§5) | ✅ |

---

## 2. Revisión línea a línea de la migración

El `.cs` generado se leyó entero antes de aceptarlo, porque es el fichero que nadie mira en una revisión y donde los errores no dan error:

| Comprobación | Esperado | En la migración |
|---|---|---|
| `FiltersJson`, `ResultsJson` | `jsonb` | ✅ `jsonb` |
| `SearchText` | 500, del contrato congelado | ✅ `character varying(500)` |
| `TraceId` | acotado y nullable | ✅ `character varying(64)`, nullable |
| Índice compuesto | `PointOfSaleId` **antes** de `CreatedAt` | ✅ `{ "PointOfSaleId", "CreatedAt" }` |
| Evento → usuario / POS / producto | `Restrict` | ✅ los tres |
| Venta → evento | `SetNull` | ✅ `FK_Sales_ProductSearchEvents_SearchEventId` |

**Desviación aceptada:** EF generó además `IX_ProductSearchEvents_UserId` e `IX_ProductSearchEvents_SelectedProductId`, índices automáticos de clave foránea. Se conservan: las reglas `Restrict` obligan a la base a comprobar filas referenciadas antes de borrar un usuario o un producto, y sin ellos esa comprobación sería un recorrido secuencial. Recogido como precisión en la decisión 12 del [design](design.md).

---

## 3. El arnés probado contra sí mismo

La tarea 3.4 pedía comprobar que el arnés **falla** cuando el esquema no es el esperado. Un ayudante que devolviera siempre lo que el test espera pasaría igual y no protegería nada.

Se escribió un test desechable que afirmaba lo contrario en tres puntos y se ejecutó:

| Aserción invertida | Lo que devolvió el catálogo | ¿Falló? |
|---|---|---|
| `ResultsJson` es `text` | `jsonb` | ✅ |
| Índice compuesto en orden `CreatedAt, PointOfSaleId` | `PointOfSaleId, CreatedAt` | ✅ |
| Regla de borrado hacia la venta es `CASCADE` | `SET NULL` | ✅ |

Los tres fallaron como debían, confirmando que el ayudante lee el catálogo real. El fichero se borró acto seguido.

---

## 4. Los 52 fallos preexistentes: diagnóstico, no suposición

Es la parte más larga de este QA porque la primera lectura fue **equivocada** y la corrección tiene valor para el resto del proyecto.

### Lo que se dijo primero, y por qué era incorrecto

La primera conclusión fue *«fallos preexistentes y flaky, el recuento varía entre ejecuciones»*. La variación es cierta, pero «flaky» no describe el conjunto: al abrir los mensajes aparecieron fallos **deterministas** con causas concretas, incluidos tests unitarios puros que no tocan base de datos ni red. Documentar «flaky» habría enterrado cinco defectos distintos bajo una etiqueta que invita a ignorarlos.

### Diagnóstico verificado

Los dos árboles se comportan de forma distinta, y ahí está la explicación:

| Árbol | Tests | Fallos | Desde cuándo se sabe |
|---|---|---|---|
| `UnitTests/` | 315 | **10** | El QA de C03 (2026-08-09) registró exactamente estos 10, **nombre por nombre** |
| `IntegrationTests/` | 270 | **~42** | **Nunca se habían medido** |

C03 registró «315 total» — que es **exactamente el recuento del árbol unitario**. Los de integración necesitan Docker y en aquella sesión no llegaron a ejecutarse. Y en CI tampoco: [`test-backend.yml`](../../../.github/workflows/test-backend.yml) corre la solución completa sobre `ubuntu-latest`, que sí tiene Docker, **pero solo se dispara en `push`/`pull_request` a `main` y `develop`**, y todo el Proyecto Final se está construyendo en `ai-eng` y sus ramas de change. Un árbol de 270 tests lleva semanas sin ejecutarse ni en local ni en CI.

Eso no es una suite que se haya podrido: es una suite que nadie estaba mirando.

### Familias identificadas

**Unitarios (10, estables desde C03):** umbrales de tamaño comprimido escritos contra una versión anterior de ImageSharp (5); `MissingMethodException` sobre `ImageSharp.Image.Load` por incompatibilidad binaria con `PdfSharpCore`, más un PDF sin páginas (2); expectativas de Moq sobre transacciones que el servicio ya no invoca (2); una validación de importación (1). Los dos primeros son **deriva de dependencias**, no lógica rota.

**Integración (~42):** dieciséis del tipo «se esperaba 401 y llegó 200/403/201», porque el `HttpClient` compartido de la clase es el que hace los `login` y **arrastra sus cookies**; cuatro de `Cannot create a DbSet for 'TestEntity'`; cuatro de `22001: value too long for character varying(20)`, **la única familia genuinamente no determinista** y la que explica que dos ejecuciones del mismo código den recuentos distintos; el resto, casos sueltos.

### Dos de esas familias se toparon dentro de este change

No son teoría: aparecieron escribiendo los tests nuevos y se corrigieron en ellos, así que el patrón de arreglo ya está escrito.

| Familia | Cómo se manifestó aquí | Corrección |
|---|---|---|
| Cliente compartido con cookies | `RecordSelection_WhenUnauthenticated_Returns401` devolvió **204**: la llamada «anónima» llevaba las cookies de los logins previos | Pedir un cliente nuevo a la factoría para la aserción anónima |
| Dato generado que no cabe | `22001` intermitente al crear el punto de venta: Bogus genera teléfonos de longitud variable y la columna es `varchar(20)` | Fijar el campo con `.WithPhone("600123456")`, como ya hacía `SalesControllerTests` |

### Dónde queda registrado

- **[CLAUDE.md](../../../CLAUDE.md)** — la regla operativa duradera: un recuento en rojo no es señal de regresión, se compara **por nombres** contra la línea base, y las dos trampas concretas con las que tropezará quien escriba el siguiente test. Sin cifras, que caducan.
- **[Documentos/testing-backend.md](../../../Documentos/testing-backend.md)**, sección *Estado de la suite: fallos conocidos* — el inventario fechado con causas raíz, la explicación del hueco de CI y el orden de rentabilidad para cerrarlo.
- Este QA — lo medido en este change.

**No se ha arreglado ninguno**, y es deliberado: no son de este change y tocarlos habría mezclado dos cosas distintas en un mismo diff. **Merece un change propio**, y el primer punto —extender el disparador de CI a las ramas de trabajo— es el que impide que siga creciendo en silencio.

---

## 5. Comprobaciones de disciplina y alcance

| Comprobación | Resultado |
|---|---|
| `openspec validate --all --strict` | ✅ **31 passed, 0 failed** |
| Ninguna ruta de lectura sobre eventos | ✅ el único endpoint es la selección |
| Sin propiedades de navegación en la entidad | ✅ |
| `ProductSearchEvent` sin `CreatedSaleId` | ✅ el enlace vive en `Sale.SearchEventId` |
| Contrato `ai-service/openapi.json` sin tocar | ✅ solo leído |
| Frontend, `ai-service/`, `terraform/` sin cambios | ✅ |
| Una sola migración | ✅ `20260811061759_AddProductSearchEventTracking` |
| El DTO del cliente tiene un solo campo | ✅ `{ productId }` |

---

## 6. Decisiones tomadas durante la aplicación

| Qué | Decisión | Motivo |
|---|---|---|
| Tarea 1.5, repositorio dedicado | **Descartada** | `IRepository<T>` ya expone `GetByIdAsync`, `AddAsync` y `UpdateAsync`, y está registrado genéricamente. Una interfaz dedicada sería un marcador vacío más una línea de DI |
| Espacio de nombres del test de desfase | `UnitTests.Persistence`, no `UnitTests.Infrastructure` | Dentro de `...Infrastructure` la directiva `using Microsoft.EntityFrameworkCore.Infrastructure` no resuelve: las directivas se buscan primero contra los espacios de nombres contenedores |
| Aserción sobre `ResultsJson` en integración | Sobre el JSON parseado, no sobre el texto | **`jsonb` normaliza el documento**: reordena claves y reescribe separadores. Una aserción por subcadena estaría comprobando el formateo de PostgreSQL, no la proyección |
| Borrado del evento en el test de `SET NULL` | SQL directo | Con EF, el arreglo en memoria anularía la referencia aunque el esquema no estuviera de acuerdo; lo que se quiere probar es la restricción de la base |

---

## 7. Lo que **no** se ha comprobado

- **El camino real de C15**: nadie invoca todavía `RecordSearchAsync` desde un endpoint de búsqueda. La obligación A1 está escrita en el proposal y en la ficha de C15, pero hasta que ese change llegue, la tabla solo se llena desde tests.
- **La escritura de `Sale.SearchEventId`**: la columna existe y su regla de borrado está probada, pero ningún camino de aplicación la escribe. La regla «identificador desconocido ⇒ atribución nula, venta intacta» está especificada y **no implementada**, por lo que tampoco está probada.
- **Volumen real**: los índices se justifican por opción de futuro, no por medición. A ~3.000 filas no hay nada que medir.
- **La reversión de la migración**: omitida con motivo escrito — es generada, no artesanal, y probarla exigiría un contenedor propio.

---

## 8. Riesgos vivos tras la verificación

| Riesgo | Estado |
|---|---|
| C15 no invoca el servicio y el change queda inerte **sin síntoma** | Vivo. Mitigado solo por escrito: proposal + ficha de C15 |
| Los ~42 fallos de integración siguen sin ejecutarse en las ramas de trabajo | Vivo. Documentado, sin arreglar; requiere change propio |
| La regla C1 (identificador desconocido ⇒ nulo) se implementa mal al conectar la venta | Vivo. Especificada, no implementada, no probada |
| Bloqueo de la migración única sobre C07, C08, C19, C27 y C29 | Vivo mientras el change no se archive |

---

## Veredicto

**Apto.** 43 tests nuevos en verde, migración revisada línea a línea y verificada contra el catálogo real, arnés probado contra sí mismo, y `openspec validate --all --strict` en `0 failed`. Los 52 fallos preexistentes quedan medidos, diagnosticados por familias y registrados en los dos sitios donde alguien los buscará; ninguno pertenece a este change y ninguno se ha tocado.
