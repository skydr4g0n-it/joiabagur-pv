# Augmentation: ensamblar contexto para que el LLM lo use bien

Creada: 15 de junio de 2026 12:59
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S9. Fundamentos de RAG y técnicas de recuperación (https://app.notion.com/p/S9-Fundamentos-de-RAG-y-t-cnicas-de-recuperaci-n-380ea9ca03c480268ac0c4739784b444?pvs=21)

## **La tentación del `"\\n\\n".join` y por qué falla**

El retriever del Artículo 3 te ha devuelto cinco chunks de presupuestos históricos, bien filtrados por sector y por año, todos con cosine distance por debajo del threshold. Tienes la query reformulada del Artículo 2 con los campos estructurados (función, tecnologías, escala, restricciones regulatorias). Solo te falta pasar todo eso al modelo y obtener una estimación. La tentación inmediata — y la que la mitad de los tutoriales de RAG en internet enseña — se parece a esto:

```python
context = "\\n\\n".join([chunk.content for chunk in retrieved_chunks])
prompt = f"Contexto:\\n{context}\\n\\nGenera una estimación para: {query_text}"
response = client.responses.create(model="gpt-5", input=[{"role": "user", "content": prompt}])
return response.output_text
```

El código funciona, en el sentido de que no lanza ninguna excepción y devuelve algo que parece una estimación. Lo que produce con regularidad incómoda son tres clases de fallo que aparecen sin previo aviso en producción.

El primer fallo son las **citas inventadas**. El modelo, sin instrucciones claras sobre cómo referenciar las fuentes, fabrica identificadores que parecen razonables ("según el proyecto número 312...") cuando ese proyecto no estaba entre los chunks recuperados. El segundo son las **mezclas cruzadas**: el modelo combina información de chunks distintos como si fuera de un único proyecto, generando una estimación que no corresponde a ninguno de los presupuestos históricos reales. El tercero, y el más sutil, es la **respuesta sin contexto**: el modelo ignora silenciosamente los chunks que le has pasado y produce una estimación basada en su conocimiento general entrenado, dejándote la falsa impresión de que el retrieval ha funcionado cuando realmente no ha influido en la respuesta.

Las tres patologías tienen una causa común: el modelo no ha recibido instrucciones sobre cómo tratar el bloque de texto que le hemos pasado. No sabe si los chunks son contexto autoritativo del que debe extraer hechos, sugerencias inspiracionales que puede ignorar, o documentación que debe citar. No sabe si debe rechazar la generación cuando el contexto sea insuficiente o si debe forzar siempre una respuesta. No sabe qué fuente atribuir a cada afirmación. Esta etapa del flujo RAG — la augmentation — no es "meter chunks en el prompt"; es construir un input al modelo que le diga explícitamente todas esas cosas y le facilite hacer lo correcto. El presente artículo recorre las cinco decisiones que ese ensamblaje implica.

## **Delimitadores XML: que el modelo distinga contexto de instrucción**

Los modelos modernos están entrenados con cantidades masivas de XML — específicamente con las convenciones que Anthropic y OpenAI han popularizado para marcar partes estructurales de un prompt — y la consecuencia práctica es que reconocen etiquetas como `<source>`, `<context>` o `<document>` como límites semánticamente significativos. Cuando un chunk va envuelto en `<source id="142">...</source>`, el modelo entiende dos cosas que con la concatenación raw no le quedan claras: dónde empieza y dónde acaba esa unidad de información, y qué metadata estructural le acompaña.

En el servicio IA de tu proyecto, la función que ensambla el bloque de contexto vive en `generation/context_assembler.py` y tiene esta forma:

```python
def build_context_block(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for chunk in chunks:
        meta = [
            f'id="{chunk.id}"',
            f'sector="{chunk.sector}"',
            f'project_year="{chunk.project_year}"',
            f'chunk_type="{chunk.chunk_type}"',
            f'distance="{chunk.distance:.3f}"',
        ]
        attrs = " ".join(meta)
        blocks.append(f"<source {attrs}>\\n{chunk.content.strip()}\\n</source>")
    return "\\n\\n".join(blocks)
```

Tres detalles deliberados en este formato. Primero, **cada chunk va con metadata estructurada como atributos XML**, no embebida en el texto. La metadata es lo que permite al modelo citar con precisión ("según `source id=142`") y filtrar mentalmente por sector cuando sea relevante; meter sector y año en prosa dentro del chunk obligaría al modelo a parsearlo cada vez. Segundo, **se incluye la** `distance` entre los atributos. Esto es debatible: algunos sistemas prefieren ocultar la distancia al modelo para que no se sobreajuste a los chunks más cercanos; el programa adopta la posición opuesta porque exponer la distancia da al modelo una señal explícita de relevancia que puede usar al ponderar evidencia (más sobre esto en la sección de orden). Tercero, **el delimitador es** `<source>`, en singular, no `<context>` o `<document>`: la etiqueta se elige por su connotación — el modelo tiende a tratar cada `<source>` como una unidad atribuible de información, exactamente lo que queremos para forzar citaciones.

Una alternativa frecuente es **JSON delimited context**, donde el bloque se serializa como un array de objetos con `id`, `content` y metadata. Funciona, pero presenta un fallo silencioso: los modelos tienden a "leer" estructuras JSON dentro del prompt como datos a interpretar y no como instrucciones autoritativas. Un JSON con un campo `"content": "..."` se trata a veces como descripción, no como contexto de referencia. El delimitador XML lleva la connotación correcta de "esto es contenido de referencia que debes consultar".

![art_4_figura-10-anatomia-contexto.jpg](https://media1-production-mightynetworks.imgix.net/asset/291ab0c0-bf9c-433b-8e1a-b01ba2051453/art_4_figura-10-anatomia-contexto.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Orden de los chunks: lost in the middle es real y predecible**

Una vez que el ensamblador construye el bloque de contexto, queda decidir en qué orden van los chunks dentro de él. La intuición ingenua es que da igual: el modelo lee todo el contexto, le da el mismo peso a cada parte. La evidencia empírica dice lo contrario, y de forma medible.

El paper de referencia es "Lost in the Middle: How Language Models Use Long Contexts" (Liu et al., 2023). El experimento es directo: los autores construyen prompts con un contexto compuesto por N documentos de los cuales solo uno es relevante para la pregunta, y mueven sistemáticamente la posición del documento relevante. La curva de precisión resultante tiene forma de **U**: el modelo recupera la información cuando el documento relevante está al principio del contexto (precisión alta) o al final (precisión alta), pero la pierde con regularidad cuando está en el medio (precisión que cae hasta veinte puntos porcentuales). El efecto se ha replicado en GPT-4, en Claude, y en los modelos posteriores; no es un artefacto de una arquitectura específica.

![art_4_figura-11-lost-in-the-middle.jpg](https://media1-production-mightynetworks.imgix.net/asset/8a4602e5-bb75-4f97-8dcf-bdea28e86189/art_4_figura-11-lost-in-the-middle.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La implicación operativa es directa. Si tu retriever devuelve diez chunks ordenados por distancia ascendente, y los colocas en el contexto en ese mismo orden, el chunk con `rank=1` recibe atención privilegiada (está al principio), el chunk con `rank=10` también la recibe (está al final), y los chunks `rank=4-7` están en la zona de penalización. Tu retrieval está haciendo el trabajo correcto pero el modelo está degradando la mitad de tus chunks por geometría del prompt.

Hay dos estrategias para mitigarlo, y el programa adopta la primera por simplicidad. **Most-relevant-first** sin más artificio: dejar los chunks en el orden de distancia ascendente. El razonamiento es que, con `K=5-10` (el rango típico del programa), el efecto lost-in-the-middle es modesto y los chunks más relevantes están en las posiciones privilegiadas del principio. Para `K=15-20` el efecto se vuelve más severo y entonces sí merece la pena la **estrategia U-pattern**, donde los chunks se reordenan para que `rank=1` vaya al principio, `rank=2` vaya al final, `rank=3` vaya en segunda posición desde el principio, y así sucesivamente. Es código sencillo:

```python
def reorder_u_pattern(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    front, back = [], []
    for i, chunk in enumerate(chunks):
        (front if i % 2 == 0 else back).append(chunk)
    return front + list(reversed(back))
```

El programa deja esta función como opción configurable en el `context_assembler.py`, pero no la activa por defecto. La decisión de cuándo activarla es del operador del sistema y se basa en métricas observables: si tras desplegar a producción la calidad de las estimaciones es notablemente peor cuando `K` sube, es señal de que lost-in-the-middle está penalizando y vale la pena el reorder. En la sesión en vivo vamos a ver una demo concreta del efecto poniendo deliberadamente el chunk crítico en posiciones distintas y observando la estimación resultante.

## **Truncamiento defensivo: cortar el chunk completo, no el contenido**

Cuando el bloque de contexto excede el budget de tokens que el sistema se permite gastar por petición, hay que descartar contenido. El antipatrón clásico es truncar por caracteres o por palabras al llegar al límite: el último chunk se corta a mitad, queda incompleto, y el modelo intenta interpretarlo igualmente con tres consecuencias predecibles. La primera es que el chunk truncado pierde coherencia semántica y aporta ruido en lugar de señal. La segunda es que cualquier cita al `id` de ese chunk va a ser estructuralmente inválida — el modelo cita un proyecto del cual solo recibió la mitad de la evidencia. La tercera es que se desperdician todos los tokens del chunk truncado: aporta menos que cero a la respuesta.

La regla del programa es **truncar a nivel de chunk completo**: si el chunk no cabe entero, no entra en el contexto. La función queda así:

```python
def truncate_to_token_budget(
    chunks: list[RetrievedChunk],
    max_context_tokens: int,
    encoder,
) -> list[RetrievedChunk]:
    selected = []
    used_tokens = 0
    for chunk in chunks:  # already sorted by relevance
        wrapped_size = len(encoder.encode(_wrap_chunk(chunk)))
        if used_tokens + wrapped_size > max_context_tokens:
            break
        selected.append(chunk)
        used_tokens += wrapped_size
    return selected
```

El detalle clave es `_wrap_chunk(chunk)`: la función cuenta los tokens del chunk **ya envuelto con sus delimitadores XML y metadata**, no solo del contenido. Los delimitadores cuestan entre 30 y 50 tokens por chunk; ignorarlos en el cálculo deja al sistema con un budget consistentemente más optimista que la realidad. Si tu límite teórico es 8.000 tokens de contexto y olvidas contar los wrappers, vas a empezar a recortar al final del prompt cuando ya hayas excedido el límite real.

El segundo punto sobre truncamiento es **dejar margen para la salida**. El budget de tokens del modelo es total: input más output. Si el modelo tiene una ventana de 200k tokens y el output esperado son 1.500 tokens (una estimación estructurada con citaciones), el contexto no debería ocupar 199.000 tokens sino tener un buffer claro. El programa adopta como regla heurística reservar el 15% del budget total para la salida y otro 5% para overhead de prompt (system message, instrucciones, query estructurada). Sobre un modelo con 200k de ventana, eso deja 160k para el contexto recuperado — que en práctica es más de lo que cualquier retrieval razonable va a necesitar.

## **El prompt de generación: grounding explícito y política de "no sé"**

El prompt es lo que convierte un bloque de chunks en una instrucción accionable. La diferencia entre un prompt mediocre y uno disciplinado para RAG está en cuatro elementos concretos: la **restricción de fuentes**, la **obligación de citar**, la **política de insuficiencia** y la **distinción evidencia/asunción**. El system prompt del estimador queda así:

```python
ESTIMATOR_SYSTEM_PROMPT = """You are a senior software estimation assistant.
Your job is to produce structured budget estimates for new software projects
based on historical reference projects.

Rules you must follow:

1. Base every estimate ONLY on the information contained in <source> blocks.
   Do not rely on general knowledge or training data to set numbers.

2. Cite every quantitative claim with the source id it comes from. Example:
   "Backend implementation: 45 engineer-days (source 142, source 387)".

3. Never invent source ids. If no source supports a claim, surface it as an
   assumption with explicit impact level instead.

4. If the provided context is insufficient to estimate the new project,
   set confidence to "insufficient" and list what additional information
   would be needed. Do not force an estimate.

5. Distinguish evidence-backed components from assumptions you must make
   to bridge gaps in the historical data.

Output must conform to the provided JSON schema."""
```

Cada regla está ahí por una razón concreta. La regla 1 contiene el grounding explícito con `ONLY` en mayúsculas; aunque parece trivial, el contraste tipográfico es una señal que los modelos reconocen como énfasis y mejora la adherencia. La regla 2 fuerza la atribución: sin esta línea, el modelo cita "a veces" y de forma inconsistente; con ella, citar es parte del contrato. La regla 3 es lo que reduce las citas inventadas — el modelo tiene un camino explícito ("surface as assumption") para decir "no tengo evidencia", lo que reduce la presión para inventar. La regla 4 es el contrato más importante de todos: el modelo puede negarse a estimar, y la salida `confidence="insufficient"` activa el camino downstream que el orquestador maneja con criterio. La regla 5 separa numéricamente lo que está apoyado por el corpus de lo que requiere extrapolación.

El user prompt es más corto y combina el bloque de contexto con la query estructurada del reformulador:

```python
def build_user_prompt(context_block: str, structured_query: EstimationQuery) -> str:
    return f"""Historical reference projects:

{context_block}

New project to estimate:

{structured_query.model_dump_json(indent=2)}

Generate a structured estimate. Cite sources for every quantitative component.
If the historical context does not cover this kind of project sufficiently,
return confidence="insufficient" and explain what is missing."""
```

La repetición de la instrucción ("return confidence='insufficient' if ...") al final del user prompt es deliberada. El system prompt define las reglas; el user prompt las reactiva justo antes del momento en que el modelo va a generar. Los modelos atienden de forma especialmente fuerte al final del prompt, y poner ahí el recordatorio crítico mejora la tasa de respuestas honestas cuando el contexto es flojo.

## **Esquema de salida: structured output como contrato**

El sistema usa la Responses API con `text.format` y JSON schema strict, exactamente la misma mecánica que el reformulador del Artículo 2. La diferencia es la complejidad del esquema, que en este caso captura toda la estructura de la estimación más los metadatos de trazabilidad:

```python
from typing import Literal
from pydantic import BaseModel, Field

class SourceCitation(BaseModel):
    source_id: int
    relevance: Literal["primary", "supporting", "tangential"]
    used_for: str = Field(description="Which component this source informed")

class Assumption(BaseModel):
    description: str
    impact: Literal["high", "medium", "low"]
    rationale: str

class CostComponent(BaseModel):
    name: str
    engineer_days: int
    sources: list[int] = Field(description="Source ids that support this component")

class Estimate(BaseModel):
    total_engineer_days: int | None
    cost_breakdown: list[CostComponent]
    duration_weeks: int | None
    sources: list[SourceCitation]
    assumptions: list[Assumption]
    confidence: Literal["high", "medium", "low", "insufficient"]
    reasoning: str
    insufficient_context_explanation: str | None = Field(
        default=None,
        description="If confidence is 'insufficient', explain what is missing"
    )
```

El esquema codifica varias decisiones arquitectónicas. `total_engineer_days` y `duration_weeks` son `int | None`: cuando `confidence == "insufficient"`, el modelo debe devolverlos a `None` en lugar de inventarse un número. Cada `CostComponent` carga su propia lista de `sources`, lo que permite trazabilidad fina por componente, no solo a nivel global. `Assumption` separa explícitamente "qué se asume" de "por qué" para que la revisión humana posterior pueda evaluar la asunción. Y `insufficient_context_explanation` activa el camino de soft-fail simétrico al del retriever: cuando el modelo no puede estimar, el sistema captura el motivo en un campo dedicado en lugar de en una salida ad-hoc.

La llamada a la API encaja sin sorpresas:

```python
response = client.responses.create(
    model="gpt-5",
    input=[
        {"role": "system", "content": ESTIMATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "Estimate",
            "schema": Estimate.model_json_schema(),
            "strict": True,
        }
    },
    reasoning={"effort": "medium"},
)
estimate = Estimate.model_validate_json(response.output_text)
```

Dos parámetros merecen comentario. El modelo elegido para generación es `gpt-5` (no `gpt-5-mini` como el reformulador): la tarea aquí — sintetizar evidencia de múltiples fuentes, razonar sobre componentes, decidir cuándo no estimar — es genuinamente compleja, y el coste extra del modelo capable se justifica. El parámetro `reasoning.effort="medium"` es lo que en los modelos de razonamiento de OpenAI sustituye al `temperature` que las versiones anteriores aceptaban: `temperature` ya no es válido en gpt-5 — está en la guía de "Deprecated parameters in reasoning models" que cubrimos en la Sesión 01 — y la palanca operativa para controlar el balance entre rapidez y profundidad es ahora `reasoning.effort` con valores `low`, `medium`, `high`. Para estimación, `medium` es el punto razonable: `low` produce estimaciones superficiales sin profundizar en el razonamiento, `high` aumenta latencia y coste sin mejora medible para este caso.

## **Validación post-generación: cerrar el bucle**

El structured output garantiza que la salida tiene la forma correcta — los campos están todos, los tipos son los esperados, los `Literal` están dentro de sus valores válidos. Lo que no garantiza es la **coherencia semántica** entre la salida y los chunks recuperados. La validación post-generación cubre exactamente eso.

La verificación crítica son las **citaciones**. El modelo, incluso con instrucciones claras, ocasionalmente cita un `source_id` que no estaba entre los chunks recuperados. La causa puede ser un fallo de atención, una confusión entre IDs similares, o una alucinación explícita. Sea cual sea, la validación es trivial y no es opcional:

```python
def validate_citations(estimate: Estimate, retrieved_chunks: list[RetrievedChunk]) -> list[int]:
    valid_ids = {c.id for c in retrieved_chunks}
    cited_ids = set()
    cited_ids.update(c.source_id for c in estimate.sources)
    for component in estimate.cost_breakdown:
        cited_ids.update(component.sources)
    return sorted(cited_ids - valid_ids)
```

Si `validate_citations` devuelve una lista no vacía, el orquestador tiene tres opciones operativas. La primera es **reintentar** la generación con un mensaje adicional del estilo "your previous response cited invalid source ids: ..."; suele funcionar y es la opción por defecto. La segunda es **degradar la confianza** automáticamente (si el modelo dijo `confidence="high"` pero inventó una cita, bajar a `medium` y anotar el incidente). La tercera es **rechazar la respuesta** y devolver al backend de negocio un mensaje de "estimación no fiable, requiere revisión manual". El programa adopta la primera por defecto con un máximo de un reintento; si el segundo intento también cita IDs inválidos, se cae a la tercera opción.

La segunda validación es la **coherencia de confidence**: si el modelo dijo `confidence="insufficient"`, el campo `insufficient_context_explanation` debe estar presente y no vacío; los campos numéricos (`total_engineer_days`, `duration_weeks`) deben ser `None`. Cualquier inconsistencia (decir "insufficient" pero rellenar números, o decir "high" sin citar fuentes) se trata como respuesta malformada y se reintenta. La tercera es de **sanidad numérica**: una estimación de cien mil días-ingeniero o de tres semanas para un proyecto B2B complejo es probablemente un fallo, y el sistema marca esos casos para revisión sin bloquear la respuesta — la sanidad ayuda al humano que revise, no es un guardarraíl absoluto.

![art_4_figura-12-pipeline-validacion.jpg](https://media1-production-mightynetworks.imgix.net/asset/25436eb6-104f-4d45-aa07-71266cfe7485/art_4_figura-12-pipeline-validacion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Trade-offs honestos**

El control de la "creatividad" del modelo merece un párrafo dedicado porque la intuición de muchos ingenieros sigue pidiendo bajar `temperature` a cero y el parámetro ya no existe en gpt-5. En reasoning models, el efecto equivalente — respuestas más deterministas, menos variación entre llamadas — se obtiene con `reasoning.effort` bajo combinado con prompts muy restrictivos. La verdad operativa es que con un prompt bien estructurado y structured output schema strict, la variabilidad inter-llamadas es ya muy baja sin tocar parámetros: el modelo está restringido por la forma de salida y por las reglas del system prompt, y eso le quita la mayor parte de los grados de libertad que en chat libre producirían respuestas distintas.

La pregunta de **instrucción estricta vs flexible** vuelve a la asimetría de errores que estructuró el Artículo 3. El system prompt actual es severo: "ONLY del contexto", "never invent", "return insufficient if needed". Esa severidad tiene un coste — el modelo a veces se niega a estimar cuando un humano sí habría podido extrapolar razonablemente — pero el ahorro en alucinaciones lo compensa. La alternativa flexible ("use the context as primary reference but you may extrapolate when reasonable") produce más cobertura aparente y mucha menos confiabilidad real. Para un sistema cuyo output va a influir en presupuestos de proyecto, severo es mejor que cómplice.

El **coste de las citaciones obligatorias** es medible y vale la pena nombrarlo. Forzar al modelo a citar cada componente cuantitativo aumenta los tokens de salida entre un 10% y un 20% — cada `SourceCitation` es entre cinco y diez tokens, y un breakdown de diez componentes con citas duplica fácilmente el tamaño de la respuesta versus uno sin citar. Sobre miles de peticiones al mes, el coste no es despreciable. Pero la trazabilidad que las citas habilitan es lo que distingue una estimación "que el sistema produjo" de una "que el sistema puede defender", y para estimación financiera esa distinción es operativamente crítica.

## **Conexión con la sesión en vivo**

El quinto bloque de la sesión es una iteración sobre el prompt de generación. Vamos a partir del prompt mínimo (concatenación raw, sin reglas) y a añadir restricciones de una en una, observando cómo cambia la salida sobre la misma transcripción y los mismos chunks. Primero solo delimitadores XML sin instrucciones especiales: la salida empieza a tener forma. Luego el grounding explícito ("ONLY"): las alucinaciones de conocimiento general desaparecen. Luego la obligación de citar: las atribuciones aparecen pero algunas son inventadas. Luego la política de insuficiencia: el modelo deja de forzar estimaciones cuando el contexto no da. Cada paso del experimento es observable en la salida y aprovecha que el alumno tiene el flujo end-to-end ya montado.

Hay también una demo deliberada del fenómeno lost-in-the-middle. Vamos a coger el mismo set de cinco chunks y a generar la estimación con dos órdenes distintos: most-relevant-first y un orden adverso donde el chunk crítico está en posición tres. La diferencia en la estimación resultante es visible — a veces el modelo simplemente no usa el chunk crítico — y el ejercicio sirve para interiorizar que el orden del contexto no es neutral, sino parte del diseño del prompt.

Lo que cierra este artículo y lleva al siguiente es una observación arquitectónica. Hasta aquí, todo lo que hemos construido en S09 — reformulador, retriever, ensamblador, generador — vive en un solo proceso Python. Es lo que se pide para llegar al MVP, pero deja al sistema con un problema operativo: el retriever (que la S10 va a evolucionar con reranking) y el generador (que el negocio va a pulsar miles de veces al día) viven detrás del mismo endpoint, con la misma autenticación, con el mismo rate limit, en el mismo proceso. El Artículo 5 separa esas dos capas en routers distintos del servicio IA, les da régimenes de seguridad y rate limiting diferentes, y conecta el patrón con la forma en que el backend de negocio en Rails va a invocar el servicio IA en producción.