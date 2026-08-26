# Modelos en local

Creada: 25 de agosto de 2026 8:14
Módulo: M6. Despliegue y puesta en producción (https://app.notion.com/p/M6-Despliegue-y-puesta-en-producci-n-345ea9ca03c480d8a7a9e2275f20c2ef?pvs=21)
Sesión: S16. Puesta en producción II - Calidad y observabilidad (https://app.notion.com/p/S16-Puesta-en-producci-n-II-Calidad-y-observabilidad-3c7ea9ca03c480a6a244e54a2f05e42a?pvs=21)

Durante toda la sesión, cuando el servicio IA ha necesitado un modelo, ha hecho lo mismo: mandar la petición a un proveedor —OpenAI, Anthropic, el que sea—, que ejecuta el modelo en su infraestructura y os devuelve la respuesta. Pagáis por token, confiáis vuestros datos a su sistema y vuestra disponibilidad a la suya. Es una opción excelente, y es el punto de partida sensato para casi todo el mundo.

Pero es *una* opción, y tratarla como la única esconde una decisión que en algún momento vais a tener que tomar de verdad. Porque el modelo no tiene por qué correr en el ordenador de otro. Puede correr en el vuestro: en vuestro portátil mientras desarrolláis, o en una instancia con GPU que alquiláis en AWS —o en el proveedor cloud que uséis— y que controláis vosotros. A eso se le llama **self-hosting**, y este artículo trata de cuándo tiene sentido, dónde puede vivir el modelo, y qué os cuesta de verdad.

## **Tres sitios donde puede vivir el modelo**

Conviene ver las opciones como lo que son: tres sitios distintos donde ejecutar el modelo, cada uno para un momento distinto.

El primero es la **API alojada**, la que ya usáis. El modelo vive en la infraestructura del proveedor; vosotros solo llamáis. Cero operación, calidad de primera línea, y pagáis por uso. Es el mejor sitio por defecto y el peor si tenéis un motivo de peso para no estar ahí.

El segundo es vuestra **máquina local**. Con herramientas como Ollama o llama.cpp podéis correr un modelo de pesos abiertos —un Llama, un Mistral, un Qwen, normalmente cuantizado para que quepa— directamente en vuestro portátil o estación de trabajo. Es maravilloso para desarrollar: gratis en el margen, sin límites de rate, funciona sin conexión, y vuestros datos no salen de la máquina. Su límite es obvio: modelos más pequeños y poca capacidad de tráfico. Es un entorno de desarrollo y prototipo, no de producción.

El tercero es una **instancia cloud con GPU**. Aquí alquiláis una máquina con GPU en AWS u otro proveedor y levantáis en ella un servidor de inferencia —vLLM o TGI son los habituales— que sirve el modelo de pesos abiertos a vuestra escala. Esto sí es self-hosting de producción: lo controláis del todo, escala con vuestro tráfico, pero pagáis la GPU y —esto es lo importante— lo operáis vosotros.

![articulo-16-7-diagrama-donde-vive.png](https://media1-production-mightynetworks.imgix.net/asset/54e44125-d4b5-42fd-9fb6-f4b12c4a3537/articulo-16-7-diagrama-donde-vive.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: al servicio IA le da igual dónde viva el modelo. Detrás de la misma interfaz puede haber una API alojada, un modelo local o una instancia cloud con GPU; son backends intercambiables.*

## **Y al servicio IA le da casi igual: es cambiar la URL**

Aquí es donde recogéis lo que sembrasteis en el Módulo 2. Cuando construisteis el servicio IA, lo hicisteis para **encapsular** la llamada al modelo detrás de una abstracción, con su capa de proveedores y sus fallbacks. Esa decisión, que entonces parecía higiene, ahora paga.

Porque las herramientas de self-hosting —Ollama, vLLM, TGI— exponen casi todas una interfaz **compatible con OpenAI**. Es decir: hablan el mismo idioma que ya habla vuestro cliente. Cambiar de un proveedor alojado a un modelo que corre en vuestra máquina o en vuestra GPU es, en lo esencial, apuntar el cliente a otra `base_url` y elegir otro nombre de modelo. El resto del servicio IA —el RAG, los agentes, los guardrails— no se entera de dónde vive el modelo.

Esto es más profundo de lo que parece. Significa que "dónde corre el modelo" no es una decisión de arquitectura que os ate: es un backend intercambiable detrás de vuestra abstracción. Podéis desarrollar contra un modelo local, desplegar contra una API, y mañana mover parte del tráfico a una GPU propia, sin reescribir el sistema. La costura está en un solo sitio, que es exactamente donde la pusisteis.

## **Por qué self-hostear: tres razones de peso**

Cambiar de la comodidad de una API a la responsabilidad de operar un modelo no se hace por moda. Se hace por una de estas tres razones, y conviene que sea explícita.

La primera es la **privacidad y el cumplimiento**. Si trabajáis con datos que, por regulación o por contrato, no pueden salir de vuestra infraestructura, entonces mandar esos datos a un proveedor externo no es una opción a optimizar: está directamente prohibido. Ahí el self-hosting no es una mejora de coste, es un requisito. El modelo corre dentro de vuestra red privada —la misma frontera del primer artículo— y los datos nunca la cruzan. Es la continuación natural del compliance-by-design que veremos en la siguiente sesión.

La segunda es el **control**. Con una API, el proveedor puede actualizar el modelo por debajo y cambiaros el comportamiento de un día para otro, sin que toquéis nada —justo el fantasma que abría la sesión de LLMOps—. Un modelo de pesos abiertos que vosotros alojáis se queda quieto: es la versión que vosotros fijasteis, hasta que vosotros decidáis cambiarla. Para un sistema donde la estabilidad del comportamiento importa, eso vale mucho.

La tercera es el **coste a volumen**, y merece su propia sección, porque es la razón más citada y la peor entendida.

## **El cruce de costes: "barato" depende del volumen**

La intuición de que self-hostear "sale más barato" es verdad y mentira a la vez, y la diferencia está en el volumen.

Una API se paga **por uso**: cada token cuesta, y si no mandáis peticiones, no pagáis nada. Su coste crece con el tráfico, pero empieza en cero. Una GPU se paga **por tiempo encendida**: cuesta lo mismo tanto si le mandáis diez peticiones al día como diez millones. Su coste es plano, pero empieza alto y no baja cuando el tráfico baja.

De ahí sale un **punto de cruce**. Por debajo de cierto volumen, la API es más barata, porque no estáis pagando una GPU cara que está la mayor parte del tiempo ociosa. Por encima de ese volumen, la GPU propia puede salir más a cuenta, porque su coste fijo se reparte entre tantísimas peticiones que el coste por petición se hunde. Vuestro trabajo es saber de qué lado del cruce estáis.

![articulo-16-7-diagrama-cruce-costes.png](https://media1-production-mightynetworks.imgix.net/asset/1f9fa3ff-1204-4efb-829f-8fd4030ef62f/articulo-16-7-diagrama-cruce-costes.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

*Diagrama: el coste de la API crece con el volumen desde cero; el de una GPU propia es plano pero arranca alto. Se cruzan en un punto: por debajo, la API es más barata; por encima, el self-hosting puede compensar.*

Pero hay una trampa en ese gráfico, y es la que arruina más presupuestos: **la GPU no es el único coste**. Cuando self-hosteáis, os convertís en el equipo de operaciones del modelo. Hay que parchear, escalar, vigilar la disponibilidad, gestionar los picos, actualizar el servidor de inferencia. Ese coste de operación —horas de gente— no aparece en la factura de AWS, pero es real y es fácil de olvidar al hacer la cuenta. El cruce de costes de verdad está más a la derecha de lo que sugiere la factura de la GPU sola.

## **Lo que perdéis al self-hostear**

Por honestidad, y porque decidir bien exige ver las dos caras: self-hostear no es gratis en calidad ni en esfuerzo.

Perdéis, casi siempre, algo de **calidad de frontera**. Los modelos de pesos abiertos son excelentes y mejoran a gran velocidad, pero suelen ir un paso por detrás de los mejores modelos alojados. Para muchas tareas la diferencia no importa; para las difíciles, puede que sí.

Perdéis la **red de seguridad del proveedor**: sus capas de safety, sus mejoras continuas, su escalado automático ante un pico. Todo eso pasa a ser vuestro problema.

Y ganáis, sobre todo, una **superficie operativa nueva**. Un modelo self-hosted es un sistema más que mantener vivo, con su GPU, su servidor de inferencia y sus madrugadas. No lo hagáis por prestigio ni porque suene avanzado. Hacedlo cuando tengáis un motivo concreto —una regulación que os obliga, un volumen que lo justifica, un control que necesitáis— y no antes.

## **Dónde encaja esta decisión**

Fijaos en que nada de esto cambia la arquitectura del sistema. El servicio IA sigue siendo el que encapsula la llamada al modelo; lo único que cambia es **qué hay detrás** de esa llamada: la nube de un proveedor, vuestro portátil, o una GPU vuestra. Y como esa costura está aislada tras vuestra abstracción, la decisión es reversible y hasta mixta: podéis tener un modelo pequeño self-hosted para las tareas fáciles y de alto volumen —enlazando con el "modelo por tarea" de la optimización— y seguir llamando a una API de frontera para las difíciles.

Un último apunte que ata con el resto de la sesión: un modelo self-hosted, viva en una instancia cloud o en vuestra red, es una pieza más dentro de la **frontera privada**. No se expone a internet, se securiza como el resto de la capa de datos, y el servicio IA lo alcanza por la red interna. Cambiar dónde vive el modelo no cambia las reglas de quién puede hablar con él.

De cuánto cuesta operar todo esto —tokens, GPU, latencia— y de cómo optimizarlo sin perder calidad se ocupa de lleno la siguiente sesión. Esta decisión, la de dónde vive el modelo, es la primera pieza de esa conversación sobre el coste.