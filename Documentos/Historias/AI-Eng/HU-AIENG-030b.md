# HU-AIENG-030b: El argumentario en prosa — generación con integridad referencial, tramo de apoyo verificable y puerta numérica en ejecución

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** que `POST /v1/assist/sale` redacte el argumentario de una pieza y responda a las preguntas sobre ella **citando el corpus y declarando qué tramo de su propio texto sostiene cada cita**, con una puerta determinista que impide que ninguna cifra de precio o de stock llegue al mostrador,
**para** que el proyecto tenga por fin la capa de generación que el rubro nombra, **medible como ablación contra la capa estructurada de C30a**, y para que la garantía anti-alucinación deje de existir sólo en evaluación y exista **en ejecución**.

---

## Descripción

C30a dejó `POST /v1/assist/sale` sirviendo estructura real: tres modos, agrupación por familia con
`family_id` nulable, avisos por vocabulario cerrado, citas resolubles con su `claim_scope` y puerta
de abstención. Y dejó el hueco marcado con un requisito, no con una omisión: la spec viva
[`assist-generation`](../../../openspec/specs/assist-generation/spec.md) dice literalmente *«This
capability generates no prose and calls no provider»*, con su escenario *«no language model provider
call is made»*. Esta historia **invierte ese requisito**.

El andamio está construido y esta historia **no debe reconstruirlo**:

| Pieza | Estado verificado | Qué aporta |
|---|---|---|
| [`assist/orchestrator.py`](../../../ai-service/src/jbg_ai/assist/orchestrator.py) | Los tres modos servidos; `pitch=""`, `prompt_version=None`, `usage=Usage()` | El hueco es **exactamente uno** |
| [`assist/grounding.py`](../../../ai-service/src/jbg_ai/assist/grounding.py) | `ground_piece()` direcciona por clave primaria y filtra a `claim_scope: general` | El contexto de M2 llega **ya destilado**, sin vectores y sin modelo |
| [`knowledge/search.py`](../../../ai-service/src/jbg_ai/knowledge/search.py) | `search_knowledge()` con filtro de slug asimétrico | El contexto de M3, con las fichas de materiales no declarados fuera |
| [`enrichment/llm.py`](../../../ai-service/src/jbg_ai/enrichment/llm.py) | `LiteLlmEnrichClient`: temperatura 0, `num_retries: 0`, *backoff* propio, `complete` inyectable | **La costura**, que se replica — no la clase, que no sirve (ver refutación 2) |
| `prompts/assist/` | **No existe** | La zona del prompt versionado |
| `assist/constants.py` | `DEFAULT_PITCH_SECTIONS`, `DEFAULT_MATERIAL_CAP`, todo **por parámetro** | El barrido corre en un proceso, sin reiniciar |
| `IAiGatewayClient` (.NET) | Cinco métodos, **ninguno de assist** | `/v1/assist/sale` sigue con **cero consumidores** |

### La ablación que el corte dejó servida

Misma ruta, mismos candidatos, mismas citas, con prosa y sin ella. Es la única fila de la tabla del
§11.2 que aísla lo que aporta el LLM frente a lo que ya aportaba la recuperación, y sale gratis del
propio desdoble. Esta historia es la mitad que la hace medible — y también la mitad de la que el §6
del plan dice que *«si C30b se cayera, C30a seguiría entregando recuperación, citas resolubles y
abstención»*: eso es una propiedad del corte, no un permiso para usarlo.

### Dos supuestos de la ficha del plan que la exploración refuta

Comprobados contra el repositorio antes de escribir código. Las nueve decisiones, con sus
alternativas descartadas y las cuatro mediciones estáticas, están en
[`c30b-exploration-decisions.md`](../../Proyecto%20Final%20AIEng/informes/c30b-exploration-decisions.md).

**1 · La lista blanca numérica se abre sola, y la abre el propio corpus.**

La ficha dice que la puerta admite *«`925`, tallas, mm y dígitos de SKU por pertenencia al contexto
y no por regex de excepción»*. Cierto, y por eso mismo insuficiente:

