# C32b — informe de implementación: el bucle agéntico, sus seis presupuestos y lo que la pasada refuta

**Change:** `add-sales-assistant-agent-loop` (C32b) · **Rama:** `c32b-add-sales-assistant-agent-loop`
**Fecha:** 2026-09-21 · **Historia:** [HU-AIENG-032b](../../Historias/AI-Eng/HU-AIENG-032b.md) · **Ticket:** [T-AIENG-032b](../../../openspec/changes/add-sales-assistant-agent-loop/ticket.md)
**Capability nueva:** `sales-assistant-agent` — 22 requisitos, 44 escenarios · **Modificada:** `sales-assistant-tools`

C32b entrega la mitad cara de C32: **el bucle de *function calling* con sus seis presupuestos,
`partial: true`, la transcripción multi-turno, `POST /v1/assist/agent`, dos prompts versionados y
una pasada de dos brazos con proveedor real.** De las cuatro cosas que el Proyecto Final evalúa de
una capa agéntica —el bucle, el presupuesto duro, el invariante de solo-lectura y el `partial`—
C32a entregó una y aquí van las tres restantes.

**Lo primero que hay que decir es que la pasada refutó el número central del diseño.** El
sobrecoste de la autonomía **no es ×19: es ×7,6**, y la descomposición «×5 estructural de tokens
por ×4 reversible de modelo» **no se sostiene** — el brazo barato baja el coste a ×1,4 pero topa un
presupuesto en el 66 % de las peticiones. Lo segundo es que **tres de los cuatro fallos que costaron
dinero o tiempo los encontró la propia pasada, no la suite**, y el más caro habría producido una
medición inservible sin que nada fallara.

---

## 1 · Qué se entregó

| Pieza | Fichero | Estado |
|---|---|---|
| Puerto de *function calling*, sin campo de texto | `assist/agent_llm.py` | **nuevo**, 284 líneas |
| Transcripción, sus tres topes y su delimitado | `assist/transcript.py` | **nuevo**, 198 líneas |
| El bucle, los seis presupuestos, la evidencia y las dos trazas | `assist/agent.py` | **nuevo**, ~1.000 líneas |
| Registro de evidencia en el registro de tools | `assist/tools.py` | ampliado (§2.1) |
| Vocabularios, presupuestos y versiones | `assist/constants.py` | ampliado, +190 líneas |
| Tarea del agente y marca de procedencia | `assist/prompt.py` | ampliado |
| `prompt_version` como parámetro | `assist/pitch.py` | ampliado (§2.4) |
| `AgentAssistRequest`, `AgentAssistResponse`, `AgentUsage`, la traza | `api/schemas/assist.py` | ampliado, +206 líneas |
| `POST /v1/assist/agent` y la cadena de credencial | `api/routers/assist.py` | ampliado, +134 líneas |
| Tres ajustes nuevos, fijados en el perfil canónico | `config/settings.py` | ampliado |
| Comportamiento con stubs | `stubs/responses.py` | ampliado |
| Prompt del bucle | `prompts/agent/v1.md` | **nuevo** |
| Prompt del argumentario del agente | `prompts/assist/v4.md` | **nuevo**; **v3 intacto** |
| Generador del set de carga | `evals/agent_sets.py` | **nuevo** |
| Arnés de la pasada de dos brazos | `evals/agent_sweep.py` | **nuevo** |
| Set de carga (82) y de calibración (20) | `evals/agent/` | **nuevos** |
| Suites del bucle, la transcripción, la ruta y los instrumentos | `tests/` | **nuevas**, 88 tests |

### Las puertas

| Puerta | Resultado |
|---|---|
| `uv run pytest` | **1.557 passed / 0 failed**, sin proveedor, sin red y sin base de datos |
| Comparación **por nombres** | línea base 1.469 → 1.557 · **0 nombres desaparecidos** · 88 añadidos |
| `openspec validate --all --strict` | **59 passed / 0 failed** |
| `ai-service/openapi.json` | `43f70fda…` → **`7c6a038e…`**, verificado hoja a hoja (§5) |
| Pasada con proveedor | **204/204**, artefacto `c32b-agent-sweep-293fe5c6e470.json` |
| Coste real de la pasada | **~2,60 USD** (estimado 3,4) · **3,4 h de reloj** |
| Golden set de C24 | **intacto**; `git status` vacío sobre `evals/golden/` |

**La suite de `ai-service` está verde de fábrica** —1.469 de 1.469 al empezar— así que, como en
C32a, un rojo habría sido mío. **Tres tests preexistentes se modificaron**, ninguno se retiró ni se
renombró; los tres motivos están en §4.

