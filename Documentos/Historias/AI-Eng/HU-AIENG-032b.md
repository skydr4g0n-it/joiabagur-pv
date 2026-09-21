# HU-AIENG-032b: El bucle agéntico del asistente de venta — la capa de decisión, sus seis presupuestos y la pasada que los fija

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** que el asistente de venta decida por sí mismo qué herramienta usar en cada vuelta, sobre
una transcripción multi-turno, con presupuestos duros, `partial: true` cuando se agotan y una traza
que diga qué hizo y cuánto costó,
**para** que el Proyecto Final pueda comparar **el pipeline determinista contra el agente sobre el
mismo conjunto** y publicar el sobrecoste real de la autonomía en lugar de afirmarlo.

---

## Descripción

C32 se partió el 2026-09-20 por la regla 5 del §1 del plan de changes. [C32a](HU-AIENG-032a.md)
entregó la mitad que no llama a ningún proveedor: las seis tools, el registro, los esquemas de
*function calling*, el invariante de solo-lectura por introspección y la etiqueta cualitativa de
disponibilidad. Esta historia entrega **la otra mitad, que es la cara**: el bucle.

El corte dejó **una ablación gratis**, y ésa es la razón de que el bucle *conviva* con el pipeline
en vez de sustituirlo. El §11.4 del diseño pide una fila —*pipeline contra agente, mismo golden set,
mismas tools*— que desaparecería si `/v1/assist/sale` pasara a ejecutar el bucle detrás de un *flag*.
De las cuatro cosas que el PF evalúa de la capa agéntica —**el bucle, el presupuesto duro, el
invariante de solo-lectura y el `partial: true`**—, C32a entregó una. Esta historia entrega las tres
restantes.

### Lo que C32a deja escrito y en verde, y que aquí no se decide

| Pieza | Estado | Evidencia |
|---|---|---|
| `build_registry(principal, settings, embed, search, knowledge)` | ✅ ata el principal **en la construcción** | [`assist/tools.py`](../../../ai-service/src/jbg_ai/assist/tools.py) |
| `registry.schemas()` | ✅ los seis esquemas en **orden congelado**, listos para el parámetro `tools` | ídem |
| `await registry.invoke(nombre, args)` | ✅ **no lanza nunca**, ni con un nombre de tool inventado | ídem |
| `registry.embedding_calls` | ✅ contador propio de *embeddings*, separado de `usage.calls` | ídem |
| `verify_read_only(registry)` | ✅ corre **en la construcción**: un puerto que escribe falla al construir, no en la vuelta tres | ídem |
| Capability viva `sales-assistant-tools` | ✅ 13 requisitos, 25 escenarios | [`spec.md`](../../../openspec/specs/sales-assistant-tools/spec.md) |

### Estado actual del código, verificado en el repositorio

| Pieza que el bucle necesita | Estado | Evidencia |
|---|---|---|
| Puerto de *function calling* | ❌ **cero** — `AssistLlm.generate()` está fijado a `response_format=AssistPitch` y `RouterLlm.classify()` a `RouteDecision` | [`assist/llm.py`](../../../ai-service/src/jbg_ai/assist/llm.py), [`assist/router_llm.py`](../../../ai-service/src/jbg_ai/assist/router_llm.py) |
| Bucle, iteraciones, presupuestos | ❌ **cero** | — |
| `POST /v1/assist/agent` | ❌ **cero** — el contrato congelado **nunca reservó ruta** para el agente de venta | [`ai-service/openapi.json`](../../../ai-service/openapi.json) |
| Transcripción multi-turno | ❌ **cero** — `AssistRequest` lleva `query` suelta, `max_length=500` | [`api/schemas/assist.py`](../../../ai-service/src/jbg_ai/api/schemas/assist.py) |
| Prompt del bucle | ❌ **cero** — existen `assist/v1-v3` (argumentario) y `router/v1-v3` (clasificador), ninguno del agente | [`ai-service/prompts/`](../../../ai-service/prompts/) |
| `generate_pitch()` y `free_query_payload_from()` | ✅ existen — C30b | [`assist/pitch.py`](../../../ai-service/src/jbg_ai/assist/pitch.py), [`assist/prompt.py`](../../../ai-service/src/jbg_ai/assist/prompt.py) |
| `classify_query()` y `RoutingOutcome` | ✅ existen — C31 | [`assist/routing.py`](../../../ai-service/src/jbg_ai/assist/routing.py) |
| Pool de conexiones | ⚠️ **5 sin overflow**, y `SqlAlchemyProductSearch` abre un `session_scope` por método | [`db/engine.py`](../../../ai-service/src/jbg_ai/db/engine.py) |

### Los cinco hallazgos de la exploración que reencuadran la ficha

**1 · La propuesta de enrutado de la ficha cuesta O(N²) y rompe el techo que ella misma declara.**
La ficha proponía *«clasificar todos los turnos y que sólo el primero cortocircuite»*. Con contrato
sin estado, el cliente reenvía la transcripción entera en cada petición, así que «clasificar todos»
significa **N clasificaciones en la petición N**: una conversación de cinco turnos hace 15 llamadas
de enrutador en vez de 5, y a partir del turno 8 el techo declarado de ocho llamadas se rompe solo.
Y las repetidas compran **la misma respuesta** — mismo prompt, temperatura cero—, que es el
argumento exacto con el que C31 rechazó el reintento del clasificador.

