# Patrones de comunicación entre agentes: estado compartido, handoff y mensajes

Creada: 20 de julio de 2026 21:10
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S14. Sistemas multi-agente y patrones avanzados (https://app.notion.com/p/S14-Sistemas-multi-agente-y-patrones-avanzados-3a3ea9ca03c4800f98e8fdae96ec7f6f?pvs=21)

Hay una decisión en vuestra arquitectura multi-agente que probablemente no recordáis haber tomado: **cómo se comunican los agentes entre sí**.

No la recordáis porque no la tomasteis. Vino de regalo con el framework. Cuando definisteis un `EstimationState` tipado y pusisteis a cada agente a escribir su parcial en él, elegisteis un patrón de comunicación —uno bueno, con nombre propio y cincuenta años de historia— sin llegar a nombrarlo.

Conviene nombrarlo. Porque en cuanto el sistema crece, esa elección invisible empieza a tener consecuencias muy visibles: en la factura, en el acoplamiento entre agentes y en vuestra capacidad de entender una traza.

Hay tres patrones. Los tres son legítimos. Y el orden en que os los vais a encontrar en producción es exactamente el orden en que aparecen aquí.

![fig-01-tres-patrones-comunicacion.png](https://media1-production-mightynetworks.imgix.net/asset/e3ee9232-7c88-4bd7-91db-3206878d1991/fig-01-tres-patrones-comunicacion.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **1. Estado compartido: la pizarra que ya tenéis**

El patrón se llama **blackboard**, y viene de la IA de los años setenta. La metáfora es literal: un grupo de especialistas frente a una pizarra. Ninguno le habla a otro. Cada uno mira lo que hay escrito, ve si puede aportar algo, y escribe su contribución. La solución emerge de las escrituras sucesivas.

Vuestro `EstimationState` **es** la pizarra:

```python
class EstimationState(TypedDict):
    transcript: str
    requirements: list[str]
    budget_matches: Annotated[list[dict], operator.add]
    estimate: dict | None
    validation: dict | None
    confidence: float | None
```

El `budget_searcher` no le pasa nada al `estimate_generator`. Escribe en `budget_matches` y se va. El generador, cuando le toca, lee `budget_matches` de la pizarra. Están completamente desacoplados el uno del otro: **su único acoplamiento es al esquema del estado**.

Y ese acoplamiento —al esquema, no entre componentes— es exactamente el que sabéis gestionar. Es el mismo que tenéis entre servicios que comparten una base de datos, o entre un frontend y el contrato de una API. Añadir un agente nuevo no obliga a tocar ningún agente existente: solo a añadir un campo. Reordenar el flujo no rompe a nadie, porque nadie sabe quién va después.

### **El detalle que sí importa: los reducers**

La pizarra tiene una única pregunta difícil: **qué pasa cuando dos agentes escriben la misma clave**.

En un flujo estrictamente secuencial, nunca ocurre y el problema no existe. Pero en cuanto el supervisor lanza dos agentes en paralelo —cosa perfectamente razonable: buscar presupuestos para tres componentes independientes a la vez— tenéis dos escrituras concurrentes sobre `budget_matches`. Sin una política explícita, la última gana y la primera desaparece en silencio.

Por eso `budget_matches` está anotado:

```python
budget_matches: Annotated[list[dict], operator.add]
```

Esa anotación es el **reducer**: la función que decide cómo se combinan dos escrituras sobre la misma clave. Aquí, concatenar. Cada agente devuelve una actualización parcial y el framework las funde según la política que declarasteis.

La regla de diseño es simple y os va a ahorrar bugs raros: **para cada campo del estado, decidid conscientemente si acumula o sobrescribe**. Los campos que un solo agente produce una vez (`estimate`, `validation`) sobrescriben, y está bien. Los campos donde varios agentes o varias invocaciones aportan (`budget_matches`, `routing_trail`) acumulan. Un campo que debería acumular pero sobrescribe es una pérdida silenciosa de datos, y es de los bugs más difíciles de ver porque el sistema no falla: simplemente estima con menos evidencia de la que buscó.

### **La otra cara**

El blackboard tiene dos límites reales.

**El estado crece.** Todo lo que un agente pueda necesitar tiene que estar en el esquema. Con seis agentes y un flujo maduro, `EstimationState` empieza a parecerse a un objeto Dios: un tipo enorme del que cada agente usa el 15%. Es el mismo olor que un modelo ActiveRecord con cuarenta columnas donde cada caso de uso toca cuatro. Y la mitigación es la misma: proyecciones. Cada agente recibe la vista del estado que le corresponde, no el estado entero.

**Todo el mundo lo puede leer todo.** La pizarra es un espacio de lectura común. Si un agente maneja información sensible y otro no debería verla, el estado compartido no os protege por sí solo. Eso deja de ser una cuestión de comunicación y pasa a ser una de privilegio.

**Cuándo usarlo: por defecto.** Ya lo tenéis, es trazable, es barato y desacopla a los agentes entre sí. No lo cambiéis hasta que algo os obligue.

## **2. Handoff directo: cuando el centro es el cuello de botella**

En el patrón supervisor, el control siempre vuelve al centro. Agente → supervisor → agente → supervisor. Cada retorno al centro es una llamada al modelo cuyo único producto es una decisión de enrutado.

El **handoff** elimina ese viaje de vuelta. El agente que termina decide él mismo quién sigue y le pasa el testigo directamente. En el ecosistema esto se conoce como *swarm*, y el mecanismo en LangGraph es una tool que en lugar de devolver un dato devuelve un `Command`:

```python
from typing import Annotated

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command

def build_handoff_tool(*, target_agent: str, description: str):
    """A tool that transfers control instead of returning data."""

    @tool(f"handoff_to_{target_agent}", description=description)
    def handoff(
        task_brief: Annotated[str, "What the next agent must do, with all relevant context."],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        return Command(
            goto=target_agent,
            graph=Command.PARENT,
            update={
                "messages": [
                    ToolMessage(
                        content=f"Transferred to {target_agent}.",
                        tool_call_id=tool_call_id,
                    )
                ],
                "task_brief": task_brief,
            },
        )

    return handoff
```

Dos cosas que merecen entenderse bien.

`graph=Command.PARENT` es lo que hace que el salto escape del subgrafo del agente y aterrice en el grafo padre. Sin eso, el `goto` buscaría un nodo dentro del propio agente y no lo encontraría. Es el error número uno al implementar handoff a mano.

Y `task_brief` es la decisión de diseño de verdad. **¿Qué viaja en el testigo?** Si pasáis el historial de mensajes completo, el siguiente agente hereda todo el contexto —y todo el coste, y todo el ruido— del anterior. Si pasáis solo un brief que el agente que suelta el testigo redacta, tenéis un contexto limpio pero habéis introducido un cuello de botella semántico: **lo que no esté en el brief, no existe para el que viene**. Un requisito que el buscador consideró irrelevante y no mencionó es un requisito que el estimador jamás verá.

No hay respuesta universal. Hay una decisión explícita, y es vuestra. Lo que no podéis es no tomarla, porque el valor por defecto de casi todas las librerías —pasar todo el historial— es el que peor escala.

### **Lo que ganáis y lo que pagáis**

![fig-02-coste-enrutado-supervisor-vs-handoff.png](https://media1-production-mightynetworks.imgix.net/asset/e37f7ea8-dde9-4e15-8b87-b96518166068/fig-02-coste-enrutado-supervisor-vs-handoff.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Para una tarea que toca dos especialistas, el supervisor gasta cuatro llamadas al modelo (enrutar, trabajar, enrutar, trabajar). El handoff gasta dos: la decisión de enrutado viaja **dentro** de la llamada del agente, como una tool call más. A escala, esa diferencia es dinero y es latencia.

Lo que pagáis es **acoplamiento topológico**. En el patrón supervisor, un agente no sabe que existen los demás; solo sabe hacer su trabajo. Con handoff, cada agente necesita conocer a sus vecinos y tener una tool por cada destino posible. Añadir un agente nuevo obliga a decidir quién puede saltar hacia él y a tocar esos agentes. Habéis cambiado una estrella por una malla, y las mallas crecen mal.

Y pagáis en **trazabilidad**. Con supervisor, todas las decisiones de enrutado están en un sitio: el `routing_trail`. Con handoff, la decisión está repartida por los agentes, y reconstruir por qué el sistema acabó donde acabó exige recorrer los saltos.

**Cuándo usarlo:** cuando el enrutado central se ha convertido en el cuello de botella medible —de coste o de latencia— y las transiciones entre agentes son mayoritariamente locales y predecibles. No antes. El handoff se gana su sitio; no se elige por elegancia.

## **3. Mensajes: cuando los agentes dejan de compartir proceso**

Los dos patrones anteriores comparten una premisa que nadie enuncia: **todos los agentes viven en el mismo proceso**. Comparten memoria, comparten un objeto de estado, comparten una traza. Por eso `Command(goto=...)` funciona: hay un runtime que puede mover el control de un sitio a otro.

El patrón de mensajes rompe esa premisa. Un agente publica un evento; a quién le llegue, y cuándo, no es asunto suyo.

```python
# Sketch, not an implementation: the point is the shape of the contract.
await bus.publish(
    "estimation.requirements_extracted",
    {
        "estimation_id": estimation_id,
        "requirements": requirements,
        "correlation_id": correlation_id,
    },
)
```

Nadie llama a nadie. El que extrae requisitos no sabe que existe un buscador de presupuestos. Publica un hecho —*los requisitos han sido extraídos*— y sigue con su vida. Quien esté suscrito a ese hecho reaccionará. O no. O tres servicios distintos lo harán a la vez.

Esto os debería sonar mucho, porque no es una idea de IA. Es arquitectura orientada a eventos, la misma que lleváis años aplicando entre servicios. Y las propiedades son exactamente las que conocéis: desacoplamiento máximo, escalado independiente de cada consumidor, reintentos y colas de fallidos, resiliencia si un consumidor se cae.

También los costes que conocéis: **consistencia eventual** (el estado ya no es una foto coherente en un objeto, es lo que haya llegado hasta ahora), **trazabilidad distribuida** (hace falta un `correlation_id` y una herramienta que sepa coserlo todo), y **complejidad operativa** (un bus es infraestructura que hay que desplegar, monitorizar y mantener).

**Cuándo usarlo:** cuando los agentes dejan de ser funciones de un servicio y pasan a ser servicios. Si vuestros agentes tienen ciclos de vida distintos, se despliegan por separado, o los escribe otro equipo, la comunicación por mensajes deja de ser una opción exótica y pasa a ser la única sensata. Mientras vivan todos dentro del servicio IA —que es donde viven ahora— es infraestructura que os complica sin comprar nada.

## **La postura**

Los tres patrones no son alternativas del mismo nivel. Son **tres puntos de una escalera**, y subir un escalón sin necesitarlo es la forma más común de arruinar una arquitectura multi-agente.

- **Estado compartido** por defecto. Es lo que ya tenéis, tiene el mejor ratio de trazabilidad por unidad de complejidad, y desacopla a los agentes entre sí de la única forma que os importa. La mayoría de los sistemas se quedan aquí, y hacen bien.
- **Handoff** cuando el impuesto de enrutado sea un problema medido, no imaginado. Es un ahorro real de llamadas, comprado con acoplamiento topológico y trazas más difíciles.
- **Mensajes** cuando los agentes crucen la frontera del proceso. Aquí ya no estáis eligiendo un patrón de comunicación entre agentes: estáis eligiendo una arquitectura de sistemas distribuidos, con todo lo que eso arrastra.

Y —esto es lo importante— **son combinables**. Un supervisor sobre estado compartido dentro del servicio IA, que publica un evento cuando la estimación está lista para que el backend de negocio reaccione, es una arquitectura perfectamente coherente. La pregunta nunca es cuál es el mejor patrón, sino qué patrón corresponde a cada frontera del sistema.

## **Lo que ninguno de los tres resuelve**

Los tres patrones responden a la misma pregunta: cómo se pasan información los agentes. Ninguno responde a esta otra:

**¿Qué pasa cuando el sistema no debería decidir solo?**

Cuando la estimación sale disparada, cuando la transcripción describe algo sin precedente en el histórico, cuando la confianza es baja. En ese momento no hace falta que un agente hable con otro agente. Hace falta que el sistema **se detenga**, se lo enseñe a una persona, y espere.

Y una pausa que puede durar horas o días no es un patrón de comunicación. Es un problema de estado persistido y de contrato hacia el exterior.