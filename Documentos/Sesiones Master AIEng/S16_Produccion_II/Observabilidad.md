# Observabilidad

Creada: 25 de agosto de 2026 8:13
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S16. Puesta en producción II - Calidad y observabilidad (https://app.notion.com/p/S16-Puesta-en-producci-n-II-Calidad-y-observabilidad-3c7ea9ca03c480a6a244e54a2f05e42a?pvs=21)

El golden set está en verde. La última evaluación fue buena, los KPIs aguantan, el regression testing no saltó con el último cambio. Dormís tranquilos.

Y mientras dormís, en producción un usuario pega una transcripción rarísima que a vosotros no se os habría ocurrido en la vida, el sistema tarda doce segundos en responderla, el coste por petición se triplica durante unas horas porque el modelo se pone a razonar de más, y una tanda de peticiones parecidas empieza a recibir estimaciones malas. Os enteráis tres días después, por la factura o por un cliente enfadado.

El laboratorio no os mintió. El sistema *era* bueno la última vez que lo mirasteis, con vuestros casos. Lo que pasa es que el laboratorio no estaba mirando la producción, y la producción es otro sitio: allí hay usuarios reales mandando entradas que nunca imaginasteis, a todas horas, os miréis o no. En el artículo anterior aprendimos a medir el sistema cuando nosotros lanzamos la evaluación. Este trata de vigilarlo cuando no la lanzamos: en vivo, con el tráfico de verdad. Eso es la **observabilidad**.

## **Evaluación mira dentro; observabilidad mira fuera**

Conviene separar bien las dos cosas, porque se confunden y son complementarias, no intercambiables.

La **evaluación** —el golden set, el harness— es la prueba de laboratorio. Vosotros elegís las entradas, vosotros ponéis la vara, y la lanzáis cuando queréis. Es controlada, repetible y responde a una pregunta muy concreta: "¿es bueno el sistema *en mis casos*?". Su fuerza es que compara contra un patrón fijo; su límite es que solo ve lo que vosotros metisteis en el patrón.

La **observabilidad** es el monitor de constantes vitales. No elegís las entradas —las manda el mundo—, no hay vara, y no se lanza: está siempre puesta, pasiva, escuchando. Responde a otra pregunta: "¿qué está haciendo el sistema *ahora mismo*, con el tráfico real?". Su fuerza es que ve la realidad tal cual llega; su límite es que no juzga la calidad contra un ideal, solo muestra lo que ocurre.

Necesitáis las dos. La evaluación caza las regresiones antes de desplegar; la observabilidad caza lo que la evaluación no pudo imaginar, después de desplegar. Una os protege de vuestros propios cambios; la otra, de la realidad.

## **Las señales que se vigilan**

Observar no es registrarlo todo y mirar un mar de logs. Es elegir un puñado de **señales** que delatan un problema antes de que lo haga un cliente, y ponerlas donde se vean de un vistazo. Para vuestro sistema de estimación, las imprescindibles:

**Latencia**, y no solo la media: la media engaña, porque esconde a la minoría que sufre. El p95 —lo que experimenta el 5% más lento— es el que dice si hay usuarios esperando una eternidad.

**Coste por petición.** Es la señal del sube-y-baja silencioso del que hablábamos al principio de la sesión. Una petición que empieza a costar el triple no rompe nada; solo engorda la factura, calladita, hasta que alguien la mira. Verla en tiempo real es lo que convierte esa sorpresa en un aviso.

**Tasa de error.** La proporción de peticiones que no acaban bien: timeouts, 503, respuestas que el guardrail de salida bloquea. Es la señal más clásica y la que antes salta cuando algo se cae.

**Señales de calidad y de usuario.** Más sutiles, y muy valiosas. La tasa de abstención: si de repente el sistema abstiene mucho más que ayer, algo ha cambiado —quizá los datos han derivado—. Los pulgares abajo, los reintentos, los usuarios que reformulan tres veces: son la voz del usuario diciéndoos que la calidad bajó, sin que ningún error salte.

![articulo-16-5-diagrama-dashboard.png](https://media1-production-mightynetworks.imgix.net/asset/e325f44c-f9f2-45d3-a2a4-dedf5d59af44/articulo-16-5-diagrama-dashboard.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el dashboard de producción. Unas pocas señales —latencia p95, coste por petición, tasa de error y señales de calidad— puestas donde se ven de un vistazo, con alertas cuando cruzan un umbral.*

Un dashboard es esas señales juntas y a la vista; las alertas son el dashboard avisándoos sin que tengáis que estar mirándolo. Porque la gracia no es tener los números, es que los números os llamen cuando se tuercen.

## **El trace: por qué una petición tardó lo que tardó**

El dashboard os dice **que** la latencia se disparó. No os dice **dónde**. Y en un sistema RAG, "dónde" es la mitad del problema, porque una petición pasa por varias etapas y cualquiera puede ser la culpable.

Para eso está el **trace**: el desglose de una petición en sus tramos, cada uno con su tiempo y su coste. Una estimación no es una caja negra que tarda 4 segundos; es un embedding de la consulta, más una búsqueda en la base de datos vectorial, más una generación del LLM. El trace os enseña cuánto se fue en cada tramo, y con eso pasáis de "las estimaciones van lentas hoy" a "la recuperación es el cuello de botella desde que creció la base vectorial". Lo primero es una queja; lo segundo, un diagnóstico.

![articulo-16-5-diagrama-trace.png](https://media1-production-mightynetworks.imgix.net/asset/1f9ea5ab-28c8-49c7-8ee3-7db1f6d83310/articulo-16-5-diagrama-trace.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el trace de una petición de estimación, desglosado por tramos —embedding, recuperación, generación— con el tiempo y el coste de cada uno. El dashboard dice que algo va lento; el trace dice dónde.*

Aquí es donde entran las herramientas que ya visteis en la Sesión 13. **Langsmith** y **Logfire** están hechas precisamente para esto: instrumentan el flujo RAG y las llamadas al LLM y os dan las trazas casi sin trabajo, con sus tiempos, sus tokens y su coste por tramo. No hace falta construir el trazado desde cero; hace falta saber qué buscáis en él.

## **Feedback loops: lo que se observa vuelve al sistema**

Hay un último giro, y es el que separa observar de vigilar por vigilar. La observabilidad no termina en el dashboard: **cierra un bucle**. Lo que veis en producción vuelve a mejorar el sistema.

La producción es, resulta, la mejor fuente de casos nuevos que tenéis. Esa entrada rarísima que hizo tardar doce segundos y devolvió una mala estimación es, exactamente, un caso que le faltaba a vuestro golden set —el golden set vivo del que hablamos en el artículo de evaluación, que crece justo por donde el sistema demuestra ser débil—. La subida en la tasa de abstención os avisa de una deriva de datos que toca reindexar. Los pulgares abajo señalan un fallo de calidad que vuestros casos no cubrían. El sistema, si lo observáis, os va enseñando dónde es flojo; el bucle consiste en recoger eso y devolverlo a la evaluación y a los datos.

Y un recordatorio que enlaza con el despliegue de la sesión anterior: todo esto —comprobar que el modelo responde con calidad, medir su coste, vigilar su latencia— es trabajo del dashboard y de las trazas, **no del health check**. El `/health` sigue siendo barato y tonto, solo dice "estoy vivo". La calidad de lo que está vivo se mira aquí. No confundáis el latido con la vigilancia.

## **Lo que queda por decidir**

Con la observabilidad puesta, por fin veis el sistema entero: si es bueno (evaluación), si sigue siéndolo (regresión), si se comporta (seguridad) y, ahora, qué hace de verdad en producción. Las cuatro preocupaciones del mapa del primer artículo, cubiertas.

Pero ver tiene una consecuencia incómoda: ahora que veis el coste por petición y el tiempo de cada tramo, es imposible no notar que son **más altos de lo que deberían**. El modelo más grande contestando hasta las preguntas triviales, cada petición recalculando lo que ya se calculó hace un minuto, prompts inflados que gastan tokens de más. La observabilidad os ha puesto delante la factura y el reloj; el siguiente paso es bajarlos sin estropear la calidad.

Y ahí aparece el último problema de la sesión: ¿cómo sabéis que la versión más barata y más rápida sigue siendo lo bastante buena? No basta con optimizar; hay que **demostrar** que la optimización no os costó calidad. Optimizar latencia y coste, y probar con A/B testing que la versión nueva gana, es la última decisión del camino —y con ella se cierra el recorrido del sistema en producción—.