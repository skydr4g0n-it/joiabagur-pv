# C40 — las mediciones de la implementación

**Change:** `add-frontend-free-query-panel` (C40) · **Rama:** `c40-add-frontend-free-query-panel`
**Abierto:** 2026-09-24 · **Estado:** en curso, grupos 1 a 3 cerrados
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

---

## 3 · Tramo 2 · el contrato se mueve, verificado hoja a hoja

`AssistRequest` gana `filters`. Es el movimiento más pequeño que este contrato admite, y la razón
es que **el modelo al que apunta ya estaba publicado**: `RetrievalFilters` servía desde C14 a
`RetrievalRequest` y a `SubstitutesRequest`, así que la adición es una referencia y no un esquema.

### La verificación hoja a hoja, que es el criterio del DoD

Los dos documentos aplanados a `ruta -> escalar` y la diferencia partida en cuatro. No es una
lectura de un diff ni una comparación de claves de primer nivel.

| | Hojas |
|---|---|
| Antes (`93115cf`, `sha256 d8d48f87…`) | **1.300** |
| Después (`sha256 8c1827d3…`) | **1.302** |
| **Retiradas** | **0** |
| **Cambiadas de tipo** | **0** |
| **Con valor distinto** | **0** |
| Añadidas | **2** |

Las dos añadidas:

```
+ /components/schemas/AssistRequest/properties/filters/$ref
+ /components/schemas/AssistRequest/properties/filters/description
```

El `git diff` del fichero lo dice igual de corto: **4 inserciones, 0 borrados.**

**Adición pura, y además opcional**: un cliente que no envíe `filters` recibe exactamente el
comportamiento de antes. El test lo fija en las dos direcciones — que la propiedad no está en
`required`, y que apunta a `RetrievalFilters` en vez de a un esquema nuevo.

### El fixture de línea base del contrato cambia de dueño

`test_the_published_contract_moved_by_addition_only` comparaba contra
`fixtures/openapi-c32a-baseline.json`, y su propio docstring decía que **el siguiente change que
moviera el contrato reemplazaría ese fixture y su lista de adiciones permitidas**. C40 es ese
change: el fixture pasa a ser `openapi-c40-baseline.json` —el snapshot tal como estaba en
`93115cf`— y las adiciones permitidas pasan a ser la única propiedad nueva.

### El doble del stub deja de emitir marcadores en el modo libre

Y esto **corrigió dos tests que afirmaban lo contrario**, los dos legítimamente escritos antes de
que existiera la cadena que C40 documenta:

| Test | Afirmaba | Afirma ahora |
|---|---|---|
| `test_assist_sale_groups_by_family` | `{{price}}` **está** en el argumentario de una consulta libre | **no está** |
| `test_stub_mode_still_serves_the_fixture` | ídem | ídem, y que **sí hay prosa** |

El motivo por el que el doble no puede escribirlos: `PitchPlaceholderResolver` retira el
argumentario **entero** cuando un marcador le llega sin ancla contra la que resolverlo. Un doble
que los escribiera estaría enseñando a todo cliente que corre contra *stubs* un contrato que la
ruta real rechaza, y la prosa desaparecería la primera vez que alguien apuntara al servicio de
verdad, sin nada en el diff que lo explicara.

**Los modos anclados quedan intactos**, con su propio test que lo fija: ahí el resolutor sí tiene
una pieza contra la que resolver.

### Suites del grupo 3

| Suite | Línea base | Tras el grupo 3 |
|---|---|---|
| `ai-service` | 1.576 pasados, 0 con error | **1.581 pasados, 0 con error** (+5, los 5 nuevos pasan) |
| `openspec validate --all --strict` | 62 passed, 0 failed | **62 passed, 0 failed** |

El frontend **no se tocó** en este grupo —ni un fichero bajo `frontend/`—, así que su suite no se
re-ejecuta: la comparación por nombres del grupo 2 sigue siendo la vigente.

### La forma del campo en .NET la decidió un guard, no yo

Escribí `AiAssistSaleRequest.Filters` **anulable con `[JsonIgnore(WhenWritingNull)]`**, para que la
petición anclada saliera byte a byte igual que antes de C40. `AiContractSnapshotTests` lo rechazó en
la primera pasada completa:

```
Expected IsNullableInContract(declared) to be True because nullability of 'filters' must match
between AiAssistSaleRequest and schema AssistRequest … but found False.
```

Y tiene razón: el contrato declara `filters` **con defecto**, no como anulable, y ese test existe
justamente para que una deriva entre los dos lados rompa la compilación en vez de aparecer en
ejecución como un valor nulo silencioso.

**El precedente de la casa resuelve la duda sin discusión:** `AiSubstitutesRequest.Filters` lleva el
mismo campo del mismo contrato y es **no anulable con defecto**, y su test de serialización afirma
que `filters` viaja siempre. Así que `AiAssistSaleRequest` pasa a la misma forma.

**Esto se desvía de la letra de la tarea 3.3**, que pedía el campo *«omitido cuando no hay
ninguno»*. Se declara aquí en vez de callarse. El argumento por el que no se sigue: un conjunto de
filtros vacío y una propiedad ausente **significan lo mismo para el servicio**, que rellena el
defecto en los dos casos; y mantener la paridad que el guard vigila vale más que ahorrar cuatro
claves en un cuerpo, sobre todo cuando el hermano más cercano del DTO ya las envía. Exención del
guard descartada: debilitar la única red que convierte una deriva de contrato en una conversación
explícita, para ganar una frugalidad que el servicio no nota, es mal cambio.

Dos tests se ajustaron a la forma nueva: `AssistSaleRequest_Serialization_OmitsPosId` —que fija el
cuerpo exacto— y el que yo había escrito, ahora
`AssistSaleAsync_WithoutFilters_SendsAnEmptyFilterSet`.

### Suite de backend del grupo 3, tras la corrección