```
data/knowledge/material-plata.md  → «una aleación de 925 milésimas», «`925` punzonado»
data/knowledge/material-oro.md    → «18 quilates son 750 milésimas, 14 quilates son 585»

lista blanca con la ficha del oro en contexto ⊇ {18, 750, 585, 14}
                                                    ↓
           un pitch que escriba «750 €» en una pieza de oro  →  PASA
```

Es exactamente el agujero que la puerta existía para cerrar, disfrazado de cifra legítima. De ahí la
regla añadida: **adyacencia a un símbolo o palabra de moneda, o a una expresión de existencias,
rechaza siempre**, esté o no el número en la lista blanca. Es la única lista negra del diseño y es
correcta aquí porque el conjunto de marcadores de moneda es **cerrado y no ambiguo**, a diferencia
de «números en joyería», que es lo que hizo descartar las listas negras en D-H.

**2 · La costura de C09 no devuelve `usage`, así que no se puede reutilizar.**

`LiteLlmEnrichClient.extract()` devuelve el modelo parseado y **descarta `response.usage`**;
[`pipeline.py:311`](../../../ai-service/src/jbg_ai/enrichment/pipeline.py) construye
`Usage(model=llm.model_id)` con **cero tokens**. C09 nunca los necesitó. C30b los necesita en tres
sitios a la vez —el campo `usage` del contrato, la línea de log que D-I exige, y la columna de coste
del §11.2—, así que se **replica la costura** y no la clase.

### El hallazgo que decide la forma de la salida

`{pitch, citation_ids[]}` **no hace lo que D-D dice que hace**. La integridad referencial verifica
pertenencia del identificador al conjunto entregado, y nada más: un modelo que devuelva los cinco
`citation_id` que se le dieron pasa esa comprobación de forma **perfecta y trivial**, sin haber
usado ninguno. La frase que D-D escribió contra la decoración —*«citar todo lo recuperado no es
atribuir, es decorar»*— no la prohíbe: la deja en palabra del modelo.

```
┌─ lo que el citation_id ya cumple ─┐   ┌─ lo que D-D afirma y nadie verifica ─┐
│ resuelve  → ∈ el conjunto dado    │   │ «son las que el pitch USÓ»           │
│ localiza  → documento#sección     │   │   con {pitch, ids[]}: palabra        │
│ trazable  → el fichero, en git    │   │   del modelo, y nada más             │
└───────────────────────────────────┘   └──────────────────────────────────────┘
```

Por eso el modelo declara, por cada cita, **el tramo de su propio argumentario** que esa cita
sostiene, y el código comprueba que ese tramo es subcadena literal del texto que escribió. Declarar
cinco citas obliga a señalar cinco tramos reales; un tramo inventado no es subcadena de nada. Es
determinista, no es un juez, no es una llamada más, y **no viaja al cable**: la respuesta HTTP
conserva `pitch: str` y `citations[]` con sus diez campos.

### Las tres comprobaciones, y la que ninguna hace

| Comprobación | Qué garantiza | Política si falla |
|---|---|---|
| **Resolución** — `citation_id` ∈ conjunto entregado | La fuente existe y estuvo en el contexto | **Dura**: reparación única y, si reincide, **sin argumentario** |
| **Correspondencia** — el tramo es subcadena del `pitch` | La cita se usó **para algo efectivamente escrito** | **Proporcionada**: misma reparación y, si sobrevive, **se retira esa cita** y la prosa se publica |
| **Lista blanca + adyacencia a moneda** | Ninguna cifra de precio o stock llega al operario | **Dura**: reparación única y, si reincide, **sin argumentario** |
| ~~Fidelidad semántica~~ | *Que el fragmento diga lo que la frase afirma* | **No se comprueba aquí.** Es la *alucinación con coartada*: se mide con RAGAS en C38 y se declara como limitación |

---

### Alcance de esta historia (sí)

1. **`prompts/assist/v1.md`** con `PROMPT_VERSION = "assist/v1"` y su test fichero↔constante, con
   reglas invariantes en el mensaje de sistema y bloque de tarea por modo.