**2 · El turno de seguimiento es elíptico, y la matriz de C31 se midió sobre consultas sueltas.**
`«¿y en dorado?»` clasificado en solitario produce, casi con seguridad, *insuficiente* → repregunta.
El sistema preguntaría al operario por un eje que la conversación acaba de responder. La salida no
es cambiar lo que entra al clasificador —eso invalidaría los 119 casos medidos— sino **mover la
repregunta a quien sí tiene contexto**: el bucle, vía `pedir_aclaracion`.

**3 · No existe ningún puerto de *function calling*.** La ficha cuenta el bucle como lo único nuevo.
Hacen falta además un **tercer puerto**, una **tercera cadena de credencial** y una **tercera
variable de modelo**, con el mismo criterio con el que C30b y C31 separaron las suyas.

**4 · El 5× que predicen los apuntes es el multiplicador de *tokens*, no el de dinero.** Derivado de
cifras medidas en este repositorio —enrutador **0,00205 USD** (C31), argumentario **0,00077 USD** sobre
120 generaciones (C30b)—, el pipeline cuesta ~**0,0028 USD/petición**. El bucle estimado en `gpt-4o`
con cinco vueltas de contexto creciente sale ~**0,054 USD**, es decir **~19×**. Esos 19 se descomponen
en **×5 de tokens**, que es estructural, y **×4 de modelo**, que es una **elección separable y
reversible** — y por eso los dos brazos se miden en la misma pasada.

**5 · La ficha escribe cuatro presupuestos y el que falta es el que un mostrador siente.** No hay
presupuesto de **reloj de pared**. El peor caso declarado son 15-20 s, y sin *deadline* el peor caso
real es cinco vueltas al timeout del proveedor más las tools más el argumentario.

### El muro de contaminación, que es el riesgo mayor de esta historia

El §11.4 pide la ablación sobre el **mismo golden set**. Si el prompt del agente se itera contra el
golden set, el golden set deja de poder arbitrar esa comparación; y si se itera contra escenarios
multi-turno, ésos son los 20-25 de C38. En ambos casos la cifra que el PF puntúa nace contaminada.
La regla ya está escrita como requisito vivo desde C31: *«The classifier's prompt is derived from the
catalogue vocabulary and never from the evaluation sets»*.

```
 ┌─ SET DE CARGA ──────────────────┐   ┌─ SET DE CALIBRACIÓN ───────────┐
 │  ~60-100 transcripciones        │   │  ~15-20 transcripciones        │
 │  SINTÉTICAS generadas, del      │   │  a mano, CON TOOL ESPERADA     │
 │  vocabulario del catálogo       │   │  por turno                     │
 ├─────────────────────────────────┤   ├────────────────────────────────┤
 │  p95 de tokens · p95 de reloj   │   │  granularidad de las seis      │
 │  curva de crecimiento           │   │  ¿la etiqueta se queda corta?  │
 │  coste 4o contra 4o-mini        │   │  iteración del prompt agent/v1 │
 ├─────────────────────────────────┤   ├────────────────────────────────┤
 │  contaminación: NINGUNA         │   │  declarado calibration-only    │
 │  (mide acumulación, no calidad) │   │  C38 escribe las suyas aparte  │
 └─────────────────────────────────┘   └────────────────────────────────┘
 ╔═══════════════════════════════════════════════════════════════════════╗
 ║  GOLDEN SET (C24) · 48 consultas — ESTA HISTORIA NO LO TOCA           ║
 ║  Queda limpio para la ablación pipeline-contra-agente de C38          ║
 ╚═══════════════════════════════════════════════════════════════════════╝
```

Los dos tamaños son distintos por una razón que no es presupuestaria: **a temperatura cero y con
registro determinista, repetir un escenario devuelve casi lo mismo**, así que las repeticiones no
compran resolución de p95. Un p95 de tokens necesita **variedad de transcripciones**; las dos
preguntas de C32a necesitan lo contrario, pocas y con verdad de terreno.

---

### Alcance de esta historia (sí)

1. **El bucle manual con *function calling***: decidir, ejecutar tools **en paralelo**, observar,
   volver a decidir, hasta que el modelo deje de pedir herramientas o se agote un presupuesto.
2. **Un puerto de agente nuevo** cuyo tipo de retorno **no tiene dónde poner prosa**, y su adaptador.
3. **Seis presupuestos duros** con aserción en ejecución, y `partial: true` al agotar cualquiera.
4. **La transcripción multi-turno en la petición**, con el servicio **sin estado**, delimitado por
   turno y topes de turnos y de caracteres.
5. **`POST /v1/assist/agent`**, con `ai-service/openapi.json` regenerado y verificado hoja a hoja.
6. **El guardarraíl de entrada**: una clasificación por petición, sobre el turno que se contesta.
7. **Dos prompts versionados**: `agent/v1` (el bucle) y `assist/v4` (el argumentario, con la tarea
   nueva de evidencia del agente).