| | Antes de corregir | Tras corregir |
|---|---|---|
| Con error | 54 de 1.271 | **46 de 1.271** |
| `AiContractSnapshotTests` en rojo | **sí** (la regresión) | **no** |
| Nombres nuevos fuera de lo ya visto | 7 | **2**, los dos en `InventoryIntegrationTests` |
| Fallos en clases que C40 toca | 0 | **0** |

Limpio según el criterio del grupo 1.

---

## 4 · Tramo 2 · el recuento de marcadores, antes y después de `v5` (grupo 4.7)

**La cifra que decide si M1 tiene prosa**, y la primera de las cinco comprometidas. Medida contra
el proveedor real, el índice real y el corpus real, desde el contenedor de Compose.

### El método, y por qué es una comparación y no dos anécdotas

`free_query_gate.py` gana `--prompt-version`, que inyecta el texto y la versión en
`generate_pitch` —que ya los aceptaba **en pareja**, precisamente para que nadie estampe una
respuesta con un prompt que no llegó al modelo—. Las dos pasadas comparten **código, índice,
corpus, punto de venta, modelos y consultas**: lo único que cambia es el prompt.

El recuento se hace sobre el **primer intento**, antes de cualquier reparación, y se **cuenta sin
almacenar**: el argumentario es contenido que la ruta de servicio no puede persistir; un recuento
no lo es.

**Población: las 90 consultas del conjunto etiquetado que pueden generar** —48 `catalog`, 32
`knowledge`, 10 `both`—. El ticket habla de «las 42 consultas», que son las 32 `eval_question`
más las 10 `both`; se miden las 90 porque **excluir `catalog` dejaría fuera la ruta donde el
precio tiene sentido**, que es justo lo que la medición busca. El desglose por ruta está en los
artefactos, así que la lectura de 42 sigue siendo derivable.

### Las dos cifras

| | `assist/v3` (antes) | `assist/v5` (después) |
|---|---|---|
| Consultas | 90 | 90 |
| Generaciones | 90 | 89 |
| **`{{price}}` en el argumentario** | **2** | **0** |
| **`{{stock}}` en el argumentario** | **1** | **0** |
| Generaciones con algún marcador | **2 · 2,2 %** | **0** |
| Retiradas por la puerta | 8 | **0** |
| Tasa de rechazo del modo libre | **8,9 %** | **0 %** |
| Degradaciones del enrutador | 0 | 0 |
| Errores | 0 | 0 |

Artefactos persistidos con `run_id`, `git_sha` y `prompt_version`:
`evals/results/c40-placeholders-before-v3-ed9ee934e8c6.json` y
`c40-placeholders-after-v5-53f4759f200f.json`.

**Los dos casos con marcador de `v3` estaban los dos en la ruta `both`** (`b02`, `b04`), ninguno
en `catalog` ni en `knowledge`.

### Lo que esta medición refuta, y hay que decirlo

El ticket y el diseño razonan así: `v3` ordena escribir los marcadores en **las seis** tareas →
C30b midió `{{price}}` en **147 de 213 · 69 %** y `{{stock}}` en **188 de 213 · 88,3 %** en los
modos anclados → luego, sin `v5`, «**la mayoría de los argumentarios de M1 se retirarían**».

**Medido: 2 de 90 y 1 de 90.** La proporción de los modos anclados **no se traslada al modo
libre**, y no por poco: 69 % contra 2,2 %, un factor de treinta.

La explicación que el propio prompt sugiere: en el modo anclado hay **una** pieza y la tarea
invita a venderla, así que nombrar su precio es natural y el marcador aparece. En el modo libre
hay hasta quince piezas agrupadas y la tarea pide **comparar**, no vender una; el modelo
prácticamente nunca llega a nombrar un precio. La regla invariante lo **permitía**; la tarea no
lo **pedía**.

**Lo que esto no cambia, y conviene no sobrecorregir:**

- **El guardia de `AiGatewayClient` rechazaba M1 al 100 %.** Eso era real, medible y total, y es
  lo que de verdad impedía que el argumentario llegara al operario. La cadena tenía tres
  eslabones y el que mordía era el tercero, no el primero.
- **`v5` sigue justificado, con otra magnitud.** Dos argumentarios de noventa retirados es
  pérdida evitable, y la causa dura convierte la frecuencia en algo **partido por causa** en vez
  de una caída inexplicada. La tasa de rechazo del modo libre cae de **8,9 % a 0 %**.
- **La cuarta tarea funciona contra el corpus real**: disparó una vez (`b05`, ruta `both`, cero
  citas) y generó correctamente. Con `v3` esa misma consulta cayó a `free_query_both` —registrado
  en `task_fallbacks`— y corrió la tarea que dice «apóyate en esos fragmentos» **sin fragmentos**.

**Corrección que esto obliga en los artefactos:** la frase «sin el tramo 2 completo, C40 entrega
un panel asistido sin prosa» **es cierta**, pero por el guardia de la pasarela, no por la
frecuencia de marcadores. La predicción de que «la mayoría se retirarían» era una extrapolación
de una población a otra y **la medición la desmiente**. Queda corregida en `ticket.md`, en
`design.md` y en la cabecera de `prompts/assist/v5.md`.

### Dos averías del arnés que esta medición destapó

1. **`free_query_gate.py` no podía correr en un contenedor.** Fijaba
   `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())` **sin condición**, y ese
   atributo no existe en Linux. Los otros tres módulos del arnés ya estaban protegidos; éste era
   el único. Corregido con el guardia de la casa.
2. **Su `--pos-id` por defecto apunta a un punto de venta de proyección vacía**, lo que aborta
   cada consulta con `RetrievalDependencyError`. En esta base el poblado es
   `0388f003-2ffd-4d4c-8d7a-9a7466b36ca4`, con 1.082 productos asignados.

