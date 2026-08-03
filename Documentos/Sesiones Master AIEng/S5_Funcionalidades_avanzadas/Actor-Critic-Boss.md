# Actor-Critic-Boss: la composición de roles que eleva la calidad

Creada: 17 de mayo de 2026 16:20
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S5. Funcionalidades avanzadas (https://app.notion.com/p/S5-Funcionalidades-avanzadas-363ea9ca03c4809fa6b4c8d2a9413af9?pvs=21)

Llegado este punto del programa, el `estimator` tiene una arquitectura razonable. Recibe transcripciones acompañadas de adjuntos, mantiene memoria conversacional separada del historial, adapta su salida al perfil del usuario, y empieza a tener una suite mínima de evals que detecta regresiones. Es un sistema que un equipo se puede tomar en serio.

Y aún así, si miras de cerca las salidas, hay un techo de calidad que no se rompe solo refinando prompts. Una estimación generada en una sola pasada es buena en promedio, pero **inconsistente en los casos donde el coste del error es más alto**. Aritméticas internas que no cuadran. Riesgos importantes que no se mencionan. Componentes técnicos que aparecen en la justificación pero no en el desglose de horas. Casos límite donde el modelo elige una de las dos respuestas posibles sin verificar si era la correcta.

Este artículo plantea el patrón que rompe ese techo: una composición de tres roles —**Actor, Critic y Boss**— que separa la generación de la evaluación y de la decisión, y que en la literatura de agentes está sólidamente establecida bajo otros nombres. No es magia ni un framework nuevo: son tres llamadas al LLM con responsabilidades diferenciadas y un poco de orquestación.

## **1. Por qué un mejor prompt no es la solución**

El instinto razonable cuando un sistema CAG falla en casos sutiles es reescribir el prompt. Más ejemplos en el system prompt, más restricciones explícitas, más estructura en la salida. Y de hecho funciona — hasta cierto punto.

El punto donde deja de funcionar es donde el problema **no es de instrucción**, sino de **verificación**. Cuando un humano produce una estimación importante, el flujo natural no es "pienso una respuesta y la entrego". Es "pienso una respuesta, la reviso, encuentro un error, la corrijo, vuelvo a revisar". Esa segunda pasada de revisión es estructuralmente distinta de la primera de generación: usa criterios explícitos, va a contracorriente del razonamiento original, y suele descubrir cosas que el generador no podía ver porque estaba comprometido con su propia narrativa.

Un único LLM en una sola llamada hace ambas cosas a la vez —genera y se autovalida sobre la marcha— y resulta que los modelos modernos no son muy buenos en autocrítica genuina. Madaan et al. mostraron en *Self-Refine* (2023) que separar generación de feedback en dos llamadas distintas mejoraba la calidad del output un 20% absoluto en promedio sobre siete tareas distintas, sin entrenamiento adicional ni datos supervisados. La conclusión no es que los modelos sean malos generando, sino que **mezclar generación y verificación en una misma llamada degrada ambas funciones**.

Lo que viene en este artículo es la versión disciplinada de esa idea, llevada un paso más allá.

## **2. Composición de roles: Actor, Critic, Boss**

El patrón consiste en separar el trabajo en tres roles, cada uno encarnado por una llamada al LLM con su propio prompt y su propio criterio de éxito.

![006-actor-critic-boss.jpg](https://media1-production-mightynetworks.imgix.net/asset/71551d5f-0849-4f1b-a9ce-8166bec4540b/006-actor-critic-boss.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Actor.** Genera la estimación inicial a partir de la transcripción, los adjuntos y el `project_metadata`. Es la llamada al LLM que el `estimator` ya hace hoy. No cambia. Sigue exactamente el patrón que conoces: template Jinja2 según tier, schema Pydantic en la salida, contexto CAG en el system prompt. La diferencia es que su salida deja de ser la respuesta final y pasa a ser un *candidato*.

**Critic.** Recibe el output del actor y lo evalúa contra un conjunto explícito de criterios: ¿está completo? ¿la aritmética interna cuadra? ¿los riesgos identificados son coherentes con el alcance? ¿hay contradicciones con el `project_metadata`? ¿faltan componentes que la transcripción menciona explícitamente? El crítico **no genera una nueva estimación**: produce feedback estructurado sobre la estimación que recibió.

**Boss.** Recibe la estimación del actor + el feedback del crítico. Toma una decisión: si el feedback no encuentra problemas materiales, acepta y devuelve la estimación tal cual. Si el feedback identifica problemas corregibles, devuelve la estimación al actor con instrucciones específicas para una nueva iteración. Si el feedback es complejo y la corrección no es obvia, sintetiza la versión final integrando el output del actor con las correcciones del crítico. Y, crucialmente, **limita el número de iteraciones** para acotar coste y latencia.

## **3. Anclaje en la literatura**

Aunque el nombre "Actor-Critic-Boss" es nuestro, los tres roles tienen anclaje sólido en la literatura de agentes y de patrones de orquestación con LLMs. Conocer ese anclaje importa por dos razones: te da autoridad para defender el patrón en una conversación técnica, y te abre las puertas al cuerpo de investigación correspondiente cuando quieras profundizar.

![image.png](https://media1-production-mightynetworks.imgix.net/asset/bde8c719-a574-4dce-80da-8dd65f3bf738/5ded8b7619879a98.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Rol del patrón Equivalente en la literatura Fuente principal **Actor** Generator / Optimizer Anthropic, *Building Effective Agents* (2024); Madaan et al., *Self-Refine* (2023); Estornell et al., *ACC-Collab* (2024) **Critic** Evaluator / Critic / Self-Verifier Anthropic, *Building Effective Agents*; Madaan et al., *Self-Refine*; Shinn et al., *Reflexion* (2023) **Boss** Orchestrator / Supervisor Anthropic, *Building Effective Agents* (orchestrator-workers workflow); LLaMAC (2023)

El ensayo *Building Effective Agents* de Anthropic formaliza dos patrones de workflow que son la base directa de lo que estamos componiendo aquí:

- **Evaluator-Optimizer:** un LLM genera, otro evalúa, se itera. Es el origen estructural del `actor + critic`.
- **Orchestrator-Workers:** un LLM central descompone tareas, delega a workers, y sintetiza resultados. Es el origen del `boss`.

Lo que añade el patrón Actor-Critic-Boss respecto a las versiones más simples (Self-Refine puro, Evaluator-Optimizer simple) es la **separación explícita entre evaluación y decisión**. Es la pieza que conviene examinar.

## **4. Por qué tres roles y no dos**

El instinto inicial al ver el patrón es preguntar "¿no basta con actor y crítico?". Es una pregunta legítima, y la respuesta concreta es lo que justifica la introducción del tercer rol.

![007-dos-vs-tres-roles.jpg](https://media1-production-mightynetworks.imgix.net/asset/2a297623-ea17-40ed-b1ec-7afea478e10c/007-dos-vs-tres-roles.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Si el crítico también decide qué hacer con su propio feedback —aceptar, iterar o sintetizar—, aparecen dos modos de fallo recurrentes que han sido reportados en sistemas Self-Refine puros:

**Bucles infinitos por insatisfacción crónica.** El crítico, especialmente si está bien calibrado para detectar problemas, casi siempre encuentra algo que mejorar. Sin un árbitro externo, el sistema itera turno tras turno con mejoras marginales, agotando presupuesto de tokens y latencia sin convergencia clara. El problema no es del crítico — está haciendo su trabajo. El problema es que evaluar y decidir cuándo parar son funciones diferentes.

**Sesgo de confirmación temprana.** El opuesto. El crítico se convierte en cómplice del actor: encuentra excusas para aceptar la primera respuesta porque eso resuelve el problema rápido. En modelos donde el mismo LLM actúa como crítico que como actor, este sesgo es especialmente fuerte porque el modelo tiende a defender lo que acaba de producir.

Separar evaluación de decisión rompe ambos modos de fallo. El crítico se concentra exclusivamente en producir feedback de calidad. El boss, con un prompt diferente y criterios distintos —centrados en *governance* del proceso, no en calidad técnica de la respuesta—, decide cuándo lo bueno es suficientemente bueno y cuándo el coste de iterar más supera al beneficio esperado.

Esta separación tiene un paralelo directo en cómo se organizan equipos humanos: el ingeniero hace el trabajo, el revisor de código identifica problemas, y el tech lead decide qué problemas son bloqueantes para el merge y cuáles son notas de seguimiento. Mezclar los tres roles en una misma persona suele producir o bien parálisis perfeccionista, o bien releases apresuradas. La especialización funciona.

## **5. Cuándo el patrón compensa y cuándo es overkill**

Como cualquier patrón con coste real, Actor-Critic-Boss no es la respuesta a todo. Triplica las llamadas al LLM por petición (mínimo) y multiplica la latencia. Conviene tener criterios explícitos para decidir cuándo invocarlo.

**El patrón compensa cuando se cumplen al menos dos de estas condiciones:**

- **El coste del error es alto.** Una estimación que el cliente va a usar como base de un contrato comercial. Una recomendación médica que se va a archivar en historia clínica. Un análisis que va a fundamentar una decisión de inversión. En todos estos casos, una respuesta defectuosa cuesta más que la latencia adicional.
- **Existen criterios de evaluación claros.** El crítico necesita instrucciones específicas para evaluar. Si los criterios son "que esté bien", el patrón degenera porque el crítico no tiene material concreto sobre el que producir feedback. Para el `estimator`, los criterios son claros: aritmética interna, completitud de componentes, coherencia con la transcripción.
- **La latencia adicional es tolerable.** Si tu sistema está en un loop de chat con expectativa de respuesta inmediata, multiplicar la latencia por tres rompe la experiencia. Si tu sistema produce un informe que el usuario va a recibir cuando esté listo, los segundos extra son aceptables.

**El patrón es overkill cuando:**

- La tarea es simple y la respuesta es difícilmente errónea ("traduce este texto al inglés").
- El sistema ya tiene tests deterministas hard que cubren los modos de fallo importantes.
- El coste por petición ya es un factor crítico del modelo de negocio.
- Los criterios de evaluación son tan vagos que el crítico no añade información sobre el actor.

La regla operativa que suele funcionar: **aplica el patrón solo a los caminos críticos del producto, no a todas las llamadas al LLM**. Para el `estimator`, esto se traduce en aplicarlo al flujo de generación de estimación final, no a la extracción de `project_metadata` ni a respuestas auxiliares.

## **6. Anti-patrones frecuentes**

Tres errores que se ven cuando equipos implementan este patrón sin haber interiorizado por qué los tres roles son distintos.

**Anti-patrón 1 — Tres llamadas con prácticamente el mismo prompt.** Actor, crítico y boss usan templates Jinja2 muy parecidos porque "todos están trabajando sobre la misma tarea". El resultado: tres veces el coste sin ganancia de calidad, porque el crítico está haciendo lo mismo que el actor y el boss está repitiendo el trabajo del crítico. Cada rol necesita un prompt **estructuralmente distinto**: el actor optimiza por generación, el crítico por detección de fallos, el boss por gobernanza del proceso.

**Anti-patrón 2 — El crítico devuelve texto libre.** "Le pido al crítico que me diga qué problemas encuentra, en lenguaje natural". El boss recibe un párrafo y tiene que interpretarlo. La interpretación a veces falla, los problemas detectados se pierden, y el sistema se vuelve menos predecible que el monolítico de partida. El feedback del crítico **debe ser estructurado**: lista de issues con categoría (`arithmetic_error`, `missing_component`, `inconsistency_with_metadata`...), severidad (`critical`, `major`, `minor`) y referencia al campo afectado del output del actor. La disciplina de schemas Pydantic que ya conoces aplica directamente aquí.

**Anti-patrón 3 — Iteraciones sin límite.** "El boss decide cuándo parar; cuando el crítico no encuentre más problemas, listo". En la práctica el crítico siempre encuentra algo. Sin límite explícito de iteraciones, una petición puntualmente difícil consume cinco o seis ciclos antes de converger, multiplicando coste y latencia hasta romper el sistema. **El boss siempre opera con un presupuesto máximo de iteraciones** (típicamente 2 o 3); cuando se agota, sintetiza la mejor respuesta disponible y la entrega aunque no sea perfecta. Producción se prefiere a perfección.

## **7. Resumen**

Cuatro afirmaciones operativas para llevarte:

1. **Hay un techo de calidad que no se rompe refinando prompts.** Cuando el problema es de verificación, no de instrucción, la solución es estructural: separar generación de evaluación.
2. **Tres roles, no dos.** Actor genera, Critic evalúa, Boss decide. La separación entre evaluación y decisión rompe los modos de fallo clásicos del Self-Refine puro: bucles infinitos por insatisfacción crónica y sesgo de confirmación temprana.
3. **El patrón está sólidamente fundamentado en la literatura.** Actor-Critic-Boss compone evaluator-optimizer y orchestrator-workers, los dos workflows formalizados por Anthropic en *Building Effective Agents*, sin frameworks adicionales.
4. **El patrón compensa cuando el coste del error es alto, los criterios de evaluación son claros y la latencia extra es tolerable.** Aplícalo a los caminos críticos del producto, no a todas las llamadas al LLM.

Lo importante de esta pieza no es la implementación —que es relativamente directa— sino haber interiorizado **por qué** la separación de roles eleva la calidad. Cuando ese por qué está claro, el cómo se construye solo.