# Diseño del esquema y búsqueda semántica

Creada: 6 de junio de 2026 14:04
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S8. Bases de datos vectoriales (https://app.notion.com/p/S8-Bases-de-datos-vectoriales-377ea9ca03c48099b3eadf17047947a7?pvs=21)

Los tres artículos anteriores han construido la teoría: por qué existen las bases de datos vectoriales, qué hay en el mercado y por qué elegimos pgvector, y cómo funcionan por dentro los índices HNSW e IVFFlat. Lo que falta es lo más importante para que el ejercicio pre-sesión salga bien: el modelo concreto de las tablas que va a sostener todo el sistema, los operadores SQL que se usarán para hacer búsqueda semántica, y el antipatrón silencioso que destruye el rendimiento sin levantar errores.

Este artículo es la pieza aplicada de la sesión. Aterrizamos el esquema del proyecto del programa, las tres métricas de distancia con el caso particular de los embeddings normalizados de OpenAI, y la regla operativa que cierra la mitad del valor de la sesión: el operador de la query y la operator class del índice tienen que estar alineados, siempre, sin excepción. Cuando no lo están, Postgres no emite ningún error: simplemente desactiva el índice silenciosamente, cae a sequential scan, y la latencia se multiplica por mil. Es el bug operativo más caro y más fácil de cometer en pgvector, y conviene salir del artículo conociéndolo.

## **El modelo relacional: dos tablas, no una**

Cuando un alumno se enfrenta por primera vez al modelado de un sistema RAG, el reflejo natural es crear una única tabla `chunks` que contenga todo lo necesario: el texto del chunk, su embedding, y la metadata del documento al que pertenece. Funciona en cuanto al producto final, pero introduce duplicación y pierde garantías que un modelo relacional bien diseñado da gratis. Si un presupuesto produce 17 chunks, vas a repetir la metadata del documento (tipo, sector, fecha, cliente) 17 veces. Si actualizas la metadata del documento, tienes que tocar 17 filas en coherencia. Si borras el documento, tienes que recordar borrar sus chunks. Cuando llegas a varios cientos de documentos con miles de chunks, esa duplicación es un problema operativo real.

El modelo correcto para el proyecto es exactamente el que el ejercicio pre-sesión te pide construir: dos tablas con una relación uno-a-muchos. La tabla `documents` representa cada presupuesto histórico una sola vez, con su metadata; la tabla `chunks` contiene los fragmentos derivados del chunking estructural de cada documento, cada uno con su embedding y su propio bloque de metadata flexible. La integridad referencial entre ambas, con `ON DELETE CASCADE`, garantiza que eliminar un documento elimina automáticamente todos sus chunks sin necesidad de lógica aplicativa.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id            BIGSERIAL PRIMARY KEY,
    source_path   TEXT NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE chunks (
    id            BIGSERIAL PRIMARY KEY,
    document_id   BIGINT NOT NULL
                  REFERENCES documents(id) ON DELETE CASCADE,
    chunk_type    VARCHAR(50) NOT NULL,
    content       TEXT NOT NULL,
    embedding     vector(1536),
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

![articulo-04-figura-01-schema-relacional.jpg](https://media1-production-mightynetworks.imgix.net/asset/d3403943-bd0e-4546-8302-fdebe49b5ff6/articulo-04-figura-01-schema-relacional.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Cinco decisiones de este schema merecen una nota explícita porque vas a tener que defenderlas (en el README del proyecto, y posiblemente en cualquier sistema RAG que diseñes fuera del programa).

**La separación entre columnas tipadas y JSONB.** La metadata estable que sabes que vas a consultar de forma estructurada — el tipo de documento, el tipo de chunk, las fechas — va en columnas tipadas. La metadata que el chunker puede enriquecer con campos arbitrarios (sector inferido del contenido, tecnologías mencionadas, scope, tags) va en `JSONB`. Esta separación te da lo mejor de dos mundos: las queries por columnas tipadas son rápidas y aprovechan índices B-tree convencionales, y las queries por JSONB son flexibles y aprovechan índices GIN. El error opuesto — meter toda la metadata en una sola columna `JSONB` "por flexibilidad" — funciona pero pierde eficiencia y legibilidad. El error inverso — añadir una columna nueva al schema cada vez que el chunker quiere persistir un campo más — convierte cada cambio del pipeline en una migración. La división propuesta evita ambos extremos.

**El índice GIN sobre** `metadata`**.** Sin él, una query como `WHERE metadata->>'sector' = 'fintech'` hace sequential scan sobre toda la tabla. Con él, Postgres puede usar el índice para reducir drásticamente las filas examinadas. El coste de mantenimiento del índice GIN es bajo para volúmenes en el rango del proyecto, y el beneficio en consultas con filtros estructurados es enorme. Lo veremos en directo cuando comparemos planes de ejecución.

`vector(1536)`**.** La dimensionalidad de `text-embedding-3-small`, el modelo del proyecto. Está hardcodeada en el schema y eso es deliberado: cambiarla implica reembedear todo el corpus, lo que es una operación costosa que no debería disparar accidentalmente nadie. Si en el futuro migras a `text-embedding-3-large` (3072 dimensiones), la migración pasa por una columna nueva, no por modificar la existente.

`embedding nullable`**.** Permite insertar un chunk en una transacción y rellenar el embedding después si el cálculo fallase. En el ejercicio no lo aprovechamos así (ingestamos chunk+embedding atómicamente), pero deja la puerta abierta a patrones de ingesta asíncrona que veremos más adelante en el programa.

**No hay índice vectorial todavía.** El esquema del ejercicio pre-sesión deliberadamente omite el índice HNSW. La sesión en vivo arranca midiendo la latencia del endpoint `/search` sin índice, creando el índice, y midiendo de nuevo. Es la única forma de aterrizar empíricamente el orden de magnitud que el índice aporta.

## **Las tres métricas de distancia: cosine, L2 e inner product**

pgvector expone tres operadores de distancia entre vectores, cada uno con su propia semántica geométrica y su propia operator class para la creación de índices. Conviene tener claros los tres porque la elección entre ellos no es una preferencia estética: depende del modelo de embeddings que uses y del tipo de problema que estés resolviendo.

![image.png](https://media1-production-mightynetworks.imgix.net/asset/9d49615d-c625-4b1e-be3b-6c537c613240/5c228af8c3e13003.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

![articulo-04-figura-02-metricas-distancia.jpg](https://media1-production-mightynetworks.imgix.net/asset/b4c5f69a-8f2b-4a19-aba7-21c7fad79dce/articulo-04-figura-02-metricas-distancia.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Distancia coseno (**`<=>`**).** Mide el ángulo entre dos vectores ignorando la magnitud. Dos vectores que apuntan en la misma dirección tienen distancia coseno 0, sin importar si uno mide 1 unidad o 1000. Es la métrica estándar para embeddings de texto provenientes de modelos modernos (OpenAI, Cohere, Voyage, los principales de Hugging Face), porque esos modelos están entrenados para que el significado semántico se codifique en la dirección del vector, no en su longitud. Para el proyecto del programa, con embeddings de `text-embedding-3-small`, es la elección por defecto razonable.

**Distancia L2 (**`<->`**).** Mide la distancia euclídea, la "distancia en línea recta" entre los extremos de los dos vectores. Es sensible a la magnitud: dos vectores que apuntan en la misma dirección pero tienen longitudes distintas tienen distancia L2 mayor que cero. Es la métrica natural para datos donde la magnitud carga información — coordenadas espaciales, datos de sensores físicos, embeddings de imagen donde la intensidad de los píxeles importa. Para embeddings de texto rara vez es la elección correcta.

**Inner product negativo (**`<#>`**).** Mide el producto escalar, sensible tanto al ángulo como a la magnitud. pgvector devuelve el valor negado porque Postgres solo soporta ordenación ascendente en operadores de índice, y queremos que `ORDER BY ... ASC` devuelva primero los más similares. Para vectores normalizados (longitud = 1), el inner product es **matemáticamente equivalente** al coseno en términos de ordenación, pero más eficiente computacionalmente porque ahorra el paso de dividir por las normas.

Para `text-embedding-3-small` los tres operadores funcionan, pero solo uno de ellos es la elección óptima. La clave está en una propiedad poco subrayada del modelo: **OpenAI normaliza sus embeddings**. Todos los vectores que salen de la API tienen norma euclídea igual a 1. Eso tiene una consecuencia práctica importante: para vectores normalizados, distancia coseno e inner product producen exactamente el mismo orden de resultados. La elección entre `<=>` y `<#>` es indiferente en términos de qué chunks se recuperan; lo único que cambia es la eficiencia computacional, donde `<#>` gana ligeramente porque ahorra el paso de cálculo de normas que en realidad no necesita (las normas ya son 1).

A pesar de esa eficiencia, en el proyecto del programa usamos `<=>` y `vector_cosine_ops`. Hay dos razones. La primera es convencional: la literatura RAG y la mayoría de tutoriales públicos usan coseno, y aprender con la convención dominante reduce fricción al consultar fuentes externas. La segunda es práctica: si en el futuro algún equipo migra el sistema a un modelo de embeddings que no normaliza (un Sentence Transformer local, por ejemplo), la query SQL seguirá funcionando sin cambios y sin sorpresas. Usar `<#>` "por eficiencia" hoy te obliga a recordar para siempre que solo es seguro mientras los embeddings estén normalizados.

## **El antipatrón que destruye el rendimiento sin levantar errores**

Aquí entra la pieza operativa que es el corazón del artículo, el bug silencioso que más caro sale en pgvector. Cuando creas un índice HNSW con `vector_cosine_ops`, ese índice solo acelera queries que usan el operador `<=>`. Si la query usa `<->`, el índice **no se activa**. Postgres no emite ningún error ni warning. La query funciona y devuelve resultados. Lo único que cambia es que internamente Postgres ha caído a sequential scan, recalculando la distancia L2 contra cada fila de la tabla. El resultado es correcto en términos del orden por distancia L2, pero la latencia que en una tabla de un millón de filas debería ser de unos pocos milisegundos pasa a ser de decenas de segundos.

La regla operativa es estricta y simple:

> **El operador de la query (**`<=>`**,** `<->`**,** `<#>`**) tiene que coincidir con la operator class del índice (**`vector_cosine_ops`**,** `vector_l2_ops`**,** `vector_ip_ops`**).**
> 

![articulo-04-figura-03-antipatron.jpg](https://media1-production-mightynetworks.imgix.net/asset/a2d5bc37-7472-40cb-9768-09eda5327788/articulo-04-figura-03-antipatron.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Cualquier desalineamiento entre los dos rompe el uso del índice sin emitir advertencias. Es uno de los bugs más caros y más fáciles de cometer en pgvector. Pasa cuando un desarrollador copia código de una fuente externa que usaba otra métrica, cuando el equipo cambia de modelo de embeddings sin actualizar las queries, o simplemente cuando alguien escribe `<->` por inercia porque es el operador más intuitivo (parece una flecha de "distancia").

En el proyecto del programa, el índice se crea con `vector_cosine_ops` y todas las queries usan `<=>`. Esto significa que cuando en el directo construyamos el `CREATE INDEX`, lo haremos exactamente así:

```sql
CREATE INDEX chunks_embedding_idx
ON chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 128);
```

Y cuando ejecutemos la query de búsqueda, lo haremos exactamente así:

```sql
SELECT id, document_id, chunk_type, content, metadata,
       embedding <=> :query_vector AS distance
FROM chunks
ORDER BY embedding <=> :query_vector
LIMIT :k;
```

Los dos `<=>` en la SELECT (uno para devolver la distancia como columna, otro para ordenar) son obligatorios y son el mismo operador. La distancia se calcula una sola vez por fila gracias a la optimización del query planner; conceptualmente, lo importante es que el operador en el `ORDER BY` sea exactamente el mismo que la operator class del índice.

### **Cómo verificarlo: EXPLAIN ANALYZE**

La forma de confirmar que el índice se está usando es `EXPLAIN ANALYZE` sobre la query. Si la salida muestra `Index Scan using chunks_embedding_idx`, el índice está activo. Si muestra `Seq Scan on chunks`, no lo está, y hay un problema que debug. Las tres causas más comunes en orden de frecuencia son:

1. **Desalineamiento operador/operator class.** El más frecuente. Vista la regla anterior, casi nunca pasa si llevas la disciplina de copiar el operador de la operator class del índice.
2. **Filtros relacionales muy selectivos.** Si el `WHERE` reduce el resultado a un puñado de filas, Postgres puede decidir que es más barato hacer sequential scan sobre las filas ya filtradas que pasar por el índice vectorial. Esto se resuelve con `hnsw.iterative_scan`, que vemos en directo.
3. **Estadísticas obsoletas.** Después de cargar muchos vectores nuevos, las estadísticas de la tabla pueden quedar desactualizadas y el planner toma decisiones subóptimas. Un `ANALYZE chunks` periódico mantiene el planner informado.

El reflejo operativo correcto cuando una query semántica funciona pero es inexplicablemente lenta es: `EXPLAIN ANALYZE` primero, antes de asumir cualquier otra cosa. Es la herramienta más útil que pgvector hereda gratis de PostgreSQL, y es la diferencia entre un equipo que produce sistemas RAG performantes y uno que pelea con latencias misteriosas durante semanas.

## **La query completa: tres capas en una sentencia atómica**

Hasta ahora hemos hablado solo de búsqueda vectorial pura, sin filtros. En la práctica, casi nadie quiere "los k chunks más cercanos a la query" sin más; lo que quiere es algo como "los k chunks más cercanos a la query, del sector fintech, ingestados en los últimos 24 meses, de presupuestos con monto entre 50k y 200k". Esos filtros viven en columnas tipadas (`metadata`, `ingested_at`) y en relaciones (`document_id` apuntando a `documents`). En pgvector, todo eso cabe en una única query SQL atómica:

```sql
SELECT c.id, c.content, c.chunk_type,
       c.embedding <=> :query_vector AS distance,
       d.metadata->>'sector' AS sector,
       d.ingested_at
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.metadata->>'sector' = 'fintech'
  AND d.ingested_at > NOW() - INTERVAL '24 months'
  AND (d.metadata->>'budget')::numeric BETWEEN 50000 AND 200000
ORDER BY c.embedding <=> :query_vector
LIMIT 5;
```

Esta query mezcla búsqueda semántica con filtros relacionales, filtros sobre JSONB, joins entre tablas, y proyección de campos arbitrarios — todo con garantías ACID, todo en una sola operación atómica. Es exactamente el tipo de query que un sistema RAG sobre datos empresariales necesita y que Pinecone, Qdrant o Weaviate no pueden hacer sin coordinación con otro sistema. Es la razón principal por la que pgvector es la elección correcta para el proyecto del programa, y la propiedad que más vas a echar en falta el día que migres a una BBDD vectorial dedicada por razones de escala.

Hay un matiz importante que el directo aborda en profundidad: cuando los filtros del `WHERE` son muy selectivos (reducen el resultado a una pequeña fracción de las filas), el índice HNSW puede tener dificultades porque está optimizado para encontrar los k vecinos en el conjunto completo, no en un subconjunto pre-filtrado. pgvector 0.8 introdujo `hnsw.iterative_scan` precisamente para resolver este caso: cuando el motor detecta que ha devuelto menos de k resultados después de aplicar el filtro, expande iterativamente la búsqueda hasta cumplir el `LIMIT`. Es una funcionalidad relativamente reciente y muy útil; la activaremos y mediremos su impacto en directo.