8. **La traza**, en dos formas: acotada en el cable, rica en proceso para el arnés.
9. **La pasada con proveedor real de dos brazos**, que fija el presupuesto de tokens y el de reloj y
   responde las dos preguntas que C32a dejó abiertas.
10. **`presupuesto_agotado`** como quinta causa de fallo de tool, con la modificación de la
    capability viva `sales-assistant-tools` que eso implica.

### Fuera de alcance (no)

1. **Los 20-25 escenarios multi-turno de evaluación, los adversarios y los de inyección
   sistemáticos** — **C38**. Los sets de esta historia son de carga y de calibración, y se declaran
   como tales.
2. **El golden set de C24 no se toca**, ni para calibrar ni para iterar el prompt.
3. **`POST /v1/assist/sale` no cambia**: ni su forma de respuesta, ni su techo de tres llamadas, ni
   su comportamiento. Sigue siendo la fila determinista de la ablación.
4. **Ningún consumidor .NET.** C34 llama a `/sale`; la ruta del agente no tiene cliente en `backend/`
   y su política de *timeout* de Polly queda **identificada y no hecha**.
5. **Ninguna pantalla.** C36 pinta la tarjeta de `/sale`; el bucle no llega a frontend.
6. **Sin almacén de sesión, sin *checkpointer* y sin LangGraph.** El §9.2 del diseño lo descarta por
   escrito: *«no hay ramificación con estado ni reanudación que lo justifique»*.
7. **Sin streaming ni respuesta en dos fases.** El peor caso de 15-20 s síncronos queda **declarado
   como limitación**, no mitigado.
8. **El endpoint .NET de disponibilidad puntual** sigue identificado, acotado y no hecho.
9. **Compactación o resumen de observaciones antiguas**: identificada y **no hecha**, ver D-14.
10. **Ningún cambio en `backend/`, `frontend/` ni `terraform/`.** Sin migración de EF Core.

---

### Decisiones de diseño ya acordadas

Las tres primeras vienen del §0 del plan (2026-09-20); de la **D-4** en adelante se tomaron en la
sesión de exploración previa a esta historia.

