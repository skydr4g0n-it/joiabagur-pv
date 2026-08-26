# Tratamiento de regresiones

Creada: 25 de agosto de 2026 8:12
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S16. Puesta en producción II - Calidad y observabilidad (https://app.notion.com/p/S16-Puesta-en-producci-n-II-Calidad-y-observabilidad-3c7ea9ca03c480a6a244e54a2f05e42a?pvs=21)

Un usuario se queja: las estimaciones para tareas de autenticación se le quedan cortas. Miráis, tiene razón, el sistema tiende a infravalorar ese tipo de trabajo. Ajustáis el prompt para que sea más conservador con la autenticación. Comprobáis ese caso: arreglado, ahora estima bien. Desplegáis, problema resuelto, a otra cosa.

Lo que no habéis visto es que ese mismo ajuste ha vuelto peores las estimaciones de las migraciones de datos. Y las de las integraciones. Y las de media docena de tipos de tarea que ni tocasteis, porque no estabais mirando. Arreglasteis un caso y rompisteis diez, y os habéis ido tan tranquilos, porque solo mirasteis el que veníais a arreglar.

Esto es una **regresión silenciosa**, y es la forma más común y más traicionera en que un sistema de IA bueno se estropea. En el artículo anterior conseguisteis medir la calidad en un momento dado. Este trata de un uso mucho más valioso de esa medición: detectar cuándo un cambio, que parece una mejora, es en realidad un retroceso.

## **Por qué arreglar un caso empeora otros**

Para entender por qué pasa esto —y por qué es tan fácil que pase— hay que ver en qué se diferencia tocar un prompt de tocar código normal.

Cuando cambiáis una función en vuestro backend de negocio, el efecto está acotado: esa función hace algo distinto, y lo que no la llama, ni se entera. El cambio es local porque el código es modular. Podéis razonar sobre el radio de impacto: "toco esto, afecta a esto".

Un prompt no funciona así. El prompt no es un módulo con una responsabilidad; es una instrucción global que condiciona **todo** lo que el modelo hace. Cuando lo empujáis para que sea más conservador con la autenticación, no estáis tocando "la parte de autenticación" —no existe tal parte—. Estáis desplazando el comportamiento entero del modelo, y ese desplazamiento se nota en cosas que no tenían nada que ver con lo que queríais arreglar. El radio de impacto de un cambio de prompt no es el caso que tocáis: es el sistema completo.

Esto tiene una consecuencia que conviene interiorizar: **"he arreglado el bug" nunca significa "no he creado otros".** En software determinista, esas dos frases van casi de la mano; con un modelo, están divorciadas. Podéis haber arreglado exactamente lo que queríais y, a la vez, haber degradado el sistema en su conjunto. Y si solo miráis el caso que arreglabais, no hay forma de que lo sepáis.

## **Regression testing: no miréis el caso, mirad el conjunto**

La solución cae por su propio peso una vez visto el problema. Si un cambio afecta a todo el sistema, no podéis juzgarlo mirando un caso: tenéis que mirar **todo el conjunto**. Y eso es exactamente lo que el golden set y el harness os permiten hacer.

Regression testing es esto: después de cualquier cambio —un prompt, un modelo nuevo, datos reindexados— ejecutáis el golden set entero y comparáis el resultado con el de antes del cambio. La pregunta no es "¿arreglé el caso de autenticación?", sino "¿está el sistema, en su conjunto, mejor o peor que antes?". Y esa pregunta se responde con números que ya tenéis: ¿subió o bajó la tasa de aciertos? ¿Algún caso que pasaba ahora falla?

![articulo-16-4-diagrama-regresion.png](https://media1-production-mightynetworks.imgix.net/asset/41f59b2c-991d-494c-a908-ae37f7290b1f/articulo-16-4-diagrama-regresion.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: una regresión silenciosa. El cambio arregla el caso que mirabais, pero varios que pasaban ahora fallan, y la tasa de aciertos del conjunto baja. Sin comparar contra la medición anterior, no lo veríais.*

Aquí está el verdadero valor del harness, el que anunciamos al final del artículo anterior. Su utilidad no es darte *una* medición —"el sistema acierta el 72%"—, sino permitir *comparar* mediciones: "antes acertaba el 80%, con tu cambio acierta el 60%". Una medición aislada te dice cómo está el sistema; la comparación te dice si tu cambio ayuda o hace daño. Por eso conviene guardar el informe de cada ejecución: la serie de mediciones es lo que convierte el harness en una red de seguridad. Sin la línea base anterior, "60%" no significa nada; contra el "80%" de ayer, es una alarma.

La regla de bolsillo:

> Un cambio no se juzga por el caso que arregla, sino por lo que le hace al conjunto.
> 

## **Qué medir: los KPIs del sistema**

Hasta ahora hemos hablado de "aciertos" como si la calidad fuera un solo número. No lo es. Un sistema de estimación puede fallar de varias maneras distintas, y cada una pide su propia métrica. Los KPIs son ese puñado de números que, juntos, dan la foto completa del sistema.

Cuatro que no deberían faltar:

**Acierto** (la tasa de estimaciones dentro del rango). ¿El sistema da buenas cifras cuando da cifras? Es la métrica más obvia, y la que ya calcula vuestro harness.

**Tasa de alucinación.** ¿El sistema se inventa cosas: fuentes que no existen, cifras sin ningún apoyo en los datos? Esta métrica caza el fallo del artículo 2 —el número con aplomo y sin base— que la tasa de acierto por sí sola no ve.

**Cumplimiento de seguridad.** ¿El sistema abstiene y escala cuando debe? Mide si el suelo de seguridad se mantiene: un sistema que empieza a responder en casos donde debería abstenerse se está degradando, aunque sus aciertos no bajen.

**Latencia.** ¿Responde a tiempo? Un sistema que acierta perfectamente pero tarda veinte segundos es, para el usuario, un sistema roto.

![articulo-16-4-diagrama-kpis.png](https://media1-production-mightynetworks.imgix.net/asset/77db5ff7-f164-4475-bf86-43ddaf74403b/articulo-16-4-diagrama-kpis.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el cuadro de KPIs del sistema. Cada métrica caza un tipo de fallo distinto —cifras flojas, invenciones, inseguridad, lentitud— y por eso se vigilan juntas.*

Para la parte específica de RAG hay atajos: frameworks como **RAGAS**, que ya visteis en la Sesión 11, os dan métricas de calidad de recuperación y generación hechas —fidelidad a las fuentes, relevancia de la respuesta, precisión del contexto— sin que tengáis que inventarlas. No hace falta construir toda la vara desde cero cuando parte ya existe.

## **El cambio que mejora una métrica y hunde otra**

Que los KPIs sean varios no es un detalle administrativo: es que **se mueven unos contra otros**, y ahí está la miga de operar el sistema. Reescribís el prompt para reducir las alucinaciones y, de paso, el sistema se vuelve tan cauto que abstiene de más y baja el acierto. Cambiáis a un modelo más grande y la precisión sube, pero la latencia y el coste también. Casi ninguna decisión mejora todo a la vez; la mayoría son intercambios.

Por eso no existe "el número" del sistema, y desconfiad de quien lo busque. Existe un equilibrio entre varios KPIs que **vosotros** decidís según lo que vuestro producto necesita: cuánta precisión estáis dispuestos a cambiar por cuánta velocidad, cuánta cobertura por cuánta seguridad. El regression testing sobre todos los KPIs a la vez es lo que hace ese intercambio **visible** en lugar de accidental: veis, con números, que vuestro cambio subió una métrica y hundió otra, y decidís a sabiendas si compensa. Sin esa foto, el intercambio ocurre igual, pero a ciegas.

## **Lo que queda por decidir**

Con regression testing y un cuadro de KPIs, ya no solo sabéis si el sistema es bueno: sabéis si sigue siéndolo después de cada cambio, y qué estáis intercambiando cuando lo tocáis. Es la diferencia entre mejorar el sistema y manosearlo con la esperanza de que salga bien.

Pero fijaos en una limitación de todo esto, y no es pequeña: mide el sistema **cuando vosotros lanzáis la evaluación**, con **vuestro** golden set, en el laboratorio. Y el laboratorio, por bueno que sea, no es la producción. En producción hay usuarios reales mandando entradas que a vosotros no se os ocurrieron nunca, a todas horas, mientras dormís. El golden set os dice que el sistema era bueno la última vez que lo mirasteis; no os dice qué está pasando *ahora mismo*, con el tráfico de verdad.

Para eso hace falta dejar de sacar fotos en el laboratorio y empezar a vigilar el sistema vivo. Ver qué hace en producción, en tiempo real, con las señales que delatan un problema antes de que lo haga un cliente enfadado: eso es observabilidad, y es el siguiente tramo.