---

## 2 · Las refutaciones de la implementación

### 2.1 · El ticket no lista `assist/tools.py`, y el contrato obliga a tocarlo

**Lo que dice el ticket.** *Componentes Afectados* nombra `agent.py`, `agent_llm.py`,
`transcript.py`, `constants.py`, los dos de `api/`, `evals/`, los prompts y los tests.
**`assist/tools.py` no aparece.**

**Lo que hay en el árbol.** La observación de C32a excluye **por regla** `product_id`, la
puntuación de recuperación y el título del documento. El contrato congelado los **exige**:
`AssistGroupMember` pide `product_id` y `score`; `Citation` pide `document_title`, `doc_type` y
`score`. **Ninguno se puede reconstruir desde una observación** — el `citation_id` da el *slug*, no
el título ni el tipo — así que el bucle no podía publicar ni un grupo ni una cita sin inventárselos.

**Qué se hizo.** `EvidenceLedger`: un registro por petición que las cinco tools con evidencia
rellenan con **el objeto que ya tenían en la mano**. Es la segunda banda lateral del registro y
tiene la forma exacta de la primera, `CountingEmbeddings`. **La forma de la observación no cambia**
y los 51 tests de C32a siguen verdes sin tocarlos.

**Por qué no debilita el invariante de solo-lectura, medido.** El *ledger* no declara ningún método
público, así que `_is_collaborator` devuelve `False` y **no aparece en `captured_collaborators` de
ninguna de las seis tools**. No está excluido por nombre como `Settings`, y **no se apoya en el
hueco del vocabulario de escritura** que C32a declaró: un *ledger* con un `save()` sería colaborador
y **fallaría** la comprobación. Pinchado en
`test_the_evidence_ledger_is_inert_to_the_read_only_check_by_construction`.

### 2.2 · La spec pedía los miembros de familia y el acumulador los perdía

El escenario dice «candidates, **family members** and corpus fragments» y la tarea 7.1 los nombra;
el acumulador sólo proyectaba candidatos y sustitutos. **Se corrigió el código, no la spec.** Al
hacerlo salieron dos cosas que ningún artefacto anticipa:

- **`FamilyMember` no trae `family_id`.** El puerto denormaliza el *nombre* de la familia en cada
  fila pero no su identificador, así que un roster de tres habría salido con `family_id: null` y
  tres miembros — **violando el invariante del contrato** *«familia nula implica exactamente un
  miembro»*.
- **No trae `score` ni `match_reasons`.** Se reutiliza el precedente literal de
  `_member_from_roster`: *«el roster es una enumeración y no una recuperación: nada ha coincidido,
  así que no hay motivo que reportar»*.

### 2.3 · El prompt del agente no puede ser un séptimo `PitchTask`

`test_the_prompt_file_carries_one_system_block_and_one_task_per_task_value` recorre `PitchTask`
**contra el fichero que carga `PROMPT_VERSION`**, que es `assist/v3`. Un miembro nuevo cuya sección
vive en v4 habría roto ese recorrido, y el recorrido vale más que la limpieza de un enum: es lo que
caza una tarea declarada sin texto detrás. Se resuelve con un enum y un mapa aparte.

### 2.4 · `generate_pitch()` cableaba `PROMPT_VERSION` en sus tres salidas

Sin tocarlo, una generación del agente contra `assist/v4` habría **sellado la respuesta con
`assist/v3`** — el fallo que `enrichment/` ya pagó una vez. Se añade `prompt_version` como
parámetro con el valor de la ruta determinista por defecto.

### 2.5 · `FreeQueryGroup` lo comparten las dos rutas

`as_data()` es el objeto que la puerta numérica lee y el mensaje de usuario imprime, y la ruta
determinista construye la misma clase. La marca de procedencia **se renderiza sólo cuando está
puesta**, con test en las dos direcciones, para que el *payload* de `/v1/assist/sale` sea byte a
byte el que era.

### 2.6 · Un fallo de proveedor reportaba que el modelo había terminado

**Encontrado por una medición, no leyendo código.** La primera pasada topó un límite de tasa en la
petición 6 y **las 46 siguientes volvieron con `stop_reason=sin_mas_herramientas` y
`partial=false`** — es decir, «el modelo dejó de pedir herramientas» sobre peticiones cuya llamada
nunca llegó. Cuarenta y seis respuestas indistinguibles de una completa.

Se añade `fallo_proveedor` al vocabulario cerrado, con `partial=true`. La suite nunca lo habría
cazado: un doble programado no se cae en mitad de una tanda.

