# Evaluacion en producción

Creada: 25 de agosto de 2026 8:11
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S16. Puesta en producción II - Calidad y observabilidad (https://app.notion.com/p/S16-Puesta-en-producci-n-II-Calidad-y-observabilidad-3c7ea9ca03c480a6a244e54a2f05e42a?pvs=21)

Cambiáis una palabra en el prompt de estimación. Lanzáis tres o cuatro transcripciones de prueba, de esas que tenéis a mano. Miráis las respuestas: sí, se ven mejor. Más ajustadas, más razonables. Desplegáis con la tranquilidad del que ha comprobado que su cambio funciona.

Acabáis de tomar una decisión de producto basada en nada.

No es una exageración. "Se ven mejor" en tres o cuatro casos que vosotros habéis elegido no es una comprobación: es un sesgo de confirmación con pasos intermedios. Elegisteis los casos, los mirasteis con ganas de que el cambio funcionara, y encontrasteis lo que buscabais. Si el cambio hubiera empeorado el sistema en veinte casos que no se os ocurrió probar, esas cuatro respuestas bonitas os habrían tranquilizado igual.

En el artículo anterior le pusimos al sistema un suelo de seguridad. Ahora toca la otra pregunta: ¿es **bueno**? Y la respuesta empieza por aceptar algo incómodo: vuestra intuición, por buena que sea, no puede responderla. Para saber si un sistema no determinista es bueno hace falta dejar de mirarlo y empezar a medirlo. Este artículo trata de construir la vara.

## **Por qué el ojo no sirve para medir calidad**

Que quede claro por qué la evaluación a ojo falla, porque no es cuestión de mirar con más cuidado. Falla por tres motivos estructurales, y ninguno se arregla con buena voluntad.

**Probáis los casos que se os ocurren, que son los que el sistema ya hace bien.** Cuando elegís ejemplos de prueba a mano, elegís los que tenéis en la cabeza, y los que tenéis en la cabeza son los representativos, los de manual. Justo los que el sistema domina. Los casos donde falla son, por definición, los que no se os ocurren —si se os ocurrieran, ya los habríais tenido en cuenta al construirlo—.

**El sistema no es determinista, así que "se veía mejor" puede ser suerte.** La misma transcripción puede dar respuestas distintas en dos ejecuciones. Esa respuesta bonita que os convenció a lo mejor no se repite a la siguiente. Juzgar un sistema estocástico por una tirada es como juzgar un dado por un lanzamiento.

**No tenéis contra qué comparar.** "Responde mejor" mejor ¿que qué? Sin un punto de referencia fijo, "mejor" es una sensación relativa a vuestro recuerdo de la última vez, que es un recuerdo poco fiable. No hay línea base, así que no hay medida, solo impresión.

La conclusión es dura pero libera: no vais a poder confiar en vuestro criterio para esto, igual que un laboratorio no confía en el ojo para pesar. Necesitáis un instrumento. Y el instrumento es un conjunto de referencia fijo.

## **El golden test set: vuestra definición de "bueno", escrita**

Un **golden test set** es un conjunto de casos de referencia en los que vosotros —no el modelo— habéis decidido de antemano cuál es una buena respuesta. Es la vara de medir: fija, escrita, la misma cada vez.

Para vuestro sistema de estimación, cada caso lleva una entrada —una transcripción o descripción de tarea— y la respuesta que vosotros consideráis buena: una estimación esperada, y sobre todo un **rango aceptable**, porque una estimación no es una cifra exacta sino un intervalo razonable. Decir que un caso "de 8 puntos" pasa si el sistema responde entre 5 y 13 es codificar vuestro criterio de qué cuenta como acierto.

![articulo-16-3-diagrama-golden-set.png](https://media1-production-mightynetworks.imgix.net/asset/7abdc1ed-615f-4d12-bb66-c1984e57ad1d/articulo-16-3-diagrama-golden-set.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: la anatomía de un caso del golden set. Una entrada y la respuesta que vosotros habéis decidido que es buena —incluido, cuando toca, que la respuesta buena sea abstenerse.*

Dos cosas hacen que un golden set valga de verdad. La primera es que cubra **dificultades distintas**: un caso fácil y frecuente, uno de esfuerzo medio-alto, uno de borde. Si solo metéis casos de manual, medís lo que el sistema ya hacía bien y volvéis al punto ciego del ojo. La segunda, y aquí conecta con el artículo anterior, es que incluya al menos un **caso de abstención**: una entrada sin precedentes, donde la respuesta correcta no es un número sino "no tengo datos suficientes". Medir eso es medir la seguridad del sistema como parte de su calidad. Un sistema que acierta mucho pero nunca sabe abstenerse no es bueno; es un buen adivino, que no es lo mismo.

Lo esencial del golden set es *cuándo* decidís qué es bueno: **antes**, en frío, con criterio, y no caso a caso en el calor de un despliegue. Cuando la definición de "bueno" está escrita de antemano, deja de estar a merced de vuestras ganas de que el cambio funcione.

## **El harness: medir sin opinar**

El golden set es la vara; el **evaluation harness** es lo que mide con ella. Es el programa que coge cada caso del set, se lo lanza al servicio IA desplegado, compara la respuesta con lo que esperabais y agrega el resultado en un puñado de números.

La comparación es mecánica, y ahí está su virtud: no opina. Un caso de estimación pasa si la respuesta cae dentro del rango aceptable. Un caso de abstención pasa si el sistema efectivamente se abstuvo. No hay "me parece"; hay "cae en rango" o "no cae".

![articulo-16-3-diagrama-harness.png](https://media1-production-mightynetworks.imgix.net/asset/17a05b3b-66dd-4eb5-90f8-dfc57c98b225/articulo-16-3-diagrama-harness.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el harness ejecuta el golden set contra el servicio IA desplegado —llamando al modelo de verdad—, compara cada respuesta con lo esperado y agrega el resultado en métricas.*

Aquí hay un detalle que enlaza con la sesión anterior y que conviene no pasar por alto. En la Sesión 15 dijimos que en CI **no** se llama al modelo, que se mockea. El harness de evaluación es justo lo contrario: **sí** llama al modelo real, porque su trabajo no es testear vuestro código, es evaluar al modelo. Son las dos caras de la misma moneda que ya distinguimos: testear (vuestro código, determinista, mockeando el modelo, en cada commit) y evaluar (el modelo, no determinista, llamándolo de verdad, de forma deliberada). El harness vive en el lado de evaluar, y por eso no corre en cada push, sino cuando queréis saber cómo de bueno es el sistema.

Lo que os devuelve el harness es lo que convierte la conversación: en lugar de "me parece que responde mejor", tenéis "el 72% de las estimaciones cae en rango, el error medio es de 3 puntos, y abstiene correctamente en los casos sin datos". Eso ya no es una impresión. Es una medida, que se puede comparar, discutir y mejorar.

## **Un golden set es tan bueno como el criterio que hay detrás**

Una advertencia para que no os llevéis una falsa sensación de rigor. El harness es implacable comparando, pero solo compara contra lo que vosotros pusisteis. Si las estimaciones esperadas del golden set son inventadas a ojo, tenéis una máquina que mide con precisión contra una vara torcida. *Garbage in, garbage out* también aplica aquí: basad los valores esperados en los datos históricos reales que pobláis en la base de datos vectorial, no en una corazonada.

Y pensad el golden set como algo **vivo**, no como un fichero que se escribe una vez. Cada vez que el sistema falle en producción de una forma que no teníais cubierta, ese fallo se convierte en un caso nuevo del set. Así la vara crece justo por donde el sistema os ha demostrado que es débil. Un golden set pequeño pero honesto y creciente vale infinitamente más que uno grande hecho a ojo de una tacada.

## **Lo que queda por decidir**

Con el golden set y el harness ya no dependéis del ojo: podéis poner un número a cómo de bueno es el sistema en un momento dado. Es un salto enorme respecto a "me parece". Pero fijaos en la trampa que aún queda: una medida aislada dice cómo está el sistema hoy, no si vuestro próximo cambio lo mejora o lo empeora.

Y ese es, en realidad, el uso más valioso de todo esto. El verdadero peligro no es tener un sistema mediocre y saberlo; es tener uno bueno y estropearlo sin enteraros, con un cambio de prompt que arregla el caso que teníais delante y rompe otros diez que no estabais mirando. Para cazar eso hace falta comparar medidas a lo largo del tiempo, no una sola: es lo que se llama regression testing, y trae consigo la pregunta de qué números, exactamente, merece la pena vigilar.

De detectar que el sistema se degrada —y de los KPIs que lo delatan— trata el siguiente tramo.