Y una **pasada descartada**: la primera, con `--delay 0.3`, agotó el cupo de `gpt-4o` a partir de
la consulta 16 y degradó **46 de 90** con `RateLimitError`, todas al *fail-open*. Publicar desde
ahí habría sido medir el cupo del proveedor y no el prompt. Repetida con `--delay 4`: cero
degradaciones.

### El PEM del host, montado y verificado

CLAUDE.md dice que `litellm` sale por el bundle de `certifi` y que hay un MITM de Norton cuya
raíz vive sólo en el almacén de Windows. Verificado, y sin ambigüedad:

```
certifi          FALLA SSLCertVerificationError: unable to get local issuer certificate
windows-roots    OK   emisor=Norton Web/Mail Shield Root
```

El bundle se construye concatenando `certifi` con `LocalMachine` y `CurrentUser` × `ROOT`/`CA`/
`AuthRoot` —131 certificados únicos— **sin filtrar por bandera de confianza**, porque la raíz de
Norton no la lleva. Y se confirma la otra mitad del documento: **desde el contenedor los
embeddings y la generación funcionan sin PEM ninguno**, que es por lo que la medición se hizo ahí.

---

## 5 · Tramo 2 · el endpoint de la consulta libre (grupo 5)

`POST /api/ai/search/assisted`, con interruptor, cupo, presupuesto y circuito **propios**.

| Suite | Antes del grupo | Tras el grupo 5 |
|---|---|---|
| `backend` | 46 de 1.271 | **52 de 1.316** (+45 tests, los 45 nuevos pasan) |
| `openspec validate --all --strict` | 62 passed, 0 failed | **62 passed, 0 failed** |
| `dotnet build` | verde | **verde** |

Los cuatro nombres que difieren de todo lo visto hasta ahora están en `InventoryIntegrationTests`
(2) y `ReturnsControllerTests` (2), las dos clases de rotación que el grupo 1 midió. **Cero fallos
en cualquier clase que C40 toca.**

### Tres decisiones de implementación

**1 · La hidratación se extrae, no se duplica.** `AssistedSearchResultProjector` lo comparten los
dos servicios. Lo que vive ahí es la regla de **dónde viene cada campo** —precio, stock, SKU,
nombre y foto del catálogo; puntuación, materiales, razones de coincidencia, familia y variante
del índice—, que es lo único de esa proyección que es fácil equivocar e imposible notar. Una
segunda copia habría derivado la primera vez que alguien arreglase una de las dos.

**2 · La disponibilidad exige los dos interruptores.** `GetAvailability` requiere el del endpoint
nuevo **y** el de la ficha: el primero gobierna si este endpoint responde, el segundo si el
servicio escribe prosa para esa tienda. Informar sobre uno solo devolvería la pantalla justo a
donde C40 la encontró — ofreciendo una capacidad apagada.

**3 · El punto de venta es obligatorio en este grupo.** El ámbito «todos los puntos de venta» es
el grupo 12 y llega **con su frontera de autorización**; darle aquí una versión provisional sería
la clase de puerta entreabierta que nadie revisa. Declarado en el DTO y en el servicio.

### Lo que la validación al arranque evita, y por qué no se clampa

Dos relaciones que ningún rango por clave puede expresar y que fallan **en silencio** en tiempo de
petición: una página por defecto mayor que el máximo, y una ventana de candidatos demasiado
pequeña para llenar una página. Ninguna lanza nada — el endpoint sirve el número equivocado de
resultados, durante todo el tiempo que nadie los cuente —, así que se rechazan al arrancar
nombrando la clave. Clampar habría hecho el error permanente e invisible, que es exactamente el
modo de fallo que este change existe para retirar.

### Una nota de mecánica del repositorio

`perl -0pi -e` sobre los ficheros de este árbol **falla en silencio** por los CRLF: no da error,
simplemente no sustituye. Costó tres ediciones que parecían aplicadas y no lo estaban. Para
ediciones multilínea, `node` con el script en un fichero aparte.

---

## 6 · Tramo 2 · el toggle y la copia (grupo 6)

| Suite | Antes del grupo | Tras el grupo 6 |
|---|---|---|
| `frontend` | 113 de 740, 14 ficheros | **113 de 764, 14 ficheros** — conjunto de nombres **idéntico** |
| `npm run build` | verde | **verde** |
| `openspec validate --all --strict` | 62 passed, 0 failed | **62 passed, 0 failed** |

+24 tests, los 24 nuevos pasan. Cero nombres nuevos y cero desaparecidos.

### Dos tests de C36 afirmaban lo contrario, y los dos eran correctos cuando se escribieron

C36 dejó `query_out_of_domain` y `query_not_in_catalogue` **sin copia**, y lo razonó: el
clasificador de intención corre **sólo** en el modo libre, ese modo no tenía pantalla, así que
ninguno de los dos códigos podía llegar a ninguna parte. Escribir su castellano habría sido copia
para un camino imposible — *«dos tests verdes sobre caminos imposibles»*, en sus palabras.

**C40 le da pantalla al modo libre**, lo que vuelve los códigos alcanzables y la copia debida. Los
dos tests que fijaban la etiqueta neutra se reescriben:

| Test | Dónde | Qué cambia |
|---|---|---|
| `should label a router refusal code…` | `assist-copy.test.ts` | Inversión **total**: ahora son alcanzables y tienen copia |
| `should carry the copy of the two router refusal codes…` | `assist.test.tsx` | Sólo la etiqueta. **La ficha sigue sin poder alcanzarlos** |

La diferencia entre los dos no se aplana. En la tabla de copia la inversión es completa. En la
ficha **no**: sus dos rutas siguen siendo ancladas, el clasificador nunca corre y los códigos
siguen sin poder llegar ahí; lo único que cambió es que la tabla compartida ya no los deja sin
etiquetar. El test lo dice así en vez de fingir que la ficha ganó un camino que no tiene.

**Y el segundo lo encontró la comparación por nombres, no la búsqueda.** Busqué el patrón en el
fichero donde vive la tabla y no se me ocurrió que la página de la ficha tuviera su propia
aserción sobre el mismo hecho. Dos ficheros, la misma propiedad.

