# C31 — informe de implementación: el enrutador, y las siete cosas que la implementación refuta

**Change:** `add-guardrails-and-intent-router` (C31) · **Rama:** `c31-add-guardrails-and-intent-router`
**Fecha:** 2026-09-15 · **Historia:** [HU-AIENG-031](../../Historias/AI-Eng/HU-AIENG-031.md) · **Ticket:** [T-AIENG-031](../../../openspec/changes/archive/2026-09-16-add-guardrails-and-intent-router/ticket.md)
**Conjunto de enrutado:** [`evals/routing/cases.yaml`](../../../ai-service/evals/routing/cases.yaml) — 119 casos, seis clases

C31 entrega el enrutador de intención y los guardarraíles de entrada: clasificación de la
consulta libre **antes de recuperar nada**, dos puertas con dos códigos distintos, rechazo
cortés, repregunta determinista desde catálogo cerrado, guardarraíl gratuito en el modo anclado
con pregunta, argumentario de la consulta libre, y `openapi.json` movido **sólo en
descripciones**.

Este informe recoge lo **medido**. Y lo primero que hay que decir es que la primera medición
**tumbó el change**: el veto declarado antes de medir rechazó la primera configuración, y llegar
a una que pasara costó **tres revisiones de prompt y un barrido de modelo**. Lo segundo es que el
riesgo mayor que la ficha declaraba —la lista blanca numérica ensanchada por cada candidato— **no
se materializó ni una vez**, y el que sí tumbó el argumentario de M1 era otro que nadie había
escrito.

---

## 1 · Qué se entregó

| Pieza | Fichero | Estado |
|---|---|---|
| Esquema de salida del clasificador, interno y con `Literal` | `assist/schema.py` | nuevo bloque |
| Cliente del clasificador, costura replicada | `assist/router_llm.py` | **nuevo**, ~150 líneas |
| Proyección, plantillas de repregunta y *fail-open* | `assist/routing.py` | **nuevo**, ~300 líneas |
| Prompt del clasificador, tres versiones | `prompts/router/v1.md`, `v2.md`, `v3.md` | **nuevo** |
| Prompt del argumentario, dos versiones nuevas | `prompts/assist/v2.md`, `v3.md` | **nuevo**; `v1.md` **intacto** |
| Tareas por ruta y segunda forma de *payload* | `assist/prompt.py` | ampliado |
| Cableado, corte antes de recuperar, techo de 3 | `assist/orchestrator.py` | ampliado |
| Tres ajustes con cadena de repliegue | `config/settings.py`, `api/routers/assist.py` | ampliado |
| Vocabularios: 3 intenciones y 3 códigos nuevos | `assist/constants.py` | ampliado |
| Carga del manifiesto y matriz de confusión | `evals/routing.py`, `evals/routing_run.py` | **nuevo** |
| Puerta numérica de M1, medida aparte | `evals/free_query_gate.py` | **nuevo** |

**Suite:** línea base **1.320 passed / 0 failed**; al cierre **1.415 passed / 0 failed**,
comparada **por nombres** y no por recuento: **99 tests nuevos** y **4 renombrados**, cada uno
con sucesor nombrado, porque los cuatro afirmaban una propiedad que este change invierte a
propósito —los vocabularios cerrados «en exactamente dos» y «el modo de consulta libre no tiene
bloque de tarea»—. **Ningún test desaparece sin sucesor.** La suite de `ai-service` está verde
de fábrica, así que rojo habría sido mío.

| retirado | sucesor |
|---|---|
| `test_warning_vocabulary_holds_exactly_two_codes` | `..._holds_the_two_rule_codes_and_the_three_of_the_router` |
| `test_the_intent_vocabulary_has_exactly_two_members` | `..._gained_the_routing_verdicts_and_kept_the_piece_anchored_one` |
| `test_the_free_query_mode_has_no_task_block_at_all` | `test_a_free_query_mode_cannot_pick_a_task_without_a_decided_route` |
| `..._one_system_block_and_one_task_per_anchored_mode` | `..._one_system_block_and_one_task_per_task_value` |

