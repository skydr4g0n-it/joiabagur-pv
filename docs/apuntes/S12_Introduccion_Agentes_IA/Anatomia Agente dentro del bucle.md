# Anatomía de un agente: qué ocurre dentro del bucle

Creada: 7 de julio de 2026 10:32
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S12. Orquestación de Agentes (https://app.notion.com/p/S12-Orquestaci-n-de-Agentes-394ea9ca03c4809baf0bdfe714f24cc8?pvs=21)

Un agente, reducido a su forma más honesta, es un bucle: el modelo decide una acción, tu código la ejecuta, el resultado vuelve al modelo, y se repite hasta que hay respuesta. Eso es cierto, pero "un bucle" no te dice nada sobre lo que pasa dentro de cada vuelta. Y ahí es donde se gana o se pierde el control del sistema.

Este artículo abre una vuelta del bucle y le pone nombre a sus piezas: razonamiento, planificación, acción, observación, y el handover que permite al agente apartarse cuando toca. No es un ejercicio taxonómico. Nombrar las partes es exactamente lo que te permite depurar, medir el coste y decidir dónde intervenir. No puedes depurar lo que no sabes nombrar, y un agente sin anatomía es una caja negra que "a veces da mal la estimación".

Situemos el escenario, porque lo necesitamos para lo demás. Tenemos un sistema de estimación de proyectos software: recibe la transcripción de una reunión y produce una estimación estructurada. El agente dispone de herramientas —`search_budgets`, que recupera presupuestos históricos parecidos; `calculate_estimate`, que calcula costes a partir de referencias; `validate_estimate`, que aplica comprobaciones sobre el resultado— y su trabajo es orquestarlas cuando la transcripción es lo bastante compleja como para no tener una forma fija.

## **El esqueleto: reason, act, observe, repeat**

La formulación canónica de este bucle viene del trabajo de Yao y sus coautores sobre ReAct, en el que un modelo intercala trazas de razonamiento y acciones: el razonamiento le sirve para inducir, seguir y actualizar un plan y para manejar excepciones; las acciones le sirven para interactuar con fuentes externas y traer información nueva. La idea es que razonar y actuar por separado es peor que hacerlo entrelazado: el razonamiento sin acción se queda sin datos frescos y alucina; la acción sin razonamiento no sabe qué hacer con lo que trae.

En su forma original, ReAct era una técnica de *prompting*: escribías trayectorias de ejemplo con un formato explícito de texto.

```
Thought: The transcript describes two independent components; I will price them separately.
Action: search_budgets(query="ERP integration REST")
Observation: 4 historical budgets found; median 120h for a similar integration.
Thought: The migration component has no clear match; I need to reformulate.
Action: search_budgets(query="legacy data migration undocumented schema")
Observation: 1 weak match; low confidence.
```

Ese patrón —`Thought / Action / Observation`, en bucle, hasta una respuesta final— es el esqueleto. El resto del artículo son los órganos que cuelgan de él. Y hay un detalle de implementación que conviene adelantar, porque cambia cómo se construye hoy: con los modelos de razonamiento actuales, buena parte del `Thought` ya no la escribes tú en el prompt; ocurre de forma nativa dentro del modelo. Volveremos a ello.

Un esqueleto necesita, además, una condición de parada. Un bucle de agente sin guarda es un bug esperando a pasar: o el modelo da la respuesta final, o se alcanza un máximo de pasos, o se agota un presupuesto de error. Sin esa guarda, un agente confundido itera hasta consumir tu cuota. La condición de parada no es un detalle: es parte del esqueleto.

![S12-fig-02a-anatomia-bucle.jpg](https://media1-production-mightynetworks.imgix.net/asset/7f301404-994e-4bf2-a88d-ef8ffc4f0487/S12-fig-02a-anatomia-bucle.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Razonamiento: decidir qué hacer**

El razonamiento es la facultad de interpretar la situación y elegir la siguiente acción. Es donde el agente mira lo que tiene delante —la transcripción, lo que ha observado hasta ahora— y concluye algo como: "esto describe una integración con un ERP y una migración de datos legacy; son bestias distintas, las voy a estimar por separado".

Aquí está el matiz que separa el modelo mental de la implementación real. El patrón ReAct nació haciendo el razonamiento explícito en texto, y eso tenía una virtud: podías leerlo. Los modelos de razonamiento actuales hacen ese trabajo de forma nativa, gastando tokens internos de razonamiento que no escribes ni ves directamente. No desaparece el `Thought`; se muda dentro del modelo. Lo que te queda para observabilidad son los *reasoning summaries* que algunos proveedores exponen: resúmenes de la cadena de razonamiento, útiles para depurar y auditar sin tener que forzar el formato de texto a mano.

La consecuencia práctica es doble. Por un lado, ya no tienes que enseñarle al modelo a razonar con ejemplos de `Thought:`; lo hace solo, y a menudo mejor. Por otro, pierdes el control fino sobre esa traza: si necesitas auditabilidad estricta, tienes que capturar los resúmenes de razonamiento de forma deliberada, porque por defecto el razonamiento es opaco. No es una regresión ni un avance limpio; es un cambio en dónde vive el razonamiento y en qué palancas tienes sobre él.

## **Planificación: descomponer el problema**

Si el razonamiento decide el siguiente paso, la planificación decide la forma del conjunto: cómo se descompone el problema en pasos. En nuestro caso, planificar es leer la transcripción y concluir que hay cuatro componentes a estimar —portal de clientes, integración con el ERP, app móvil, migración legacy— y que cada uno merece su propia búsqueda de presupuestos.

Hay dos momentos en que puede ocurrir esa planificación, y merece la pena distinguirlos porque tienen implicaciones distintas. Uno es el plan por adelantado: el agente esboza los pasos al principio y luego los ejecuta. Otro es la planificación continua: el agente decide el siguiente paso en cada vuelta, a la luz de lo que acaba de observar. El plan por adelantado es más auditable —tienes el plan escrito antes de gastar— pero más rígido ante sorpresas; la planificación continua se adapta a lo que va encontrando pero es más difícil de anticipar y presupuestar.

Con modelos capaces, la planificación tiende a ser emergente más que un paso explícito: el modelo descompone sobre la marcha sin que tú le pidas un plan formal. Eso suele bastar. Pero nombrar la planificación como componente te da una palanca: cuando necesitas auditabilidad —justificar ante un cliente por qué la estimación salió como salió— puedes forzar un plan explícito como primer paso del bucle y guardarlo. La decisión de forzarlo o dejarlo emerger es tuya, y es una decisión de diseño, no un detalle del modelo.

## **Acción: tocar el mundo**

La acción es el único punto en el que el agente afecta a algo fuera de sí mismo. Todo lo demás —razonar, planificar, observar— ocurre en la cabeza del modelo o en tu gestión de estado. La acción es donde llama a `search_budgets` y de verdad pasa algo: se consulta la base de datos vectorial, se recuperan presupuestos.

Mecánicamente, esto es function calling, y su contrato es exactamente el de una interfaz tipada de toda la vida: tú declaras qué operaciones existen y qué forma tienen sus entradas y salidas; el modelo emite una petición estructurada; tu código la ejecuta y devuelve el resultado. El modelo nunca ejecuta nada por su cuenta. Emite una intención —"llama a `search_budgets` con estos argumentos"— y tú decides qué hacer con ella. Un ingeniero con experiencia en APIs integra esto igual que cualquier otra interfaz: define el esquema, maneja la llamada, devuelve el resultado. La diferencia es que quien llama, al otro lado, es un modelo que elige la función según la conversación.

Esa mediación tuya sobre la acción es donde vive la seguridad del agente, y conviene no regalarla. No todas las acciones son iguales. `search_budgets` es de solo lectura: reversible, barata de equivocarse, segura de conceder. Una acción que escribe en producción, envía un correo o mueve dinero es otra cosa. El principio es el de mínimo privilegio: das al agente las acciones que necesita y ni una más, y las acciones irreversibles pasan por una comprobación —o por un humano— antes de ejecutarse. Que el modelo pida una acción no te obliga a ejecutarla tal cual; puedes validar los argumentos antes, y debes hacerlo con las acciones que duelen.

## **Observación: leer la respuesta del entorno**

La observación es lo que devuelves al modelo tras ejecutar una acción, y es la forma en que el agente obtiene *ground truth* del entorno en cada paso. Sin observación, el modelo razona sobre su propia imaginación; con ella, corrige el rumbo a partir de hechos.

Lo que se subestima es hasta qué punto la calidad de la observación gobierna la calidad de la siguiente decisión. Una observación de alto valor —estructurada, concreta, con lo justo— alimenta un buen razonamiento. Una observación inflada —doscientos ítems de presupuesto en crudo cuando bastaban los cinco relevantes— desperdicia contexto y confunde al modelo. Devolver identificadores estables y semánticos, y solo los campos que el agente necesita para decidir el siguiente paso, no es cosmética: es lo que mantiene el bucle enfocado.

Los errores son un caso especial de observación, y probablemente el más importante. Cuando `search_budgets` no encuentra nada útil, eso *es* una observación, y una buena. Si se la devuelves al modelo con información —"1 coincidencia débil, baja confianza para migración legacy"— el agente puede razonar y reformular la consulta. Si se la devuelves como un genérico "error" o, peor, la ocultas, el agente se queda ciego y da tumbos. Un mensaje de error informativo devuelto como observación es lo que permite a un agente recuperarse de sus propios fallos; un error mudo es lo que lo hace fracasar de formas incomprensibles.

## **Handover: saber cuándo apartarse**

Un agente no siempre debe terminar el trabajo él solo. El handover es la transferencia de control a otra parte, y tiene dos direcciones.

La primera es hacia un humano. Es el patrón de *human in the loop*: el agente se detiene en un punto de control y pide criterio, o escala cuando su confianza es baja o cuando la siguiente acción es cara e irreversible. En nuestro sistema, imagina que el componente de migración legacy no tiene ninguna referencia histórica fiable —schema no documentado, nada parecido en el histórico de presupuestos—. El agente puede estimar el resto con solvencia y, para esa pieza, apartarse: marcar la estimación como necesitada de revisión humana en lugar de inventarse un número con falsa precisión. Eso no es un fallo del agente; es un agente bien diseñado reconociendo el límite de lo que puede verificar.

La segunda dirección es hacia otro agente: delegar una sub-tarea a un especialista mejor equipado para ella. En sistemas de un solo agente esto no aparece, pero es la base sobre la que se construyen las arquitecturas de varios agentes.

En ambos casos, el handover necesita un contrato explícito: qué estado se transfiere, quién pasa a ser dueño de la decisión, y cómo vuelve el control (si es que vuelve). Un handover sin contrato es una pelota que se lanza al aire sin que nadie sepa que tiene que recogerla.

Aquí es donde la anatomía del agente se cruza con la arquitectura del sistema. El agente vive dentro del **servicio IA**, y el handover hacia un humano se traduce limpiamente en un contrato: el servicio IA devuelve un estado —por ejemplo, `needs_review`— junto con lo que sí ha podido calcular y la razón. El **backend de negocio** enruta ese estado hacia una persona. Desde el lado cliente, en la implementación de referencia en Rails, eso es tan simple como esto (el patrón es independiente del stack: cualquier cliente HTTP sirve):

```ruby
# backend de negocio: routing the servicio IA response
result = ai_service.estimate(transcript)

case result.status
when "done"
  save_estimate(result.estimate)
when "needs_review"
  enqueue_for_human_review(result.partial_estimate, result.reason)
end
```

![S12-fig-02b-handover-capas.jpg](https://media1-production-mightynetworks.imgix.net/asset/1a49dfb9-468b-4791-b403-6021f229583c/S12-fig-02b-handover-capas.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El handover deja de ser un concepto abstracto y se convierte en un `status` en una respuesta y un `case` que lo enruta. Software normal.

## **La anatomía, desde el punto de vista del código**

Puestas todas las piezas, una vuelta del bucle se lee así. Es un esquema, no una API concreta, pero cada línea es un órgano:

```python
def run_agent(transcript: str) -> AgentResult:
    state = build_initial_state(transcript)          # the accumulating context
    for step in range(MAX_STEPS):
        decision = model.decide(state)               # reasoning + planning
        if decision.needs_human:                     # handover to a person
            return AgentResult(status="needs_review", state=state)
        if decision.is_final:                        # stopping condition
            return AgentResult(status="done", estimate=decision.estimate)
        observation = execute_tool(decision.action)  # action + observation
        state.append(decision, observation)          # the loop carries the trace
    return AgentResult(status="max_steps_exceeded", state=state)
```

Fíjate en el estado. El bucle no es memoria pura del modelo: es una estructura que tú mantienes y que crece en cada vuelta con la decisión y su observación. Ese estado acumulado es la traza del agente —el `Thought / Action / Observation` en bucle— y es lo que puedes loguear, inspeccionar y usar para depurar. Cada órgano tiene su línea: el razonamiento y la planificación viven en `model.decide`; la acción y la observación, en `execute_tool` y su resultado; el handover, en la rama `needs_human`; la parada, en `is_final` y en el `range(MAX_STEPS)` que la envuelve. Todo dentro del servicio IA. El backend de negocio solo ve el `AgentResult` final y su `status`.

Ese estado que crece tiene un coste que conviene no perder de vista, porque es la contrapartida directa de la anatomía. Cada vuelta añade la decisión y la observación al contexto, y ese contexto se reenvía al modelo en la vuelta siguiente. Es decir: el bucle no solo hace más llamadas, sino que cada llamada es más cara que la anterior, porque arrastra todo lo observado hasta el momento. Un agente que da ocho vueltas sobre una transcripción compleja está pagando, en la octava, por reenviar las siete observaciones previas. Nombrar el estado como órgano es también reconocer que engorda, y que en agentes largos acabas necesitando estrategias para adelgazarlo —resumir observaciones antiguas, descartar las que ya no informan la decisión, quedarte con el identificador en lugar del contenido completo—. No es una optimización prematura: es la consecuencia estructural de un bucle que acumula, y saberlo desde el principio evita la sorpresa en la factura.

## **Cierre: la anatomía desmitifica**

Nombra las partes y el agente deja de ser un misterio. El razonamiento es lógica de decisión, solo que ahora vive dentro del modelo en lugar de en tus `if/else`. La planificación es descomposición de un problema, algo que haces cada vez que diseñas una función. La acción es una llamada a función con efectos. La observación es un valor de retorno que vuelves a meter en el flujo. El handover es escalado y delegación, un patrón de cualquier sistema de trabajo serio. Y el bucle es control de flujo con una guarda, como cualquier `while` que hayas escrito con cuidado.

Esa es la utilidad real de la anatomía: no es teoría, es lo que te deja instrumentar el sistema. Puedes medir cuántos pasos tarda, testear cada órgano por separado dar una observación fija y comprobar la decisión, ejecutar una acción con argumentos conocidos y verificar el resultado, y poner límites donde duelen. Un agente cuyos órganos sabes nombrar es un sistema que puedes operar. Uno cuyos órganos no distingues es una caja negra a la que solo puedes rezarle.

## **Fuentes**

- Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* (ICLR 2023), arXiv 2210.03629 — el ciclo de razonamiento y acción entrelazados: [https://arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629)
- Anthropic, *Building Effective Agents* — el agente que obtiene *ground truth* del entorno en cada paso y se detiene para pedir criterio humano en los puntos de control: [https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)
- Anthropic, *How tool use works* — la acción como contrato tipado y el bucle gobernado por una condición de parada: [https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)