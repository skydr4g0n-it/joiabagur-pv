# HU-AIENG-031: El enrutador de intención y los guardarraíles — dos puertas, dos cifras, y el derecho del sistema a decir «no lo sé»

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** que `POST /v1/assist/sale` **clasifique la consulta antes de recuperar nada** y sepa distinguir *«esto no es una pregunta de joyería»* de *«esto es joyería y este catálogo no la tiene»* de *«esto no basta para buscar»*, rechazando con cortesía las dos primeras y repreguntando en la tercera,
**para** que el sistema tenga el **suelo de seguridad** que el rubro nombra —un camino explícito para reconocer que no sabe— y para que el argumentario del modo de consulta libre, que C30b difirió, se redacte por fin **sobre una intención clasificada y no sobre una suposición**.

---

## Descripción

C30b dejó `POST /v1/assist/sale` redactando prosa con tres comprobaciones deterministas encima. Lo
que **no** dejó es una decisión sobre la consulta: la capa de generación se calla cuando la regla de
abstención de C25 desconfía del perfil de candidatos, y eso —dicho por la propia spec viva— **es una
red, no un clasificador**. Esta historia pone el clasificador.

### El hallazgo que reencuadra el change: «fuera de dominio» significa dos cosas, y la ficha las mezcla

La ficha de C31 en el plan se justifica con esta frase:

> *Sin puerta, C30 contestaría **«¿qué tiempo hace mañana?»** con cinco familias y un argumentario
> convencido […] medido, **18 de 20** consultas fuera de dominio llegan hoy con candidatos.*

**Las dos mitades no hablan del mismo conjunto.** Las 20 consultas de la categoría `fuera-de-dominio`
del golden set son `un salero de plata`, `un lingote de oro`, `una correa de reloj marron`, `una
cuberteria de plata para doce`, `un joyero de viaje para los anillos`. Relojería, platería de mesa,
papelería y numismática: **los oficios vecinos**. Ninguna se parece a «¿qué tiempo hace mañana?», y
el propio [`criterion.md`](../../../ai-service/evals/golden/criterion.md) lo dice con todas las
letras — *«son plausibles **dentro de la joyería** y el catálogo no las puede satisfacer»*.

La consecuencia es dura y hay que escribirla antes de implementar: **un clasificador de intención que
se pregunte «¿es esto una pregunta de joyería?» contestará que sí a las veinte, y con razón**. C31
tal como está redactada en el plan entregaría un guardarraíl para un conjunto de **cinco casos** en
todo el repositorio, y **no movería ni una décima** de la cifra con la que se justifica.

```
┌────────────────────────────────────────────────────────────────────┐
│ A · DOMINIO   «esto no es una pregunta de joyería»                │
│   ¿Cuál es la capital de Australia? · ¿A qué hora abrís?          │
│   → clasificable SIN recuperar                                     │
│   → conjunto existente: data/knowledge/_eval/out-of-domain.yaml    │
│   → n = 5.  En el golden set de producto: n = 0                    │
├────────────────────────────────────────────────────────────────────┤
│ B · COBERTURA «esto es joyería y ESTE catálogo no lo tiene»        │
│   un salero de plata · un lingote de oro · una petaca de plata     │
│   → NO es intención, es cobertura del catálogo                     │
│   → categoría MAYOR del golden set: n = 20 de 72                   │
│   → es la que mide el 18 de 20 y el 0,10 de abstención             │
└────────────────────────────────────────────────────────────────────┘
```

**Esta historia cubre las dos**, y publica **dos cifras separadas que nunca se suman**: la abstención
del retriever de C25 —que no se mueve, porque lee la forma del perfil de distancias— y el rechazo
del enrutador, que es un mecanismo distinto. La diferencia entre ambas **es el hallazgo**: el
retriever no puede distinguirlas —está medido, el rango entero de las imposibles vive *dentro* del de
las contestables— y el enrutador sí. Ésa, contada con números, es su razón de existir.

### La distinción no es opaca: está escrita en los datos, y es contra un vocabulario cerrado