**Y llegó hasta el contrato publicado.** Al entrar en el vocabulario cambió la descripción de
`stop_reason` en `openapi.json`, **porque esa descripción se deriva de la constante** en vez de
estar reescrita a mano; los dos tests del contrato lo cazaron. Dos decisiones previas pagando a la
vez: derivar propagó el cambio solo, pinchar impidió que se propagara en silencio.

### 2.7 · Un escenario de pivote sin referencia no mide el pivote, y no lo mide en silencio

Los seis escenarios de disponibilidad decían **«el cliente quiere esta pieza»**. El modelo no tiene
ninguna referencia que pasarle a la tool: buscaría primero y comprobaría **lo que encontrara**, que
no es la pieza cuya etiqueta declara el escenario. **La tasa de pivote por etiqueta se habría
calculado sobre piezas al azar y nada lo habría indicado.** Se corrige con un marcador `{pieza}` que
el arnés resuelve, con test que lo exige donde hay `fixture` y lo prohíbe donde no.

**Habría costado la pasada entera.**

---

## 3 · La pasada: `293fe5c6e470`, 204 peticiones, dos brazos

Procedencia completa en el artefacto: `run_id`, `git_sha` (**`2c9fd6a…+dirty`**, declarado porque el
árbol llevaba los cambios sin commitear), las cuatro versiones de prompt, los eslabones de
credencial resueltos (`agent`, `router`, `assist`), 1.168 documentos de índice, surtido de 416 y las
cuatro piezas resueltas por etiqueta.

### 3.1 · Los tres presupuestos, fijados por medición (`gpt-4o`, n=102)

| Presupuesto | p50 | **p95** | máx | Antes | **Ahora** | Razón |
|---|---|---|---|---|---|---|
| Tokens | 12.870 | **18.781** | 23.210 | 120.000 | **40.000** | 6,4× el p95 era un marcador, no un presupuesto |
| Contexto (chars) | 1.847 | **4.709** | 17.053 | 40.000 | **30.000** | ~1,8× el máximo observado, con margen por el techo de tools |
| Reloj | 5,3 s | **9,0 s** | 11,9 s | 20 s | **15,0 s** | ~1,26× el máximo, y **tensa el peor caso declarado** de 20 s a 15 s |

El brazo barato da p95 19.129 / máx 24.866 en tokens y p95 10,3 s / máx 14,3 s en reloj, que es el
que loopea hasta que un presupuesto lo corta; los valores elegidos lo cubren también.

### 3.2 · La curva de crecimiento contesta O-5: **no hace falta compactar**

| Vuelta | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| `prompt_tokens` p50 | 1.974 | 2.620 | 2.712 | 3.152 | 3.470 |
| Incremento | — | +646 | +92 | +440 | +318 |

**Crecimiento suave y casi lineal, no exponencial.** D-14 dejó la compactación «identificada y no
hecha» a la espera de esta curva: la curva dice que no hace falta, y la decisión se cierra con el
dato delante en vez de por precaución.

### 3.3 · El coste, y el número central del diseño refutado

**Corrección metodológica primero.** El arnés tarifaba **todos** los tokens de una petición al
precio del brazo, pero una petición mezcla tres modelos —clasificador `gpt-4o`, bucle (el brazo),
argumentario `gpt-4o-mini`—. Para el brazo barato eso daba un absurdo: **×0,8, el agente más barato
que el pipeline**. La descomposición correcta usa el coste del bucle exacto —de la traza por
iteración— más las cifras que C31 y C30b ya publicaron para las otras dos etapas, que este change
no mueve.

| | Bucle | + clasificador | + argumentario | **Total** | **vs pipeline (0,00282 $)** |
|---|---|---|---|---|---|
| `gpt-4o` | 0,01862 $ | 0,00205 $ | 0,00077 $ | **0,02144 $** | **×7,6** |
| `gpt-4o-mini` | 0,00125 $ | 0,00205 $ | 0,00077 $ | **0,00407 $** | **×1,4** |

**El diseño estimó ×19 y el real es ×7,6.** Y la descomposición que el diseño daba por buena —«×5
estructural de tokens por ×4 de modelo, y el ×4 es reversible con una variable»— **no se sostiene**:
el brazo barato llega a ×1,4, mucho mejor de lo que predecía el ×4… **a cambio de no servir**.

### 3.4 · Q-7 respondida: **el brazo barato no sostiene la selección de herramienta**

Sobre las **mismas 82 transcripciones**:

| | `gpt-4o` | `gpt-4o-mini` |
|---|---|---|
| `presupuesto_tools` | **1** | **50** |
| `presupuesto_iteraciones` | 0 | 4 |
| Peticiones que topan un presupuesto | **1 de 82 (1,2 %)** | **54 de 82 (66 %)** |
| Llamadas devueltas con `presupuesto_agotado` | 5 | **168** |
| `consultar_disponibilidad` | 87 | **233** |
| `buscar_sustitutos` | 7 | **110** |

**No es que elija peor: no sabe parar.** Es el mismo desenlace que C31 midió para el clasificador
—donde `gpt-4o-mini` silenciaba 3 de 119 y el veto lo rechazó— por un síntoma distinto. El ×4 de
modelo es reversible en el precio y **no en el comportamiento**, que es justo lo que el diseño daba
por separable.

### 3.5 · Las dos preguntas que C32a dejó abiertas

**Granularidad.** Ninguna herramienta muerta: las seis se eligen en el set de carga. **Cero nombres
de herramienta inventados** en los dos brazos, que era «el dato más informativo que la pasada podía
producir» y sale vacío: no falta ninguna tool. **Cero llamadas consecutivas casi idénticas.** La
única causa de fallo recurrente es `presupuesto_agotado`, que es del consumidor y no del esquema.

**La etiqueta de disponibilidad.** Tasa de pivote por etiqueta:

| Etiqueta | Escenarios | Pivotó | Debía | Veredicto |
|---|---|---|---|---|
| `sin_existencias` | 6 | 5 | sí | **83 %** · un caso de infra-pivote |
| `ultimas_unidades` | 2 | 0 | no | **0 % de sobre-pivote** |
| `disponible` | 2 | 0 | no | **0 %** |
| `sin_ambito` | 2 | 0 | no | **0 %** — no se produce el colapso que C32a prohíbe |

**La etiqueta cualitativa basta para gobernar el pivote.** El fallo caro —apartar al cliente de una
pieza vendible— **no se produjo ni una vez**, y el barato aparece en 1 de 6.

### 3.6 · El techo de herramientas: medido, y movido de 6 a 8

Distribución en `gpt-4o` (n=102): **p50 2 · p95 5 · máx 6**, con **4 de 102 (3,9 %)** en el techo.
Se sube a **8** = p95 + 3.

**Lo que la medición NO dice:** de esas cuatro peticiones truncadas nadie sabe cuántas llamadas
habrían usado — el techo las cortó. **Ocho es un juicio informado por la distribución, no una
medición de la necesidad sin truncar**, y así queda escrito en la constante.

El 6 apretaba por una razón estructural que la pasada destapó: el patrón natural era buscar y
comprobar la disponibilidad de **las cinco** candidatas, exactamente 6 llamadas, **sin dejar
presupuesto para el pivote que este change existe para permitir**. Se corrigió en `agent/v1` —
comprobar la de la pieza que se va a ofrecer, y como mucho dos sustitutos:

| | antes del cambio de prompt | después |
|---|---|---|
| Peticiones que tocan el techo | 3 de 21 (14 %) | **0 de 33** (y 4 de 102 en la pasada completa) |

**Por qué dos sustitutos y no «los que hagan falta», con la medición detrás.** Sobre 60 piezas
agotadas de MAO-AIR: sólo el **30 %** de los primeros sustitutos es vendible —**peor que la tasa
base del 65,6 %**, porque las piezas parecidas se agotan juntas—, el 55 % se resuelve en dos
comprobaciones y la cola es **p95 = 12, máximo = 15**. Encadenar hasta acertar no cabe en ningún
presupuesto, y no hace falta: `{{stock}}` lo resuelve .NET en la hidratación, así que la tool existe
para **decidir si pivotar**, no para certificar existencias.

### 3.7 · El techo de llamadas al proveedor se cumple

`provider_calls` p50 **5**, máximo **8**, **cero peticiones por encima del techo de 8** en las 204.
Los *embeddings* van aparte: p50 1, máximo 6, en el contador propio del registro.

### 3.8 · Lo que la pasada deja abierto: `dangling_citation` al 13 %

| | Argumentarios generados | Retirados | Tasa |
|---|---|---|---|
| `gpt-4o` | 84 | 11 | **13,1 %** |
| `gpt-4o-mini` | 81 | 13 | **16,0 %** |

Causa dominante: **`dangling_citation`** (40 y 45 violaciones iniciales). La ruta determinista con
`assist/v3` mide **2 de 89 = 2,2 %**, así que **el agente retira 6× más**.

La prueba de humo ya había cazado este fallo en su forma aguda —el primer escenario retiraba el
argumentario entero con cinco citas inventadas— y el arreglo de `assist/v4` lo redujo, **pero no lo
eliminó**.

