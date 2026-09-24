# C40 — las mediciones de la implementación

**Change:** `add-frontend-free-query-panel` (C40) · **Rama:** `c40-add-frontend-free-query-panel`
**Abierto:** 2026-09-24 · **Estado:** en curso, grupo 1 cerrado
**Complementa:** [c40-exploration-decisions.md](c40-exploration-decisions.md) y
[c40-m1-panel-states.md](c40-m1-panel-states.md), que son de exploración; éste es de **medición sobre
el código escrito**.

Este documento recoge las cifras que el DoD del ticket exige y que **hoy no existen**. Se escribe a
medida que los grupos se cierran, no al final, porque las dos mediciones del tramo 2 son entregables y
no diagnósticos: sin ellas el tramo no está hecho aunque compile.

Las cinco cifras comprometidas:

| # | Cifra | Grupo | Estado |
|---|---|---|---|
| 1 | Marcadores `{{price}}`/`{{stock}}` en el argumentario de M1, **antes y después de `v5`** | 4.7 | pendiente |
| 2 | Reparto de los **dieciséis estados** sobre las 42 consultas | 8.2 | pendiente |
| 3 | **Latencia p50/p95 extremo a extremo por .NET** sobre las 42 consultas | 8.1 | pendiente |
| 4 | Tasa de **`router_index_absent`** tras la coerción | 10.7 | pendiente |
| 5 | **Efecto de la sonda** sobre la latencia de una búsqueda filtrada | 10.7 | pendiente |

---

## 1 · La línea base, medida antes de tocar una línea (grupo 1)

Medida **directamente sobre `93115cf`** con el árbol limpio, sin `stash`. La regla que gobierna toda
comparación posterior: **se compara el conjunto de nombres, nunca el número.**

| Suite | Comando | Resultado | Duración |
|---|---|---|---|
| `backend` | `dotnet test backend/src/JoiabagurPV.sln` | **50 con error · 1.191 superados · 1.241 total** | 8 m 58 s |
| `frontend` | `npx vitest run` | **113 con error · 616 superados · 729 total**, en 14 de 54 ficheros | ~5 m |
| `ai-service` | `uv run --system-certs pytest` | **1.576 superados · 0 con error** — verde | 143 s |

Los nombres que fallan están volcados en el directorio de trabajo de la sesión
(`baseline/backend-failing-names.txt`, `frontend-failing-names-run1.txt` y `-run2.txt`). No se
versionan: ningún change archivado de este repositorio guarda artefactos de línea base, y estas listas
describen una máquina y un día, no el change.

### Las otras dos anotaciones de la puerta

| Qué | Valor |
|---|---|
| `sha256` de `ai-service/openapi.json` | `d8d48f87b279d45d22bce80a67c4fd51caef6e679363c413f5b697c99ec2b875` (102.186 bytes) |
| `openspec validate --all --strict` | **62 passed, 0 failed** |

La copia de la línea base del contrato queda guardada para la verificación **hoja a hoja** del grupo
3.2, que es donde se comprueba que el movimiento es adición pura.

### Lo que la línea base refutó de la documentación, y ya está corregido

**El recuento del frontend que `CLAUDE.md` y el ticket citaban estaba caducado.** Los dos decían
«113 o 114 de 597, en 14 o 15 de 48 ficheros». Medido hoy, dos veces: **113 de 729, en 14 de 54**.

No es que la cifra fuera falsa: era la línea base **de apertura** de C36, y el árbol está en su
**cierre**. `Documentos/testing-frontend.md:298` ya registraba el dato correcto —*«al cierre **729**
tests, 113 fallos, en 14 de 54»*—, así que lo que había era un desfase entre el inventario detallado y
los dos sitios que lo resumen. Corregidos los dos en el grupo 1.

