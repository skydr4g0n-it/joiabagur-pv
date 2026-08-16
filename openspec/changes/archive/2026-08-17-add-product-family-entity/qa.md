# QA — C07 `add-product-family-entity`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-16 / 2026-08-17 · **Rama:** `c07-add-product-family-entity` · **Commit previo a la implementación:** `34c254d` · **Commit de la implementación:** `05a7ddf`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| .NET | 10 (`net10.0`) |
| Herramientas EF Core | 10.0.0 — **por detrás del runtime 10.0.1**; avisa en cada invocación y no afectó al resultado |
| Docker | 29.6.2 (Docker Desktop, Windows 11) |
| PostgreSQL de los tests | Testcontainers (`postgres:15`), con `Respawn` entre tests de API y migración real en `TestDatabaseFixture` |
| `ai-service` | **No se ejecuta**: este change no cruza la frontera. Ver §6 |
| Contrato | `ai-service/openapi.json` — **este change NO lo modifica** |

---

## 1. Suite automática de .NET

| Ejecución | Total | Superados | Fallos | Duración |
|---|---|---|---|---|
| **Línea base** (commit `34c254d`, antes de escribir código) | 729 | 680 | **49** | 12 m 24 s |
| Tras la implementación | 762 | 717 | **45** | 8 m 41 s |
| **Tras las correcciones del verify** | **771** | **727** | **44** | 9 m 21 s |

**+42 tests nuevos**, y **ninguno de ellos falla en ninguna de las dos pasadas**. Los fallos bajan de 49 a 44.

> **Cómo hay que leer estos números.** `CLAUDE.md` avisa de que el recuento de esta suite no es fiable: hay fallos dependientes del orden y dos pasadas idénticas dan conjuntos distintos. La comparación válida es por **nombres**, y así se hizo. La banda documentada es 45-51; ambas ejecuciones caen dentro.

**Sobre el `git stash` de la tarea 1.1.** Resultó innecesario: el árbol estaba limpio tras commitear los artefactos, así que **HEAD era la línea base** y medirla ahí es equivalente y más simple. Queda anotado porque la instrucción del plan asume un árbol sucio.

### 1.1. Los nombres nuevos, comprobados y descartados

La comparación se hizo por nombres en las dos pasadas, y en ninguna coincidieron los nombres nuevos — que es en sí la prueba de que son ruido y no regresión.

| Pasada | Fallos de la línea base que desaparecen | Nombres nuevos |
|---|---|---|
| Tras la implementación | 7 | 3: `InventoryIntegrationTests.GetStock_WithNonExistentPOS_ShouldReturnEmpty`, `InventoryIntegrationTests.Operator_AccessCentralizedInventory_ShouldBeForbidden`, `PaymentMethodsControllerTests.Update_WithValidData_ShouldReturnUpdatedPaymentMethod` |
| Tras el verify | 6 | 1: `InventoryIntegrationTests.ExcelImport_NegativeQuantityExceedingStock_ShouldReturnErrorAndLeaveStockUnchanged` |

**Ninguno se dio por *flake* sin comprobarlo.** Cuatro evidencias:

1. **Todos pasan en aislamiento.** Los tres de la primera pasada: `Con error: 0, Superado: 3` en 6 s. El de la segunda: `Con error: 0, Superado: 1` en 13 s.
2. **Los conjuntos no se solapan.** Ninguno de los tres primeros reaparece en la segunda pasada, sobre código que solo ganó tests. Un fallo real no se cura solo.
3. **Este change no toca inventario ni métodos de pago.** El diff sobre `backend/` se limita a ficheros nuevos de familia más tres registros de DI, dos `DbSet` y una ruta añadida a `ProductsController`.
4. **El total de fallos baja** en las dos pasadas: 49 → 45 → 44.

Es el mismo fenómeno que C08 registró en su QA, con otros nombres de la misma clase `InventoryIntegrationTests`. **Conclusión: sin regresión.**

### 1.2. Desglose de los 33 tests nuevos

| Fichero | Tests | Qué cubre |
|---|---|---|
| `IntegrationTests/ProductFamilySchemaTests.cs` | **17** | Los tres índices únicos, el orden de columnas del compuesto, las dos reglas de borrado, nulabilidad de las columnas de aprobación y de la etiqueta, columnas obligatorias, y que `Origin` sea `integer` y no un tipo enumerado nativo |
| `IntegrationTests/ProductFamiliesControllerTests.cs` | **25** | Creación con orden, corrección de metadatos, conflicto por doble pertenencia y por carrera perdida, lectura de hermanos, baja sin disolver, vaciado, reordenado, intercambio de etiquetas, ámbito de la etiqueta por familia, cortocircuito de no-operación, etiquetas duplicadas y ausentes, producto repetido, nombres repetidos entre familias, huérfano frente a inexistente, y la matriz de autorización completa |