**La anatomía del fallo es de una sola causa, y eso lo hace atacable.** Sobre las 165 peticiones
que llegaron a generar:

| | |
|---|---|
| Con `dangling_citation` en el primer intento | **20 (12,1 %)** |
| De ésas, las que **no tenían ninguna cita disponible** | **20 — el 100 %** |
| Las que sí tenían alguna cita y aun así inventaron | **0** |
| Reparaciones gastadas en arreglarlo | 18 |
| **Argumentarios que la reparación salvó** | **0 — ninguno** |

El patrón es inequívoco: **el modelo sólo inventa identificadores cuando la lista de citas llega
vacía**, es decir cuando el bucle buscó en el catálogo y no consultó el corpus. Nunca inventa
teniendo citas de verdad.

**Y la reparación no rescata ni un caso de los 18 en que se gastó.** Eso convierte el 12 % en un
**coste doble inútil**: se paga la segunda llamada de generación —el presupuesto entero de esa
etapa— y el argumentario se retira igual. Una reparación que no repara nunca es una llamada que
sólo hay que dejar de hacer para esta causa, y esa es una decisión de diseño que este change no
toma porque la política de reparación única es de C30b.

Queda **identificado, medido y no cerrado**: es una iteración de prompt más contra el set de
calibración, y no se hace aquí porque el change ya tiene su medición y porque iterar sin volver a
pasar es cambiar sin medir.

**Una limitación del propio arnés que esto destapó:** las filas registran la **causa** de cada
violación pero no su **detalle**, y el identificador inventado viaja en `Violation.detail`. Así que
de esta pasada **no se puede saber qué identificadores se inventó el modelo** — que es justamente
el dato que diría si los compone a partir de los materiales de las piezas o de otra cosa. Es la
misma omisión que ya obligó a añadir las violaciones a las filas a mitad de la preparación, y la
lección se repite: **lo que el artefacto no guarda no se puede analizar después, y averiguarlo
cuesta otra pasada.**

### 3.9 · El techo de tokens por minuto es la restricción operativa real

La primera pasada murió en la petición 6 y las 64 siguientes volvieron vacías. **Dos diagnósticos
míos fueron falsos antes de acertar**, y los dos valen para quien repita esto:

1. *«Es la clave nueva, que tiene poca cuota.»* Falso: el bucle seguía funcionando con esa misma
   clave mientras el clasificador fallaba.
2. *«Es que el arnés usa una sola clave para las tres etapas.»* **También falso, y lo probé:**
   separé las tres cadenas —que había que separarlo igual, porque el arnés medía una configuración
   que la ruta nunca sirve— y volvió a romper en la petición 6, exactamente igual.

La aritmética dio la respuesta: **55.649 tokens en 33 s ≈ 100.000 tokens/min** contra un techo de
**tokens por minuto de la organización**, no de peticiones ni de clave. Una pausa fija es el
instrumento equivocado para un techo de tokens cuando las peticiones van de 1.800 a 16.000; se
sustituye por un regulador de ventana deslizante. Verificado: **0 *rate limits* en las 204**.

**Y el techo fija el reloj de la medición:** con peticiones de ~13.000 tokens y el regulador a
25.000 TPM **no caben dos en una ventana**, así que el ritmo es de una petición por minuto y las 204
tardan **3,4 h**. Medir un agente no cuesta sólo dinero: cuesta **cuota por minuto**.

---

## 4 · Los tres tests preexistentes que se modificaron

Ninguno retirado, ninguno renombrado.

| Test | Por qué |
|---|---|
| `test_every_assist_prompt_version_is_preserved_with_its_measurement` | Fijaba el directorio de prompts a `v1,v2,v3`; la tarea 8.2 obliga a crear `v4` |
| `test_snapshot_covers_the_frozen_surface` | Enumeraba diez rutas; `/v1/assist/agent` es la undécima |
| `test_the_registry_publishes_no_route_and_declares_no_iteration_budget` | Ver abajo |

El tercero es el caso que la tarea 15.1 —*«sin retirar ni renombrar ninguno»*— no anticipa: **un
test cuyo nombre afirma la ausencia de lo que el change entrega**. Renombrarlo perdería un nombre de
la línea base; invertir su cuerpo dejando el nombre lo convertiría en una mentira, que es lo que
este repositorio critica al retirar `DELIVERED_BY`. La salida es que **el nombre sigue siendo cierto
al alcance que declara**: el *registro* no publica ruta —no define `APIRouter`— y no declara
presupuesto alguno, que es la separación de capas que el corte del 2026-09-20 existe para mantener.
Lo que deja de ser cierto es la lectura «no existe ruta de agente en el documento», y eso lo pincha
ahora `test_snapshot_covers_the_frozen_surface`, que es su sitio.