2. **Argumentario en M2 y M3**: la pieza sin pregunta y la pieza con pregunta.
3. **Cliente generativo propio**, replicando la costura de `LiteLlmEnrichClient`, **devolviendo
   `usage`** con acumulación sobre la reparación, y con *timeout* explícito.
4. **Salida estructurada** en la que el modelo declara, por cita usada, el **tramo del argumentario**
   que la cita sostiene. No viaja al cable.
5. **Las tres comprobaciones** de la tabla de arriba, con sus dos políticas —dura y proporcionada— y
   **una sola reparación** por petición, con las violaciones acumuladas.
6. **Puerta numérica por lista blanca** leyendo el **objeto de payload** —nunca el prompt
   renderizado— **más la regla de adyacencia a moneda o a stock**.
7. **`prompt_version` relleno siempre que la capa de generación corre**, produzca o no argumentario
   publicable, y **regeneración del `openapi.json`** por el cambio de su descripción.
8. **No persistencia del argumentario, log incluido**, con los dos tests fuertes: listener
   `before_cursor_execute` contando DML, y ausencia del texto en el log.
9. **Degradación en vez de fallo**: proveedor caído o *timeout* devuelven la respuesta de C30a, y la
   abstención **corta antes** de llamar.
10. **La consulta del operario como dato delimitado** en el mensaje de usuario, nunca concatenada al
    mensaje de sistema.
11. **Barrido de 1/2/3 secciones** con su muestra de piezas declarada, publicando la tasa de rechazo
    **clasificada por causa** y el coste — y dejando montada, de paso, la **excepción de persistencia
    del arnés** que C38 necesita.
12. **Deltas** sobre la capability `assist-generation`: tres `MODIFIED` y los `ADDED` de las puertas,
    la no persistencia, el prompt versionado y la degradación.

### Fuera de alcance (no)

1. **El argumentario del modo de consulta libre (M1).** Sigue vacío y declarado. Su intención la
   reescribe C31, y hoy C30a midió que **18 de 20** consultas fuera de dominio llegan con
   candidatos: redactar sobre eso antes del clasificador es trabajo que C31 revisa.
2. **Clasificar la intención y rechazar cortésmente.** Es C31 entero. Aquí sólo entra la mitigación
   **estructural** de la inyección, que es de quien construye el prompt.
3. **`clarification_question`.** Se mantiene nula y se declara **de C31**, cerrando la orfandad que
   arrastra desde C30a.
4. **Fidelidad semántica en ejecución.** Ningún LLM juez: el §11.3 del diseño ya decidió *«sin LLM
   juez»*, y RAGAS *faithfulness* es C38.
5. **Publicar *faithfulness*.** El barrido publica tasa de rechazo y coste. La fidelidad necesita el
   arnés de C38.
6. **El bucle agéntico y sus tools.** Es C32.
7. **Los dos avisos de stock, `?question=` y la caja de la tarjeta.** Son C34 y C36.
8. **Tocar `backend/` o `frontend/`.** Esta historia es **sólo `ai-service/`**.
9. **Migración de base de datos.** Ninguna, ni Alembic ni EF Core. El argumentario **no se persiste**,
   que es justo lo contrario de necesitar tabla.
10. **Mover la *forma* del contrato.** Se regenera el `openapi.json` por **una descripción**; ningún
    campo se añade, se retira ni cambia de tipo.
11. **Reindexar, recalibrar umbrales o mover pesos.** Se consumen, no se re-fijan.

### Decisiones de diseño ya acordadas

