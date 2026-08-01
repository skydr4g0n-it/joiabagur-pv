# Del bucle manual al grafo: cuando necesitamos un framework

Creada: 16 de julio de 2026 17:41
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S13. Orquestación de Agentes (https://app.notion.com/p/S13-Orquestaci-n-de-Agentes-39fea9ca03c480a9b543f627044858ef?pvs=21)

El sistema de estimación tiene hoy una capa agéntica construida a mano: un bucle sobre el pipeline RAG que, dado el texto de una reunión, decide qué operación ejecutar a continuación, recuperar presupuestos, calcular, validar, y repite hasta cerrar una estimación. Es un `while` con function calling y unas cuantas ramas. Funciona, y funciona bien mientras el flujo es corto.

El problema aparece cuando el flujo crece. En cuanto hay varios pasos con dependencias, decisiones condicionales que dependen de lo que devolvió el paso anterior, trabajo que podría hacerse en paralelo o situaciones en las que hay que volver atrás, el bucle imperativo empieza a acumular `if` anidados, banderas de estado y comentarios que explican por qué el orden es ese y no otro. El código sigue siendo correcto, pero deja de ser legible, y sobre todo deja de ser fácil de razonar cuando algo falla en producción.

Ahí es donde entra la orquestación formal. Y con ella, la pregunta que este artículo quiere responder con criterio y no por moda: ¿cuándo merece la pena un framework de orquestación, y cuándo el bucle a mano ya era la respuesta correcta?

## **El panorama de frameworks en 2026**

El ecosistema se ha consolidado bastante respecto a los años anteriores. Hoy conviven, a grandes rasgos, tres modelos de orquestación.

**Orquestación basada en grafos.** Modelas el sistema como un grafo dirigido: nodos que hacen trabajo, aristas que deciden la transición. El exponente es **LangGraph**, de LangChain, que alcanzó su versión 1.0 estable en octubre de 2025 junto con LangChain 1.0. En este modelo el flujo está definido de antemano y es explícito, lo que da control determinista y depuración más sencilla a cambio de más diseño previo.

**Orquestación basada en roles.** Defines agentes como personas de un equipo, cada uno con su rol, sus herramientas y su tarea. El exponente es **CrewAI**: un agente "manager" delega en especialistas. El modelo mental es intuitivo y se prototipa rápido, a costa de menos control fino en flujos con ramificación compleja.

**Orquestación conversacional.** Los agentes coordinan intercambiando mensajes por turnos. Es el linaje de **AutoGen**. Conviene saber que Microsoft fusionó AutoGen y Semantic Kernel en el **Microsoft Agent Framework**, que llegó a 1.0 en abril de 2026; los dos proyectos originales quedan en modo mantenimiento. Es la opción natural en ecosistemas Azure/.NET.

Fuera de esos tres, hay dos nombres que un equipo Python debería tener en el radar. **Google ADK** (Agent Development Kit), el kit code-first y model-agnostic dentro de la plataforma de agentes de Google Cloud, con agentes de flujo secuencial, paralelo y bucle. Y **Pydantic AI**, nativo de Python, tipado y con inyección de dependencias al estilo FastAPI, que encaja de forma especialmente cómoda con un servicio construido sobre ese stack. A esto se suman los SDK de agente de los propios proveedores de modelo (OpenAI, Anthropic), pensados para el bucle de agente único.

La foto importante no es la lista, sino la observación de fondo: **la novedad de estos frameworks está acotada**. Todos resuelven variaciones del mismo problema, coordinar pasos, mantener estado, recuperar de errores, con abstracciones distintas. Ninguno hace magia. Son ingeniería de sistemas aplicada a un tipo de servicio nuevo.

## **Frameworks vs orquestación interna: la pregunta correcta**

La tentación, cuando aparece un framework maduro, es adoptarlo por defecto. La tentación contraria, en un equipo que valora el control, es construirlo todo a mano. Las dos son atajos que se saltan la única pregunta que importa: **¿qué forma tiene mi flujo?**

Conviene ser honesto sobre lo que cuesta cada camino. El equipo de ingeniería de LinkedIn resumió su experiencia en producción con una recomendación tajante: intenta comprar antes que construir, y construye solo si lo que necesitas no existe, porque el espacio se mueve muy rápido. El patrón que domina en la práctica es híbrido: framework o plataforma para el 80% estándar del flujo, y código propio solo para el porcentaje que es tu diferencial de dominio.

El consejo operativo más repetido por los equipos que han llevado agentes a producción es igual de sobrio: **empieza simple, instrumenta mucho, y añade complejidad solo donde los datos la exijan**. La mayoría de los equipos se pasan un escalón de sofisticación: montan un sistema multi-agente donde un solo agente bien instrumentado habría bastado.

Hay un dato que ordena las prioridades. Según el informe de ingeniería de agentes de LangChain de 2026, más del 60% de los incidentes de agentes en producción se originan en la gestión de estado: agentes que pierden el hilo, repiten trabajo o se caen a medias porque el estado no se persistió bien. No en la calidad del modelo, no en el prompt: en el estado. Eso dice mucho sobre dónde está el trabajo de verdad, y sobre qué debería resolver bien un framework para ganarse su sitio.

## **Dónde encaja LangGraph**

Para un flujo como el de estimación, una secuencia de pasos con responsabilidad propia, alguna rama condicional y trabajo paralelizable, el modelo de grafo es el que mejor encaja. Y su modelo es deliberadamente pequeño.

Un grafo en LangGraph es cuatro ideas:

- Un **estado** compartido y tipado que todos los nodos leen y actualizan.
- **Nodos**, que son funciones que reciben el estado y devuelven una actualización parcial.
- **Aristas**, que conectan nodos; las **aristas condicionales** inspeccionan el estado y deciden a dónde ir.
- Un **checkpointer**, que persiste el estado tras cada paso y hace posible pausar, reanudar y recuperar.

Todo lo demás, ejecución paralela, ramas, subgrafos, intervención humana, se construye sobre esas cuatro ideas. Para cualquier ingeniero que haya dibujado alguna vez un diagrama de flujo o una máquina de estados, el modelo es familiar. Esa familiaridad es precisamente el punto: no estás aprendiendo un paradigma nuevo, estás poniendo nombre y runtime a algo que ya sabías dibujar.

Conviene separar dos niveles dentro del propio LangChain, porque se confunden. El atajo de alto nivel `create_agent` (que reemplaza al antiguo `create_react_agent`) construye en pocas líneas un agente de tipo ReAct: un bucle donde el modelo decide si llamar a una herramienta o terminar. Es exactamente el patrón de un agente único que razona y actúa. Para eso, un bucle a mano o `create_agent` sirven igual de bien. La API de grafos de bajo nivel, `StateGraph`, es otra cosa: das forma explícita a topologías que el bucle ReAct no expresa bien, varios pasos con dependencias, enrutado condicional, paralelismo, ciclos acotados. Ese es el terreno donde el grafo se gana su sitio.

En términos de arquitectura del proyecto, nada de esto altera el contrato. El grafo vive dentro del **servicio IA**, igual que el bucle que sustituye. El **backend de negocio** sigue enviando una transcripción y recibiendo una estimación estructurada con su campo `status`, indiferente a que debajo haya un bucle, un grafo o cualquier otra cosa. LangGraph es además agnóstico del modelo: los nodos siguen envolviendo la misma llamada al modelo que ya usa el servicio. El framework orquesta; no sustituye tu capa de llamada al LLM.

![S13-fig-01-decision-framework.jpg](https://media1-production-mightynetworks.imgix.net/asset/1c8cb540-e1a9-49cb-bb12-50f9d13d08cd/S13-fig-01-decision-framework.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **El impuesto de complejidad**

Un framework no sale gratis, y decirlo forma parte de elegirlo bien. LangChain 1.0 es estable, pero es pesado: arrastra una superficie de dependencias, capas de indirección y andamiaje que un bucle propio no tiene. Ese es su impuesto de complejidad, y hay que pagarlo con los ojos abiertos.

La regla práctica es directa. Si tu "flujo" es una sola llamada al modelo con un formato de salida y, como mucho, una cola por detrás, no metas un framework de orquestación: no hay nada que orquestar y solo estarías pagando el impuesto sin recibir nada a cambio. Si tu flujo es un agente único que razona y llama herramientas en bucle, un bucle a mano bien instrumentado ya es una respuesta perfectamente profesional; el framework aporta poco. El framework empieza a ganarse su sitio cuando el flujo tiene forma de grafo de verdad: pasos con dependencias, ramas condicionales, paralelismo, necesidad de persistir y reanudar estado, puntos donde un humano tiene que aprobar antes de seguir. En ese punto, lo que el framework te ahorra, el checkpointer, el enrutado condicional, la pausa/reanudación, la instrumentación por nodo, es exactamente el trabajo que, si no, reimplementarías tú peor.

Y hay una prueba que no se puede saltar: **mide la línea base antes de decidir**. El bucle a mano que ya existe es la referencia honesta. Si al reexpresarlo como grafo el sistema no gana nada medible, ni claridad, ni capacidad de recuperación, ni observabilidad, entonces el bucle ya era la respuesta correcta y el framework sobra. La decisión se toma con datos, no con fe en la abstracción.

## **El siguiente paso**

La conclusión no es "usa un framework" ni "no lo uses". Es que el flujo de estimación tiene, hoy, la forma exacta que justifica un grafo: una secuencia de pasos con responsabilidad propia, con al menos una rama condicional en la validación y con trabajo, la búsqueda de presupuestos por component, que pide a gritos ejecutarse en paralelo. Reexpresar ese flujo como un grafo explícito, con estado tipado y persistente y con observabilidad por nodo, es el paso natural: convierte un bucle que había que leer con cuidado en una estructura que se puede ver, medir y razonar. Lo que sigue es dibujar ese grafo y hacerlo correr.

## **Resumen**

- **El sistema tiene un bucle agéntico a mano que funciona, pero escala mal.** En cuanto el flujo suma pasos, ramas y paralelismo, el bucle imperativo se llena de estado implícito y se vuelve difícil de razonar.
- **En 2026 conviven tres modelos de orquestación:** basado en grafos (LangGraph), basado en roles (CrewAI) y conversacional (linaje AutoGen, hoy Microsoft Agent Framework). Google ADK y Pydantic AI completan el radar de un equipo Python.
- **La pregunta correcta no es "framework sí o no", sino qué forma tiene el flujo.** El patrón dominante es híbrido; el consejo dominante, empezar simple e instrumentar mucho.
- **La gestión de estado es donde se cae la mayoría de los agentes en producción.** Eso define qué tiene que resolver bien un framework para merecer la pena.
- **LangGraph es cuatro ideas:** estado tipado, nodos-función, aristas (condicionales) y checkpointer. `create_agent` cubre el agente ReAct de bucle único; `StateGraph` cubre las topologías reales con ramas y paralelismo.
- **Todo framework tiene un impuesto de complejidad.** Sin flujo que orquestar, no lo pagues. Con un grafo de verdad, lo que te ahorra es el trabajo que reimplementarías peor. Mide la línea base antes de decidir.

## **Referencias**

- LangChain - anuncio de LangChain 1.0 y LangGraph 1.0: `https://www.langchain.com/blog/langchain-langgraph-1dot0`
- LangChain - comparativa de frameworks de agentes: `https://www.langchain.com/resources/ai-agent-frameworks`
- Microsoft - Agent Framework (overview y sucesión de AutoGen y Semantic Kernel): `https://learn.microsoft.com/en-us/agent-framework/overview/`
- Google -
- Agent Development Kit (overview): `https://docs.cloud.google.com/agent-builder/agent-development-kit/overview`
- Patrones de orquestación de agentes en producción: `https://arahi.ai/blog/ai-agent-orchestration`