**La oscilación 113/114 no se reprodujo.** Dos pasadas consecutivas sobre el mismo commit dieron
**113 las dos**, con conjuntos de nombres **idénticos byte a byte**, y el test dependiente del orden que
C36 documentó —`family-review.test.tsx :: should create a family with its members from the review
screen`— **pasó en las dos**. Coincide con lo que vio la verificación de C36. La banda 113/114 sigue en
pie como aviso, pero no se puede confirmar desde las pasadas de hoy: por eso la línea base contra la que
se compara es **el conjunto de nombres**, no ninguna de las dos cifras.

### El fallo de medición que casi se cuela, y que conviene no repetir

La primera ejecución de `dotnet test` **no compiló y ejecutó cero tests**, porque un
`JoiabagurPV.API.exe` arrancado el 23/09 tenía bloqueados los DLL de `bin/Debug`. Terminó con **seis
errores `MSB3021`/`MSB3027`** y, aun así, **el proceso salió con código 0**.

Es el gemelo exacto de la trampa que `CLAUDE.md` ya documenta para `vitest` —*«sale con código 0 al
pipearlo, así que un prompt verde no dice nada»*—, sólo que en el otro lado y por otra razón. La regla
que vale para los dos: **leer la línea de resumen, no el código de salida**. Una suite que no llega a
compilar se parece mucho a una suite que pasa.

### La comparación por nombres del backend necesita un matiz, y no es menor

`CLAUDE.md` dice del backend *«compara nombres»*, dando a entender que los nombres son estables.
`Documentos/testing-backend.md` documenta que **no lo son**: dos pasadas idénticas sobre el mismo commit
llegaron a diferir en **trece nombres**, siempre confinados a las mismas clases
—`InventoryIntegrationTests`, `PaymentMethodsControllerTests` y `ReturnsControllerTests`—, y una prueba
con `--no-build` sobre el **mismo binario** dio **diez nombres de diferencia**.

Esto **cualifica el criterio del DoD** —«cero nombres desaparecidos y cero nuevos en rojo»—: en el
backend ese cero literal no es alcanzable, y exigirlo llevaría a perseguir ruido. La lectura correcta es
la que el propio inventario da: **los nombres que difieran deben caer dentro de las clases inestables
conocidas, y ninguno en una clase que el change toque.** Las cifras de rotación medidas hoy sobre
`93115cf` están en la tabla siguiente.

#### La rotación del backend, medida hoy sobre `93115cf`

Dos pasadas completas, **mismo commit, mismo árbol, sin recompilar entre medias**:

| | Pasada 1 | Pasada 2 |
|---|---|---|
| Con error | **50** | **51** |
| Superados | 1.191 | 1.190 |
| Total | 1.241 | 1.241 |
| Duración | 8 m 58 s | 8 m 1 s |

Comparados **por nombre**:

| | Nombres |
|---|---|
| Estables en las dos pasadas | **43** |
| Aparecen sólo en la 2ª | **8** |
| Desaparecen tras la 1ª | **7** |
| **Rotación total** | **15** |

**Los quince están confinados a dos clases**, las dos del trío que
[testing-backend.md](../../testing-backend.md) ya nombra: **14 en `InventoryIntegrationTests`** y
**1 en `ReturnsControllerTests`**. Cero rotación fuera de ellas. `PaymentMethodsControllerTests`, la
tercera del trío, no rotó hoy pero mantiene su fallo fijo.

**Esto es el yardstick de C40, y es lo que hace utilizable el criterio del DoD.** Un nombre nuevo en
rojo dentro de `InventoryIntegrationTests` no dice nada —hoy, sin tocar una línea, entraron ocho—;
un nombre nuevo en rojo **fuera** de esas clases, o en cualquier clase que C40 toque, es una
regresión. La comparación de los grupos 2.8, 7.8 y 14.3 se lee con esta tabla al lado.

Ninguna de las clases que rotan es de las que C40 toca: el change trabaja sobre
`AssistedSearchRepository`, `AssistedSearchService`, `SalesAssistService`, `AiGatewayClient`,
`AiCallScope`, `SearchOrigin` y el controlador de búsqueda, y añade clases nuevas para el endpoint de
consulta libre.
<!-- GRUPO1-CHURN-FIN -->

---

## 2 · Tramo 1 · la verificación del grupo 2

