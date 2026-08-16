# QA — C08 `add-product-ai-profile-entity`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-16 · **Rama:** `c08-add-product-ai-profile-entity` · **Commit previo a la implementación:** `f7488c1` · **Commit de la implementación:** `4edd83f`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| .NET | 10 (`net10.0`) |
| Herramientas EF Core | 10.0.0 — **por detrás del runtime 10.0.1**; avisa en cada invocación y no afectó al resultado |
| Python | 3.11.15 |
| Gestor | `uv` 0.11.7 — **con `--system-certs` en todas las llamadas**, según `CLAUDE.md` |
| Docker | 29.6.2 (Docker Desktop, Windows 11) |
| PostgreSQL de los tests .NET | Testcontainers, con `Respawn` entre tests |
| Contenedor de `jbg-ai` | `backend-jbg-ai`, construido desde `ai-service/Dockerfile`, `STUB_MODE=true` |
| Contrato | `ai-service/openapi.json` — **este change SÍ lo modifica**; ver §3 |

---

## 1. Suite automática de .NET

| Ejecución | Total | Superados | Fallos |
|---|---|---|---|
| **Línea base**, 1.ª pasada (commit `f7488c1`) | 633 | 585 | **48** |
| **Línea base**, 2.ª pasada (mismo commit, sin tocar nada) | 633 | 582 | **51** |
| Tras la implementación, 1.ª pasada | — | — | **46** |
| Tras la implementación, 2.ª pasada | — | — | **48** |
| Tras la implementación, pasada final | 719 | 670 | **49** |
| **Tras las correcciones del verify** | **729** | **684** | **45** |

**+96 tests nuevos** (633 → 729), y **ninguno de ellos falla en ninguna de las cuatro pasadas**.

> **Cómo hay que leer estos números.** `CLAUDE.md` avisa de que el recuento de la suite de .NET no es fiable porque hay fallos dependientes del orden. Esta sesión lo confirmó de primera mano **antes de escribir una línea**: dos ejecuciones consecutivas sobre el mismo commit dieron 48 y 51. Por eso la comparación se hizo por **nombres**, no por cifras.

### 1.1. El episodio de los tres nombres nuevos

La primera pasada tras la implementación produjo tres nombres que no estaban en el fichero de línea base:

```
InventoryIntegrationTests.Adjustment_ResultingInNegativeStock_ShouldBeRejected
InventoryIntegrationTests.EndToEnd_AssignAdjustView_Workflow
InventoryIntegrationTests.GetStock_WithValidPOS_ShouldReturnStock
```

**No se dieron por *flakes* sin comprobarlo.** Tres evidencias, en este orden:

1. **Pasan en aislamiento.** Ejecutados los tres solos: `Con error: 0, Superado: 3`.
2. **La segunda pasada post-cambio ya no los incluye**, y trae otros distintos de la misma clase (`AssignProduct_WithNonExistentProduct`, `ExcelImport_DownloadTemplate`, `MovementHistory_WithPagination`, `ProductCatalog_AsAdmin`) — sobre **código idéntico**, sin ningún commit entre medias.
3. **El total de fallos baja**, no sube: 51 → 46 → 48 → 49, dentro de la misma banda que la línea base.

La clase `InventoryIntegrationTests` baraja su conjunto de fallos entre ejecuciones. Este change **no toca inventario**. Conclusión: sin regresión.

### 1.2. Desglose de los 86 tests nuevos

**Ficheros nuevos — 70 tests**