Los cuatro tests que la ficha del plan pedía están, con sus nombres exactos: `CreateFamily_WithMembers_PersistsOrder`, `AddMember_WhenProductAlreadyInAnotherFamily_ReturnsConflict`, `GetFamily_ReturnsSiblingsOrderedBySortOrder` y `RemoveMember_KeepsFamilyWhenOthersRemain`.

### 1.3. Los nueve tests añadidos tras el verify

`/opsx:verify` encontró **cinco escenarios de la spec sin cubrir** —dos críticos y tres avisos—, todos en rutas que «obviamente funcionaban». Se cerraron los cinco:

| Test añadido | Escenario de la spec que cubre |
|---|---|
| `UpdateFamily_ChangesNameAndDescription_LeavesMembersUntouched` | *A family's name and description can be corrected afterwards* |
| `UpdateFamily_WhenFamilyDoesNotExist_Returns404` · `GetFamilyById_WhenFamilyDoesNotExist_Returns404` | Lectura y corrección de una familia inexistente |
| `CreateFamily_WithNameUsedByAnotherFamily_Succeeds` | *Two families may carry the same name* |
| `ReplaceMembers_WithLabelUsedInAnotherFamily_Succeeds` | *The same label may be reused in a different family* |
| `UpdateFamily_AsOperator_Returns403` · `ReplaceMembers_AsOperator_Returns403` | *An operator cannot create **or modify** a family* — antes solo se afirmaba la mitad |
| `ReplaceMembers_Unauthenticated_Returns401` | *An unauthenticated caller is rejected* en **cualquier** endpoint, no solo el `POST` |
| `ReplaceMembers_WhenAnotherWriterWinsTheRace_ReturnsConflictInsteadOfServerError` | *A concurrent write does not surface as a server error* |

**El más serio era el primero.** `PUT /api/product-families/{id}` estaba implementado y **no lo ejercía nada**: `grep -c UpdateProductFamilyRequest` sobre el fichero de tests devolvía 0. «Editable» es la palabra que justifica que esta entidad exista —la clave textual que sustituye no la podía corregir un administrador—, así que era precisamente la promesa del change la que no tenía prueba.

**El de la carrera** merece nota aparte porque cambia el estado de una afirmación: la traducción del `23505` a 409 estaba escrita y **supuesta**. Ahora está **probada**. La ventana se abre de forma determinista con `RaceBlindFamilyRepository`, que deja a la comprobación previa mirar una sola vez y no ver nada —el estado exacto en el que está un escritor cuando otro confirma primero— y deja intacta la segunda lectura, que es la que permite que el 409 siga nombrando a la familia ganadora. Correr dos peticiones de verdad habría dado un test que pasa o falla según el reloj.

---

## 2. Detectores de esquema, verificados fallando

Un detector de fallos mudos que nadie ha visto fallar es él mismo un fallo mudo. Las tres roturas se aplicaron **a la vez** sobre la migración:

| Rotura aplicada | Test que debía fallar | ¿Falló? |
|---|---|---|
| Quitar `unique: true` de `IX_ProductFamilyMembers_ProductId` | `Migration_ProductIdIsUnique` | ✅ |
| `Restrict` → `Cascade` en la FK a `Products` | `Migration_DeletingProduct_IsRestrictedNotCascaded(FK_…_Products_ProductId)` | ✅ |
| `Cascade` → `Restrict` en la FK a `ProductFamilies` | `Migration_DeletingFamily_CascadesToMembers` | ✅ |

Resultado: **3 con error / 14 superados**, exactamente los tres correspondientes y **ninguno de más**.

Detalle que merece anotarse: la otra variante del mismo `[Theory]` —`FK_ProductFamilies_Users_ApprovedByUserId`— **siguió pasando**. El detector discrimina por *constraint*, no por tabla, que es justo lo que hace útil el `[Theory]`.

Tras revertir las tres roturas: **18 superados, 0 fallos**, contando `Model_HasNoPendingMigrationDifferences`.

**`SchemaAssert` no se extendió.** Las seis preguntas que ya expone —tipo, nulabilidad, longitud, columnas de índice, unicidad y regla de borrado— cubren las diecisiete aserciones. Se respeta el guardarraíl que C04 escribió para sí mismo.

