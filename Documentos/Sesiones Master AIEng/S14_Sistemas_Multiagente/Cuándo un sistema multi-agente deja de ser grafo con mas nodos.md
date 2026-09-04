# Cuándo un sistema multi-agente deja de ser un grafo con más nodos

Creada: 20 de julio de 2026 21:07
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S14. Sistemas multi-agente y patrones avanzados (https://app.notion.com/p/S14-Sistemas-multi-agente-y-patrones-avanzados-3a3ea9ca03c4800f98e8fdae96ec7f6f?pvs=21)

Tenéis un grafo de estimación que funciona. Recibe una transcripción, extrae requisitos, clasifica componentes, busca presupuestos históricos, genera una estimación y la valida. Cinco nodos, estado tipado, checkpointer sobre Postgres, trazas limpias. Hace lo que promete.

Y ahora alguien os dice que hay que convertirlo en un sistema multi-agente.

La pregunta correcta ante esa frase no es "¿cómo?". Es "¿por qué?". Porque desde fuera —y esto es lo primero que conviene desactivar— un sistema multi-agente se parece bastante a un grafo con más nodos y nombres más ambiciosos. Si la única diferencia fuese llamar `budget_searcher` a lo que antes era `search_budgets`, estaríamos haciendo teatro de arquitectura. Y el teatro de arquitectura se paga en latencia, en coste por token y en madrugadas depurando por qué el sistema tomó una decisión que nadie escribió.

Este artículo trata de la frontera. De qué límite concreto tiene que haberos golpeado para que multiplicar agentes deje de ser una complicación gratuita y pase a ser la respuesta correcta.

## **El techo del grafo único**

Empecemos por lo que sí funciona, porque el grafo de la sesión anterior no es un borrador que haya que superar. Es una arquitectura legítima que resuelve una clase entera de problemas, y muchos sistemas en producción no necesitan pasar de ahí.

Lo que hace un grafo dirigido con nodos-función es fijar el *control flow* en el código. Vosotros decidís, en tiempo de escritura, que después de extraer requisitos se clasifican componentes y que después se buscan presupuestos. Las aristas condicionales dan flexibilidad, pero la flexibilidad está acotada: son ramas que alguien previó y escribió. El modelo rellena huecos; no elige el camino.

Esa propiedad es una ventaja enorme. Un flujo determinista es predecible, barato de trazar y fácil de testear. Cuando el proceso de negocio que estáis modelando tiene una secuencia estable —y estimar software, en su forma canónica, la tiene— el grafo lineal es la respuesta correcta. Empezar por multi-agente cuando el flujo es fijo es como montar una arquitectura de microservicios para un CRUD de tres tablas: no está mal por ser complejo, está mal porque la complejidad no compra nada.

El techo aparece cuando ese modelo mental deja de sostenerse. Y aparece de formas bastante reconocibles.

**El prompt de un nodo empieza a acumular reglas de dominios distintos.** Mirad el nodo que genera la estimación. Si su *system prompt* dice cómo calcular horas, y además cómo interpretar presupuestos históricos de proyectos que no encajan del todo, y además cómo ajustar por la seniority del equipo del cliente, y además cómo reaccionar si la transcripción menciona una integración con un ERP legacy... ese nodo ya no es un paso. Es un agente sobrecargado con cuatro responsabilidades peleándose dentro de una misma ventana de contexto. El síntoma clásico: tocáis una regla del prompt para arreglar un caso y se rompe otro que no tiene nada que ver. Es acoplamiento, exactamente el mismo que reconoceríais en una clase de 800 líneas.

**El conjunto de tools crece dentro de un único espacio de decisión.** Si un solo nodo tiene acceso a seis, ocho, doce herramientas, el modelo tiene que discriminar entre todas ellas en cada llamada. La tasa de elección incorrecta de tool sube con el número de opciones, igual que subiría la de un humano al que le das doce botones sin etiquetar bien. Repartir esas tools entre agentes con menos opciones cada uno no es solo higiene de seguridad: mejora la precisión.

**El orden deja de ser conocido de antemano.** Esta es la señal más definitiva, y merece detenerse. En vuestro grafo, el orden lo fijasteis vosotros. Pero imaginad una transcripción donde el cliente describe tres módulos independientes: uno es un CRUD conocido, otro es una integración con un sistema del que no hay precedente, y el tercero es una migración de datos. El camino óptimo para cada módulo es distinto. Para el CRUD basta con buscar presupuestos y calcular. Para la integración sin precedente hay que extraer requisitos con mucho más detalle, buscar por analogía, y probablemente no fiarse del resultado. Codificar todas esas ramas como aristas condicionales es posible, pero el grafo se convierte en un árbol de decisión escrito a mano que envejece mal.

Cuando quien decide qué se ejecuta a continuación deja de ser el código y pasa a ser el modelo, habéis cruzado la frontera. **Eso es lo que separa un workflow de un sistema agéntico**: no la cantidad de nodos, sino quién es dueño del control flow.

**Las responsabilidades evolucionan a ritmos distintos.** Argumento puramente de ingeniería de software, y probablemente el más familiar. Si el equipo de datos itera semanalmente sobre cómo se buscan presupuestos y el equipo de negocio toca las reglas de validación una vez al trimestre, tenerlos en el mismo nodo es un problema organizativo antes que técnico. Los ejes de cambio distintos piden componentes distintos. Esto lo lleváis aplicando toda la vida; aquí no cambia.

![fig-01-grafo-lineal-vs-supervisor.png](https://media1-production-mightynetworks.imgix.net/asset/9faf14b5-1409-4214-af45-444c2ad576da/fig-01-grafo-lineal-vs-supervisor.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Fijaos en lo que la figura *no* muestra. No hay infraestructura nueva. El estado compartido es el mismo estado tipado. Los nodos son las mismas funciones. Lo único que ha cambiado es que hay un nodo que decide y unos nodos que solo ven sus propias herramientas. Un sistema multi-agente, en la forma que os va a servir en producción, es vuestro grafo reorganizado.

## **Dos formas de repartir el trabajo**

Cuando la decisión de ir a multi-agente está justificada, hay una segunda decisión que la gente se salta y que determina el coste y el comportamiento del sistema entero: **¿los agentes cooperan o compiten?**

### **Cooperación: cada agente aporta una pieza distinta**

Es el reparto por especialización. El extractor produce requisitos, el buscador produce presupuestos análogos, el generador produce horas, el validador produce un veredicto. Ninguno hace el trabajo de otro; el resultado es la composición de todos.

Esta es la topología que tiene sentido por defecto para la estimación, y por una razón concreta: **las contribuciones son ortogonales**. Extraer requisitos de una transcripción y validar la coherencia de costes son tareas que no compiten entre sí, se necesitan. Pedirle a dos agentes que extraigan requisitos en paralelo para quedarse con el mejor sería gastar el doble para obtener, casi siempre, lo mismo.

El coste es una pasada por el flujo. El riesgo es el clásico de las cadenas: un eslabón débil contamina todo lo que viene detrás. Si el extractor se deja un requisito, ni el buscador ni el generador ni el validador tienen forma de saberlo. Ninguno vio la transcripción original con esa responsabilidad.

### **Competición: varios agentes proponen y alguien sintetiza**

Aquí dos o más agentes atacan **la misma tarea** con criterios distintos, y un tercero decide. En estimación el ejemplo es casi demasiado natural: un agente estima en modo conservador (asume fricción, integraciones que se tuercen, requisitos que crecen) y otro en modo agresivo (asume equipo competente y alcance estable). Un sintetizador recibe ambas propuestas y produce el resultado final.

Lo interesante no es que el sintetizador "elija la buena". Lo interesante es que **la divergencia entre las dos propuestas es información que no teníais**. Si el conservador dice 340 horas y el agresivo dice 190, esa separación os está diciendo que el proyecto tiene mucha incertidumbre estructural. Si ambos convergen en 250 y 270, el caso es predecible. En el grafo con un único estimador esa señal no existe: obtenéis un número y no sabéis cuánto confiar en él.

![fig-02-cooperan-vs-compiten.png](https://media1-production-mightynetworks.imgix.net/asset/bb3a91c7-aeb0-4b03-8d20-f76d804decb9/fig-02-cooperan-vs-compiten.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La competición se paga literalmente al doble o al triple: dos generaciones más una síntesis. Y tiene una trampa sutil. Si los dos agentes que compiten comparten el mismo contexto, el mismo modelo y prompts que solo se diferencian en un adjetivo, sus salidas van a correlacionar mucho más de lo que esperáis, y estaréis pagando tres llamadas por la ilusión de una segunda opinión. La competición aporta señal **cuando los criterios divergen de verdad**: distinto prompt, distinto conjunto de evidencias, idealmente distinto modelo.

Regla de bolsillo: cooperación para descomponer trabajo; competición para atacar incertidumbre. Y no las mezcléis por defecto, porque la competición aplicada a todo os multiplica la factura sin multiplicar la calidad.

## **Lo que os va a costar**

Un sistema multi-agente es una decisión de arquitectura con contrapartidas reales. Merecen estar sobre la mesa antes de escribir la primera línea.

**Coste y latencia.** Cada salto de enrutado del supervisor es una llamada al modelo que no produce trabajo útil: solo decide. En una topología con supervisor central, una tarea que toque dos especialistas implica cuatro llamadas (supervisor → agente A → supervisor → agente B) donde el grafo lineal hacía dos. Estáis pagando enrutado. Puede merecer la pena; lo que no puede es que lo descubráis en la factura.

**Pérdida de contexto en las transiciones.** Cuando un agente pasa el testigo, ¿qué se lleva el siguiente? Si le pasáis todo el historial de mensajes, el contexto crece sin control y volvéis al problema que queríais evitar. Si le pasáis solo un resumen, ese resumen se convierte en un cuello de botella semántico: lo que no esté ahí, no existe para el agente que viene. No hay respuesta universal. Hay una decisión explícita que tenéis que tomar, y que ninguna librería toma bien por vosotros.

**No-determinismo en el control flow.** Es la contrapartida directa de la ventaja principal. Si el supervisor decide la ruta, dos ejecuciones sobre la misma transcripción pueden recorrer caminos distintos. Eso complica los tests, complica la reproducción de bugs y complica explicarle a un cliente por qué la estimación de ayer no coincide con la de hoy. Es gestionable —trazas, checkpoints, temperatura baja en el enrutado, tests sobre el resultado y no sobre el camino— pero es un impuesto permanente.

**Superficie de fallo mayor.** Cinco agentes son cinco sitios donde el modelo puede alucinar, cinco conjuntos de tools que pueden invocarse mal y un enrutador que puede quedarse en bucle. El grafo lineal, con toda su rigidez, tenía una propiedad valiosa: si fallaba, sabíais exactamente dónde.

**Y el coste que nadie cuenta: el cognitivo.** El siguiente desarrollador que abra el repositorio tiene que entender cinco prompts, un protocolo de enrutado y una pizarra de estado compartida, en lugar de leer cinco funciones en orden. Si el sistema no está resolviendo un problema que justifique eso, le habéis hecho un flaco favor.

### **Cuándo *no* hacerlo**

Sed honestos con estas tres:

- **Si el flujo es fijo, no necesitáis un supervisor.** Un supervisor cuya única política es "primero A, luego B, luego C" es una arista condicional cara, con una llamada al modelo de más y una fuente de aleatoriedad gratis. El grafo lineal ya expresaba eso, y mejor.
- **Si el problema real es un prompt malo, arreglad el prompt.** Repartir un prompt mediocre entre cuatro agentes os deja cuatro prompts mediocres y un problema de coordinación encima.
- **Si no tenéis observabilidad, no añadáis agentes.** Un sistema multi-agente sin trazas por nodo no es un sistema: es una caja negra con opiniones. La instrumentación no es un extra que se añade después; es la precondición para que esta arquitectura sea depurable.

## **Lo que queda por decidir**

Si habéis llegado hasta aquí con la sensación de que multi-agente se parece sospechosamente a lo que ya sabéis hacer —separar responsabilidades, limitar lo que cada componente puede tocar, definir contratos entre piezas— es que lo habéis entendido. No hay un paradigma nuevo. Hay una capa nueva y pequeña sobre principios que lleváis años aplicando.

Pero justificar la arquitectura es la parte fácil. Lo que queda abierto es más duro y más concreto:

Alguien tiene que **enrutar**, y ese alguien es un nodo que decide en runtime qué especialista actúa. ¿Cómo se construye para que cada una de sus decisiones sea visible y no un acto de fe? Los agentes tienen que **comunicarse**, y la forma en que lo hagan —estado compartido, testigo directo, mensajes— cambia el coste y la trazabilidad del sistema entero. Habrá casos en los que el sistema **no deba decidir solo**, y la pausa para que entre una persona no puede ser un `if` improvisado: tiene que ser un estado persistido y un contrato hacia fuera. Y cada agente va a tener herramientas en la mano, lo que convierte una pregunta de arquitectura en una pregunta de **privilegio**: quién puede hacer qué, y qué pasa si intenta hacer más.

Esas cuatro preguntas —enrutado, comunicación, intervención humana y privilegio— son el resto del camino.