| # | Decisión | Alternativa descartada, y por qué |
|---|---|---|
| **D1** | Lista blanca **pura**, sobre el objeto de payload, **más** adyacencia a moneda o stock. La prosa corrida sin listas numeradas se impone **en el prompt** | *Cero dígitos en el pitch*: verificable en una línea, pero pierde «plata de ley 925» y «talla 12», que son frases de venta reales. *Excepciones de formato en la puerta*: una excepción es una lista negra encubierta; prohibir las listas en el prompt deja la puerta sin nada que explicar. *Rango `min ≤ x ≤ max`* (S11): allí combinar es legítimo, aquí una talla interpolada no existe y un precio interpolado es lo prohibido |
| **D2** | Argumentario en **M2 y M3**; M1 diferido y declarado | *Los tres modos*: el contrato tiene un solo `pitch` y M1 devuelve hasta cinco grupos, así que su semántica es una decisión de producto que se toma mejor con el clasificador de C31 delante. *Sólo M2*: deja sin prosa el modo que hace realizable el *«¿este anillo se puede mojar?»* del §7.7, **ya servido y medido** por C30a |
| **D3** | **Una sola reparación** por petición, con las violaciones acumuladas. Resolución → correspondencia → puerta numérica | *Un reintento por puerta*: techo de **cuatro** llamadas por petición frente a los **128,6 ms** que cuesta hoy la recuperación entera, sin ganancia demostrable — las dos puertas fallan por la misma causa. *Cero reintentos*: desperdicia el caso común, que es una violación única y corregible |
| **D4** | `citations[]` = las que el argumentario usó; **cuando no hay argumentario, las que fundamentaron la respuesta** | *Vaciarlas al degradar*: la respuesta degradada tendría **menos** que la de C30a, y rompería la ablación del §11.2, que exige *«mismas citas, con prosa y sin ella»*. *Un campo nuevo que separe recuperadas de usadas*: mejor diseño conceptual y **mueve la forma** del esquema; D5 distingue los dos casos sin gastarlo |
| **D5** | `prompt_version` pasa a significar **«la capa de generación corrió»** | *No tocar nada*: el motivo vive sólo en el log, que es donde D-I dice que el texto **no** debe estar, y el frontend no puede distinguir «no redactamos» de «se rechazó». *Un `pitch_status` nuevo*: el más limpio y el más caro, mueve la forma del esquema congelado |
| **D6** | **Cliente propio** con `usage`, tokens de la reparación **sumados** | *Reutilizar `LiteLlmEnrichClient`*: descarta `response.usage`. No es preferencia de estilo, la clase no sirve. *Sustituir en vez de sumar*: el coste mentiría justo en las peticiones que más cuestan |
| **D7** | Fallo o *timeout* del proveedor **degradan**; la abstención **corta antes** de llamar | *Responder 503*: convierte una degradación elegante en una caída y tira la mitad de la respuesta que ya está calculada y funciona. Redactar sobre una abstención es el caso de las 180 horas de S16 |
| **D8** | La consulta viaja como **dato delimitado** en el mensaje de usuario | *Un mini-clasificador por palabras clave aquí*: es andamio que C31 borra, y el repositorio ya pagó por eso una vez con `C25bis` |
| **D9** | Salida estructurada **plana más tramo de apoyo**, verificado y **no publicado** | *`{pitch, citation_ids[]}`*: es la forma que la ficha insinúa y **no prohíbe la decoración**, que es lo que D-D existía para prohibir. *Por afirmación (`{claims:[…]}`)*: el código acabaría ensamblando la prosa desde fragmentos, y un argumentario de mostrador necesita continuidad; además **RAGAS no lo necesita** —toma (pregunta, respuesta, contextos) y descompone por su cuenta—. *Marcadores en línea*: **muertos por medición**, dos títulos de sección llevan dígitos y el marcador inyectaría `925`, `750` y `18` en el texto que lee la puerta numérica. *El tramo en el cable*: mismo beneficio y mueve la forma del esquema, sin consumidor que lo pida |

### Referencias