| # | Decisión | Razón |
|---|---|---|
| **D-1** | **Ruta propia `POST /v1/assist/agent`**; `/v1/assist/sale` **no se toca** | Peor caso ~15-20 s contra los **5 s** que el §6.4 declara para `/v1/assist`. Un *flag* en la ruta existente pondría ese camino en la misma que C34 llama síncrona desde el mostrador, y metería `partial` y la traza en el `AssistResponse` que C34 y C36 leen. La ruta nueva es **adición pura** |
| **D-2** | **El bucle reúne evidencia; redacta `generate_pitch()`** | Si la última vuelta escribiera prosa se esquivarían de golpe la puerta numérica por lista blanca, la integridad referencial de las citas y la reparación única, las tres de C30b. Y mantiene el *«nada se persiste»* sin esfuerzo: el razonamiento intermedio no sale del proceso |
| **D-3** | **El multi-turno viaja en la petición; el servicio no guarda nada** | Un almacén de sesión chocaría con la propiedad que C30b y C31 dejaron con test. Dos consecuencias: el delimitado `QUERY_OPEN`/`QUERY_CLOSE` se aplica a **cada turno** —una inyección se esconde en el turno 3— y **los turnos del asistente son falsificables**, así que se tratan como dato igual que la consulta |
| **D-4** | **Una clasificación por petición, sobre el turno que se contesta.** El **rechazo cortocircuita en cualquier turno**; la **repregunta es del bucle** vía `pedir_aclaracion`; el **`index` se descarta** | «Clasificar todos» cuesta O(N²) y rompe el techo de ocho (hallazgo 1). Clasificar sólo el primero deja la deriva del turno 5 sin guardarraíl, que es justo la categoría adversaria del §11.4. La repregunta se mueve a quien tiene contexto (hallazgo 2), y el `index` sobra porque **el agente elige su propia tool**: eso es tener un bucle. La matriz de C31 queda **intacta** — entra una consulta suelta, sale un veredicto |
| **D-5** | El puerto del agente **devuelve `tool_calls` y coste, y no tiene campo de texto** | *«El contenido textual de las vueltas se descarta»* pasa de regla que alguien debe respetar a **verdad del tipo**. Es el mismo criterio con el que C32a comprobó el invariante de solo-lectura por introspección en vez de con un `writes: bool`: un campo que alguien no debe leer es un campo que alguien leerá. Coste declarado: se pierde el razonamiento del modelo para depurar; el adaptador registra longitud y digest, nunca el texto |
| **D-6** | **`gpt-4o` para el bucle**, con credencial y variable propias, y el brazo **`gpt-4o-mini` medido en la misma pasada** | Elegir *qué tool* es más difícil que elegir *qué etiqueta*, y C31 midió que `gpt-4o-mini` silenciaba 3 de 119 donde `gpt-4o` silenciaba 0 **sin tocar el prompt**. Los ×4 de modelo del hallazgo 4 son separables: si `mini` sostiene la selección, el coste cae y la decisión se revierte cambiando una variable — que es exactamente lo que compró tenerla separada |
| **D-7** | **Seis presupuestos**, no cuatro: ≤5 iteraciones, ≤6 tool calls, ≤8 llamadas al proveedor, **tokens**, **contexto en caracteres** y **reloj de pared** | El de llamadas es `1 enrutador + ≤5 vueltas + ≤2 argumentario`, derivado de constantes y nunca escrito como dígito. Los dos nuevos: el de **caracteres** es determinista y se evalúa **antes** de llamar; el de **tokens** sólo se puede hacer cumplir **post-hoc** sin meter un tokenizador como dependencia nueva, y puede pasarse por una vuelta como mucho. El de **reloj** es el que un mostrador siente (hallazgo 5) |
| **D-8** | Las tools de una vuelta se ejecutan **en paralelo, con tope de 4** | El apunte de S12 avisa de que asumir una sola llamada por vuelta es un bug clásico. Pero el pool es de **5 sin overflow** y `SqlAlchemyProductSearch` abre una sesión por método: seis tools concurrentes se encolan contra sí mismas y la sexta espera `pool_timeout`, que se leería como «la base de datos está caída» |
| **D-9** | Las tool calls que **no caben** en el presupuesto se ejecutan por orden de emisión hasta agotarlo; el resto vuelve como observación fallida con causa **`presupuesto_agotado`** | Un error es dato, no excepción — la regla de C32a. El modelo ve *por qué* se quedó sin herramienta. Coste declarado: es una **quinta causa** en un vocabulario cerrado con requisito vivo, así que esta historia **modifica** `sales-assistant-tools` |
| **D-10** | **`pedir_aclaracion` es terminal**: invocarla acaba el bucle | Pedir aclaración y seguir buscando es incoherente: se está diciendo que falta información para buscar. Y le da a la ablación una fila limpia — *el pipeline repregunta por regla, el agente por decisión* |
| **D-11** | **Ninguna etiqueta de disponibilidad llega al argumentario** | La etiqueta gobierna la **decisión del bucle**, no la prosa. La autoridad sobre el stock es de .NET (§6.2), la proyección se desfasa minutos, `{{stock}}` es la única expresión de existencias que el contrato admite, y `disponible` es literalmente miembro de `STOCK_MARKERS` en la puerta numérica |
| **D-12** | Los **sustitutos entran como grupo distinguido**, con un campo de vocabulario cerrado, y eso obliga a **`assist/v4`** con una tarea nueva | El *payload* cambia de forma, así que el prompt tiene que explicar qué es un sustituto. `v3` **se queda intacto en disco**, por el precedente de C31: las 120 generaciones medidas contra él tienen que seguir siendo interpretables |
| **D-13** | **Dos prompts versionados**, no uno: `agent/v1` (el bucle) y `assist/v4` (el argumentario) | La ficha sólo nombraba `assist/v4`. El *system prompt del bucle* no tenía casa: es otra llamada, con otra salida y otro modelo, exactamente el criterio por el que `router/v3` vive aparte de `assist/v3` |
| **D-14** | **Acumulación íntegra del contexto con cota**, y se **publica la curva de crecimiento**. La compactación queda identificada y **no hecha** | Los apuntes de S12 señalan el crecimiento del contexto como el factor dominante del coste. Pero resumir observaciones antiguas destruye en silencio la capacidad del modelo de razonar sobre lo que ya vio, y adoptarlo sin medición es el error de `v3-señales` al revés: primero se mide la curva, después se decide si hay que doblarla |
| **D-15** | La respuesta es **`AgentAssistResponse` subclase de `AssistResponse`**, con `partial`, iteraciones, tool calls gastadas, traza y su propio `usage` con `calls` | La ablación es *pipeline contra agente sobre el mismo conjunto*: que sea un **diff de campos** y no una traducción es el valor entero del corte. `Usage` del contrato **no publica `calls` hoy**, así que el techo «observable desde el mismo objeto que el consumidor lee» sólo se cumple si el agente trae el suyo |
| **D-16** | **Dos trazas.** En el cable, acotada y **sin argumentos ni contenido de observación**; en proceso, rica, para el arnés | Los argumentos de `buscar_catalogo` son la consulta reformulada por el modelo, y un consumidor .NET **loguea la respuesta**: la regla viva de C30b y C31 es que el texto del operario no entra en almacenamiento durable. C38 necesita *«tools invocadas contra esperadas»*, y para eso **los nombres bastan** |
| **D-17** | **`abstained` es cierto sólo si** corrió al menos una búsqueda de catálogo, **todas** abstuvieron y no se reunió ninguna cita | Reutiliza la costura `on_abstention` que `buscar_catalogo` ya usa. Colapsarlo con «no encontré nada» diría lo contrario de la verdad, que es la refutación 2.4 de C32a sobre `low_confidence` |
| **D-18** | **Dos instrumentos de medición y un muro de contaminación**: set de carga sintético generado (~60-100) y set de calibración a mano (~15-20). **El golden set no se toca** | Ver el diagrama de arriba. A temperatura cero las repeticiones no compran p95, así que el p95 necesita variedad y las dos preguntas de C32a necesitan verdad de terreno. Son dos instrumentos porque son dos preguntas |

