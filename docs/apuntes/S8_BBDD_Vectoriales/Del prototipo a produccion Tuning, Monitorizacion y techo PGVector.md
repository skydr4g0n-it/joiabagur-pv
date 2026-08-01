# Del prototipo a producción: tuning, monitorización y techo de pgvector

Creada: 6 de junio de 2026 14:06
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S8. Bases de datos vectoriales (https://app.notion.com/p/S8-Bases-de-datos-vectoriales-377ea9ca03c48099b3eadf17047947a7?pvs=21)

Al terminar el ejercicio pre-sesión, tu servicio IA tiene un Postgres con pgvector, un schema bien diseñado, un endpoint de búsqueda funcional y un script de validación. Es un sistema correcto y suficiente para el corpus de ejemplo del programa. También es, casi por definición, un sistema **de desarrollo**: corre en Docker local, con defaults de PostgreSQL pensados para un demo, sin índice vectorial todavía, sin métricas, sin estrategia de mantenimiento, sin pensamiento sobre qué pasa cuando el corpus crece de cientos a millones de chunks.

Este último artículo cubre las piezas que cruzan esa frontera. No son piezas que el alumno vaya a aplicar literalmente en el ejercicio — los volúmenes del proyecto del programa no las requieren — pero son las decisiones que separan un sistema RAG que "funciona en la sesión 09" de uno que "funciona en producción durante dos años sin sobresaltos". Y son también las decisiones que vas a necesitar argumentar el día que tu equipo decida llevar a producción un sistema basado en pgvector, dentro o fuera de este programa.

El recorrido tiene cuatro partes. Primero, la regla más importante: por qué el sizing de memoria es la decisión que más impacta el rendimiento, y cómo se calcula. Segundo, los parámetros de construcción del índice y por qué los defaults de PostgreSQL son inadecuados para construir un índice HNSW serio. Tercero, halfvec — la cuantización que reduce a la mitad el almacenamiento sin pérdida significativa de calidad. Cuarto, la monitorización operativa con `pg_stat_user_indexes` y el ciclo de mantenimiento (REINDEX, VACUUM, ANALYZE). Cerramos con las señales objetivas que indican que pgvector ha llegado a su techo en un caso concreto y conviene migrar.

## **Sizing de memoria: la regla que gobierna todo lo demás**

Hay una afirmación que merece ser literal: el rendimiento de un sistema pgvector con índices HNSW se determina en un 80% por una sola variable, y esa variable es **si el índice cabe en memoria o no**. Todo lo demás — `ef_search`, parámetros de construcción, modelo de embeddings, hardware — son refinamientos sobre esa cuestión central. Si el índice HNSW vive cómodamente en `shared_buffers` y en el cache del sistema operativo, las queries son de pocos milisegundos. Si el índice no cabe y Postgres tiene que leer páginas desde disco en cada consulta, ningún parámetro va a recuperar la latencia.

La razón es estructural. HNSW es un grafo: una búsqueda recorre múltiples nodos saltando entre vecinos. Si cada salto implica una lectura de SSD, lo que en RAM serían 5 microsegundos pasa a ser 100 microsegundos por salto, y con 30 saltos típicos por query la latencia se va a 3 ms solo por I/O — sin contar el cálculo de distancias, sin contar el round-trip de red. Si el SSD está ocupado con otros workloads, la cola de I/O se traduce en latencia adicional impredecible. Este es el famoso "long tail" que ningún tuning de aplicación arregla.

El sizing práctico tiene tres componentes. **El espacio que ocupan los vectores en disco**: para `text-embedding-3-small`, cada vector son 1536 dimensiones × 4 bytes = 6.144 bytes, o aproximadamente 6 KB. Un millón de chunks consume unos 6 GB solo en vectores. **El índice HNSW**: aproximadamente 2× a 3× el espacio de los vectores subyacentes para el default `m = 16`. Un millón de chunks produce un índice HNSW de unos 12 a 18 GB. **El overhead de Postgres**: connection pools, work_mem, OS buffers, WAL buffers. En sumatorio, una regla práctica conservadora es que necesitas hardware con RAM total mayor o igual a 1.5× el tamaño del índice más los vectores.

Para los volúmenes del proyecto del programa esto no es un problema: cientos de miles de chunks producen un índice de pocos GB que cabe sin esfuerzo en cualquier hardware razonable. El problema aparece cuando un equipo extrapola el setup del prototipo a un cliente con varios millones de presupuestos y descubre, en producción, que la latencia que en pruebas era de 5 ms ahora es de 500 ms porque el índice ya no entra en memoria. Es uno de los modos de fallo más comunes en migraciones de pgvector a entornos reales.

La configuración concreta de PostgreSQL que controla esto se reduce a tres parámetros que vienen en `postgresql.conf` o se pasan como flags al arrancar el contenedor:

- `shared_buffers` es la memoria que PostgreSQL reserva para su propio cache. La heurística estándar es 25% de la RAM total disponible. Para un servidor con 32 GB de RAM, `shared_buffers = '8GB'`.
- `effective_cache_size` no es una asignación real de memoria, sino una pista al query planner sobre cuánta memoria total (PostgreSQL + OS cache) está disponible. La heurística es 75% de la RAM total. Para los 32 GB del ejemplo, `effective_cache_size = '24GB'`.
- `work_mem` controla cuánta memoria puede usar cada operación (sort, hash join). Para workloads con búsqueda vectorial, valores de 64-256 MB son razonables.

Los defaults de PostgreSQL para `shared_buffers` (128 MB) y `work_mem` (4 MB) son apropiados para una base de datos pequeña en un servidor compartido, no para un servicio RAG en producción. Esto es lo primero que cambias cuando despliegas.

![articulo-05-figura-01-sizing-memoria.jpg](https://media1-production-mightynetworks.imgix.net/asset/fdc59abd-77a6-48be-b0bd-bbc8c13690da/articulo-05-figura-01-sizing-memoria.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Construcción del índice: parámetros que no son los de la query**

Cuando ejecutas `CREATE INDEX ... USING hnsw`, Postgres construye el grafo completo en una operación que es esencialmente una query masiva que pre-calcula muchísimas distancias entre vectores. Esa operación tiene sus propios parámetros, distintos de los que afectan a la query.

`maintenance_work_mem` es el más importante. Controla cuánta memoria puede usar PostgreSQL durante operaciones de mantenimiento de índices. El default es 64 MB, lo cual es trágico para construir un índice HNSW: si el grafo en construcción no cabe en ese buffer, Postgres cae a una construcción basada en disco que es entre 10× y 50× más lenta. Para un corpus de 5 millones de vectores de 1536 dimensiones, necesitarás entre 8 y 16 GB de memoria de mantenimiento. Antes de construir un índice grande, súbelo:

```sql
SET maintenance_work_mem = '4GB';
SET max_parallel_maintenance_workers = 4;
CREATE INDEX CONCURRENTLY chunks_embedding_idx
ON chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 128);
```

`max_parallel_maintenance_workers` controla cuántos workers paralelos pueden trabajar en la construcción del índice. El default es 2, conservador. Con 4 workers, un índice HNSW de un millón de filas que en serial tardaría 30 minutos puede construirse en 8 a 10 minutos. El techo lo marca tu número de vCPUs disponibles. En tu `docker-compose.yml`, también necesitas declarar `shm_size` suficiente: los workers paralelos comparten memoria vía `/dev/shm`, y si esa zona es pequeña, los workers crashean con errores OOM crípticos al final de una construcción de horas.

`CONCURRENTLY` es crítico para producción. Sin esa palabra clave, `CREATE INDEX` bloquea la tabla para escrituras durante toda la construcción. Para un índice que tarda media hora, eso es media hora sin poder ingestar documentos nuevos. Con `CONCURRENTLY`, la construcción es más lenta (entre 1.5× y 2× según carga concurrente) pero la tabla sigue aceptando escrituras. En desarrollo, `CONCURRENTLY` es opcional. En producción, es obligatorio.

Las cifras concretas que dan referencia útil para sizing, tomadas de benchmarks públicos de 2026 sobre Postgres + pgvector 0.8 con HNSW (`m = 16`, `ef_construction = 128`) y embeddings de 1536 dimensiones:

![image.png](https://media1-production-mightynetworks.imgix.net/asset/cf9170b4-680f-4854-9206-4152327e7f79/4f05cb13f2d5d551.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El proyecto del programa, con sus volúmenes esperados, vive en la primera fila. Pero los números de las filas siguientes son los que justifican que halfvec — el siguiente tema — sea la decisión por defecto en cualquier escenario serio.

## **Halfvec: la cuantización que ahorra la mitad del almacenamiento**

Los embeddings de `text-embedding-3-small` se almacenan por defecto en pgvector como floats de precisión simple (32 bits, 4 bytes) por dimensión. Esa es la representación que el tipo `vector(1536)` usa. La precisión de 32 bits es heredada de cómo los modelos generan los embeddings y de cómo PostgreSQL almacena floats nativamente, pero es **mucho más precisión de la que la búsqueda semántica necesita**.

El tipo `halfvec` que pgvector introdujo en la versión 0.7 almacena cada dimensión en 16 bits (half-precision float) en lugar de 32. El espacio se reduce a la mitad, los tiempos de construcción del índice se reducen aproximadamente a la mitad también, y el recall sobre embeddings normalizados de OpenAI se mantiene por encima del 99% en los benchmarks publicados. No es una cuantización agresiva como la binaria (que reduce cada dimensión a 1 bit y degrada significativamente el recall); es una pérdida de precisión que en la práctica resulta indistinguible de la representación completa para la inmensa mayoría de casos de uso.

![articulo-05-figura-02-halfvec.jpg](https://media1-production-mightynetworks.imgix.net/asset/38057f76-ae22-4ce1-ad07-c6e5aa10cba6/articulo-05-figura-02-halfvec.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La recomendación operativa en 2026 es clara: **empieza con halfvec desde el día uno** si vas a producción. Migrar de `vector` a `halfvec` cuando ya tienes decenas de millones de vectores en la tabla es una operación dolorosa que requiere reembedear o recopiar todo el corpus. Tomar la decisión correcta al diseñar el schema te ahorra ese coste.

En la práctica, esto cambia ligeramente el schema y la creación del índice:

```sql
- Schema: la columna sigue siendo vector(1536) pero indexamos halfvecCREATE INDEX chunks_embedding_idx
ON chunks
USING hnsw ((embedding::halfvec(1536)) halfvec_cosine_ops)WITH (m = 16, ef_construction = 128);
```

La expresión `embedding::halfvec(1536)` cuantiza el vector en memoria al construir el índice, sin tocar la columna original. La operator class correspondiente es `halfvec_cosine_ops` (y sus equivalentes `halfvec_l2_ops`, `halfvec_ip_ops`). Las queries siguen funcionando con el operador `<=>` sin cambios — el cast se aplica automáticamente cuando el planner detecta el índice.

Para el proyecto del programa no usamos halfvec en el ejercicio pre-sesión porque mantenemos el setup mínimo, pero es lo primero que añadirías al pasar de prototipo a producción real.

## **Monitorización operativa: ver lo que tu índice está haciendo**

Una vez el sistema está en producción, hay tres preguntas que deberías poder contestar en cualquier momento: ¿se está usando el índice?, ¿están las queries devolviendo resultados en el tiempo esperado?, y ¿está el índice degradándose con el tiempo? Postgres trae herramientas para las tres.

**¿Se está usando el índice?** La vista `pg_stat_user_indexes` mantiene contadores acumulativos por índice. El campo `idx_scan` indica cuántas veces se ha usado un índice desde el último reset de estadísticas, y `last_idx_scan` (PostgreSQL 16+) indica cuándo fue el uso más reciente. Una query útil de checkup periódico:

sql

`SELECT indexrelname AS index_name, idx_scan AS scans, last_idx_scan AS last_used, pg_size_pretty(pg_relation_size(indexrelid)) AS size FROM pg_stat_user_indexes WHERE relname = 'chunks' ORDER BY idx_scan DESC;`

Si tu índice vectorial principal tiene `idx_scan = 0` después de un período significativo en producción, algo no está bien — y casi siempre es el antipatrón del artículo anterior: queries usando un operador distinto al de la operator class del índice. Es la forma más rápida de detectar el bug silencioso.

**¿Cuánto tarda cada query?** El sistema canónico para esto es `pg_stat_statements`, una extensión que registra estadísticas agregadas de cada query distinta ejecutada: número de llamadas, tiempo total, tiempo promedio, tiempo mínimo y máximo. Permite identificar qué queries son los principales consumidores de tiempo y detectar regresiones cuando se introducen cambios. Para sistemas RAG, conviene tener esta extensión habilitada desde el primer día. El plugin Logfire que ya tenemos en el stack del programa también captura estos datos, integrándolos con las trazas de las llamadas a LLM, lo cual da una visión end-to-end de dónde se va el tiempo en cada request.

**¿Está el índice degradándose?** Aquí es donde entran las operaciones de mantenimiento. Un índice HNSW que en su construcción inicial era óptimo puede degradarse con el tiempo por dos razones. La primera, **bloat**: actualizaciones y borrados dejan páginas con espacio muerto que el índice no recupera automáticamente. La segunda, **estadísticas obsoletas**: el query planner se basa en estadísticas que se actualizan con `ANALYZE`, y si están desactualizadas, puede tomar decisiones subóptimas (por ejemplo, ignorar el índice porque cree que la tabla es más pequeña de lo que es).

El ciclo de mantenimiento básico se compone de tres operaciones:

- `VACUUM ANALYZE chunks` recupera espacio muerto y actualiza estadísticas. Postgres lo hace automáticamente en background con `autovacuum`, pero para tablas con mucha rotación conviene programarlo explícitamente en una ventana de bajo tráfico.
- `REINDEX INDEX CONCURRENTLY chunks_embedding_idx` reconstruye el índice desde cero. Es la operación que recupera el rendimiento cuando el bloat ha degradado el índice. La palabra clave `CONCURRENTLY` permite que el reindex se haga sin bloquear las queries: Postgres construye un índice nuevo al lado, valida que funciona, y atómicamente intercambia el viejo por el nuevo.
- `ANALYZE chunks` sin `VACUUM` cuando solo necesitas actualizar estadísticas. Es rápido y barato.

La cadencia recomendada para sistemas RAG con escrituras moderadas (decenas a cientos de inserciones por día) es: `ANALYZE` automático con autovacuum, `VACUUM ANALYZE` semanal en ventana de bajo tráfico, y `REINDEX CONCURRENTLY` mensual o cuando observes que la latencia del índice empieza a degradarse perceptiblemente. Para sistemas con escrituras muy intensas, las cadencias se aceleran proporcionalmente.

## **Las señales objetivas de migración**

pgvector es la elección correcta para el proyecto del programa y para la inmensa mayoría de sistemas RAG en producción en 2026. No es la elección correcta para todos los casos. Hay tres señales objetivas que indican que has llegado al techo de pgvector en un escenario concreto y que conviene evaluar migración a un sistema dedicado (Qdrant, Milvus) o a una extensión más especializada (pgvectorscale con DiskANN). No son matices ni preferencias: son métricas medibles.

![articulo-05-figura-03-senales-migracion.jpg](https://media1-production-mightynetworks.imgix.net/asset/e0fa3713-fcdb-4389-a12d-748fbe26b637/articulo-05-figura-03-senales-migracion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Señal 1: el índice HNSW ya no cabe en memoria.** Cuando el tamaño del índice supera significativamente lo que `shared_buffers` y el OS cache pueden retener, la latencia p99 se vuelve impredecible. Si compruebas el ratio entre el tamaño del índice y la RAM disponible y es mayor a ~70%, estás en zona de riesgo. La solución a corto plazo es escalar hardware vertical (más RAM); la solución a medio plazo es migrar a pgvectorscale con DiskANN, que está específicamente diseñado para mantener latencia baja con índices que viven parcialmente en SSD.

**Señal 2: la latencia p99 supera tu SLO operativo de forma sostenida.** Si las queries de búsqueda vectorial empiezan a ver p99 por encima del umbral que tu producto puede tolerar (típicamente 100-200 ms para RAG interactivo), y has descartado problemas de tuning de PostgreSQL, de antipatrones de query y de bloat, lo que estás viendo es probablemente el techo de pgvector para tu volumen y patrón de acceso. A esa altura, una BBDD vectorial dedicada como Qdrant o Milvus suele dar entre 2× y 5× mejor p99 a igualdad de hardware.

**Señal 3: necesitas funcionalidades nativas que pgvector no tiene.** Búsqueda multi-modal con embeddings de texto + imagen como ciudadanos de primera clase, sharding multi-región nativo con SLA estricto, modelos de coste muy específicos. Si tu producto las requiere de verdad y no son simples nice-to-haves, una opción dedicada va a ser mejor inversión que pelear con pgvector para imitarlas.

Lo importante es que ninguna de estas señales se basa en "qué es más cool" o "qué usa la competencia". Son métricas verificables sobre tu sistema concreto. Si ninguna de las tres se cumple, mantener pgvector es casi siempre la decisión correcta — incluso si tienes la tentación de migrar a algo "más serio". La complejidad operativa que añade un sistema dedicado tiene su propio coste, y solo se justifica cuando las señales lo exigen.

## **Cierre de la sesión**

Has recorrido el arco completo. Sabes por qué existen las bases de datos vectoriales y cuándo añadirlas al stack se justifica. Sabes qué hay en el mercado en 2026 y por qué la decisión del programa es pgvector. Conoces los tres algoritmos de indexación (IVFFlat, HNSW, DiskANN) y los parámetros operativos de cada uno. Has visto el modelo de datos concreto del proyecto, las tres métricas de distancia, y el antipatrón silencioso que destruye el rendimiento. Y ahora sabes también qué separa un sistema en desarrollo de uno en producción: sizing de memoria, parámetros de construcción, cuantización con halfvec, ciclo de mantenimiento, y las señales objetivas de migración.

El ejercicio pre-sesión cubre la primera mitad de ese recorrido — construir el sistema que persiste, indexa y consulta. La sesión en vivo cubre la otra mitad — añadir el índice HNSW y medir su impacto, comparar las tres métricas de distancia sobre tu corpus, construir búsqueda híbrida combinando full-text con similitud vectorial, y aplicar las técnicas de tuning que acabas de leer. Al cerrar la sesión 08, tienes el cimiento sobre el que toda la fase RAG del programa se construye: una capa de datos vectorial bien diseñada, indexada, monitorizada, y con un horizonte operativo claro.

Lo siguiente, en la sesión 09, es empezar a construir RAG propiamente dicho: cómo el retriever que acabas de montar se integra con el generador, qué estrategias de recuperación hay más allá del top-k básico, y cómo la respuesta del LLM se ancla en los chunks que recuperamos. El servicio IA tiene ahora memoria. La sesión 09 le enseña a usarla.