**`openspec validate --all --strict`:** 58 passed / 0 failed de partida y al cierre.

---

## 2 · Las siete refutaciones

### R1 · El veto tumbó la primera configuración, y eso es el veto funcionando

D12 declaró, **antes de medir**, que una sola consulta contestable silenciada rechaza la
configuración. La primera medición de `router/v1` sobre los 119 casos:

| | valor |
|---|---|
| Acierto sobre `catalog` | **47,9 %** |
| Falso positivo sobre `catalog` | **31,25 %** |
| Consultas contestables silenciadas | **15**, diez de ellas `descripcion-sin-anclaje` |
| Veto | **NO PASA** |

No es un accidente de redacción: es el riesgo que la ficha declaraba como principal, ocurriendo.
Y la razón por la que se declaró antes de medir es exactamente la que se vio después — con las
veinte imposibles capturadas al 95 %, la tentación de llamarlo «suficientemente bueno» estaba
servida.

### R2 · Lo que fallaba no era la clasificación de intención: era no saber cómo se nombra el catálogo

Las diez `descripcion-sin-anclaje` silenciadas por v1 son todas del mismo tipo: `la lagartija que
toma el sol en las paredes`, `el fruto de la encina`, `el bicho con puas que se pisa en las
rocas`, `un molusco que se agarra a las piedras`, `una brujula para no perder el rumbo`. El
clasificador las leía como *«no es una pregunta de joyería»* y tenía razón en lo literal.

Lo que le faltaba está en el propio catálogo, leído en `data/catalog/real/`:

```
SKU01  Pendientes botón erizo de mar mini
SKU06  Colgante erizo de mar S
SKU102 Anillo caracola
SKU107 Colgante cono de mar oro
```

**Las piezas de esta casa se llaman `<tipo> <motivo>`, y el motivo es una cosa del mundo.** Una
consulta que describe una cosa **es** una consulta de catálogo, porque pide la pieza que la
representa. `el bicho con puas que se pisa en las rocas` es el erizo de mar, y hay diez piezas
con ese motivo en el índice.

Eso reencuadra la ficha una vez más. El problema de la puerta de cobertura **no es distinguir
intención de cobertura** —que es lo que la exploración corrigió— sino algo más fino: distinguir
**un artículo de otro oficio** de **un motivo de éste**. La regla que lo corta, y que es la que
acabó funcionando, es negativa: `not_in_catalogue` es una lista corta y cerrada de cosas que
alguien compraría de verdad en una joyería —platería de mesa, relojería, joyeros, papelería,
lingotes— y **nadie entra en una joyería a comprar una bicicleta**.

### R3 · Lo que decide el veto no es el prompt, es el modelo

Tres revisiones de prompt llevaron el falso positivo de 31,25 % a 6,25 % y **no lograron
cerrarlo**. Cambiar el modelo, **con el mismo prompt y sin tocar una palabra**, lo cerró:

| run | prompt | modelo | `catalog` | falso positivo | silenciadas | degradadas | veto |
|---|---|---|---|---|---|---|---|
| [`426a70070ad3`](../../../ai-service/evals/results/c31-routing-confusion-426a70070ad3.md) | `router/v1` | `gpt-4o-mini` | 47,9 % | 31,25 % | 15 | 0 | **NO** |
| [`de9297ad6515`](../../../ai-service/evals/results/c31-routing-confusion-de9297ad6515.md) | `router/v2` | `gpt-4o-mini` | 79,2 % | 8,33 % | 4 | 22 ⚠ | **NO** |
| [`e36e4b0196df`](../../../ai-service/evals/results/c31-routing-confusion-e36e4b0196df.md) | `router/v3` | `gpt-4o-mini` | 81,3 % | 6,25 % | 3 | 0 | **NO** |
| [`2b5b98c81e28`](../../../ai-service/evals/results/c31-routing-confusion-gpt4o-2b5b98c81e28.md) | `router/v3` | **`gpt-4o`** | **100 %** | **0,00 %** | **0** | 0 | **PASA** |