### La partición de avisos es una lista de permitidos en los dos lados

Backend y pantalla filtran, y la duplicación es deliberada: la regla es una propiedad de **qué
puede mostrarse**, y una pantalla que confiara en el payload renderizaría lo que una versión
posterior del servicio decida apilar en ese array. Con lista de permitidos, un código nuevo se
queda fuera por defecto; con lista de prohibidos entraría en una banda que afirmaría algo falso
sobre cada resultado debajo.

### El toggle no recuerda, y eso es la mitad de su diseño

Estado de componente y deliberadamente nada más: ni `localStorage`, ni parámetro de consulta, ni
campo de perfil. Recordar la cara cara es como se gasta sin que nadie lo decida, y la ruta
asistida cuesta **cuatro veces** el presupuesto de tiempo y **tres veces** el cupo. El coste se
dice **antes** de pulsar —30 búsquedas por minuto contra 10, respuesta inmediata contra unos
segundos— porque quien lo descubre esperando siete segundos ya lo ha pagado.

Con la ruta asistida apagada, su opción se **deshabilita con su motivo** en vez de fallar al
pulsarla: una opción que revienta al hacer clic es la misma mentira que este change vino a
retirar, movida un paso más tarde.

---

## 7 · Tramo 2 · los dieciséis estados en pantalla (grupo 7)

| Suite | Antes del grupo | Tras el grupo 7 |
|---|---|---|
| `frontend` | 113 de 764, 14 ficheros | **113 de 794, 14 ficheros** — conjunto **idéntico** |
| `backend` | 52 de 1.316 | **sin re-ejecutar**: `git diff` vacío sobre `backend/` desde el grupo 5 |
| `ai-service` | 1.590 pasados, 0 con error | **sin re-ejecutar**: `git diff` vacío sobre `ai-service/` desde el grupo 4 |
| `dotnet build` · `npm run build` | verde | **verde** |
| `openspec validate --all --strict` | 62 passed, 0 failed | **62 passed, 0 failed** |

+30 tests, los 30 nuevos pasan. Cero nombres nuevos y cero desaparecidos.

Las dos suites que no se re-ejecutan se declaran en vez de omitirse: los grupos 6 y 7 tocaron
**sólo** `frontend/`, comprobado con `git diff --name-only` contra el commit del grupo 5, así que
sus cifras siguen siendo las vigentes. `dotnet build` sí se corre, porque es barato y es lo que
cazaría una rotura entre capas.

### La decisión que gobierna el grupo

**El render consume un estado resuelto, no una escalera de comprobaciones de campo.** Los
dieciséis estados son **combinaciones**, y una pantalla que ramifica campo a campo acierta cada
rama y falla las combinaciones — que es exactamente cómo el panel de C16 acabó con cinco ramas de
vacío, tres de las cuales pintarían una respuesta correcta como un fallo.

`resolveFreeQueryState` decide y el componente dice. Por eso las aserciones que más pesan viven en
`free-query-states.test.ts` y no en el DOM: los tres estados que se pintarían mal están mal **en la
clasificación**, no en el marcado. Un test que renderizara y buscara una cadena pasaría el día que
alguien arregla la cadena y rompe la rama.

**El orden de las comprobaciones es el de la máquina, no el de conveniencia.** El enrutador corta
antes de recuperar, así que un rechazo o una repregunta ganan a cualquier condición posterior; la
abstención va después porque se decide antes de generar. Hay un test que lo fija: un rechazo que
llega con `abstained: true` y con grupos sigue resolviendo a rechazo.

### Tres reglas de copia que la tabla obliga y que no son obvias

**1 · «Sin fuente verificable» no se dice en la ruta `catalog`.** Ahí el corpus no se consulta y la
propia tarea ordena no citar, así que una lista de citas vacía es el estado correcto: anunciarlo
inventaría un hueco. Tampoco se dice cuando ya está `knowledge_not_covered`, que describe la misma
ausencia con palabras más útiles.

**2 · Sin prosa, sin citas — y el servicio hace lo contrario a propósito.** Cuando la puerta retira
el argumentario, el servicio **conserva** las citas: una respuesta degradada no debe ser más pobre
que la que la capa estructurada produce sola, que es lo que mantiene comparable la ablación para el
arnés. Esa decisión sirve al arnés. La de la pantalla sirve al operario, y para él una cita sin
afirmación no atribuye nada. Las dos son correctas y apuntan en direcciones opuestas porque sirven
a consumidores distintos; quien lea una sin la otra intentará unificarlas.

**3 · `CitationRow` de C36 se exporta y se reutiliza, no se copia.** Lo que no había que duplicar es
la distinción establecimiento/general: un compromiso de la casa pasado como hecho del mundo es como
una tienda acaba debiendo algo que no prometió.

---

## 8 · Tramo 2 · la latencia y el reparto de estados, medidos por .NET (grupo 8)

Ésta es la segunda de las dos mediciones que el encargo pide como **entregable y no como
diagnóstico**. La pregunta que responde es si M1 cabe en el presupuesto de 10 s extremo a extremo
—el que no se puede subir— y, si no cabe, disparar el corte pre-autorizado.

**No hace falta disparar el corte.** El p95 medido es **7 160 ms** sobre un presupuesto de 10 000 y
**ninguna de las 42 consultas** lo excede.

### El montaje, porque la cifra no significa nada sin él

| Pieza | Qué |
|---|---|
| Superficie | `POST /api/ai/search/assisted`, que es la que usa el panel |
| Cliente | sesión por cookie, una petición cada vez, sin concurrencia — como un mostrador |
| API .NET | `localhost:5056`, los tres interruptores encendidos, cupo elevado para no medirlo a él |
| `jbg-ai` | contenedor en `backend_jpv-network`, **`STUB_MODE=false` y claves reales**, 1 168 documentos indexados |
| Punto de venta | `0388f003-…a4` (MAO-TALLER) |
| Conjunto | las **42 consultas etiquetadas** (32 `knowledge`, 10 `both`) |
| Procedencia | `git_sha` `1c315a9`, `prompt_version` `assist/v5`, enrutador `router/v3` |