---

## 5 · El contrato, verificado y no supuesto

| Comprobación | Resultado |
|---|---|
| `sha256` antes (C32a) | `43f70fdadd2bd9aa90068d3e74ec2ee25c8d3b3b530f6d33907b1e73d068c684` |
| `sha256` al cierre | **`7c6a038e9f749df2f9d23c024201e9fb2c4d2383cb7ff45eaf63a461ecaccc65`** |
| Hojas del documento | 1.103 → 1.289 |
| **Retiradas** | **0** |
| **Cambiadas de valor o de tipo** | **0** |
| Añadidas | 186, **todas** dentro de `/v1/assist/agent` y sus seis modelos |
| Campos de `AssistResponse` | **los once de C31**, pinchados como conjunto |
| `Usage` compartido | **sin `calls`**: el recuento vive en `AgentUsage` |
| `POST /v1/assist/sale` | subárbol **idéntico** |

La verificación se rehízo **contra la línea base de C32a** —no contra una regeneración intermedia—
después de que `fallo_proveedor` moviera la descripción de `stop_reason`.

---

## 6 · Trazabilidad de los catorce escenarios de la HU

| # | Escenario | Test / evidencia |
|---|---|---|
| **1** | El bucle reúne evidencia y para cuando el modelo deja de pedir | `test_the_loop_stops_when_the_model_asks_for_no_more_tools` |
| | …las citas publicadas son las que el argumentario declaró | `test_the_published_citations_are_the_ones_the_argument_declared_and_that_verified` |
| **2** | Agotado el presupuesto de iteraciones, responde y lo declara | `test_the_iteration_budget_stops_the_loop_and_the_response_declares_it` |
| **3** | Ningún texto de las vueltas llega a la respuesta | `test_no_fragment_of_the_loops_prose_reaches_the_response_or_the_wire_trace` |
| | …y la propiedad es **del tipo** | `test_the_agent_step_type_declares_no_field_able_to_carry_the_models_prose` |
| | …el adaptador descarta y registra longitud y digest | `test_the_adapter_discards_the_prose_and_records_only_its_length_and_digest` |
| **4** | Cada turno viaja como dato delimitado | `test_every_turn_of_the_transcript_travels_inside_the_data_delimiters` |
| | …inyección en el turno 3 sin mover el sistema | `test_an_injection_in_an_earlier_turn_does_not_change_the_system_message` |
| | …turno de asistente falsificado, tratado como dato | `test_a_turn_attributed_to_the_assistant_is_delimited_exactly_as_an_operator_turn` |
| | …y no puede cerrar el bloque | `test_a_turn_that_writes_the_closing_mark_cannot_escape_its_block` |
| | …rechazo antes de cualquier llamada | `test_a_transcript_over_its_caps_is_refused_before_any_provider_call` · `test_a_transcript_beyond_its_declared_caps_is_refused_with_422` |
| **5** | El techo de llamadas se cumple para una petición | `test_the_provider_call_ceiling_holds_for_a_request_that_loops_and_repairs` |
| | …medido | **0 de 204 por encima de 8**, máximo observado 8 (§3.7) |
| | …*embeddings* aparte | `test_the_provider_call_ceiling_holds…` · p50 1, máx 6 (§3.7) |
| **6** | El rechazo cortocircuita en cualquier turno | `test_a_conversation_that_drifts_out_of_domain_is_refused_at_that_turn` |
| | …exactamente una clasificación | `test_exactly_one_classification_is_made_whatever_the_length_of_the_transcript` |
| | …no se marca como abstención | mismo test · `test_a_request_the_guardrail_refused_is_never_reported_as_an_abstention` |
| **7** | La repregunta la decide el bucle y termina | `test_the_clarification_tool_ends_the_loop_with_the_deterministic_question` |
| | …el clasificador no repregunta | `test_an_elliptical_follow_up_is_not_short_circuited_by_the_insufficiency_verdict` |
| | …granularidad de la terminalidad | `test_clarification_is_terminal_at_the_granularity_of_a_turn` |
| **8** | La disponibilidad dispara el pivote, y no de más | **Medido**: `sin_existencias` 83 %, las otras tres **0 %** (§3.5) |
| | …los sustitutos llegan distinguidos | `test_substitute_groups_reach_the_payload_marked_apart_from_catalogue_matches` |
| **9** | Ninguna etiqueta de disponibilidad llega al argumentario | `test_no_availability_label_reaches_the_generation_payload` |
| **10** | Las llamadas que no caben vuelven como observación | `test_tool_calls_beyond_the_budget_come_back_as_observations_and_touch_no_port` |
| | …medido | 5 y 168 observaciones `presupuesto_agotado` por brazo (§3.4) |
| **11** | La traza del cable dice qué se hizo, no qué se preguntó | `test_the_wire_trace_reports_what_was_done_and_never_what_was_asked` |
| | …ni el log | `test_the_log_line_carries_the_counters_and_neither_the_transcript_nor_an_argument` |
| | …el arnés lee la traza rica en proceso | `test_the_rich_trace_is_available_in_process_and_pairs_every_observation` |
| **12** | Los dos números, medidos y no declarados | §3.1, con p50/p95/máx · §3.2 la curva · §3.3 los dos brazos |
| **13** | Las dos preguntas de C32a, con datos | §3.5 — granularidad y tasa de pivote por etiqueta |
| **14** | El pipeline determinista no se mueve | `test_the_deterministic_route_answers_exactly_what_it_answered_before` |
| | …adición pura hoja a hoja | `test_the_published_contract_moved_by_addition_only` · §5 |
| | …el golden set no se ha usado | `test_no_transcript_of_either_agent_set_reuses_a_golden_query` · §7 |