- **Decisiones de exploración:** [c30b-exploration-decisions.md](../../Proyecto%20Final%20AIEng/informes/c30b-exploration-decisions.md), que continúa [c30-exploration-decisions.md](../../Proyecto%20Final%20AIEng/informes/c30-exploration-decisions.md) (D-A … D-K) y [c30a-implementation-measurements.md](../../Proyecto%20Final%20AIEng/informes/c30a-implementation-measurements.md)
- **Historia predecesora:** [HU-AIENG-030a](HU-AIENG-030a.md)
- **Diseño:** **§7.7** con su bloque revisado del 13 sep, **§11.2** (ablaciones), **§11.3** (generación y validador anti-alucinación), **§11.6** (iteración de prompts), §15 limitaciones — [proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md)
- **Ficha del plan:** C30b en el §3 de [proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md), y la entrada del §0 del 13 de septiembre
- **Capability que se modifica:** [`assist-generation`](../../../openspec/specs/assist-generation/spec.md)
- **Capabilities que se consumen:** [`knowledge-corpus`](../../../openspec/specs/knowledge-corpus/spec.md) · [`retrieval-abstention`](../../../openspec/specs/retrieval-abstention/spec.md) · [`ai-service-api-contracts`](../../../openspec/specs/ai-service-api-contracts/spec.md)
- **Apuntes del máster usados como guía:** S11 · *Citación y atribución verificable*, S11 · *Detección y mitigación de alucinaciones*, S11 · *Content augmentation*, S16 · *Un sistema debe saber decir «No lo sé»*
- **Change:** `add-assist-pitch-generation` · **Épica:** EP15

---

## Criterios de Aceptación

### Escenario 1: Una pieza sin pregunta recibe su argumentario, con las citas que usó

- **Dado que** un producto indexado declara `plata` entre sus materiales,
- **Cuando** se solicita la asistencia de venta con su `product_id` y sin consulta,
- **Entonces** `pitch` trae prosa no vacía,
- **Y** `prompt_version` vale `assist/v1`,
- **Y** `usage` reporta tokens distintos de cero y el identificador del modelo,
- **Y** cada cita de `citations[]` fue **declarada por el modelo**, y no es simplemente una de las direccionadas.

### Escenario 2: Una pregunta sobre la pieza se responde en prosa y con cita

- **Dado que** un producto indexado declara `plata` y el operario pregunta si se puede mojar,
- **Cuando** se solicita la asistencia con `product_id` y `query`,
- **Entonces** `pitch` responde a la pregunta,
- **Y** `citations[]` contiene al menos un fragmento del corpus que el modelo declaró haber usado,
- **Y** ninguna cita procede de la ficha de un material que la pieza no declara.

### Escenario 3: El precio y el stock salen como placeholder y nunca como cifra

- **Dado que** una pieza tiene precio y existencias reales en el índice,
- **Cuando** se genera su argumentario,
- **Entonces** el texto contiene `{{price}}` y/o `{{stock}}` allí donde menciona precio o disponibilidad,
- **Y** ningún campo de la respuesta completa contiene una cifra de precio ni una cantidad de stock.

### Escenario 4: Una cifra ausente del contexto se rechaza aunque sea plausible

- **Dado que** el argumentario generado contiene un peso en gramos que no aparece en el payload entregado al modelo,
- **Cuando** se evalúa la puerta numérica,
- **Entonces** la cifra se marca como violación,
- **Y** se intenta **una** reparación con instrucción más dura,
- **Y** si reincide, la respuesta se entrega **sin argumentario**.

### Escenario 5: Una cifra pegada a un símbolo de moneda se rechaza aunque esté en la lista blanca

- **Dado que** la ficha `material-oro` está en el contexto y por tanto `750` pertenece a la lista blanca,
- **Cuando** el argumentario generado escribe «750 €»,
- **Entonces** la puerta lo rechaza **igualmente**, por adyacencia a moneda,
- **Y** el motivo registrado distingue esta causa de la de «cifra ausente del contexto».

### Escenario 6: Una cita que no resuelve se repara una vez y luego tumba el argumentario

- **Dado que** el modelo declara un `citation_id` que nunca estuvo en el conjunto entregado,
- **Cuando** se comprueba la resolución,
- **Entonces** se intenta **una** reparación,
- **Y** si el identificador sigue sin resolver, se entrega la respuesta **sin argumentario**,
- **Y** la cita colgante **nunca** se ignora ni sale del servicio.

### Escenario 7: Una cita cuyo tramo no está en el argumentario se retira, y la prosa se publica

