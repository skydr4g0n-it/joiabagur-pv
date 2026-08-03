# Documentar el sistema

Creada: 1 de agosto de 2026 12:04
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S15. Puesta en producción de proyectos, arquitectura e infra (https://app.notion.com/p/S15-Puesta-en-producci-n-de-proyectos-arquitectura-e-infra-3afea9ca03c4806d8222e1ade89cf01f?pvs=21)

Acabáis de conseguir que el sistema de estimación arranque con un comando. `docker compose up` levanta las tres capas, se hablan entre ellas por la red interna, una transcripción entra y sale una estimación con su confianza y sus fuentes. Es reproducible: en vuestra máquina, en la de un compañero, en un servidor, arranca igual.

Y aun así, si os vais de vacaciones dos semanas, el sistema no está a salvo.

Porque reproducible no es lo mismo que operable. Un `Dockerfile` captura cómo se construye una imagen; no captura por qué el servicio IA está separado del backend de negocio, ni qué hacer cuando a las tres de la madrugada deja de responder, ni cómo se interpreta una estimación que llega con confianza 0.4. Todo eso lo sabéis. El problema no es que no esté decidido: el problema es *dónde* está. Está en vuestra cabeza, y ahí no lo puede leer la persona de guardia, ni el compañero que entra el mes que viene, ni vosotros mismos dentro de seis meses, cuando ya se os haya olvidado.

Este artículo trata de esa extracción. De sacar el sistema de vuestra cabeza y ponerlo en un sitio donde otro lo pueda operar. Que es, exactamente, la promesa que quedó pendiente en el artículo anterior: un sistema en producción tiene que ser operable por quien no lo escribió. La documentación es cómo se cumple esa promesa.

## **Por qué casi toda la documentación es mala**

Antes de decir cómo se hace bien, conviene entender por qué se hace mal, porque el error es casi siempre el mismo. La documentación mala nace de tratar "documentar el proyecto" como una tarea única e indiferenciada: un documento grande, escrito de una vez, para nadie en particular. Y un documento para nadie en particular no lo lee nadie en particular, y no lo mantiene nadie en particular. Nace muerto.

El giro que lo arregla es dejar de preguntar "¿está documentado?" y empezar a preguntar **"¿quién lo va a leer, y en qué momento?"**. Porque la respuesta a esa pregunta no es una. Son tres, y cada una pide un documento distinto.

## **Tres lectores, tres documentos**

Vuestro sistema tiene tres audiencias, y las tres leen en momentos muy distintos, con la cabeza en sitios muy distintos.

Está **quien desarrolla o integra**. Lee mientras construye: cuando el compañero de backend de negocio tiene que llamar al servicio IA y necesita saber qué endpoint, qué payload, qué le va a devolver y qué pasa si algo falla. Lee con el editor abierto y prisa por conectar su pieza. Lo que necesita es documentación **técnica**: la arquitectura de las tres capas, el contrato entre ellas, los modelos de datos, el recorrido de una estimación.

Está **quien opera**. Lee durante una incidencia, con el sistema caído y la adrenalina alta. No quiere entender la arquitectura: quiere saber qué comando ejecutar para que vuelva a funcionar. Lo que necesita es documentación **operativa**: runbooks, procedimientos, a quién escalar.

Y está **quien usa** el sistema. Lee —si lee— mientras pide una estimación. No le importa Docker ni el contrato REST; le importa qué puede pedir y cómo interpretar lo que recibe. Lo que necesita es documentación de **usuario**.

![articulo-15-2-diagrama-tres-lectores.png](https://media1-production-mightynetworks.imgix.net/asset/d8e40e80-df84-49ad-9eae-f5e20ac0d1f6/articulo-15-2-diagrama-tres-lectores.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: cada tipo de documentación responde a un lector y a un momento distintos. Un documento que intenta servir a los tres no sirve bien a ninguno.*

La consecuencia práctica es liberadora: no tenéis que escribir "la documentación" como un monolito imposible. Tenéis que escribir tres cosas pequeñas y bien dirigidas. Y una de las tres, la más valiosa, casi no hay que escribirla.

## **La documentación que sale del código no se muere**

Toda documentación tiene un enemigo común, y no es la pereza: es el tiempo. Lo que documentáis hoy es correcto hoy. Dentro de tres semanas alguien cambia un campo del payload, no toca el documento, y ya tenéis documentación que miente. Y una documentación que miente es peor que ninguna, porque la gente le hace caso.

Por eso la mejor documentación técnica es la que **no escribís**: la que el código genera y mantiene por vosotros. Y aquí FastAPI os hace un regalo que conviene no desperdiciar. Si definís los endpoints del servicio IA con modelos Pydantic —el `EstimateRequest` que entra, el `EstimateResponse` que sale— FastAPI genera un esquema OpenAPI y una interfaz navegable en `/docs` sin que escribáis una línea de documentación. El contrato del servicio IA se describe a sí mismo, y cuando cambiáis el modelo, la documentación cambia con él, porque *es* el modelo. No puede desincronizarse.

El mismo principio se aplica más allá de la API. Los diagramas de arquitectura pueden vivir como código (Mermaid, PlantUML) versionados junto al repositorio, de modo que un cambio en la arquitectura y un cambio en su diagrama viajen en el mismo commit. La regla de bolsillo:

> Automatizad todo lo que se pueda pudrir. Escribid a mano solo lo que no se puede generar.
> 

Y lo que no se puede generar es justamente lo más humano: **el porqué**. Ningún esquema OpenAPI explica por qué separasteis el servicio IA, por qué elegisteis búsqueda síncrona, por qué el token de servicio en vez de exponerlo. Esas decisiones —el tipo de cosa que alguien cuestionará dentro de un año sin acordarse del contexto— hay que escribirlas a mano, y merecen su sitio: un registro breve de decisiones de arquitectura, cada una con su motivo. No documentáis qué hace el código; eso ya se lee en el código. Documentáis lo que el código no puede contar de sí mismo.

![articulo-15-2-diagrama-genera-vs-mano.png](https://media1-production-mightynetworks.imgix.net/asset/df4d109c-5c80-43ba-9e59-34b39126df8c/articulo-15-2-diagrama-genera-vs-mano.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: dos familias de documentación. La que se genera desde el código se mantiene sola; la que se escribe a mano hay que cuidarla, y por eso se reserva para lo que ninguna herramienta puede generar.*

## **El runbook es una lista para el pánico, no un manual**

Queda la documentación operativa, que es un género propio y que casi nadie escribe hasta que se quema por no tenerla.

Un runbook no es un manual que se lee con calma. Es una lista pensada para ejecutarse bajo presión, por alguien estresado que puede no ser quien la escribió. No explica teoría, no razona: dice qué mirar, qué comando lanzar y qué esperar. Su valor no se mide el día que lo escribís, tranquilos y con el sistema sano; se mide el día que todo está en llamas y la persona de guardia —que puede que no sepa nada de embeddings— necesita que el sistema vuelva sin tener que entender el sistema.

Para el sistema de estimación, un runbook mínimo tiene esta forma:

```markdown
## Runbook: el servicio IA no responde

Síntoma: el backend de negocio devuelve 502/timeout al estimar.

1. Estado del contenedor:      docker compose ps ai-service
2. Healthcheck:                debe estar en estado `healthy`.
3. Últimos logs:               docker compose logs --tail=100 ai-service
4. Causas frecuentes:
   - LLM_API_KEY caducada  -> rotar clave (ver runbook de rotación).
   - BBDD vectorial caída  -> ver runbook de BBDD vectorial.
5. Reinicio seguro (no afecta al backend de negocio):
   docker compose restart ai-service
6. Si persiste, escalar a guardia con el ID de la petición.
```

Fijaos en lo que no hay: no hay explicaciones, no hay contexto, no hay prosa. Hay pasos. La calma para entender el porqué va en la documentación técnica; el runbook es para cuando no hay calma.

## **Documentación de usuario: enseñar a leer el número, no a usar la app**

La documentación de usuario del sistema de estimación tiene una particularidad que no tendría la de un CRUD: su trabajo más importante no es enseñar a *usar* el sistema, sino a *interpretar* lo que devuelve.

Una estimación no es un dato objetivo; es una respuesta con incertidumbre. Si el usuario ve "250 horas" y se lo toma como un hecho, da igual lo buena que sea vuestra arquitectura: habéis fallado en comunicar. La guía de usuario tiene que enseñar a leer la confianza, a mirar las fuentes en las que se apoyó la estimación, y —sobre todo— a entender qué significa que el sistema diga "no tengo datos suficientes para estimar esto". Ese mensaje no es un error: es el sistema comportándose bien, y el usuario tiene que saber leerlo como tal. Un usuario que confía en una estimación de confianza 0.3 como si fuera certeza es un problema de documentación, no de modelo.

Esa idea —que a veces la mejor respuesta es reconocer que no se sabe— la retomaremos de lleno cuando hablemos de safety en producción. Por ahora quedaos con que documentar el resultado es parte de producir el resultado.

## **Lo que queda por decidir**

Si repasáis lo que hemos dicho, documentar deja de ser la tarea aburrida del final para convertirse en tres decisiones concretas: sacar el conocimiento de vuestra cabeza dirigiéndolo a quien lo va a leer, automatizar todo lo que se pueda pudrir, y reservar la escritura a mano para el porqué y para el pánico.

Pero hay un documento del que hemos hablado casi de pasada y que es el más importante de todos: el **contrato entre el backend de negocio y el servicio IA**. Hemos dicho que FastAPI lo documenta solo, y es verdad. Lo que FastAPI no hace es diseñarlo bien. Podéis tener una documentación impecable de un contrato frágil, y entonces solo tendréis un retrato nítido de vuestra fragilidad.

Documentar la frontera es una cosa. Diseñarla para que se pueda cambiar una capa sin romper la otra, para que aguante el crecimiento, para que aísle de verdad, es otra. Y esa —cuándo y cómo partir el sistema en servicios, y cómo hacer que el contrato entre ellos sea uno que podáis mover sin miedo— es la siguiente decisión del camino.