### 8.1 · Las cifras

| | 42 consultas atendidas | ruta `knowledge` (32) | ruta `both` (10) |
|---|---|---|---|
| **p50** | **3 404 ms** | 3 772 ms | 2 846 ms |
| **p95** | **7 160 ms** | 7 700 ms | 7 160 ms |
| máximo | 7 759 ms | | |
| mínimo | 776 ms | | |
| **fuera de presupuesto** | **0 de 42** | | |
| enrutador degradado | **0 de 43 llamadas** | | |
| marcadores `{{price}}` / `{{stock}}` | **0 / 0** | | |

**El corte pre-autorizado —no generar en la ruta `catalog`— no se dispara**, y el margen no es de
décimas: sobran **2,8 s** en el p95.

### Dónde se gasta el presupuesto, que no es donde se temía

| Tramo | p50 | p95 |
|---|---|---|
| llamada a IA (`usage.aiMs`) | 3 388 ms | 7 142 ms |
| total del servidor (`usage.totalMs`) | 3 390 ms | 7 147 ms |
| **.NET + red, por diferencia** | **13 ms** | **17 ms** |

La capa que C40 añade cuesta **diecisiete milisegundos en el p95**. Todo el presupuesto se gasta
dentro de `jbg-ai`, y dentro de él, en el proveedor. Esto importa para quien venga después:
optimizar el lado .NET de esta ruta no tiene nada que ganar.

### Lo que esta medición refuta

El `design.md` razonaba que M1 suma el enrutador a lo ya medido por C34 —**p95 7,1 s sin
enrutador**— y que los «~2 s» adicionales lo pondrían al borde de los 10 s. Medido, **el p95 con
enrutador es 7 160 ms**: prácticamente el mismo. La predicción trataba el enrutador como un coste
que se suma; en la práctica **el enrutador se paga con trabajo que se ahorra**, porque las consultas
que corta no llegan a recuperar ni a generar.

Eso sale muy claro en la pasada complementaria:

| | consultas **cortadas** por el enrutador (30) | consultas **respondidas** (39) |
|---|---|---|
| p50 | **686 ms** | 3 404 ms |
| p95 | **1 292 ms** | 7 700 ms |

**Un rechazo cuesta la quinta parte que una respuesta.** El operario recibe la negativa en menos de
un segundo, que es justo el caso en el que esperar siete sería más irritante.

### Cuatro manipulaciones del entorno, declaradas

1. **Una petición de calentamiento, descartada.** La primera llamada del proceso paga el TLS y un
   pool frío en los dos saltos: medida, costó 8,8 s contra 0,9–3 s en caliente. Meterla en un p95
   que describe régimen permanente sería describir un arranque. La razón está en el código del
   arnés, no sólo aquí.
2. **La proyección del punto de venta se refrescó.** Llegaba con 19,7 días y el servicio la
   declaraba `degraded=unscoped`, con lo que se habría medido otra cosa. Se actualizaron
   `refreshed_at` y `computed_as_of` en 1 176 filas. Es manipulación de datos locales y no toca
   ningún código.
3. **Dos pasadas enteras se descartaron por cuota del proveedor**, y es la misma trampa dos veces:
   46 de 90 en el grupo 4 con `--delay 0.3`, y 17 de 42 aquí sin espaciado. Una llamada limitada por
   cuota vuelve en ~150 ms, así que **arrastra el p95 hacia abajo** y empuja la consulta a un estado
   que no es el suyo. La razón está escrita en `DELAY_MS` del arnés, no sólo en este informe,
   precisamente porque ya me había pasado una vez.
4. **Una consulta se volvió a medir sola.** En la pasada complementaria, `q54` volvió con
   `intent=unclassified`, `prompt_version=null` y 1 236 ms: la forma exacta de un enrutador que no
   llegó a llamarse. El log del contenedor lo confirma —05:46:22, `cause=RateLimitError`,
   `groups=2`, el mismo recuento de grupos que la fila—. Repetida en aislamiento, `q54` es una
   **repregunta**, que es lo que le toca a una consulta ambigua. La fila sustituida se conserva en
   el artefacto bajo `superseded_rows`; no se borró.

### 8.2 · El reparto de los dieciséis estados

Las 42 consultas etiquetadas **no pueden**, por construcción, ejercitar la mayoría de los estados:
todas son de dominio y respondibles, así que cubren tres. Publicar «3 de 16» describiría el conjunto
de consultas, no el sistema. Se añadió una **pasada complementaria de 29 consultas** sobre las clases
de rechazo y ambigüedad; el reparto es sobre las **71**.

| # | Estado | n | % |
|---|---|---|---|
| 1 | rechazo · fuera de dominio | 5 | 7,0 |
| 2 | rechazo · no en catálogo | 21 | 29,6 |
| 3 | **repregunta** | 4 | 5,6 |
| 4 | admitida sin índice (`route=none`, `intent=in_domain`) | **0** | — |
| 5 | enrutador degradado (`route=none`, `intent=unclassified`) | **0** | — |
| 6 | abstención · perfil plano | 0 | — |
| 7 | filtro estrecho | 0 | — |
| 8 | ruta `catalog` con prosa | 4 | 5,6 |
| 9 | ruta `knowledge` con prosa | 18 | 25,4 |
| 10 | ruta `both` con prosa | 7 | 9,9 |
| 11 | la puerta retiró **alguna** cita | 5 | 7,0 |
| 12 | la puerta retiró **el argumentario** | 2 | 2,8 |
| 13 | sin cita que sobreviva | 5 | 7,0 |
| 14 | sin credencial de generación | 0 | — |
| 15 | **marcador en el argumentario de M1** | **0** | — |
| 16 | degradado · .NET no obtuvo respuesta | 0 | — |