- **Dado que** el modelo declara una cita cuyo `supported_claim` no es subcadena del `pitch` que escribió,
- **Cuando** se comprueba la correspondencia y la reparación no lo resuelve,
- **Entonces** **esa cita** se retira de `citations[]`,
- **Y** el argumentario **sí** se publica,
- **Y** el descarte queda registrado en el log.

### Escenario 8: Las dos puertas comparten una sola reparación

- **Dado que** un argumentario generado incumple a la vez la resolución de una cita y la puerta numérica,
- **Cuando** se decide la política,
- **Entonces** se realiza **un único** intento de reparación con **ambas** violaciones comunicadas juntas,
- **Y** el total de llamadas al proveedor para esa petición no supera dos.

### Escenario 9: Al caer el argumentario, las citas que fundamentaron la respuesta no se pierden

- **Dado que** la reparación no resolvió una violación dura y el argumentario se descarta,
- **Cuando** se compone la respuesta,
- **Entonces** `citations[]` contiene las citas que fundamentaron la respuesta, **exactamente como las entregaría C30a**,
- **Y** la respuesta degradada no es en ningún campo inferior a la que la capa estructurada produce por sí sola.

### Escenario 10: El contrato distingue «no redactamos» de «lo intentamos y se rechazó»

- **Dado que** la capa de generación corrió y su argumentario fue descartado,
- **Cuando** se compone la respuesta,
- **Entonces** `pitch` viene vacío **y** `prompt_version` vale `assist/v1`,
- **Y** en un despliegue sin capa de generación `prompt_version` sigue siendo **nulo**.

### Escenario 11: La consulta libre sigue sin argumentario, y se declara

- **Dado que** la petición trae `query` y no trae `product_id`,
- **Cuando** se sirve la asistencia,
- **Entonces** `pitch` viene **vacío** y `prompt_version` **nulo**,
- **Y** **no se realiza ninguna llamada al proveedor generativo**,
- **Y** el comportamiento está declarado en la capability como alcance de C31 y no como defecto.

### Escenario 12: Cuando el catálogo no puede contestar, no se llama al proveedor

- **Dado que** la regla de abstención decidió que el catálogo no puede responder la consulta,
- **Cuando** se sirve la asistencia,
- **Entonces** `abstained` vale verdadero y no hay grupos,
- **Y** **no se realiza ninguna llamada al proveedor generativo**, porque no hay nada sobre lo que redactar.

### Escenario 13: Un fallo del proveedor degrada y nunca convierte la respuesta en un error

- **Dado que** el proveedor generativo agota su *backoff*, devuelve error o supera el *timeout*,
- **Cuando** se sirve una asistencia anclada a pieza,
- **Entonces** la respuesta es **200** con grupos, avisos y citas,
- **Y** `pitch` viene vacío,
- **Y** la ruta **no** devuelve 5xx.

### Escenario 14: El argumentario no se persiste en ninguna parte

- **Dado que** se ha generado un argumentario y se ha entregado,
- **Cuando** se observa el tráfico de la base de datos durante la petición,
- **Entonces** **no se ejecuta ninguna sentencia de escritura**,
- **Y** la comprobación se hace contando DML sobre el motor, no comprobando qué módulos se importan.

### Escenario 15: El texto del argumentario no llega a ningún log

- **Dado que** se ha generado un argumentario,
- **Cuando** se inspeccionan las líneas de log de la petición,
- **Entonces** aparecen `trace_id`, `prompt_version`, modelo, `usage`, latencia, los `citation_id` usados, los códigos de aviso, la decisión de abstención, la longitud y un *hash*,
- **Y** **no aparece el texto** del argumentario, ni entero ni en fragmentos.

### Escenario 16: El prompt versionado y su constante no pueden divergir

- **Dado que** `PROMPT_VERSION` vale `assist/v1`,
- **Cuando** se carga el prompt de generación,
- **Entonces** procede de `ai-service/prompts/assist/v1.md`,
- **Y** un test falla si la constante y el fichero dejan de corresponderse.

### Escenario 17: La consulta del operario es dato y nunca instrucción

