# Content augmentation: preparar el contexto recuperado antes de generar

Creada: 27 de junio de 2026 11:32
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S11. RAG Avanzado - Generación y Calidad (https://app.notion.com/p/S11-RAG-Avanzado-Generaci-n-y-Calidad-38cea9ca03c48049a493d33b89499a1d?pvs=21)

Cuando el sistema de estimaciones recibe una transcripción y la convierte en una consulta, el pipeline de recuperación devuelve un puñado de fragmentos de presupuestos históricos: los más relevantes, ya filtrados, reordenados por un cross-encoder y ponderados por recencia. Es un buen conjunto de candidatos. El problema empieza justo después, en el paso que casi nadie mira: qué le pasamos exactamente al modelo que va a generar la estimación.

La respuesta honesta, en la mayoría de implementaciones, es "los fragmentos tal cual". Se envuelven en delimitadores, se ordenan, se trunca lo que no cabe, y al prompt. Y ahí está el agujero. Un fragmento de un presupuesto real no es una ficha limpia con el dato que buscas. Es un trozo de documento de cliente: cabeceras, condiciones de pago, un módulo de autenticación que no viene al caso, el de pagos que sí, totales, IVA, una nota sobre el calendario de hitos. Cuando estimas un módulo de pagos y recuperas ese fragmento, el 80% de lo que le das al modelo es ruido para esta consulta concreta.

Content augmentation es la capa que vive entre la recuperación y la generación, y su trabajo es convertir fragmentos crudos en contexto destilado: lo justo, en el orden correcto, sin perder la trazabilidad. No mejora la recuperación, eso ya está hecho, ni mejora el prompt de generación. Mejora el material con el que el modelo trabaja. Y resulta que es una de las palancas de calidad con mejor relación coste-beneficio de todo el sistema.

## **Por qué el ruido en el contexto es caro**

Pasar fragmentos crudos tiene tres costes, y los tres son medibles.

El primero es **tokens**. Pagas por cada token de entrada, y el ruido son tokens. Si la mitad de cada fragmento es boilerplate de presupuesto, estás pagando el doble de contexto para la misma señal. En volumen, eso es dinero real y latencia real.

El segundo es **atención**. Los modelos no reparten su atención de forma uniforme sobre un contexto largo: lo que está al principio y al final pesa más que lo que queda en el medio. Si la línea que de verdad respalda tu estimación, "módulo de pagos con pasarela Stripe, 40h", queda sepultada en mitad de un fragmento largo lleno de líneas irrelevantes, el modelo puede no apoyarse en ella aunque esté ahí. La recuperación la trajo; la generación la ignora.

El tercero, y el más serio para un sistema de estimaciones, es **riesgo de alucinación**. Cuanta más densidad de cifras irrelevantes le das al modelo, más fácil es que agarre la equivocada. Si en el contexto hay un "120h" que pertenece a un módulo de reporting de otro proyecto, y el modelo lo arrastra a la línea de pagos, has generado una cifra plausible y falsa. El ruido numérico no es neutral: es combustible para la alucinación. Destilar el contexto no es solo eficiencia, es una primera línea de defensa.

## **La capa de augmentation como pipeline componible**

La augmentation no es una técnica, son varias, y conviene tratarlas como etapas componibles con un contrato uniforme, fragmentos entran, evidencia destilada sale, igual que el resto del pipeline. Cada etapa debe poder activarse, desactivarse y medirse de forma aislada, porque cada una puede ayudar o hacer daño según el caso.

```python
class AugmentedContext(BaseModel):
    evidence: list[BudgetEvidence]
    dropped_chunk_ids: list[str]
    token_estimate: int

def augment_context(
    chunks: list[RetrievedChunk],
    target_components: list[str],
    token_budget: int,
) -> AugmentedContext:
    """Turn raw retrieved chunks into distilled, ordered evidence.

    Stages: compress -> extract key points -> order -> fit budget.
    Every stage is independently toggleable and logged.
    """
    compressed = [compress_chunk(c, target_components) for c in chunks]
    evidence = [extract_key_points(c) for c in compressed]
    ordered = order_by_relevance(evidence)
    return fit_to_budget(ordered, token_budget)
```

![art1-fig1-augmentation-pipeline.jpg](https://media1-production-mightynetworks.imgix.net/asset/31b1c9ca-c0c9-4b67-8978-83760913b5ba/art1-fig1-augmentation-pipeline.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La firma ya transporta una decisión importante: la augmentation necesita saber **qué** estás estimando (`target_components`). La recuperación trabaja a nivel de consulta global; la destilación es específica de lo que vas a generar. Es lo que permite descartar el módulo de autenticación de un fragmento cuando estás estimando pagos.

Un detalle que atraviesa todas las etapas y que es fácil de romper: **preservar el** `chunk_id` **de origen**. Cuando comprimes un fragmento, sigue siendo evidencia derivada de un presupuesto histórico concreto, y más adelante cada línea de la estimación tendrá que poder señalar de qué fuente salió. Si tu compresor produce texto huérfano sin id, has destruido la trazabilidad antes de generarla. Cada pieza de evidencia destilada arrastra el id de su chunk.

## **Compresión: extractiva frente a abstractiva**

Comprimir un fragmento significa quedarte con lo que importa y tirar el resto. Hay dos familias, y la elección no es estética.

La **compresión extractiva** selecciona fragmentos del texto original sin reescribirlos. Para presupuestos, que son semi-estructurados, suele bastar con quedarte con las líneas que mencionan el componente que estás estimando. Es barata, no hay llamada a un modelo, es rápida, y tiene una propiedad que para estimaciones vale oro: **no puede inventar nada**, porque solo copia.

```python
def compress_chunk(
    chunk: RetrievedChunk,
    target_components: list[str],
) -> CompressedChunk:
    """Extractive compression: keep only lines relevant to the target.

    No model call, no rewriting -> nothing can be hallucinated here.
    """
    targets = [t.lower() for t in target_components]
    kept = [
        line
        for line in chunk.text.splitlines()
        if any(t in line.lower() for t in targets) or _looks_like_figure(line)
    ]
    return CompressedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        text="\n".join(kept) if kept else chunk.text,
        was_compressed=bool(kept),
    )
```

El `if kept else chunk.text` no es un descuido: si el filtro extractivo se queda sin nada, devolver el fragmento entero es preferible a devolver vacío. Una compresión que vacía el contexto en silencio es exactamente el mismo error que un filtro de metadatos demasiado agresivo en la recuperación: degradas el recall y no te enteras. Por eso `was_compressed` viaja en la salida y se loguea.

La **compresión abstractiva** usa un modelo para resumir el fragmento enfocándose en la consulta. Es más flexible, entiende sinónimos, reorganiza, condensa prosa larga, y es la opción natural para fragmentos narrativos como transcripciones, donde no hay "líneas" que filtrar. Pero introduce algo que conviene mirar de frente: **un segundo punto de generación**. Si el resumen alucina, y resumir es generar, esa alucinación entra en el contexto con apariencia de fuente, y la generación final la cita como si fuera dato real. Has movido el problema de la alucinación aguas arriba, donde es más difícil de detectar.

Cuando la augmentación abstractiva es necesaria, la forma de contenerla es no dejar que el modelo escriba prosa libre, sino forzarlo a extraer estructura:

```python
class BudgetEvidence(BaseModel):
    chunk_id: str
    document_id: str
    component: str
    hours: float | None
    cost_eur: float | None
    sector: str | None
    project_year: int | None
    note: str  # short, grounded justification

def extract_key_points(chunk: CompressedChunk) -> BudgetEvidence:
    """Abstractive extraction constrained to a strict schema.

    The model fills fields, it does not write free prose. A missing
    figure stays None instead of being invented.
    """
    response = client.responses.parse(
        model=settings.augmentation_model,  # cheap tier, e.g. gpt-5-mini
        input=[
            {"role": "system", "content": KEY_POINT_EXTRACTION_INSTRUCTIONS},
            {"role": "user", "content": chunk.text},
        ],
        text_format=BudgetEvidence,
    )
    evidence = response.output_parsed
    evidence.chunk_id = chunk.chunk_id
    evidence.document_id = chunk.document_id
    log.info(
        "key_points_extracted",
        chunk_id=chunk.chunk_id,
        has_hours=evidence.hours is not None,
    )
    return evidence
```

El esquema estricto hace dos cosas. Restringe la salida a campos concretos, así que el modelo no puede divagar; y permite el `None` explícito, que es la diferencia entre "este presupuesto no daba el dato de horas" y "el modelo se inventó un número para rellenar el hueco". En estimaciones, ese `None` honesto vale más que una cifra de relleno.

![art1-fig2-crudo-a-evidencia.jpg](https://media1-production-mightynetworks.imgix.net/asset/2d893902-7dea-46c2-bff4-a8cb2b1111d1/art1-fig2-crudo-a-evidencia.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La extracción de puntos clave es, además, donde la augmentation aporta su mayor valor para este caso de uso. Un fragmento crudo es prosa o tabla desordenada; `BudgetEvidence` es una ficha limpia con componente, horas, coste, sector y año. El modelo de generación recibe estructura comparable en lugar de texto que tiene que parsear mentalmente, y eso reduce a la vez el ruido y el riesgo.

## **Ordenar y priorizar: poner lo bueno donde se ve**

Una vez tienes evidencia destilada, el orden importa, y por la misma razón que importaba dentro de cada fragmento: la atención del modelo no es plana. La estrategia más robusta es cargar los extremos, colocar la evidencia más fuerte al principio y al final del bloque de contexto, y dejar la más débil en el medio, que es donde el modelo menos mira.

```python
def order_by_relevance(evidence: list[BudgetEvidence]) -> list[BudgetEvidence]:
    """Edge-load the context: strongest evidence first and last.

    Assumes `evidence` arrives sorted by descending relevance score.
    """
    ordered: list[BudgetEvidence] = []
    front = True
    for item in evidence:
        if front:
            ordered.insert(0, item)
        else:
            ordered.append(item)
        front = not front
    return ordered
```

![art1-fig3-carga-extremos.jpg](https://media1-production-mightynetworks.imgix.net/asset/185b35e9-6b87-46f1-bb8e-499c05fbeb18/art1-fig3-carga-extremos.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La señal de relevancia para ordenar no tiene por qué ser solo la del reranker. La recuperación ya calculó un peso temporal por recencia; un presupuesto de hace seis meses suele ser mejor referencia de coste que uno de hace cuatro años. Combinar relevancia y recencia en la ordenación es legítimo, siempre que lo hagas de forma explícita y medible, no con una pila de multiplicadores mágicos imposibles de justificar.

Y al final, el presupuesto de tokens manda. Si la evidencia destilada todavía no cabe, no truncas por el medio a ciegas: descartas las piezas más débiles primero y registras cuáles, para que un fallo de generación pueda rastrearse hasta "dejé fuera la fuente que lo respaldaba".

```python
def fit_to_budget(
    evidence: list[BudgetEvidence],
    token_budget: int,
) -> AugmentedContext:
    kept, dropped, used = [], [], 0
    for item in evidence:
        cost = estimate_tokens(item)
        if used + cost <= token_budget:
            kept.append(item)
            used += cost
        else:
            dropped.append(item.chunk_id)
    log.info("context_fitted", kept=len(kept), dropped=len(dropped), tokens=used)
    return AugmentedContext(evidence=kept, dropped_chunk_ids=dropped, token_estimate=used)
```

## **Trade-offs honestos**

**Extractiva contra abstractiva no es una preferencia, es una decisión de riesgo.** Para un corpus de cifras, la extractiva gana casi siempre: barata, rápida, incapaz de inventar. La abstractiva es para cuando la fuente es narrativa y no hay estructura que filtrar. Si vas a usarla, restríngela a un esquema y asume que has añadido un punto de generación que también hay que vigilar.

**Comprimir para ahorrar puede salir más caro.** Un resumidor con LLM por fragmento se multiplica por el número de fragmentos recuperados. Si recuperas ocho y resumes cada uno con una llamada, esas ocho llamadas pueden costar más, en dinero y en latencia, que pasar los fragmentos crudos a la generación. La compresión abstractiva solo compensa cuando el ahorro de tokens de generación supera el coste de las llamadas de compresión, y eso depende de tu volumen. Mídelo antes de asumirlo.

**Cada destilación es una decisión de qué tirar, y tirar lo que no debías es un fallo silencioso.** Si tu compresor extractivo se basa en coincidencia de palabras y el presupuesto llamaba "módulo de cobros" a lo que tú buscas como "pagos", lo descartas. Has degradado el recall en la capa de augmentation, no en la de recuperación, y eso es más difícil de diagnosticar porque la recuperación parecía correcta. La lección es la misma de siempre: cada etapa que puede tirar información tiene que loguear qué tiró.

**La sobre-compresión borra el matiz que justificaba la analogía.** A veces el valor de un presupuesto histórico no está en la cifra, sino en una nota al margen, "40h pero con la pasarela ya integrada del proyecto anterior", que explica por qué ese número no es trasladable sin ajuste. Si destilas hasta dejar solo "pagos: 40h", el modelo pierde el contexto que lo haría estimar bien. El punto óptimo de compresión no se adivina, se mide contra la calidad de la estimación final.

**Enriquecer también es generar.** Una técnica habitual es añadir a cada fragmento una cabecera sintética que lo sitúe, "presupuesto sector fintech, 2024, proyecto con módulo de pagos similar", para que el modelo entienda de un vistazo qué está leyendo. Ayuda, pero esa cabecera la escribe un modelo, así que aplica la misma cautela: modelo barato, formato corto, y nunca una afirmación que no esté en el fragmento.

## **Lo que esto deja sin resolver**

La augmentation prepara el material: lo limpia, lo estructura, lo ordena, lo recorta a lo que cabe. Hace que el modelo trabaje con señal en vez de con ruido. Pero hay un problema que ninguna cantidad de destilación resuelve, y es el que de verdad separa una estimación mediocre de una buena.

Cuando dos presupuestos históricos, ambos relevantes, ambos recientes, ambos bien destilados, dicen cosas distintas sobre lo mismo, la augmentation no decide nada. Un proyecto cifró el módulo de pagos en 40h; otro, igual de comparable, en 90h. Los dos entran limpios en el contexto. Comprimir y ordenar no resuelve cuál pesa más, ni cómo combinar evidencia que se contradice en una sola estimación coherente que, además, pueda explicar de dónde sale cada número. Eso ya no es preparar el contexto: es sintetizar fuentes. Y es ahí donde la calidad de la generación se empieza a ganar de verdad.