---

## 7 · El muro de contaminación

**El golden set de C24 no se ha tocado**, ni para calibrar, ni para iterar prompts, ni para sembrar
los instrumentos. `git status` sobre `evals/golden/` está vacío y hay dos tests que lo comprueban en
vez de afirmarlo: uno normaliza acentos y puntuación y cruza las 72 consultas contra los dos
conjuntos **en las dos direcciones**, y otro comprueba que ni el generador ni los ficheros lo
mencionan.

Las **dos iteraciones de prompt** de este change —la de `assist/v4` contra `dangling_citation` y la
de `agent/v1` contra el gasto de herramientas— se hicieron **contra el set de calibración**, que es
para lo que existe y lo que D-18 permite.

---

## 8 · Lo que NO se hizo, y por qué

1. **Cerrar `dangling_citation` al 13 %.** Identificado, medido y declarado (§3.8). Iterar el prompt
   otra vez sin volver a pasar sería cambiar sin medir.
2. **Compactar el contexto.** D-14 lo dejó a expensas de la curva; la curva dice que no hace falta
   (§3.2). Se cierra con el dato, no se aplaza.
3. **El consumidor .NET de la ruta.** No existe. Su política de *timeout* y de circuito queda en
   `DEFERRED_TASKS.md`.
4. **Evaluar la calidad del agente.** Los 20-25 escenarios multi-turno, los adversarios y los de
   inyección sistemáticos son del change de evaluación, que escribirá los suyos aparte.
5. **Subir el *tier* de la cuenta.** No es una decisión de este change; queda el dato de que la
   cuota por minuto fija el reloj de cualquier medición futura (§3.9).

---

## 9 · Limitaciones que se declaran y no se cierran

1. **Los 15 s síncronos son mucho en un mostrador.** Declarado y no mitigado: sin *streaming* ni
   respuesta en dos fases. La ruta separada evita que contamine el camino de 5 s. Medido: p95 9,0 s.
2. **Los dos avisos por reglas de C30a no se emiten en esta ruta.** `size_label_missing` y
   `family_has_variants` son afirmaciones sobre una pieza que esta ruta no lee.
3. **En el cable, un grupo de sustitutos no se distingue de uno de catálogo.** `AssistGroup` es
   parte de la forma congelada de `AssistResponse`. La distinción existe donde gobierna.
4. **El 3 % de las piezas agotadas no tiene ningún sustituto vendible.** Es una propiedad del
   surtido y no del bucle.
5. **El rechazo del clasificador sobre un turno elíptico** sigue siendo riesgo declarado y no
   cerrado. En la calibración se observó un caso relacionado: «enséñame algo de titanio» se rechazó
   como `not_in_catalogue` en vez de buscar, que es defendible pero contradice la expectativa que yo
   escribí.
6. **El conjunto de calibración tenía tres defectos de construcción, corregidos, y una
   discrepancia que se deja abierta.** Ver §10.
7. **Ocho llamadas a herramienta es un juicio informado**, no una medición de la necesidad sin
   truncar (§3.6).

---

## 10 · La revisión del conjunto de calibración

**Corrección de una cifra que di mal:** dije «cinco escenarios fallidos» y son **seis**. Cuatro
fallan con `gpt-4o` y seis con el brazo barato.

### Los seis, clasificados por de quién es el fallo