- **Dado que** la consulta contiene texto con forma de instrucción —por ejemplo, pedir que se ignoren las reglas anteriores—,
- **Cuando** se construye la llamada al proveedor,
- **Entonces** la consulta viaja en el **mensaje de usuario**, dentro de un bloque delimitado y etiquetado como dato,
- **Y** **nunca** se concatena al mensaje de sistema,
- **Y** las reglas invariantes del prompt siguen siendo las mismas que sin esa consulta.

### Escenario 18: El uso de tokens se acumula sobre la reparación

- **Dado que** una petición necesitó una reparación y por tanto dos llamadas,
- **Cuando** se compone la respuesta,
- **Entonces** `usage` refleja la **suma** de las dos llamadas,
- **Y** no sólo la última.

### Escenario 19: Fuera de alcance explícito

- **Dado que** esta historia entrega el argumentario y sus garantías,
- **Cuando** se revisa lo que **no** hace,
- **Entonces** no clasifica la intención ni rechaza consultas fuera de dominio —eso es C31—,
- **Y** no emite `clarification_question`, que queda declarada como de C31,
- **Y** no comprueba en ejecución que un fragmento citado **diga** lo que la frase afirma, limitación que se declara y que mide C38,
- **Y** no toca `backend/` ni `frontend/`, ni crea migración alguna.

---

## Notas adicionales

- **Actor:** desarrollador del proyecto. La ruta es interna de `jbg-ai` y sólo la consume .NET con
  el token de servicio HS256; **el navegador nunca llama a Python**.
- **Es la historia que pone a este proyecto la capa que el rubro nombra.** El §4 del plan lo dice sin
  rodeos: `assist/` era el hueco que el corte de C27 dejó a la vista, y *«ésa, y no complementarios,
  es la deuda grande que queda»*. C30a puso la mitad estructurada; ésta pone la generativa.
- **La garantía anti-alucinación cambia de sitio, no de dueño.** El validador determinista del §11.3
  seguía siendo la primera línea y sólo actuaba en evaluación. A partir de aquí la primera línea
  corre **en ejecución** y el validador pasa a comprobar que la primera funciona, que es un test más
  fuerte.
- **Limitación conocida y declarada:** la *alucinación con coartada* —una cita válida, usada de
  verdad en una frase escrita de verdad, que aun así no dice lo que la frase afirma— sobrevive a las
  tres comprobaciones. No se pone un juez en el camino del mostrador: duplica latencia y coste donde
  hay un cliente delante, es circular, y el §11.3 ya decidió *«sin LLM juez»*. Se mide con RAGAS en
  C38.
- **Limitación conocida heredada:** la atribución cruzada entre materiales que la pieza **sí**
  declara. Mitigada por el tope de dos materiales y por la sección de piezas mixtas; ningún filtro la
  resuelve.
- **Hueco que esta historia descubre y que no es suyo:** el golden set de C24/C26 son **72 consultas
  sin ancla de pieza**, o sea 100 % M1. No puede evaluar el argumentario. El barrido necesita muestra
  propia y **C38 hereda el mismo hueco**, que queda anotado en su ficha.
- **Coste, para que nadie lo use como argumento:** ~1.500 tokens de entrada y ~300 de salida, que a
  los precios verificados en `evals/golden/pricing.yaml` son **~0,0004 USD por petición**. Ninguna de
  las nueve decisiones se toma por coste.
- **Trampa de máquina, y hay que resolverla antes de la sesión:** el barrido es la primera llamada
  real a un proveedor en mucho tiempo en este repositorio, y en esta máquina muere con
  `CERTIFICATE_VERIFY_FAILED` salvo que `SSL_CERT_FILE` apunte al PEM exportado del almacén de
  Windows. `--system-certs` arregla a `uv`, **no al proceso Python**. Ningún test lo nota.
- **Change de OpenSpec:** `add-assist-pitch-generation`. **Rama:** `c30b-add-assist-pitch-generation`.

---

## Tareas

1. **Puerta de entrada**: línea base de las dos suites por **nombres de test** y no por recuento
   (`git stash push -u`, correr, `git stash pop`), y `openspec validate --all --strict` en verde
   antes de tocar nada.