### Referencias

- Change de OpenSpec: `openspec/changes/add-sales-assistant-agent-loop/` (C32b), rama `c32b-add-sales-assistant-agent-loop`
- Ticket: [T-AIENG-032b](../../../openspec/changes/archive/2026-09-21-add-sales-assistant-agent-loop/ticket.md)
- Ficha del plan: [§3 · C32b](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) y la nota del **§0 del 2026-09-20**
- Diseño RAG: [§6.1, §6.4, §9.1, §9.2, §11.2, §11.4](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md)
- Capability que se modifica: [`sales-assistant-tools`](../../../openspec/specs/sales-assistant-tools/spec.md)
- Capability consumida: [`assist-generation`](../../../openspec/specs/assist-generation/spec.md)
- Informe de C32a: [`c32a-implementation-measurements.md`](../../Proyecto%20Final%20AIEng/informes/c32a-implementation-measurements.md)
- Precedente de pasada con proveedor: [`c30b-implementation-measurements.md`](../../Proyecto%20Final%20AIEng/informes/c30b-implementation-measurements.md) — 120 generaciones, 175 llamadas, 0,0897 USD
- Historia anterior: [HU-AIENG-032a](HU-AIENG-032a.md) · [HU-AIENG-031](HU-AIENG-031.md)
- Épica: [EP15 — Venta Asistida, Sustitutos y Agentes](../../epicas.md)

---

## Criterios de Aceptación

### Escenario 1: El bucle reúne evidencia y para cuando el modelo deja de pedir herramientas

- **Dado que** llega una petición al asistente agéntico con una consulta de catálogo,
- **Cuando** el modelo pide herramientas y, tras observarlas, deja de pedirlas,
- **Entonces** el bucle **para sin agotar ningún presupuesto**,
- **Y** la respuesta **no** viene marcada como parcial,
- **Y** el argumentario lo ha escrito la capa de generación sobre la evidencia reunida, no el modelo
  del bucle,
- **Y** las citas publicadas son las que el argumentario declaró haber usado y que verificaron.

### Escenario 2: Agotado el presupuesto de iteraciones, responde con lo que tenga y lo declara

- **Dado que** el modelo sigue pidiendo herramientas vuelta tras vuelta,
- **Cuando** se alcanza el tope de iteraciones,
- **Entonces** el bucle **corta**,
- **Y** la respuesta viene marcada como **parcial**,
- **Y** aun así trae la evidencia reunida hasta ese punto y un argumentario escrito sobre ella,
- **Y** la traza declara cuántas iteraciones y cuántas llamadas a herramienta se gastaron.

### Escenario 3: Ningún texto de las vueltas del bucle llega a la respuesta

- **Dado que** el modelo devuelve prosa junto con sus llamadas a herramienta en alguna vuelta,
- **Cuando** se compone la respuesta,
- **Entonces** **ningún fragmento de ese texto aparece en ningún campo** de la respuesta,
- **Y** tampoco aparece en la traza del cable,
- **Y** la propiedad se sostiene **por el tipo** que el puerto devuelve, no por una comprobación
  posterior.

### Escenario 4: Cada turno de la transcripción viaja como dato delimitado

- **Dado que** la petición trae una transcripción de varios turnos y el **turno 3** contiene un
  intento de inyección de instrucciones,
- **Cuando** se construyen los mensajes de cualquiera de las llamadas al proveedor,
- **Entonces** **todos** los turnos viajan dentro de las marcas de delimitación, y no sólo el último,
- **Y** ninguno se concatena al mensaje de sistema,
- **Y** el mensaje de sistema es **idéntico** al que produce una transcripción sin inyección,
- **Y** los turnos atribuidos al asistente se tratan como dato del cliente, sujetos a los mismos
  topes que los del operario.

### Escenario 5: El techo de llamadas al proveedor se cumple para una petición

- **Dado que** una petición clasifica, da el máximo de vueltas y repara el argumentario,
- **Cuando** termina,
- **Entonces** el número total de llamadas al proveedor de chat **no supera el techo declarado**,
- **Y** ese techo es la **suma de las constantes** de sus tres tramos y no un dígito escrito aparte,
- **Y** el total es legible por el consumidor **desde el mismo objeto** en el que lee el coste,
- **Y** las llamadas de *embeddings* quedan **fuera** de esa cifra, en su contador propio.

### Escenario 6: El rechazo del enrutador cortocircuita en cualquier turno y no gasta herramientas

- **Dado que** una conversación empezó dentro de dominio y su **último turno** deriva fuera de él,
- **Cuando** se contesta esa petición,
- **Entonces** se hace **exactamente una** clasificación, sobre el turno que se contesta,
- **Y** el bucle **no llega a arrancar**: cero llamadas a herramienta y cero recuperaciones,
- **Y** la respuesta trae el código de rechazo que corresponde, de los dos que C31 distingue,
- **Y** **no** se marca como abstención.

### Escenario 7: La repregunta la decide el bucle, y termina la conversación

- **Dado que** la consulta no trae bastante para buscar,
- **Cuando** el bucle invoca la herramienta de aclaración,
- **Entonces** el bucle **termina en esa vuelta**, sin pedir más herramientas,
- **Y** la pregunta devuelta es **exactamente** la plantilla que el catálogo cerrado asocia al eje
  elegido,
