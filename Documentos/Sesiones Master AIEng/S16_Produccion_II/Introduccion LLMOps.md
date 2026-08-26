# Introducción LLMOps

Creada: 25 de agosto de 2026 8:10
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S16. Puesta en producción II - Calidad y observabilidad (https://app.notion.com/p/S16-Puesta-en-producci-n-II-Calidad-y-observabilidad-3c7ea9ca03c480a6a244e54a2f05e42a?pvs=21)

Cerrasteis la sesión anterior con una pequeña victoria legítima: el sistema de estimación desplegado en cloud, con su frontera público/privado, su pipeline y su smoke test en verde. El smoke test es importante, así que merece la pena mirar qué os dice exactamente. Os dice que el sistema está **vivo**: que `/health` responde, que una estimación de prueba recorre el flujo completo y vuelve con la forma correcta.

Lo que no os dice —lo que ningún smoke test os puede decir— es si esa estimación es **buena**.

Y esa es, de golpe, una pregunta incomodísima. Vuestro sistema desplegado le está devolviendo a un usuario "250 horas" para un proyecto, con toda la seguridad del mundo, y vosotros no tenéis forma de saber si esas 250 horas son un acierto razonable o una cifra que el modelo se ha inventado con aplomo. Está vivo y respondiendo, sí. Pero opera a ciegas, y vosotros con él.

Esta sesión trata de quitarle la venda. De pasar de "el sistema responde" a "el sistema responde bien, de forma segura, y a un coste que sé cuánto es". Ese conjunto de prácticas —operar un sistema de IA en producción con los ojos abiertos— es lo que se llama **LLMOps**. Y para entender por qué hace falta una disciplina nueva, hay que empezar por lo que la hace distinta de operar cualquier otro software.

## **El día que "no ha cambiado el código" deja de valer**

Durante toda vuestra carrera habéis operado sobre una garantía silenciosa, tan básica que ni la nombráis: **el mismo código se comporta igual**. Si nadie ha tocado el repositorio, el sistema de hoy hace exactamente lo que hacía ayer. Sobre esa garantía se construye todo lo que sabéis de operaciones: si algo cambia de comportamiento, es porque alguien cambió algo, y lo veréis en un diff. Si algo falla, falla ruidosamente —un crash, un test rojo, un 500—.

Un sistema con un LLM en el corazón rompe esa garantía por los dos lados.

Por un lado, el mismo código puede comportarse distinto sin que nadie toque nada. El proveedor actualiza el modelo por debajo, y vuestras estimaciones cambian de un día para otro sin un solo commit. Los datos del mundo derivan, y las estimaciones que eran buenas hace seis meses dejan de serlo. Un cambio mínimo en un prompt —una palabra— altera el comportamiento en casos que ni imaginabais. El diff ya no captura el cambio, porque el cambio no está en el diff.

Y por otro lado, cuando falla, **falla en silencio**. Un sistema clásico roto se cae y os enteráis. Un sistema de IA degradado sigue respondiendo tan campante: las estimaciones simplemente empiezan a ser peores, la factura de tokens crece un poco cada semana, la tasa de "me inventé un número" sube sin que salte ninguna alarma. No hay crash. No hay test rojo. Hay respuestas silenciosamente peores y un coste silenciosamente mayor, hasta que un cliente se queja o alguien mira la factura.

![articulo-16-1-diagrama-determinista-vs-no.png](https://media1-production-mightynetworks.imgix.net/asset/adcfe018-7b6b-4baa-a605-b2c09e1b64e0/articulo-16-1-diagrama-determinista-vs-no.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: operar software determinista frente a operar un sistema no determinista. En el primero, el comportamiento solo cambia si cambia el código, y los fallos son ruidosos; en el segundo, el comportamiento cambia solo y los fallos son silenciosos.*

Esta es la raíz de todo. LLMOps existe porque las herramientas de operaciones clásicas dan por supuesta una garantía que aquí no se cumple, y por tanto no ven la mayor parte de lo que puede ir mal.

## **Cuatro preguntas que el despliegue no responde**

Si el smoke test solo responde "¿está vivo?", conviene hacer explícitas las preguntas que deja abiertas, porque son exactamente las que dan forma a esta sesión.

**¿Es bueno?** ¿Las estimaciones aciertan? No de vez en cuando y a ojo, sino de forma medible, con una vara que no dependa de vuestra impresión de un martes.

**¿Sigue siendo bueno?** Aunque hoy acierte, ¿lo seguirá haciendo tras el próximo cambio de prompt, la próxima actualización del proveedor, el próximo mes de deriva de datos? ¿Os enteraríais si dejara de acertar?

**¿Es seguro?** ¿Se comporta de forma aceptable en los casos raros? ¿Reconoce cuándo no tiene datos suficientes en vez de inventar, escala a un humano cuando toca, cumple lo que la regulación espera?

**¿Cuánto cuesta?** ¿Sabéis lo que os cuesta cada respuesta? ¿Y si el coste se duplica el mes que viene, os daríais cuenta antes de la factura?

![articulo-16-1-diagrama-mapa-llmops.png](https://media1-production-mightynetworks.imgix.net/asset/9d218494-98c7-4251-ba87-678f336d5323/articulo-16-1-diagrama-mapa-llmops.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el mapa de LLMOps. Alrededor del sistema desplegado, las cuatro preocupaciones —seguridad, evaluación, observabilidad y coste— que el despliegue deja sin responder y que estructuran la sesión.*

Ninguna de estas cuatro la responde el hecho de estar desplegado. Un sistema puede estar perfectamente vivo y ser, a la vez, malo, cada vez peor, inseguro y ruinoso. Poner ojos a cada una de esas preguntas es de lo que trata el resto de la sesión.

## **LLMOps es una disciplina, no una herramienta**

Conviene desactivar una confusión antes de seguir, porque "LLMOps" suena a producto que se instala. No lo es. No hay una herramienta que compréis y os deje "hacer LLMOps", igual que no había una que os dejara "hacer producción" en la sesión anterior. Hay herramientas que ayudan —para trazar, para evaluar, para monitorizar—, pero son medios. LLMOps es la práctica de operar un sistema no determinista de forma **segura, medible, observable y sostenible en coste**, y de mantenerlo así en el tiempo.

Fijaos en que esto rima con lo que ya vivisteis. En la Sesión 15 dijimos que "producción" no era un lugar, sino un conjunto de promesas. LLMOps es la continuación natural de esa idea: una vez el sistema cumple las promesas de *estar bien desplegado*, aparecen las de *estar bien operado*. Y son promesas distintas, que las herramientas de siempre no cubren, porque se inventaron para un mundo determinista que aquí no existe.

La buena noticia, la misma que en la sesión anterior, es que debajo no hay magia. Medir, vigilar señales, poner límites de seguridad, controlar el gasto: son disciplinas de ingeniería que ya conocéis en otros contextos. Lo único nuevo es aplicarlas a un sistema cuyo comportamiento no está fijado en el código, y que por tanto hay que observar como se observa algo vivo, no como se audita algo inerte.

## **Lo que queda por decidir**

Tenéis, entonces, un sistema vivo y cuatro preguntas sin responder. El orden en que las atacaremos no es arbitrario, y merece la pena decir por dónde empezamos y por qué no es por donde parece.

Lo natural sería lanzarse a medir: "¿es bueno?", construir el golden set, sacar métricas. Pero hay una pregunta más básica que la de la calidad, y es la de la **seguridad**. Antes de preguntar si una estimación es buena, hay que garantizar que el sistema no hace algo directamente inaceptable: devolver una cifra con total confianza cuando no tiene ni un dato en que apoyarse, por ejemplo. Eso no es "una estimación un poco mala"; es un sistema que miente con seguridad, y ninguna métrica de acierto lo captura, porque el problema no es que falle el número, es que no debería haber dado un número.

Un sistema que no sabe decir "no lo sé" no es un sistema poco preciso: es un sistema en el que no se puede confiar. Por eso lo primero que LLMOps le exige a lo desplegado no es una métrica, sino un suelo de comportamiento seguro. Y de ese suelo —guardrails, incertidumbre, escalación a humanos y lo que la regulación espera— trata el siguiente tramo.