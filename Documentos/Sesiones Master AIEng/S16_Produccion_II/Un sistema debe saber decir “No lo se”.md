# Un sistema debe saber decir “No lo sé”

Creada: 25 de agosto de 2026 8:11
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S16. Puesta en producción II - Calidad y observabilidad (https://app.notion.com/p/S16-Puesta-en-producci-n-II-Calidad-y-observabilidad-3c7ea9ca03c480a6a244e54a2f05e42a?pvs=21)

Imaginad una petición cualquiera de las que le llegan a vuestro sistema en producción. Un usuario pega la transcripción de una reunión donde se habla, por encima, de integrar el producto con un ERP interno del que no existe documentación, ni precedentes, ni nada parecido en vuestra base de datos vectorial. El sistema hace lo que hace siempre: recupera, razona, genera. Y devuelve: **"180 horas. Confianza: alta."**

Esa respuesta es lo peor que puede producir vuestro sistema. No porque 180 sea un número equivocado —a lo mejor hasta acierta por casualidad—, sino porque no tenía ninguna base para darlo, y lo ha dado con aplomo. Alguien va a planificar un proyecto alrededor de esa cifra. Va a comprometer un presupuesto, una fecha, un equipo. Y lo va a hacer confiando en un número que el sistema se sacó de la nada con cara de seguridad.

En el artículo anterior dijimos que antes de preguntar "¿es bueno?" hay que preguntar "¿es seguro?". Este es el porqué. Un sistema de estimación que no sabe reconocer cuándo no tiene ni idea siempre va a decir algo, y "algo" dicho con confianza sobre nada es el fallo de seguridad central de un producto con IA. Antes de medir la calidad, hay que garantizar un suelo: que el sistema no haga daño con su propia seguridad.

## **El fallo que ninguna métrica de acierto ve**

Aquí hay una trampa sutil que conviene desactivar antes de seguir. Cuando en la siguiente sesión midamos la calidad, mediremos cosas como "¿cuánto se acerca la estimación al valor esperado?". Esas métricas son necesarias, pero tienen un punto ciego enorme: solo miran los casos en los que **sí** hay una respuesta. Miden lo cerca que está el número cuando debía haber un número.

El caso de las 180 horas no lo ven. Ahí el problema no es que el número esté lejos del correcto; es que no debería haber ningún número. Ninguna métrica de acierto captura "no deberías haber respondido esto", porque su pregunta es *cómo de bueno es el número*, no *si tocaba dar uno*.

Por eso la seguridad es un eje distinto de la calidad, y va primero. La calidad es la media: cómo de bien responde el sistema cuando responde. La seguridad es el suelo: que el sistema no se comporte de forma inaceptable en los casos difíciles, raros o sensibles. Un sistema puede tener una calidad media excelente y ser, a la vez, peligroso, porque su calidad media no dice nada de lo que hace cuando se sale de su terreno. Y en producción, tarde o temprano, todo se sale de su terreno.

## **Guardrails: dos filtros, no una frase en el prompt**

La primera herramienta para poner ese suelo son los **guardrails**: comprobaciones que rodean al modelo, una a la entrada y otra a la salida.

El **guardrail de entrada** mira lo que llega antes de que toque al modelo. ¿Es una petición dentro del alcance del sistema, o alguien está pidiendo algo que no es estimar? ¿Trae instrucciones inyectadas que intentan secuestrar el comportamiento ("ignora tus reglas y…")? ¿Contiene datos sensibles que no deberían acabar en un prompt? Lo que no pase el filtro se rechaza o se marca antes de gastar un token.

El **guardrail de salida** mira lo que el modelo produce antes de que llegue al usuario. ¿La respuesta tiene la estructura esperada —un `EstimateResponse` válido, con su confianza—? ¿Las fuentes que cita existen de verdad o se las ha inventado? ¿El número está dentro de límites razonables, o el sistema propone 4 horas para migrar una base de datos entera? Lo que no cuadre se bloquea o se corrige antes de salir.

![articulo-16-2-diagrama-guardrails.png](https://media1-production-mightynetworks.imgix.net/asset/17a46dff-3991-4953-884e-952325caf5c9/articulo-16-2-diagrama-guardrails.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: los guardrails como dos filtros deterministas, uno a la entrada y otro a la salida, que envuelven al modelo no determinista. Comprueban lo que entra y validan lo que sale.*

Y aquí está la idea que más se malentiende: **un guardrail es código, no una frase en el prompt.** Escribir en el system prompt "por favor, no te inventes las fuentes" no es un guardrail; es un deseo. El modelo no determinista puede ignorarlo cuando le convenga. Un guardrail de verdad es una comprobación determinista —código que se ejecuta siempre, pase lo que pase con el modelo— que verifica que las fuentes citadas existen en vuestra base de datos y bloquea la respuesta si no. La gracia del guardrail es precisamente que no depende del modelo: es el trozo predecible que ponéis alrededor del trozo impredecible.

## **El derecho a decir "no lo sé"**

Los guardrails atrapan lo que está claramente mal. Pero el caso de las 180 horas es más sutil: la respuesta tiene la forma correcta, las fuentes podrían incluso existir, el número está dentro de límites. Lo que falla es más profundo: el sistema no debería haber tenido tanta confianza. Y para eso hace falta algo más que un filtro: hace falta que el sistema tenga **un camino explícito para reconocer que no sabe.**

En vuestro sistema de estimación eso es muy concreto. Cuando la recuperación devuelve precedentes pobres o inexistentes, o la confianza cae por debajo de un umbral, la respuesta correcta no es un número: es **"no tengo datos suficientes para estimar esto con fiabilidad".** Esa frase no es un fallo del sistema; es el sistema funcionando bien. Un producto que puede decirla es un producto en el que se puede confiar, precisamente porque no dice siempre que sí.

Reconocer que no se sabe abre tres caminos, y elegir bien entre ellos es el corazón de la seguridad:

**Responder**, cuando hay base suficiente: la estimación, con su confianza y sus fuentes.

**Abstenerse con honestidad** —lo que se llama *safe-completion*—, cuando no la hay: en vez de callar o inventar, el sistema da una respuesta parcial y útil ("no puedo estimar esto de forma fiable; para hacerlo necesitaría precedentes de integraciones similares o una descripción más detallada del alcance"). Reconoce el límite y, de paso, dice qué haría falta para superarlo.

**Escalar a un humano**, cuando el caso es sensible o de alto impacto: no todo lo que el sistema no puede resolver debe quedarse en una abstención. Una estimación que va a mover mucho dinero, o un caso que roza terreno delicado, merece pasar a revisión humana antes de llegar al usuario. La intervención humana no es un parche por si acaso; es un estado más del sistema, decidido a propósito.

![articulo-16-2-diagrama-incertidumbre.png](https://media1-production-mightynetworks.imgix.net/asset/9957d2d1-4618-4a47-848c-ebd9d55be370/articulo-16-2-diagrama-incertidumbre.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: ante cada petición, el sistema decide entre tres caminos —responder, abstenerse con honestidad, o escalar a un humano— según la confianza y la sensibilidad del caso.*

Fijaos en que esto no es magia de IA: es diseño de producto. Estáis decidiendo, como decisión de ingeniería, qué hace vuestro sistema cuando no está seguro. Y lo estáis decidiendo vosotros, en código, no dejándolo al azar de lo que el modelo tenga a bien contestar.

## **Compliance-by-design: la regulación no es un trámite del final**

Todo lo anterior desemboca, casi sin querer, en la parte que suena a abogados: el cumplimiento normativo. En Europa, un producto con IA opera bajo un marco —el que articula la regulación europea de IA— construido sobre unos cuantos principios que, a día de hoy, son estables aunque los plazos y detalles concretos sigan moviéndose: un enfoque basado en el **riesgo** (a más impacto, más obligaciones), la **transparencia** (el usuario debe saber que interactúa con un sistema de IA y conocer sus límites), la **supervisión humana** y la **trazabilidad** (poder documentar y reconstruir por qué el sistema hizo lo que hizo).

*Compliance-by-design* significa que esos principios se construyen dentro del sistema desde el diseño, no se atornillan al final para pasar una auditoría. Y aquí viene la buena noticia, que rara vez se cuenta: casi todo lo que os hace cumplir es lo mismo que os hace seguros y buenos. Que el sistema sepa abstenerse es transparencia sobre sus límites. Que escale a un humano es supervisión humana. Que registréis cada estimación con sus fuentes y su confianza —la trazabilidad del artículo de documentación de la sesión anterior— es exactamente lo que un marco de IA responsable espera que podáis mostrar. No es un impuesto separado; es el mismo trabajo, mirado desde el ángulo legal.

Un aviso práctico, eso sí: el detalle regulatorio concreto —qué obligación aplica a qué sistema y desde cuándo— es un blanco en movimiento, con plazos que se están ajustando. Al preparar la sesión conviene contrastar los específicos con la fuente oficial vigente en ese momento. Los principios que acabamos de ver son la parte que no cambia; las fechas y los umbrales, la que sí.

## **Lo que queda por decidir**

Con guardrails, un camino explícito para la incertidumbre y los principios de cumplimiento metidos en el diseño, vuestro sistema tiene por fin un **suelo**: no hará algo inaceptable, sabrá decir que no sabe, y podréis defender cómo se comporta. Eso es la seguridad, y era lo primero porque sin ese suelo cualquier otra virtud da igual.

Pero "seguro" no es "bueno". Un sistema puede no hacer nunca nada peligroso y, a la vez, dar estimaciones mediocres una tras otra. El suelo evita el desastre; no garantiza la calidad. Y la calidad, ya lo avisamos, no se puede juzgar a ojo un martes por la tarde: "me parece que ahora responde mejor" no es una métrica.

Así que la siguiente pregunta, una vez asegurado el suelo, es cómo se mide de verdad si el sistema es bueno. Y para responderla hace falta construir una vara: un conjunto de referencia contra el que comparar. De eso —de dejar de opinar sobre la calidad y empezar a medirla— trata el siguiente tramo.