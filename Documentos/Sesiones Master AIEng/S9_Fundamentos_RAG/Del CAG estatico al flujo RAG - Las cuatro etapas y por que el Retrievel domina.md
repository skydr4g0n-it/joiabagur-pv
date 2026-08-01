# Del CAG estático al flujo RAG: las cuatro etapas y por qué el retrieval domina

Creada: 15 de junio de 2026 12:55
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S9. Fundamentos de RAG y técnicas de recuperación (https://app.notion.com/p/S9-Fundamentos-de-RAG-y-t-cnicas-de-recuperaci-n-380ea9ca03c480268ac0c4739784b444?pvs=21)

El sistema que cerraste en la Sesión 05 funciona razonablemente bien hasta un punto concreto. Ese punto tiene nombre: los presupuestos que estaban en tu system prompt cuando montaste el CAG. Mientras una nueva transcripción describa proyectos parecidos a los que viste cuando seleccionaste el contexto estático, el modelo produce estimaciones decentes apoyándose en esos ejemplos. La calidad cae bruscamente en cuanto el cliente menciona algo que tu prompt no cubre.

Imagina que recibes una transcripción donde el cliente dice "necesito algo tipo Stripe Connect pero adaptado a marketplaces sanitarios en Alemania, con KYC reforzado por la BaFin y conciliación contable contra SAP". Tu CAG, con los 30 presupuestos que metiste en el system prompt cuando montaste el Módulo 2, probablemente no tiene ningún proyecto similar. El modelo hará una de dos cosas: o se inventará una estimación apoyándose en su conocimiento paramétrico genérico, o producirá un número razonable pero sin fundamento real en datos de tu empresa. Ambos resultados son inaceptables para un sistema cuya razón de ser es estimar **basándose en presupuestos históricos reales**.

El problema no es del modelo. El problema es que el conocimiento del sistema está congelado en el momento en que montaste el prompt. Si tu empresa cierra cinco proyectos nuevos esta semana en sectores que no estaban representados, el sistema no se entera hasta que rehagas el system prompt y redespliegues. Si tienes 800 presupuestos históricos y solo 30 caben razonablemente en contexto, los otros 770 están fuera del alcance del modelo para siempre.

La salida a ese techo es cambiar la pregunta arquitectónica. En lugar de "qué presupuestos meto en el prompt para que el modelo siempre tenga referencias", la pregunta pasa a ser "cómo encuentro, en el momento de la petición, los presupuestos más relevantes para la transcripción que acabo de recibir, y se los doy al modelo". Eso es el flujo RAG. Y como cualquier cambio arquitectónico no trivial, viene con un coste: cuatro etapas, cuatro puntos de fallo, cuatro lugares donde la calidad puede degradarse. Este artículo desmonta esas cuatro etapas y explica por qué la primera lección operativa del módulo es que el retrieval domina sobre todo lo demás.

## **La anatomía del flujo RAG**

El patrón RAG tiene cuatro etapas canónicas: Query, Retrieval, Augmentation y Generation. La nomenclatura es la que estableció el paper original de Lewis et al. en 2020, y desde entonces ha aguantado sin cambios significativos a pesar de las múltiples variantes que han aparecido (Agentic RAG, GraphRAG, Self-RAG y compañía). Toda variante moderna es una sofisticación de alguna de estas cuatro etapas, no una reorganización del flujo.

**La etapa Query** convierte la entrada del usuario en algo que el sistema de búsqueda pueda usar. Esto es menos trivial de lo que suena. En un sistema RAG didáctico de manual, "la query" es la pregunta del usuario tal cual, y la conversión es solo embeber esa pregunta en el mismo espacio vectorial donde están los chunks. En tu proyecto la entrada es una transcripción de varios miles de tokens con ruido conversacional, divagaciones, anáforas y una mezcla de temas. Embeber eso directamente y comparar contra chunks de 300 tokens produce vectores que están "en algún lugar promediado" del espacio semántico y que apenas discriminan entre los presupuestos históricos. La etapa Query, en sistemas RAG serios, hace trabajo real: extrae los requisitos clave de la transcripción, descompone si hay múltiples sub-temas, genera consultas optimizadas para la búsqueda semántica. Volvemos a esto en el Artículo 2.

**La etapa Retrieval** es donde tu base vectorial entra en juego. Recibe una o varias queries optimizadas y devuelve los chunks más relevantes del corpus. El sistema que dejaste construido al cierre de la Sesión 08 ya hace esto, pero en su versión más naive: top-K por similitud coseno, sin filtros, sin umbral de relevancia. En producción, el retrieval real combina similitud vectorial con filtros estructurales (sector, año, rango de coste), umbrales que descartan resultados poco relevantes, y eventualmente reranking con cross-encoders para refinar el orden — esto último llega en la Sesión 10. El detalle clave es que esta etapa es la que más impacto tiene en la calidad final del sistema. Lo profundizamos en el Artículo 3.

**La etapa Augmentation** ensambla los chunks recuperados en un bloque de contexto que el LLM pueda usar bien. El reflejo ingenuo es concatenar los chunks con un separador y meterlos en el prompt. Y es exactamente lo que produce alucinaciones, citas inventadas o respuestas que ignoran el contexto. La etapa Augmentation, hecha bien, decide en qué orden van los chunks (mitigando el fenómeno "lost in the middle"), qué delimitadores usa para que el modelo distinga las fuentes, cómo trunca cuando el contexto excede el presupuesto de tokens, y qué metadata acompaña cada chunk para permitir citación. El Artículo 4 entra al detalle.

**La etapa Generation** es la llamada al LLM con el contexto ya ensamblado y un prompt que instruye al modelo sobre cómo usarlo. Aquí también la diferencia entre un RAG funcional y uno serio está en los detalles: el prompt debe forzar grounding ("usa solo el contexto proporcionado, no tu conocimiento general"), debe definir el comportamiento cuando el contexto es insuficiente ("si no tienes evidencia suficiente, dilo, no inventes"), debe especificar el formato de salida (JSON con la estimación, las fuentes citadas, los supuestos asumidos, la confianza estimada), y debe permitir la validación posterior de las citaciones para detectar alucinaciones. El Artículo 4 lo cierra junto con Augmentation.

Las cuatro etapas se encadenan formando un pipeline. En código, el orquestador del flujo se ve aproximadamente así:

```python
async def estimate_from_transcript(transcript: str) -> EstimateResponse:
    structured_query = await query_reformulator.reformulate(transcript)
    chunks = await retriever.search(
        query=structured_query,
        top_k=10,
        threshold=0.65,
        filters=structured_query.metadata_filters,
    )
    context = context_assembler.assemble(chunks, max_tokens=4000)
    estimate = await generator.generate(
        transcript=transcript,
        context=context,
        schema=EstimateSchema,
    )
    return estimate
```

Cinco líneas operativas. Cada una de ellas es un punto de fallo, una decisión de diseño, una fuente potencial de degradación de calidad. La complejidad del módulo entero está, esencialmente, en hacer que cada una de esas cinco llamadas sea robusta, observable y mejorable independientemente.

![art_1_figura-1-anatomia-flujo-rag.jpg](https://media1-production-mightynetworks.imgix.net/asset/37533830-b1e8-42d3-bd77-d493bae3e6cf/art_1_figura-1-anatomia-flujo-rag.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Sobre el servicio IA, este pipeline introduce dos módulos nuevos respecto al estado en que quedó al cierre de la Sesión 08. La carpeta `retrieval/` aloja `query_reformulator.py` y `retriever.py`. La carpeta `generation/` aloja `context_assembler.py`, `prompt_builder.py` y `estimator.py` (este último es el orquestador del fragmento anterior). Los módulos existentes — `ingest/` desde la Sesión 06, `embedding_pipeline/` desde la Sesión 07, `storage/` desde la Sesión 08 — no se tocan; quedan como dependencias estables que las nuevas piezas consumen. Esa separación no es estética: hace que el retriever pueda evolucionar en la Sesión 10 introduciendo reranking sin tocar el módulo de generación, y al revés.

![art_1_figura-2-modulos-servicio-ia.jpg](https://media1-production-mightynetworks.imgix.net/asset/dd32f857-f326-4dab-afe2-6e8d8040ec0e/art_1_figura-2-modulos-servicio-ia.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **La diferencia operativa con el CAG del Módulo 2**

Cuando un alumno ve por primera vez el contraste entre CAG y RAG, el reflejo es pensar que la diferencia está en el "tamaño" del contexto: CAG mete los presupuestos en el system prompt una vez, RAG los selecciona dinámicamente cada petición. Eso es verdad pero es la punta del iceberg. Las diferencias operativas que importan son cinco, y cada una tiene implicaciones medibles sobre el sistema que vas a construir.

La primera es la **frescura del conocimiento**. En CAG, añadir un nuevo presupuesto histórico al sistema requiere editar el system prompt, validar que no rompe la caché de prompts del proveedor, y redesplegar. En RAG, añadir un presupuesto es un `POST /v1/retrieval/insert` que el backend de negocio puede llamar cuando se cierre una nueva venta. El sistema queda sincronizado en minutos sin tocar código ni servicio. Esta diferencia es la que justifica RAG por sí sola en cualquier empresa que cierre proyectos con regularidad: el sistema deja de envejecer con el tiempo.

La segunda es el **techo del corpus**. CAG está limitado por el tamaño del contexto del modelo. Con `gpt-5` y sus 400.000 tokens, puedes meter bastantes presupuestos, pero si tu empresa tiene 800 proyectos históricos con un promedio de 3.000 tokens cada uno, el corpus completo son 2,4 millones de tokens; ni los modelos más generosos te permiten meter todo. RAG no tiene ese techo: el corpus crece tanto como quieras y solo subes al modelo los chunks relevantes. El sistema escala con tu empresa, no con el modelo.

La tercera es la **latencia y el coste por petición**. Aquí RAG **pierde**, y es importante reconocerlo abiertamente. CAG hace una sola llamada al LLM con un prompt estático que se beneficia de prompt caching agresivo en OpenAI o Anthropic; la latencia es de un segundo o dos y el coste es bajo. RAG hace, en el flujo mínimo, una llamada al LLM para la reformulación, una al servicio de embeddings, una consulta a pgvector, y una llamada final al LLM para la generación; la latencia se acumula y el coste por petición puede ser tres o cuatro veces el de CAG. Si tu volumen de peticiones es alto y tu corpus es estable, eso no es trivial. Si tu volumen es bajo o moderado y la calidad importa más, es un coste que merece la pena pagar. La decisión depende del caso, no del prestigio del patrón.

La cuarta es la **trazabilidad y la auditoría**. Si un cliente cuestiona una estimación que tu sistema produjo hace tres meses, en CAG no tienes forma de explicar de dónde salió ese número: el modelo se apoyó en algún subconjunto difuso del system prompt mezclado con su conocimiento paramétrico, y nadie sabe en qué proporción. En RAG puedes responder con precisión: estos son los presupuestos históricos que se recuperaron, este es el contexto que se montó, esta es la estimación que se generó. Si tu sistema tiene que responder a auditorías, a clientes técnicos exigentes, o a regulación, esta diferencia es decisiva.

La quinta es la **resistencia a la alucinación**. Cuando le pides a un LLM una estimación apoyada en datos que no están en su contexto, el modelo rellena los huecos. CAG, aunque sus datos sí están en contexto, no fuerza al modelo a apoyarse en ellos: nada en el prompt impide al modelo ignorar los presupuestos del system prompt y producir un número de su propia cosecha. RAG, con un prompt de generación bien construido (instrucción explícita de "usa solo el contexto proporcionado, cita las fuentes, declara cuando la evidencia sea insuficiente"), reduce drásticamente la tasa de alucinación. No la elimina; la reduce de forma medible y reproducible.

Estas cinco diferencias se resumen en una idea: CAG es el sistema que asume que el contexto correcto está siempre disponible porque tú lo has elegido por adelantado; RAG es el sistema que asume que el contexto correcto hay que ir a buscarlo cada vez y que esa búsqueda es el corazón del sistema. La asunción de RAG es más robusta a la realidad pero pone más complejidad en la arquitectura. No hay almuerzo gratis.

![art_1_figura-3-comparativa-cag-rag.jpg](https://media1-production-mightynetworks.imgix.net/asset/7afb7adf-7448-4676-bdab-4b20912fef46/art_1_figura-3-comparativa-cag-rag.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Cuándo CAG sigue siendo la respuesta correcta**

Antes de seguir, conviene matizar una afirmación que late bajo todo lo anterior y que en la literatura industrial está mal contada: que RAG es "mejor" que CAG. No lo es. Es **distinto** y aplica a problemas distintos.

El paper que conviene leer aquí es "Don't Do RAG: When Cache-Augmented Generation is All You Need for Knowledge Tasks" de Chan et al. (2024), que demostró empíricamente que cuando el corpus es pequeño y estable, CAG no solo es más simple sino que produce mejores respuestas en métricas estándar de QA. La razón es intuitiva: en CAG el modelo "ve" todo el corpus en una sola atención completa; en RAG el modelo ve un subconjunto seleccionado por un retriever que puede equivocarse. Cuando el coste del error del retriever es alto y el corpus cabe en contexto, CAG gana.

Para tu proyecto en particular, RAG está justificado porque el corpus de presupuestos históricos de una empresa de software seria crece con el tiempo y no cabe completo en contexto. Pero en otras decisiones de arquitectura que vas a tomar fuera del programa, conviene tener este matiz claro: CAG es perfectamente respetable para corpus de menos de 100.000 tokens efectivos, estables, donde el coste por petición importa y la trazabilidad no es crítica. Sistemas internos de soporte basados en una FAQ de empresa, asistentes técnicos sobre documentación de producto que cambia poco, herramientas legales sobre un cuerpo normativo fijo. Hay productos serios en producción que son CAG y deben serlo.

Existe también una tercera vía que merece mención: los sistemas híbridos CAG + RAG, donde el contexto base estable (políticas, terminología, estructura del dominio) va por CAG y el contexto variable (datos específicos del caso) va por RAG. El paper de Chan et al. lo menciona como dirección futura y es razonable; en tu proyecto, las plantillas de salida JSON, las reglas de coherencia entre componentes de un presupuesto, y la terminología técnica del dominio podrían ir como CAG en el system prompt mientras los presupuestos históricos similares se recuperan por RAG. No es lo que vamos a construir en este módulo — la complejidad añadida no se justifica para el alcance del programa — pero es el siguiente paso natural si quieres optimizar más adelante.

## **El retrieval domina**

Hay un mantra en la literatura industrial de RAG en 2025 y 2026 que vale la pena interiorizar antes de seguir: "no amount of prompt engineering fixes bad retrieval". Aparece en blogs técnicos, en post-mortems de proyectos fallidos, en charlas de conferencia. La razón por la que se ha vuelto consigna no es porque suene bien sino porque describe el modo de fallo más común en sistemas RAG en producción.

La intuición es la siguiente. Si tu retrieval devuelve los chunks correctos, incluso un prompt de generación mediocre produce respuestas decentes: el modelo tiene evidencia delante y la usa. Si tu retrieval devuelve chunks irrelevantes, ningún prompt de generación, por sofisticado que sea, te va a salvar: el modelo no puede inventar evidencia que no tiene, y si le obligas a apoyarse solo en el contexto, responderá "no tengo suficiente información". El techo de calidad del sistema entero está fijado por la calidad del retrieval. Las otras tres etapas pueden empujarte hacia ese techo, pero no por encima de él.

La consecuencia operativa es que el orden de prioridades cuando un sistema RAG falla es siempre el mismo. Primero, ¿estoy recuperando los chunks correctos? Si la respuesta es no, todo lo demás es ruido. Segundo, ¿estoy ensamblando bien el contexto? Si los chunks correctos llegan al LLM pero los está ignorando, mira la etapa Augmentation. Tercero, ¿el prompt de generación fuerza grounding adecuadamente? Y solo en último lugar, ¿el modelo es lo suficientemente capaz? La tentación de empezar por el modelo es fuerte y casi siempre equivocada.

Esto no significa que las otras etapas no importen — importan, y los Artículos 4 y 5 entran a fondo en Augmentation y Generation. Significa que la ingeniería de retrieval es donde está el palanqueo. Y por eso este módulo dedica el resto de las sesiones (10 sobre técnicas de recuperación, 11 sobre evaluación) a hacer cada vez mejor esa etapa.

## **Conexión con la sesión en vivo**

En el primer bloque de la sesión vamos a correr la misma transcripción ambigua por dos sistemas: el CAG que cerraste en la Sesión 05 y un esqueleto del RAG que construirás durante el módulo. Los dos producirán una estimación. Mediremos cuatro cosas: la respuesta producida (¿es coherente con los datos disponibles?), la latencia total, el coste en tokens, y la trazabilidad (¿puedes explicar de dónde salen los números?). Los resultados de cada alumno van a divergir bastante porque cada uno habrá cerrado el CAG con presupuestos distintos en el prompt; esa divergencia es exactamente lo que abre la conversación sobre cuándo el patrón RAG empieza a justificarse.

Si has hecho ya el ejercicio pre-sesión, llegarás con el trace de la transcripción ambigua sobre tu sistema actual y con los cinco fallos identificados. Algunos de esos fallos van a mapear directamente a una de las cuatro etapas que acabas de leer: la query cruda no recupera bien (etapa Query), los chunks devueltos son irrelevantes o están mezclados (etapa Retrieval), la concatenación naive del contexto produce respuestas pobres (etapa Augmentation), el modelo inventa o no cita (etapa Generation). Llegar con esa correspondencia mental hecha vale más que cualquier explicación que pueda darte en directo. El resto del módulo es, esencialmente, atacar esas cuatro etapas una por una hasta que el sistema haga lo que el proyecto le pide desde la primera sesión: estimar basándose en los presupuestos reales de la empresa, no en la intuición del modelo.