**Nueve de dieciséis sobre tráfico real.**

### El estado 11 no se distingue desde la respuesta, y eso es un hallazgo

Los estados 8, 9, 10 y 11 llegan a la pantalla con la misma forma: prosa, piezas y una lista de
citas. Que la puerta haya retirado alguna **no viaja en la respuesta**; sólo el campo `withdrawn=`
del log del servicio lo dice. Como la pasada es estrictamente secuencial, las 43 líneas
`stage=assist` de la ventana se correlacionaron por orden con las 43 peticiones —cuadran
exactamente— y ésa es la única razón por la que el 11 puede separarse aquí. Un arnés futuro debería
guardar el `traceId`.

De esas 10 retiradas, en **5 la puerta se llevó todas las citas**, y ésas son las que pintan la línea
discreta «sin fuente verificable» que el grupo 7 añadió: **5 de 39 respuestas con prosa, un 12,8 %**.
El diseño la calibró como línea y no como alerta suponiendo «aproximadamente una cuarta parte»;
medido es la mitad de eso, lo que **refuerza** la decisión, pero la cifra del diseño era pesimista.

### La partición de `route=none` sale vacía, y hay que decir qué significa

La tarea 8.2 pide partir `route=none` por `intent`, que es la distinción entre los estados 4 y 5.
**Los dos salen a cero en las pasadas limpias**, y eso no dice que sean inalcanzables: dice que no
son propiedades de una consulta, sino de un fallo del clasificador. La evidencia de que el 5 es real
está en esta misma sesión: **19 llamadas con `router_degraded=True`** —18 por `RateLimitError` y 1
por `timeout`—, todas con `intent=unclassified`, `route=none` y piezas recuperadas. Es exactamente
el estado 5, observado 19 veces; lo que no está es **dentro** de una pasada limpia, porque cuando
aparece la pasada deja de serlo.

Los estados 4, 6, 7, 14 y 16 quedan cubiertos por los 20 tests de `free-query-states.test.ts`, que
es donde deben estar: el 16 exige apagar un interruptor, el 14 retirar una credencial, y el 7 es el
canal que el grupo 2 dejó **dormido** porque la forma de la petición del panel no permite alcanzarlo.

### El estado 15 a cero cierra el grupo 4 por la vía larga

El grupo 4.7 midió los marcadores **dentro de `jbg-ai`**. Aquí se miden **al otro extremo del
recorrido**, después de `PitchPlaceholderResolver`, del `AiGatewayClient` y de la serialización a
`FreeQuerySearchResponse`: **0 `{{price}}` y 0 `{{stock}}` en 71 respuestas**, con 39 argumentarios
generados. `v5` aguanta todo el camino, no sólo el de dentro.

### Los artefactos

| Fichero | Contenido |
|---|---|
| `ai-service/evals/results/c40-dotnet-latency-42.json` | `run_id` `84afe7037180` · 42 filas con estado numerado, `withdrawn` atribuido y las tres latencias |
| `ai-service/evals/results/c40-dotnet-states-refusals-29.json` | `run_id` `8f2c76386325` · 29 filas de rechazo y ambigüedad, con `superseded_rows` |

Los dos llevan `git_sha` `1c315a9`, `prompt_version` `assist/v5` y `router_prompt_version`
`router/v3`. La pasada de la exploración no se guardó, y por eso el encargo pedía explícitamente que
éstas sí.

---

## 9 · Tramo 2 · los tres interruptores, donde se arranca (grupo 9)

Una sola tarea, y su valor no está en escribirla sino en lo que obligó a comprobar. El bloque de
C36 en `backend/README.md` documentaba dos interruptores; ahora documenta tres, con la tabla de
variables de entorno y un párrafo de sección propio para `AiFreeQuerySearch`.

### La columna que se añadió a la tabla, y por qué es la que importa

La tarea pedía anotar «el hecho de que su ausencia deja la pantalla sirviendo en degradado sin
decirlo». Al comprobarlo contra el código resultó que **ya no es cierto de los tres**, y precisamente
por C40:

| Interruptor | ¿Se anuncia antes de usarlo? |
|---|---|
| `AiSearch:EnabledByDefault` | **sí**, desde C40 — la insignia lee «Búsqueda por texto» |
| `AiSalesAssist:EnabledByDefault` | **no** — sólo abriendo una ficha |
| `AiFreeQuerySearch:EnabledByDefault` | **sí**, desde C40 — la opción asistida sale deshabilitada con su motivo |

`aiAvailable` viaja **dentro** de una respuesta de búsqueda, así que hasta C40 la única forma de
saber que una vía estaba apagada era usarla. `GET /api/ai/search/availability` es la lectura previa
que lo cierra, y lleva `[DisableRateLimiting]` a propósito: heredar la política del controlador
haría que comprobar si puedes buscar **te costara una búsqueda**. La ficha de venta **sigue sin
lectura previa**, y eso queda escrito como lo que hay que mirar antes de diagnosticar una caída.

### Una asimetría real entre los dos extremos del interruptor

Documentarlo obligó a leer las dos comprobaciones, y **no coinciden**:

| Superficie | Qué exige |
|---|---|
| `GET /api/ai/search/availability` | `AiFreeQuerySearch` **y** `AiSalesAssist`, las dos |
| `POST /api/ai/search/assisted` | sólo `AiFreeQuerySearch` |

Cada una es defendible por separado. La lectura previa exige las dos porque la mitad generativa de
la respuesta es la funcionalidad de la ficha y arrastra su perfil de coste; el `POST` comprueba la
suya porque es la que gobierna su propio cupo y su propio presupuesto. Juntas producen un cuadrante
incómodo: **con `AiFreeQuerySearch` encendido y `AiSalesAssist` apagado, el endpoint responde
perfectamente y la opción asistida no se puede pulsar**, con el motivo `switched_off`, que es exacto
pero no nombra ninguno de los dos interruptores — y el que falta es el de la ficha.

