# Qué es CAG (Cache augmented generation)

Creada: 30 de abril de 2026 19:00
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S2. Primeros pasos de arquitectura CAG (https://app.notion.com/p/S2-Primeros-pasos-de-arquitectura-CAG-352ea9ca03c4800aa421ca55b02ceccb?pvs=21)

## **El punto de partida: ¿cómo "sabe cosas" un LLM?**

Antes de hablar de CAG, necesitamos entender una limitación fundamental de los modelos de lenguaje. Un LLM como GPT o Claude tiene un conocimiento extenso adquirido durante su entrenamiento, pero ese conocimiento tiene una fecha de corte y no incluye información privada de tu empresa. Si le preguntas cuánto costó el último proyecto de desarrollo que hizo tu equipo, no tiene forma de saberlo.

Para resolver esto, la industria ha desarrollado dos grandes estrategias para alimentar a un modelo con conocimiento externo en el momento de la inferencia: **RAG** (Retrieval Augmented Generation) y **CAG** (Cache Augmented Generation). Ambas buscan lo mismo — que el modelo disponga de información relevante para responder con precisión — pero lo hacen de formas fundamentalmente diferentes.

## **RAG: la estrategia de ir a buscar**

RAG es la arquitectura que probablemente hayas escuchado con más frecuencia. Su lógica es intuitiva: cuando un usuario hace una pregunta, el sistema primero busca los documentos más relevantes en una base de datos (generalmente vectorial), los recupera y los incluye en el prompt junto con la pregunta del usuario. El modelo genera su respuesta basándose en esos documentos recuperados.

El flujo simplificado es:

```
Pregunta del usuario
       │
       ▼
  Búsqueda en base de datos vectorial
       │
       ▼
  Selección de los fragmentos más relevantes
       │
       ▼
  Construcción del prompt (instrucciones + fragmentos + pregunta)
       │
       ▼
  Llamada al LLM
       │
       ▼
  Respuesta generada
```

RAG es potente y escalable: puedes tener millones de documentos en tu base de datos y el sistema encontrará los relevantes para cada consulta. Pero esa potencia tiene un coste. Necesitas infraestructura de búsqueda (base de datos vectorial, modelos de embeddings, pipeline de indexación), introduces latencia adicional en cada consulta (el tiempo de retrieval), y los errores en la selección de documentos pueden degradar gravemente la calidad de las respuestas. Si el sistema recupera documentos irrelevantes o se deja los relevantes fuera, el modelo generará una respuesta basada en contexto incorrecto o incompleto.

## **CAG: la estrategia de llevar todo encima**

CAG propone un enfoque radicalmente más simple. En lugar de buscar los documentos relevantes en cada consulta, **precarga todo el conocimiento necesario directamente en la ventana de contexto del modelo**. No hay búsqueda en tiempo real, no hay base de datos vectorial, no hay pipeline de retrieval. Todo el contexto viaja en cada llamada.

El flujo es mucho más directo:

```
Todo el conocimiento relevante (precargado)
  +
Pregunta del usuario
       │
       ▼
  Construcción del prompt (instrucciones + TODO el conocimiento + pregunta)
       │
       ▼
  Llamada al LLM
       │
       ▼
  Respuesta generada
```

La diferencia es conceptualmente simple pero tiene implicaciones profundas. Al eliminar el paso de retrieval, CAG elimina de un golpe tres problemas: la latencia de búsqueda, los errores de selección de documentos y la complejidad arquitectónica del sistema.

## **Una analogía para entenderlo**

Imagina que eres un consultor al que le piden estimar un proyecto de software. Tienes dos formas de trabajar:

**Modo RAG:** Tienes un archivo con cientos de presupuestos anteriores en un armario. Cuando llega un cliente nuevo, vas al armario, buscas los presupuestos que te parecen más relevantes (los de proyectos similares), te los llevas a la mesa, y te basas en ellos para hacer tu estimación. El riesgo es que te equivoques al elegir los presupuestos de referencia, que tardes demasiado buscando, o que se te escape uno que era muy relevante.

**Modo CAG:** Tienes solo cinco o diez presupuestos recientes en la mesa, bien organizados, y los tienes todos a la vista mientras trabajas. No necesitas ir a buscar nada — toda la referencia está ahí. El riesgo es diferente: si necesitas referenciar cientos de presupuestos, no te caben en la mesa.

Ninguna estrategia es universalmente mejor. Cada una tiene un escenario ideal.

## **Cuándo usar CAG (y cuándo no)**

La decisión entre CAG y RAG no es una cuestión de preferencia, sino de las características de tus datos y tu caso de uso.

**CAG es la opción correcta cuando:**

- Tu base de conocimiento es **acotada y manejable** — cabe dentro de la ventana de contexto del modelo. Para un modelo con 128K tokens de contexto, esto equivale aproximadamente a 200-250 páginas de texto. Para modelos con ventanas de 1M+ tokens, la capacidad es mucho mayor.
- Los datos son **relativamente estáticos** — no cambian cada hora ni cada minuto. Documentación de producto, políticas internas, FAQs, manuales de procedimientos, o como en nuestro caso, un conjunto acotado de estimaciones históricas de software.
- Necesitas **latencia mínima** — cada milisegundo cuenta. Al no tener paso de retrieval, CAG responde tan rápido como el modelo puede generar.
- Quieres **simplicidad arquitectónica** — menos componentes significa menos puntos de fallo, menos mantenimiento y un time-to-market más rápido. No necesitas base de datos vectorial, no necesitas modelos de embeddings, no necesitas pipeline de indexación.

**CAG no es la opción correcta cuando:**

- Tu base de conocimiento es **grande y crece continuamente** — miles de documentos que no caben en la ventana de contexto, o datos que se actualizan en tiempo real (noticias, inventario, métricas).
- Necesitas **precisión en la selección** — cuando no toda la información es igual de relevante y mezclar datos irrelevantes con relevantes puede confundir al modelo (lo que se conoce como "context distraction").
- El coste por token es una **preocupación principal** — cada llamada CAG envía todo el contexto completo, lo que significa más tokens de entrada y por tanto mayor coste por llamada. Si el volumen de consultas es alto, el coste puede escalar rápidamente.

## **Los componentes de una arquitectura CAG**

Aunque CAG es arquitectónicamente más simple que RAG, sigue teniendo componentes bien definidos que deben diseñarse con cuidado.

### **1. La fuente de conocimiento**

Es el conjunto de datos que el modelo necesita para responder. En nuestro proyecto, son los presupuestos históricos de estimación de software. En otros contextos podría ser documentación de producto, políticas de empresa o catálogos.

Lo importante es que estos datos deben estar **preparados para ser inyectados en un prompt**: limpios, bien formateados y con la información relevante destacada. Un JSON crudo de 50 campos no es un buen contexto; un resumen bien estructurado con los datos clave sí lo es.

### **2. La capa de preprocesamiento**

Antes de inyectar los datos en el prompt, necesitamos transformarlos. Esto puede incluir seleccionar qué campos son relevantes, formatear los datos de forma legible para el modelo, anonimizar información sensible, o agregar datos dispersos en resúmenes coherentes.

Esta capa es donde tomas decisiones críticas: ¿qué información incluyes y cuál omites? ¿En qué formato? ¿Con qué nivel de detalle? Estas decisiones impactan directamente en la calidad de la respuesta y en el consumo de tokens.

### **3. El constructor de prompts**

El prompt es el vehículo que lleva todo al modelo. En una arquitectura CAG, el prompt típicamente tiene esta estructura:

```
┌─────────────────────────────────────┐
│         SYSTEM PROMPT               │
│  (rol del modelo + instrucciones)   │
├─────────────────────────────────────┤
│      CONTEXTO / CONOCIMIENTO        │
│  (datos de referencia precargados)  │
├─────────────────────────────────────┤
│        MENSAJE DEL USUARIO          │
│  (la consulta o transcripción)      │
└─────────────────────────────────────┘
```

El system prompt define el comportamiento del modelo: qué rol asume, qué formato debe usar para las respuestas, qué restricciones tiene. El bloque de contexto contiene todo el conocimiento de referencia. Y el mensaje del usuario es la consulta concreta que necesita respuesta.

La calidad de cada uno de estos bloques determina la calidad de la respuesta. Un system prompt vago produce respuestas vagas. Un contexto desordenado produce respuestas desordenadas. Este es un tema que profundizaremos en el artículo dedicado a gestión de contexto.

### **4. El servicio de llamada al LLM**

Es la capa que gestiona la comunicación con la API del proveedor de LLM (OpenAI, Anthropic, etc.). Parece trivial, pero tiene responsabilidades importantes: gestionar las claves API de forma segura, manejar errores y reintentos, respetar los límites de tasa del proveedor y extraer la información relevante de la respuesta (contenido, tokens consumidos, metadatos).

### **5. El postprocesamiento**

La respuesta del modelo es texto. Dependiendo del caso de uso, puede ser necesario parsearla a JSON, validar que cumple ciertas restricciones, extraer datos estructurados de texto libre o verificar coherencia. En nuestro proyecto, por ejemplo, una estimación que diga "10 horas de desarrollo frontend" pero con un coste asociado de 50.000€ necesita ser detectada y corregida o señalada.

## **CAG en nuestro proyecto: la primera iteración**

Durante esta sesión y las siguientes del Módulo 2, construiremos un sistema de estimación de software usando arquitectura CAG. El flujo concreto será:

1. **Fuente de conocimiento:** Un conjunto de estimaciones históricas de software (presupuestos previos de la empresa) almacenadas como datos estáticos en el código.
2. **Preprocesamiento:** Formatear cada estimación de ejemplo para que sea legible y útil como referencia dentro del prompt.
3. **Construcción del prompt:** Un system prompt que define al modelo como un experto en estimación de software, seguido de las estimaciones de ejemplo como contexto de referencia, seguido de la transcripción de la reunión que se quiere estimar.
4. **Llamada al LLM:** Envío del prompt completo a la API y recepción de la estimación generada.
5. **Postprocesamiento:** Extracción de la estimación en formato utilizable (desglose de tareas, horas, costes).

Esta es la versión más simple posible de un sistema con IA que resuelve un problema real. No tiene base de datos, no tiene embeddings, no tiene retrieval. Y sin embargo, funciona — porque los datos de referencia son pocos y caben en el contexto del modelo.

Cuando los datos crezcan y necesitemos referenciar cientos de presupuestos, migraremos a RAG. Pero empezar con CAG nos permite tener un sistema funcional rápidamente y centrarnos en lo que realmente importa al principio: la calidad del prompt, la estructura de los datos de referencia y el diseño de la respuesta esperada.

## **La ventana de contexto: el recurso más valioso en CAG**

Si CAG consiste en meter todo el conocimiento en la ventana de contexto, el tamaño de esa ventana es el factor limitante de la arquitectura. Y es importante entender que no es solo una cuestión de "cuánto cabe", sino de "qué tan bien funciona el modelo con todo eso dentro".

Dos cosas que todo desarrollador debe saber sobre la ventana de contexto:

**El tamaño anunciado no es el tamaño útil.** Un modelo que anuncia 128K tokens de contexto no te da 128K tokens para tu conocimiento. Parte de ese espacio se consume con el system prompt, otra parte con la respuesta del modelo (tokens de salida), y otra con overhead interno. En la práctica, la capacidad útil para inyectar contexto suele estar entre el 60% y el 80% del tamaño anunciado.

**Más contexto no siempre significa mejor respuesta.** La investigación reciente muestra consistentemente que los modelos pierden capacidad de atención a medida que el contexto crece. La información que está al principio y al final del contexto recibe más atención que la que está en el medio (el efecto conocido como "lost in the middle"). A partir de cierto punto, añadir más contexto puede degradar la calidad de las respuestas en lugar de mejorarla.

Estos dos factores hacen que la gestión eficiente del contexto sea una disciplina en sí misma — algo que abordaremos en detalle en el artículo dedicado a gestión de contexto en arquitectura CAG.

## **De CAG a RAG: el camino natural de evolución**

Una forma útil de pensar en CAG y RAG no es como alternativas excluyentes, sino como **fases de madurez de un mismo sistema**.

Muchos productos con IA empiezan con CAG porque es la forma más rápida de validar que el concepto funciona. Una vez validado, cuando los datos crecen o las necesidades de precisión aumentan, se evoluciona a RAG añadiendo la capa de retrieval.

Este es exactamente el camino que seguiremos en el programa:

```
Módulo 2: CAG
  │  (contexto estático, sin persistencia, todo en el prompt)
  │
  ▼
Módulos 3-4: RAG
  │  (base de datos vectorial, embeddings, búsqueda semántica)
  │
  ▼
Módulo 5: Agentes
     (orquestación, razonamiento multi-paso, tools)
```

Cada fase añade capacidad, pero también complejidad. Entender CAG a fondo es imprescindible para apreciar qué aporta RAG y cuándo el salto de complejidad está justificado.

## **Resumen**

- **CAG es una arquitectura para alimentar LLMs con conocimiento externo** precargando toda la información relevante directamente en la ventana de contexto del modelo, sin necesidad de búsqueda en tiempo real.
- **Es la opción correcta** cuando tu base de conocimiento es acotada, relativamente estática y necesitas simplicidad y velocidad.
- **No es la opción correcta** cuando los datos son masivos, dinámicos o cuando el coste por token en volumen alto es una preocupación.
- **Es la primera fase natural** en la evolución de un producto con IA. Permite validar rápido, iterar sobre la calidad del prompt y los datos de referencia, y decidir con información cuándo escalar a RAG.
- **Elimina tres problemas de RAG:** latencia de retrieval, errores de selección de documentos y complejidad de infraestructura. A cambio, requiere que los datos de referencia quepan en la ventana de contexto. RAG suele construirse en arquitecturas combinadas con CAG para manejar volúmenes grandes de datos propios y aprovechar las ventajas de CAG.

Referencia: [https://blog.logrocket.com/llm-context-problem-strategies-2026](https://blog.logrocket.com/llm-context-problem-strategies-2026)