---

## 3. La migración

| Comprobación | Resultado |
|---|---|
| `Model_HasNoPendingMigrationDifferences` **antes** de generar la migración | **Rojo**, como debía: si hubiera salido verde, sería que EF no había visto las entidades |
| Migración generada compilando (nunca con `--no-build`) | `20260816210303_AddProductFamily` |
| `Model_HasNoPendingMigrationDifferences` **después** | Verde |
| Contenido revisado a mano | 3 índices únicos, 2 índices de cursor sobre `UpdatedAt`, `Cascade` familia→miembros, `Restrict` hacia `Products` y `Users`, `Origin` como `integer` |
| Aplicación real | `TestDatabaseFixture` la aplica con `Database.MigrateAsync()` antes de cada test de esquema |

La trampa del `--no-build` que C08 documentó **no se dio**, porque se generó compilando desde el principio.

---

## 4. Incidencias encontradas durante la implementación

### 4.1. El fallo que los tests destaparon, y que el diseño no anticipaba

El `design.md` dedicó su decisión más larga a un riesgo concreto: que reordenar miembros chocara con los índices únicos y hiciera falta escalonar la escritura. **Acertó en el mecanismo y se equivocó en la conclusión.**

Al ejecutar los tests, el patrón fue revelador: **vaciar una familia funcionaba, reordenar o intercambiar etiquetas fallaba**, con `DbUpdateConcurrencyException` — *«se esperaba afectar a 1 fila, se afectaron 0»*— y la traza situaba el fallo **en la fase de inserción**.

La causa no era la unicidad. `BaseEntity` asigna el `Guid` en el constructor, así que un miembro nuevo descubierto **a través de la colección de navegación** llega al change tracker con clave no vacía y se toma por una fila que ya existe: la escritura sale como `UPDATE` contra una fila inexistente. Solo se manifiesta cuando una misma petición **borra e inserta a la vez**; añadir miembros o quitarlos por separado funciona perfectamente.

**Corrección:** declarar altas y bajas **explícitamente** por el repositorio (`AddMembersAsync` / `RemoveMembersAsync`) en lugar de mutar `family.Members`.

**Dos hipótesis previas, comprobadas y descartadas** — se anotan porque descartarlas costó dos ejecuciones y evita que alguien las repita:

| Hipótesis | Cómo se descartó |
|---|---|
| `Repository.UpdateAsync` marcaba el grafo como `Modified` | Se quitó la llamada (la entidad ya venía rastreada). Los cuatro tests siguieron fallando igual |
| Era el ciclo de índices únicos que el diseño predijo | Se implementó el escalonado en transacción. Los cuatro tests siguieron fallando igual |

### 4.2. El escalonado del plan B: implementado, medido y retirado

El `design.md` dejaba escrito que si los tests de reordenado fallaban, el remedio era escalonar la escritura en una transacción explícita —borrar y guardar, insertar y guardar, confirmar— y que **lo decidiría el test, no la suposición**.

Se cumplió al pie de la letra. Una vez corregido el fallo real de §4.1:

| Variante | Resultado |
|---|---|
| Escalonada en transacción, dos `SaveChanges` | 16/16 en verde |
| **Un solo `SaveChanges`** | **16/16 en verde** |

El change tracker añade aristas de dependencia entre comandos que tocan el mismo valor de índice único, así que ordena los borrados por delante de las altas que reutilizan una posición o una etiqueta. **La predicción del diseño sobre el orden de comandos era correcta.** El escalonado se retiró por no comprar nada: mantenerlo habría sido complejidad sin evidencia.

### 4.3. Reasignar la colección de navegación de una entidad rastreada

La primera versión del repositorio ordenaba los miembros cargándolos y reasignando `family.Members = family.Members.OrderBy(...).ToList()`. Eso desengancha al change tracker de los miembros que sostiene. Corregido ordenando **dentro del `Include`**: `Include(f => f.Members.OrderBy(m => m.SortOrder))`.

Se corrigió antes de encontrar la causa de §4.1, así que no fue el culpable de los cuatro fallos — pero era un fallo real por su cuenta.

### 4.4. Un *object mother* que se escribió y se retiró

Se creó `ProductFamilyMother` en `TestHelpers/Mothers/` y **acabó sin un solo uso**: todos los tests construyen familias por la API. Antes de dejarlo «por si acaso» se miró qué hace realmente el repositorio, y la respuesta fue concluyente:

| Evidencia | Resultado |
|---|---|
| Usos de `ProductFamilyMother` | **0** |
| ¿Existe un mother para `ProductAiProfile`, la entidad de C08? | **No.** C08 usa mothers para el entorno (POS, producto, usuario) y monta sus perfiles por el endpoint o, cuando necesita un estado previo, directamente por el contexto |
| Usos de `ProductPhotoEmbeddingMother` | 1 — los mothers de este proyecto se crean **cuando hay quien los llame** |

El patrón establecido es *mothers para el atrezo, la API para el sujeto*, y tiene una virtud que no es solo estilística: montar el sujeto por su endpoint impide preparar estados que la API rechaza —un orden duplicado, dos etiquetas iguales— y por tanto impide escribir tests que pasan contra datos imposibles.

**Se retiró.** Un ayudante sin usuarios no es neutral: anuncia un patrón que el código no sigue, se desincroniza de la entidad en cuanto C18 le añada una columna, y hace que quien lea `TestDataMother` suponga que los tests de familia lo usan. El único caso que lo justificaría —persistir `Origin = AiApproved` con su aprobador— es deliberadamente de C18, y su nulabilidad ya está afirmada a nivel de esquema; C08 tomó la misma decisión con `ReviewDurationMs`. Queda un comentario en `TestDataMother` explicando por qué no está, para que no se reescriba por inercia.

Es el guardarraíl que C04 escribió para `SchemaAssert`, aplicado a otra cosa: *solo lo que este change necesita hoy; el siguiente lo extiende cuando sepa qué le hace falta.*

### 4.5. `Application` no referencia `Infrastructure`

Las cotas de longitud se pusieron primero en las configuraciones de EF, y los validadores no podían verlas: `JoiabagurPV.Application` solo referencia `Domain`. Se movieron a las entidades (`ProductFamily.NameMaxLength`, `ProductFamilyMember.VariantLabelMaxLength`), que es donde ambos proyectos las alcanzan. Detectado en compilación, no en ejecución.

---

## 5. Puertas del proyecto

| Puerta | Resultado |
|---|---|
| `dotnet build src/JoiabagurPV.sln` | `Compilación correcta. 0 Errores` |
| `openspec validate --all --strict` | **34 passed, 0 failed** |
| `openspec status --change add-product-family-entity` | **4/4 artefactos**, 28/28 tareas |
| Nomenclatura de tests | `Método_Escenario_ResultadoEsperado` en los 33 |

---

## 6. La frontera, comprobada

| Comprobación | Resultado |
|---|---|
| `git status --porcelain ai-service/` | **Vacío** |
| `git status --porcelain openspec/specs/` | **Vacío** — ninguna spec viva se modifica |
| `ai-service/openapi.json` | Sin cambios; no se regenera |
| `backend/src/JoiabagurPV.Domain/Entities/Product.cs` | **Sin cambios en el diff**: el catálogo no gana ni una columna ni una propiedad de navegación |
| `frontend/`, `terraform/`, `Documentos/modelo-c4.md` | Sin cambios |

El contrato de `jbg-ai` ya transportaba `family_id` y `variant_label` desde C02, y `ai.product_document` ya los reservaba desde C05. Este change solo produce el dato del lado .NET.

---

## 7. Lo que este QA **no** cubre

Se dice entero, porque un QA que solo lista lo verde miente por omisión.

- **Cobertura no medida.** La DoD del proyecto pide ≥70 % del código nuevo. No se ha ejecutado ninguna herramienta de cobertura, así que no puede afirmarse.
- **Sin prueba extremo a extremo contra un contenedor de la API.** Todo pasó por la suite de integración, que sí levanta PostgreSQL real con Testcontainers y ejercita el host HTTP real, pero no se ha hecho ninguna llamada manual contra un despliegue.
- **Sin datos a escala.** Las ~350 familias con 15 % de huérfanos son de C06 y todavía no existen. Los índices sobre `UpdatedAt` están justificados por el coste de añadirlos después, no por una medición de latencia.
- **RDS de producción.** La migración solo se ha aplicado sobre Testcontainers.
- **Sin interfaz.** Este change no tiene ninguna, y la pantalla de familias es de C18.
- **La reserva para C18 no está ejercida.** `Origin` se escribe siempre como `Manual`; `ApprovedByUserId` y `ApprovedAt` no tienen hoy ningún camino de escritura. Las columnas están y su nulabilidad está probada, pero nadie las ha llenado.