No se ha tocado. Cambiar el `POST` para que exigiera los dos alteraría el comportamiento más allá de
lo que el grupo 9 pide, y la opción más estrecha aquí es **documentarlo**, que es lo que se ha hecho
en el bloque del README. Queda anotado para 14.1.

### Lo que esta tarea no cambió

Cero código. La tarea 14.5 vuelve sobre `backend/README.md` junto al resto de la documentación de
contexto, así que aquí sólo se ha escrito lo que hace falta para **arrancar** el sistema sin repetir
la avería: los tres interruptores, sus defectos, sus síntomas y el comando de PowerShell con las
tres líneas.

---

## 10 · Tramo 3 · la sonda, la abstención y la contradicción del enrutador (grupo 10)

El grupo más grande del change, y el que más cosas mide. Siete tareas, todas menos la última en
`ai-service`, y **las dos mediciones que pedía la 10.7 refutan las dos predicciones de la
exploración**.

### 10.1 · La sonda sin filtro

`retrieve_products` emite ahora **una segunda sentencia vectorial sin filtro de cuerpo**, y sólo
cuando la petición trae algo que estreche. Las propiedades que la hacen aceptable no son promesas:
son tests.

| Propiedad | Cómo se comprueba |
|---|---|
| Dos sentencias cuando hay filtro, una cuando no | `search_calls` del puerto falso, contadas |
| **Secuenciales y nunca a la vez** | un contador de peticiones en vuelo sobre el puerto: el máximo es 1 |
| Cero llamadas extra al proveedor | el contador del cliente de *embeddings*: 1 con filtro y 1 sin él |
| Nada de lo que encuentra llega a la respuesta | collares más cercanos que todos los anillos, y ninguno aparece |

La sonda **conserva el ámbito del punto de venta**, y eso es una decisión: el ámbito no es un filtro
del operario, es lo que la tienda tiene. Una sonda que lo ignorase juzgaría la consulta contra un
catálogo desde el que el mostrador no puede vender.

`SearchFilters.is_empty` cuenta los **cuatro** campos, que es la lectura literal de «no trae filtro
de cuerpo». Incluye `exclude_product_ids`, cuyo efecto sobre un perfil de distancias es
despreciable; ningún llamador del orquestador lo usa hoy —`substitutes` compone su propia
sentencia—, así que la lectura literal no cuesta nada y no puede desviarse del requisito.

### 10.2 · La decisión lee el perfil sin filtro, y el perfil se persiste

La abstención se toma ahora sobre las distancias de la sonda cuando la hay. **Ésta es la avería que
el grupo corrige**: leída sobre un perfil filtrado, la regla no puede dispararse cuando el filtro es
estrecho —necesita `min_candidates` dentro de su banda y un filtro estrecho nunca los da—, así que
el sistema servía un puñado de piezas mediocres y, en la ruta generativa, escribía prosa
elogiándolas.

Para que `--rescore` siga pudiendo recalcular una pasada filtrada, `CapturedWindow` gana
`probe_distances` y `Capture` gana la **regla** con la que se capturó. Dos decisiones que conviene
declarar:

- **`CAPTURE_VERSION` no se mueve.** La spec refusa un *re-score* cuando la regla **altera el
  conjunto de candidatos**, y ésta no lo altera: lee otro perfil. Las capturas anteriores siguen
  siendo válidas y un *re-score* de ellas no se rechaza — hay un test que lo fija.
- **La regla viaja en el fichero y no se lee de `Settings()`.** El primer intento la leía de la
  configuración y **rompió la propiedad que la fase C promete**: su test corta todos los *sockets*, y
  `Settings()` exige un entorno. La huella de la fusión ya viajaba en la captura por el mismo
  motivo; la regla la acompaña.

### Y una cosa que el grupo destapó: el *re-score* calculaba la decisión y la tiraba

`rescore` pasaba `abstained` a `score_case` desde siempre, y `aggregate` no promedia ese campo: no
salía por ninguna parte. **Una recomputación que nadie puede leer no es una recomputación**, y el
requisito pide justamente que el *re-score* recalcule en vez de adivinar. Ahora las lecturas llevan
`abstention_rate`, calculada con la función que ya existía. Es aditivo: ninguna clave existente
cambia de valor y la métrica que decide el barrido es otra.

### 10.4 · `filters_too_narrow`, y por qué lo emite recuperación

El código es el sexto del vocabulario cerrado, **añadido al final y nunca insertado**, porque el
orden de esa tupla es lo que un consumidor lee.

Lo emite **recuperación**, no la capa de asistencia, y ésa es la razón de que llegue a las dos rutas
que aceptan filtros en vez de sólo a la generativa: la decisión necesita la sonda, y la sonda vive
ahí. `RetrievalResponse` gana `warnings` —aditivo— y el orquestador de asistencia **lo transporta,
no lo recalcula**, para que las dos rutas no puedan divergir diciendo cosas distintas de una misma
búsqueda.

Una decisión menor declarada: el código se emite sólo con la **regla de abstención encendida**. Los
dos umbrales que lo definen —«no amerita abstención» y «menos que el mínimo»— son de la regla, así
que con la regla apagada el aviso no tendría de dónde salir. Es la opción más estrecha: con la regla
apagada, ningún comportamiento nuevo.

### 10.5 · La contradicción del enrutador, coercida y observable

`served` + sin eje pendiente + `index=None` afirma a la vez «esta consulta es de esta joyería» y «no
hay nada que consultar». El código no puede saber a cuál creer, y hasta ahora **no creía a ninguna**:
no ejecutaba tarea, mientras el *fail-open* del orquestador ya había pagado las dos ramas. Ahora se
coerce a `both`, que es lo que ese *fail-open* ya consulta, y la contradicción queda **observable por
causa** en la línea de etapa: `route=both coerced=router_index_absent`, con `index=None` reportado
igual que antes.