Las tres que `gpt-4o-mini` seguía silenciando en v3 son `el calzado tipico que se lleva en las
fiestas de la isla`, `una brujula para no perder el rumbo` y `una bicicleta antigua` — y **las
tres están nombradas literalmente en el prompt de v3** como ejemplos de lo que *no* hay que
rechazar. El modelo pequeño las rechazaba de todas formas.

**Esto refuta la opción por defecto nº 4 del ticket** (*«mismo `gpt-4o-mini` de partida»*) y
**vindica D9** con una medición: la variable separada del modelo es lo único que permitió mover
el del clasificador **sin tocar el del argumentario**, cuyo coste y tasa de rechazo están
medidos sobre otro. Si los dos hubieran compartido variable, este barrido no se podría haber
hecho sin invalidar las 120 generaciones de C30b.

`DEFAULT_ROUTER_MODEL` queda fijado en **`openai/gpt-4o`**, con la tabla al lado en el docstring.

### R4 · El veto podía aprobar de forma vacía, y aprobó

Una pasada de `gpt-4o` con concurrencia 6 murió de límite de tasa en **89 de 119 casos**, y el
informe dijo **«PASA — 0 consultas contestables silenciadas»**. Es correcto por construcción y
falso como criterio: un caso que no se clasificó **no es un rechazo**, así que cero violaciones
sobre cero mediciones no es un aprobado, es una pasada rota.

`veto.passed` ahora exige **cobertura completa sobre la clase contestable**, el informe publica
las degradaciones de toda la pasada, y hay un test que lo fija. **Un criterio que una pasada rota
satisface no es un criterio**, y esto no estaba escrito en ningún artefacto del change.

### R5 · El riesgo mayor declarado no se materializó — y el que tumbó M1 era otro

La ficha, el diseño y la HU coinciden en señalar como riesgo principal del argumentario de M1 el
**ensanchamiento de la lista blanca numérica**: la puerta midió **0 violaciones en 120
generaciones** con una pieza, y cinco candidatos aportarían cinco SKU, cinco tallas y cinco
etiquetas de variante.

Medido contra el índice real, sobre consultas reales del golden set:

- La lista blanca real es de **15 numerales**, no de cinco: `top_k=5` son **familias tras
  hidratar**, y la recuperación devuelve **15 candidatos**. El riesgo era **tres veces** el
  declarado.
- Violaciones de la puerta numérica en la primera generación: **cero**. Ni una.
- Lo que sí rechazaba el argumentario era `dangling_citation` — **3 de 4** en la sonda que lo
  destapó, y la sonda era de **cuatro consultas**: basta para ver la causa y **no** para publicar
  una tasa, así que aquí va como recuento y no como porcentaje.

La ruta `catalog` entrega al modelo candidatos y **ninguna** cita —la lista `corpus` llega
vacía— y el modelo **declaraba citas igualmente**, inventando identificadores. La causa no
estaba en el modelo: la sección de tarea de `catalog` en `assist/v2.md` **no mencionaba las
citas en absoluto**, así que la única instrucción que el modelo tenía sobre ellas era la regla
invariante *«puedes no citar nada»*, que **permite pero no obliga**. `assist/v3.md` lo dice
explícitamente y `v2.md` se conserva con su recuento publicado.

> **La lección que vale más allá de este change:** una regla invariante permisiva no sustituye a
> una instrucción de tarea. Donde los datos no traen algo, hay que decir que no lo traen.

### R6 · La primera llamada de un proceso paga el `import litellm` dentro de su propio *timeout*

Medido en el arnés: los **dos primeros** casos de una pasada agotaron **20 s** y no por el
proveedor, sino porque `assist/router_llm.py` importa `litellm` **dentro** de la llamada —
deliberadamente, para que el paquete siga siendo importable y la suite offline — y ese import
cae dentro de `asyncio.wait_for`.

Con el corte de servicio en **2 s**, eso significa que **la primera consulta libre tras un
arranque en frío degrada**. Cae en el *fail-open*, que es el comportamiento correcto, pero es una
degradación evitable calentando el import al arrancar la aplicación. No se toca aquí —el arranque
está fuera del alcance— y queda anotado en `DEFERRED_TASKS.md`.