Las dos puertas de compilación en verde —`dotnet build` y `npm run build`— y las dos suites
comparadas **por nombres** contra la línea base del grupo 1.

| Suite | Línea base | Tras el grupo 2 | Lectura |
|---|---|---|---|
| `backend` | 50 y 51 de 1.241 | **51 de 1.269** | **+28 tests, los 28 nuevos pasan** |
| `frontend` | 113 de 729, 14 ficheros | **113 de 740, 14 ficheros** | **+11 tests, los 11 nuevos pasan** |
| `openspec validate --all --strict` | 62 passed, 0 failed | **62 passed, 0 failed** | — |

**Frontend: conjunto de nombres idéntico.** Cero nuevos y cero desaparecidos contra la pasada de
línea base.

**Backend: tres nombres difieren de la unión de las dos pasadas de línea base, y los tres están en
`InventoryIntegrationTests`** — la clase que el grupo 1 midió rotando catorce de sus quince nombres
sin que nadie tocara nada. Cero nombres nuevos fuera de ella. Y el dato que cierra la lectura:
**cero fallos en cualquier clase que C40 toca** —`AssistedSearch*`, `SalesAssist*`, `AiSearch*`,
`ProductSearchEvent*`, `AiGateway*`, `AiCallScope*`—. Limpio según el criterio del grupo 1.

La pasada tardó **13 m 11 s** contra los 8 m 58 s de la línea base. El grupo añade seis tests de
integración con Testcontainers y tres que emiten cuarenta peticiones HTTP, así que el coste está
explicado; se vigila por si sigue creciendo.

### La regresión que la comparación por nombres cazó, y que el recuento habría escondido

La primera pasada de frontend del grupo 2 dio **117 fallos con cuatro nombres nuevos**, los cuatro en
`assist-entrances.test.tsx`. Causa: ese fichero mockea `aiSearchService` con un objeto literal, así
que al añadir `getAvailability` al servicio el panel llamaba a `undefined` y la página no llegaba a
estabilizarse. Corregido, y barrido el resto de ficheros que mockean ese servicio por si tenían el
mismo agujero.

Es exactamente el caso de uso de la regla: **117 contra 113 sólo dice «has roto algo»**; los nombres
dijeron qué, dónde y por qué en un minuto. Queda anotado porque el patrón se repetirá en cada grupo
que añada un método al servicio del frontend — el mock literal no falla al compilar, falla al
ejecutar.

### Dos detalles menores que el contacto con el código obligó a decidir

Los dos resueltos con la regla por defecto del diseño —la opción más estrecha que no añade
migración, no cambia la ficha más allá de `degradedReason`, no retira ni cambia de tipo ningún campo
del contrato y no suprime ningún dato—, y los dos anotados aquí porque no estaban listados.

**1 · El fragmento C# del ticket para `SearchLexicalAsync` no compila.** Propone pasar
`AiSearchFilters` —de `Application`— a `IAssistedSearchRepository`, que vive en `Domain`. `Domain` no
referencia ningún proyecto y `Infrastructure`, donde vive la consulta, referencia sólo a `Domain`, así
que la firma del ticket invierte la dependencia. **Resuelto** con un tipo `AssistedSearchFilters`
propio del `Domain` que lleva sólo los dos filtros que el catálogo transaccional puede responder, y el
mapeo en el único sitio donde la capa de aplicación los construye. Sin migración y sin tocar el
contrato congelado.

**2 · El escenario «un filtro que no se puede aplicar se declara» no es alcanzable.** La petición del
panel lleva exactamente dos filtros —categoría y materiales— y la ruta degradada ahora **aplica los
dos**, así que `unappliedFilters` sale vacío en todos los casos que este endpoint puede producir.
**Resuelto** construyendo el canal igualmente y documentando que está dormido: el requisito es una red
de seguridad, y la avería que abrió C40 fue invisible precisamente porque no había dónde reportarla.
El test se nombró por lo que afirma —que una categoría aplicada **no** se declara sin aplicar— en vez
de fingir que el canal dispara.