### 10.7 · Las dos mediciones, y las dos refutan a la exploración

#### La tasa de `router_index_absent`: **0 de 42**

| | Predicho (H7) | Medido |
|---|---|---|
| Réplicas contradictorias | **5 de 42 · 11,9 %** | **0 de 42 · 0 %** |

Sobre las 42 consultas etiquetadas, pasadas extremo a extremo por .NET con 4 s de espaciado:
**42 réplicas servidas, 0 degradadas, `coerced=none` en las 42**. Y no es una casualidad de esta
pasada: en el conjunto de tráfico de la sesión anterior —102 réplicas servidas del enrutador, entre
las pasadas de 42 y 29 y las descartadas— la forma `verdict=in_domain index=None missing_axis=None`
**no apareció ni una vez**. Las 29 `index=None` que sí hay son rechazos, donde la ausencia de índice
es correcta.

**La coerción no se ha retirado.** No cuesta nada, resuelve una contradicción que el esquema admite,
y su valor es exactamente el que acaba de ejercer: ahora hay una cifra donde antes había una
predicción. Lo que cambia es cómo se lee el estado 4 de la tabla del panel — no es «el 11,9 % de las
consultas», es un estado que esta versión del clasificador no produce.

#### El coste de la sonda: **20,9 ms de mediana, y sólo cuando hay filtro**

Doce consultas, cada una servida dos veces —sin filtro y con `materials=[plata]` + `category=anillo`—
por `POST /api/ai/search`, la ruta **semántica**: ejercita exactamente la recuperación donde vive la
sonda, acepta los filtros del operario y no hace llamada de generación, así que la medición no la
marca la cuota del proveedor ni la puede contaminar un enrutador limitado.

| | sin filtro (12) | con filtro (12) |
|---|---|---|
| sondas emitidas | **0** | **12** |
| sentencia servida, p50 | 21,3 ms | **9,3 ms** |
| sentencia servida, p95 | 24,9 ms | 12,4 ms |
| **sonda, p50 / p95** | — | **20,9 / 29,3 ms** |
| extremo a extremo, p50 | 82 ms | 87 ms |
| extremo a extremo, p95 | 97 ms | 112 ms |
| `filters_too_narrow` | 0 | 2 |

**Lo que esto refuta.** El ticket justificaba el coste diciendo que *«at 1.168 rows a hard filter
saves no time»*, y de ahí que el escaneo extra fuese «de un dígito de milisegundos». Medido, las dos
mitades fallan y en direcciones opuestas: **el filtro sí ahorra tiempo** —más de la mitad: 21,3 ms
contra 9,3— y **la sonda cuesta dos dígitos**, 20,9 ms, porque es precisamente el escaneo completo
que el filtro evitaba.

**La conclusión operativa no cambia, y conviene decir por qué.** El tiempo de SQL de una búsqueda
filtrada pasa de 9,3 a 30,2 ms, que es triplicarlo; pero lo que el operario espera pasa de 82 a
87 ms, **cinco milisegundos**, porque la ida y vuelta al proveedor de *embeddings* domina el
recorrido. Contra los 3 404 ms de mediana que el grupo 8 midió para la ruta asistida, la sonda es un
**0,6 %**. Y sobre una búsqueda sin filtros cuesta exactamente cero, comprobado: **0 líneas
`stage=probe`** en la pasada de las 42 consultas etiquetadas, que no llevan filtros.

Ese último dato tiene una segunda función. Esa misma pasada dio p50 4 465 ms y p95 8 213 ms, contra
los 3 404 y 7 160 del grupo 8 — sigue dentro del presupuesto, 0 de 42 fuera, pero es más alta. **La
sonda no puede explicarlo**, y no hay que argumentarlo: se emitieron cero. La diferencia es varianza
del proveedor, con 5 argumentarios retirados por la puerta en esta pasada frente a 2 en la anterior.

### Los artefactos

| Fichero | Contenido |
|---|---|
| `ai-service/evals/results/c40-probe-cost.json` | `run_id` `2d876f8c67b9` · 24 filas, las latencias de etapa y el reparto del aviso |
| `ai-service/evals/results/c40-router-index-absent.json` | `run_id` `5e1374166136` · la tasa de coerción y la pasada de la que sale |

### Qué cambió en el conjunto de tests que falla

| Suite | Antes | Ahora |
|---|---|---|
| `ai-service` | 1 592 en verde | **1 616 en verde, 0 rojos** (+24 tests nuevos) |
| `backend` | — | `dotnet build` limpio; 115 de 115 en los ficheros tocados |
| `frontend` | 113 de 729 en 14 ficheros | **113 / 114 de 794 en 14 ficheros** |

El frontend volvió a dar **dos respuestas distintas sobre el mismo código**, 113 y 114 con minutos
de diferencia. El nombre discrepante es `scan.test.tsx :: ScanningPage should show manual SKU input
fallback after initialization`, que **no había fallado en ninguna de las siete pasadas anteriores de
este change y pasa cuando el fichero se corre solo**. No toca nada de C40 — cero referencias a
`ai-search`, `assisted` o `warnings`—. Es un tercer nombre rotatorio; el `CLAUDE.md` documentaba uno
y ahora documenta el criterio útil, que es el del backend: **si el nombre discrepante cae en un
fichero que ya estaba rojo y tu propia área está limpia, no es tuyo**.

### Una tarea que este grupo hizo y no estaba en su lista

jbg-ai emite `warnings` en la respuesta de recuperación, y .NET lo habría **tirado**: la ruta
semántica del panel no tenía por dónde llevarlo. Eso es exactamente la supresión que la regla de
completitud prohíbe, así que se cerró aquí en vez de dejarlo para el grupo 11 — `AiSearchResponse`,
`AssistedSearchResponse`, el tipo del frontend y un bloque de aviso en la ruta semántica, con la
copia compartida. Cuatro adiciones, ningún campo retirado ni cambiado de tipo.
