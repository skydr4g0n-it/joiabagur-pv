# Human-in-the-loop: interrupt, pausa y reanudación sobre el checkpointer

Creada: 20 de julio de 2026 21:11
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S14. Sistemas multi-agente y patrones avanzados (https://app.notion.com/p/S14-Sistemas-multi-agente-y-patrones-avanzados-3a3ea9ca03c4800f98e8fdae96ec7f6f?pvs=21)

Vuestro sistema de estimación acaba de producir 840 horas para un CRUD de tres entidades. En el histórico, un CRUD equivalente ha costado entre 120 y 200. Nadie va a mandar ese presupuesto a un cliente.

La pregunta no es cómo evitar que el sistema se equivoque —se va a equivocar, y lo interesante es que aquí *sabía* que algo iba mal: el validador tenía delante el rango histórico—. La pregunta es qué debe hacer el sistema cuando detecta que no está en condiciones de responder solo.

La respuesta fácil es un `if` que devuelva un error. La respuesta correcta es más incómoda: **el sistema tiene que detenerse, enseñarle lo que tiene a una persona, y esperar**.

Y esperar es lo difícil. Porque la persona puede tardar diez minutos o tres días. Vuestro proceso Python no puede quedarse ahí bloqueado con un `input()`. La ejecución tiene que morir y poder resucitar exactamente donde estaba, con el estado intacto, en otro proceso, quizá en otra máquina, después de un despliegue.

Eso no es una pausa. Es **persistencia**. Y resulta que ya la tenéis montada.

## **La pausa vive en el checkpointer**

Cuando montasteis el checkpointer sobre el Postgres del proyecto, lo hicisteis por una razón práctica: no perder el trabajo si algo fallaba a mitad del grafo. Esa infraestructura es, sin tocar una línea, el mecanismo completo de intervención humana.

El razonamiento es directo. El checkpointer persiste el estado del grafo después de cada nodo. Si el estado está persistido, la ejecución en memoria es prescindible: se puede tirar y reconstruir desde el checkpoint. Y si se puede reconstruir, se puede **parar indefinidamente y continuar más tarde**.

Un human-in-the-loop es exactamente eso: una parada que dura lo que tarde un humano.

```python
from langgraph.types import interrupt, Command

CONFIDENCE_THRESHOLD = 0.7

def human_review_gate(state: EstimationState) -> Command[Literal["finalize"]]:
    if not requires_human_review(state):
        return Command(goto="finalize")

    decision = interrupt(
        {
            "reason": build_review_reason(state),
            "estimate": state["estimate"],
            "confidence": state["confidence"],
            "budget_matches": state["budget_matches"],
        }
    )

    return Command(
        goto="finalize",
        update={
            "human_decision": decision,
            "estimate": apply_human_decision(state["estimate"], decision),
        },
    )
```

`interrupt()` no es un `sleep`. Lanza una excepción de control que LangGraph captura: el estado queda escrito en el checkpoint, la ejecución termina, y el `invoke` que lanzasteis os devuelve el control con la información de la interrupción. El proceso queda libre. Y cuando la decisión humana llegue —dentro de un minuto o de una semana— se reanuda desde ese punto exacto.

El payload que le pasáis a `interrupt()` es lo que verá la persona. Ponedlo con cuidado: no es un log, es **la interfaz**. Un revisor al que le enseñáis un `confidence: 0.42` y nada más no puede decidir nada. Un revisor al que le enseñáis la estimación, el rango histórico con el que choca y los presupuestos análogos que el sistema encontró, puede.

### **Reanudar**

```python
config = {"configurable": {"thread_id": estimation_id}}

# First run: the graph may stop at the gate.
result = await graph.ainvoke({"transcript": transcript}, config)

# Later, once a human has decided:
result = await graph.ainvoke(Command(resume=human_decision), config)
```

El `thread_id` es la pieza que lo cose todo. Es el identificador con el que el checkpointer guardó el estado, así que **es lo que os permite volver**. Usad el `estimation_id` del dominio y no un UUID nuevo: el backend de negocio ya tiene ese identificador, ya lo muestra en su interfaz, y va a ser el mismo que use el revisor. Cuando ese `thread_id` sea también la clave de vuestras trazas, tendréis un identificador único que atraviesa las tres capas y una operación entera.

Fijaos en la simetría: `ainvoke` con un input arranca el grafo; `ainvoke` con un `Command(resume=...)` lo continúa. La misma función. No hay una API especial de reanudación, porque para LangGraph reanudar no es un caso especial: es lo que hace siempre, partiendo de un checkpoint que resulta que no está vacío.

## **Qué debe parar el grafo**

Aquí es donde se decide si vuestro human-in-the-loop es útil o es teatro.

![fig-01-contrato-hitl-tres-capas.png](https://media1-production-mightynetworks.imgix.net/asset/9255ba6b-cf55-40b5-954d-e72f52e7f51b/fig-01-contrato-hitl-tres-capas.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Las tres señales legítimas en estimación:

**Confianza baja.** El validador puntúa su propia certeza. Esto no es un número que aparezca por arte de magia: se lo pedís explícitamente, con un esquema, y le dais criterios para producirlo.

```python
class ValidationResult(BaseModel):
    is_coherent: bool
    confidence: float = Field(ge=0.0, le=1.0)
    concerns: list[str]
    reasoning: str
```

**Fuera de rango histórico.** Esta ni siquiera necesita un modelo. Tenéis presupuestos históricos indexados; sabéis lo que ha costado un CRUD. Si la estimación se sale de la banda por un factor grande, es una comparación aritmética.

**Sin precedente.** Si ningún presupuesto análogo supera el umbral de similitud, el sistema está estimando a ciegas. No es que se haya equivocado: es que no tiene base sobre la que acertar.

```python
def requires_human_review(state: EstimationState) -> bool:
    validation = state["validation"]
    estimate = state["estimate"]

    low_confidence = validation["confidence"] < CONFIDENCE_THRESHOLD
    out_of_range = is_outside_historical_band(estimate, state["budget_matches"])
    no_precedent = len(state["budget_matches"]) == 0

    return low_confidence or out_of_range or no_precedent
```

**La regla que hay debajo:** una señal de disparo es una **condición evaluable sobre el estado**. Si no la podéis escribir como un booleano, no es una señal: es una intuición. Y las intuiciones no se pueden testear, no se pueden ajustar y no se pueden explicar a un cliente.

### **Y qué no debe pararlo**

Tres antipatrones que veréis en producción, los tres disfrazados de prudencia.

**Un agente ha fallado.** Eso no es una revisión, es un error. Un fallo de una tool, un timeout o un JSON mal formado se resuelven con reintento, fallback o degradación. Si mandáis los errores a un humano, habéis convertido a vuestro revisor en un servicio de reintentos manual, y el día que caiga la API del proveedor le vais a llenar la bandeja con doscientos casos idénticos.

La distinción es limpia: **el error es que el sistema no pudo hacer su trabajo; la revisión es que el sistema hizo su trabajo y el resultado necesita juicio.**

**Revisar por si acaso.** La tentación de poner el umbral alto "hasta que confiemos". Si el 80% de las estimaciones pasan por revisión, el revisor no revisa: aprueba en automático, en bloque, sin mirar. Habéis construido una interfaz elaborada para que alguien pulse "aceptar" cuarenta veces seguidas, y encima habéis destruido la señal, porque cuando llegue el caso que de verdad importaba, llegará indistinguible del resto. **Si todo se revisa, nada se revisa.** Un human-in-the-loop que dispara en el 5% de los casos vale más que uno que dispara en el 60%.

**Una regla de negocio dura.** Si vuestra empresa exige que un socio apruebe cualquier presupuesto por encima de 50.000 euros, eso es un flujo de aprobación, y su sitio es el backend de negocio. No lo metáis en el grafo. El gate del servicio IA existe para un caso concreto y distinto: **cuando el sistema de IA sabe que no sabe**.

## **El contrato: la pausa cruza las tres capas**

Y aquí llega la parte que casi todos los tutoriales se saltan, porque en un notebook la reanudación es la siguiente celda.

En vuestro sistema no. La pausa ocurre en el **servicio IA**. La persona decide en el **frontend**. Y en medio está el **backend de negocio**, que es quien tiene usuarios, permisos y persistencia. Esa pausa es la primera cosa en todo el programa que **modifica el contrato** entre las capas.

![fig-02-senales-de-disparo.png](https://media1-production-mightynetworks.imgix.net/asset/08aabca2-6ef2-48b8-b1eb-3e50be6e1c66/fig-02-senales-de-disparo.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La superficie mínima son dos cosas: un estado nuevo en la respuesta, y un endpoint para volver.

```python
@router.post("/estimations")
async def create_estimation(payload: EstimationRequest) -> EstimationResponse:
    config = {"configurable": {"thread_id": payload.estimation_id}}
    result = await graph.ainvoke({"transcript": payload.transcript}, config)

    if interrupts := result.get("__interrupt__"):
        return EstimationResponse(
            estimation_id=payload.estimation_id,
            status="awaiting_human_review",
            review_payload=interrupts[0].value,
            estimate=None,
        )

    return EstimationResponse(
        estimation_id=payload.estimation_id,
        status="completed",
        estimate=result["estimate"],
    )

@router.post("/estimations/{estimation_id}/resume")
async def resume_estimation(
    estimation_id: str, payload: HumanDecision
) -> EstimationResponse:
    config = {"configurable": {"thread_id": estimation_id}}
    result = await graph.ainvoke(Command(resume=payload.model_dump()), config)

    return EstimationResponse(
        estimation_id=estimation_id,
        status="completed",
        estimate=result["estimate"],
    )
```

El campo `status` no es nuevo: ya estaba en vuestro contrato. Lo único que hacéis es añadirle un valor posible. Ese detalle importa más de lo que parece — significa que el backend de negocio no necesita una integración nueva, solo una rama nueva sobre un campo que ya leía. La arquitectura no cambia; se extiende.

Del lado del backend de negocio, en la referencia Rails (el patrón es idéntico con cualquier cliente HTTP):

```python
class EstimationsController < ApplicationController
  def create
    response = AiService.create_estimation(
      estimation_id: @estimation.id,
      transcript: @estimation.transcript
    )

    case response["status"]
    when "awaiting_human_review"
      @estimation.update!(
        status: :awaiting_review,
        review_payload: response["review_payload"]
      )
      ReviewMailer.with(estimation: @estimation).pending_review.deliver_later
    when "completed"
      @estimation.update!(status: :completed, estimate: response["estimate"])
    end
  end

  def resume
    authorize! :approve, @estimation

    response = AiService.resume_estimation(
      estimation_id: @estimation.id,
      decision: decision_params
    )

    @estimation.update!(status: :completed, estimate: response["estimate"])
  end
end
```

Fijaos en dónde vive cada responsabilidad. El `authorize!` está en el backend de negocio, porque es quien tiene usuarios y roles: **el servicio IA no sabe quién es un revisor autorizado y no tiene por qué saberlo**. La notificación, la bandeja, el histórico de quién aprobó qué: todo eso es negocio. El servicio IA solo sabe pausar y reanudar.

Esa separación no es purismo. Es lo que hace que el día que cambiéis la política de aprobación —que ahora hagan falta dos revisores, o que un junior no pueda aprobar por encima de cierto importe— no tengáis que tocar el grafo.

## **Lo que os va a morder**

**El nodo se reejecuta desde el principio al reanudar.** Este es el que más caro sale y el que menos se documenta. Cuando reanudáis, LangGraph **no** continúa justo después del `interrupt()`: vuelve a ejecutar el nodo entero desde su primera línea, y esta vez `interrupt()` devuelve el valor en lugar de detener. Consecuencia: **todo lo que hicierais antes del** `interrupt()` **dentro de ese nodo se ejecuta dos veces**. Si ahí dentro habíais llamado al modelo, lo pagáis dos veces. Si habíais insertado una fila en base de datos, la insertáis dos veces.

La regla, entonces: **el nodo que interrumpe no hace nada más que interrumpir**. Nada de efectos laterales antes del `interrupt()`. Cualquier trabajo real va en un nodo anterior; el gate solo evalúa una condición y para.

**Reanudaciones huérfanas.** ¿Qué pasa si nadie decide nunca? El checkpoint se queda ahí, ocupando sitio, y la estimación cuelga para siempre en `awaiting_human_review`. Necesitáis una política: un plazo, un escalado a otro revisor, o una caducidad que cierre el caso. No es una decisión del servicio IA —es de negocio— pero alguien tiene que tomarla, y si no la tomáis vosotros la va a descubrir un cliente.

**Doble reanudación.** Dos revisores abren la misma estimación y ambos pulsan aprobar. La segunda llamada a `resume` llega a un grafo que ya terminó. Vuestro endpoint tiene que ser idempotente, o el backend de negocio tiene que impedirlo con un bloqueo. Es el mismo problema del doble submit de un formulario, y se resuelve igual: no es un problema de IA.

**La decisión humana es el dato más valioso que produce vuestro sistema.** Cada vez que una persona corrige una estimación, os está diciendo exactamente en qué se equivoca el modelo, sobre un caso real, con la respuesta correcta al lado. Ese par —lo que el sistema propuso, lo que el humano decidió— es oro: para ajustar umbrales, para entender qué transcripciones os dan problemas, y como material de evaluación. Guardadlo desde el primer día, aunque todavía no sepáis qué vais a hacer con él. Es gratis ahora y es irrecuperable después.

## **Lo que queda**

Con esto el sistema sabe parar. Sabe que no sabe, se lo dice a alguien, y espera con el estado a salvo.

Pero hay una asimetría rara en lo que hemos construido. Hemos sido muy cuidadosos decidiendo cuándo el sistema **no debe decidir solo**, y no hemos dedicado ni un párrafo a lo que cada agente **puede hacer** cuando decide solo.

Vuestros agentes tienen herramientas en la mano. Consultan bases de datos. Y en cuanto alguien añada la tool que faltaba —la que escribe, la que envía, la que borra— la pregunta de arquitectura se convierte en otra: **qué puede tocar cada agente, y qué pasa si intenta tocar lo que no debe**.