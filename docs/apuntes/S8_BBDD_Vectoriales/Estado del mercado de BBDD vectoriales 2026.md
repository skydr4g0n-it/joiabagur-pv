# Estado del mercado de BBDD vectoriales 2026

Creada: 6 de junio de 2026 14:02
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S8. Bases de datos vectoriales (https://app.notion.com/p/S8-Bases-de-datos-vectoriales-377ea9ca03c48099b3eadf17047947a7?pvs=21)

El artículo anterior cerró con una pregunta abierta. Sabes ya que el proyecto está en el rango en el que añadir esta pieza al stack se justifica, sabes qué propiedades debe tener (persistencia, concurrencia, joins con datos relacionales, transacciones), y sabes que la primitiva técnica nueva es la búsqueda aproximada con índices ANN. Lo que no tienes todavía es el mapa del mercado.

Este artículo es ese mapa. Cubre las cinco opciones que en 2026 dominan los despliegues de producción, las posiciona según los ejes que importan operativamente, y termina justificando la decisión locked del programa — usar pgvector — sin venderla. Es deliberadamente honesto sobre cuándo esa decisión es correcta y cuándo dejaría de serlo, porque la pregunta "¿qué base de datos vectorial usamos?" no se contesta una vez para toda una carrera: se contesta para cada proyecto, y los proyectos de tu vida laboral fuera del programa probablemente vayan a apuntar en direcciones distintas.

Antes de entrar en cada opción, conviene tener claros los cuatro ejes con los que vamos a evaluarlas. Cualquier comparativa que se base solo en QPS o solo en precio te deja a medias.

## **Los cuatro ejes que importan**

**Modelo operativo.** ¿Lo gestionas tú o lo gestiona el proveedor? Self-hosted significa que tu equipo tiene control total — pero también que tu equipo es responsable de updates, backups, monitorización, tuning y respuesta a incidentes a las 3 de la mañana. Managed significa que pagas para no tener que pensar en nada de eso, a cambio de menos control y un modelo de coste que escala con uso. No hay una respuesta universalmente mejor; hay una respuesta correcta para el tamaño y madurez operativa de tu equipo.

**Escala práctica.** El número de vectores que el sistema soporta razonablemente. "Soporta" no significa "técnicamente puede almacenar"; significa que mantiene latencias aceptables, recall razonable, y un coste que no se dispara cuadráticamente. Los benchmarks públicos de 2026 marcan tres rangos claros: bajo diez millones de vectores cualquiera de las cinco opciones es viable, entre diez y cien millones el campo se estrecha, y por encima de mil millones la lista se reduce a sistemas diseñados específicamente para esa escala.

**Funcionalidades nativas.** ¿La búsqueda híbrida (vector + keyword) viene de serie o tienes que componerla tú? ¿El filtrado por metadata es first-class o es un add-on? ¿El sistema entiende multi-modal (texto + imagen) sin reconfiguración? ¿Soporta sharding multi-región? Cada una de estas funcionalidades, cuando no está incluida, supone trabajo de ingeniería real para construirla, mantenerla y monitorizarla.

**Modelo de coste.** El precio en factura mensual es solo una de las tres componentes del coste real. La segunda es el coste de operación (DevOps, on-call, gestión de incidentes). La tercera es el coste de migración el día que necesites cambiar — y todos los benchmarks de 2026 coinciden en que cambiar de base de datos vectorial en producción no es proyecto de un fin de semana, sobre todo cuando el corpus tiene decenas de millones de vectores que hay que re-indexar.

Con estos ejes en la cabeza, las cinco opciones.

## **pgvector — la extensión de Postgres**

pgvector es una extensión open-source de PostgreSQL que añade un tipo de dato `vector` y un puñado de operadores de distancia, junto con índices ANN (HNSW desde la versión 0.5 e IVFFlat antes de eso). No es una base de datos nueva: es Postgres haciendo más cosas. Si tu equipo ya opera Postgres, pgvector aparece como una extensión más que se habilita con `CREATE EXTENSION vector`. No hay servicio nuevo que monitorizar, no hay credenciales nuevas que gestionar, no hay sistema nuevo que aprender a debuggear.

La narrativa de "Postgres es lento para vectores" viene de la era del índice IVFFlat y ya no se sostiene. Los benchmarks públicos recientes muestran que con índices HNSW bien dimensionados pgvector compite seriamente con los sistemas dedicados hasta volúmenes de unos diez millones de vectores, y con la extensión pgvectorscale (que añade DiskANN y compresión cuantizada) el techo sube significativamente. Un análisis de abril de 2026 sobre 50M vectores reporta pgvectorscale a 471 QPS frente a Qdrant a 41 QPS en condiciones equivalentes — un orden de magnitud a favor de pgvector. Hay que tomar estos números con la cautela habitual de los benchmarks de vendor, pero el patrón general es consistente: la diferencia entre pgvector y los sistemas dedicados se ha reducido drásticamente en los últimos dos años.

La ventaja conceptual que ningún sistema dedicado iguala es la capacidad de cruzar búsqueda vectorial con datos relacionales en una sola query atómica. Quieres los chunks más parecidos al brief del cliente filtrados por sector, por año, por rango de presupuesto, ordenados por una combinación de similitud y antigüedad, con joins a la tabla de clientes — y todo eso en una sola sentencia SQL con garantías ACID. Pinecone y Qdrant pueden hacer la parte vectorial bien, pero los datos relacionales viven en otro sistema y la coherencia entre ambos es responsabilidad tuya.

El techo de pgvector llega cuando el volumen de vectores excede lo que cabe cómodamente en `shared_buffers` y el índice empieza a hacer I/O de disco en cada query, o cuando necesitas funcionalidades muy específicas (búsqueda híbrida con BM25 sintonizado, embeddings multimodales como ciudadanos de primera clase, sharding multi-región nativo). En esas situaciones, los sistemas dedicados ganan claramente. Para el resto, pgvector es probablemente la respuesta correcta y casi nadie te lo cuenta porque vender Postgres no genera revenue para nadie.

## **Qdrant — el líder de velocidad open-source**

Qdrant es una base de datos vectorial dedicada escrita en Rust, open-source, con un perfil muy claro: rendimiento puro y filtrado por metadata como ciudadanos de primera clase. Sus benchmarks públicos consistentemente muestran latencias p50 por debajo de 5 ms a alto recall, y su sistema de filtros pre-search es genuinamente el mejor entre las opciones open-source — un detalle que importa más de lo que parece cuando las queries reales casi nunca son "los k más cercanos en absoluto" sino "los k más cercanos que cumplen estas condiciones".

Donde Qdrant brilla es en cargas read-heavy con filtrado complejo, donde la velocidad importa, y donde el equipo está cómodo operando un servicio adicional en su stack. Donde se queda corto es en operaciones con datos no vectoriales: no hay joins, no hay garantías transaccionales sobre datos relacionales fuera del sistema, y la integración con el resto del backend depende de mantener dos fuentes de verdad coherentes.

Su sweet spot práctico va de unos cientos de miles de vectores hasta varias decenas de millones. Por debajo de ese rango es over-engineering. Por encima, los reportes públicos sugieren que el rendimiento empieza a degradarse en escenarios de escritura intensiva, aunque para cargas predominantemente de lectura escala mejor de lo que la documentación reconoce.

## **Weaviate — búsqueda híbrida nativa**

Weaviate es open-source, con servicio gestionado disponible, y su seña de identidad es que la búsqueda híbrida — combinar similitud vectorial con BM25 sobre keywords — es nativa y bien integrada, no un patrón que tengas que construir tú. También trae módulos de vectorización integrados: puedes insertar texto crudo y Weaviate llama a OpenAI, Cohere o Hugging Face por debajo para generar el embedding antes de almacenarlo. Para equipos que valoran la "developer experience" por encima de la flexibilidad fina, esto reduce fricción real.

El precio de esa integración es que el modelo conceptual de Weaviate es más opinionado que el de Qdrant o pgvector. Hay un esquema de clases que define cómo se vectorizan los campos, hay una API GraphQL como interfaz primaria, y hay un cierto coupling con el ecosistema que el equipo de Weaviate diseña. Para proyectos donde la búsqueda híbrida es el centro del producto (documentos legales, e-commerce con SKUs y descripciones, compliance donde el match exacto sobre nombres propios importa tanto como la similitud semántica), Weaviate ahorra trabajo. Para proyectos donde la búsqueda vectorial es una pieza más dentro de un sistema con mucha lógica relacional, esa opinión integrada se siente como una restricción.

## **Milvus — la escala de mil millones**

Milvus es la opción que se diseñó desde el principio para escala extrema. Arquitectura distribuida con separación entre almacenamiento, computación e indexación; sharding maduro; soporte de GPU; backing por Zilliz, que ofrece el servicio gestionado. Por número de estrellas en GitHub, es la opción open-source más popular, y su comunidad de usuarios a escala es la más activa de las cinco.

Para proyectos por debajo de cien millones de vectores, Milvus está sobredimensionado: la complejidad operativa de gestionar sus múltiples componentes (etcd, MinIO, varios servicios distintos) no se justifica para escalas que pgvector o Qdrant manejan con un solo proceso. Pero por encima de mil millones de vectores, Milvus es una de las dos o tres opciones que realmente funcionan en producción, y casi todas las arquitecturas RAG a esa escala que se documentan públicamente lo usan o usan Vespa.

No es la elección probable para el proyecto del programa. Vale la pena conocerla porque define el techo real del mercado open-source y porque varios casos de uso a los que vas a enfrentarte en tu carrera — si trabajas con catálogos de e-commerce muy grandes, telemetría de IoT, o sistemas de recomendación a escala consumer — terminan ahí.

## **Pinecone — la opción gestionada**

Pinecone es totalmente gestionado, propietario, y vende "zero ops" como propuesta de valor central. Creas un índice serverless, subes los vectores, lanzas las queries. No hay servidores que provisionar, no hay índices que tunear, no hay rebalanceos que vigilar. Para equipos pequeños donde el coste de un ingeniero senior dedicado a DevOps de bases de datos vectoriales supera el coste de la factura mensual, esto es exactamente lo que necesitas pagar.

El modelo de coste tiene tres componentes — storage a $0.33/GB/mes, read units, write units — más un mínimo mensual de $50 que Pinecone introdujo en 2025 y que cambió el cálculo para cargas muy ligeras. La cuestión que ningún tutorial de Pinecone te cuenta es que el coste no escala linealmente con uso visible: las read units se consumen más rápido de lo que la documentación sugiere, especialmente con filtros de metadata, y un benchmark reciente sobre cargas RAG estándar reporta que la factura real promedia entre 2.5× y 4× la estimación inicial del calculator de Pinecone. No es publicidad engañosa exactamente — es que los workloads que la gente despliega son distintos de los que se modelan en la calculadora.

Hasta unos diez millones de vectores con cargas moderadas, Pinecone es competitivo y a veces más barato que la alternativa self-hosted una vez sumas el coste real de DevOps. A partir de ahí, la economía cambia: a cincuenta o cien millones de vectores con tráfico sostenido, los reportes públicos consistentemente muestran que self-hosted Qdrant, Milvus o pgvector son 3× a 10× más baratos en TCO. Para equipos en industrias reguladas con requisitos de soberanía de datos, Pinecone directamente no entra en la conversación.

## **Resumen comparativo**

![articulo-02-figura-01-matriz-posicionamiento.jpg](https://media1-production-mightynetworks.imgix.net/asset/94dc5ce3-230b-40d4-ab5e-fdc2feea1638/articulo-02-figura-01-matriz-posicionamiento.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

![image.png](https://media1-production-mightynetworks.imgix.net/asset/3f408149-f8fc-43e4-868f-ae6b6611613f/9a825cc86b36ff3d.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Las latencias p50 de las cinco opciones bien sintonizadas están todas en el rango de 5 a 50 ms para volúmenes hasta 10M vectores, así que las diferencias de QPS publicadas en los benchmarks no son lo que decide. Lo que decide son los cuatro ejes de arriba, en este orden: modelo operativo, escala práctica esperada, funcionalidades nativas que vas a usar de verdad, y modelo de coste integrando los tres componentes.

## **La decisión del programa: pgvector**

Para el sistema de estimaciones que construimos a lo largo del programa, pgvector es la elección. Las razones son cuatro y conviene articularlas con precisión porque exactamente las mismas razones — o la ausencia de ellas — son las que justifican o rechazan pgvector en cualquier proyecto que evalúes fuera del programa.

**Primera, el alineamiento con el stack del backend de negocio.** La implementación de referencia del programa usa Ruby on Rails sobre PostgreSQL para el backend de negocio. El servicio IA puede hablar directamente con ese mismo PostgreSQL — o con un Postgres dedicado, pero con la misma tecnología — y aprovechar todo lo que tu equipo ya sabe operar. Si la elección hubiera sido Qdrant o Pinecone, habríamos añadido al stack un componente nuevo con su propio modelo de fallos, sus propios backups, su propia monitorización, su propia curva de aprendizaje. Para los volúmenes del proyecto, ese coste operativo no se compensa con ninguna ventaja técnica.

**Segunda, la simplicidad de los joins transaccionales.** El proyecto necesita constantemente cruzar resultados de búsqueda vectorial con datos relacionales: clientes, sectores, fechas, montos. En pgvector eso es una query SQL con un `JOIN` y un `WHERE`, atómica, con garantías ACID. En cualquiera de las otras cuatro opciones es coordinación entre dos sistemas, con todos los modos de fallo que esa coordinación introduce. Para un proyecto que es por naturaleza "RAG con muchos filtros estructurados", esto es decisivo.

**Tercera, la búsqueda híbrida natural.** PostgreSQL tiene `tsvector` y `ts_rank` desde hace décadas. Combinar similitud vectorial con full-text search en una sola query es directo, sin necesidad de bolt-on. Weaviate ofrece búsqueda híbrida más sofisticada, pero el coste de añadir un sistema entero al stack solo por esa funcionalidad no se justifica en este caso.

**Cuarta, la escala esperada.** El proyecto del programa, replicado en un cliente real, va a manejar cientos a unos pocos miles de presupuestos históricos. Cada presupuesto produce entre 10 y 50 chunks. El corpus total razonable está en el rango de decenas o cientos de miles de vectores. Cien mil vectores con HNSW corren en pgvector con latencias de pocos milisegundos sobre hardware modesto. Estamos al menos dos órdenes de magnitud por debajo de cualquier techo plausible.

Esta decisión no es ideológica. Es la respuesta correcta para este proyecto específico bajo estas restricciones específicas. Conviene que tengas ahora muy claro bajo qué condiciones esa respuesta correcta dejaría de serlo.

## **Cuándo esta decisión dejaría de ser correcta**

Si tu proyecto fuera del programa se parece al de estimaciones — datos relacionales con búsqueda semántica como pieza importante pero no única, volúmenes en el rango de decenas a unos pocos millones de vectores, equipo familiarizado con Postgres — la decisión vuelve a ser pgvector. Si difiere en alguno de los ejes, conviene reconsiderar.

![articulo-02-figura-02-arbol-decision.jpg](https://media1-production-mightynetworks.imgix.net/asset/0f9efaf1-8b68-4063-8375-ca0b84c6043e/articulo-02-figura-02-arbol-decision.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Si tu volumen real va a estar consistentemente por encima de cincuenta millones de vectores, conviene evaluar Qdrant o Milvus antes de comprometerte. pgvectorscale extiende el techo pero introduce su propia complejidad operativa.

Si tu producto es predominantemente búsqueda donde el match exacto sobre nombres propios, identificadores y SKUs es tan importante como la similitud semántica, Weaviate o Elasticsearch con su soporte vectorial son probablemente mejor inversión que pgvector.

Si tu equipo no tiene experiencia operando PostgreSQL pero sí tiene presupuesto para SaaS y prioriza developer velocity, Pinecone es la elección racional, especialmente por debajo de diez millones de vectores donde su coste todavía es competitivo.

Si tu sistema necesita distribución multi-región nativa con SLA estricto, Pinecone o Astra DB son las opciones serias; pgvector lo puede hacer con replicación de Postgres pero el patrón es más artesanal.

Si tu equipo está construyendo algo con embeddings multimodales (texto + imagen + audio) como ciudadanos de primera clase, LanceDB o Marqo están específicamente diseñados para ese caso; pgvector lo soporta pero sin las optimizaciones específicas.

Estas no son condiciones binarias. La realidad es que muchos proyectos empiezan en pgvector durante el prototipo y migran a una opción dedicada cuando algún eje cruza un umbral concreto. La migración nunca es trivial pero tampoco es imposible si el diseño del schema y de la capa de acceso a datos contemplan esta posibilidad desde el principio — algo que vamos a hacer en el ejercicio pre-sesión y en el directo.

## **Bridge al siguiente artículo**

Tienes ya el mapa del mercado y entiendes por qué la decisión locked del programa es pgvector. La siguiente pregunta es interna: dentro de la base de datos elegida, ¿cómo decide concretamente el sistema "estos son los vectores más cercanos"? ¿Qué hace HNSW por debajo? ¿Qué hace IVFFlat? ¿Por qué uno es mejor para ciertos casos y el otro para otros? ¿Qué significan exactamente parámetros como `m`, `ef_construction` y `ef_search`, y cómo se eligen sus valores sin recurrir a copiar los defaults sin entenderlos?

Eso es el siguiente artículo: **Anatomía de un índice vectorial: HNSW, IVFFlat y el horizonte de DiskANN**. Es el artículo más técnicamente denso de la sesión, pero también el que más impacto tiene sobre tu capacidad de tomar decisiones operativas con criterio cuando llegue el momento de poner un sistema RAG en producción.