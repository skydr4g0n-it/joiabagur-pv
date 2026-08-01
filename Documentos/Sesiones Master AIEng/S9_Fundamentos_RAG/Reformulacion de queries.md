# Reformulación de queries

Creada: 15 de junio de 2026 12:57
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S9. Fundamentos de RAG y técnicas de recuperación (https://app.notion.com/p/S9-Fundamentos-de-RAG-y-t-cnicas-de-recuperaci-n-380ea9ca03c480268ac0c4739784b444?pvs=21)

Tienes ya un servicio IA que sabe embeber texto y buscar chunks similares. La tentación, cuando aterriza la primera transcripción de reunión real, es la más sencilla del mundo: embeber esa transcripción y pasársela al endpoint de búsqueda de la Sesión 08. Si tanto cuidado hemos puesto en chunkear bien los presupuestos y en mantener la dimensionalidad del espacio vectorial, ¿no debería bastar?

![art_2_figura-6-impacto-espacio-vectorial.jpg](https://media1-production-mightynetworks.imgix.net/asset/93519b87-1750-4bbf-ab61-753b09ddfa5b/art_2_figura-6-impacto-espacio-vectorial.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

No basta. Y la razón no es ningún misterio profundo del álgebra de altas dimensiones; es algo mucho más mundano. La transcripción que el cliente acaba de pasarte por la videollamada se parece a esto:

> Pues mira, lo que hablábamos el otro día. Necesitamos algo que junte a los proveedores con los compradores en lo nuestro, ¿no? No es un Amazon ni nada, es más como Stripe Connect pero adaptado. Cada proveedor con su panel, sus comisiones, KYC porque movemos dinero entre cuentas... el sector es salud, vamos a empezar con dos clínicas piloto en Múnich así que toca la BaFin. Y la conciliación con SAP es no negociable, lo tienen montado todo ahí. ¿Cuánto nos sale esto y por dónde empezamos?
> 

Esto no es una query. Es la transcripción condensada de cinco minutos de conversación que en una reunión real iría dentro de un torrente de tres mil tokens donde el cliente también habla de su CTO anterior, del retraso del proyecto pasado, de un curso de gestión que hizo el verano pasado, y de su perro. Y aun en este fragmento sin ruido conversacional pasan tres cosas que rompen la búsqueda vectorial.

Primero, **la longitud disuelve la señal**. Tu base vectorial contiene chunks de unos trescientos tokens, cada uno describiendo un componente concreto de un presupuesto histórico. El embedding de un chunk de trescientos tokens vive en una región muy específica del espacio: este componente trata de "integración OAuth para fintech B2B" y su vector apunta hacia esa región. Cuando metes en el mismo embedder dos mil tokens con cinco temas mezclados, el vector resultante es algo así como el centroide de cinco regiones distintas: un punto que está "en medio de todas" y cerca de ninguna. Las distancias coseno a tus chunks históricos se comprimen alrededor de un valor medio mediocre y el sistema no distingue lo crítico de lo periférico.

Segundo, **el ruido conversacional ahoga las keywords técnicas**. En el ejemplo de arriba, las palabras clave operativas para discriminar el proyecto — "marketplace", "Stripe Connect", "KYC", "BaFin", "SAP", "salud", "piloto" — están enterradas entre conectores y expresiones coloquiales ("pues mira", "lo nuestro", "no es un Amazon", "no negociable"). El modelo de embeddings no sabe que esas siete palabras son las que importan; las trata como tokens más entre el flujo conversacional. El resultado es un vector que se parece más al promedio de cualquier reunión comercial que a la región específica de "fintech B2B con KYC para salud".

Tercero, **las anáforas no significan nada para el modelo de embeddings**. Cuando el cliente dice "lo que hablábamos el otro día", "lo nuestro" o "como me decíais", está apoyándose en contexto que no está en la transcripción. Tu sistema, que no asistió a la conversación previa, no tiene cómo resolver esas referencias. El embedder simplemente codifica las palabras como si fueran contenido informativo, contaminando el vector con señal que no remite a nada.

La conclusión operativa es directa: necesitas una capa que convierta la transcripción en algo que el retriever pueda usar. Esa capa se llama reformulación de queries, y es la pieza que más impacto tiene en el recall del sistema porque, sin ella, ningún ajuste de top-K, ningún threshold, ningún reranker te va a salvar de la entrada degradada que estás metiendo al retriever.

## **Las cinco familias de reformulación**

La literatura industrial agrupa las técnicas de reformulación en cinco familias razonablemente bien delimitadas. Cada una resuelve un subconjunto de los problemas anteriores y cada una tiene su precio. Conviene conocerlas todas antes de elegir.

**Query rewriting** es la más sencilla. Le pasas la entrada al LLM con la instrucción "reformula esto como una consulta técnica concisa y específica para buscar en una base de datos de presupuestos de software". El modelo produce algo como "marketplace B2B con pagos KYC para sector salud en Alemania, integración SAP". Embebes esa salida y buscas. La técnica funciona razonablemente bien cuando la entrada es corta pero mal formulada, y razonablemente mal cuando la entrada es larga y multi-tema porque pierdes información en la compresión arbitraria que el modelo hace.

**Sub-query decomposition** ataca el problema de los temas mezclados desbordando hacia varias búsquedas. El LLM analiza la entrada y produce un listado de sub-queries, cada una orientada a un sub-tema. Para la transcripción de arriba serían algo como "marketplace B2B con onboarding de proveedores y comisiones", "integración de pagos con KYC y compliance fintech", "conciliación contable con SAP", "regulación BaFin para sector salud en Alemania". Cada sub-query se ejecuta independientemente contra el retriever, recuperando sus propios chunks; al final se fusionan los resultados — típicamente con Reciprocal Rank Fusion — antes de pasar al augmentation. El recall mejora notablemente porque cada sub-tema tiene su propio "haz" semántico. El coste también: cuatro búsquedas en lugar de una, cuatro embeddings, y la complejidad añadida de fusionar resultados que pueden ser contradictorios.

**Step-back prompting** sube un nivel de abstracción antes de buscar. En lugar de embeber lo específico, el LLM genera una pregunta más general — "qué tipo de proyectos de plataforma fintech han tenido históricamente clientes empresariales en sectores regulados" — y se busca con esa pregunta. La idea es que las preguntas demasiado específicas a veces no recuperan bien porque ningún chunk individual cubre la combinación exacta de requisitos; subir un nivel encuentra chunks que sí cubren los conceptos relevantes aunque a otra granularidad. En la práctica, step-back es una técnica que brilla en QA sobre conocimiento estructurado (Wikipedia, textos técnicos) y rinde peor en dominios narrow como el de estimaciones de software donde el "concepto general" del que partir es difuso. La técnica existe y es válida en otros contextos; en este programa apenas la tocaremos.

**HyDE (Hypothetical Document Embeddings)** invierte el problema de forma elegante. En lugar de embeber la pregunta, le pide al LLM que genere una **respuesta hipotética** — un documento ficticio que se parecería a la respuesta correcta si existiera — y embebe esa respuesta. Para nuestra transcripción, el LLM produciría algo como "Este proyecto consiste en una plataforma de pagos marketplace orientada a proveedores sanitarios alemanes. Incluye autenticación con KYC reforzado, orquestación de pagos vía Stripe Connect, conciliación contable bidireccional con SAP S/4HANA, y cumplimiento con BaFin para fintech". Embebes ese documento sintético y buscas. El insight crítico de HyDE es que tu base vectorial contiene documentos descriptivos (descripciones de componentes de presupuestos pasados), y un documento sintético se parece más a otros documentos en el espacio vectorial que una pregunta corta. Funciona muy bien cuando el dominio es estable y conocido por el modelo — y peor cuando el modelo alucina tecnologías que tu empresa no ha usado nunca.

**Extracción estructurada** es la quinta vía y la que el programa va a elegir por defecto. En lugar de pedir al LLM un texto reformulado o un documento sintético, le pides un **objeto estructurado**: un JSON validable contra un esquema explícito, con campos para función principal, tecnologías mencionadas, sector, escala, geografía, regulaciones, y restricciones. Para la transcripción de arriba la salida sería un objeto con `function = "B2B payments marketplace platform"`, `technologies = ["Stripe Connect", "KYC", "SAP"]`, `sector = "healthcare"`, `scale = "pilot"`, `country = "Germany"`, `regulations = ["BaFin"]`. Ese objeto se usa de dos maneras: sus campos textuales se componen en un texto sintético que se embebe (similar a HyDE pero más controlado), y sus campos categóricos se usan como filtros de metadata en pgvector — algo que las otras cuatro técnicas no permiten porque no producen estructura aprovechable downstream.

## **La elección del programa: extracción estructurada**

La razón por la que el programa elige extracción estructurada no es que sea la más sofisticada — HyDE produce vectores ligeramente mejores en benchmarks académicos puros — sino que es la que mejor balance ofrece entre cuatro dimensiones que importan en producción: **predictibilidad de coste**, **predictibilidad de latencia**, **debugabilidad**, y **utilidad downstream**.

En coste y latencia, extracción estructurada y HyDE son comparables: ambas requieren una sola llamada al LLM antes de la búsqueda. HyDE genera un documento de 200-400 tokens, extracción genera un JSON de 50-100 tokens; la diferencia en output tokens es pequeña pero consistentemente a favor de extracción. En query rewriting el output es aún más corto pero la pérdida de información es mayor. Sub-query es la opción más cara: una llamada para descomponer más N llamadas al retriever, donde N puede ser 3-5.

En debugabilidad, extracción estructurada es la única que produce un artefacto inspectable. Cuando una estimación es mala, puedes mirar el JSON intermedio y ver si el reformulador entendió mal el sector, si se le escapó una tecnología clave, o si interpretó "piloto" como escala "small" en lugar de "pilot". Con query rewriting tienes que adivinar qué entendió el modelo a partir del texto reformulado; con HyDE tienes que leer un documento sintético que mezcla extracción con generación.

En utilidad downstream, extracción estructurada gana sin discusión. El JSON no solo sirve para componer la query embebida, también alimenta los filtros de metadata del retriever. Si el cliente menciona "sector salud", la búsqueda no solo se concentra semánticamente en presupuestos similares; también se restringe estructuralmente a chunks marcados con `sector = "healthcare"`. Eso es información que se pierde en cualquier otra técnica.

En el servicio IA, el componente que ejecuta esta reformulación es `retrieval/query_reformulator.py`. El esquema canónico del proyecto se define en Pydantic:

```python
from pydantic import BaseModel, Field
from typing import Literal

class EstimationQuery(BaseModel):
    function: str = Field(description="Primary product function in 3-7 words")
    technologies: list[str] = Field(
        default_factory=list,
        description="Specific technologies, services, or integrations mentioned"
    )
    sector: str | None = Field(
        default=None,
        description="Industry or vertical if explicitly mentioned"
    )
    scale: Literal["pilot", "small", "medium", "large"] | None = Field(
        default=None,
        description="Project scale if inferable from the conversation"
    )
    country: str | None = Field(
        default=None,
        description="Geographic scope if mentioned"
    )
    regulations: list[str] = Field(
        default_factory=list,
        description="Regulatory frameworks mentioned (GDPR, BaFin, HIPAA, etc.)"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Non-negotiable requirements or hard constraints"
    )
```

La llamada al modelo usa la Responses API de OpenAI con `text.format` estricto para que el modelo no se desvíe del esquema:

```python
async def reformulate(transcript: str) -> EstimationQuery:
    response = await client.responses.create(
        model="gpt-5-mini",
        input=[
            {
                "role": "system",
                "content": REFORMULATION_SYSTEM_PROMPT,
            },
            {"role": "user", "content": transcript},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "EstimationQuery",
                "schema": EstimationQuery.model_json_schema(),
                "strict": True,
            }
        },
    )
    return EstimationQuery.model_validate_json(response.output_text)
```

El system prompt instruye al modelo a extraer solo lo que esté explícitamente mencionado o inequívocamente inferible, y a dejar campos opcionales en `null` cuando no haya evidencia suficiente. La tentación de "rellenar" con sentido común — inferir GDPR porque hay datos personales, inferir Stripe porque hay pagos — es la fuente principal de errores en producción, y conviene reprimirla explícitamente en el prompt.

El objeto validado se compone después en un texto sintético compacto que es lo que efectivamente se embebe y se pasa al retriever:

![art_2_figura-5-flujo-reformulacion-fallback.jpg](https://media1-production-mightynetworks.imgix.net/asset/facc140b-3d76-4a3b-bfd4-5e5e9eaee458/art_2_figura-5-flujo-reformulacion-fallback.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

```python
def compose_search_text(q: EstimationQuery) -> str:
    parts = [q.function]
    if q.technologies:
        parts.append(f"with {', '.join(q.technologies)}")
    if q.sector:
        parts.append(f"for the {q.sector} sector")
    if q.country:
        parts.append(f"in {q.country}")
    if q.regulations:
        parts.append(f"compliant with {', '.join(q.regulations)}")
    if q.constraints:
        parts.append(f"requiring {', '.join(q.constraints)}")
    return ". ".join(parts) + "."
```

Para la transcripción de arriba, esto produce:

> "B2B payments marketplace platform. with Stripe Connect, KYC, SAP. for the healthcare sector. in Germany. compliant with BaFin. requiring SAP reconciliation."
> 

Compárese ese texto con la transcripción cruda. El vector embebido a partir de él vive cerca de la región donde están los chunks de presupuestos históricos de plataformas fintech B2B para sectores regulados, en lugar de en el centroide difuso de la reunión completa. La diferencia en el recall del retriever sobre la misma base vectorial es típicamente entre dos y cinco veces, dependiendo del corpus.

Hay un patrón de fallback que conviene mencionar y dejar implementado. Cuando la validación del JSON falla — porque el modelo produjo algo que no encaja en el esquema o porque la transcripción es genuinamente ambigua — el sistema cae a una versión más simple: query rewriting puro, devolviendo un texto reformulado libre. Es peor que extracción estructurada pero mejor que la transcripción cruda. El fallback debe activarse y registrarse para poder iterar sobre los casos donde la extracción no funciona; si nunca se activa, el reformulador está siendo demasiado tolerante con sus salidas; si se activa más del 5%, hay un problema sistemático con el prompt o con el esquema.

![art_2_figura-4-matriz-tecnicas-reformulacion.jpg](https://media1-production-mightynetworks.imgix.net/asset/7e6fd35f-e23c-4586-b1e4-8122a6367c33/art_2_figura-4-matriz-tecnicas-reformulacion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Trade-offs honestos: cuándo subir a algo más sofisticado**

La decisión por defecto no es la decisión universal. Hay condiciones bajo las cuales conviene subir el coste arquitectónico a otra técnica, y conviene reconocerlas.

**Subir a HyDE** tiene sentido cuando el corpus es muy descriptivo (cada chunk es un párrafo elaborado, no una entrada estructurada) y el modelo conoce bien el dominio. Para un sistema RAG sobre documentación médica o jurídica donde los chunks son texto narrativo, un documento sintético de 300 tokens embebido produce mejores vectores que un texto compuesto de 50 tokens. Para tu sistema de estimaciones de software, donde los chunks son descripciones de componentes presupuestarios con estructura semi-formal, el beneficio es marginal.

**Subir a sub-query decomposition** tiene sentido cuando las transcripciones son consistentemente multi-tema y los temas son ortogonales. Si la mitad de tus transcripciones cubren dos o tres proyectos distintos en la misma conversación, una sola query estructurada va a perder información. En esos casos, decomposición seguida de RRF mejora el recall a costa de duplicar la latencia y el coste. Para el patrón típico — un cliente describe un proyecto con varias dimensiones — la extracción estructurada captura las dimensiones en campos del JSON y rinde mejor que descomponer en sub-queries.

**Subir a una técnica híbrida** — extracción estructurada para el filtrado, HyDE para la búsqueda semántica — es el siguiente paso natural si la calidad del retrieval se queda corta tras unas semanas de uso. Se ejecutan las dos en paralelo: una llamada extrae el JSON para filtros, otra genera el documento hipotético para embedding. El coste se duplica pero el recall puede subir un escalón adicional. Es la trayectoria razonable de evolución del sistema, no la elección inicial.

**Lo que no compensa** es complicar el reformulador antes de medir. La tentación de empezar por HyDE "porque suena mejor en los papers" lleva al mismo sitio que la tentación de empezar por un retriever híbrido o por un reranker: sistemas complejos que son difíciles de depurar cuando fallan y cuyas mejoras marginales no son ni siquiera medibles porque no había una baseline simple contra la que comparar. La regla operativa del módulo es construir la versión más simple del componente, instrumentarla, medir su comportamiento sobre transcripciones reales, y solo entonces decidir si la complejidad adicional se justifica.

## **Conexión con la sesión en vivo**

El bloque central de la sesión es exactamente este: iterar sobre la reformulación. Vamos a coger la misma transcripción ambigua que algunos habréis trabajado en el ejercicio pre-sesión y a contrastar tres caminos sobre ella: el embedding directo de la transcripción cruda como baseline naive, la extracción estructurada que acabas de leer aquí, y HyDE como contraste. Sobre cada uno mediremos cuántos de los chunks recuperados pertenecen efectivamente a presupuestos del sector y geografía correctos, y veremos cómo la calidad del retriever depende de forma casi proporcional a la calidad de la query que le entregamos.

Hay también un debate productivo que vale la pena anticipar. Cuando el modelo produce el JSON, hay decisiones de diseño del prompt que cambian el comportamiento sustancialmente: ¿le permitimos inferir tecnologías no mencionadas explícitamente, o lo forzamos a quedarse solo con lo verbalizado? ¿Marcamos el sector como `null` cuando hay ambigüedad o nos arriesgamos a inferirlo? ¿Aceptamos extraer `scale = "pilot"` de una mención de "dos clínicas piloto" o lo dejamos también en `null`? Estas son las decisiones que separan un reformulador que funciona razonablemente bien en demo del que aguanta el día a día con transcripciones del mundo real, y son la materia del segundo y tercer bloque del directo.

Lo que cierra este artículo es una idea operativa que conviene anclar antes de seguir: la reformulación no es un detalle de implementación del retriever, es una capa con vida propia que merece su prompt versionado, su esquema versionado, su instrumentación propia, y su test suite. Cuando el sistema RAG entre en producción, la mayor parte de las regresiones de calidad van a venir de aquí — del momento en que alguien edita el system prompt del reformulador para arreglar un caso concreto y rompe diez casos que iban bien sin darse cuenta. Esa fragilidad es la contrapartida de poner un LLM en la entrada del sistema, y la disciplina de tratar al reformulador como un componente de primera clase es la que lo mantiene bajo control.