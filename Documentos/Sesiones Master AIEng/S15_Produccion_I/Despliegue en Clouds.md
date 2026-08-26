# Despliegue en Clouds

Creada: 1 de agosto de 2026 12:06
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S15. Puesta en producción de proyectos, arquitectura e infra (https://app.notion.com/p/S15-Puesta-en-producci-n-de-proyectos-arquitectura-e-infra-3afea9ca03c4806d8222e1ade89cf01f?pvs=21)

Durante toda la sesión hemos usado la palabra "desplegar" sin abrirla. El pipeline del artículo anterior sabe construir imágenes y moverlas por los entornos, pero "a dónde" y "cómo" seguían siendo una caja negra. Este artículo la abre. Y lo primero que aparece dentro no es una lista de comandos ni un proveedor concreto, sino una decisión —una sola, repetida sobre infraestructura real— que ya conocéis: **qué pieza mira a la calle y cuál no.**

La conocéis porque es la frontera del primer artículo. Pero hay una diferencia enorme entre dibujarla y materializarla. En un `docker-compose`, ponerle un puerto de más al servicio IA era un error sin público: como mucho lo veíais vosotros en `localhost`. En infraestructura cloud, exponer el servicio IA es la clave del LLM abierta a internet, con una dirección que alguien acabará encontrando. La misma decisión de siempre, pero ahora con consecuencias que se pagan en la factura y en una brecha. Desplegar bien es, sobre todo, llevar esa frontera a redes de verdad sin equivocarse de lado.

## **Elegir dónde desplegar: la herramienta más simple que resuelva el problema**

Antes de la frontera, una decisión que la gente sobredimensiona: dónde. Hay un abanico de opciones, y se ordenan bastante bien de más simple a más potente —que casi siempre significa también de más simple a más complejo de operar.

En un extremo, los **PaaS de contenedores** (Render, Railway, Fly y similares): les dais vuestra imagen y se encargan de casi toda la infraestructura por vosotros. En el medio, los **contenedores gestionados** del proveedor cloud, con más control y más configuración. En el otro extremo, **Kubernetes**: máxima flexibilidad y máxima complejidad operativa.

Para vuestro sistema —tres capas y sus datastores— un PaaS de contenedores es suficiente y es lo que usaréis. Kubernetes para tres servicios no es "hacerlo bien": es sobreingeniería, complejidad que no compra nada, exactamente el mismo error que analizamos al hablar de partir en microservicios. La regla es la de siempre:

> Elegid la herramienta más simple que resuelva el problema, no la más impresionante que sepáis nombrar.
> 

![articulo-15-6-diagrama-opciones-despliegue.png](https://media1-production-mightynetworks.imgix.net/asset/ad106b46-25fc-4e60-878f-4e86b56186cd/articulo-15-6-diagrama-opciones-despliegue.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el abanico de opciones de despliegue, de más simple a más potente. Para un sistema de tres capas, un PaaS de contenedores cubre lo que hace falta; Kubernetes es complejidad que aquí no compra nada.*

Conviene saber que Kubernetes existe y cuándo se justifica —muchos servicios, equipos grandes, necesidades finas de escalado— para no reinventarlo mal, pero no es vuestro caso hoy. Y elegir la opción simple no es conformarse: es reservar vuestra complejidad para donde de verdad importa, que en un sistema de IA no es la infraestructura, sino la calidad y el coste de las respuestas.

## **Materializar la frontera en redes reales**

Ahora sí, la frontera. Sobre el PaaS, la topología del primer artículo se traduce en configuración de red concreta, pieza por pieza.

El **backend de negocio** es lo único público: se expone tras HTTPS, con su dominio, como puerta de entrada del sistema. El **servicio IA** va en la red privada del proveedor, sin dirección pública, alcanzable solo desde el backend de negocio y autenticado con el token de servicio. Es la traducción exacta del "solo el backend de negocio publica puerto" del `docker-compose`, pero donde equivocarse ya no es inocuo. Las **bases de datos** —la relacional y la vectorial— también privadas, ya sean servicios gestionados del proveedor o contenedores con almacenamiento persistente. Y los **secretos** llegan del gestor de secretos de la plataforma, inyectados en el despliegue, nunca en la imagen ni en el repositorio.

![articulo-15-6-diagrama-cloud.png](https://media1-production-mightynetworks.imgix.net/asset/16120612-a751-45d7-801f-bc1681ddd40a/articulo-15-6-diagrama-cloud.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: la frontera del primer artículo, ya sobre infraestructura cloud. Backend de negocio público tras HTTPS; servicio IA y datastores en la red privada; secretos desde el gestor del proveedor.*

Fijaos en que no hay ninguna idea nueva aquí: es todo lo que llevamos diciendo, aterrizado. Lo único que cambia es que un descuido —una casilla de "público" marcada por defecto, un datastore expuesto para "probar rápido"— ya no lo ve solo vuestro `localhost`. Por eso el despliegue no es un paso mecánico: es el momento en que todas las decisiones de aislamiento de la sesión se examinan de verdad.

## **El health check tiene que ser barato (y no llamar al modelo)**

Hay una pieza pequeña del despliegue que decide si el sistema se mantiene en pie solo: el health check. El proveedor lo usa para dos cosas distintas —saber si una instancia está lista para recibir tráfico (*readiness*) y si sigue viva o hay que reiniciarla (*liveness*)— y las consulta constantemente.

De ahí sale una regla que parece un detalle y no lo es: **el** `/health` **del servicio IA tiene que ser barato y no puede llamar al modelo.** Si el healthcheck gastara tokens, estaríais pagando por cada comprobación, muchas veces por minuto, para siempre. Y peor aún: si dependiera de que el proveedor de LLM responda, un hipo del proveedor haría que vuestro healthcheck fallara, y la plataforma —viendo la instancia "enferma"— la reiniciaría o le cortaría el tráfico. Tendríais un sistema que se autodestruye cada vez que el LLM tose, por culpa de un healthcheck demasiado ambicioso.

El `/health` solo debe responder que la aplicación está viva; como mucho, que sus dependencias internas contestan. Comprobar que el modelo responde con calidad es una pregunta legítima, pero es trabajo de la **monitorización**, no del healthcheck —y de eso va, precisamente, la siguiente sesión. Vigilancia y latido son cosas distintas: el latido tiene que ser tan barato que puedas tomarlo cada segundo sin pensarlo.

## **Un par de trampas que solo aparecen en cloud**

Cuando todo esto se junta sobre infraestructura real, aparecen dos detalles que en local no se notaban.

El primero, la **persistencia**. En cloud, un redeploy puede recrear el contenedor desde cero. Si la base de datos vectorial no vive en almacenamiento persistente con backups, un despliegue rutinario os borra el conocimiento del sistema —esos vectores que costaron tiempo y tokens generar—. Lo que en el `docker-compose` era un volumen, aquí es un servicio de datos gestionado o un disco persistente que hay que configurar a conciencia.

El segundo, el **arranque en frío y la latencia**. El servicio IA puede tardar en estar listo si carga modelos de embeddings al arrancar, y la región donde despleguéis determina la latencia contra el proveedor de LLM. Ninguna de las dos es dramática, pero conviene tenerlas en el radar antes de que un usuario las note.

## **Cierre: de "funciona en mi máquina" a un sistema en producción**

Aquí se cierra el camino que empezó con una demo que sabíais conjurar en vuestro portátil. Recorrámoslo hacia atrás un momento, porque cada tramo era una de las promesas del principio hecha realidad.

El sistema de estimación está ahora **documentado**, de modo que otro lo puede operar. Está partido en las **fronteras** que compran algo, con un contrato explícito entre el backend de negocio y el servicio IA. Cada pieza es una **imagen reproducible**, así que arranca igual en cualquier parte y "en mi máquina funciona" ya no significa nada. Un **pipeline** lo construye y lo prueba sin gastar un token, y lo mueve por dev, staging y producción cambiando solo la configuración. Y todo ello está **desplegado en cloud** con la frontera público/privado materializada en redes reales: el backend de negocio de cara al mundo, el servicio IA y su clave a resguardo.

El Proyecto 2 está en producción. Reproducible, seguro por defecto, operable por quien no lo escribió: las cuatro promesas del primer artículo, cumplidas.

Y sin embargo, hay una pregunta que el despliegue no responde y que a partir de ahora no os va a dejar dormir tranquilos: **¿está funcionando *bien*?** Ahora mismo sabéis que el sistema está *vivo* —el smoke test lo confirma— pero no sabéis si estima con acierto, si ha empezado a alucinar desde el último cambio de prompt, si cumple lo que la regulación espera, ni cuánto os está costando cada respuesta. Un sistema desplegado que no sabéis medir es un sistema que opera a ciegas.

Poner ojos a lo que habéis desplegado —evaluación, observabilidad, safety y control de costes: LLMOps— es de lo que trata la siguiente sesión. Habéis conseguido que el sistema funcione en producción. Falta conseguir que funcione *bien*, y que lo siga haciendo.