- **Y** el clasificador **no** ha emitido repregunta alguna, porque en esta ruta no decide eso.

### Escenario 8: La disponibilidad dispara el pivote a sustitutos, y no lo dispara de más

- **Dado que** la pieza sobre la que gira la conversación está **sin existencias** en el punto de
  venta del token,
- **Cuando** el bucle observa su disponibilidad,
- **Entonces** invoca la herramienta de sustitutos en una vuelta posterior,
- **Y** los sustitutos llegan al argumentario como **grupo distinguido** de los resultados de
  catálogo,
- **Y** una pieza en **últimas unidades** o con **ámbito ausente** **no** dispara el pivote, porque
  ninguna de las dos significa que la tienda no pueda venderla.

### Escenario 9: Ninguna etiqueta de disponibilidad llega al argumentario

- **Dado que** el bucle ha observado la disponibilidad de una o varias piezas,
- **Cuando** se construye lo que se entrega a la capa de generación,
- **Entonces** **ninguna etiqueta de disponibilidad forma parte de ello**,
- **Y** el argumentario generado no contiene ninguna de esas etiquetas,
- **Y** la única expresión de existencias en la respuesta sigue siendo el marcador que .NET resuelve.

### Escenario 10: Las llamadas a herramienta que no caben vuelven como observación y no se ejecutan

- **Dado que** el modelo pide en una vuelta más herramientas de las que quedan en el presupuesto,
- **Cuando** se despacha esa vuelta,
- **Entonces** se ejecutan **las que caben, en el orden en que el modelo las emitió**,
- **Y** las restantes vuelven como observación fallida con la causa de presupuesto agotado,
- **Y** **ninguna** de ellas llega a tocar un puerto,
- **Y** el bucle termina tras esa vuelta marcando la respuesta como parcial.

### Escenario 11: La traza del cable dice qué se hizo, y no qué se preguntó

- **Dado que** una petición ha dado varias vueltas invocando herramientas,
- **Cuando** se lee la traza de la respuesta,
- **Entonces** trae, por iteración, **qué herramientas se invocaron, si tuvieron éxito y con qué
  causa si no**, más su coste y su latencia,
- **Y** **no** trae los argumentos con que se invocaron ni el contenido de las observaciones,
- **Y** la línea de log tampoco los trae,
- **Y** el arnés de evaluación sí puede leer la traza rica, en proceso, sin pasar por el cable.

### Escenario 12: Los dos números se entregan medidos, y no declarados

- **Dado que** el change declara un presupuesto de tokens y uno de reloj,
- **Cuando** se revisa lo entregado,
- **Entonces** ambos valores proceden de una **pasada con proveedor real** y no de un juicio de
  producto,
- **Y** se publican con su distribución —al menos p50 y p95—, nunca sólo la media,
- **Y** se publica la **curva de crecimiento del contexto por vuelta**,
- **Y** se publican las cifras de **los dos brazos de modelo** y el sobrecoste del agente **frente al
  pipeline**, que es el número que justifica o no la autonomía.

### Escenario 13: Las dos preguntas que C32a dejó abiertas se responden con datos

- **Dado que** la pasada de calibración ha terminado,
- **Cuando** se analizan sus trazas,
- **Entonces** se publica, por herramienta, **si alguna no fue elegida jamás**, si alguna acumuló
  fallos de argumento y si el modelo **inventó nombres de herramienta** —y cuáles—,
- **Y** se publica la **tasa de pivote a sustitutos por cada etiqueta de disponibilidad**,
  distinguiendo el pivote de más del pivote de menos,
- **Y** cada una de las dos preguntas queda **respondida con una cifra o declarada como limitación
  con su motivo**, nunca heredada en silencio a C38.

### Escenario 14: Fuera de alcance explícito — el pipeline determinista no se mueve

- **Dado que** este change añade una ruta y no modifica la existente,
- **Cuando** se compara el comportamiento de la asistencia de venta clásica antes y después,
- **Entonces** su forma de respuesta es **idéntica**, campo a campo,
- **Y** su techo de llamadas al proveedor sigue siendo el que C31 publicó,
- **Y** el movimiento del contrato es **adición pura**: ningún campo se retira ni cambia de tipo,
  verificado hoja a hoja y no supuesto,
- **Y** el golden set de C24 **no se ha usado** para calibrar ni para iterar ningún prompt.

---

## Notas adicionales

**Actor.** Desarrollador del proyecto. Esta historia es **habilitadora y de evaluación**: su ruta no
tiene consumidor en `backend/` ni pantalla en `frontend/`, y su valor se cobra en la ablación del
§11.4 y en la demostración del §16. El operario la notará el día que C34 y C36 decidan consumirla,
que no es este change.