2. **Muestra del barrido**, declarada antes de medir: piezas estratificadas por número de materiales
   —1 frente a ≥2—, porque la sección de piezas mixtas sólo entra a partir de dos y es donde vive el
   riesgo de atribución cruzada.
3. **Prompt versionado**: `prompts/assist/v1.md`, `PROMPT_VERSION` y su test fichero↔constante.
   Reglas invariantes en el sistema, bloque de tarea por modo, prosa corrida sin listas numeradas y
   la consulta como dato delimitado.
4. **Esquema de salida estructurada** `AssistPitch` / `UsedCitation`, interno y no publicado.
5. **Cliente generativo** en `assist/`, replicando la costura de `LiteLlmEnrichClient` y devolviendo
   `usage`, con *timeout* y fake inyectable por constructor.
6. **Las tres comprobaciones y la reparación única**: resolución, correspondencia y lista blanca con
   adyacencia a moneda, en ese orden, con sus dos políticas.
7. **Cableado en el orquestador**: M2 y M3 generan; M1 y la abstención cortan antes de llamar; el
   fallo del proveedor degrada.
8. **`prompt_version` en degradación** y **regeneración del `openapi.json`** con el perfil canónico,
   verificando el diff **campo a campo** y no por lectura.
9. **Tests de no persistencia**: listener `before_cursor_execute` contando DML, y ausencia del texto
   en el log.
10. **Barrido de 1/2/3 secciones** con su runner en `evals/`, resultados atados a `run_id`, `git_sha`
    y `prompt_version` —que es la excepción de persistencia de C38, ya implementada—, publicando la
    tasa de rechazo **por causa** y el coste.
11. **Deltas de la capability `assist-generation`** con `openspec validate --all --strict` en verde,
    incluida la declaración de la limitación semántica y la asignación de `clarification_question` a
    C31.
12. **Informe de implementación** con las cifras del barrido y con lo que la implementación refute de
    esta historia.
13. **Documentación**: `Documentos/epicas.md`, plan de changes, `ai-service/README.md` y las fichas de
    C31 y C38 si el trabajo mueve algo de lo que ya llevan anotado.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **5/5** — el §6 del plan la marca como **«nunca se recorta»**, y con motivo propio: *«sin argumentario el PF no tiene capa de generación, que es literalmente lo que el rubro nombra»* |
| Urgencia | **4/5** — desbloquea **C31** y **C38**. No está en la cadena `C30a → C34 → C36`, que ya corre en paralelo, pero cierra por el otro lado `C30b → C31 → C32 → C38 → C39` |
| Complejidad / esfuerzo | **4/5** — sin migración, sin `backend/`, sin `frontend/` y con el contexto ya destilado por C30a. Lo caro es calibrar la puerta para que no se coma los argumentarios buenos, y la disciplina de no persistir el texto en ningún sitio, log incluido |
| Riesgos | **El principal es el falso positivo de la puerta numérica**: un rechazo por formato cuesta el argumentario entero, así que una puerta mal calibrada hace que este change **no entregue prosa** (mitigado por la prosa corrida impuesta en el prompt, por la tasa de rechazo clasificada por causa del Escenario 5, y porque la política dura sólo se aplica a violaciones duras). Que la comprobación de correspondencia rechace por paráfrasis o puntuación y retire citas buenas (mitigado por la normalización y por ser política **proporcionada**, no dura). Que la degradación acabe pareciéndose a un fallo silencioso (mitigado por el Escenario 10). Que el texto del argumentario se escape a un log al depurar (mitigado por el Escenario 15, que es un test y no una convención). Que el barrido se lleve la sesión por delante, en cuyo caso es la línea de corte declarada y los valores actuales quedan como *punto de partida no calibrado*. Y el certificado de esta máquina, que no es riesgo de diseño pero sí de sesión |
| Dependencias | **C30a**, archivado el 2026-09-13. Consume **C23** (corpus y direccionamiento), **C25** (abstención) y **C09** (la costura del cliente, que se replica y no se reutiliza). **Bloquea a C31**, y con él a C32 y a C38 |
