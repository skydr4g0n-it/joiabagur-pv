# Patrones de agentes y diseño de tools de calidad

Creada: 7 de julio de 2026 11:06
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S12. Orquestación de Agentes (https://app.notion.com/p/S12-Orquestaci-n-de-Agentes-394ea9ca03c4809baf0bdfe714f24cc8?pvs=21)

"Agente" no es una cosa. Bajo esa palabra caben formas muy distintas de resolver un problema, y elegir la forma correcta para el tuyo importa tanto como saber escribir el bucle. Un agente que da un solo paso y otro que itera veinte veces son animales diferentes, con costes, riesgos y modos de fallo diferentes.

Este artículo tiene dos mitades que se necesitan. La primera es sobre **la forma del agente**: los ejes por los que un agente se diferencia de otro, y cómo elegir. La segunda es sobre **la palanca que dirige su comportamiento dentro de esa forma**: el diseño de las tools. Porque una vez fijada la forma, lo que el agente hace bien o mal depende, en una medida que sorprende, de cómo describes sus herramientas.

Antes de empezar, el terreno. Trabajamos con un agente de estimación: recibe la transcripción de una reunión, y con tres tools `search_budgets` (recupera presupuestos históricos), `calculate_estimate` (calcula costes), `validate_estimate` (comprueba el resultado) produce una estimación de proyecto. Sobre ese caso concreto veremos cómo cambian las cosas.

## **Un solo paso o iterativo**

El primer eje es el más básico: ¿cuántas vueltas da el agente?

Un **agente de un solo paso** hace una llamada, quizá usa una tool, y termina. No hay bucle real: es casi un pipeline con una decisión. Para una transcripción simple —"una landing con formulario de contacto" esto basta y sobra: una búsqueda de presupuestos, un cálculo, listo. Barato, rápido, predecible.

Un **agente iterativo** repite el ciclo de decidir, actuar y observar hasta converger. Es lo que necesitas cuando el problema no cabe en un solo paso: una transcripción con cuatro componentes exige buscar por separado, quizá reformular alguna búsqueda que vino pobre, calcular parciales y consolidar. Cada vuelta añade capacidad de adaptación, pero también latencia, coste y una superficie de fallo mayor.

La decisión no es filosófica: es de coste contra necesidad. Si puedes resolver el problema en un paso, hazlo en un paso. La iteración es una herramienta para problemas cuya forma no conoces de antemano, no un valor por defecto. Un error común es montar un bucle iterativo para tareas que un solo paso resolvería mejor y más barato, y descubrirlo solo cuando llega la factura.

## **Reactivo o proactivo**

El segundo eje es cómo el agente se relaciona con el futuro.

Un **agente reactivo** decide el siguiente paso a la luz de lo que acaba de observar, sin un plan hacia adelante. Busca presupuestos, ve el resultado, y solo entonces decide qué hacer a continuación. Es simple y sorprendentemente robusto: como no se compromete con un plan, no se rompe cuando la realidad no encaja con él. Su debilidad es que puede ser miope, tomando decisiones localmente buenas que no componen un buen conjunto.

Un **agente proactivo** anticipa: se forma una idea del objetivo y actúa hacia él, no solo en respuesta al último estímulo. Ante la transcripción, un agente proactivo puede razonar "voy a necesitar estimar cuatro componentes, así que buscaré presupuestos para los cuatro" antes de haber visto ningún resultado. Es más eficiente cuando el camino es predecible, porque no descubre el trabajo sobre la marcha. Es más frágil cuando no lo es, porque un plan formado demasiado pronto puede quedar desmentido por la primera observación.

Para nuestro caso, la reactividad suele ganar. Las transcripciones traen sorpresas un componente que resulta ser dos, una migración sin referencias históricas y un agente que decide paso a paso las absorbe mejor que uno casado con un plan prematuro. Pero no es absoluto: una pizca de proactividad, la de descomponer el proyecto en componentes al principio, ahorra vueltas sin comprometerte con un camino rígido.

## **Plan fijo o planificación dinámica**

El tercer eje afina el anterior: si hay plan, ¿cuándo se decide?

Con un **plan fijo**, el agente descompone el problema al principio y luego ejecuta ese plan hasta el final. Su gran virtud es la auditabilidad: tienes el plan escrito antes de gastar un token, y puedes justificar después por qué se hizo lo que se hizo. En una estimación que vas a defender ante un cliente, poder mostrar "el agente decidió estimar estos cuatro componentes, en este orden, por estas razones" tiene valor real.

Con **planificación dinámica**, el agente re-planifica en cada vuelta según lo que observa. Es lo que le permite reaccionar: si una búsqueda de presupuestos vuelve vacía, replantea y busca de otra forma antes de calcular sobre datos malos. Gana en adaptabilidad lo que pierde en previsibilidad.

Un apunte honesto: estos tres ejes no son ortogonales. Un agente proactivo tiende al plan fijo; uno reactivo, a la planificación dinámica. No son tres tipos que eliges de un catálogo, sino tres lentes para pensar la misma decisión de diseño, y los agentes reales mezclan posiciones en cada eje. Lo útil no es clasificar tu agente en una casilla, sino ser consciente de dónde lo estás colocando y por qué.

Puestos a mojarnos con el agente de estimación: iterativo, mayoritariamente reactivo, con una planificación ligera y dinámica una descomposición inicial floja en componentes, revisada sobre la marcha cuando una observación lo pide. Esa combinación absorbe la variabilidad de las transcripciones sin pagar el coste de un bucle innecesario ni la fragilidad de un plan rígido. No es la única elección defendible, pero es la que mejor encaja con la naturaleza del problema, y saber articular por qué es media batalla.

![S12-fig-05a-ejes-de-patrones.jpg](https://media1-production-mightynetworks.imgix.net/asset/583acefb-79e2-4097-b38c-53d706c8cae7/S12-fig-05a-ejes-de-patrones.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Enrutar la forma según el caso**

Hay una decisión que precede a todas las anteriores y que a menudo se pasa por alto: no tienes que elegir una sola forma para todas las entradas. Puedes elegir la forma por caso.

En producción, la mayoría de las transcripciones son simples y solo unas pocas son complejas. Comprometerte con el agente iterativo para todas significa pagar su coste y su latencia también en los casos que un solo paso resolvería mejor. La alternativa es enrutar: una clasificación barata al principio decide si la transcripción es simple y va al camino de un solo paso o compleja y va al agente iterativo. Así pagas la iteración solo cuando el problema la exige, y el coste medio del sistema se mantiene bajo.

Esto reencuadra la elección de patrón de forma útil. La pregunta deja de ser "qué forma tiene mi agente" y pasa a ser "qué forma merece cada entrada". El enrutado en sí es un paso barato y determinista, y su valor es que te deja quedarte con lo mejor de cada forma sin pagar el peor caso en cada petición. Es, otra vez, ingeniería corriente: mides la distribución real de tus entradas, diseñas para el caso común, y dejas una vía para el caso difícil. La forma del agente no tiene por qué ser una constante del sistema; puede ser una decisión que se toma por petición.

## **Las tools son la interfaz que dirige al agente**

Fijada la forma, ¿qué determina que el agente decida bien dentro de ella? Casi por completo, las tools: cuáles existen y cómo las describes. El modelo elige qué hacer leyendo los nombres, las descripciones y los schemas de las herramientas que le das. No lee tu código ni tu intención; lee esas frases. Por eso el diseño de tools no es documentación: es dirección de comportamiento.

De aquí sale un principio que ahorra muchísimo tiempo de depuración. Cuando el agente se comporta mal elige la tool equivocada, inventa argumentos raros, mete cuatro componentes en una búsqueda que debía ser de uno, o llama a las cosas en un orden absurdo el instinto es culpar al modelo o retocar el bucle. Casi siempre es un error. **El fallo suele estar en la descripción de una tool o en el conjunto de tools, y ahí está también el arreglo.** El modelo hizo lo que tus descripciones le dijeron; si te sorprende lo que hizo, es que las descripciones decían algo distinto de lo que creías.

## **La descripción es un prompt que se itera**

La consecuencia práctica es que las descripciones de tools se tratan como prompts: se escriben, se prueban, se observan los resultados y se ajustan. No se acierta a la primera, y no pasa nada.

Míralo con `search_budgets`. Una primera versión ingenua:

```python
{
		"name":"search_budgets",
		"description":"Searches historical budgets.",
		# ...
}
```

Con esto, el agente no tiene forma de saber que debe buscar un componente cada vez. Ante una transcripción con una integración y una migración, es probable que lance una única búsqueda con ambas mezcladas y reciba resultados incomparables. No es culpa del modelo: la descripción no le dijo otra cosa.

La versión que arregla el comportamiento lleva la restricción, el contraejemplo y la razón dentro de la propia descripción:

```python
{
    "name": "search_budgets",
    "description": (
        "Search historical budgets for ONE software component at a time. "
        "Call this separately for each component in the project; never combine "
        "unrelated components (for example, an ERP integration and a data "
        "migration) in a single query, because mixed results cannot be "
        "compared. Returns comparable historical items with their hours and a "
        "confidence signal."
    ),
    # ...
}
```

La diferencia entre las dos no es cosmética: es la diferencia entre un agente que estima bien y uno que produce números sin sentido, y vive enteramente en un campo de texto. Una descripción efectiva le dice al modelo cuándo usar la tool, cuándo no, con qué granularidad, y qué va a recibir de vuelta. Ese es el trabajo, y es donde se gana la fiabilidad no en un modelo más caro.

![S12-fig-05b-descripcion-palanca.jpg](https://media1-production-mightynetworks.imgix.net/asset/1fa46bf1-367d-42fe-924a-71b1f6847647/S12-fig-05b-descripcion-palanca.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **El conjunto de tools, no solo cada tool**

Hay una capa de diseño por encima de cada descripción: la del conjunto. El modelo no elige una tool en el vacío, sino entre todas las que le ofreces, y la relación entre ellas afecta a la calidad de la elección.

Demasiadas tools con fronteras solapadas confunden: si dos herramientas podrían servir para lo mismo, el modelo duda y a veces escoge mal. Muy pocas y demasiado genéricas fuerzan al modelo a hacer malabares con los argumentos para expresar lo que quiere. El punto dulce es un conjunto pequeño de tools con fronteras nítidas: `search_budgets` busca, `calculate_estimate` calcula, `validate_estimate` valida, y ninguna invade el terreno de otra. Cuando el conjunto de tools crece, los nombres con espacio de nombres `budgets_search`, `estimate_calculate` ayudan al modelo a agrupar y desambiguar.

Una señal de alarma útil: si te descubres explicando en la descripción de una tool cuándo *no* usarla en favor de otra, probablemente las fronteras entre ambas están mal trazadas. El arreglo no es una descripción más larga, sino un conjunto de tools mejor delimitado.

## **Optimizar es mirar las trazas**

¿Cómo se hace todo esto en la práctica, sin adivinar? Empíricamente, mirando lo que el agente hace de verdad.

El método es directo. Coges un puñado de transcripciones representativas simples, complejas, con casos raros, ejecutas el agente sobre ellas, y lees las trazas: qué tool eligió en cada paso, con qué argumentos, en qué orden, dónde se atascó o falló. Cada comportamiento anómalo tiene una causa que puedes rastrear hasta una descripción vaga, una frontera mal puesta entre dos tools, un resultado que devolvía demasiado ruido, o un error mudo que dejó al agente ciego. Arreglas la causa, vuelves a ejecutar, y compruebas que la traza mejora sin romper los otros casos.

Un ejemplo del tipo de hallazgo que aparece. Supón que, al leer trazas, ves que el agente llama a `calculate_estimate` antes de haber buscado presupuestos para todos los componentes, produciendo estimaciones parciales sobre datos incompletos. El instinto es pensar que el modelo "se precipita". Pero la causa está en la descripción de `calculate_estimate`, que no declara su precondición: que espera recibir todos los componentes con sus referencias ya recuperadas. Añades esa precondición a la descripción "only call this after budgets have been searched for every component" y el comportamiento se corrige. No tocaste el modelo ni el bucle; ajustaste una frase. Ese es el bucle de mejora, y la mayoría de los arreglos tienen exactamente esa forma.

Esto tiene una implicación de diseño que conviene tener presente desde el principio: la calidad de tus trazas determina tu capacidad de optimizar. Un agente que registra acción, argumentos y observación en cada paso es un agente que puedes mejorar; uno que solo devuelve el resultado final es una caja negra a la que solo puedes cambiarle el modelo y rezar. Y lo que devuelve cada tool es parte de esto: resultados de alto valor lo justo para decidir el siguiente paso, con identificadores estables producen buenas decisiones, y los errores devueltos como observaciones informativas "1 coincidencia débil, baja confianza" permiten al agente recuperarse en lugar de dar tumbos.

## **Cierre: forma e interfaz, ninguna es magia**

Recapitulando las dos mitades. Los patrones de agente son decisiones sobre la **forma**: cuántas vueltas, cuánta anticipación, cuándo planificar. Son decisiones de arquitectura de control de flujo, de las que tomas cada vez que diseñas un sistema, aplicadas a un caso donde una de las ramas la decide un modelo. El diseño de tools es la **palanca** que dirige el comportamiento dentro de esa forma. Es ingeniería de interfaces y de prompts: describir bien, delimitar bien, devolver bien, e iterar mirando los resultados.

Lo que une ambas mitades es lo que ninguna de las dos es. No hay aquí aprendizaje automático, ni un modelo secreto que haya que entrenar. Hay elecciones de diseño y un bucle de mejora empírico. No consigues un agente mejor esperando un modelo mejor; lo consigues eligiendo la forma adecuada para tu problema y afinando las tools hasta que las trazas tienen el aspecto que deben tener. Es tunable, es medible, y es tu trabajo el mismo oficio de siempre, con una pieza nueva y acotada en medio.

## **Fuentes**

- Anthropic, *Building Effective Agents* — cuándo un problema pide un agente iterativo frente a un flujo más simple, y la disciplina de empezar por lo mínimo: [https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)
- Anthropic, *Define tools* — descripciones efectivas, espacios de nombres y resultados de alto valor como palanca de comportamiento: [https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)
- Anthropic, *Writing effective tools for agents* — el diseño de tools tratado como superficie que se itera empíricamente: [https://www.anthropic.com/engineering/writing-tools-for-agents](https://www.anthropic.com/engineering/writing-tools-for-agents)