**Encaje con los apuntes del máster.** *«El bucle agéntico paso a paso»* (S12) da la forma canónica
que esta historia sigue: registro que desacopla qué tools existen de cómo funciona el bucle,
ejecución **en paralelo** de las llamadas de una misma vuelta, el error de tool como **observación
recuperable**, la traza como único instrumento de depuración y la guarda de pasos como *«una factura
esperando a dispararse»* si falta. *«Cuánto cuesta un agente»* aporta las cuatro fuentes del
sobrecoste —más llamadas, **contexto que engorda vuelta a vuelta**, tokens de razonamiento y
exploración— y las tres cosas que hay que medir: **coste por paso**, **distribución y no media**, y
**comparación contra el pipeline**. La palanca que ese apunte pone primera —*«enruta: no mandes al
agente lo que un pipeline resuelve»*— **ya está aplicada por construcción**: la ruta separada de D-1
es ese enrutado, y conviene decirlo porque es la decisión de coste más importante del change.

**Dónde el apunte no se sigue, y por qué.** S12 encadena el estado con `previous_response_id` de la
Responses API de OpenAI. Esta capa sale por la costura de LiteLLM que C09, C30b y C31 ya usan, que es
de *chat completions*: **el contexto se reenvía explícitamente en cada vuelta**. No es un
inconveniente sino la condición que hace posible el presupuesto de caracteres de D-7 — se controla
lo que se reenvía porque se reenvía a mano.

**Limitaciones conocidas que se declaran y no se cierran.**

1. **El peor caso son 15-20 s síncronos**, que en un mostrador es mucho. No hay streaming ni
   respuesta en dos fases: la ruta separada evita que eso contamine el camino de 5 s de C34, y ahí
   acaba la mitigación.
2. **La ruta no tiene consumidor .NET.** Su política de *timeout* y de circuito queda identificada y
   no hecha.
3. **Los sets de esta historia no son de evaluación.** El de carga es sintético y no juzga calidad;
   el de calibración es pequeño y se declara *calibration-only*. Las cifras de calidad del agente son
   de C38.
4. **La compactación del contexto no se implementa**, sólo se mide su necesidad.
5. **El invariante de solo-lectura sigue cazando lo que puede cazar**, con los cuatro límites que
   C32a declaró. Esta historia no los estrecha.
6. **`style_similarity` sigue en cero para 403 de 404 productos reales** (C26), así que las
   observaciones de sustitutos heredan esa limitación. No es de aquí.

**Change de OpenSpec por el que se implementa.**
`openspec/changes/add-sales-assistant-agent-loop/`, rama `c32b-add-sales-assistant-agent-loop`.

---

## Tareas

1. **Puerta de entrada**: línea base de la suite de `ai-service` **por nombres de test** y no por
   recuento (`git stash push -u`, correr, `git stash pop`); `openspec validate --all --strict` en
   verde; y `sha256` de `ai-service/openapi.json` guardado **antes** de empezar.
2. **Constantes y vocabularios**: los seis presupuestos, las versiones de los dos prompts y la quinta
   causa `presupuesto_agotado`, en `assist/constants.py`, que **no importa nada** y debe seguir sin
   hacerlo.
3. **Puerto del agente y su adaptador**: tipo de retorno **sin campo de texto** (D-5), temperatura
   cero, sin `response_format`, `tools` desde `registry.schemas()`, *timeout* por llamada y cliente
   inyectable para que ningún test abra un socket.
4. **Transcripción**: modelo de turnos, topes de turnos, de caracteres por turno y **totales**, y
   delimitado `QUERY_OPEN`/`QUERY_CLOSE` **por turno**, reutilizando las marcas de C30b.
5. **El bucle**: decidir, ejecutar en paralelo con tope de 4 (D-8), observar, acumular, repetir; con
   sus seis guardas, la terminalidad de la repregunta (D-10) y el recorte de llamadas que no caben
   (D-9).
6. **Acumulador de evidencia** y su proyección al *payload* de generación, con sustitutos como grupo
   distinguido (D-12), **sin etiquetas de disponibilidad** (D-11) y con tope de piezas distintas, por
   la regla de C30b de que cada campo nuevo ensancha la lista blanca de numerales.
7. **Guardarraíl de entrada**: una clasificación sobre el turno que se contesta, con el rechazo
   cortocircuitando y el `index` descartado (D-4).
8. **Prompts**: `prompts/agent/v1.md` nuevo y `prompts/assist/v4.md` como v3 más la tarea de
   evidencia del agente, con **v3 intacto en disco** y el test que lo protege.
9. **Contrato**: `AgentAssistRequest` y `AgentAssistResponse` subclase (D-15), ruta
   `POST /v1/assist/agent` con su comportamiento bajo `STUB_MODE`, resolución de credencial con
   cadena y log de cuál ganó, y **regeneración de `openapi.json` verificada hoja a hoja**.
10. **Traza doble** (D-16): la acotada del cable y la rica en proceso, más la línea de log con
    agregados y **nunca argumentos**.
11. **Modificación de la capability viva `sales-assistant-tools`** para la quinta causa, más la delta
    de la capability del bucle —nueva o ampliación de `assist-generation`, a decidir en el
    `proposal`—, con `openspec validate --all --strict` en verde.
12. **Set de carga sintético** (~60-100 transcripciones) y **set de calibración a mano** (~15-20 con
    herramienta esperada por turno), los dos declarados por lo que son y **sin tocar el golden set**.
