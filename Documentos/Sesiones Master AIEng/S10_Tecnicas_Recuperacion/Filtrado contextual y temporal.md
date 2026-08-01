# Filtrado contextual y temporal

Creada: 20 de junio de 2026 9:42
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S10. Técnicas de recuperación (https://app.notion.com/p/S10-T-cnicas-de-recuperaci-n-385ea9ca03c4806b8530fd77248bbb31?pvs=21)

Una última escena del sistema de estimación. Llega la descripción de un proyecto: portal de cliente con área privada, gestión documental y firma electrónica. La búsqueda recorre el histórico y encuentra un presupuesto casi calcado — mismo tipo de cliente, mismo alcance funcional, misma estructura de partidas. Similitud semántica altísima, primera posición indiscutible.

El presupuesto es de 2019. El frontend se presupuestó en AngularJS, la firma electrónica con un proveedor que ya no existe, las tarifas son de otra época y el equipo estimó con prácticas que el estudio abandonó hace tres años. Como referencia de *qué partidas tiene* un portal de cliente, todavía orienta; como referencia de *cuánto cuesta hoy*, es directamente peligroso — y el LLM generador, que recibirá ese presupuesto como contexto estrella, no tiene forma de saberlo.

Este es el punto ciego que ninguna de las técnicas de similitud puede cubrir, por sofisticada que sea: **el embedding codifica lo que el texto dice, no cuándo se escribió, ni con qué tecnología, ni para qué sector, ni si sigue siendo verdad**. Esas dimensiones existen, pero viven fuera del texto: en los metadatos. Y los metadatos, bien usados, son la técnica de recuperación con mejor relación coste-beneficio de todo el arsenal — la única cuyo coste de ejecución es *negativo*, porque filtrar antes de buscar abarata todo lo que viene después.

Este artículo cubre los dos usos de los metadatos en recuperación — el filtro duro que excluye y la ponderación blanda que reordena —, el tratamiento del tiempo como caso especial, y el principio de ensamblaje que ordena todas las piezas de un pipeline de recuperación moderno.

## **Filtros duros: reducir el universo antes de buscar**

El filtro duro es el uso más directo: condiciones sobre metadatos que excluyen documentos *antes* de que la similitud opine. Si el proyecto a estimar es React Native, los presupuestos de tecnologías sin relación no deberían ni competir; si la política del estudio es no estimar con referencias de más de cuatro años, la fecha corta en seco. En SQL, es el `WHERE` de toda la vida conviviendo con la búsqueda vectorial:

```sql
SELECT chunk_id, embedding <=> :query_embedding AS distance
FROM budget_chunks
WHERE project_date >= :min_project_date
  AND technology = ANY(:relevant_technologies)
ORDER BY distance
LIMIT 50;
```

La sintaxis es trivial; la trampa está debajo, y conviene conocerla antes de que muerda. Los índices vectoriales aproximados como HNSW no entienden de `WHERE`: el índice navega su grafo buscando los vecinos más cercanos *del universo completo*, y el filtro se aplica después sobre lo que el índice devolvió. Si pides 50 resultados con un filtro que solo satisface el 5% del corpus, el índice puede devolver sus 50 vecinos más cercanos, el filtro descartar 48, y la consulta entregar 2 resultados — o cero — sin ningún error visible. Las versiones recientes de pgvector (0.8 en adelante) mitigan el problema con el escaneo iterativo (`hnsw.iterative_scan`), que sigue pidiendo candidatos al índice hasta reunir los solicitados tras el filtro; para filtros muy frecuentes y selectivos, el índice parcial (un índice HNSW construido solo sobre las filas que cumplen la condición) es la solución estructural. La lección de fondo no es la técnica concreta sino el hábito: **cuando combines filtros con búsqueda aproximada, verifica la cardinalidad de lo que vuelve** — y déjala en los logs, porque "el filtro vació el resultado en silencio" es uno de los modos de fallo más desconcertantes de depurar a posteriori.

Hay una segunda condición de posibilidad que se da por supuesta y no debería: **los metadatos tienen que existir, y existir bien**. La fecha viene gratis; la tecnología, el sector o el tamaño de equipo hay que extraerlos del documento en el momento de la ingesta — con reglas cuando el formato lo permite, con un LLM de extracción estructurada cuando no — y esa extracción se hace una vez por documento, nunca por consulta. La calidad de esa extracción es el techo de todo lo demás: un filtro duro sobre un metadato mal extraído es peor que ningún filtro, porque excluye con total confianza al mejor candidato y nadie ve el hueco que deja. Los filtros duros se reservan para metadatos en los que se confía; lo dudoso, como mucho, pondera.

## **El tiempo: el metadato que nunca es opcional**

De todos los metadatos, la fecha merece tratamiento propio, porque su efecto sobre la utilidad es universal y direccional: en un histórico de presupuestos, lo reciente vale sistemáticamente más que lo antiguo — los precios caducan, los stacks rotan, las prácticas cambian. La pregunta de diseño es cómo materializar esa preferencia, y hay dos familias de respuesta.

**La ventana dura** es el filtro temporal como condición: solo presupuestos de los últimos N años. Simple de implementar, simple de explicar, y con un comportamiento brutal en el borde: el presupuesto de hace 3 años y 11 meses compite en igualdad total, el de hace 4 años y un mes no existe. Cuando el corpus es abundante, la brutalidad da igual; cuando es escaso — y los históricos de empresa lo son más de lo que se admite —, la ventana puede dejar fuera la única referencia decente de un tipo de proyecto raro.

**El decaimiento continuo** trata la edad como una penalización progresiva en lugar de un veredicto. La forma habitual es exponencial, y su único parámetro tiene una lectura de negocio directa — la **semivida**: cada cuántos días un presupuesto pierde la mitad de su peso.

```python
# app/generation/rag/retrieval/temporal.py

from datetime import date

def temporal_weight(document_date: date, half_life_days: int = 900) -> float:
    """Exponential decay: a document loses half its weight every half_life_days."""
    age_days = (date.today() - document_date).days
    return 0.5 ** (max(age_days, 0) / half_life_days)
```

Con una semivida de 900 días (dos años y medio), un presupuesto de hace un año conserva el 76% de su peso; el de 2019, en torno al 15%. Sigue *existiendo* — si es la única referencia de su especie, aparecerá, correctamente degradado — pero ya no puede ganarle la primera posición a un equivalente reciente. La semivida no se optimiza con una fórmula: se elige con juicio de dominio ("¿a partir de cuándo dejarías de fiarte de las cifras de un presupuesto?") y se revisa cuando el dominio cambie.

![articulo-06-figura-01-decaimiento-temporal.jpg](https://media1-production-mightynetworks.imgix.net/asset/dadc768b-03aa-4ea4-8f71-1f76d006e90e/articulo-06-figura-01-decaimiento-temporal.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La elección entre ventana y decaimiento no es ideológica: la ventana cuando exista una razón categórica (cumplimiento, política de empresa, un cambio de era que invalide lo anterior — "todo lo pre-migración no sirve"); el decaimiento para la erosión gradual normal del valor. Y se combinan sin conflicto: una ventana generosa como filtro de seguridad, decaimiento dentro de ella como ordenación fina.

## **Ponderación dinámica: cuando el contexto de la consulta cambia los pesos**

El tercer nivel de sofisticación: que la importancia de cada metadato dependa de la consulta. Si la descripción del proyecto gira alrededor de una tecnología concreta, la coincidencia tecnológica debería pesar mucho; si describe un proyecto para banca, la experiencia sectorial sube de valor porque arrastra regulación y plazos; si no menciona nada de eso, esos mismos metadatos deberían callar. La idea es atractiva y la implementación honesta es prosaica: el ajuste contextual se aplica como multiplicadores sobre la ordenación final — coincidencia de tecnología cuando la consulta la menciona, coincidencia de sector cuando aplica, el peso temporal siempre — con los factores definidos en configuración, no enterrados en el código.

Y aquí toca la advertencia más seria del artículo, porque esta es la técnica donde el exceso de ingeniería acecha con mejor disfraz: **cada peso es un número mágico que alguien tendrá que justificar, recalibrar y depurar**. Un sistema con siete boosts contextuales interactuando es un sistema donde nadie sabe ya por qué un documento quedó tercero — se ha sustituido la opacidad del embedding por una opacidad artesanal, que es peor porque encima parece controlable. La progresión sensata es conservadora: primero filtros duros y decaimiento temporal, que resuelven la mayor parte del problema con dos decisiones explicables; ponderación dinámica después, solo para los metadatos donde haya evidencia medida de que aporta, y con los multiplicadores documentados donde el siguiente desarrollador los encuentre. Un buen ejercicio de humildad: si no puedes explicar en una frase por qué un boost vale 1,3 y no 1,5, no estaba listo para producción.

## **Ensamblar el pipeline: el orden es el mensaje**

Cierra el artículo la pregunta de arquitectura que da sentido a todo lo anterior: un pipeline de recuperación moderno acumula etapas — reformulación de consultas, routing, filtros, búsqueda por dos ramas, fusión, reranking, ponderaciones —, ¿y en qué orden van? La respuesta no es arbitraria; sale de un principio que se puede enunciar en una línea y defender en cualquier revisión de arquitectura:

**Lo barato y excluyente, al principio; lo caro y fino, al final; lo blando, al cierre.**

Desplegado sobre las etapas:

1. **Reformulación y routing primero**, porque operan sobre la consulta y deciden *qué* se busca y *dónde* — todo lo demás depende de ellas.
2. **Filtros duros inmediatamente después**, empotrados en la propia consulta de búsqueda: reducen el universo antes de que nada caro lo recorra. Cada documento que el filtro excluye es trabajo que la búsqueda, la fusión y el reranking no harán.
3. **La búsqueda (con sus dos ramas, semántica y léxica) y su fusión**, sobre el universo ya filtrado, produciendo el conjunto amplio de candidatos.
4. **El reranking al final del tramo caro**, sobre los supervivientes y solo sobre ellos: es la etapa más costosa por documento, y cada etapa anterior existe, en parte, para que llegue poco y bueno.
5. **Las ponderaciones blandas (temporal, contextual) como último ajuste**, sobre la ordenación de los finalistas — donde una corrección de pesos es barata y sus efectos, visibles.

![articulo-06-figura-02-pipeline-completo.jpg](https://media1-production-mightynetworks.imgix.net/asset/52041ff7-6dd9-4474-b81d-5182b2bb964f/articulo-06-figura-02-pipeline-completo.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Obsérvese la asimetría deliberada entre los dos usos de los metadatos, que es la moraleja estructural del artículo: **los filtros duros van lo más temprano posible; las ponderaciones blandas, lo más tarde posible.** El filtro temprano ahorra trabajo a todo lo que sigue; la ponderación tardía ajusta sobre el conjunto pequeño donde equivocarse es barato y corregir es rápido. Invertir ese orden produce los dos clásicos del pipeline mal montado: rerankear documentos que un filtro iba a tirar (dinero quemado), y ponderar tan pronto que el ajuste blando expulsa candidatos del conjunto antes de que el reranker pudiera valorarlos (información destruida).

Y una nota final sobre el ensamblaje completo: no todas las consultas necesitan todas las etapas. El pipeline de la figura es el camino máximo; cada etapa debe poder activarse y desactivarse por configuración, tanto para medir su aportación como porque la consulta simple y nítida no tiene por qué pagar el peaje de la compleja. Un pipeline donde cada pieza es opcional y observable no es solo mejor ingeniería — es la única forma de responder, con datos, a la pregunta que cada pieza debe contestar para quedarse: ¿qué aportas tú, exactamente, y cuánto cuestas?

## **La relevancia no vive solo en el texto**

La idea para llevarse: la similitud semántica responde "¿de qué habla este documento?", y la relevancia real casi siempre necesita además "¿de cuándo es, de qué tecnología, de qué sector, y cuánto me fío?". Esas respuestas viven en los metadatos. Usados como filtro duro, abaratan todo el pipeline y eliminan lo que ninguna etapa posterior podría arreglar; usados como ponderación blanda, afinan el orden final sin destruir candidatos; y el tiempo — el metadato universal — se trata con ventanas cuando hay una razón categórica y con decaimiento cuando el valor simplemente se erosiona. Todo ello con la condición que sostiene el edificio: metadatos extraídos con calidad en la ingesta, porque un filtro confiado sobre un dato malo es el error más silencioso de toda la recuperación.

En la sesión en vivo ensamblaremos el pipeline completo sobre el sistema de estimación — todas las etapas, en su orden, cada una activable por configuración — y comprobaremos con consultas reales qué aporta cada pieza al resultado final. El presupuesto de 2019 seguirá en el corpus; lo que ya no podrá es disfrazarse de mejor referencia disponible.