### R7 · El test de la muestra del barrido de C30b habría falsificado su propia procedencia

`evals/assist/sweep-sample.yaml` declara `prompt_version: assist/v1` porque es **la versión
contra la que se midieron las 120 generaciones de C30b**, y su test lo comparaba contra la
constante `PROMPT_VERSION` del código. Al mover la constante a `assist/v2`, el test falla y la
reparación obvia —actualizar el fichero— **falsificaría la procedencia de una medición ya
publicada**, que es exactamente lo que D10 existe para impedir, llegando por la dirección que
nadie había previsto.

El test ahora fija la versión histórica literalmente y comprueba que difiere de la actual.

---

## 3 · La matriz de confusión publicada

Configuración servida: **`router/v3` sobre `openai/gpt-4o`**, temperatura 0, 119 casos,
**0 degradaciones**. Artefacto: [`c31-routing-confusion-gpt4o-2b5b98c81e28.json`](../../../ai-service/evals/results/c31-routing-confusion-gpt4o-2b5b98c81e28.json).

| esperada \ predicha | `catalog` | `knowledge` | `both` | `ambiguous` | `not_in_catalogue` | `out_of_domain` | n | acierto |
|---|---|---|---|---|---|---|---|---|
| `catalog` | **48** | 0 | 0 | 0 | 0 | 0 | 48 | **100 %** |
| `knowledge` | 1 | **28** | 3 | 0 | 0 | 0 | 32 | 88 % |
| `both` | 2 | 0 | **8** | 0 | 0 | 0 | 10 | 80 % |
| `ambiguous` | 0 | 0 | 0 | **4** | 0 | 0 | 4 | **100 %** |
| `not_in_catalogue` | 0 | 0 | 0 | 0 | **20** | 0 | 20 | **100 %** |
| `out_of_domain` | 0 | 0 | 0 | 0 | 1 | **4** | 5 | 80 % |

Por categoría del golden set, dentro de `catalog` — **todas perfectas**, incluidas las doce que
el veto protege:

| categoría | n | acierto |
|---|---|---|
| `descripcion-sin-anclaje` | 12 | 12/12 |
| `variante-talla` | 7 | 7/7 |
| `sinonimos` | 6 | 6/6 |
| `materiales` | 5 | 5/5 |
| `subjetiva` | 5 | 5/5 |
| `sustituto` | 5 | 5/5 |
| `piedra` | 4 | 4/4 |
| `lexico-exacto` | 4 | 4/4 |

### Las dos cifras, que **no son sumables**

| cifra | valor | mecanismo |
|---|---|---|
| **Rechazo del enrutador** | **21,01 %** (25 de 119) | clasifica **antes** de recuperar |
| **Abstención del retriever** (C25, sin tocar) | **10 %** | lee el perfil de distancias **después** de recuperar |

**No se suman, y no por prudencia retórica.** Se miden sobre conjuntos distintos con mecanismos
distintos: el 21,01 % es la fracción de los 119 casos del conjunto de enrutado que el
clasificador rechazó, y las 25 consultas rechazadas son **exactamente** las que había que
rechazar. El 10 % de C25 es la tasa de abstención del retriever sobre el golden set, medida
sobre 43 consultas contestables antes de que C26 añadiera las cinco de sustitutos. Sumarlas
produciría un «31 %» que no describe ninguna población.

### El falso positivo sobre la clase contestable, como cifra propia

**0,00 %.** Ninguna de las 48 consultas que la tienda **sí** puede contestar quedó silenciada, y
ninguna de las doce `descripcion-sin-anclaje`. **El veto pasa**, con cobertura completa.

Es una cifra propia y no el complemento de ningún acierto: una consulta de `catalog` enviada a
`knowledge` es un error de ruta que enseña una explicación en vez de piezas —recuperable— y una
**rechazada** no enseña nada, que es el fallo en el mostrador.

### Las tres limitaciones, declaradas antes de los números

1. **Los diez casos `both` son construidos**, derivados de las propias `eval_question` del
   corpus. Miden si el enrutador reconoce una consulta compuesta, **no** con qué frecuencia un
   operario real escribe una. Ocho llevan par de control.
