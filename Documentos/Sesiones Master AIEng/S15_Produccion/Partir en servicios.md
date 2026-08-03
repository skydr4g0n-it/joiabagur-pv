# Partir en servicios

Creada: 1 de agosto de 2026 12:05
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S15. Puesta en producción de proyectos, arquitectura e infra (https://app.notion.com/p/S15-Puesta-en-producci-n-de-proyectos-arquitectura-e-infra-3afea9ca03c4806d8222e1ade89cf01f?pvs=21)

Mirad la implementación de referencia un momento, porque toma una decisión que, vista de lejos, parece contradictoria. Por un lado mantiene el frontend y el backend de negocio juntos, en un único proyecto Ruby on Rails: un solo deploy, sin ningún contrato REST interno entre ellos. Por otro, saca el servicio IA a un proceso aparte, en Python, con su propia frontera, su propio contrato y su propia clave. Tres piezas conceptuales, dos servicios. Una costura donde parecía que podía haber dos.

¿Por qué esa línea y no otra? ¿Por qué no un único proceso que lo haga todo, o por qué no tres servicios bien separaditos, uno por capa?

La respuesta a esa pregunta es, en realidad, todo lo que necesitáis saber sobre cuándo partir un sistema. Porque partir no es gratis, y el sitio exacto por donde cortáis no es una cuestión de gusto: es una cuestión de qué compra cada corte y qué cuesta.

## **Separar cuesta; solo se paga donde compra algo**

Empecemos por el coste, porque es el que casi siempre se ignora. Cada frontera entre servicios que introducís os cobra un peaje, y lo cobra para siempre:

Un **salto de red** donde antes había una llamada a función. Lo que era instantáneo y no fallaba nunca ahora tarda milisegundos y puede fallar: timeouts, reintentos, el otro servicio caído. Un **contrato que mantener sincronizado**: dos lados que tienen que ponerse de acuerdo en el payload y no romperse mutuamente al evolucionar. Dos **despliegues que coordinar** en vez de uno. Y una **superficie de fallo mayor**: más piezas, más sitios donde algo se tuerce.

Si una frontera no compra nada que compense ese peaje, es teatro de arquitectura. Y el teatro de arquitectura se paga en latencia, en coste y en madrugadas depurando por qué dos servicios que deberían hablar no se entienden.

Así que la pregunta correcta ante cada corte es: **¿qué compra?** Y hay exactamente cuatro cosas que un corte puede comprar y que valen su peaje.

La primera, y la decisiva para el servicio IA: **lenguaje distinto**. Todo el ecosistema de IA —los clientes de LLM, las librerías de embeddings, los frameworks de agentes— vive en Python. Vuestro backend de negocio, en la referencia, es Ruby. No podéis meter la orquestación de agentes dentro de un proceso Rails; son mundos que no conviven en el mismo runtime. Ese solo argumento ya justifica sacar el servicio IA a un proceso aparte. No es una preferencia: es que la alternativa no existe.

Las otras tres refuerzan el mismo corte. **Escalado independiente**: una estimación consume mucho y tarda segundos; un CRUD de negocio es barato e instantáneo. Separados, escaláis el que sufre sin tocar el otro. **Despliegue independiente**: podéis cambiar un prompt o la lógica RAG del servicio IA sin volver a desplegar toda la aplicación de negocio. **Aislamiento de fallos**: si el proveedor de LLM cae, el servicio IA se degrada, pero el backend de negocio sigue en pie y puede responder con elegancia en vez de arrastrar a todo el sistema.

Ahora mirad la costura que la referencia **no** hace: separar el frontend del backend de negocio. ¿Por qué no? Porque entre ellos no hay ninguno de esos cuatro ejes. Comparten lenguaje, comparten los datos, cambian al mismo ritmo y no hay una frontera de seguridad entre medias. Meter un contrato REST ahí sería pagar el peaje entero sin comprar absolutamente nada. Un solo deploy, sin contratos internos, es la decisión correcta precisamente porque ahí separar no compraría nada.

> Separad por los ejes que de verdad divergen —lenguaje, escalado, ritmo de cambio, frontera de seguridad—, no por dibujar un diagrama más simétrico.
> 

## **El contrato es la frontera hecha código**

Cuando un corte sí está justificado —como el del servicio IA— aparece la pieza más importante de todo el sistema: el **contrato** entre el backend de negocio y el servicio IA. Es la frontera del primer artículo, pero ya no como concepto: como código que hay que diseñar con cuidado, porque es la superficie por la que las dos capas se acoplan.

Tres decisiones que marcan la diferencia entre un contrato que aguanta y uno que se rompe al primer cambio:

**Versionad desde el día uno.** Prefijo `/v1/`. El día que necesitéis cambiar el contrato de forma incompatible, `/v2/` convive con `/v1/` mientras migráis, en vez de romper a todos los clientes a la vez.

**Payloads explícitos y validados.** El servicio IA recibe un `EstimateRequest` con sus campos tipados (Pydantic) y devuelve un `EstimateResponse` igual de explícito. Nada de diccionarios ambiguos que cada lado interpreta a su manera.

**Los errores son parte del contrato.** No basta con el camino feliz. El servicio IA tiene que decir con claridad qué ha pasado: `422` si la entrada es inválida, `401` si el token de servicio es incorrecto, `503` si una dependencia —el LLM o la BBDD vectorial— no está disponible. El backend de negocio necesita distinguirlos para reaccionar bien: reintentar, degradar o avisar. Un contrato que solo define el éxito obliga al otro lado a adivinar ante el fracaso.

Y todo esto cruza la frontera privada del primer artículo: la llamada va por la red interna y autenticada con el token de servicio. El contrato no es solo qué datos viajan; es también quién tiene permiso para hacer la llamada.

![articulo-15-3-diagrama-contrato.png](https://media1-production-mightynetworks.imgix.net/asset/90fc243e-9d3c-4bf9-853a-fcf40a482710/articulo-15-3-diagrama-contrato.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el contrato entre el backend de negocio y el servicio IA. Un endpoint versionado, un payload tipado de ida y vuelta, y los errores como parte explícita del acuerdo.*

## **Síncrono hasta que duela**

Definido el contrato, queda una decisión que determina cómo se *siente* el sistema: ¿el backend de negocio llama y espera, o encola y sigue?

Una estimación con RAG y agentes tarda segundos, no milisegundos. La opción simple es **síncrona**: el backend de negocio hace la llamada y espera la respuesta, como quien llama por teléfono y no cuelga hasta tener la respuesta. Es lo que usaréis por defecto, y es suficiente mientras los tiempos sean razonables. Lo único que exige es poner timeouts sensatos: si el servicio IA no responde en X segundos, el backend de negocio tiene que cortar y degradar, no quedarse colgado arrastrando peticiones web detrás.

La opción **asíncrona** aparece cuando lo síncrono empieza a doler: estimaciones que tardan demasiado, o picos de concurrencia que saturan. Entonces el backend de negocio encola la petición, recibe un identificador y consulta el resultado más tarde por polling, o recibe un aviso por webhook cuando está listo. Desacopla la carga y deja de bloquear peticiones web, a cambio de complejidad real: una cola, un worker, y estado del trabajo que gestionar.

![articulo-15-3-diagrama-sync-vs-async.png](https://media1-production-mightynetworks.imgix.net/asset/0c28014a-4780-4c16-991f-961b9e0746d0/articulo-15-3-diagrama-sync-vs-async.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: los dos patrones de comunicación. Síncrono —llamar y esperar— frente a asíncrono —encolar, recibir un identificador y consultar el resultado.*

La regla es la misma que con la propia decisión de partir: empezad por lo síncrono, que es más simple, y pasad a lo asíncrono cuando la latencia o la concurrencia lo exijan de verdad. Montar colas y workers "por si acaso", para un sistema que responde en dos segundos, es volver a pagar un peaje que nadie os está cobrando todavía.

## **Cuándo no partir**

Por simetría con lo anterior, tres casos en los que la respuesta correcta es no cortar:

Si dos piezas **comparten lenguaje, datos y ritmo de cambio**, no las separéis. Es el caso del frontend y el backend de negocio: juntas cuestan menos y no pierden nada. Separarlas es complejidad sin contrapartida.

Si el problema es que **un proceso es lento**, un servicio nuevo no lo va a acelerar. Lo reparte y le añade un salto de red por encima. Optimizad el proceso; no lo troceéis para esconder la lentitud detrás de más cajas.

Y no fragmentéis en microservicios **porque suene maduro**. Cada servicio de más es un sitio más donde algo falla, un contrato más que mantener y un despliegue más que coordinar. Las tres capas del programa, más sus datastores, son las costuras que compran algo. Ni una más hasta que el sistema la pida a gritos.

## **Lo que queda por decidir**

Si habéis seguido el hilo, "partir en servicios" deja de ser una moda y se convierte en una cuenta: cada frontera cuesta un peaje fijo y solo se justifica donde compra lenguaje, escalado, ritmo de cambio o seguridad. La referencia hace exactamente dos cortes porque exactamente dos cortes compran algo.

Pero decidir las fronteras y diseñar el contrato es solo la mitad. Un servicio bien delimitado sigue siendo, ahora mismo, "un proceso que arrancáis a mano en una terminal". Para que la frontera sea real en producción, cada servicio tiene que convertirse en un artefacto que arranca igual en cualquier sitio, con sus dependencias dentro, sin depender de lo que tengáis instalado en la máquina.

Eso —empaquetar cada servicio en un contenedor para que "funciona en mi máquina" deje de ser una excusa y pase a ser una garantía— es el siguiente tramo del camino.