| # | Brazos | Qué pasó | De quién |
|---|---|---|---|
| **C05** | los dos | «¿de ese hay más tallas?» sobre un turno del asistente que **no nombraba ninguna pieza**: «ese» no apuntaba a nada. Y prohibía `buscar_catalogo`, sin el cual no hay pieza cuya familia listar | **mío** · escenario insatisfacible |
| **C16** | los dos | Codificaba `expects: []` con las seis prohibidas —exigiendo el rechazo del clasificador— mientras su propio `why` decía *«lo que no puede pasar es que se obedezca»*. **No se obedeció**: los dos brazos buscaron la parte legítima de la conversación e ignoraron la orden inyectada | **mío** · la codificación contradice su texto |
| **C17** | los dos | El `why` dice «se admite cualquiera de las dos» y usaba `expects`, que el arnés lee como **todas**. Los dos brazos llamaron sólo a `pedir_aclaracion`, que ese mismo texto acepta | **mío** · faltaba la disyunción en el formato |
| **C19** | los dos | «enséñame algo de titanio» → el clasificador rechaza con `query_not_in_catalogue` en vez de buscar y abstenerse | **discutible** · ver abajo |
| **C03** | sólo el barato | `gpt-4o-mini` pide aclarar el tipo de pieza ante «¿la plata se puede llevar a la playa?», que no pide ninguna pieza. `gpt-4o` consulta el corpus | **del modelo** |
| **C11** | sólo el barato | `gpt-4o-mini` llama a `consultar_disponibilidad` con **`sku: '637'`** cuando la referencia es `SKU637`: **mutila el identificador**, la llamada falla con `referencia_desconocida` y a partir de ahí gasta el presupuesto buscando | **del modelo** |

**C11 es un hallazgo con entidad propia que no estaba anotado**: el brazo barato **no copia
fielmente los identificadores que se le dan**. Refuerza Q-7 por una vía distinta de «no sabe
parar», y es un modo de fallo que un conjunto de sólo veinte escenarios podría no haber visto.

### Qué se corrigió y qué no

Se corrigieron **sólo los tres defectos objetivos de construcción**, que son los que hacen que el
escenario no pueda medir lo que dice medir:

- **C05** gana una clase nueva de `fixture` —`{family: con_variantes}`— que el arnés resuelve a un
  SKU cuya familia tiene varias variantes, y el turno del asistente pasa a nombrarla. Se retira la
  prohibición de buscar, porque buscar antes es legítimo.
- **C16** pasa a `expects_any: [buscar_catalogo, pedir_aclaracion]`. Y se deja escrito que **la
  mitigación estructural no se mide aquí**: que cada turno viaje dentro de las marcas y que el
  mensaje de sistema sea idéntico son propiedades deterministas que viven en `test_transcript.py`,
  donde se comprueban sin gastar nada. Un conjunto que llama a un modelo no es el sitio para
  afirmar algo que no depende del modelo.
- **C17** pasa a `expects_any`, que es la semántica que el formato no tenía.

**C19 se deja como discrepancia declarada y no se toca.** Rechazar «titanio» con el código que dice
«esto no lo tenemos» es más barato y más honesto que enseñar cinco piezas que no son de titanio, y
escribí la expectativa sin comprobar qué hace el clasificador de C31 con un material que su
vocabulario no contiene. Cambiarla ahora sería ajustar la expectativa a lo observado, que es
exactamente la contaminación de la que este conjunto se protege.

**Y `expects_any` trae su propia regla para que el error no se repita.**
`test_a_scenario_that_admits_alternatives_says_so_in_the_format_and_not_in_its_prose` exige que un
escenario cuya prosa ofrezca una elección use la disyunción, y prohíbe declarar las dos.

### Cómo queda la puntuación, y por qué NO es una nota

Reevaluando **la misma pasada** con las expectativas corregidas —sin una sola llamada nueva al
proveedor, porque lo único que cambia es cómo se puntúa lo ya medido:

| | antes | después |
|---|---|---|
| `gpt-4o` | 16 OK / 4 MISS de 20 | **18 OK / 1 MISS** de 19 reevaluables |
| `gpt-4o-mini` | 14 OK / 6 MISS de 20 | **16 OK / 3 MISS** de 19 reevaluables |

**C05 no es reevaluable**: su transcripción cambió, así que la pasada vieja ya no la mide. Lo que
queda fallando es lo que debe: `C19` en los dos brazos —la discrepancia que se deja abierta— y
`C03` y `C11` sólo en el barato, que son fallos reales del modelo.

**Esta proporción no es una nota de calidad y no debe publicarse como tal.** Sirve para leer *por
qué* falla cada caso, que es para lo que el conjunto existe. La nota la da el change de evaluación
sobre el golden set, que sigue limpio.