2. **Las veinte `not_in_catalogue` fueron elegidas para ser insatisfacibles**, así que el 100 %
   medido sobre ellas es una **cota superior** de lo que verá un mostrador real.
3. **La cifra final es dentro de muestra.** Tres revisiones de prompt y un barrido de modelo se
   decidieron mirando resultados sobre este mismo conjunto. La partición de ajuste del golden
   set —8 consultas, y sólo una de `descripcion-sin-anclaje`— es demasiado pequeña para sostener
   una lectura retenida, y se dice en vez de disimularse. Lo que **no** queda contaminado es el
   **veto**: es un criterio de rechazo declarado antes de medir, y una configuración que lo falla
   sigue rechazada por muchas iteraciones que se hayan hecho.

---

## 4 · El contraste enrutador ↔ umbral `0,51` (D3, tarea 10.6)

C23 fijó `jpv_knowledge_distance_threshold = 0,51` sobre un **hueco limpio de 8 milésimas**, y su
propio informe advirtió de que el margen es estrecho *«y por construcción»*. El enrutador da una
**segunda opinión independiente** sobre las mismas 37 preguntas:

| | umbral `0,51` (C23) | enrutador (`gpt-4o`) |
|---|---|---|
| 32 preguntas que el corpus responde | 32 por debajo (**100 %**) | **32 admitidas**, 0 rechazadas |
| 5 preguntas de fuera | 5 por encima, 0 citas (**0 %**) | **5 rechazadas**, 0 admitidas |

**Discrepancias sobre el eje servir / no servir: 0 de 37.** Dos mecanismos que no comparten ni
entrada ni método coinciden por completo, lo que es la evidencia más fuerte disponible de que el
margen estrecho de C23 separa algo real y no un artefacto del corpus.

Donde sí difieren es en el **grano**, y eso es información nueva y no desacuerdo: de las 32 que
el umbral trata como una sola clase, el enrutador manda 28 a `knowledge`, 3 a `both` y 1 a
`catalog`. Y de las 5 de fuera, el enrutador distingue 4 `out_of_domain` de 1
`not_in_catalogue` — una distinción que el umbral no puede hacer, porque sólo sabe decir
«ninguna cita».

---

## 5 · La puerta numérica de M1, publicada **aparte** (tarea 10.5)

Medido contra el **índice real** —1.168 documentos de catálogo, 161 fragmentos de corpus— con el
enrutador real decidiendo la ruta, sobre las **90** consultas del conjunto que pueden generar
(`catalog`, `knowledge` y `both`; las rechazadas y las repreguntadas no llaman al proveedor y no
tienen nada que decir sobre una puerta). Artefacto:
[`c31-free-query-gate-387fa94e792a.json`](../../../ai-service/evals/results/c31-free-query-gate-387fa94e792a.json).

**Publicada aparte de la de M2/M3 porque no son la misma puerta**, que es lo que la tarea 10.5
pide y lo que la comparación de poblaciones exige: la anclada lee un *payload* de **una pieza**,
ésta lee hasta **quince**.

| | M2/M3 (C30b) | **M1 (C31)** |
|---|---|---|
| Generaciones medidas | 120 | **89 de 90** (0 degradaciones del enrutador) |
| Numerales de la lista blanca | ~4 (una pieza) | **13,0 de media, máximo 23** |
| Candidatos en el material | 1 | **9,4 de media, máximo 15** |
| **Violaciones de la puerta numérica** | **0** | **0** |
| Argumentario retirado | 0 | **2 de 89 — 2,25 %** |

**Cero.** Ni una sola `figure_not_in_context`, `currency_adjacent_figure`,
`stock_adjacent_figure`, `decimal_form` ni `enumeration_format` en 89 generaciones con listas
blancas tres veces más anchas que las de C30b. El riesgo que la ficha, el diseño y la HU
declaraban como el principal de este change **no se materializó ni una vez**.

Las dos retiradas, en detalle, porque una de ellas no es una retirada de la puerta:

| caso | tarea | lista blanca | causa | qué pasó |
|---|---|---|---|---|
| `b05` | `free_query_both` | 15 | `dangling_citation` | sobrevivió a la reparación y se llevó el argumentario — **la única retirada real de la puerta: 1 de 89, 1,12 %** |
| `q11` | `free_query_catalog` | 5 | *ninguna* | el modelo devolvió un `pitch` **vacío** que pasó las tres comprobaciones; no es un rechazo de la puerta sino una generación vacía |

Y una tercera cifra que **no** es una tasa de rechazo y conviene no confundir con ella:
`claim_not_in_pitch` apareció **30 veces en la primera generación y 23 sobrevivieron** (25,8 %
de las 89). Es una violación **blanda por política**: retira **esa cita** y publica la prosa,
porque el fragmento existía y estaba en el contexto y lo que falló es el relato del modelo sobre
haberlo usado. Es la tasa más alta del conjunto y merece una medición propia en C38 — aquí se
publica como lo que es, no como parte del 2,25 %.

**Reparto de rutas sobre las 90**, decidido por el enrutador y no por un fixture:
`catalog` **50**, `knowledge` **28**, `both` **11**, y **0 degradaciones** — el *fail-open* no
entró ni una vez en esta pasada.

---

## 6 · El contrato: sólo descripciones, verificado hoja a hoja

Aplanados los dos `openapi.json` a hojas y comparados uno a uno:

| | antes | después |
|---|---|---|
| hojas totales | 1.102 | 1.103 |
| **campos añadidos** | — | **0** |
| **campos retirados** | — | **0** |
| **tipos cambiados** | — | **0** |
| hojas de `type` | 346 | 346, **idénticas** |
| hojas de `required` | 125 | 125, **idénticas** |
| descripciones cambiadas | — | 2 (`intent`, `warnings`) |
| descripciones añadidas | — | 1 (`clarification_question`, que no tenía) |

La única hoja «añadida» es una clave `description` sobre un campo que ya existía. **Ningún campo
se añade, se retira ni cambia de tipo**, que es la verificación que D4 exige y la misma que C30b
ejecutó. Leerlo a ojo no habría bastado: el diff de git son **3 líneas**.

---

## 6.bis · Lo que la sincronización del archivado destapó

La evaluación previa al sync encontró una **contradicción que la delta habría escrito en la spec
viva**: el requisito vivo de los avisos declara *«SHALL emit exactly two codes»* y C31 lleva el
vocabulario a **cinco**, sin que la delta lo modificara. `openspec validate --all --strict` no lo
habría visto —comprueba estructura, no coherencia semántica— y los tests tampoco, porque afirman
sobre la constante y no sobre lo que la spec dice de ella.

Corregido **en la delta**, que es de donde se deriva la spec viva: un segundo `MODIFIED` que lleva
el requisito a cinco códigos y que además exige que **los dos de rechazo sigan siendo dos**. La
delta pasa de 19 a **20 requisitos** y de 26 a **31 escenarios**.

---

## 7 · Lo que NO se hizo, y por qué

- **No se reconstruyó nada de C30b.** La mitigación de inyección (`QUERY_OPEN`/`QUERY_CLOSE`), la
  validación de salida del argumentario y sus siete causas siguen exactamente como estaban.
  `prompts/assist/v1.md` **no se ha tocado**, y hay un test que lo fija sección a sección.
- **La costura del cliente se replicó, no se reutilizó.** `LiteLlmAssistClient` fija
  `response_format` a `AssistPitch`; reutilizarla habría significado un cliente al que se le
  puede pedir el objeto equivocado.
- **`abstained` no se reutiliza** para el rechazo del enrutador, con test en los dos sentidos.
- **Nada se persiste**: ni la decisión del enrutador ni la repregunta, ni en base ni en log. El
  log lleva etiqueta, ruta, motivo, latencia, coste y credencial en vigor — **nunca la consulta**,
  y hay un test que busca el texto de la consulta en lo emitido y exige no encontrarlo.
- **`retrieval/`, `enrichment/` y `knowledge/` no se modifican.** El guardarraíl de M3 se
  construye **sobre** el resultado de `search_knowledge`, no dentro de él.

