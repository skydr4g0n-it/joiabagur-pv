# Competición y síntesis entre agentes

Creada: 20 de julio de 2026 21:12
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S14. Sistemas multi-agente y patrones avanzados (https://app.notion.com/p/S14-Sistemas-multi-agente-y-patrones-avanzados-3a3ea9ca03c4800f98e8fdae96ec7f6f?pvs=21)

Vuestro sistema devuelve 260 horas.

¿Cuánto os fiáis de ese número? No tenéis forma de saberlo. Es la salida de un agente que hizo su trabajo lo mejor que pudo, y podría venir de un caso trivial que el sistema clavó o de un caso imposible sobre el que el modelo improvisó con aplomo. La cifra se ve exactamente igual en ambos casos. Esa es la debilidad de fondo de un estimador único: **no produce ninguna medida de su propia fragilidad**.

Podéis pedirle al modelo que puntúe su confianza, y es mejor que nada. Pero un modelo evaluando su propia respuesta tiene el sesgo que cabe esperar: tiende a confiar en lo que acaba de decir, y a producir números que suenan razonables sin correlacionar demasiado con si acertó.

Hay otra forma de conseguir esa medida, y es más honesta: **hacer que dos agentes con criterios opuestos ataquen el mismo problema y mirar cuánto se separan**.

## **De cooperar a competir**

Hasta ahora todos vuestros agentes cooperan: cada uno aporta una pieza distinta y el resultado es la composición. El extractor no compite con el buscador; se necesitan.

La competición es otra cosa. Dos o más agentes atacan **la misma tarea**, con criterios deliberadamente distintos, y un tercero decide qué hacer con el desacuerdo.

En estimación de software el ejemplo es casi obsceno de tan natural, porque es exactamente lo que ocurre en cualquier reunión de estimación real. Está el que dice que son dos semanas y está el que dice que son dos meses, y los dos tienen razón bajo sus supuestos. El desacuerdo no es un fallo del proceso: **el desacuerdo es el proceso**.

Dos estimadores, entonces:

- `conservative_estimator`: asume fricción. Integraciones que se tuercen, requisitos que crecen, un entorno de staging que nadie ha montado.
- `aggressive_estimator`: asume el mejor caso razonable. Equipo competente, alcance estable, sin sorpresas.

Y un `synthesizer` que recibe ambas propuestas.

![art_5_fig-01-subgrafo-competicion_1.png](https://media1-production-mightynetworks.imgix.net/asset/8508418d-5b74-43a7-b77a-ff369e8b3bfb/art_5_fig-01-subgrafo-competicion_1.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Implementarlo**

### **Las propuestas tienen esquema**

Lo primero que hay que fijar es qué produce un estimador. Si devuelve un número suelto, el sintetizador no puede hacer nada inteligente con el desacuerdo: solo puede promediar, que es la peor de las opciones. Un estimador tiene que devolver **su número y los supuestos que lo sostienen**.

```python
from pydantic import BaseModel, Field

class EstimateProposal(BaseModel):
    stance: Literal["conservative", "aggressive"]
    hours: float = Field(gt=0)
    assumptions: list[str] = Field(description="What this estimate takes for granted.")
    risks: list[str] = Field(description="What would make this estimate wrong.")
    reasoning: str
```

Los `assumptions` son la carga útil. Cuando el conservador dice 340 horas porque *asume que la integración con el ERP legacy no está documentada*, y el agresivo dice 190 porque *asume que el cliente proporciona documentación y un entorno de pruebas*, la diferencia entre ambos no es un número: **es una pregunta concreta que alguien puede ir a resolver**. Ese es el output valioso.

### **Los dos estimadores corren en paralelo**

Son independientes, así que no hay motivo para pagar dos latencias en serie. LangGraph ejecuta en paralelo los nodos que salen de un mismo punto, y el estado los reúne:

```python
class EstimationState(TypedDict):
    requirements: list[str]
    budget_matches: list[dict]
    proposals: Annotated[list[dict], operator.add]   # <- the reducer does the fan-in
    estimate: dict | None
    confidence: float | None
```

```python
builder.add_edge("requirements_extractor", "conservative_estimator")
builder.add_edge("requirements_extractor", "aggressive_estimator")

builder.add_edge("conservative_estimator", "synthesizer")
builder.add_edge("aggressive_estimator", "synthesizer")
```

El fan-in es gratis, y es gratis **por el reducer**. `proposals` está anotado con `operator.add`, así que las dos escrituras concurrentes se concatenan en lugar de pisarse. Si ese campo estuviera sin anotar, uno de los dos estimadores desaparecería en silencio y tendríais un sistema de competición con un solo competidor. Es el bug más silencioso de todo este artículo.

```python
CONSERVATIVE_INSTRUCTIONS = """You estimate software projects assuming friction.
Undocumented integrations, scope creep, environments that are not ready,
requirements that turn out to hide complexity. Be explicit about every
assumption you make. You are not pessimistic for its own sake: you are the
estimate that survives contact with reality.
"""

async def conservative_estimator(state: EstimationState) -> dict:
    with logfire.span("agent.conservative_estimator"):
        response = await client.responses.parse(
            model="gpt-5",
            input=[
                {"role": "system", "content": CONSERVATIVE_INSTRUCTIONS},
                {"role": "user", "content": render_estimation_brief(state)},
            ],
            text_format=EstimateProposal,
        )
        return {"proposals": [response.output_parsed.model_dump()]}
```

### **La divergencia se calcula, no se opina**

Y aquí está la decisión de diseño que hace que todo esto valga la pena.

La tentación es pasarle las dos propuestas al sintetizador y pedirle que "evalúe cuánto difieren". **No lo hagáis.** La divergencia entre dos números es una operación aritmética. Pedírsela a un LLM es pagar tokens por una división, y encima aceptar que a veces la haga mal.

```python
def compute_divergence(proposals: list[dict]) -> float:
    """Relative spread between proposals. Deterministic, cheap, testable."""
    hours = [p["hours"] for p in proposals]
    lo, hi = min(hours), max(hours)
    return (hi - lo) / hi
```

Una línea de aritmética. Cero tokens. Y con eso ya tenéis, **antes de llamar al sintetizador**, la señal que os faltaba: 190 contra 340 da una divergencia de 0.44; 250 contra 270 da 0.07.

![art_5_fig-02-divergencia-como-senal_1.png](https://media1-production-mightynetworks.imgix.net/asset/7695cbb5-4594-4d2f-b0c5-13bce125269b/art_5_fig-02-divergencia-como-senal_1.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Fijaos en lo que significa cada caso, porque no es simétrico.

**Convergen.** Dos criterios deliberadamente opuestos han llegado casi al mismo sitio. Eso es información fuerte: **el resultado no depende de los supuestos**. Da igual si el equipo es senior o si la integración se tuerce, el proyecto cuesta lo que cuesta. El sistema puede cerrar solo con confianza alta.

**Divergen.** El resultado depende por completo de qué supuestos se acepten. No es que el sistema haya calculado mal: es que **la pregunta no tiene una respuesta calculable** sin decidir antes si el cliente va a entregar la documentación del ERP. Eso es un juicio, y un juicio lo toma una persona.

Es decir: la competición no os da solo una estimación mejor. Os da **el criterio para saber cuándo no deberíais estar estimando solos**. La divergencia alimenta directamente la confianza, y la confianza alimenta la decisión de parar.

### **El sintetizador no promedia**

```python
SYNTHESIZER_INSTRUCTIONS = """You receive two estimates for the same project,
produced under opposite assumptions, plus a computed divergence score.

Do not average them. Your job is to:
- Identify which assumptions actually drive the difference.
- Produce a final estimate with an explicit range, not a single point.
- State what would have to be true to move the estimate toward either end.
- Report your confidence, taking the divergence score into account.
"""

class SynthesizedEstimate(BaseModel):
    hours: float
    range_low: float
    range_high: float
    confidence: float = Field(ge=0.0, le=1.0)
    driving_assumptions: list[str]
    open_questions: list[str]

async def synthesizer(state: EstimationState) -> dict:
    divergence = compute_divergence(state["proposals"])

    response = await client.responses.parse(
        model="gpt-5",
        input=[
            {"role": "system", "content": SYNTHESIZER_INSTRUCTIONS},
            {"role": "user", "content": render_proposals(state["proposals"], divergence)},
        ],
        text_format=SynthesizedEstimate,
    )
    result = response.output_parsed

    return {
        "estimate": result.model_dump(),
        "confidence": result.confidence,
    }
```

La instrucción explícita de **no promediar** no es paranoia. Es el comportamiento por defecto al que tiende un modelo cuando le das dos números y le pides uno, y promediar es precisamente lo que destruye el valor de haber pagado dos estimaciones. La media entre 190 y 340 es 265, un número que nadie puede defender y que además **oculta que el rango existe**. Vuestro cliente no necesita un punto falsamente preciso: necesita un rango y las dos o tres preguntas cuya respuesta lo estrecharía.

Y `open_questions` es, para mí, el campo más útil que produce este sistema entero. Es la lista de lo que habría que ir a preguntarle al cliente. Un estimador único jamás la produce, porque no sabe en qué se estaba jugando el número.

## **Cuándo esto es un fraude**

Tres formas de tirar el dinero, ordenadas por frecuencia.

### **La trampa de la correlación**

Coged dos agentes, dadles **el mismo modelo, el mismo contexto y prompts que se diferencian en un adjetivo** ("estima de forma conservadora" / "estima de forma agresiva"), y observad lo que pasa: sus salidas se parecen muchísimo. Habréis pagado tres llamadas para obtener la ilusión de una segunda opinión.

El motivo es evidente en cuanto se dice en voz alta: dos muestras del mismo modelo sobre el mismo contexto están enormemente correlacionadas. El adjetivo mueve el número un 10% y ya. Y lo peor no es el coste: es que la **divergencia baja resultante es una señal falsa de confianza**. El sistema os dirá que el caso es predecible cuando en realidad lo que pasa es que no habéis creado ninguna diversidad real.

Para que la competición valga algo, los competidores tienen que diferir **de verdad**:

- **Prompts con criterios sustantivos y distintos**, no adjetivos. Que el conservador tenga instrucciones sobre integraciones no documentadas y deuda técnica; que el agresivo tenga instrucciones sobre reutilización y equipos con contexto.
- **Evidencia distinta.** Este es el que más impacto tiene y el que menos se usa: dadle al conservador los presupuestos históricos que **se pasaron de plazo**, y al agresivo los que salieron limpios. Ahora no están discutiendo sobre estilo: están mirando mundos distintos.
- **Idealmente, modelos distintos.** Dos proveedores tienen sesgos distintos, y su desacuerdo es más informativo que el de un modelo consigo mismo.

Si no podéis conseguir ninguna de las tres, la competición no os va a dar señal. No la montéis.

### **La competición donde no hay nada que juzgar**

Competir en la extracción de requisitos es tirar dinero: hay una respuesta razonablemente correcta y dos agentes van a converger a ella. La competición solo aporta cuando **hay un juicio de por medio**, es decir, cuando dos personas expertas y razonables podrían discrepar legítimamente. Estimar horas cumple. Extraer de una transcripción que el cliente pidió login con Google, no.

Regla: si vosotros no sabríais defender las dos posturas, vuestros agentes tampoco.

### **Escalar a N competidores**

Es tentador pensar que si dos son buenos, cinco son mejores. No: **los retornos decaen rápido y el coste es lineal**. Con dos criterios genuinamente opuestos ya tenéis la señal que buscabais —la banda de incertidumbre—. El tercero suele caer en medio y no os dice nada que no supierais. Quedaos en dos, salvo que podáis nombrar un tercer criterio que sea de verdad ortogonal a los otros dos.

### **Y una alternativa más barata que conviene conocer**

Antes de montar tres agentes, sabed que existe una técnica más simple: **muestrear el mismo prompt varias veces y mirar la dispersión**. Es más barato de construir, no exige diseñar criterios opuestos y os da también una medida de estabilidad.

Lo que *no* os da es lo bueno: no produce supuestos contrapuestos, no produce preguntas abiertas y no os dice **por qué** los números difieren. El muestreo repetido mide el ruido del modelo. La competición mide la **incertidumbre del dominio**. Son cosas distintas, y solo la segunda es accionable con un cliente delante.

## **El coste, sin adornos**

Un estimador: una llamada. Competición: dos llamadas en paralelo más una síntesis, es decir, **tres llamadas y latencia de la más lenta de las dos**. En coste, x3. En latencia, aproximadamente x2.

¿Merece la pena? Si la salida de vuestro sistema es un presupuesto que se manda a un cliente y compromete a la empresa durante meses, triplicar el coste de una inferencia para obtener un rango defendible, una lista de supuestos y una medida real de incertidumbre es, con diferencia, el mejor dinero que vais a gastar en todo el sistema.

Si la salida es una estimación orientativa para priorizar un backlog interno, no. Poned un estimador y seguid.

Esa es toda la decisión, y depende de lo que cueste equivocarse.

## **Un cabo suelto**

Llevamos cinco agentes, seis con el sintetizador, y los hemos ido añadiendo con bastante alegría. Cada uno tiene su prompt, su esquema y sus herramientas.

Sus herramientas. Ahí hay algo que no hemos mirado.

El `budget_searcher` consulta la base de datos de presupuestos. ¿Solo consulta? El día que alguien le dé una tool para escribir —para guardar la estimación, para marcar un presupuesto como usado, para lo que sea— habrá un agente gobernado por un modelo con permiso de escritura sobre datos de la empresa, y nadie habrá tomado esa decisión de forma explícita: simplemente habrá pasado.

La pregunta que queda es la más aburrida y la más importante: **qué puede tocar exactamente cada agente, y qué pasa cuando intenta tocar lo que no debe.**