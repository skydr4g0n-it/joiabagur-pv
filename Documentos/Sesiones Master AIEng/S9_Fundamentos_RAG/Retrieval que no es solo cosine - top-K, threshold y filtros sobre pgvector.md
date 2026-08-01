# Retrieval que no es solo cosine: top-K, threshold y filtros sobre pgvector

Creada: 15 de junio de 2026 12:58
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S9. Fundamentos de RAG y técnicas de recuperación (https://app.notion.com/p/S9-Fundamentos-de-RAG-y-t-cnicas-de-recuperaci-n-380ea9ca03c480268ac0c4739784b444?pvs=21)

Al cierre de la Sesión 08 dejaste construido un endpoint de búsqueda que recibe un vector de consulta y devuelve los `K` chunks más similares según el operador `<=>` (cosine distance) de pgvector sobre tu índice HNSW. Es exactamente lo que un sistema RAG didáctico de manual hace y, durante las primeras pruebas con queries inventadas en el seed, funciona razonablemente. La fricción aparece la primera vez que le pasas la salida de tu nuevo `query_reformulator.py` sobre una transcripción real, y mirando los resultados te llevas una de estas dos sorpresas.

La primera sorpresa es la de los **resultados clónicos**. Le has pedido al retriever los diez chunks más similares para una transcripción de marketplace fintech B2B; al inspeccionar la respuesta, descubres que ocho de los diez chunks pertenecen al mismo presupuesto histórico. El sistema ha encontrado un único proyecto realmente similar en la base, y como `top-K=10` exige diez resultados, el resto de las posiciones se rellenan con chunks de ese mismo proyecto. La estimación que vas a generar después está fundamentada en un solo caso histórico, no en diez, y eso no es lo que el sistema promete.

La segunda sorpresa es la opuesta y aparece cuando el corpus no tiene presupuestos genuinamente similares. Has pedido diez resultados y el retriever ha devuelto diez, pero al mirar las distancias coseno te das cuenta de que todas están comprimidas alrededor de 0.7-0.8 en pgvector: ninguno es realmente similar, todos son mediocres. El retriever ha cumplido la promesa literal — "los diez más similares" — pero los chunks recuperados no van a fundamentar nada porque no se parecen a la query lo suficiente. La estimación que se genere a partir de ese contexto va a ser una alucinación apoyada en presupuestos genéricamente parecidos pero no realmente comparables.

Ambas sorpresas tienen una causa común: el retriever está usando una única palanca, `top-K`, y le falta disciplina sobre dos dimensiones críticas. La primera, **calidad mínima**: ningún chunk por debajo de un umbral de similitud debería entrar en el contexto, aunque eso signifique devolver menos de `K` resultados. La segunda, **filtrado estructural**: no todos los chunks históricos son candidatos para toda query; un proyecto del sector retail en 2018 no debería competir con uno de fintech en 2024 cuando la transcripción habla explícitamente del sector salud. Este artículo añade esas dos palancas y muestra cómo se encajan dentro del retriever de tu servicio IA usando los operadores que pgvector ya te ofrece.

## **Top-K: la palanca obvia y sus dos sesgos**

`top-K` es la palanca que viene de fábrica con cualquier base vectorial y la única que el sistema de la Sesión 08 expone. Define cuántos chunks queremos que el retriever devuelva ordenados por distancia ascendente. Aparentemente no hay mucho que discutir: pides cinco, te dan cinco; pides veinte, te dan veinte. La discusión real es **cuántos pedir** y por qué.

El reflejo de muchos alumnos al ver los primeros resultados pobres es subir `K`. La intuición es razonable: si entre los diez no hay nada bueno, quizá entre los veinte sí. Y a veces funciona: en corpus grandes con queries ambiguas, ampliar `K` te aporta diversidad y a veces rescata chunks relevantes que estaban "más abajo en la cola". Pero en producción, subir `K` por reflejo lleva a tres consecuencias que tienen coste medible.

Primero, **el coste del prompt de generación se multiplica casi linealmente con K**. Cada chunk que entra al contexto son entre 200 y 400 tokens; pasar de `K=10` a `K=30` añade entre cuatro y ocho mil tokens al prompt de generación. Si tu llamada a `gpt-5` para generar la estimación cuesta cincuenta céntimos por petición con `K=10`, con `K=30` cuesta un euro y medio. Multiplica eso por miles de peticiones al mes.

Segundo, **el ruido en el contexto degrada la calidad de la respuesta**, no la mejora. Los modelos modernos sufren el fenómeno "lost in the middle" — que el Artículo 4 examina a fondo — y cuando metes treinta chunks parcialmente relevantes en el prompt, el modelo tiende a ignorar la mayoría y a apoyarse desproporcionadamente en los primeros y los últimos. El chunk crítico que estaba en la posición catorce probablemente va a recibir menos atención que el chunk irrelevante de la posición uno.

Tercero, **subir K oculta el problema real**. Si tu retriever solo encuentra tres chunks realmente similares y le pides diez, no estás haciendo retrieval mejor; estás haciendo retrieval del mismo tres chunks con siete distracciones. El sistema te está diciendo "tu corpus no tiene más material relevante para esta query" y la respuesta correcta no es disfrazar esa señal con resultados de baja calidad, sino propagarla hacia adelante para que la etapa de generación lo sepa.

La regla operativa del programa es mantener `K` en un valor moderado y estable — diez es razonable para el caso del proyecto — y dejar que el threshold se ocupe de descartar resultados que no merecen entrar en el contexto. El número correcto de chunks por petición no es un parámetro fijo del retriever, es un emergente del threshold aplicado sobre los K candidatos: a veces serán diez, a veces serán tres, a veces serán cero. Y eso último — cero — es información válida, no un fallo del sistema.

## **Threshold: la disciplina que falta**

Threshold es el filtro que decide qué distancia es lo suficientemente baja para que un chunk merezca entrar en el contexto. En pgvector, donde el operador `<=>` produce cosine distance entre 0 (vectores idénticos) y 2 (vectores opuestos), un threshold típico para corpus de embeddings de OpenAI estaría entre `0.5` y `0.7`: por debajo de eso, el chunk es razonablemente similar a la query; por encima, es contenido tangencial que probablemente confundirá al modelo más que ayudarle.

El número exacto del threshold no se decide por intuición. Se decide mirando la **distribución empírica de distancias** sobre queries reales contra tu corpus. El procedimiento es directo: coges veinte o treinta transcripciones representativas, las pasas por tu reformulador, ejecutas la búsqueda con `K=50` y sin threshold, y graficas las distancias resultantes. Vas a ver dos patrones reconocibles. Un grupo de chunks con distancias bajas (entre 0.3 y 0.5 típicamente para tu corpus) que al inspección manual son genuinamente relevantes para la query. Y un grupo más grande con distancias en torno a 0.7-0.9 que al inspección manual son ruido. El threshold se coloca en el valle entre los dos grupos; para `text-embedding-3-small` sobre un corpus razonablemente especializado, ese valle suele caer alrededor de 0.6-0.65. La sesión en vivo va a hacer exactamente ese ejercicio sobre tu propio corpus.

![art_3_figura-7-distribucion-distancias.jpg](https://media1-production-mightynetworks.imgix.net/asset/4fb7791b-ef9b-4e72-8ee1-95739f32bad4/art_3_figura-7-distribucion-distancias.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Una vez fijado el threshold, el endpoint de búsqueda lo aplica como un `WHERE` adicional a la SQL que ya tenías:

```sql
SELECT
    c.id,
    c.content,
    c.metadata,
    c.embedding <=> :query_embedding AS distance
FROM chunks c
WHERE c.embedding <=> :query_embedding < :distance_threshold
ORDER BY c.embedding <=> :query_embedding
LIMIT :top_k;
```

Hay un detalle operativo importante en esta query. La cláusula `WHERE` evalúa la distancia, y eso significa que pgvector la calcula dos veces por cada candidato si no se tiene cuidado — una para el `WHERE` y otra para el `ORDER BY`. En la práctica, el planner de Postgres es inteligente y reusa el cálculo cuando el índice HNSW está bien configurado con la operator class adecuada (`vector_cosine_ops`, alineada con el operador `<=>` de la query — el antipatrón que cubrimos en la Sesión 08). Si por descuido el operator class del índice fuera `vector_l2_ops` y la query usara `<=>`, el índice no se aplicaría, el planner caería a sequential scan, y los `EXPLAIN ANALYZE` te dirían que la búsqueda tarda segundos en lugar de milisegundos. Mantener el operator class del índice alineado con el operador de la query es la condición previa para que cualquier ajuste de threshold tenga el comportamiento esperado.

El comportamiento del retriever cuando ningún chunk supera el threshold merece una decisión explícita. La opción que el programa adopta es **soft-fail**: el endpoint devuelve una lista vacía y un campo `low_confidence: true` en el body de la respuesta. El orquestador, al ver la lista vacía, no llama al generador con un contexto vacío — eso solo invita al modelo a alucinar — sino que produce una respuesta directa al backend de negocio del tipo "no hay evidencia suficiente en el corpus histórico para estimar este proyecto; el equipo comercial debería revisarlo manualmente". Esta semántica es la que distingue un sistema RAG serio de uno didáctico: el sistema reconoce sus límites y los comunica hacia arriba, en lugar de generar siempre algo que parezca una estimación.

Una alternativa que algunos sistemas adoptan es **relajar el threshold dinámicamente** cuando la búsqueda inicial devuelve menos de un mínimo de resultados. El retriever empieza con threshold estricto (`0.55`), y si devuelve menos de tres chunks, lo relaja a `0.65` y repite. Es una optimización válida pero introduce no-determinismo y dificulta el debug; el programa no la adopta por defecto pero la deja como mejora opcional en la sesión en vivo.

## **Filtros de metadata: tres estrategias en pgvector**

La similitud vectorial captura semejanza semántica pero ignora datos estructurales que pueden ser críticos. Cuando la transcripción habla explícitamente del sector salud, no quieres que el retriever te devuelva chunks de presupuestos de retail aunque sean semánticamente cercanos en algunos aspectos. Cuando el cliente pide un proyecto para empezar el año que viene, no quieres anclar la estimación en presupuestos de 2019 con tecnologías ya obsoletas. Los filtros estructurales sobre metadata resuelven exactamente esto: añaden cláusulas `WHERE` sobre campos de tus tablas que restringen el universo de candidatos antes, durante o después de la búsqueda vectorial.

Hay tres patrones operativos de aplicar estos filtros y conviene conocer los tres porque la elección entre ellos tiene impacto sobre el rendimiento de la query y sobre el recall efectivo.

**Pre-filtering** aplica las cláusulas estructurales **antes** de la búsqueda vectorial: pgvector primero restringe el universo de candidatos según el `WHERE`, y solo después aplica el operador de distancia sobre el subconjunto resultante. La SQL queda así:

```sql
SELECT
    c.id,
    c.content,
    c.metadata,
    c.embedding <=> :query_embedding AS distance
FROM chunks c
JOIN documents d ON c.document_id = d.id
WHERE d.sector = ANY(:sectors)
  AND d.project_year >= :year_min
  AND c.embedding <=> :query_embedding < :distance_threshold
ORDER BY c.embedding <=> :query_embedding
LIMIT :top_k;
```

Pre-filtering es la opción correcta cuando el filtro tiene **alta selectividad**, es decir, cuando reduce el corpus a un subconjunto pequeño antes de buscar. Si tu cláusula `sector = 'healthcare' AND project_year >= 2022` deja solo el 5% de tus chunks, pgvector ejecuta la búsqueda vectorial sobre 50 chunks en lugar de 1000 y los milisegundos se sienten.

Durante años, la advertencia operativa fue que pre-filtering destruía el índice HNSW: el plan de ejecución caía a sequential scan porque el índice no sabía combinar la similitud vectorial con el filtro estructural. En las versiones modernas de pgvector (desde 0.7), la situación ha cambiado significativamente gracias a los **iterative scans** sobre HNSW filtrado, que permiten al índice navegar el grafo descartando candidatos que no cumplen el `WHERE`. El comportamiento ya no es óptimo en todos los casos pero deja de ser catastrófico, y para selectividades por debajo del 20% el rendimiento es razonable. El programa adopta pre-filtering como estrategia por defecto basándose en este comportamiento.

**Post-filtering** invierte el orden: primero buscas vectorialmente con `K` ampliado, y después aplicas el `WHERE` para descartar los que no cumplen los criterios estructurales:

```sql
WITH top_candidates AS (
    SELECT
        c.id,
        c.content,
        c.metadata,
        c.document_id,
        c.embedding <=> :query_embedding AS distance
    FROM chunks c
    WHERE c.embedding <=> :query_embedding < :distance_threshold
    ORDER BY c.embedding <=> :query_embedding
    LIMIT :wide_k
)
SELECT t.*
FROM top_candidates t
JOIN documents d ON t.document_id = d.id
WHERE d.sector = ANY(:sectors)
ORDER BY t.distance
LIMIT :top_k;
```

Post-filtering es la opción correcta cuando el filtro tiene **baja selectividad** y el índice HNSW funciona mejor sin restricciones. Si tu cláusula sólo elimina el 10% del corpus, pre-filtering apenas reduce el trabajo del índice y sí que limita el grafo de navegación; en ese caso es preferible buscar primero con `wide_k = top_k × 3` o algo similar, y luego descartar los pocos que no cumplen. El riesgo de post-filtering es perder recall cuando el filtro es muy selectivo: si tu `wide_k` es 50 pero solo 2 de esos cumplen el filtro, has fallado y deberías haber subido `wide_k` aún más; sin instrumentación, no te enteras.

**In-query filtering** es la fusión moderna que pgvector facilita gracias a los iterative scans: la query se escribe como pre-filtering pero el optimizador decide internamente la mejor estrategia. La cláusula `WHERE` mezcla filtros estructurales y de distancia, y pgvector evalúa el índice HNSW filtrado o el sequential scan en función de la selectividad estimada. Para el caso del proyecto, esta es de hecho la query que ejecutas en producción; el "pre" vs "post" se convierte en una decisión interna del planner, no algo que tengas que escribir tú.

Sobre el esquema concreto del proyecto, los filtros más útiles que merece la pena exponer en la API de retrieval son cuatro: `sectors` (lista de sectores aceptables), `project_year_range` (rango de años para limitar a presupuestos recientes), `tech_stack` (tecnologías mencionadas, usando operador JSONB `@>` sobre el campo de metadata), y `chunk_types` (limitar a ciertos tipos de chunk del esquema de Sesión 07: `scope_block`, `line_item`, `phase`). La SQL con los cuatro integrados queda:

```sql
SELECT
    c.id,
    c.content,
    c.chunk_type,
    c.metadata,
    c.embedding <=> :query_embedding AS distance
FROM chunks c
JOIN documents d ON c.document_id = d.id
WHERE (:sectors IS NULL OR d.sector = ANY(:sectors))
  AND (:year_min IS NULL OR d.project_year >= :year_min)
  AND (:year_max IS NULL OR d.project_year <= :year_max)
  AND (:tech_filter IS NULL OR c.metadata @> :tech_filter::jsonb)
  AND (:chunk_types IS NULL OR c.chunk_type = ANY(:chunk_types))
  AND c.embedding <=> :query_embedding < :distance_threshold
ORDER BY c.embedding <=> :query_embedding
LIMIT :top_k;
```

El patrón `(:filter IS NULL OR ...)` permite que los filtros sean opcionales: si el reformulador no extrajo sector de la transcripción, el campo viene a `null` y el filtro se ignora; si lo extrajo, se aplica. Esto encadena directamente con la salida estructurada del Artículo 2: cada campo del esquema Pydantic se mapea a un filtro opcional del retriever, y la coherencia entre las dos capas se mantiene por construcción.

![art_3_figura-8-pre-vs-post-filtering.jpg](https://media1-production-mightynetworks.imgix.net/asset/d71a6254-6549-4aef-9f8b-b09bab250f5d/art_3_figura-8-pre-vs-post-filtering.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Anti-patrones que el sistema invita a cometer**

Hay cuatro anti-patrones recurrentes en sistemas RAG que merece la pena nombrar para reconocerlos cuando aparezcan, porque van a aparecer.

El primero es **subir K para arreglar la calidad**. Lo hemos discutido arriba pero merece repetirlo: si tus resultados son malos, la solución no es traer más; es traer mejor. Si tres chunks son relevantes y los otros siete son ruido, sumar ruido al contexto no mejora la respuesta. Subir `K` solo tiene sentido cuando una inspección manual confirma que hay chunks relevantes más allá del top-10 que el sistema está dejando fuera.

El segundo es **confiar en el LLM como filtro final**. La narrativa es seductora: "metemos veinte chunks en el contexto y dejamos que el modelo elija los relevantes". En la práctica el modelo no es un buen retriever: no compara sistemáticamente chunks entre sí, no rechaza información irrelevante con disciplina, y bajo presión narrativa acaba sintetizando información de chunks que debería haber ignorado. El filtrado se hace en el retriever; el LLM sintetiza, no filtra.

El tercero es **omitir el threshold porque "casi siempre hay algo en el corpus"**. La asunción es a veces correcta — corpus densos con cobertura amplia rara vez producen búsquedas vacías — pero como decisión arquitectónica es frágil. El día que la asunción falle, el sistema generará una estimación basada en chunks irrelevantes y nadie lo notará hasta que un cliente cuestione el resultado. Tener threshold como parte del contrato del retriever desde el día uno hace que la primera vez que un proyecto sea genuinamente nuevo, el sistema lo reconozca explícitamente.

El cuarto es **mezclar** `chunk_types` **sin filtrar**. Tu esquema de chunks de Sesión 07 distingue entre tipos (un `scope_block` describe un bloque funcional, un `line_item` describe una tarea presupuestada). Una búsqueda que mezcla los dos puede recuperar chunks de tipos distintos con scores similares pero con utilidades distintas para la generación. Si la query del reformulador es claramente sobre "estimación de coste", probablemente quieres `line_item`; si es sobre "alcance funcional", probablemente `scope_block`. Filtrar por tipo cuando el reformulador da pistas claras es gratis y mejora la precisión.

## **Recall vs precision: el trade-off real**

Detrás de todas las decisiones anteriores hay un debate de fondo que conviene nombrar: el sistema tiene que elegir entre **recall** (recuperar todo lo potencialmente relevante, aunque incluya algo de ruido) y **precision** (recuperar solo lo claramente relevante, aunque deje fuera alguna joya). Las dos no se pueden maximizar simultáneamente; subir una baja la otra.

En sistemas RAG didácticos la convención es priorizar recall: traer más para que el LLM tenga material con el que trabajar. En sistemas RAG en producción, especialmente cuando el LLM va a sintetizar una respuesta que tiene consecuencias económicas — y una estimación de software lo es —, la posición operativa correcta es priorizar **precision**: traer menos pero mejor, aceptar que a veces el sistema responde "no tengo evidencia suficiente", y dejar para etapas posteriores (reranking en la Sesión 10, búsqueda híbrida en la misma sesión) los mecanismos que permiten subir el recall sin sacrificar precision.

La razón es la siguiente: una alucinación apoyada en chunks parcialmente relevantes es más peligrosa que un "no lo sé" honesto. Un sistema que produce una estimación de 250.000 euros para un proyecto donde no tiene evidencia sólida está creando una expectativa que ni la empresa ni el cliente pueden honrar. Un sistema que dice "no tengo presupuestos suficientemente similares; revisa esto manualmente" preserva la confianza en las estimaciones que sí produce. La asimetría entre los dos errores es lo que justifica favorecer precision sobre recall en este dominio.

![art_3_figura-9-impacto-k-threshold.jpg](https://media1-production-mightynetworks.imgix.net/asset/3f9a8125-88df-4017-98e4-3351d355b43e/art_3_figura-9-impacto-k-threshold.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Conexión con la sesión en vivo**

El cuarto bloque de la sesión es una iteración sobre los parámetros del retriever. Vamos a coger la misma transcripción ambigua de los artículos anteriores y a explorar tres ejes: cómo varían los chunks recuperados al cambiar `top_k` entre 3 y 30, cómo cambia el conjunto al ajustar el threshold entre 0.5 y 0.8, y cómo afectan los filtros estructurales (sector, año, tipo de chunk) al recall y a la latencia. Cada combinación va a producir un resultado distinto y vamos a medir tres métricas observables: el número de chunks devueltos efectivamente, el porcentaje de chunks que pertenecen al sector correcto, y la latencia mediana de la query sobre el seed que tenéis cargado.

El objetivo de la iteración no es encontrar los parámetros "óptimos" — esa búsqueda es en parte folklore en RAG: lo que es óptimo en tu corpus de hoy puede no serlo en tu corpus de seis meses — sino interiorizar la sensibilidad del sistema a cada palanca. Cuando termines la sesión deberías poder predecir, ante un cambio de threshold de 0.6 a 0.5, qué va a pasar con el coste por petición y qué va a pasar con la tasa de respuestas en modo `low_confidence`.

Hay también un debate productivo que vale la pena anticipar. Algunos alumnos llegarán defendiendo el patrón opuesto al que el programa adopta: priorizar recall, traer treinta chunks, dejar que el LLM filtre. La discusión que tendremos no es teórica; está basada en evidencia empírica del módulo. Vamos a ejecutar las dos estrategias sobre la misma transcripción y a inspeccionar las dos estimaciones generadas: con la de recall alto verás los problemas concretos (lost-in-the-middle, contaminación cruzada entre proyectos), con la de precision alta verás los suyos (cobertura insuficiente cuando el corpus es escaso). Ninguna es universalmente correcta; la del programa es la que mejor encaja en el caso de uso de estimación, pero los argumentos del otro lado son legítimos y conviene articularlos para defender la decisión propia con base.

Lo que cierra este artículo, y conecta con el siguiente, es una idea: por bien que ajustes el retriever, los chunks que devuelva siempre van a llegar al LLM como un bloque de texto que el modelo tiene que entender. La forma en que ensambles ese bloque — qué orden, qué delimitadores, qué metadata acompaña a cada chunk, qué hace el prompt con todo eso — es lo que determina si la calidad del retrieval se traduce en calidad de la estimación o se desperdicia. El Artículo 4 entra a fondo en esa etapa de augmentation.