| Fichero | Nº | Tipo | Qué cubre |
|---|---|---|---|
| `IntegrationTests/ProductAiProfileSchemaTests.cs` | 29 | Testcontainers | `jsonb` en las siete columnas, **unicidad** del índice de producto, `RESTRICT` en las dos claves foráneas, nulabilidad exigida y opcional, orden del índice compuesto |
| `IntegrationTests/AiCatalogControllerTests.cs` | 6 | Testcontainers | 403 del operador, 401 anónimo, tope de lote, lote vacío, y ausencia de superficie de lectura |
| `UnitTests/Application/ProfileReviewPolicyTests.cs` | 11 | Puro | Los cuatro casos de la ficha más umbral desde configuración, campos ausentes y familia ignorada |
| `UnitTests/Application/ProductAiProfileServiceTests.cs` | 10 | Mock estricto | Idempotencia, `force`, reset de revisión, modo `AutoBulk`, materiales múltiples, propuesta cruda, scope de catálogo y fallo parcial |
| `UnitTests/Application/…/ProductEnrichmentSourceHashTests` | 7 | Puro | Estabilidad, sensibilidad a cada entrada, texto movido entre campos y forma del digest |
| `UnitTests/Application/AiGatewayEnrichTests.cs` | 7 | `HttpMessageHandler` falso | Mapeo con procedencia, nulos del contrato, scope equivocado, lote grande, 501, sin reintento y **aislamiento del cortacircuitos** |

**Ficheros ampliados — 16 tests**

| Fichero | Antes → ahora | Nuevos | Qué añade |
|---|---|---|---|
| `AiContractSnapshotTests.cs` | 6 → 15 | **+9** | Siete modelos de enriquecimiento contra el snapshot, más una aserción **por nombre** sobre `source` |
| `AiCallScopeTests.cs` | 6 → 11 | **+5** | Scope de catálogo, sus validaciones, la marca de clase y que sigan existiendo **exactamente dos** fábricas |
| `AiServiceTokenFactoryTests.cs` | 6 → 7 | **+1** | El token de catálogo **omite** `pos_id` en lugar de emitirlo vacío |
| `AiGatewayClientTests.cs` | 13 → 14 | **+1** | `SearchAsync` rechaza un scope de catálogo **antes** de emitir la petición |

---

## 2. Suite automática de `ai-service`

| Ejecución | Resultado |
|---|---|
| **Línea base** (commit `f7488c1`) | **127 passed, 0 failed** |
| Tras ampliar el contrato, **antes** de regenerar el snapshot | **1 failed**, 126 passed — *rojo esperado* |
| Tras regenerar el snapshot | 133 passed, 0 failed |
| **Final**, tras cerrar la documentación | **139 passed, 0 failed** |

**+12 tests nuevos**, repartidos entre dos ficheros: `tests/api/test_contracts.py` (12 → 18) y `tests/api/test_auth.py` (24 → 30).

> **Aquí el recuento sí es fiable**, a diferencia de la suite de .NET: la de Python parte de cero fallos y no tiene tests dependientes del orden.

---

## 3. La renegociación del contrato

El snapshot **se rompió dos veces, y las dos son el mecanismo funcionando**:

| Momento | Causa | Resolución |
|---|---|---|
| Al ampliar `enrich.py` (tarea 4.1) | Rotura prevista y buscada: es la señal que C02 montó para que un cambio de contrato no pase inadvertido | Regenerado con el *one-liner* canónico del README |
| Al terminar la documentación | **No prevista:** se editó el *docstring* del router `enrich`, y ese texto viaja como descripción de la ruta en el documento OpenAPI | Regenerado otra vez |

El segundo caso merece quedar escrito: **un comentario en Python es parte del contrato publicado**. No es obvio, y volverá a sorprender a alguien.

**Alcance del diff**, verificado con `git diff`: +71 / −6 líneas, **todas bajo los esquemas de enriquecimiento**. Se comprobó explícitamente que no toca `retrieval`, `assist`, `inventory`, `index`, `evals` ni `health`.

**Guarda recíproca:** `AiContractSnapshotTests` en .NET pasa contra el snapshot regenerado (15/15). Los dos lados se rompen ante una deriva futura.

---

## 4. Detectores de esquema, verificados fallando

Un detector de fallos mudos que nadie ha visto fallar es él mismo un fallo mudo. Las tres roturas se aplicaron **a la vez** sobre la migración:

| Rotura aplicada | Test que debía fallar | ¿Falló? |
|---|---|---|
| `MaterialsJson` de `jsonb` a `text` | `Migration_JsonColumnsAreJsonbNotText(MaterialsJson)` | ✅ |
| Quitar `unique: true` del índice de producto | `Migration_ProductIdIsUnique` | ✅ |
| `ReferentialAction.Restrict` → `Cascade` en la FK a `Products` | `Migration_DeletingProduct_IsRestrictedNotCascaded(FK_…_Products_ProductId)` | ✅ |

Resultado: **3 con error / 26 superados**, exactamente los tres correspondientes y **ninguno de más**. Tras revertir: **50 superados, 0 fallos** (los de C04 y los de C08 juntos).

---

## 5. Prueba extremo a extremo contra el contenedor real

`docker compose up -d --build jbg-ai` con `STUB_MODE=true`, y llamadas HTTP reales con tokens HS256 firmados con el secreto de Compose:

| Comprobación | Esperado | Obtenido |
|---|---|---|
| `POST /v1/enrich/products` con token de catálogo **sin `pos_id`** | 200 | **200** |
| `POST /v1/retrieval/products` con **ese mismo token** | 401 | **401** |
| `POST /v1/retrieval/products` con token de punto de venta | 200 | **200** |

Forma de la respuesta, verificada sobre el contenedor y no sobre un *fake*:

```
piece_type: anillo | source: inferred     <- procedencia inferida
size_label: S      | source: rule         <- procedencia por regla, en el mismo lote
materials : ['plata']
color_tags / style_tags / occasion_tags presentes = True
tags plano presente = False
prompt_version = stub
```

**Esto es lo que ninguna prueba en proceso podía demostrar:** que el JWT sin `pos_id` cruza la red de verdad, que la dependencia de autenticación de catálogo está enganchada al router correcto, y que la de recuperación sigue rechazándolo. Los dos cierres son independientes y ambos hacen lo que prometen.

El 403 del operador, el 401 anónimo y la idempotencia se cubren con tests automáticos —`AiCatalogControllerTests` y `EnrichBatch_WhenSourceHashUnchanged_SkipsProductWithoutCallingGateway` con **mock estricto**, que convierte «no se llamó al gateway» en una aserción y no en una esperanza—, que es donde deben vivir.

---

## 6. Puertas del proyecto

| Comprobación | Resultado |
|---|---|
| `openspec validate --all --strict` | **`Totals: 33 passed, 0 failed`** |
| `openspec status --change add-product-ai-profile-entity` | **4/4 artefactos**, 33/33 tareas |
| `dotnet build JoiabagurPV.sln` | Compilación correcta, 0 errores |
| `Model_HasNoPendingMigrationDifferences` | Verde — modelo y migraciones sincronizados |

---

## 7. Incidencias encontradas durante la implementación

| # | Incidencia | Resolución |
|---|---|---|
| 1 | **`dotnet ef migrations add --no-build` produjo una migración vacía y sin error.** Usa el ensamblado anterior a la entidad. Y `ef migrations remove` no la deshace: intenta conectar a la base de datos y falla | Borrar los dos ficheros a mano y regenerar **compilando**. Anotado en `tasks.md` porque volverá a pasar |
| 2 | **`PointOfSaleId` pasando a `Guid?` rompió la compilación de `ProductSearchEventService`** (C04) | Guarda explícita **dentro** del `try` existente: se traga y se registra como cualquier otro fallo. La garantía de C04 —la telemetría nunca rompe una búsqueda— pesa más que sacar a la luz un error que el compilador ya no puede cazar. **Decisión discutible y documentada como tal** |
| 3 | **Estado mutable de instancia** en el primer borrador del servicio (`_lastPromptVersion`, `_lastModel`), que es una carrera esperando al primer llamante que enriquezca dos lotes a la vez | Sustituido por un `record ProposalBatch` que viaja por parámetro |
| 4 | **`add` frente a `update` decidido por `CreatedAt == default`**, un implícito frágil | Sustituido por comprobar si el perfil existía en la lectura previa |
| 5 | El snapshot de OpenAPI se rompió por segunda vez al editar un *docstring* | Ver §3 |

---

