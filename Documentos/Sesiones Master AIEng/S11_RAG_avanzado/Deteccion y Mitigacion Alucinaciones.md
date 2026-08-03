# Detección y mitigación de alucinaciones

Creada: 27 de junio de 2026 12:37
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S11. RAG Avanzado - Generación y Calidad (https://app.notion.com/p/S11-RAG-Avanzado-Generaci-n-y-Calidad-38cea9ca03c48049a493d33b89499a1d?pvs=21)

Llegamos al punto donde la estimación parece intachable. Cada componente lleva su cifra, cada cifra su citación, y las citaciones resuelven a presupuestos reales que estuvieron en el contexto recuperado. La integridad referencial está garantizada: ninguna fuente apunta al vacío. Y sin embargo, el sistema puede estar mintiendo.

Porque que `fin-2024-07#c3` exista y resuelva a un presupuesto real no dice nada sobre si ese presupuesto contiene "40 h para pagos". El modelo pudo citar, con un identificador perfectamente válido, un fragmento que en realidad habla de autenticación. Pudo atribuir a esa fuente una cifra que no aparece en ella. O pudo inventarse el número entero y colgarle la citación más plausible que tenía a mano. La citación está impecable. La afirmación es falsa. Esto es una alucinación con coartada, y es la más peligrosa precisamente porque ha pasado todos los filtros estructurales.

Detectarla ya no es comprobar identificadores. Es comprobar que el contenido de la fuente sostiene de verdad lo que la estimación dice. Esa es la última capa de confianza del sistema, y la más difícil de construir, porque exige verificar significado, no forma.

## **Tres formas de alucinar en una estimación**

No todas las alucinaciones son iguales, y distinguirlas importa porque se detectan con técnicas distintas.

La **fabricación** es el caso puro: una cifra que no aparece en ninguna fuente. El modelo escribe "40 h para pagos" y ninguno de los fragmentos recuperados contiene ese número para ese componente. Se lo ha inventado, a veces porque "suena razonable", a veces porque rellena un hueco que no sabía cómo dejar vacío. Es la más fácil de detectar si tienes las cifras de las fuentes a mano.

La **atribución falsa** es más sutil: la cifra existe, pero no en la fuente que se le adjudica. Quizá el 40 h sí está en algún presupuesto, pero el `chunk_id` citado corresponde a otro componente o a otro proyecto. O dos fuentes dicen 40 h y 90 h, y el modelo presenta 40 h citando el fragmento que en realidad decía 90. La cifra es real; la trazabilidad es mentira. Y como la citación resuelve, los filtros estructurales no la ven.

La **extrapolación no fundamentada** es la más difícil de acotar: el modelo razona más allá de lo que las fuentes soportan. Las fuentes dan el módulo de pagos en 40 h y 90 h, y el modelo concluye que "un módulo de pagos complejo con antifraude rondará las 160 h", una cifra que no está en ningún sitio y que no se deriva de los datos, sino de una generalización que suena experta. Aquí no hay una fuente equivocada que señalar; hay un salto lógico que nadie pidió.

![art4-fig10-tres-alucinaciones.jpg](https://media1-production-mightynetworks.imgix.net/asset/45877ebe-5c3b-4758-85c5-ee73d7d10a48/art4-fig10-tres-alucinaciones.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Las tres comparten una propiedad incómoda: producen salidas plausibles. Una alucinación que sonara absurda no sería un problema. El problema es justo que suenan bien.

## **Detectar: lo barato primero, lo caro después**

La verificación cuesta, en latencia, en llamadas, en dinero, así que no se aplica toda a todo. La estrategia que funciona es por capas: primero comprobaciones deterministas que no cuestan casi nada y cazan lo flagrante, y solo sobre lo que sobrevive, verificación semántica cara. Lo que un `if` puede descartar no debería gastar una llamada a un modelo.

![art4-fig11-embudo-verificacion.jpg](https://media1-production-mightynetworks.imgix.net/asset/0b988c0d-d86d-44ef-b6f3-ffb1b7be2d52/art4-fig11-embudo-verificacion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

### **Anclaje numérico: la comprobación que no cuesta una llamada**

La primera capa es puramente aritmética. Cada cifra de la estimación debería poder rastrearse hasta las cifras de las fuentes citadas. Si la estimación dice 40 h citando dos fragmentos, y esos fragmentos dicen 40 h y 55 h, el 40 está anclado. Si dice 160 h y los fragmentos citados dicen 40 y 90, el 160 está fuera del rango de todo lo que cita: es una extrapolación, y se marca.

```python
def numeric_grounding(line: SynthesizedComponent, evidence_by_id: dict[str, BudgetEvidence]) -> bool:
    """Cheap, deterministic check: is the claimed figure traceable to cited sources?

    Interpolation within the cited range is allowed; a figure outside the
    range of every cited source is an unsupported extrapolation.
    """
    cited_hours = [
        evidence_by_id[cid].hours
        for cid in line.source_chunk_ids
        if cid in evidence_by_id and evidence_by_id[cid].hours is not None
    ]
    if not cited_hours:
        return False  # no numeric support at all -> fabrication
    return min(cited_hours) <= line.low_hours and line.high_hours <= max(cited_hours)
```

La decisión de diseño que hay detrás de ese `min <= ... <= max` merece explicarse. Permitir interpolación dentro del rango citado es deliberado: si las fuentes dan 40 y 90, un 65 es una mezcla defendible, no una invención. Lo que se marca es la extrapolación fuera de rango, que es donde el modelo deja de combinar datos y empieza a inventarlos. Si tu dominio es más estricto y solo aceptas cifras que aparezcan literalmente en una fuente, endurece la condición; pero para estimaciones, donde combinar es legítimo, el rango es el ancla correcta. Esta capa, sola, ya caza la fabricación pura (sin soporte numérico) y la extrapolación (fuera de rango) sin gastar un token.

### **Verificación semántica: el juez, con sus límites**

El anclaje numérico no ve la atribución falsa: un 40 h citando un fragmento que habla de otra cosa pasa la comprobación aritmética si por casualidad el 40 está en el rango. Para eso hace falta mirar el significado, y ahí entra un verificador basado en modelo, instruido para ser estricto y para dudar a favor de "no soportado".

```python
class ClaimVerdict(BaseModel):
    component: str
    supported: bool
    reason: str
    confidence: float

VERIFY_INSTRUCTIONS = """\
You are a strict verifier of software estimate lines against their cited sources.
A claim is SUPPORTED only if the cited sources actually mention this component
and a figure consistent with the claim. A number present in no cited source is
NOT supported. Attributing a figure to a source that discusses a different
component is NOT supported. Do not be charitable: when in doubt, return supported=false.
"""

def verify_claim(line: SynthesizedComponent, cited_evidence: list[BudgetEvidence]) -> ClaimVerdict:
    response = client.responses.parse(
        model=settings.verifier_model,  # a cheaper, separate model from the generator
        input=[
            {"role": "system", "content": VERIFY_INSTRUCTIONS},
            {"role": "user", "content": render_verification_input(line, cited_evidence)},
        ],
        text_format=ClaimVerdict,
    )
    return response.output_parsed
```

Aquí hay que ser honesto sobre lo que es esto y lo que no. Usar un modelo para detectar las alucinaciones de otro modelo es circular: el verificador también puede alucinar, y puede declarar soportado lo que no lo está. No lo elimina el riesgo; lo reduce, y lo reduce por tres vías concretas. La primera, un esquema de veredicto estrecho, `supported` es un booleano, no una redacción libre donde esconder ambigüedad. La segunda, usar un modelo distinto y más barato que el generador, para que los dos no compartan exactamente los mismos puntos ciegos. La tercera, y la más importante, instruir al verificador para que dude en contra: ante la duda, no soportado. Un verificador permisivo es peor que no tener verificador, porque da una falsa sensación de seguridad.

### **Consistencia: barato no es, pero a veces vale**

Hay una tercera señal, independiente de las fuentes: la estabilidad. Si pides la misma cifra varias veces y el modelo devuelve 40, 42 y 38, está apoyado en algo; si devuelve 40, 110 y 70, está adivinando. La dispersión entre muestras es un indicador de cuánto se está inventando el modelo.

```python
def consistency_spread(transcript: str, component: str, n: int = 3) -> float:
    """Regenerate a single figure n times; high variance suggests guessing.

    Expensive (n generations). Reserve it for high-stakes or low-confidence
    lines, not for every figure in every estimate.
    """
    samples = [generate_single_figure(transcript, component) for _ in range(n)]
    mean = statistics.mean(samples)
    return statistics.pstdev(samples) / mean if mean else 0.0
```

El comentario del código no es opcional: la consistencia cuesta N generaciones por cifra, así que aplicarla a todo es inviable. Se reserva para las líneas de alto impacto o de baja confianza, donde el coste de equivocarse justifica el de comprobar. Y tiene una trampa conceptual que hay que tener muy presente: la consistencia confunde "el modelo adivina" con "los datos genuinamente discrepan". Un componente que de verdad va de 40 a 90 horas según el alcance producirá muestras dispersas, y eso *no* es una alucinación: es incertidumbre honesta, y el rango es la respuesta correcta. No castigues la duda legítima como si fuera invención. La dispersión es sospechosa cuando las fuentes coinciden y el modelo no; no cuando las fuentes ya discrepaban.

## **Mitigar: prevenir, validar, abstenerse**

Detectar es la mitad. La otra mitad es qué hacer, y empieza antes de generar.

**Prevenir** es lo más barato y lo más efectivo. Las instrucciones del generador deben prohibir explícitamente lo que no quieres: usar solo cifras presentes en la evidencia, marcar un componente como no fundamentado en lugar de inventarlo, no extrapolar más allá de las fuentes. El esquema estructurado ayuda, porque un campo `grounded` que el modelo tiene que rellenar lo obliga a posicionarse sobre cada cifra. Prevenir no elimina las alucinaciones, ningún prompt lo hace, pero reduce el volumen que llega a la detección, y eso abarata todo lo demás.

**Validar** es la red post-generación que combina las tres señales anteriores en una decisión por línea. Y la decisión no es binaria: es graduada, de más a menos estricta según lo que falle.

```python
class VerifiedLine(BaseModel):
    component: str
    low_hours: float | None
    high_hours: float | None
    status: Literal["grounded", "insufficient", "rejected"]
    confidence: float

def gate_line(
    line: SynthesizedComponent,
    evidence_by_id: dict[str, BudgetEvidence],
    verdict: ClaimVerdict,
) -> VerifiedLine:
    anchored = numeric_grounding(line, evidence_by_id)

    if anchored and verdict.supported:
        return VerifiedLine(
            component=line.component,
            low_hours=line.low_hours,
            high_hours=line.high_hours,
            status="grounded",
            confidence=verdict.confidence,
        )

    if not anchored and not verdict.supported:
        # No numeric anchor and the verifier rejects it: do not emit a figure.
        log.warning("ungrounded_line_dropped", component=line.component)
        return VerifiedLine(
            component=line.component,
            low_hours=None,
            high_hours=None,
            status="insufficient",
            confidence=0.0,
        )

    # Mixed signals: keep the figure but degrade confidence and flag for review.
    log.info("line_degraded", component=line.component, anchored=anchored, supported=verdict.supported)
    return VerifiedLine(
        component=line.component,
        low_hours=line.low_hours,
        high_hours=line.high_hours,
        status="grounded",
        confidence=min(verdict.confidence, 0.4),
    )
```

![art4-fig12-gate-line-matriz.jpg](https://media1-production-mightynetworks.imgix.net/asset/774e3dcb-9421-4621-bf86-66f4424feca4/art4-fig12-gate-line-matriz.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Abstenerse** es la salida honesta cuando una línea no se sostiene. El `status="insufficient"` no es un fallo del sistema: es el sistema haciendo lo correcto. Para un módulo del que no hay datos comparables, decir "no tengo presupuestos suficientes para estimar esto con fiabilidad" es infinitamente más valioso que inventar un número que alguien usará para comprometer un plazo. La abstención convierte una mentira confiada en una pregunta útil: el jefe de proyecto sabe ahora qué parte de la estimación necesita un experto humano, en lugar de descubrirlo cuando el plazo se incumple.

## **Trade-offs honestos**

**La detección añade latencia y coste, y nunca es completa.** Las tres capas juntas pueden duplicar el tiempo de respuesta y multiplicar las llamadas. Por eso se ordenan de barata a cara y se aplican de forma selectiva: el anclaje numérico a todo, el juez a lo que el anclaje no decide, la consistencia solo a lo crítico. Aun así, asumir que detectarás todas las alucinaciones es, en sí mismo, una alucinación. El objetivo es reducir la tasa a un nivel aceptable para el riesgo del dominio, no llegar a cero.

**El juez es un modelo, y los modelos alucinan.** Detectar alucinaciones con un LLM tiene un suelo de fiabilidad que no puedes superar solo añadiendo más LLM. El esquema estrecho, el modelo distinto y el sesgo hacia "no soportado" bajan el riesgo, pero un verificador no es una garantía: es otra capa probabilística. Cuando el coste de un error es muy alto, la última verificación sigue siendo un humano.

**La consistencia castiga la incertidumbre honesta si no la calibras.** Es la trampa más fácil de pisar: marcar como alucinación un componente que legítimamente tiene un rango amplio. La dispersión solo es señal de invención cuando contradice fuentes que coincidían. Si las fuentes ya discrepaban, la dispersión es la verdad, no el error.

**Abstenerse de más vuelve el sistema inútil.** Un estimador que responde "datos insuficientes" a la mitad de los componentes no lo usa nadie. La abstención tiene que estar calibrada al umbral correcto: abstenerse cuando algo está de verdad sin fundamentar, no cada vez que hay una pizca de duda. Para estimaciones, un falso "grounded" (una mentira confiada) suele ser más caro que un falso "insufficient" (utilidad perdida), pero ambos tienen coste, y empujar el umbral hacia la abstención total no es prudencia: es renunciar a hacer el trabajo.

**Prevenir en el prompt da rendimientos decrecientes.** Cada instrucción nueva contra alucinar ayuda menos que la anterior, y un prompt sobrecargado de prohibiciones empieza a degradar la calidad general de la generación. La prevención reduce el volumen, pero la detección post-generación es la que de verdad sostiene la garantía. No intentes resolver en el prompt lo que toca resolver verificando.

## **Lo que esto deja sin resolver**

Con esto, el sistema verifica cada estimación que produce: ancla las cifras a las fuentes, comprueba el significado con un juez estricto, mide la consistencia donde importa, y se abstiene en lugar de inventar cuando no hay fundamento. Para una estimación concreta, sabe línea a línea si puede confiar en ella.

Pero todas estas comprobaciones miran una respuesta cada vez. Te dicen si *esta* estimación está fundamentada; no te dicen si tu sistema está mejorando o empeorando. Si mañana cambias el prompt de generación, o el modelo verificador, o la forma de ensamblar el contexto, ¿la tasa de alucinaciones sube o baja? ¿La fidelidad media de las respuestas mejora, o acabas de introducir una regresión silenciosa que solo verás cuando un cliente se queje? La verificación por petición es un guardarraíl: impide que una respuesta mala salga. No es una medida: no te dice cómo de bueno es el sistema en conjunto, ni si una decisión de diseño lo ha hecho mejor o peor.

Saber eso, medir la calidad de la generación de forma sistemática, sobre un conjunto representativo, con números que puedas comparar entre versiones, es una disciplina distinta. Sin ella, cada cambio en el sistema es una apuesta a ciegas, por muy buenos que sean los guardarraíles de cada respuesta.