# Multi-indice y routing

Creada: 20 de junio de 2026 9:41
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S10. Técnicas de recuperación (https://app.notion.com/p/S10-T-cnicas-de-recuperaci-n-385ea9ca03c4806b8530fd77248bbb31?pvs=21)

Durante sus primeras semanas de vida, el sistema de estimación tenía un corpus homogéneo: presupuestos históricos, troceados y vectorizados. Pero los sistemas RAG reales engordan, y el nuestro ya almacena tres familias de documentos bien distintas: los **presupuestos** (estructurados, telegráficos, llenos de partidas y cifras), las **transcripciones de reuniones** (lenguaje oral, redundante, divagante, donde la información útil nada entre muletillas) y la **documentación técnica** interna (descriptiva, densa, escrita para ser referencia).

Y con la mezcla llega un fenómeno incómodo. Ante la consulta "¿cuánto costó la integración con SAP en proyectos anteriores?", el documento que responde es un presupuesto. Pero en un índice único que mezcla las tres familias, el top-5 viene contaminado: dos chunks de transcripciones donde un cliente *habló* de SAP largo y tendido, un fragmento de documentación técnica sobre conectores, y solo después los presupuestos. Semánticamente, todos orbitan "integración con SAP"; funcionalmente, solo unos pocos sirven para estimar. El índice único responde a "¿qué se parece a esta consulta?" cuando la pregunta real era "¿qué presupuesto se parece a esta consulta?" — y esa diferencia, que un humano resuelve sin pensar, el índice no puede resolverla porque nadie se lo ha dicho.

Este artículo trata de decírselo: cómo particionar el corpus en colecciones especializadas y cómo decidir, consulta a consulta, dónde buscar. La técnica se llama **RAG multi-índice con routing**, y como todas las de su familia, es tan valiosa cuando toca como contraproducente cuando se aplica por moda.

## **Por qué el índice único se degrada con la mezcla**

Conviene precisar el mecanismo de la degradación, porque no es solo "salen resultados de otro tipo".

**Las familias de documentos tienen texturas semánticas distintas.** Una transcripción de cuarenta minutos y un presupuesto de tres páginas no se embeben igual: el lenguaje oral produce chunks difusos y temáticamente mezclados; el lenguaje de presupuesto produce chunks densos y monotemáticos. Cuando ambos compiten en el mismo espacio por la misma consulta, las distancias no son comparables en términos de utilidad — un chunk de transcripción puede quedar *más cerca* del embedding de la consulta precisamente por su verbosidad temática, siendo menos útil.

**El tipo dominante inunda.** Si el histórico tiene diez veces más chunks de transcripciones que de presupuestos (y lo tendrá: las reuniones generan texto a un ritmo que los presupuestos no pueden seguir), el top-k de cualquier consulta tendrá la proporción que dicte el volumen, no la que dicte la utilidad.

**Cada familia quiere su propio preprocesamiento.** El chunking razonable para una transcripción (por turnos de palabra, por bloques temáticos) no es el de un presupuesto (por partidas) ni el de documentación (por secciones). Un índice único empuja hacia un preprocesamiento único de compromiso, mediocre para todos.

**Y la operación sufre.** Reindexar las transcripciones —porque cambió su estrategia de chunking, por ejemplo— no debería tocar los presupuestos. En un índice único, todo cambio es un cambio global, con su riesgo global.

La respuesta arquitectónica es particionar: colecciones separadas, cada una con su preprocesamiento, su esquema de metadatos y su índice vectorial. Lo que abre dos preguntas de diseño: cómo particionar físicamente, y quién decide dónde buscar.

## **Particionar en PostgreSQL: columna discriminadora o tablas separadas**

Con el corpus en PostgreSQL, hay dos formas de materializar las colecciones, y la elección no es estética.

**Opción A — una tabla con columna discriminadora.** Todos los chunks conviven en una tabla con una columna `document_type`, y cada búsqueda filtra por tipo. Es la opción de menor fricción: una migración trivial, un solo modelo de datos, una sola consulta con un `WHERE` más. Funciona razonablemente cuando las familias comparten esquema (los mismos metadatos sirven para todas) y cuando muchas consultas quieren buscar en todas a la vez.

**Opción B — una tabla por familia.** `budget_chunks`, `transcript_chunks`, `technical_doc_chunks`: cada una con sus columnas propias, su índice vectorial propio y su ciclo de vida propio. Más piezas, más migraciones — y a cambio, cada familia puede tener el esquema que su naturaleza pide (los presupuestos llevan importes y partidas; las transcripciones llevan interlocutores y fechas de reunión; la documentación lleva versiones), cada índice HNSW se construye y ajusta sobre una población homogénea, y reindexar una familia es una operación local que no roza a las demás.

![articulo-05-figura-01-matriz-particionado.jpg](https://media1-production-mightynetworks.imgix.net/asset/74866c77-6298-46a1-b551-6cf33b570489/articulo-05-figura-01-matriz-particionado.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La regla de decisión que este artículo defiende: **si los esquemas de metadatos divergen, tablas separadas; si las familias son variaciones de lo mismo, columna discriminadora.** Los metadatos son la confesión involuntaria del diseño — cuando te descubres añadiendo columnas que solo tienen sentido para una familia (`speaker_count` que es NULL en todos los presupuestos, `total_amount` que es NULL en todas las transcripciones), la tabla única te está diciendo que en realidad son entidades distintas conviviendo a disgusto. En el sistema de estimación los esquemas divergen sin ambigüedad, así que el camino es la opción B. Con una honestidad operativa: tres tablas son tres migraciones, tres índices que monitorizar y tres pipelines de ingesta que mantener; el precio existe y se paga en mantenimiento, no en rendimiento.

## **El router: quién decide dónde buscar**

Con las colecciones separadas, cada consulta necesita un destino. La pieza que lo decide es el **router**, y su diseño tiene una jerarquía de soluciones que conviene recorrer en orden de coste — porque la versión cara y vistosa se ha vuelto el reflejo por defecto, y casi nunca es la primera que toca.

**Nivel cero: el mejor router es no tener router.** En un sistema real, muchas consultas llegan con su destino implícito en el contexto de quien las hace. El flujo de estimación del backend de negocio busca presupuestos *siempre*: no hay nada que clasificar. La forma correcta de capturar ese conocimiento es el contrato de la API — un parámetro explícito de colección, o directamente endpoints distintos por caso de uso. Es gratis, es determinista, es trazable, y convierte el routing en una decisión del que sabe (el llamante) en lugar de una adivinanza del que no (el servicio). Antes de construir cualquier clasificador, la pregunta obligada es: ¿de verdad el servicio IA tiene que adivinar algo que el backend de negocio ya sabe?

**Nivel uno: reglas deterministas.** Cuando la consulta llega sin destino — el caso del buscador libre interno, donde un usuario pregunta lo que quiera —, una capa de reglas baratas resuelve una parte sorprendente del tráfico: patrones de vocabulario inequívocos ("¿cuánto costó...?", "¿qué presupuestamos para...?" → presupuestos; "¿qué dijo el cliente...?", "¿qué se acordó en la reunión...?" → transcripciones). Las reglas son frágiles ante la creatividad lingüística, pero gratis en latencia y transparentes al depurar; como primer filtro antes del clasificador caro, rinden.

**Nivel dos: el LLM como clasificador.** Para lo que las reglas no resuelven, una llamada a un modelo pequeño con salida estructurada. La disciplina es la misma de cualquier LLM con función de infraestructura: esquema cerrado, instrucciones que acotan, y un diseño de salida que contemple la duda honesta:

```python
# app/generation/rag/retrieval/router.py

from enum import StrEnum

from pydantic import BaseModel, Field

class SearchTarget(StrEnum):
    BUDGETS = "budgets"
    TRANSCRIPTS = "transcripts"
    TECHNICAL_DOCS = "technical_docs"

class RoutingDecision(BaseModel):
    """Which collections a query should be searched against."""

    targets: list[SearchTarget] = Field(
        min_length=1,
        max_length=3,
        description="Collections to search. Use several only when the query genuinely spans them.",
    )
    reason: str = Field(description="One short sentence explaining the choice")

ROUTING_INSTRUCTIONS = """
You classify search queries for a project estimation system into the
collections they should be searched against.

Collections:
- budgets: historical project budgets, with line items, effort and cost figures.
- transcripts: meeting transcripts between the team and clients.
- technical_docs: internal technical documentation and architecture references.

Rules:
- Choose the single most appropriate collection whenever possible.
- Choose several collections only when the query genuinely needs them.
- Questions about cost, effort or estimates belong to budgets, even if the
  query mentions meetings or documents.
"""

async def route_query(self, query: str) -> RoutingDecision:
    """Classify a query into the collections it should be searched against."""
    response = await self._client.responses.parse(
        model=settings.router_model,
        instructions=ROUTING_INSTRUCTIONS,
        input=query,
        text_format=RoutingDecision,
    )
    decision = response.output_parsed
    logger.info(
        "query_routed",
        targets=[target.value for target in decision.targets],
        reason=decision.reason,
    )
    return decision
```

Tres decisiones de este diseño merecen defensa. La salida es una **lista de destinos, no un destino con un número de confianza**: cuando el clasificador duda entre dos colecciones, la acción correcta no es elegir mal con un 0,55 de confianza, es buscar en ambas — y modelar la salida como lista convierte la duda en un comportamiento bien definido en lugar de un umbral arbitrario que calibrar. El campo `reason` no es decorativo: cuesta una frase de tokens y convierte cada decisión de routing en algo auditable cuando, meses después, alguien pregunte por qué una consulta acabó buscando donde buscó. Y el `StrEnum` cierra el universo de respuestas — el modelo no puede inventarse una colección que no existe, porque el esquema no se lo permite.

**El último peldaño: cuando ni el clasificador decide, se busca en todo.** Buscar en paralelo en las tres colecciones y combinar es el fallback honesto, y su coste en latencia es el de la colección más lenta, no la suma. La degradación es elegante: en el peor caso, el sistema multi-índice se comporta como el índice único del que veníamos — nunca peor.

![articulo-05-figura-02-cascada-routing.jpg](https://media1-production-mightynetworks.imgix.net/asset/f9ef8b7b-87f7-4bac-ba80-d43552ffc827/articulo-05-figura-02-cascada-routing.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Combinar resultados de colecciones distintas: con cuidado**

Cuando una consulta acaba buscando en varias colecciones, aparece una trampa que ya conocemos en versión agravada: las puntuaciones de similitud de colecciones distintas **no son comparables entre sí** — cada colección tiene su textura, su distribución de distancias, su densidad. Fusionar por puntuación cruda hace que la colección de distancias generosas devore a las demás.

Las salidas sensatas son dos. Si el consumidor necesita un ranking único, fusión por posiciones o por cuotas por colección (los dos mejores de cada una), nunca por puntuación cruda. Pero muchas veces la respuesta correcta es **no fusionar**: presentar los resultados agrupados por procedencia — "esto dicen los presupuestos; esto se habló en reuniones" — porque el consumidor final (humano o LLM generador) hace cosas distintas con cada familia, y aplanarlas en una lista única destruye información que costó un router obtener. Para eso, cada chunk recuperado debe viajar con su etiqueta de procedencia. No es un detalle: la procedencia es lo que permitirá después atribuir, auditar y depurar, y perderla en la fusión es perderla para siempre.

## **La semilla de algo más grande**

Una observación de arquitectura antes de cerrar, porque conecta esta pieza con el futuro del sistema. El patrón que acabamos de construir — un componente que examina una petición y la delega en el especialista adecuado, con la opción de consultar a varios y combinar — no es exclusivo de la búsqueda. Es un patrón general de delegación, y es exactamente el embrión de cómo los sistemas con agentes se reparten el trabajo: un coordinador que decide qué especialista atiende qué petición. La diferencia es de grado y de libertad: nuestro router hace *una* clasificación acotada con un esquema cerrado, sin razonamiento abierto ni herramientas. Esa contención es deliberada — para decidir dónde buscar, una clasificación barata y auditable rinde más que cualquier sofisticación —, pero el patrón mental que deja instalado se reutilizará, ampliado, más adelante en el programa.

## **Cuándo no particionar**

Como siempre, la técnica tiene su contraindicación, y en este caso es especialmente tentador ignorarla porque particionar *parece* arquitectura seria.

No particiones si el corpus es funcionalmente homogéneo, por mucho que los documentos tengan orígenes distintos. No particiones si una colección concentraría el 95% de las consultas: el router sería un peaje que casi siempre da la misma respuesta. Y no particiones "para cuando crezcamos": tres tablas, tres ingestas y un router son deuda de mantenimiento contraída hoy contra una necesidad hipotética. La señal legítima para particionar es observable y concreta: resultados de una familia contaminando consultas dirigidas a otra, de forma recurrente y medible. En el sistema de estimación esa señal existe — el ejemplo de SAP del arranque no es hipotético, es el comportamiento real de un índice mezclado —; en otro sistema, quizá no. Particionar sin la señal es sumar complejidad para resolver un problema que no se tiene.

## **Buscar donde está la respuesta**

La idea para llevarse: un corpus heterogéneo en un índice único responde siempre a la pregunta equivocada — "qué se parece" en lugar de "qué se parece *de entre lo que sirve*". Particionar en colecciones devuelve a cada familia su preprocesamiento, su esquema y su índice; el routing decide el destino con una jerarquía de coste creciente — el contrato de la API primero, reglas después, el clasificador LLM solo para lo que queda, y la búsqueda en todo como fallback honesto; y la combinación de colecciones respeta lo que la fusión ingenua destruye: que las puntuaciones no son comparables y que la procedencia es información.

En la sesión en vivo montaremos el routing sobre el sistema de estimación con sus tres colecciones reales, y comprobaremos con consultas del dominio cómo cambia el resultado cuando "¿cuánto costó la integración con SAP?" deja de competir contra cuarenta minutos de reunión que hablaban de otra cosa.