Lo que separa las 20 de las 48 contestables está redactado, caso por caso, en los `note` del propio
golden set — `un joyero de viaje para los anillos` → *«lo que guarda las joyas, **no una joya**»*;
`una pila para el reloj de pulsera` → *«aquí `pulsera` significa reloj de muñeca»*. Eso no es
clasificación de intención: es **una pregunta sobre el objeto pedido contra los doce tipos de pieza
cerrados** de [`vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml)
(`anillo, pendientes, collar, pulsera, colgante, tobillera, broche, cadena, diadema, gemelos,
cinturon, llavero`).

**Una regla léxica muere aquí, y a propósito:** `pulsera` y `anillos` aparecen literalmente en dos de
las veinte, puestas ahí para matarla. Y la trampa simétrica también existe: las **12** consultas de
`descripcion-sin-anclaje` no nombran ningún tipo de pieza —`joya con forma de concha marina`— y son
exactamente las que la rama vectorial existe para servir.

### Lo que C30b ya dejó hecho, y lo que sigue siendo de aquí

Verificado en el árbol, no en las fichas:

| Ítem de la ficha del plan | Estado real | Evidencia |
|---|---|---|
| Consulta tratada como dato | ✅ **Entregado por C30b** | `QUERY_OPEN`/`QUERY_CLOSE` en [`assist/prompt.py`](../../../ai-service/src/jbg_ai/assist/prompt.py); regla invariante en `prompts/assist/v1.md`; `test_prompt_injection_in_the_query_does_not_change_the_system_message` en verde |
| Validación de salida contra JSON schema | ✅ **Entregado por C30b** | `AssistPitch` como `response_format`, `model_validate_json`, `verify()` con siete causas |
| …con reintento único | ⚠️ **Conflicto resuelto a favor de C30b** | Un fallo de parseo es `PitchProviderError` y **degrada sin reintentar**, argumentado en [`assist/llm.py`](../../../ai-service/src/jbg_ai/assist/llm.py). Ver la decisión D-6 |
| Clasificador de intención | ❌ **Cero** | `assist/modes.py` es estructural **a propósito** |
| Rechazo cortés sin llamar al retriever | ❌ **Cero** | |
| `clarification_question` | ❌ Siempre `null` | El campo existe en el contrato desde C30a |
| Argumentario de M1 | ❌ Diferido aquí por C30b | `test_free_query_mode_calls_no_provider` |

**Dos tercios de la ficha ya están entregados.** El trabajo nuevo real es clasificar, rechazar,
repreguntar y redactar M1.

### La arquitectura que sale de las decisiones: el enrutador cuesta UNA llamada, y sólo en M1

```
                        AssistRequest
                             │
                    resolve_mode  (C30a, estructural, sin mirar palabras)
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
    M2                      M3                      M1
 pieza sola            pieza + pregunta        consulta sola
     │                       │                       │
 SIN enrutador          ruta = `both`           ENRUTADOR · 1 llamada
 (no hay consulta       POR CONSTRUCCIÓN        ┌────────────────────┐
  que clasificar)       la pieza es el catálogo │ eje 1 ¿atendemos?  │
     │                  la pregunta, el corpus  │ eje 2 ¿qué índice? │
     │                       │                  │ eje 3 ¿basta?      │
     │                  guardarraíl GRATIS:     └────────────────────┘
     │                  cero citas tras el              │
     │                  umbral 0,51 ⇒ el corpus    ┌────┼────┬────────┐
     │                  no cubre la pregunta       ▼    ▼    ▼        ▼
     │                       │                  fuera no en ambigua  in_domain
     │                       │                  domin. catál. │        │
     │                       │                    └─────┴─────┘        │
     │                       │                    rechazo cortés /     │
     │                       │                    repregunta           │
     │                       │                    SIN RECUPERAR        │
     └───────────────────────┴─────────────────────────────────────────┘
                             │
                  abstención de C25 (la RED, no la puerta)
                             │
                        generación
```

**Por qué M3 no necesita llamada, y es una medición y no una comodidad.** La pieza ya ancla el
dominio, así que el enrutador no podría rechazar nada sin rechazar una pieza legítima. Y la pregunta
ya pasa por un detector de fuera-de-dominio que **existe, corre en producción y está medido**: C23
fijó el umbral `jpv_knowledge_distance_threshold = 0,51` sobre un **hueco limpio de 8 milésimas**,
con las 32 preguntas que el corpus responde por debajo y las 5 de fuera por encima —**100 % y 0 %**—.
*Cero citas tras el umbral* es un guardarraíl determinista que **nadie está leyendo como tal**: hoy
M3 genera igual, sin citas, y el consumidor no puede distinguirlo.

Eso resuelve entero el problema del presupuesto de latencia. Medido:

| | ms |
|---|---|
| `AssistTimeoutMs` de .NET ([`appsettings.json`](../../../backend/src/JoiabagurPV.API/appsettings.json)) | **5.000** |
| recuperación híbrida completa | 129 |
| una llamada de generación, p50 / p95 (barrido C30b, 175 llamadas) | 2.216 / 2.863 |
| peticiones que gastan la reparación y hacen dos llamadas | **55 %** |
| una petición reparada, del orden de | **~4.400** |

El margen que le queda a C34 es de **centenares de milisegundos**, no de un segundo. Meter un tercer
viaje en serie delante de M3 lo revienta — y **M1 no tiene ruta .NET** (§15.12 del diseño), así que
el camino caro es justamente el que no tiene presupuesto.

### El conjunto de evaluación ya existía, repartido, y nadie lo había conectado

Cinco de las seis clases que un enrutador necesita están etiquetadas en el repositorio, escritas
antes de medir y por otros changes. El manifiesto que las reúne es
[`evals/routing/cases.yaml`](../../../ai-service/evals/routing/cases.yaml), creado el 2026-09-14:

| Clase | Conjunto | n | Origen |
|---|---|---|---|
| `catalog` | golden set, ocho categorías juzgadas | **48** | C24 / C26 |
| `not_in_catalogue` | golden `fuera-de-dominio` | **20** | C24 |
| `ambiguous` | golden `ambigua`, **declaradas sin juzgar** | **4** | C24 |
| `knowledge` | marca `eval_question`, una por documento | **32** | C23 |
| `out_of_domain` | `data/knowledge/_eval/out-of-domain.yaml` | **5** | C23 |
| `both` | **no existía** — se escribe en este change | **10** | C31 |

**109 casos existentes + 10 nuevos = 119**, con coste de etiquetado cero para cinco de las seis
clases. Y el detalle que cierra el círculo: las cuatro consultas `ambigua` —`algo bonito`, `un
regalo`, `lo de siempre`, `quiero una joya`— se declararon **sin juicios de relevancia** el
2026-09-11 con esta nota, escrita antes de que nadie asignara `clarification_question` a ningún
change:

> *«Declarada sin juicios: **la respuesta correcta es una repregunta**, y eso es una decisión del
> agente.»*

Su conjunto de evaluación llevaba tres días esperando, con la respuesta correcta escrita en el campo
`note`.

### El criterio de veto, y el riesgo de circularidad

**El falso positivo sobre la clase `catalog` es lo que decide si el enrutador se sirve o no.** La
asimetría está medida y argumentada en
[`retrieval/abstention.py`](../../../ai-service/src/jbg_ai/retrieval/abstention.py): silenciar una
consulta que la tienda **sí** puede contestar es un fallo visible en el mostrador; no rechazar una
imposible enseña cinco piezas que no encajan y el operario lo ve. **Una sola de las doce
`descripcion-sin-anclaje` silenciada veta la configuración**, aunque capture las veinte.

Y el riesgo de proceso, que hay que cerrar en las tareas y no después: los `note` del golden set
llevan **literalmente escrita la regla de clasificación**. Si el prompt del enrutador se redacta
leyendo esos campos —o los `why` del fixture nuevo—, la medición es circular y el change no arbitra
nada. **El prompt se escribe desde `vocabularies.yaml` y el README del corpus, y eso se declara.**

---

### Alcance de esta historia (sí)

- **Enrutador de intención en el modo de consulta libre (M1)**, con tres ejes: si se atiende
  (`in_domain` / `out_of_domain` / `not_in_catalogue`), con qué índice (`catalog` / `knowledge` /
  `both`) y si la consulta basta (`sufficient` / `ambiguous`). **Una sola llamada al proveedor, sin
  reparación.**
- **Rechazo cortés como *safe-completion*, no como respuesta en blanco**: código de vocabulario
  cerrado en el cable, castellano en el frontend — el precedente doble de `warnings[]` y de los
  `match_reasons` del panel.
- **`clarification_question` deja de ser nula**, resuelta desde un **catálogo cerrado de plantillas
  en Python** seleccionado por el código del eje que falta (tipo de pieza, material, ocasión o
  precio).
- **Guardarraíl determinista de M3**: cero citas tras el umbral de conocimiento ⇒ código de aviso y
  tarea degradada, **sin llamada extra al proveedor**.
- **Argumentario del modo de consulta libre (M1)**, con la forma de *payload* que hoy no existe y su
  política de lista blanca numérica.
- **`prompts/assist/v2.md`** con secciones de tarea nuevas por ruta, conservando `v1.md` y sus
  mediciones — lo que entrega de paso la progresión v1→v2 que pide C39.
- **Tres variables de configuración nuevas** (`JPV_ROUTER_LLM_MODEL`, `JPV_ROUTER_LLM_API_KEY`,
  `JPV_ROUTER_TIMEOUT_SECONDS`) con su entrada en `openspec/DEFERRED_TASKS.md`, siguiendo el patrón
  que C30b ya ejecutó.
- ***Fail-open* declarado**: si el clasificador no está disponible o su salida no parsea, `intent`
  vuelve a `unclassified` y el sistema se comporta **exactamente como hoy**, con la degradación
  registrada en el log.
- **Matriz de confusión publicada** sobre los 119 casos, con las **dos cifras separadas** y los dos
  huecos declarados.
- **Deltas sobre la capability viva `assist-generation`**, que es donde C30a y C30b ya escriben.

### Fuera de alcance (no)

- **La pantalla del rechazo y de la repregunta.** M1 no tiene ruta .NET ni superficie en el frontend;
  la ruta queda **anotada en la ficha de C34** y el bloque de pantalla es de **C36**. El *«no lo sé»*
  se demuestra con escenarios, y eso se declara.
- **Los casos adversarios y de inyección**, que son **C38** (20-25 casos). Lo que aquí entra es la
  clasificación y el rechazo; la mitigación estructural de la inyección ya la entregó C30b y **no se
  rehace**.
- **`faithfulness` / RAGAS**: sigue siendo C38, y la alucinación con coartada sigue declarada como
  limitación de la capability.
- **El bucle agéntico, las tools y el presupuesto duro**: son **C32**, y la tool `pedir_aclaracion`
  de aquel change **no es** esta `clarification_question`.
- **Reintento ante fallo de parseo del argumentario**: se mantiene la decisión medida de C30b.
- **Mover la forma del contrato.** `intent` es `str` plano y `clarification_question` ya existe: el
  movimiento es **de descripción**, como el único que hizo C30b.
- **Mover la tabla de ablations v0→v3**: el enrutador vive en `assist/` y no en `retrieval/`, así que
  la abstención publicada de C25 **no se toca**.
- **`backend/`, `frontend/`, `terraform/` y cualquier migración de EF Core.**

### Decisiones de diseño ya acordadas

| # | Decisión | Razón |
|---|---|---|
| **D-1** | El enrutador cubre **los dos** conjuntos —dominio y cobertura de catálogo— y se publican **dos cifras separadas**, nunca sumadas | La ficha las confunde. Sólo A son 5 casos y no mueve la cifra que la justifica; sólo B pierde la distinción entre *«no es nuestro oficio»* y *«es nuestro oficio y no lo tenemos»*, que son dos rechazos distintos ante un cliente |
| **D-2** | La llamada al clasificador es **sólo de M1**. M2 no tiene consulta; M3 es `both` por construcción | Presupuesto de 5 s de C34 con la generación ya en ~4,4 s al p50 en el 55 % de las peticiones. Y en M3 el enrutador no podría rechazar sin rechazar una pieza legítima |
| **D-3** | El guardarraíl de M3 es **el umbral 0,51 de C23**, ya medido: cero citas ⇒ el corpus no cubre la pregunta | Determinista, coste cero, mecanismo existente. Da además una **segunda opinión independiente** sobre el margen de 8 milésimas que el propio informe de C23 declaró estrecho *«y por construcción»* |
| **D-4** | El veredicto viaja en **`intent`**; el motivo, como código en `warnings[]`; la repregunta, en `clarification_question` | Cero movimiento de forma en `openapi.json`. `product_pitch` sobrevive intacto, tal como `modes.py` prometió: *«ese router reemplazará a `unclassified`, nunca a `product_pitch`»* |
| **D-5** | **`abstained` NO se reutiliza** para el rechazo del enrutador | Borraría la distinción que las dos cifras publicadas existen para sostener, y haría el 0,10 de C25 indistinguible de la cifra nueva |
| **D-6** | Se **mantiene** la decisión de C30b de no reintentar ante fallo de parseo; se enmienda el nombre del test de la ficha | El techo literal de dos llamadas es lo que hace testeable la garantía. Un tercer viaje agrava el presupuesto que C34 heredará |
| **D-7** | La repregunta se resuelve desde un **catálogo cerrado de plantillas en Python**, no la escribe el modelo | `clarification_question` está tipada como prosa, así que el frontend no puede resolverla; y una frase generada —*«¿algo por menos de 50 €?»*— no pasaría por ninguna puerta numérica. Además hace las 4 consultas `ambigua` **juzgables deterministamente** |
| **D-8** | ***Fail-open***: clasificador caído ⇒ `intent = unclassified` y comportamiento de hoy | Fallar cerrado convertiría un parpadeo del proveedor en un rechazo cortés universal. `unclassified` deja de significar «todavía no clasificamos» y pasa a significar «esta vez no pudimos»: mismo valor, honesto en las dos eras |
| **D-9** | Techo **literal de 3 llamadas** al proveedor por petición: 1 de enrutador + 2 de argumentario | Propiedad comprobable por introspección, como la de dos llamadas que entregó C30b |
| **D-10** | `JPV_ROUTER_LLM_MODEL` **no hereda** de `JPV_ASSIST_LLM_MODEL` ni de `JPV_RAG_LLM_MODEL`; la credencial **sí repliega** en cadena | Mismo argumento medido de C30b: son dos llamadas de forma muy distinta —~30 *tokens* de salida contra un párrafo— y compartir variable haría falsa cualquier comparación de coste. La credencial es de la misma superficie de mostrador y replegar evita un despliegue roto |
| **D-11** | El prompt del clasificador se redacta desde `vocabularies.yaml` y el README del corpus, **nunca** desde los `note` del golden set ni los `why` del fixture | Es el riesgo estructural que `criterion.md` declaró del suyo, aquí en forma más aguda: los `note` llevan la regla escrita |
| **D-12** | El **falso positivo sobre `catalog`** es el criterio de veto, y una sola `descripcion-sin-anclaje` silenciada tumba la configuración | La asimetría de `abstention.py`, aplicada al mecanismo nuevo |

### Referencias

- Change de OpenSpec: `openspec/changes/add-guardrails-and-intent-router/` (C31)
- Ficha del plan: [§3 · C31](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md)
- Diseño RAG: [§11.2, §15.12 y §15.13](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md)
- Capability viva: [`assist-generation`](../../../openspec/specs/assist-generation/spec.md)
- Capabilities consumidas: [`retrieval-abstention`](../../../openspec/specs/retrieval-abstention/spec.md), [`knowledge-corpus`](../../../openspec/specs/knowledge-corpus/spec.md), [`vector-retrieval`](../../../openspec/specs/vector-retrieval/spec.md)
- Conjunto de enrutado: [`ai-service/evals/routing/cases.yaml`](../../../ai-service/evals/routing/cases.yaml)
- Golden set y su criterio: [`queries.jsonl`](../../../ai-service/evals/golden/queries.jsonl), [`criterion.md`](../../../ai-service/evals/golden/criterion.md)
- Historia anterior: [HU-AIENG-030b](HU-AIENG-030b.md) · [HU-AIENG-030a](HU-AIENG-030a.md)
- Épica: [EP15 — Venta Asistida, Sustitutos y Agentes](../../epicas.md)

---

## Criterios de Aceptación

### Escenario 1: Una consulta que no es de joyería se rechaza sin recuperar nada

- **Dado que** el operario escribe una consulta ajena al negocio, como una pregunta de enciclopedia,
- **Cuando** se solicita la asistencia de venta **sin `product_id`**,
- **Entonces** la respuesta llega con **200** y `groups[]` vacío,
- **Y** `intent` declara que la consulta queda fuera del dominio,
- **Y** `warnings[]` trae el código de rechazo del vocabulario cerrado,
- **Y** **no se ha ejecutado ninguna recuperación de catálogo ni ninguna búsqueda de conocimiento**,
- **Y** `abstained` vale **false**, porque no hubo recuperación de la que abstenerse.

### Escenario 2: Una consulta de joyería que el catálogo no cubre se rechaza, y no como abstención

- **Dado que** el operario pide un objeto propio de una joyería que este catálogo no vende —platería
  de mesa, relojería, papelería—,
- **Cuando** se solicita la asistencia sin pieza anclada,
- **Entonces** `groups[]` llega vacío y `intent` declara que el catálogo no cubre la petición,
- **Y** el código de motivo **distingue** este caso del de fuera de dominio,
- **Y** `abstained` sigue valiendo **false**: el rechazo es del enrutador y no de la regla de C25.

### Escenario 3: Una consulta contestable no se silencia — el criterio de veto

- **Dado que** la consulta pertenece a cualquiera de las ocho categorías contestables del golden set,
  incluidas las **doce** descriptivas sin anclaje léxico,
- **Cuando** se solicita la asistencia,
- **Entonces** el enrutador la admite,
- **Y** la recuperación se ejecuta y devuelve grupos,
- **Y** **ninguna** de las doce descriptivas sin anclaje es rechazada.

### Escenario 4: Una pregunta de conocimiento se enruta al corpus y no enseña piezas

- **Dado que** el operario pregunta algo que responde el corpus y no el catálogo, como el cuidado de
  un material,
- **Cuando** se solicita la asistencia sin pieza,
- **Entonces** `citations[]` trae fragmentos del corpus con su `claim_scope`,
- **Y** **no se recuperan candidatos de catálogo**, porque enseñar cinco piezas al lado de una
  respuesta sobre limpieza es ruido y no ayuda.

### Escenario 5: Una consulta ambigua recibe repregunta y no candidatos

- **Dado que** la consulta es una de las cuatro declaradas sin juicios por ser irremediablemente
  ambiguas,
- **Cuando** se solicita la asistencia,
- **Entonces** `clarification_question` llega **no nula** y en castellano,
- **Y** `groups[]` llega vacío,
- **Y** no se ha llamado al proveedor para redactar ningún argumentario.

### Escenario 6: La repregunta es determinista y nombra el eje que falta

- **Dado que** el clasificador determina que la consulta no basta para buscar,
- **Cuando** se compone la respuesta,
- **Entonces** el texto de `clarification_question` procede de un **catálogo cerrado de plantillas**
  y no de la salida del modelo,
- **Y** la plantilla elegida se corresponde con el eje ausente —tipo de pieza, material, ocasión o
  precio—,
- **Y** dos ejecuciones de la misma consulta producen **exactamente** el mismo texto.

### Escenario 7: Una pieza sin pregunta no paga clasificador

- **Dado que** la petición ancla un `product_id` y no trae consulta,
- **Cuando** se sirve la asistencia,
- **Entonces** `intent` sigue valiendo el valor anclado a pieza que C30a fijó,
- **Y** **no se realiza ninguna llamada al clasificador**,
- **Y** el argumentario se genera como lo hacía antes de este change.

### Escenario 8: Una pieza con pregunta se enruta por construcción y tampoco paga clasificador

- **Dado que** la petición ancla una pieza **y** trae una pregunta,
- **Cuando** se sirve la asistencia,
- **Entonces** se consultan los dos índices, porque la pieza es el lado de catálogo y la pregunta el
  de conocimiento,
- **Y** **no se realiza ninguna llamada al clasificador**,
- **Y** el total de llamadas al proveedor para esa petición no supera las dos del argumentario.

### Escenario 9: Una pregunta anclada que el corpus no cubre se detecta sin coste

- **Dado que** la petición ancla una pieza y la pregunta queda por encima del umbral de distancia del
  corpus,
- **Cuando** se sirve la asistencia,
- **Entonces** `citations[]` llega vacía,
- **Y** `warnings[]` trae el código que declara que el corpus no cubre la pregunta,
- **Y** el argumentario se redacta **sobre la pieza** sin fingir que ha contestado,
- **Y** **no se ha hecho ninguna llamada adicional al proveedor** para averiguarlo.

### Escenario 10: El modo de consulta libre redacta, y redacta según la ruta

- **Dado que** el enrutador admite una consulta libre y decide su ruta,
- **Cuando** se sirve la asistencia,
- **Entonces** `pitch` trae prosa no vacía,
- **Y** `prompt_version` declara la versión nueva del prompt,
- **Y** la sección de tarea empleada se corresponde con la ruta decidida.

### Escenario 11: La lista blanca numérica de la consulta libre se construye desde lo recuperado

- **Dado que** una consulta libre produce varios grupos de candidatos,
- **Cuando** se compone el material que se entrega al modelo,
- **Entonces** las cifras admisibles son **exactamente** las presentes en ese material,
- **Y** un importe o una cantidad de existencias en el argumentario se rechaza igual que en los modos
  anclados,
- **Y** los identificadores internos de producto **no** entran en la lista blanca.

### Escenario 12: Si el clasificador no está disponible, el sistema se comporta como antes

- **Dado que** no hay credencial para el clasificador, o el proveedor falla, o excede su tiempo, o su
  salida no parsea,
- **Cuando** se sirve una consulta libre,
- **Entonces** la respuesta llega con **200** y sin error de servidor,
- **Y** `intent` vale el valor sin clasificar,
- **Y** la recuperación se ejecuta con normalidad y la regla de abstención de C25 sigue actuando como
  red,
- **Y** el log registra la degradación con su causa.

### Escenario 13: El techo de llamadas al proveedor es literal y comprobable

- **Dado que** una petición de consulta libre clasifica, genera y necesita una reparación,
- **Cuando** termina de servirse,
- **Entonces** el número total de llamadas al proveedor es **tres** y nunca más,
- **Y** el uso de tokens reportado **acumula** las tres.

### Escenario 14: El rechazo del enrutador no se disfraza de abstención

- **Dado que** el enrutador rechaza una consulta,
- **Cuando** se compone la respuesta,
- **Entonces** `abstained` vale **false**,
- **Y** el motivo del rechazo viaja en su propio campo y con su propio código,
- **Y** una consulta que sí llega al retriever y dispara la regla de C25 sigue declarando
  `abstained: true` como hasta ahora.

### Escenario 15: Las dos cifras se miden y se publican por separado

- **Dado que** se ejecuta la evaluación sobre el conjunto de enrutado,
- **Cuando** se publica el informe,
- **Entonces** la tasa de abstención del retriever y la tasa de rechazo del enrutador aparecen en
  **filas distintas**,
- **Y** el informe declara que **no son sumables**,
- **Y** se publica el falso positivo sobre la clase contestable como cifra propia.

### Escenario 16: El prompt versionado no pisa al anterior

- **Dado que** el prompt gana secciones de tarea para la consulta libre,
- **Cuando** se carga el fichero,
- **Entonces** la constante de versión y la ruta del fichero **no pueden divergir**, como ya
  garantiza el test de C30b,
- **Y** el fichero de la versión anterior **sigue existiendo**, para que las mediciones tomadas
  contra él sigan siendo interpretables.

### Escenario 17: La credencial repliega y se puede saber cuál está en vigor

- **Dado que** el despliegue no define la credencial propia del clasificador,
- **Cuando** arranca el servicio,
- **Entonces** repliega a la del argumentario y, si tampoco está, a la del enriquecimiento,
- **Y** el log declara **cuál** de las tres está en vigor, sin escribir ninguna clave,
- **Y** si no hay ninguna, el clasificador no se construye y aplica el escenario 12.

### Escenario 18: La consulta del operario sigue siendo dato y nunca instrucción

- **Dado que** la consulta contiene texto que ordena ignorar las reglas,
- **Cuando** se construye cualquiera de las llamadas al proveedor, la del clasificador incluida,
- **Entonces** la consulta viaja en el mensaje de usuario dentro de su bloque delimitado,
- **Y** el mensaje de sistema es idéntico al de cualquier otra consulta,
- **Y** la etiqueta que devuelva el clasificador se valida contra el **conjunto cerrado** de valores
  antes de usarse.

### Escenario 19: Fuera de alcance explícito

- **Dado que** esta historia entrega el enrutador y sus guardarraíles,
- **Cuando** se revisa lo entregado,
- **Entonces** **no** hay ruta .NET ni pantalla para la consulta libre —quedan anotadas en C34 y
  C36—,
- **Y** **no** hay casos adversarios ni de inyección sistemáticos, que son de C38,
- **Y** **no** se mide `faithfulness`,
- **Y** **no** se mueve la forma del contrato ni la tabla de ablations publicada,
- **Y** la limitación se declara por escrito en la capability en lugar de quedar implícita.

---

## Notas adicionales

**Actor.** Desarrollador del proyecto. El beneficiario final es el operario de mostrador, que deja de
recibir cinco piezas y un argumentario convencido ante una petición que la tienda no puede atender.

**Change de OpenSpec.** `add-guardrails-and-intent-router` (C31), sobre la rama
`c31-add-guardrails-and-intent-router`. Schema `spec-driven`.

**Conflicto de zona.** `ai-service/src/jbg_ai/assist/` es la misma zona que C30a, C30b y C32, y los
cuatro son **estrictamente secuenciales por dependencia**. No se abren dos a la vez.

**Encaje con el apunte de S16.** *«Un sistema debe saber decir no lo sé»* fija dos guardarraíles
—entrada y salida— y tres caminos ante la incertidumbre: responder, **abstenerse con honestidad** y
escalar a un humano. Esta historia entrega el guardarraíl de entrada y el segundo camino; el de
salida lo entregó C30b con sus tres comprobaciones. El tercero —escalado— no aplica aquí: el operario
**es** la persona, y el sistema ya escribe para que él decida.

**Limitaciones conocidas que se declaran y no se cierran.**

1. **La clase `both` no tiene conjunto independiente.** Sus diez casos son **construidos** y
   derivados de las `eval_question` del corpus: miden si el enrutador reconoce una consulta
   compuesta, no con qué frecuencia un operario real escribe una.
2. **Las veinte consultas de cobertura fueron elegidas para ser insatisfacibles**, así que la
   precisión medida sobre ellas es una **cota superior** de lo que verá un mostrador real.
3. **El rechazo cortés no se ve en pantalla**, porque la consulta libre no tiene superficie. Se
   demuestra con escenarios — §15.12 del diseño, y la ruta queda anotada en la ficha de C34.
4. **El margen de 8 milésimas del umbral de conocimiento sigue siendo estrecho**, como su propio
   informe advirtió. El enrutador da una segunda opinión, no lo sustituye.
5. **La alucinación con coartada** sigue fuera de alcance y declarada: es C38.

---

## Tareas

1. **Puerta de entrada**: línea base de la suite de `ai-service` por **nombres de test** y no por
   recuento (`git stash push -u`, correr, `git stash pop`), y `openspec validate --all --strict` en
   verde antes de tocar nada.
2. **Prompt del clasificador redactado desde el vocabulario**, no desde los conjuntos de evaluación:
   los doce tipos de pieza y los nueve materiales de `vocabularies.yaml` más el README del corpus.
   **Se declara por escrito en el informe** que no se leyeron los `note` ni los `why` al redactarlo.
3. **Esquema de salida del clasificador**, interno y no publicado, con etiqueta de conjunto cerrado,
   código de motivo y eje ausente. Validación en código contra el conjunto cerrado, nunca confiando
   en la cadena que devuelva el modelo.
4. **Cliente del clasificador** en `assist/`, replicando la costura ya establecida: temperatura 0,
   `num_retries: 0`, `response_format` fijado, `complete` inyectable por constructor, *timeout*
   propio y **sin reparación**.
5. **Constantes y ajustes**: `DEFAULT_ROUTER_MODEL`, `ROUTER_TIMEOUT_SECONDS` y
   `MAX_ROUTER_PROVIDER_CALLS` en `assist/constants.py`, con las tres variables de entorno y la
   cadena de repliegue de credencial con su línea de log.
6. **Cableado en el orquestador**: el enrutador corre **sólo** en M1 y decide antes de recuperar;
   M2 no lo invoca; M3 se marca `both` por construcción. El *fail-open* es una rama con test, no un
   `except` mudo.
7. **Guardarraíl determinista de M3**: cero citas tras el umbral ⇒ código de aviso nuevo y tarea
   degradada en el prompt.
8. **Catálogo cerrado de plantillas de repregunta** en Python, con su test de determinismo y su
   correspondencia eje↔plantilla.
9. **`prompts/assist/v2.md`** con las secciones de tarea de la consulta libre por ruta, conservando
   `v1.md`; test fichero↔constante como el que ya existe.
10. **Forma de *payload* para la consulta libre**, con su política de lista blanca numérica sobre los
    candidatos y la exclusión explícita de los identificadores internos.
11. **Los diez casos `both`** y el manifiesto de enrutado ya escritos en
    `evals/routing/cases.yaml`: cablear su carga, comprobar que las cinco referencias resuelven y
    que los recuentos declarados cuadran con los reales — que la carga **falle** si no cuadran, como
    hace el golden set.
12. **Runner de la matriz de confusión** con las **dos cifras separadas**, el falso positivo sobre
    `catalog` como cifra propia y los resultados atados a `run_id`, `git_sha` y versión del prompt.
13. **Deltas de la capability `assist-generation`**: el requisito de C30a *«el intent se deriva de la
    forma de la petición»* se **modifica**, y el de C30b *«no se llama al proveedor en el modo de
    consulta libre»* se **retira**, porque este change lo invierte — con
    `openspec validate --all --strict` en verde.
14. **Entrada en `openspec/DEFERRED_TASKS.md`** con los cuatro pasos de despliegue, siguiendo el
    patrón de C30b, y dejando el *timeout* fuera hasta tener medición del propio despliegue.
15. **Informe de implementación** con las cifras y con lo que la implementación refute de esta
    historia.
16. **Documentación**: `Documentos/epicas.md`, plan de changes, `ai-service/README.md`,
    `openspec/config.yaml` y las fichas de C32, C34, C36 y C38 si el trabajo mueve algo de lo que ya
    llevan anotado.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **5/5** — el §6 del plan la marca como **«nunca se recorta»**, con motivo propio: *«sin guardrails el agente de C32 no es defendible como sistema en producción»*. Y es la única pieza que entrega el **suelo de seguridad** que el rubro pide antes que la calidad |
| Urgencia | **4/5** — desbloquea **C32** y con él **C38** y **C39**. Va **antes que C34** por decisión explícita: `/v1/assist/sale` sigue teniendo cero consumidores, que es la ventana en la que cualquier movimiento de contrato es gratis |
| Complejidad / esfuerzo | **4/5** — sin migración, sin `backend/`, sin `frontend/`, sin mover la forma del contrato y con el conjunto de evaluación ya escrito. Lo caro son dos cosas: **calibrar el clasificador para que no silencie ninguna contestable**, y la **forma de *payload* de la consulta libre**, que no existe y que ensancha la lista blanca numérica con cada candidato |
| Riesgos | **El principal es el falso positivo sobre la clase contestable**: una sola de las doce descriptivas sin anclaje silenciada veta la configuración, y son justamente las que no nombran ningún tipo de pieza (mitigado por el escenario 3, por el criterio de veto declarado antes de medir y por el *fail-open*, que hace que el peor caso sea el comportamiento de hoy). **La circularidad de la medición**, porque los `note` del golden set llevan la regla de clasificación escrita (mitigado por la tarea 2, que es una declaración y no una convención). **El ensanchamiento de la lista blanca numérica en la consulta libre**, donde cinco candidatos aportan cinco SKU y cinco tallas contra la puerta que midió 0 violaciones en 120 generaciones (mitigado por el escenario 11). **El presupuesto de 5 s de C34**, que este change no empeora por D-2 pero que hereda sin resolver. Y que **el argumentario de M1 se lleve la sesión**, en cuyo caso es la línea de corte declarada: el enrutador y el rechazo son irrenunciables por ficha, M1 no |
| Dependencias | **C30b**, archivado el 2026-09-14. Consume **C23** (corpus, umbral y su fixture de fuera de dominio), **C24** (golden set y sus cuatro consultas ambiguas), **C25** (abstención, que sigue siendo la red) y **C09/C30b** (la costura del cliente, que se replica y no se reutiliza). **Bloquea a C32**, y con él a C38 y C39 |
