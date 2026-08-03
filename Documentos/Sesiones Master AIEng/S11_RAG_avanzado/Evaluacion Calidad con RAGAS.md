# Evaluación de calidad con RAGAS

Creada: 27 de junio de 2026 12:40
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S11. RAG Avanzado - Generación y Calidad (https://app.notion.com/p/S11-RAG-Avanzado-Generaci-n-y-Calidad-38cea9ca03c48049a493d33b89499a1d?pvs=21)

El sistema de estimaciones ya hace cosas que hace unas semanas parecían difíciles: recupera presupuestos relevantes, sintetiza fuentes que se contradicen, cita de forma verificable, detecta cuando se está inventando una cifra y se abstiene en lugar de mentir. Cada respuesta que produce pasa por guardarraíles que comprueban si esa respuesta concreta es de fiar.

Y sin embargo, hay una pregunta que el sistema no sabe responder sobre sí mismo: ¿es bueno? No "¿es buena esta estimación?", eso lo contestan los guardarraíles, sino "¿es bueno el sistema, y está mejorando o empeorando?". Porque has tomado decenas de decisiones de diseño, el prompt de generación, el modelo, la forma de ensamblar el contexto, el reranker, la versión de embeddings y cada vez que cambias una, no tienes ni idea de si la calidad sube o baja. Cambias el prompt porque "parece mejor", lo despliegas, y descubres semanas después, por una queja, que introdujiste una regresión. Sin medida, cada cambio es una apuesta a ciegas con una venda muy bien puesta.

RAGAS es el marco que quita la venda. Convierte la calidad de un sistema RAG en cuatro números que puedes calcular sobre un conjunto de pruebas y comparar entre versiones. No te dice si una respuesta es verdad, eso es imposible de saber con certeza, pero te dice si la versión de hoy es mejor que la de ayer, y dónde está perdiendo calidad si la pierde.

## **Cuatro métricas que separan recuperación de generación**

RAGAS mide cuatro cosas, y la clave para usarlas bien es entender que dos miden la recuperación y dos miden la generación. Esa división es lo que convierte cuatro números sueltos en un diagnóstico.

**Faithfulness** (fidelidad) mide si la respuesta está fundamentada en el contexto recuperado: qué proporción de las afirmaciones de la estimación se puede inferir de los presupuestos que se recuperaron. Es la versión a escala de la detección de alucinaciones: si el sistema afirma "40 h para pagos" y eso no se deriva de ningún fragmento del contexto, la fidelidad baja. Mide la **generación**.

**Answer Relevancy** (relevancia de la respuesta) mide si la respuesta realmente aborda la pregunta, sin irse por las ramas ni rellenar. Una estimación que contesta sobre componentes que la transcripción no pidió, o que se queda corta respecto a lo que se preguntó, puntúa bajo. Mide la **generación**.

**Context Precision** (precisión del contexto) mide cuántos de los fragmentos recuperados son de verdad relevantes, y si los relevantes están bien posicionados arriba. Es la métrica que evalúa el trabajo del reranker y de la búsqueda: mucho ruido recuperado, o lo bueno enterrado abajo, la hunde. Mide la **recuperación**.

**Context Recall** (exhaustividad del contexto) mide si la recuperación trajo todo el contexto necesario para fundamentar la respuesta de referencia. Si para estimar bien un módulo hacían falta tres presupuestos y solo se recuperaron dos, el recall baja. Mide la **recuperación**, y necesita una respuesta de referencia con la que comparar.

![art6-fig16-cuatro-metricas.jpg](https://media1-production-mightynetworks.imgix.net/asset/f0e029a9-dc34-4d2b-94b9-2ee22d461725/art6-fig16-cuatro-metricas.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La utilidad real aparece cuando lees las cuatro juntas. Si la fidelidad cae pero la precisión y el recall del contexto siguen altos, el problema es de generación: el contexto era bueno y el modelo no lo usó bien. Si la fidelidad es alta pero el recall del contexto es bajo, el modelo se porta bien con lo poco que le llega, pero la recuperación no le está dando lo que necesita. Las métricas no solo te dicen *que* la calidad bajó; te dicen *dónde* mirar.

## **Qué necesita RAGAS, y por qué el golden set es el techo**

Para calcular esas métricas, RAGAS necesita, por cada caso de prueba, cuatro piezas: la pregunta, la respuesta que generó tu sistema, los contextos que recuperó, y una respuesta de referencia (el `ground_truth`, la estimación correcta según un experto). Las dos primeras métricas, fidelidad y relevancia, se calculan sin referencia; las dos del contexto, sobre todo el recall, necesitan ese `ground_truth`.

Y aquí está lo que más se subestima de toda la evaluación: **el golden set es el techo de la calidad de tus métricas**. RAGAS calculará números sobre el conjunto que le des, pero esos números solo valen lo que valga el conjunto. Un golden set pequeño, o sesgado, o con respuestas de referencia mal hechas, produce métricas confiadas y sin sentido. Construirlo bien es la parte difícil, humana, y no automatizable de todo esto.

![art6-fig17-golden-set-techo.jpg](https://media1-production-mightynetworks.imgix.net/asset/af395811-5a5c-4d59-b4a8-0a0b65073539/art6-fig17-golden-set-techo.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Para el caso de estimación, un buen golden set no es una lista de transcripciones fáciles. Es un conjunto representativo que cubre el espectro real de lo que el sistema verá: casos con presupuestos comparables y respuesta clara, casos ambiguos, casos donde las fuentes se contradicen (para comprobar que el sistema entrega un rango y no un número falso), y crucial, casos donde la respuesta correcta es "no hay datos suficientes". Si tu golden set no incluye un caso que debe terminar en abstención, no estás midiendo si tu sistema sabe abstenerse; estás premiando que conteste siempre. Los casos adversariales no son opcionales: son los que distinguen un sistema robusto de uno que solo funciona en el camino feliz.

## **Implementación**

Con el golden set construido, la evaluación es un proceso por lotes que pasa cada caso por el pipeline real y recoge las cuatro piezas que RAGAS necesita.

```python
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

def build_eval_dataset(golden: list[GoldenItem], pipeline) -> Dataset:
    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    for item in golden:
        result = pipeline.run(item.transcript)  # real retrieval + generation
        rows["question"].append(item.question)
        rows["answer"].append(result.answer_text)
        rows["contexts"].append([chunk.content for chunk in result.retrieved_chunks])
        rows["ground_truth"].append(item.ground_truth)
    return Dataset.from_dict(rows)

def run_ragas(golden: list[GoldenItem], pipeline) -> dict[str, float]:
    dataset = build_eval_dataset(golden, pipeline)
    scores = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    log.info("ragas_scores", **scores)
    return scores
```

Dos notas de implementación. La primera, operativa: RAGAS usa por dentro un modelo de lenguaje como juez y un modelo de embeddings para algunas métricas. Se configura con tu clave de OpenAI, `text-embedding-3-small` para los embeddings y un modelo de chat como juez; el corpus está en español y el juez evalúa en español sin problema. La segunda, honesta: la API de RAGAS ha cambiado de forma notable entre versiones, nombres de columnas, clases de dataset, cómo se pasan los modelos. El esqueleto de arriba refleja la forma clásica; fija la versión de RAGAS en tu proyecto y comprueba los nombres exactos contra ella, porque lo que aquí se llama `ground_truth` y `Dataset` puede llamarse de otra forma en la versión que instales.

## **De la medida puntual a la monitorización continua**

Calcular las métricas una vez sirve para una foto. El valor de verdad aparece cuando las usas en dos modos distintos, y conviene no confundirlos.

El primero es la **evaluación offline como puerta de regresión**. Antes de desplegar un cambio, un prompt nuevo, otro modelo, una migración de embeddings, pasas el golden set por la versión candidata y comparas sus cuatro métricas con las de la versión actual. Si la fidelidad o el recall caen, no despliegas: acabas de cazar una regresión antes de que llegue a producción, en lugar de después por una queja. Esto necesita el `ground_truth`, así que solo es posible offline, sobre tu golden set.

El segundo es la **monitorización en producción**, y tiene un límite que hay que respetar: en producción no tienes respuesta de referencia. Para una consulta real de un usuario, nadie ha escrito de antemano la estimación correcta, así que no puedes calcular context recall sobre tráfico vivo. Lo que sí puedes calcular son las métricas que no necesitan referencia, fidelidad y relevancia de la respuesta sobre una muestra del tráfico real.

```python
async def monitor_production_sample(estimates: list[ServedEstimate]) -> dict[str, float]:
    """Reference-free quality monitor on sampled live traffic.

    Faithfulness and answer relevancy need no ground_truth, so they work on
    real queries. Context recall does not: there is no reference answer for a
    live request. Alert on downward drift, not on absolute values.
    """
    dataset = Dataset.from_dict({
        "question": [e.question for e in estimates],
        "answer": [e.answer_text for e in estimates],
        "contexts": [[c.content for c in e.retrieved_chunks] for e in estimates],
    })
    scores = evaluate(dataset, metrics=[faithfulness, answer_relevancy])
    return scores
```

![art6-fig18-offline-vs-produccion.jpg](https://media1-production-mightynetworks.imgix.net/asset/2880877f-109f-4460-9d51-7101c580df63/art6-fig18-offline-vs-produccion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

A esa muestra se le suman las señales operativas que ya producen los guardarraíles de cada respuesta: la tasa de abstenciones, la de citas colgantes cazadas, la de líneas degradadas. Juntas dan un cuadro de mando de calidad que se mueve en el tiempo, y una alerta cuando algo se degrada sin que nadie haya tocado nada.

## **Trade-offs honestos**

**El juez de RAGAS es un modelo, con la misma circularidad de siempre.** Usar un LLM para puntuar la fidelidad de otro LLM hereda todas las limitaciones de un juez basado en modelo: las métricas son ruidosas y probabilísticas. Una fidelidad de 0,82 no significa "82% verdadero"; es un número comparable. Úsalas como tendencias y como comparaciones relativas entre versiones, A contra B, no como verdades absolutas. El día que trates un 0,82 como una nota objetiva, la métrica empieza a engañarte.

**El golden set es el techo, y un techo bajo no se ve.** Un conjunto pequeño o poco representativo da números igual de confiados que uno bueno; la diferencia es que los del malo no significan nada, y nada en la salida te avisa de ello. Invertir en un golden set amplio, representativo y con respuestas de referencia correctas no es preparación para la evaluación: es la evaluación. Lo demás es cómputo sobre datos malos.

**Optimizar una métrica sola estropea las otras.** Es la ley de Goodhart en versión RAG: si persigues fidelidad a toda costa, el sistema aprende a abstenerse más y a comprometerse menos, y la relevancia y la utilidad se hunden mientras la fidelidad sube. La tensión entre fidelidad (no afirmar lo que no se sostiene) y relevancia (de verdad contestar) es la misma de la abstención, ahora visible en números. Las cuatro métricas se leen juntas, nunca una en aislamiento.

**La deriva en producción no siempre es una regresión.** Las métricas sin referencia sobre tráfico vivo se mueven también cuando cambia el tipo de preguntas que hacen los usuarios, no solo cuando cambia el sistema. Una caída de fidelidad puede venir de que esta semana entran consultas más difíciles, no de un bug. No atribuyas cada bajada a una regresión: cruza la deriva con qué cambió de verdad antes de actuar.

**Evaluar cuesta, y es un lote, no una petición.** RAGAS hace muchas llamadas al juez por cada caso, multiplicado por el tamaño del conjunto. Es un trabajo offline que se presupuesta y se programa, no algo que corras en la ruta de cada respuesta. Confundir la evaluación con un guardarraíl en línea es una forma cara de no entender ninguno de los dos.

## **Lo que cierra, y lo que abre**

Con la evaluación, el arco de la calidad se completa. El contexto recuperado se prepara para que el modelo no se ahogue en ruido; las fuentes que se contradicen se sintetizan en una estimación coherente con su rango y su razón; cada cifra se cita de forma verificable hasta el presupuesto original; cada respuesta se verifica contra sus fuentes y se abstiene antes que inventar; el índice se mantiene sano para que nada se degrade en silencio; y, por fin, cuatro métricas sobre un golden set permiten saber si todo eso funciona y si cada cambio lo mejora o lo empeora. El sistema ya no solo genera estimaciones: las genera citadas, verificables y medibles.

Pero todo esto vale para *una* estimación: una transcripción entra, una estimación sale. Los proyectos de verdad no son una estimación. Un encargo serio se descompone en piezas que casi no se parecen entre sí el frontend, la lógica de negocio, la infraestructura, una auditoría de seguridad, y cada pieza quiere su propia recuperación, su propio razonamiento, su propia verificación. Estimar bien un sistema complejo no es generar una respuesta grande: es coordinar muchas respuestas especializadas, cada una fundamentada y medible, y juntarlas sin que el conjunto pierda la coherencia ni la trazabilidad que tanto ha costado construir.

Coordinar varios pasos de razonamiento especializados, descomponer un problema grande en sub-tareas, repartirlas, y recomponer el resultado, es una arquitectura distinta de la que hemos levantado hasta aquí. Y la disciplina de medir que cierra esta sesión no desaparece cuando llegan las piezas móviles: se vuelve más necesaria, porque cuantas más partes coordinas, más sitios hay donde la calidad se puede perder sin que nadie lo vea.