13. **Runner de la pasada** al modo de `evals/assist_sweep.py`: `--dry-run` con procedencia y tamaño,
    `--limit` para la prueba corta, política de bucle de eventos de Windows, y los **dos brazos de
    modelo** en la misma ejecución.
14. **Precondiciones de la pasada**: `SSL_CERT_FILE` apuntando a un PEM que incluya la raíz del
    interceptor TLS de la máquina —sin él toda llamada muere con `CERTIFICATE_VERIFY_FAILED`—, y una
    prueba de humo de tres transcripciones antes de la pasada larga.
15. **Análisis y fijación**: p50/p95 de tokens y de reloj, curva de crecimiento del contexto, coste
    por brazo, sobrecoste contra el pipeline, y las dos respuestas del escenario 13.
16. **Informe de implementación** con lo que la implementación refute de esta historia, siguiendo el
    patrón de los diez anteriores.
17. **Documentación**: `Documentos/epicas.md`, plan de changes, `ai-service/README.md`,
    `ai-service/tests/README.md`, `openspec/config.yaml`, `.env.example` y la ficha de C38 si el
    trabajo mueve algo de lo que ya lleva anotado.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **4/5** — no llega a pantalla, pero entrega **tres de las cuatro cosas que el PF evalúa de la capa agéntica** y la única fila de ablación que puede justificar el sobrecoste de la autonomía. Sin ella, C32a es un registro que nadie usa |
| Urgencia | **5/5** — **taponea a C38 y a C39**, que son el cierre del proyecto. El §6 del plan marca C32a y C32b como **«nunca se recortan»** |
| Complejidad / esfuerzo | **5/5** — el change más caro de los que quedan. Puerto nuevo, contrato que se mueve, seis presupuestos, dos prompts, dos sets de datos, una pasada con proveedor real de dos brazos y una capability viva que se modifica. Es también el primero desde C30a que **regenera `openapi.json`** |
| Riesgos | **Contaminación de la evaluación**: si el prompt se itera contra el golden set o contra escenarios de C38, la cifra del §11.4 nace inservible (mitigado por D-18 y el escenario 14). **La pasada falla por TLS** y se pierden 40 minutos en el minuto 38 (mitigado por la tarea 14). **El coste sale muy por encima de lo estimado**: el precedente de C30b midió **1,9×** su propia estimación, así que ~0,10 USD/petición y ~36× es un desenlace posible (mitigado porque los ×4 de modelo son reversibles con una variable). **El paralelismo se come el pool de 5** y un `pool_timeout` se lee como base de datos caída (mitigado por D-8). **El rechazo del clasificador sobre un turno elíptico** corta una conversación legítima: riesgo **declarado y no cerrado**, medible en C38. **El p95 no converge** con ~60-100 transcripciones y hay que ampliar el set |
| Dependencias | **C32a**, archivado el 2026-09-20, y con él **C30b** y **C31**. Consume además C14/C21/C25, C22, C23, C26 y C30a a través del registro. **Bloquea a C38 y a C39** |

---

## Preguntas Abiertas

| # | Pregunta | Opción por defecto si no hay respuesta antes del *apply* |
|---|---|---|
| **Q-1** | ¿El bucle nace capability propia o amplía `assist-generation`? | **Capability propia** `sales-assistant-agent`, por el mismo criterio con el que C32a se separó: `assist-generation` ya pasa de 40 requisitos y describe otra ruta. Se decide al redactar el `proposal` |
| **Q-2** | ¿La traza del cable es obligatoria o se activa con un parámetro de la petición? | **Siempre presente y acotada.** Un campo opcional que el arnés activa y el consumidor no crea dos formas de respuesta que hay que probar por separado |
| **Q-3** | ¿El set de carga se genera con el simulador de mundo sintético existente o con un guion propio? | **Guion propio** en `evals/agent/`, sembrado desde el vocabulario real del catálogo. Reutilizar el simulador arrastraría su modelo de mundo a un instrumento que sólo mide acumulación de tokens |
| **Q-4** | ¿El tope de caracteres del contexto es global o por sección (transcripción / observaciones)? | **Por sección y además global.** Un único tope global deja que una transcripción larga se coma el presupuesto de observaciones, que es donde está la evidencia |
| **Q-5** | ¿La pasada corre contra la base de datos de desarrollo o contra una copia congelada? | **La de desarrollo**, con la procedencia registrada (`git_sha`, recuento de índice, `run_id`), como hizo la pasada de C30b. Una copia congelada es más limpia y no existe |
| **Q-6** | ¿Cuántas iteraciones exactas separan «el modelo paró» de «el presupuesto cortó» en la traza? | **Se distinguen con un motivo de parada explícito** de vocabulario cerrado, no deduciéndolo del recuento: `sin_mas_herramientas`, `presupuesto_iteraciones`, `presupuesto_tools`, `presupuesto_tokens`, `presupuesto_reloj`, `aclaracion` |
| **Q-7** | ¿El brazo `gpt-4o-mini` corre sobre los dos sets o sólo sobre el de carga? | **Sobre los dos.** Si `mini` sostiene el coste pero no la selección de herramienta, hay que verlo en el set que tiene verdad de terreno |
