# De pipeline a agente: cuándo tu sistema RAG necesita una capa de decisión

Creada: 5 de julio de 2026 12:21
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S12. Orquestación de Agentes (https://app.notion.com/p/S12-Orquestaci-n-de-Agentes-394ea9ca03c4809baf0bdfe714f24cc8?pvs=21)

Nuestro sistema de estimación funciona. Le pasas una transcripción de reunión, reformula la consulta, recupera presupuestos históricos parecidos, y genera una estimación estructurada. Es un pipeline fijo: tres pasos, siempre los mismos, siempre en el mismo orden. Es predecible, se testea con facilidad, cuesta poco y falla de formas que sabes anticipar.

Con ese punto de partida, la pregunta interesante no es "cómo construyo un agente". Es "por qué querría hacerlo". Porque un agente no es una mejora gratuita del pipeline. Es una decisión arquitectónica con un coste concreto, y la mayoría de las veces la respuesta correcta es no añadirlo. Este artículo trata de cuándo sí.

## **El pipeline que ya funciona**

Conviene ser honestos sobre lo bueno que es un pipeline fijo, porque el marketing de agentes tiende a hacernos olvidarlo.

Un pipeline es una secuencia de pasos que tú escribes. En nuestro caso:

```python
def estimate_from_transcript(transcript: str) -> Estimate:
    query = reformulate(transcript)
    budgets = search_budgets(query)
    return generate_estimate(transcript, budgets)
```

El control de flujo es tuyo. Tú decidiste que primero se reformula, después se busca y por último se genera. El modelo rellena cada hueco, pero no decide la estructura. Y eso tiene consecuencias muy deseables:

- **Es predecible.** La misma entrada recorre siempre el mismo camino. Si algo falla, sabes en qué paso.
- **Es barato.** Sabes exactamente cuántas llamadas al LLM haces por petición. El coste no explora, no se dispara.
- **Es testeable.** Puedes probar cada paso por separado con entradas conocidas y aserciones deterministas.
- **Es rápido.** No hay idas y vueltas de negociación con el modelo sobre qué hacer a continuación.

Para una parte enorme de los problemas reales, esto es todo lo que necesitas. Una tarea de clasificación, una extracción de campos, una única recuperación seguida de una generación: nada de eso requiere que el modelo tome el timón. Añadir agencia ahí es meter no-determinismo, latencia y coste a cambio de nada.

Así que el pipeline es el estado por defecto. La pregunta es qué tiene que romperse para justificar salir de él.

## **El punto en el que el pipeline se rompe**

Toma dos transcripciones.

La primera dice, en esencia: *"Necesitamos una landing page con un formulario de contacto y despliegue en un hosting sencillo."* Un componente, una búsqueda de presupuestos parecidos, una estimación. El pipeline lo clava. No hay decisión que tomar: la forma del problema es fija y tú ya la codificaste.

La segunda es una reunión de kickoff de un proyecto real: un portal de clientes con su capa de negocio, una integración con el ERP del cliente vía API, una app móvil que consume ese portal, y una migración de datos de un sistema legacy que "nadie sabe muy bien cómo está montado". Aquí el pipeline fijo empieza a crujir, y merece la pena ver exactamente por qué.

El problema no tiene una forma conocida de antemano. No sabes cuántos componentes hay hasta que lees la transcripción. No sabes cuántas búsquedas de presupuestos necesitas ni sobre qué. La integración con el ERP y la migración legacy son bestias muy distintas y buscarlas con una única consulta reformulada te devuelve una mezcla inútil. Tampoco sabes en qué orden conviene atacarlas, ni si el resultado de estimar la migración cambia cómo estimas la integración.

Tienes dos malas salidas dentro del paradigma del pipeline. Una: lanzar una sola búsqueda gigante y pedirle al generador que se apañe con un revoltijo de presupuestos que mezclan cosas incomparables. La calidad se hunde. Dos: codificar a mano un árbol de decisiones "si hay integración, haz esta rama; si hay migración, esta otra" que tienes que mantener para cada forma de proyecto que aparezca. Eso no escala: cada cliente trae una combinación nueva.

Lo que falta no es más recuperación ni mejor generación. Es **capacidad de decisión en tiempo de ejecución**: alguien que lea la transcripción, decida que hay cuatro componentes, busque presupuestos para cada uno por separado, calcule estimaciones parciales y las consolide. Un camino que se construye según el caso, no uno que escribiste tú por adelantado.

![S12-fig-01-pipeline-vs-agente.jpg](https://media1-production-mightynetworks.imgix.net/asset/a178d237-27b8-42a9-b36b-88a746cdc1c3/S12-fig-01-pipeline-vs-agente.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Tres niveles: tarea, workflow y agente**

Ayuda tener un vocabulario preciso, porque "agente" se usa para casi todo. Anthropic, en su guía sobre construcción de agentes efectivos, y Barry Zhang, de su equipo de agentes, proponen una escala de tres niveles que resulta muy útil para decidir.

**Tarea.** Una única llamada al modelo. Resume esto, clasifica aquello, extrae estos campos. Hace dos años esto parecía magia; hoy es la base sobre la que se construye todo. El coste es predecible y los modos de fallo están acotados.

**Workflow.** Varias llamadas al modelo encadenadas en un flujo de control que tú defines. Reformular, recuperar y generar es un workflow. Tú escribes los pasos; el modelo los rellena. Aquí vive la mayor parte de un sistema RAG bien hecho, y está bien que así sea.

**Agente.** El modelo dirige su propio proceso. Decide la siguiente acción a partir de lo que observa en el entorno el resultado de una búsqueda, la salida de un cálculo y sigue hasta que considera que ha terminado. Tú posees el objetivo y las barreras de seguridad; no posees cada rama del camino.

La frase que mejor lo resume es de Zhang: con un workflow, la fontanería la controlas tú; con un agente, la fontanería la controla el modelo. Todo lo demás el coste, la latencia, la testabilidad, la observabilidad se deriva de esa única diferencia estructural.

Verlo desde el código lo deja claro. Un workflow es la función de antes: la secuencia está escrita. Un agente es, en su forma más honesta, un bucle:

```python
def run_agent(transcript: str) -> Estimate:
    messages = build_initial_context(transcript)
    for _ in range(MAX_STEPS):
        decision = model.decide(messages, tools=TOOLS)
        if decision.is_final():
            return decision.estimate
        observation = execute_tool(decision.tool_call)
        messages.append(observation)
    raise AgentDidNotConverge()
```

(Es un esquema, no una API real.) La diferencia con el workflow no es el bucle en sí los bucles no tienen nada de novedoso. Es la línea `model.decide`: quién elige el siguiente paso. En el workflow lo elegiste tú al escribir la secuencia. En el agente lo elige el modelo en cada vuelta, en función de lo que acaba de observar. Esa es toda la novedad. El resto es control de flujo que reconoces de cualquier programa que hayas escrito.

## **Qué compra realmente un agente**

Lo que compras con un agente es una sola cosa: **la capacidad de resolver problemas cuyo árbol de decisión no puedes pre-mapear.**

En nuestro sistema de estimación, eso se traduce en algo concreto. El agente lee la transcripción del proyecto complejo, decide que hay cuatro componentes con perfiles distintos, y trata cada uno como una sub-tarea: busca presupuestos históricos para la integración con el ERP por un lado, para la migración legacy por otro, calcula estimaciones parciales con las referencias adecuadas, y consolida. Cuando una búsqueda devuelve poco o nada relevante, puede reformular y volver a intentarlo antes de calcular sobre datos malos. Ese camino cuatro búsquedas, dos reintentos, un cálculo por componente, una consolidación no lo escribiste tú. Lo construyó el modelo al vuelo, a partir del contenido de esa transcripción concreta.

Fíjate en lo que **no** compras. No compras mejor recuperación: el agente busca con las mismas herramientas de siempre. No compras mejor generación: consolida con el mismo modelo. No compras inteligencia nueva. Compras exclusivamente orquestación adaptativa. Si tu problema tiene una forma fija, no hay nada aquí para ti, porque la orquestación fija ya la tenías resuelta y más barata.

## **El precio de la autonomía**

Aquí es donde el marketing suele callarse. Un agente paga por su flexibilidad, y el precio no es pequeño.

**Latencia.** Cada vuelta del bucle es una ida y vuelta al modelo. El pipeline hacía una o dos llamadas; el agente puede hacer ocho antes de converger. El usuario que esperaba dos segundos ahora espera veinte.

**Coste.** La exploración cuesta tokens. Como regla mental, Zhang sugiere que unos diez céntimos de dólar por tarea equivalen a entre treinta mil y cincuenta mil tokens. Un agente que razona, busca cuatro veces y consolida se come ese presupuesto con facilidad, y multiplica por varias veces lo que costaba el pipeline. A escala, la diferencia deja de ser anecdótica: una operación que procesa un millón de peticiones al mes gastando cinco veces los tokens necesarios quema del orden de un millón y medio de dólares al año de más. Que sea razonable depende por completo del valor de cada tarea.

**No-determinismo.** La misma transcripción puede recorrer caminos distintos en dos ejecuciones. Eso complica el testing ya no basta con comprobar la salida contra un valor esperado y hace que reproducir un bug sea un ejercicio de paciencia.

**Los errores se componen.** En un pipeline, una recuperación mala produce una respuesta mala: un fallo, acotado. En un agente, una recuperación mala en el paso dos puede convertirse en tres pasos más construidos sobre esa base podrida. Cada iteración multiplica la tasa de fallo del eslabón más débil. La autonomía amplifica tanto los aciertos como los errores.

**Deuda de observabilidad.** Con un pipeline te bastaba con loguear entradas y salidas. Con un agente necesitas trazar decisiones: qué razonó, qué herramienta eligió, qué observó, por qué siguió. Sin esa traza, depurar un agente que "a veces da mal la estimación" es casi imposible.

Ninguno de estos costes es un argumento para no usar agentes nunca. Son el precio que pagas, y la decisión sensata consiste en comprobar que lo que compras vale más que lo que pagas.

## **Los criterios de decisión**

Traducido a preguntas que puedes hacerte delante de un problema concreto:

**¿Puedes pre-mapear el árbol de decisión?** Si puedes enumerar los pasos y sus ramas, constrúyelo como workflow. Tendrás más precisión, más control y menos coste que cualquier agente. Que puedas mapearlo es la señal más fuerte de que no necesitas agencia.

**¿El problema tiene forma variable?** Si el número de pasos, su orden o su naturaleza dependen de la entrada de maneras que no puedes enumerar por adelantado, entras en territorio de agente. La transcripción compleja lo es; la landing page no.

**¿El valor justifica el gasto?** La exploración cuesta dinero. Una tarea de alto volumen y bajo valor por unidad —clasificar millones de tickets— es territorio de workflow, casi siempre. Una tarea de bajo volumen y alto valor, estimar un proyecto de seis cifras puede justificar de sobra el sobrecoste de un agente.

**¿Cuál es el coste del error, y puedes verificarlo?** Si un error es caro y difícil de detectar, la autonomía se vuelve un pasivo. Aquí es donde las mitigaciones importan: herramientas de solo lectura, validación automática de la salida antes de darla por buena, y un humano en el bucle en los puntos críticos. Un agente cuyas acciones son todas reversibles y verificables es mucho menos arriesgado que uno que escribe en producción.

**¿El modelo es lo bastante bueno en tu dominio?** Si el modelo no razona de forma fiable sobre presupuestos de software, ni se recupera de sus propios errores, no le des el volante. La agencia sobre un modelo que no domina el dominio solo produce fallos más elaborados.

Hay un caso de agente que funciona bien hoy y que ilustra los criterios a la perfección: los agentes de código. El problema es ambiguo (no hay un camino fijo para resolver un bug), el valor de la salida es obvio, los modelos actuales son buenos en ello, y clave el resultado se puede verificar con tests. Cuando tu problema cumple esas cuatro condiciones, el agente se gana su sitio. Cuando no, sospecha.

## **Cómo se aplica a nuestro sistema de estimación**

Aquí toca mojarse, porque la conclusión no es "reemplaza el pipeline por un agente".

El pipeline sigue siendo el camino por defecto. Las transcripciones simples que son la mayoría lo recorren tal cual: más rápido, más barato, determinista. No hay ninguna razón para pagar el impuesto de la agencia en un problema que ya tiene forma fija.

El agente entra como **una capa de decisión por encima del pipeline, no como su sustituto.** Y el detalle que hace que esto sea limpio en lugar de un rediseño es que las piezas del pipeline se convierten en las herramientas del agente. La recuperación de presupuestos que ya tenías pasa a ser una tool, `search_budgets`. El cálculo de costes pasa a ser otra, `calculate_estimate`. La validación de la salida, `validate_estimate`. No reimplementas nada: promocionas los pasos del workflow a acciones invocables y dejas que el modelo las secuencie cuando la forma del problema es desconocida. Para las transcripciones complejas, el agente orquesta exactamente las mismas primitivas que el pipeline ejecutaba en orden fijo.

Esto sugiere una arquitectura de dos vías con un enrutado barato al principio: un clasificador ligero decide si la transcripción es simple al pipeline o compleja al agente. Así pagas la autonomía solo cuando el problema la exige, y mantienes el coste medio bajo control.

Un punto que no conviene difuminar: todo esto vive dentro del **servicio IA**. Es un detalle interno suyo. El **backend de negocio** sigue enviando una transcripción y recibiendo una estimación estructurada por el mismo contrato de siempre; le da igual si detrás la produjo un pipeline de tres pasos o un agente que hizo ocho llamadas. Esa separación es lo que te permite introducir el agente sin tocar la capa de negocio ni el frontend, y lo que te dejará quitarlo o cambiarlo mañana si el coste no compensa. La agencia es una decisión de implementación del servicio IA, no un cambio de arquitectura del producto.

## **El agente, desde el punto de vista del código**

Si has llegado hasta aquí, la conclusión debería sonar casi decepcionante, y esa es exactamente la idea.

Un agente no es un paradigma nuevo que jubila tu ingeniería de software. Es una decisión de control de flujo. En lugar de escribir tú el `if/else` que elige el siguiente paso, el modelo emite la siguiente acción y tú la ejecutas en un bucle. Eso es la novedad, y está acotada. Todo lo que rodea a esa línea las herramientas y sus contratos, la validación de las salidas, la observabilidad de las decisiones, el control de coste y de latencia, la condición de parada para que el bucle no se vaya de las manos es ingeniería que ya sabes hacer. Diseño de interfaces, manejo de errores, límites y timeouts, trazabilidad. Nada de eso es específico de la IA.

Por eso la parte difícil de trabajar con agentes no es construirlos. El bucle son veinte líneas. La parte difícil es decidir si de verdad necesitabas uno, y resistir la tentación de meterlo donde un workflow habría hecho el trabajo mejor, más barato y con menos sorpresas. Empieza siempre por la solución más simple que pase tus pruebas. Sube un escalón de tarea a workflow, de workflow a agente solo cuando la forma del problema te obligue. Por defecto, el pipeline. El agente, cuando no te quede otra.

## **Fuentes**

- Anthropic, *Building Effective Agents* — distinción entre workflows y agentes, y la recomendación de empezar por la solución más simple: [https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)
- Barry Zhang (Anthropic), *How We Build Effective Agents* — la taxonomía tarea / workflow / agente y la matemática de coste, sintetizada en: [https://shellypalmer.com/2026/04/how-anthropic-thinks-about-agents-workflows-and-tasks/](https://shellypalmer.com/2026/04/how-anthropic-thinks-about-agents-workflows-and-tasks/)
- OpenAI, *Function calling* (Responses API) — mecánica de tools y del bucle de ejecución: [https://developers.openai.com/api/docs/guides/function-calling](https://developers.openai.com/api/docs/guides/function-calling)