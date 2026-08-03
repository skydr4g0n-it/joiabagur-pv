# Anatomía de un índice vectorial: HNSW, IVFFlat y el horizonte de DiskANN

Creada: 6 de junio de 2026 14:03
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S8. Bases de datos vectoriales (https://app.notion.com/p/S8-Bases-de-datos-vectoriales-377ea9ca03c48099b3eadf17047947a7?pvs=21)

Si has llegado hasta aquí siguiendo los dos artículos anteriores, sabes ya que vas a usar pgvector y sabes por qué. Lo que todavía no sabes — y lo que separa al desarrollador que copia los defaults del que toma decisiones operativas con criterio — es qué pasa exactamente cuando ejecutas `CREATE INDEX ... USING hnsw` y por qué la diferencia entre los parámetros que pongas ahí marca dos órdenes de magnitud en latencia, recall y consumo de memoria.

Este artículo es la apertura de esa caja negra. No vamos a derivar matemáticas; vamos a construir la intuición geométrica de los algoritmos y a aterrizar cada uno en los parámetros concretos que pgvector expone, con los valores reales que el alumno va a tocar en producción. Hay tres familias relevantes en el panorama actual: el índice IVFFlat (basado en particionamiento del espacio), el índice HNSW (basado en grafos navegables) y el horizonte de DiskANN (la siguiente generación, que aparece como pgvectorscale y como `diskann` en Azure). Las tres resuelven el mismo problema con estrategias geométricas distintas, y conocer las tres es lo que te permite reconocer en qué momento la elección por defecto deja de ser la correcta.

Antes de entrar en cada una, conviene recordar la línea base contra la que se compara. Sin ningún índice, pgvector hace un **sequential scan**: para cada query, calcula la distancia entre la query y los embeddings de las filas que sobreviven a los filtros relacionales (si los hay), ordena, y devuelve los k más cercanos. Es el método más simple, garantiza recall del 100% y devuelve resultados deterministas. La latencia crece linealmente con el número de vectores, y en el momento en que ese número entra en las decenas de miles, hablar de "interactivo" deja de ser realista. Los índices ANN existen para romper esa linealidad. Cada uno lo hace de una forma distinta.

## **IVFFlat — partir el espacio en celdas y mirar solo las que importan**

La intuición de IVFFlat es la más sencilla de los tres. Si tienes un mapa de una ciudad con miles de restaurantes y un cliente te pregunta por los cinco más cercanos a su ubicación, lo razonable no es comparar la distancia uno a uno con todos los restaurantes de la ciudad. Lo razonable es identificar el barrio donde está el cliente, mirar los restaurantes de ese barrio y, si hay pocos, ampliar a los barrios vecinos. IVFFlat hace exactamente eso, pero en un espacio de 1536 dimensiones.

El proceso tiene dos fases. Primero, durante la construcción del índice, se aplica un algoritmo de clustering (k-means) sobre el conjunto de vectores existente, que identifica `lists` centroides — los "barrios". El espacio queda dividido en regiones llamadas **celdas de Voronoi**: a cada punto del espacio le corresponde la celda cuyo centroide es el más próximo. Cada vector almacenado se asigna a su celda correspondiente. La estructura resultante es una "lista invertida": para cada centroide, una lista de los vectores que viven en su celda. De ahí el nombre IVFFlat: *Inverted File index with Flat (uncompressed) vectors*.

![articulo-03-figura-01-ivfflat.jpg](https://media1-production-mightynetworks.imgix.net/asset/4d328abe-a04b-4aae-bd1f-fc21359ba595/articulo-03-figura-01-ivfflat.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Durante la consulta, se invierte la lógica. Dada una query, se calcula su distancia a los `lists` centroides — operación rápida, porque `lists` suele estar entre 100 y 10.000, mucho menor que el número total de vectores. Se eligen los `probes` centroides más cercanos a la query, y la búsqueda se restringe a los vectores que viven en esas celdas. Si `probes = 1`, miras solo el barrio del cliente; si `probes = 10`, miras también los nueve vecinos más próximos. El recall sube con `probes`, la latencia también.

El parámetro `lists` se elige durante la construcción del índice y la heurística estándar es `lists ≈ sqrt(rows)` para corpus de hasta un millón de vectores, escalando a `rows/1000` para corpus mayores. Para los cientos de miles de chunks que tendrá el proyecto del programa, esto se traduce en valores entre 100 y 1000 — números pequeños, fáciles de manejar. El parámetro `probes` se elige en cada query (o por defecto en la sesión) y la heurística estándar es `probes ≈ sqrt(lists)`: si `lists = 100`, prueba con `probes = 10`. Subir `probes` mejora recall y aumenta latencia de forma aproximadamente lineal.

IVFFlat tiene tres virtudes y dos defectos importantes. Las virtudes: construcción rápida (k-means sobre los embeddings es razonable hasta cientos de miles de vectores), memoria moderada (solo necesitas almacenar los centroides más los vectores agrupados, no estructuras adicionales), y trabaja bien en corpus mostly-static. Los defectos son los que casi siempre te lo descartan en RAG real: **necesita training** (no puedes crear el índice sobre una tabla vacía; necesitas que haya datos representativos para que k-means produzca centroides útiles), y **sufre con datos dinámicos** (a medida que insertas vectores nuevos, las celdas que el k-means original definió empiezan a no representar la distribución real, y el recall se degrada silenciosamente hasta que reconstruyes el índice). Para un sistema RAG donde el corpus crece con cada nuevo presupuesto ingestado, esa degradación silenciosa es un riesgo operativo concreto.

El otro problema clásico de IVFFlat — que dos vectores cercanos pueden caer en celdas distintas si están cerca del borde — se mitiga con `probes` mayores, pero nunca desaparece. La calidad de los resultados depende fundamentalmente de la forma de los clusters que k-means encontró, y eso no es algo que controles directamente.

## **HNSW — un grafo multicapa que actúa como un GPS jerárquico**

HNSW resuelve el mismo problema desde un ángulo completamente distinto, y la analogía geográfica más útil no es la del mapa con barrios, sino la del sistema de carreteras de un país. Cuando quieres llegar a una dirección específica en un pueblo a 800 kilómetros, no recorres todos los caminos posibles. Coges una autopista que te acerca a la región general, luego una carretera nacional que te acerca a la zona, después una comarcal que te lleva al pueblo, y solo al final atraviesas calles locales hasta la dirección exacta. Cada nivel de la jerarquía cubre distancias distintas, y la combinación es lo que hace que el viaje sea logarítmico en vez de lineal.

HNSW construye exactamente esa jerarquía. Es un grafo dividido en capas. La capa inferior — la capa 0 — contiene todos los vectores almacenados, cada uno conectado a sus vecinos más cercanos por aristas cortas. Las capas superiores contienen subconjuntos cada vez más pequeños de vectores, elegidos al azar con una distribución exponencialmente decreciente: aproximadamente el 1% de los vectores aparece en la capa 1, el 0.01% en la capa 2, y así sucesivamente. Las aristas de las capas superiores cubren distancias largas; las de las inferiores, cortas.

La búsqueda funciona de arriba hacia abajo. Empiezas por un punto de entrada en la capa más alta y avanzas voraciosamente hacia el vecino que está más cerca de la query. Cuando ya no hay vecinos en esa capa que te acerquen más, bajas a la capa siguiente y continúas el proceso con resolución más fina. En la capa 0, donde ya estás muy cerca, exploras una vecindad amplia para encontrar los k vectores más próximos finales. La estructura es esencialmente una skip list aplicada a grafos: lo que las skip lists son a las listas enlazadas, HNSW lo es a los grafos de vecinos. El paper original de Malkov y Yashunin, publicado en 2018, mostró que esto produce complejidad logarítmica con recall consistentemente alto incluso en espacios de muy alta dimensión.

![articulo-03-figura-02-hnsw.jpg](https://media1-production-mightynetworks.imgix.net/asset/b1e14a9e-f27a-4a47-b038-e1b9a85e5627/articulo-03-figura-02-hnsw.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

En pgvector, HNSW se gobierna con tres parámetros. Los dos primeros son **build-time** (decididos al crear el índice y no se pueden cambiar después sin reconstruir): `m` y `ef_construction`. El tercero, `ef_search`, es **query-time** (se ajusta en cada sesión o transacción sin tocar el índice).

`m` es el número máximo de conexiones bidireccionales que cada vector tiene en cada capa del grafo. El valor por defecto es 16 y la comunidad ha convergido en que es el correcto para embeddings de 1536 dimensiones (los del OpenAI text-embedding-3-small del proyecto). Subir `m` a 32 o 48 mejora ligeramente el recall a costa de doblar la memoria del índice y prácticamente doblar el tiempo de construcción. El paper original lo nombra como el parámetro más importante, y casi nadie debería cambiarlo sin haber medido primero que el recall es insuficiente con los demás parámetros agotados. Para el proyecto del programa, `m = 16` es la elección correcta.

`ef_construction` es el tamaño de la lista dinámica de candidatos que el algoritmo mantiene mientras construye el grafo. El valor por defecto en pgvector es 64, pero la comunidad de 2026 ha convergido en que `ef_construction = 128` o incluso 200 es un punto de partida más razonable para producción, especialmente con embeddings de alta dimensión. El coste de subirlo es tiempo de construcción del índice (se duplica aproximadamente al pasar de 64 a 128), pero como la construcción se hace una vez y la búsqueda muchas, casi siempre vale la pena. Para el proyecto, empieza con `128` y solo bajes si el tiempo de construcción se vuelve un cuello de botella operativo.

`ef_search` es el más interesante y el más usado. Controla el tamaño de la lista de candidatos durante la consulta. El valor por defecto es 40 y se puede cambiar por sesión, por transacción o por query. Subirlo a 80 o 100 mejora recall a costa de latencia (la curva no es lineal: la mejora marginal de recall decrece, mientras que la latencia sube de forma aproximadamente lineal). Bajarlo a 20 acelera consultas con un coste de recall que puede ser aceptable para casos donde los k resultados se van a re-rankear después de todas formas. Es el parámetro que conviene tunear empíricamente: barres `ef_search` entre 10 y 200 sobre un conjunto representativo de queries, mides recall y latencia, y eliges el punto que mejor balancea ambos para tu caso de uso.

Las virtudes de HNSW son las opuestas a los defectos de IVFFlat. No necesita training: puedes construir un índice HNSW sobre una tabla con cero filas y luego ir insertando. Absorbe inserciones sin reconstrucciones (las nuevas filas se añaden al grafo de forma incremental). Y su recall es consistentemente alto, típicamente por encima del 95% con los defaults, sin las degradaciones silenciosas de IVFFlat. El coste es memoria: HNSW consume entre 2 y 5 veces más memoria que IVFFlat para el mismo número de vectores, porque tiene que almacenar el grafo completo además de los vectores. Para volúmenes hasta unos diez millones de vectores en hardware razonable, ese coste es perfectamente manejable. Para volúmenes mayores, empieza a apretar.

![articulo-03-figura-03-parametros-hnsw.jpg](https://media1-production-mightynetworks.imgix.net/asset/52f5d8ba-38ed-4ef5-b78a-5740d0d02998/articulo-03-figura-03-parametros-hnsw.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Para el proyecto del programa, HNSW es la elección correcta y los parámetros de partida son `m = 16`, `ef_construction = 128`, `ef_search = 40`. Estos son los valores que vamos a usar en directo cuando creemos el índice y los que vas a tocar empíricamente cuando midamos latencia y recall.

## **DiskANN — el horizonte que extiende pgvector más allá de la RAM**

Hay un tercer algoritmo que conviene conocer, aunque no lo vayas a usar en el proyecto del programa: **DiskANN**. Es la evolución natural cuando los volúmenes superan lo que cabe cómodamente en RAM y necesitas seguir manteniendo latencias bajas. El paper original es de Microsoft Research y se publicó en 2019; la implementación de Microsoft alcanza mil millones de vectores con recall del 95% y latencia de 5 ms en una sola máquina con SSD — una escala donde HNSW se vuelve inviable porque su índice no entra en memoria.

La intuición clave de DiskANN es que reemplaza la jerarquía multicapa de HNSW por un único grafo aplanado pero con aristas "largas" insertadas estratégicamente durante la construcción, mediante un algoritmo llamado Vamana. Esas aristas largas hacen el papel de los saltos entre capas de HNSW, pero como el grafo es plano, su layout en disco se puede optimizar para minimizar las lecturas de SSD durante la búsqueda. El truco operativo está en dos partes: una versión cuantizada y comprimida del grafo vive en memoria, lo que permite navegar rápido por candidatos aproximados; y solo cuando hay que comparar distancias finales se lee el vector completo desde el SSD. El resultado es que indexar mil millones de vectores requiere unos pocos GB de RAM en lugar de cientos.

En el ecosistema de Postgres, DiskANN aparece como **pgvectorscale**, una extensión open-source de Tiger Data (antes Timescale) que añade un tercer tipo de índice — `USING diskann` — sobre el tipo `vector` de pgvector. La sintaxis es la misma y los operadores de distancia también; solo cambia el algoritmo subyacente. Microsoft también ofrece su propia versión como extensión gestionada en Azure Database for PostgreSQL Flexible Server. Ambas implementaciones añaden, además del algoritmo en sí, una técnica de cuantización (Statistical Binary Quantization en pgvectorscale, Product Quantization en la versión de Azure) que reduce todavía más el footprint de memoria.

¿Cuándo migrar de HNSW a DiskANN? Las dos señales claras son: el índice HNSW ya no entra en `shared_buffers` y la latencia se degrada porque se hace I/O de disco en cada query; o el coste de RAM para sostener el índice supera al coste de SSD necesario para DiskANN. En 2026 los benchmarks públicos de Tiger Data reportan que pgvectorscale alcanza 471 QPS al 99% de recall sobre 50 millones de vectores, mientras que HNSW puro empieza a degradarse en ese rango. Para volúmenes por debajo de varios millones, HNSW sigue siendo más rápido y simple. Para el proyecto del programa estamos órdenes de magnitud por debajo de cualquier umbral de migración a DiskANN, así que lo mencionamos como horizonte y seguimos con HNSW.

## **La tabla de decisión: cuándo cada algoritmo gana**

La elección entre los tres no es una preferencia personal. Hay un mapa razonablemente claro:

**Sequential scan (sin índice).** Hasta unos pocos miles de vectores, especialmente si los datos son muy dinámicos (muchas inserciones, lecturas relativamente raras) o si necesitas recall del 100% garantizado por razones de auditoría o evaluación. Es también el baseline contra el que mides el impacto de añadir un índice ANN: si construyes HNSW y la latencia no baja significativamente, algo está mal (típicamente: el plan de ejecución no está usando el índice, lo veremos en directo).

**IVFFlat.** Hasta unos cuantos millones de vectores, dataset mostly-static, presupuesto de memoria estricto, tiempo de construcción crítico. Es razonable, por ejemplo, en sistemas analíticos batch donde la BBDD se reconstruye periódicamente y la búsqueda en tiempo real no es el caso de uso principal. Para RAG con corpus que crece, evítalo: la degradación silenciosa con inserciones es un problema operativo real.

**HNSW.** El caballo de batalla para casi todo RAG en el rango de decenas de miles a decenas de millones de vectores, con escrituras activas, recall alto requerido y memoria disponible razonable. Es la elección del proyecto del programa y la elección de la inmensa mayoría de sistemas RAG en producción en 2026.

**DiskANN (vía pgvectorscale o equivalente).** A partir de varios millones de vectores donde HNSW empieza a apretar la memoria, o decenas de millones donde HNSW ya no es viable. Aporta el techo más alto sin migrar a un sistema dedicado.

Hay un detalle importante que conviene tener en mente y que vemos en directo: los tres algoritmos ANN comparten en pgvector las mismas tres **operator classes** — `vector_cosine_ops` para coseno (`<=>`), `vector_l2_ops` para L2 (`<->`), y `vector_ip_ops` para inner product (`<#>`). Al crear el índice eliges una de las tres, y a partir de ese momento solo las queries que usan el operador correspondiente aprovecharán el índice. Si construyes el índice con `vector_cosine_ops` y luego ejecutas una query con `<->`, Postgres caerá a sequential scan silenciosamente, sin error, sin warning, solo con una degradación de latencia brutal. Es uno de los antipatrones más comunes y lo cubrimos con detalle en el artículo siguiente.

## **Cómo verificar que el índice se está usando**

Aunque la mecánica detallada la veremos en directo, conviene anticipar la herramienta principal: `EXPLAIN ANALYZE`. Postgres muestra el plan de ejecución de una query y, crucialmente, indica si el plan está usando el índice o haciendo sequential scan. Una query bien planeada que use HNSW se verá así:

```sql
EXPLAIN ANALYZE
SELECT id, content, embedding <=> :query AS distance
FROM chunks
ORDER BY embedding <=> :query
LIMIT 5;
```

```
Limit (cost=... rows=5 ...)
  -> Index Scan using chunks_embedding_idx on chunks (cost=...)
       Order By: embedding <=> '[...]'::vector
       ...
Planning Time: 0.234 ms
Execution Time: 4.821 ms
```

La clave es la línea `Index Scan using chunks_embedding_idx`. Si en su lugar aparece `Seq Scan on chunks`, el índice no se está usando, y casi siempre es por una de tres razones: el operador de la query no coincide con la operator class del índice, los filtros relacionales del `WHERE` son demasiado selectivos y Postgres considera más barato escanear que pasar por el índice, o el índice todavía no se ha vacuumed después de su construcción.

## **Bridge al siguiente artículo**

Tienes ya el mapa de los tres algoritmos. Sabes qué hace cada uno por debajo, qué parámetros expone pgvector para tunearlos y bajo qué condiciones cada uno gana. Sabes también que para el proyecto del programa la elección es HNSW con `m = 16`, `ef_construction = 128`, `ef_search = 40`, y que esa elección lleva aparejada una decisión adicional importantísima: con qué operator class construir el índice y, por tanto, qué operador usar en las queries.

Esa decisión, junto con el diseño del esquema relacional que sostiene todo el sistema, es el contenido del siguiente artículo: **Diseño de esquema y búsqueda semántica en pgvector**. Ahí aterrizamos el modelo concreto de las tablas `documents` y `chunks` para el proyecto, las tres métricas de distancia con el caso particular de los embeddings de OpenAI (que están normalizados, lo que tiene consecuencias prácticas), y la trampa silenciosa del desalineamiento operador-índice que acabamos de mencionar. Léelo justo antes del ejercicio pre-sesión: contiene el schema SQL ejecutable que vas a usar como referencia.