---

## 8 · La declaración de D11, por escrito

**El prompt del clasificador se redactó desde `enrichment/vocabularies.yaml` y la documentación
del corpus, y no desde las anotaciones de los conjuntos de evaluación.** En concreto:

- **No se abrieron** los campos `note` de `evals/golden/queries.jsonl` ni los campos `why` de
  `evals/routing/cases.yaml` antes de escribir `prompts/router/v1.md`. Los dos llevan la regla de
  clasificación escrita con todas sus letras —*«lo que guarda las joyas, no una joya»*— y un
  prompt derivado de ellos se confirmaría por construcción.
- **El orden lo garantizó, no la voluntad:** `prompts/router/v1.md` y `prompts/assist/v2.md` se
  escribieron **antes** de la primera lectura de cualquiera de los dos ficheros. Es una puerta de
  un solo sentido y no hay forma de deshacerla, así que el orden de trabajo era el único
  mecanismo posible.
- **Las revisiones v2 y v3 se escribieron desde las mismas fuentes**, ampliadas con los **nombres
  de producto del propio catálogo** (`data/catalog/real/`), que son catálogo y no anotación de
  evaluación. Lo que se miró para decidir que hacían falta fue **qué clases fallaban y con qué
  etiqueta**, que es para lo que existe una medición.
- **La declaración viaja también en los tres ficheros de prompt**, no sólo aquí, y hay un test
  que comprueba que cada versión la lleva.

---

## 9 · Trazabilidad de los 19 escenarios de la HU

| # | Escenario | Dónde se ejerce |
|---|---|---|
| 1 | Fuera de dominio, sin recuperar | `test_an_out_of_domain_query_is_refused_before_anything_is_retrieved` |
| 2 | Fuera de catálogo, código distinto | `test_a_neighbouring_trade_request_is_refused_with_its_own_distinct_code` |
| 3 | Contestable no silenciada (veto) | `test_a_single_silenced_answerable_query_is_a_veto_violation` + la medición del §3 |
| 4 | Pregunta al corpus, sin piezas | `test_a_knowledge_question_is_routed_to_the_corpus_and_shows_no_pieces` |
| 5 | Ambigua ⇒ repregunta | `test_an_ambiguous_query_is_answered_with_a_question_and_no_candidates` |
| 6 | Repregunta determinista | `test_the_same_query_always_yields_the_same_clarification_text` |
| 7 | Pieza sin pregunta no paga clasificador | `test_a_piece_with_no_question_makes_no_classifier_call` |
| 8 | Pieza con pregunta, `both` estructural | `test_an_anchored_question_consults_both_indexes_and_makes_no_classifier_call` |
| 9 | Pregunta anclada sin cobertura | `test_an_uncovered_anchored_question_is_declared_and_costs_no_extra_call` |
| 10 | M1 redacta según la ruta | `test_a_catalogue_query_receives_an_argument_written_over_the_candidates` |
| 11 | Lista blanca desde lo recuperado | `test_the_free_query_material_carries_no_internal_identifier_and_no_score` |
| 12 | Clasificador caído ⇒ como antes | `test_a_classifier_fault_serves_the_answer_the_capability_served_before_it_routed` |
| 13 | Techo literal de 3 llamadas | `test_a_routed_generated_and_repaired_request_makes_exactly_three_calls` |
| 14 | El rechazo no se disfraza de abstención | `test_a_refused_request_does_not_claim_to_have_abstained` |
| 15 | Dos cifras separadas | `test_the_report_keeps_the_two_rates_apart_and_says_they_are_not_summable` |
| 16 | Prompt versionado no pisa al anterior | `test_the_previous_prompt_version_is_present_and_was_not_edited` |
| 17 | Credencial repliega y se sabe cuál | `test_the_classifier_credential_falls_back_through_the_three_links` |
| 18 | Consulta como dato, etiqueta validada | `test_an_instruction_shaped_query_does_not_change_the_classifier_system_message` |
| 19 | Fuera de alcance explícito | declarado en la spec y en el §7 de este informe |
