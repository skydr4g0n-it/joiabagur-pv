# Reranking: cuando el top-k vectorial no es suficiente

Creada: 20 de junio de 2026 9:31
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S10. Técnicas de recuperación (https://app.notion.com/p/S10-T-cnicas-de-recuperaci-n-385ea9ca03c4806b8530fd77248bbb31?pvs=21)

Imagina esta escena en el sistema de estimación de proyectos. Llega una transcripción de reunión describiendo una plataforma de e-commerce: catálogo de productos, carrito, gestión de inventario, panel de administración. El pipeline de recuperación busca entre los presupuestos históricos y devuelve, en primera posición, el presupuesto de una app de pagos móviles que se hizo hace dos años.

No es un resultado absurdo. E-commerce y pagos comparten vocabulario (transacciones, pasarelas, checkout, seguridad), comparten contexto de negocio y probablemente comparten tecnologías. En el espacio vectorial, sus embeddings están genuinamente cerca. Pero para estimar una plataforma de e-commerce, ese presupuesto es casi inútil: el grueso del esfuerzo de un e-commerce está en el catálogo, el inventario y la administración, no en la pasarela de pago. Si el LLM genera la estimación con ese contexto, la estimación saldrá sesgada hacia un proyecto que no es el que tenemos delante.

Este es el problema central de este artículo: **la búsqueda vectorial es excelente encontrando candidatos y mediocre ordenándolos**. La distinción importa porque la solución no es cambiar de modelo de embeddings ni afinar el chunking — es añadir una segunda etapa que haga bien lo que la primera hace mal.

## **Por qué el bi-encoder ordena mal: la compresión tiene un precio**

El modelo de embeddings que usamos para vectorizar presupuestos y consultas es un **bi-encoder**: codifica cada texto por separado y lo comprime en un único vector de dimensión fija. La consulta se convierte en un vector, cada chunk de presupuesto se convirtió en otro en su día, y la relevancia se aproxima midiendo la distancia entre ambos.

Esa independencia es justo lo que hace al bi-encoder viable en producción. Como los documentos se codifican una sola vez en la ingesta, buscar es barato: vectorizar la consulta y comparar contra vectores precalculados con un índice aproximado. Millones de documentos, milisegundos de búsqueda.

Pero la compresión a un vector único tiene dos consecuencias que se pagan en el ranking fino:

**Primera: el vector promedia.** Un presupuesto de e-commerce con una sección menor sobre integración de pagos produce un embedding que mezcla todo su contenido. Un presupuesto de app de pagos produce un embedding donde los pagos dominan. Frente a una consulta que menciona pagos de pasada, ambos pueden quedar a distancias parecidas, porque el vector no distingue entre "habla principalmente de esto" y "lo menciona entre otras diez cosas".

**Segunda: consulta y documento nunca se miran.** El bi-encoder codifica cada texto sin saber con qué se va a comparar. No existe ningún punto del proceso en el que el modelo pueda razonar "esta consulta pide e-commerce y este documento trata sobre pagos; se parecen, pero no es lo que pide". La similitud coseno es geometría sobre dos resúmenes comprimidos, no una lectura conjunta.

El resultado práctico: entre los 50 presupuestos más cercanos a una consulta, los realmente relevantes casi siempre están. Pero el orden dentro de esos 50 es poco fiable, y a un pipeline RAG que va a pasar 5 documentos al LLM le va la vida en ese orden.

![articulo-01-figura-01-biencoder-vs-crossencoder.jpg](https://media1-production-mightynetworks.imgix.net/asset/97cb1d9c-5241-4fa9-80ac-78f8045c866e/articulo-01-figura-01-biencoder-vs-crossencoder.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Cross-encoders: leer los dos textos a la vez**

Un **cross-encoder** ataca exactamente esa limitación. En lugar de codificar consulta y documento por separado, los concatena en una sola entrada y los procesa juntos a través del transformer. Los mecanismos de atención operan sobre los tokens de ambos textos simultáneamente: cada palabra de la consulta puede atender a cada palabra del documento. La salida no es un vector, sino directamente una puntuación de relevancia del par.

Esa lectura conjunta es la diferencia cualitativa. El cross-encoder puede capturar que "plataforma de e-commerce" y "aplicación de pagos" comparten campo semántico pero no intención, porque ve los dos textos en el mismo contexto de atención y fue entrenado específicamente para puntuar relevancia de pares, no para producir representaciones reutilizables. En los benchmarks de ranking, los cross-encoders superan sistemáticamente a los bi-encoders en precisión de ordenación, y la intuición de por qué es sólida: tienen acceso a información que el bi-encoder destruyó al comprimir.

El precio es igual de claro: **no hay nada que precalcular**. La puntuación depende del par completo, así que cada consulta nueva obliga a pasar por el modelo cada par consulta-documento que queramos evaluar. Puntuar un documento cuesta una inferencia de transformer; puntuar todo un corpus de miles de presupuestos por cada consulta es inviable. El cross-encoder es preciso y lento; el bi-encoder es impreciso y rápido. Ninguno de los dos, solo, resuelve el problema.

## **Recall-then-rerank: dividir el trabajo**

La solución estándar en recuperación de información — anterior a los LLMs, de hecho; los buscadores web llevan décadas usándola — es encadenar ambos en un pipeline de dos etapas:

1. **Etapa de recall (búsqueda amplia).** La búsqueda vectorial recupera un conjunto generoso de candidatos: top-50, por ejemplo. Aquí no pedimos orden fino; pedimos que los documentos relevantes *estén en el conjunto*. Es la tarea en la que el bi-encoder es bueno, y es barata.
2. **Etapa de precision (reranking).** El cross-encoder puntúa cada uno de esos 50 pares consulta-documento y reordena. Nos quedamos con los mejores: top-5. Es la tarea en la que el cross-encoder es bueno, y como solo evalúa 50 pares en lugar de todo el corpus, su coste se vuelve asumible.

![articulo-01-figura-02-recall-then-rerank.jpg](https://media1-production-mightynetworks.imgix.net/asset/5b27cefe-e95f-49fc-b373-af9c992c03bc/articulo-01-figura-02-recall-then-rerank.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Los dos números del pipeline merecen criterio propio, no valores por inercia:

**El tamaño del conjunto amplio (50 en el ejemplo)** controla el techo de calidad. Si el presupuesto relevante no entra en el top-50 vectorial, ningún reranker lo va a rescatar: el reranking reordena, no recupera. Un conjunto mayor da más margen al reranker a cambio de más latencia, porque cada candidato adicional es una inferencia más. En corpus pequeños y heterogéneos como un histórico de presupuestos de empresa, entre 30 y 75 candidatos suele ser razonable; vigilar qué posición ocupaban los documentos relevantes en el ranking vectorial original dice rápidamente si el margen es suficiente.

**El tamaño del conjunto final (5 en el ejemplo)** lo dicta el consumidor del contexto, no el reranker. ¿Cuántos presupuestos completos caben con holgura en el contexto del LLM sin diluir la instrucción? ¿Cuántos aporta de verdad el caso de uso? Para estimación de proyectos, pasar 5 presupuestos bien elegidos produce mejores resultados que pasar 15 mediocres: el modelo generador también sufre cuando le entierras la señal en ruido.

## **El panorama de modelos: local u hospedado**

Hay dos caminos para incorporar un reranker, con trade-offs nítidos.

### **Cross-encoders open source en local**

La librería `sentence-transformers` ofrece la vía más directa para servir un cross-encoder dentro del propio servicio IA. La familia clásica es `ms-marco-MiniLM`, entrenada sobre el dataset MS MARCO de pares consulta-pasaje: modelos pequeños (decenas de millones de parámetros), rápidos en CPU para lotes de 50 candidatos, y sorprendentemente competentes.

Hay un matiz que en un proyecto con datos en español no es opcional: **los modelos clásicos de MS MARCO son monolingües en inglés**. Para corpus en español o multilingües, las opciones serias son `mmarco-mMiniLMv2` (la variante multilingüe de la misma familia, ligera) o `BAAI/bge-reranker-v2-m3` (más potente y más pesado, multilingüe nativo). La elección entre ambos es el clásico equilibrio calidad-latencia: el MiniLM multilingüe responde en decenas de milisegundos por lote en CPU; el BGE sube la calidad de ordenación a cambio de necesitar más músculo, idealmente GPU si el volumen de consultas crece.

A favor de lo local: coste marginal cero por consulta, los datos no salen de tu infraestructura (con presupuestos de clientes, esto puede ser requisito y no preferencia), y latencia sin red de por medio. En contra: la dependencia de PyTorch engorda la imagen del servicio en cientos de megas, el modelo consume memoria de forma permanente, y la calidad de los modelos pequeños, aunque buena, no es punta de gama.

### **Rerankers como servicio**

La alternativa es delegar en una API. **Cohere Rerank** es la referencia del segmento: se le envía la consulta y la lista de documentos, devuelve la lista reordenada con puntuaciones. Su modelo multilingüe cubre el español sin configuración adicional, la calidad es superior a la de los cross-encoders pequeños locales, y la integración son tres líneas de cliente HTTP sin tocar la imagen Docker.

En contra: cada consulta tiene coste monetario directo, añade una dependencia de red en el camino crítico de cada recuperación (con su latencia y sus fallos), y los documentos viajan a un tercero — exactamente lo que la opción local evitaba. Para un histórico de presupuestos con información comercial sensible, este último punto merece una conversación con quien corresponda antes de elegir.

### **Una posición, no una lista de pros y contras**

Para un sistema interno con corpus en español, volumen de consultas moderado y datos sensibles, el punto de partida sensato es **un cross-encoder multilingüe ligero en local**: el coste de infraestructura es asumible, la mejora sobre el ranking vectorial puro es inmediata y los datos no salen de casa. El salto a un reranker hospedado se justifica cuando la calidad del modelo ligero se queda corta de forma medible o cuando no quieres cargar con la operación del modelo — y esa decisión hay que tomarla con números de tu propio dominio delante, no con benchmarks genéricos.

## **Implementación en el servicio IA**

El reranker es un componente de la capa de recuperación y vive con ella. En un servicio FastAPI organizado por capas, esto significa un módulo propio dentro del paquete de retrieval, junto a la búsqueda vectorial a la que complementa.

El wrapper esencial sobre `sentence-transformers`:

```python
# app/generation/rag/retrieval/reranker.py

from sentence_transformers import CrossEncoder

from app.foundation.config import settings
from app.foundation.logging import get_logger

logger = get_logger(__name__)

class Reranker:
    """Cross-encoder reranker for retrieved candidates."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.reranker_model_name
        self._model = CrossEncoder(self._model_name)
        logger.info("reranker_loaded", model=self._model_name)

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Score query-candidate pairs jointly and return the top_k best."""
        if not candidates:
            return []

        pairs = [(query, candidate.content) for candidate in candidates]
        scores = self._model.predict(pairs)

        ranked = sorted(
            zip(candidates, scores),
            key=lambda item: item[1],
            reverse=True,
        )

        logger.info(
            "rerank_completed",
            candidates_in=len(candidates),
            candidates_out=min(top_k, len(ranked)),
        )

        return [candidate for candidate, _ in ranked[:top_k]]
```

Tres decisiones de este código merecen comentario, porque son las que diferencian un ejemplo de tutorial de un componente de producción:

**El modelo se carga una vez, en la construcción.** Cargar un cross-encoder cuesta segundos; hacerlo por consulta sería un desastre de latencia. La instancia del reranker debe crearse en el arranque de la aplicación y compartirse entre peticiones — el mismo patrón de singleton de ciclo de vida que ya sigue el cliente del LLM. La primera consecuencia operativa: el arranque del servicio se vuelve más lento y más pesado en memoria, y el healthcheck del contenedor debe esperar a que el modelo esté cargado antes de declarar el servicio listo.

**El reranker recibe y devuelve el mismo tipo.** Entra una lista de chunks recuperados, sale una lista de chunks recuperados, más corta y mejor ordenada. Esto lo convierte en una etapa opcional y componible del pipeline: activarlo o desactivarlo es decidir si la lista pasa o no por él, sin que el resto del flujo se entere. Cuando una técnica de recuperación se puede encender y apagar con un booleano de configuración, comparar su impacto deja de ser una refactorización y pasa a ser un experimento.

**El logging registra los tamaños de entrada y salida.** Cuando dentro de unos meses una estimación salga mal y haya que auditar por qué el sistema eligió esos presupuestos, el log estructurado de cada etapa — qué entró, qué salió, con qué modelo — es la diferencia entre diagnosticar en minutos o en días.

La integración en el flujo de recuperación queda entonces en una composición simple:

```python
# app/generation/rag/retrieval/pipeline.py (fragment)

async def retrieve(self, query: str) -> list[RetrievedChunk]:
    candidates = await self._vector_search.search(
        query,
        limit=settings.retrieval_candidate_pool_size,  # wide net: e.g. 50
    )

    if not settings.reranking_enabled:
        return candidates[: settings.retrieval_top_k]

    return self._reranker.rerank(
        query,
        candidates,
        top_k=settings.retrieval_top_k,  # narrow output: e.g. 5
    )
```

Nótese que la búsqueda vectorial es asíncrona (I/O contra la base de datos) y el reranking no lo es (cómputo local). En un servicio asyncio esto importa: una inferencia de cross-encoder de cientos de milisegundos ejecutada en el event loop bloquea todas las demás peticiones mientras dura. Si el reranker local entra en el camino de un endpoint con concurrencia real, la inferencia debe despacharse a un thread pool (`asyncio.to_thread` o el executor del loop). Es el tipo de detalle que no aparece en los tutoriales y sí en los incidentes.

## **La latencia: el impuesto del reranking**

Conviene tener claro dónde se paga el reranking, porque se paga siempre y en el peor sitio posible: el camino crítico de cada consulta, entre que el usuario pregunta y el LLM empieza a responder.

Los órdenes de magnitud orientativos para un lote de 50 candidatos: un cross-encoder ligero en CPU se mueve en decenas a pocos cientos de milisegundos; un modelo potente sin GPU puede irse a segundos (y con GPU vuelve a cientos de milisegundos); una API externa añade su inferencia más la ida y vuelta de red, típicamente entre cien y quinientos milisegundos. A esto se suma el coste fijo del arranque en frío local — la carga del modelo — que no afecta a cada consulta pero sí al despliegue y al autoescalado.

¿Es mucho? Depende de un denominador que solo tu caso de uso conoce. En el sistema de estimación, la generación posterior del LLM tarda varios segundos: un reranking de 200 ms es ruido frente a una mejora sustancial del contexto. En un autocompletado interactivo donde el presupuesto total de latencia es de 300 ms, ese mismo reranking es inasumible. La pregunta correcta nunca es "¿cuánto tarda el reranker?" sino "¿qué fracción de mi presupuesto de latencia consume y qué me devuelve a cambio?" — y responderla exige medir la ganancia de relevancia en tu dominio, con tus datos, no asumirla.

## **Cuándo no rerankear**

El reranking se ha vuelto recomendación por defecto en cualquier artículo sobre RAG, y conviene resistirse al defecto. Hay escenarios donde sobra:

- **Cuando el ranking vectorial ya es suficiente.** Si los documentos relevantes aparecen consistentemente en las primeras posiciones — corpus pequeños y bien diferenciados, consultas muy específicas — el reranker reordena algo que ya estaba bien ordenado. Coste sin beneficio.
- **Cuando el cuello de botella está antes.** Si los documentos relevantes ni siquiera entran en el conjunto amplio de candidatos, el problema es de recall: del chunking, de los embeddings o de la propia búsqueda. El reranking no rescata lo que no se recuperó, y añadirlo encima de un recall pobre es pulir el orden de los resultados equivocados.
- **Cuando el presupuesto de latencia no da.** Hay productos donde los milisegundos mandan, y la honestidad arquitectónica consiste en reconocerlo en lugar de degradar la experiencia por seguir una buena práctica genérica.

La señal de que el reranking es la herramienta correcta es precisa: los documentos relevantes *están* entre los candidatos recuperados, pero *no arriba*. Ese es exactamente el caso del presupuesto de e-commerce enterrado bajo la app de pagos — y por eso esta técnica es la primera parada para mejorar la recuperación del sistema de estimación.

## **El orden importa, y se puede comprar**

La idea para llevarse de este artículo cabe en tres frases. La búsqueda vectorial encuentra bien y ordena regular, porque comprime cada texto en un vector que nunca llega a mirar a la consulta. El cross-encoder ordena bien y escala mal, porque lee cada par consulta-documento conjuntamente. El pipeline recall-then-rerank compra lo mejor de ambos: una red amplia y barata para no dejarse nada, y una lectura fina y cara solo sobre los finalistas.

En la sesión en vivo lo veremos funcionar sobre el proyecto: integraremos el reranker en el pipeline de recuperación de presupuestos y comprobaremos, con consultas reales del dominio, cómo cambia lo que le llega al LLM — y, con ello, la calidad de las estimaciones que produce.