# Búsqueda híbrida

Creada: 20 de junio de 2026 9:33
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S10. Técnicas de recuperación (https://app.notion.com/p/S10-T-cnicas-de-recuperaci-n-385ea9ca03c4806b8530fd77248bbb31?pvs=21)

Una escena del sistema de estimación de proyectos. Llega la descripción de un proyecto nuevo: una app de reservas que necesita "integración de pagos con Stripe, incluyendo suscripciones y webhooks de facturación". El pipeline de recuperación busca entre los presupuestos históricos por similitud semántica y devuelve resultados razonables: presupuestos de proyectos con pasarelas de pago, cobros recurrentes, integraciones financieras. Todos del campo semántico correcto.

Pero en el histórico hay un presupuesto que integró *exactamente* Stripe, con sus suscripciones y sus webhooks, hace año y medio. Para estimar, ese documento vale oro: contiene el esfuerzo real que costó pelearse con esa API concreta, sus sorpresas y sus partidas. Y aparece en la posición catorce, por detrás de media docena de proyectos con otras pasarelas.

¿Por qué? Porque para un modelo de embeddings, "Stripe" es aproximadamente sinónimo de "pasarela de pago". Esa generalización es precisamente la virtud de los embeddings — entienden que "cobros recurrentes" y "suscripciones" hablan de lo mismo — y aquí es exactamente el problema: el nombre propio, el término exacto que distingue al documento perfecto de los simplemente parecidos, se diluye en un vector que promedia todo el contenido del chunk. La búsqueda semántica es miope para lo literal.

La ironía es que el problema que los embeddings no resuelven lo tenía resuelto la generación anterior de tecnología de búsqueda: el matching exacto de términos. La **búsqueda híbrida** consiste en no elegir — ejecutar ambas búsquedas, la semántica y la léxica, y fusionar sus resultados en un único ranking. Este artículo construye esa idea de abajo arriba: qué ve cada familia de búsqueda que la otra no ve, cómo montar la búsqueda léxica sin salir de PostgreSQL, y cómo fusionar dos rankings que no hablan el mismo idioma de puntuaciones.

## **Dos familias de búsqueda, dos puntos ciegos**

La búsqueda léxica — la de los buscadores clásicos — opera sobre los términos literales del texto. Su pregunta es: ¿qué documentos contienen las palabras de la consulta, y con qué peso? Las palabras raras en el corpus discriminan mucho (si "Stripe" aparece en tres documentos de mil, esos tres importan); las palabras omnipresentes discriminan poco. Sobre esa intuición se construyeron décadas de recuperación de información.

La búsqueda semántica opera sobre representaciones del significado: la consulta y los documentos se proyectan a un espacio vectorial donde la cercanía aproxima la afinidad temática, digan lo que digan las palabras exactas.

Cada una es ciega justo donde la otra ve:

**La léxica no entiende paráfrasis.** "Cobros recurrentes" y "suscripciones de pago" no comparten ni una palabra; para la búsqueda léxica son consultas sin relación. Un histórico de presupuestos escrito por personas distintas a lo largo de años está lleno de estas variaciones: lo que un autor llamó "panel de administración" otro lo llamó "backoffice". La semántica cruza esas variaciones sin esfuerzo.

**La semántica diluye lo literal.** Nombres propios, siglas, versiones, códigos internos: "Stripe", "SAP", "ISO 27001", "PostGIS". Son los términos con menos masa semántica general y más valor discriminante en un corpus técnico, la combinación exacta que peor sobrevive a la compresión en un embedding. Cuando la consulta pide un identificador concreto, la búsqueda léxica lo clava y la semántica lo aproxima.

En un sistema de estimación conviven los dos tipos de consulta — descripciones conceptuales de proyectos y menciones de tecnologías concretas —, y muy a menudo *dentro de la misma consulta*. La conclusión no es elegir mejor entre familias: es dejar de elegir.

## **Búsqueda full-text en PostgreSQL: la pieza que ya tienes**

La reacción instintiva al oír "búsqueda por palabras clave en producción" es pensar en Elasticsearch. Resiste el instinto un momento: si los vectores del sistema ya viven en PostgreSQL, el propio PostgreSQL trae un motor de full-text search maduro, y usarlo significa cero infraestructura nueva, cero sincronización entre almacenes y las dos búsquedas a una consulta SQL de distancia.

Las piezas del full-text en PostgreSQL:

`tsvector`**: el documento preprocesado.** Un `tsvector` es la representación de un texto optimizada para búsqueda: el texto tokenizado, normalizado a minúsculas, sin palabras vacías (stopwords) y con cada palabra reducida a su raíz (stemming) — "integraciones", "integración" e "integrar" colapsan en la misma raíz y se encuentran entre sí. Esa normalización depende del idioma, y por eso la configuración lingüística no es un detalle: un corpus de presupuestos en español debe procesarse con la configuración `'spanish'` para que el stemming y las stopwords sean los correctos. Los términos que el diccionario no reconoce — "Stripe", "webhook" — pasan casi intactos, que es justo lo que queremos: son los identificadores que vinimos a buscar.

`tsquery`**: la consulta preprocesada.** La consulta del usuario pasa por la misma normalización para que ambos lados hablen el mismo idioma de raíces. La función `websearch_to_tsquery` acepta sintaxis natural de buscador (términos sueltos, comillas para frases, OR) y tolera entradas imperfectas, lo que la hace la opción sensata cuando la consulta viene de un usuario o de un texto libre.

**El índice GIN y** `ts_rank`**.** El operador `@@` comprueba si un `tsvector` satisface una `tsquery`; el índice GIN (Generalized Inverted Index — un índice invertido, la estructura clásica de los buscadores: de cada término a los documentos que lo contienen) lo hace rápido sobre millones de filas; y `ts_rank` puntúa cada coincidencia según la frecuencia y proximidad de los términos para poder ordenar.

En la práctica, la pieza se monta con una columna generada — PostgreSQL mantiene el `tsvector` sincronizado con el contenido automáticamente, sin triggers ni código de aplicación — y su índice:

```sql
ALTER TABLE budget_chunks
ADD COLUMN content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('spanish', content)) STORED;

CREATE INDEX ix_budget_chunks_content_tsv
ON budget_chunks USING gin (content_tsv);
```

Y la búsqueda léxica queda en una consulta:

```sql
SELECT chunk_id, ts_rank(content_tsv, query) AS lexical_rank
FROM budget_chunks,
     websearch_to_tsquery('spanish', :query_text) AS query
WHERE content_tsv @@ query
ORDER BY lexical_rank DESC
LIMIT 50;
```

![articulo-03-figura-01-arquitectura-hibrida.jpg](https://media1-production-mightynetworks.imgix.net/asset/9c3d8993-f1ee-4837-9357-4f06707466d9/articulo-03-figura-01-arquitectura-hibrida.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Dos honestidades antes de seguir. La primera: `ts_rank` no es BM25, el algoritmo de ranking léxico que es estándar de facto en buscadores dedicados, y es algo más tosco puntuando — no normaliza por longitud de documento con la misma sofisticación. Existen extensiones de PostgreSQL que incorporan BM25, pero para un corpus de empresa de miles o decenas de miles de chunks, la diferencia entre `ts_rank` y BM25 es ruido comparada con la ganancia de tener rama léxica frente a no tenerla. La segunda: Elasticsearch (u OpenSearch) sigue teniendo su sitio — corpus enormes, necesidades léxicas avanzadas como analizadores personalizados o búsqueda difusa tolerante a erratas, equipos que ya lo operan. La posición de este artículo no es "Elasticsearch nunca"; es "no añadas un segundo almacén de datos hasta que el primero se te quede pequeño, porque cada almacén extra es sincronización, monitorización y modos de fallo nuevos".

## **El problema de juntar dos rankings**

Ya tenemos dos búsquedas que devuelven, cada una, su top-50: la semántica con sus distancias de coseno, la léxica con sus puntuaciones de `ts_rank`. Y aquí aparece un problema más sutil de lo que parece: **las dos puntuaciones no son comparables**. La similitud coseno vive en un rango acotado con su propia distribución; `ts_rank` produce valores en otra escala completamente distinta, sin cota superior intuitiva. Sumarlas directamente es sumar metros con kilogramos.

La tentación de ingeniero es normalizar: reescalar ambas puntuaciones a un rango común y combinarlas con pesos. Funciona en la demo y se rompe en producción, porque la distribución de las puntuaciones cambia con cada consulta — una consulta con términos muy raros produce puntuaciones léxicas altísimas; una conceptual, bajísimas — y la normalización calibrada con las consultas de ayer queda descalibrada con las de hoy. Mantener esa calibración es un trabajo permanente que nadie pidió.

La solución elegante esquiva el problema por completo: **ignorar las puntuaciones y usar solo las posiciones**.

## **Reciprocal Rank Fusion: fusionar por consenso**

Reciprocal Rank Fusion (RRF) fusiona rankings con una regla de una línea: cada documento recibe, de cada ranking en el que aparece, una puntuación inversamente proporcional a su posición, y las puntuaciones se suman.

`rrf_score(d) = Σ 1 / (k + rank_i(d))`

donde `rank_i(d)` es la posición del documento en el ranking *i* (empezando en 1) y `k` es una constante de suavizado, típicamente 60. La puntuación final de un documento solo depende de en qué posiciones quedó — nunca de las puntuaciones brutas de cada motor, que es exactamente lo que las hace incomparables.

Verlo con números aclara por qué funciona. Con `k = 60`:

- Un presupuesto que queda **2º en la búsqueda semántica y 5º en la léxica**: 1/62 + 1/65 ≈ 0,0315.
- Un presupuesto que queda **1º en la semántica pero no aparece en la léxica**: 1/61 ≈ 0,0164.

El documento que ambas búsquedas consideran bueno supera al campeón de una sola. RRF es, en esencia, una máquina de premiar el consenso: aparecer razonablemente arriba en varios rankings vale más que arrasar en uno. Para el presupuesto de Stripe, esto es el rescate exacto que necesitábamos — la rama léxica lo coloca arriba por el término exacto, la semántica lo mantiene digno por el tema, y la fusión lo sube a las primeras posiciones del ranking combinado.

![articulo-03-figura-02-calculo-rrf.jpg](https://media1-production-mightynetworks.imgix.net/asset/2e465ece-7aca-4023-881a-38738df80f73/articulo-03-figura-02-calculo-rrf.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La constante `k` merece treinta segundos de atención porque es el único mando de la técnica. Con `k` pequeña, las primeras posiciones dominan la fusión (la diferencia entre 1/1 y 1/2 es enorme); con `k` grande, las diferencias de posición se aplanan y la fusión se vuelve más democrática con todo el top. El valor 60 viene del paper original que propuso la técnica y ha demostrado ser robusto en dominios muy distintos; cambiarlo rara vez es la palanca que mueve la calidad, y empezar tocándolo es optimización prematura.

La implementación cabe en una función pura:

```python
# app/generation/rag/retrieval/fusion.py

from collections import defaultdict

RRF_SMOOTHING_K = 60

def reciprocal_rank_fusion(
    rankings: list[list[str]],
    k: int = RRF_SMOOTHING_K,
) -> list[str]:
    """Fuse multiple ranked lists of chunk ids into a single ranking."""
    scores: dict[str, float] = defaultdict(float)

    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] += 1.0 / (k + rank)

    return [
        chunk_id
        for chunk_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ]
```

Nótese que recibe *una lista de rankings*, no exactamente dos. Es deliberado: RRF no sabe ni le importa cuántas fuentes fusiona, y esa generalidad la convierte en la pieza de fusión universal del pipeline — hoy fusiona la rama semántica con la léxica; el día que el sistema genere resultados desde varias búsquedas paralelas, la misma función los fusionará sin cambiar una línea.

## **La búsqueda híbrida en el servicio IA**

Orquestar la híbrida es componer lo anterior. Las dos ramas son consultas independientes a la misma base de datos, así que la implementación natural en un servicio asíncrono es lanzarlas en paralelo: la latencia de la híbrida es la de la rama más lenta, no la suma de ambas.

```python
# app/generation/rag/retrieval/hybrid_search.py (fragment)

import asyncio

async def hybrid_search(self, query: str, limit: int = 50) -> list[RetrievedChunk]:
    """Run semantic and lexical search in parallel and fuse with RRF."""
    semantic_results, lexical_results = await asyncio.gather(
        self._vector_search.search(query, limit=limit),
        self._fulltext_search.search(query, limit=limit),
    )

    fused_ids = reciprocal_rank_fusion(
        [
            [chunk.id for chunk in semantic_results],
            [chunk.id for chunk in lexical_results],
        ]
    )

    chunks_by_id = {
        chunk.id: chunk
        for chunk in [*semantic_results, *lexical_results]
    }
    return [chunks_by_id[chunk_id] for chunk_id in fused_ids[:limit]]
```

El contrato es el mismo que el de cualquier otra búsqueda del sistema: entra una consulta, sale una lista ordenada de chunks. Esa uniformidad es una decisión de arquitectura, no una casualidad — cuando cada estrategia de recuperación respeta el mismo contrato, cambiar de búsqueda vectorial a híbrida es cambiar una pieza por otra detrás de una configuración, y comparar ambas se convierte en un experimento de un booleano en lugar de una rama de tres semanas. La híbrida produce un ranking que, como cualquier otro, puede alimentar directamente al generador o pasar antes por una etapa de reordenación fina; es una pieza componible más del pipeline, no un pipeline distinto.

El coste operativo de la híbrida es modesto y conviene nombrarlo con precisión: una consulta SQL adicional por búsqueda (en paralelo, así que el impacto en latencia es pequeño), una columna generada que engorda la tabla y se recalcula en cada escritura de contenido, y un índice GIN que ocupa espacio y se mantiene en cada inserción. En un corpus de presupuestos de empresa, todo ello es calderilla. El coste real está donde siempre: una pieza más que entender, configurar y depurar.

## **Cuándo la híbrida gana — y cuándo no aporta**

La búsqueda híbrida no es mejor que la semántica en abstracto; es mejor en un perfil de consultas concreto, y honesto es delimitarlo.

**Donde gana con claridad:** consultas con identificadores exactos — tecnologías, productos, siglas, normas, nombres de cliente. En un sistema de estimación, esto no es el caso raro sino el pan de cada día: las descripciones de proyectos están sembradas de "Stripe", "Salesforce", "GDPR", "React Native". También gana en consultas cortas y específicas, donde hay poca señal semántica que explotar y cada término literal cuenta.

**Donde apenas mueve la aguja:** consultas puramente conceptuales y bien parafraseadas — "proyecto de digitalización de procesos internos con flujos de aprobación" — donde la semántica ya hacía un buen trabajo y la rama léxica devuelve más o menos lo mismo con otro orden. En estos casos la fusión no estorba (RRF degrada con elegancia: si ambos rankings coinciden, el fusionado también), pero tampoco luce.

**Donde hay que vigilarla:** si el corpus y las consultas están en idiomas mezclados — presupuestos en español plagados de terminología en inglés, como es norma en el sector —, la configuración lingüística del `tsvector` procesará bien una parte y dejará la otra sin stemming. No suele ser grave (los términos técnicos en inglés funcionan como identificadores exactos, que es el caso donde la léxica brilla), pero es el tipo de detalle que explica resultados desconcertantes y que conviene conocer antes de depurarlos a ciegas.

La pregunta de si la híbrida compensa *en tu sistema, con tus consultas* tiene la misma respuesta que cualquier pregunta de este tipo: se mide contra una referencia fija, configuración contra configuración, y deciden los números. Lo que este artículo aporta es la convicción de que, en dominios técnicos con vocabulario propio, la apuesta a priori es claramente favorable — y el coste de comprobarlo, una tarde.

## **Dejar de elegir**

La idea para llevarse: la búsqueda semántica y la léxica no compiten, se cubren los puntos ciegos mutuamente. La semántica entiende paráfrasis y se le escapan los identificadores; la léxica clava los identificadores y no entiende paráfrasis. PostgreSQL ofrece las dos sobre la misma tabla — pgvector para una, `tsvector` con GIN para la otra — y Reciprocal Rank Fusion las une sin el pantano de calibrar puntuaciones incomparables: solo posiciones, premiando al documento que ambas búsquedas respetan.

En la sesión en vivo, la búsqueda híbrida será una de las piezas sobre las que trabajaremos en el sistema de estimación: la veremos rescatar en directo presupuestos que la búsqueda puramente semántica dejaba enterrados, y comprobaremos con consultas reales del dominio en qué casos marca la diferencia y en cuáles no.