# Síntesis de múltiples presupuestos: combinar fuentes que se contradicen

Creada: 27 de junio de 2026 11:43
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S11. RAG Avanzado - Generación y Calidad (https://app.notion.com/p/S11-RAG-Avanzado-Generaci-n-y-Calidad-38cea9ca03c48049a493d33b89499a1d?pvs=21)

El sistema de estimaciones rara vez se apoya en un solo presupuesto histórico. Para estimar el módulo de pagos de un proyecto nuevo, recupera tres o cuatro presupuestos de proyectos parecidos, cada uno con su cifra. Y aquí aparece el problema que ninguna técnica de preparación de contexto resuelve: esas cifras no coinciden. Un proyecto fintech de 2024 cifró el módulo de pagos en 40 horas. Otro, de comercio electrónico de 2023, en 90. Un tercero, fintech y reciente, en 55. Los tres son relevantes. Los tres están bien recuperados y bien destilados. Y se contradicen.

La síntesis es el paso que convierte ese conjunto de fuentes en una sola estimación coherente. Es, con diferencia, donde más se nota la diferencia entre un sistema que parece serio y uno que lo es. Un generador ingenuo hace una de tres cosas con esas cifras, y las tres son malas: promedia en silencio y devuelve "62 horas" sin explicar nada; se queda con la primera que encuentra; o, peor, inventa un número intermedio que suena razonable y no corresponde a ninguna fuente. Las tres producen una cifra plausible. Ninguna produce una cifra defendible.

Sintetizar bien no es elegir un número. Es entender por qué las fuentes discrepan, decidir cuánto pesa cada una, y producir una estimación que sea honesta sobre lo que sabe y lo que no.

## **El problema no es combinar, es que se contradicen**

Si los tres presupuestos coincidieran en 50 horas, no haría falta sintetizar nada: cualquier media da el resultado correcto. El trabajo aparece precisamente cuando discrepan, y la primera pregunta no es "¿qué número pongo?" sino "¿por qué discrepan?".

Casi siempre hay una razón, y casi siempre está en los datos si los miras. El proyecto de 40 horas tenía la pasarela de pago ya integrada de un encargo anterior: cifró solo la conexión, no la infraestructura. El de 90 lo construyó desde cero y además es de hace dos años, cuando las herramientas eran menos maduras. El de 55 es reciente y de alcance comparable. La discrepancia no es ruido: es información. Te está diciendo que la estimación depende de una variable, si la pasarela está integrada o no, que el cliente probablemente no mencionó en la transcripción.

![art2-fig4-tres-fuentes-contradiccion.jpg](https://media1-production-mightynetworks.imgix.net/asset/e7251bc1-6c86-4012-a6b3-e4472961f1cb/art2-fig4-tres-fuentes-contradiccion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Una síntesis que aplasta esa señal en un "62 horas" tira a la basura lo más valioso que tenían los datos. Una síntesis buena la conserva: "entre 55 y 90 horas si se construye desde cero; alrededor de 40 si la pasarela ya está integrada". Eso es una estimación que un jefe de proyecto puede usar, porque le dice qué pregunta hacer antes de comprometerse.

El objetivo, entonces, es doble: producir un número (o un rango) defendible, y hacer explícita la razón de la discrepancia cuando la hay.

## **Pesar las fuentes con criterio**

No todas las fuentes merecen el mismo voto. El pipeline de recuperación ya calculó, para cada fragmento, tres señales que importan aquí: la relevancia (lo bien que el reranker lo consideró aplicable a la consulta), la recencia (un peso que decae con la antigüedad del presupuesto) y la similitud semántica con la consulta. Esas señales son la base para ponderar.

```python
class SourceWeights(BaseModel):
    relevance: float   # reranker score, normalized to 0..1
    recency: float     # temporal decay weight, 0..1
    similarity: float  # vector similarity, 0..1

def combined_weight(w: SourceWeights) -> float:
    """Single auditable weight per source.

    The coefficients are a policy decision, documented and versioned.
    Three signals, not seven: the goal is a number you can defend in
    one sentence, not a pile of multipliers nobody can justify.
    """
    return 0.5 * w.relevance + 0.3 * w.recency + 0.2 * w.similarity
```

El comentario del código no es decorativo. La tentación al ponderar es añadir factores: un boost por sector, otro por tamaño de equipo, otro por tipo de cliente. Cada factor que añades es un número mágico que tendrás que defender, y siete factores interactuando entre sí sustituyen la opacidad del modelo por una opacidad artesanal que solo *parece* bajo control. La regla práctica es dura pero sana: si no puedes explicar en una frase por qué la relevancia pesa 0,5 y no 0,4, ese coeficiente no estaba listo. Empieza con las pocas señales que de verdad mueven el resultado y añade más solo con evidencia de que ayudan.

## **Agregar antes de generar**

Hay dos formas de hacer la síntesis. Puedes pasarle al modelo todas las fuentes con sus pesos y pedirle que razone y produzca la estimación de una sola vez. Es simple, pero el número final sale de una caja negra: no sabes si el modelo respetó tus pesos, ni por qué aterrizó en esa cifra, y auditarlo después es difícil.

La alternativa, más robusta para un sistema donde la cifra tiene que ser defendible, es separar la aritmética del juicio. Primero calculas en código un ancla determinista por componente, una cifra central ponderada, su dispersión, y una señal de si hay contradicción real, y luego le das al modelo las fuentes *y* esos agregados, para que razone sobre ellos en vez de inventarse la aritmética. El número tiene un esqueleto auditable; el modelo aporta el juicio que la aritmética no puede dar (entender que 40 y 90 difieren por alcance, no por error).

```python
class ComponentAggregate(BaseModel):
    component: str
    weighted_estimate: float   # central anchor, in hours
    low: float
    high: float
    contradiction: bool
    sources: list[str]         # chunk_ids contributing to this component

def weighted_median(values_weights: list[tuple[float, float]]) -> float:
    """Robust central tendency: a single outlier budget cannot drag it."""
    items = sorted(values_weights, key=lambda vw: vw[0])
    half = sum(weight for _, weight in items) / 2
    acc = 0.0
    for value, weight in items:
        acc += weight
        if acc >= half:
            return value
    return items[-1][0]

CONTRADICTION_REL_SPREAD = 0.5  # >50% spread between strong sources -> surface it
STRONG_WEIGHT_FLOOR = 0.4

def aggregate_components(
    evidence: list[BudgetEvidence],
    weights: dict[str, SourceWeight],
) -> list[ComponentAggregate]:
    by_component: dict[str, list[BudgetEvidence]] = defaultdict(list)
    for item in evidence:
        if item.hours is not None:
            by_component[normalize_label(item.component)].append(item)

    aggregates: list[ComponentAggregate] = []
    for component, items in by_component.items():
        vw = [(it.hours, combined_weight(weights[it.chunk_id])) for it in items]
        anchor = weighted_median(vw)
        hours = [it.hours for it in items]
        low, high = min(hours), max(hours)
        rel_spread = (high - low) / anchor if anchor else 0.0
        strong_values = {value for value, weight in vw if weight >= STRONG_WEIGHT_FLOOR}
        contradiction = rel_spread > CONTRADICTION_REL_SPREAD and len(strong_values) > 1
        aggregates.append(
            ComponentAggregate(
                component=component,
                weighted_estimate=round(anchor, 1),
                low=low,
                high=high,
                contradiction=contradiction,
                sources=[it.chunk_id for it in items],
            )
        )
        log.info(
            "component_aggregated",
            component=component,
            anchor=anchor,
            low=low,
            high=high,
            contradiction=contradiction,
        )
    return aggregates
```

Dos decisiones merecen un comentario. La primera: uso mediana ponderada y no media. La mediana es robusta a outliers, y en estimaciones eso importa, porque un presupuesto con un alcance muy distinto no debería arrastrar el ancla hacia su cifra anómala solo por estar en el conjunto. La segunda: la contradicción no se declara por dispersión alta a secas, sino por dispersión alta *entre fuentes fuertes*. Si la única cifra discordante viene de una fuente con peso bajo, es un outlier que puedes ignorar; si dos fuentes con peso alto discrepan, es una contradicción real que hay que sacar a la luz. Esa distinción evita inundar al usuario de avisos falsos.

## **Generar la síntesis: rango, razón y fuentes**

Con los agregados calculados, la generación deja de ser "inventa un número" y pasa a ser "razona sobre estos datos". El esquema de salida obliga a que cada componente sea un rango, no un punto: cuando hay confianza, el rango colapsa (`low == high`); cuando hay contradicción, el rango la refleja. Y cada componente arrastra los `chunk_id` de las fuentes que lo respaldan, porque una estimación que no sabe de dónde sale cada número no es defendible.

![art2-fig5-sintesis-dos-etapas.jpg](https://media1-production-mightynetworks.imgix.net/asset/76b5254a-cd8b-48f9-b16f-92c0f144f50d/art2-fig5-sintesis-dos-etapas.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

```python
class SynthesizedComponent(BaseModel):
    component: str
    low_hours: float
    high_hours: float            # equals low_hours when it is a confident point
    rationale: str               # why this number; explains any disagreement
    source_chunk_ids: list[str]
    contested: bool              # sources disagreed for a substantive reason

class Estimate(BaseModel):
    components: list[SynthesizedComponent]
    total_low: float
    total_high: float
    summary: str
```

Las instrucciones al modelo son donde se gana o se pierde la honestidad de la síntesis. No basta con pedir "una estimación"; hay que prohibir explícitamente el promedio ciego y exigir que la discrepancia se explique:

```python
SYNTHESIS_INSTRUCTIONS = """\
You synthesize a software estimate from multiple historical budgets.

Rules:
- Never blindly average conflicting figures. If sources disagree, find the
  reason in the evidence (scope, recency, team, client complexity) and state
  it in `rationale`.
- Stay within the [low, high] range of the precomputed aggregate for each
  component unless you can name an explicit reason to go outside it.
- When `contradiction` is true for a component, return a range (low_hours <
  high_hours) and explain the dependency that drives it. Do not collapse a
  real disagreement into a false-precise single number.
- Every component must list the source_chunk_ids it is grounded on. Do not
  cite a source that was not provided.
- If the evidence for a component is thin or only weakly relevant, say so in
  the rationale rather than projecting false confidence.
"""

def synthesize_estimate(
    evidence: list[BudgetEvidence],
    aggregates: list[ComponentAggregate],
) -> Estimate:
    response = client.responses.parse(
        model=settings.generation_model,  # gpt-5, reasoning effort medium
        input=[
            {"role": "system", "content": SYNTHESIS_INSTRUCTIONS},
            {"role": "user", "content": render_synthesis_input(evidence, aggregates)},
        ],
        text_format=Estimate,
    )
    return response.output_parsed
```

El ancla determinista y las instrucciones trabajan juntas: el agregado le dice al modelo dónde está el centro y dónde están los bordes razonables, y las instrucciones le impiden salirse de ahí sin justificarlo. El modelo no inventa la aritmética; la explica y la ajusta con el juicio que la aritmética no tiene. Para el módulo de pagos del ejemplo, eso produce algo como: "55–90 h si se construye desde cero (proyectos de 2023 y 2025); ~40 h si la pasarela ya está integrada, como en el proyecto fintech de 2024", con los tres `chunk_id` en `source_chunk_ids` y `contested=True`.

![art2-fig6-anatomia-componente.jpg](https://media1-production-mightynetworks.imgix.net/asset/3bfa5c00-a4fc-42ed-9aa4-031d6fb0a07c/art2-fig6-anatomia-componente.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Trade-offs honestos**

**Síntesis en una pasada frente a dos etapas.** La pasada única es más simple y aprovecha mejor el razonamiento del modelo, pero el número sale opaco y cuesta auditarlo. Las dos etapas dan un ancla determinista y trazable a costa de más maquinaria y de un riesgo nuevo: que el modelo se aparte del ancla sin justificarlo, que es precisamente lo que las instrucciones tienen que vigilar. Para un sistema de estimaciones que alguien usará para comprometer dinero, la auditabilidad suele ganar.

**La ponderación es tan buena como las señales que la alimentan.** Si la relevancia del reranker está mal calibrada o el decaimiento temporal usa una semivida que no corresponde a tu dominio, el ancla ponderada será confiadamente incorrecta. Pesar fuentes no arregla señales malas; las amplifica. Antes de afinar coeficientes, comprueba que las señales que ponderas miden lo que crees.

**Mediana frente a media, y el problema del N pequeño.** La mediana es robusta, pero con dos o tres fuentes es una herramienta tosca: la "mediana" de dos valores no aporta mucho. Con conjuntos pequeños, el valor real no está tanto en el estadístico central como en el rango y en la explicación de por qué se abre. No sobre-interpretes un ancla calculada sobre tres puntos.

**El umbral de contradicción es una política, no una verdad.** Demasiado estricto y marcarás como contradicción cualquier variación normal; demasiado laxo y ocultarás discrepancias reales. El 50% del ejemplo es un punto de partida razonable, no un valor sagrado: ajústalo observando cuántas alertas resultan accionables frente a cuántas son ruido.

**El rango incomoda al producto, y hay que defenderlo igual.** Un rango "55–90 h" es menos cómodo de enseñar que un "70 h" limpio, y habrá presión para colapsarlo. Pero colapsar un desacuerdo real en un punto de falsa precisión es mentir con apariencia de rigor. La síntesis honesta a veces tiene que entregar un rango, y la interfaz tiene que estar preparada para mostrarlo y para explicar de qué depende.

**Sintetizar no fabrica información.** Si las cuatro fuentes son de relevancia baja, ninguna ponderación ni razonamiento las convierte en una buena estimación. Una síntesis segura sobre evidencia pobre es peor que una que admite que los datos no dan para tanto. La confianza de la salida tiene que ser un reflejo de la calidad de la entrada, no un valor por defecto.

## **Lo que esto deja sin resolver**

La síntesis produce ahora una estimación que es coherente, que razona sobre sus propias contradicciones y que entrega rangos honestos en lugar de números de relleno. Pero al combinar varias fuentes en cada componente ha hecho algo que tiene una consecuencia incómoda: ha entrelazado los hilos. La cifra de pagos ya no viene "de un presupuesto"; viene de tres, ponderados, con un razonamiento encima.

Y eso vuelve más difícil, y más urgente, una pregunta que cualquiera que reciba la estimación va a hacer: *este 55, ¿de dónde sale exactamente?* Tener los `chunk_id` en la salida es un principio; no es todavía una respuesta verificable. Que cada afirmación de la estimación pueda señalar, de forma comprobable, el presupuesto histórico y la línea concreta de la que se deriva es un problema en sí mismo, y es el cimiento sobre el que se construye la confianza en todo lo demás. Una estimación que no puede mostrar su origen no es una estimación: es una opinión bien formateada.