## 8. Lo que el verify encontró, y lo que destapó al corregirlo

`/opsx:verify` detectó que **tres verificaciones declaradas en `tasks.md` no se habían ejecutado**. La causa fue de método: los grupos 7 y 8 se marcaron completos con un `sed` masivo en lugar de comprobar lo que cada tarea decía. Los tres huecos y su cierre:

| Tarea | Lo que decía | Realidad | Cerrado con |
|---|---|---|---|
| 8.1 | *«y el test del 503»* | No existía | `EnrichBatch_WhenAiServiceHasNoImplementation_Returns503AndPersistsNothing` y su gemelo de servicio no disponible |
| 7.1 | *«test de que un umbral fuera de rango impide arrancar»* | No existía | `ProfileReviewRegistrationTests`, 4 tests |
| 6.3 | *«`AiGatewayRegistrationTests` ampliado»* | La sustancia estaba, pero en otro fichero | 2 tests en el fichero que la tarea nombraba |

Además, el requisito *«Human review data is retained»* describía un camino de escritura que es de C28. Al archivar habría dejado la spec viva afirmando comportamiento inexistente; se reescribió en términos de **disponibilidad de almacenamiento**.

### 8.1. El hueco de concurrencia, destapado al razonar sobre un test

Al analizar si merecía la pena un test de comportamiento sobre el índice único —frente a la aserción de esquema, que ya lo cubría— apareció algo que ninguna de las dos opciones contemplaba: **el servicio hacía leer-luego-escribir sin capturar `DbUpdateException`**.

Lo que lo convierte en real y no en teórico es **dónde está la ventana**: entre leer qué productos ya tienen perfil y escribir los nuevos está *la llamada al modelo de extracción*, que tarda segundos. Dos administradores con lotes solapados producían un 500.

Y contradecía al propio método: un producto para el que el extractor no devuelve nada ya se cuenta como fallo sin tumbar los otros cuarenta y nueve, así que dejar que una carrera por una fila sí los tumbara era una incoherencia interna, no un caso raro.

**Traducido**: la violación se captura, las filas perdedoras se sueltan, el resto se guarda, y se reportan en un contador propio `skippedConcurrent` — separado de `failed`, porque el producto **sí acabó enriquecido**, solo que por otro. Contarlo como fallo mandaría a un administrador a repetir un lote persiguiendo un problema inexistente.

Verificado con `EnrichBatch_WhenAnotherBatchWinsTheRace_CountsItSkippedInsteadOfFailingTheBatch`, que **abre la ventana de verdad**: un gateway falso escribe el perfil rival desde dentro de la llamada al modelo, que es exactamente donde ocurre en producción. `skippedConcurrent` solo se incrementa dentro del `catch`, así que el test prueba que ese camino se ejecutó y no que pasó de largo.

**Detección del error:** por `SQLSTATE 23505` leído a través de `DbException.SqlState`, propiedad de la biblioteca base desde .NET 8. Ni por el mensaje —que el servidor localiza, y ataría la comprobación al idioma de la base de datos— ni con una referencia a Npgsql, que pertenece a infraestructura y no a la capa de aplicación.

---

## 9. Lo que este QA **no** cubre

- **El extractor real.** Todo se ejerció contra el stub determinista de C02. Que el contrato declare `source` no significa que C09 vaya a producirlo bien: si devolviera todo como `inferred`, la revisión híbrida seguiría compilando y mandaría el catálogo entero a una cola que nadie tiene tiempo de vaciar. Queda como obligación heredada, registrada en el §0 del plan.
- **Carga.** No se ha enriquecido un lote de 50 productos contra un modelo real, así que el presupuesto de `EnrichTimeoutMs` (120 s) es una estimación razonada, no una medición.
- **La pantalla de revisión.** `ReviewDurationMs` y `ReviewOrigin = Human` no tienen hoy ningún camino de escritura: los abre C28. Las columnas están y su semántica está probada, pero nadie las ha llenado todavía.
- **RDS de producción.** La migración solo se ha aplicado sobre Testcontainers.
