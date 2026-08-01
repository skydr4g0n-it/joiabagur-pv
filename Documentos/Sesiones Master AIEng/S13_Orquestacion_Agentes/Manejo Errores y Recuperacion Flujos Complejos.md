# Manejo de errores y recuperación en flujos complejos

Creada: 16 de julio de 2026 18:03
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S13. Orquestación de Agentes (https://app.notion.com/p/S13-Orquestaci-n-de-Agentes-39fea9ca03c480a9b543f627044858ef?pvs=21)

El flujo de estimación ya es rápido y flexible: paraleliza lo independiente y decide su camino según lo que el estado va diciendo. Pero todo eso describe el camino feliz. En producción, el camino feliz es solo uno de los que ocurren. Una de las ramas paralelas de búsqueda puede fallar. Una recuperación puede agotar su tiempo contra una base lenta. Un nodo puede lanzar una excepción a mitad de ejecución porque el modelo devolvió algo inesperado. Enrutar cuando todo va bien es una cosa; sostener el flujo cuando algo se rompe es otra, y es la que separa un prototipo de un sistema.

La buena noticia es que un grafo con estado persistente parte de una posición fuerte para esto. La mala es que "manejar errores" no es una sola cosa: son varias estrategias distintas, y aplicar la equivocada al tipo de fallo equivocado es su propia fuente de problemas. Este artículo las separa.

## **Cada tipo de fallo pide una respuesta distinta**

Antes del código, la distinción que ordena todo: no todos los fallos son iguales, y meterlos en el mismo saco lleva a reintentar lo que no se va a arreglar solo, o a rendirse ante lo que un simple reintento habría resuelto.

Un **fallo transitorio,** un pico de latencia, un corte momentáneo de red, se arregla solo si lo intentas otra vez. La respuesta es reintentar con backoff. Una **dependencia caída** de forma persistente no se arregla reintentando: reintentar solo alarga la agonía y multiplica el coste. La respuesta es un camino de fallback y, si conviene, un circuit breaker que deje de golpear a la dependencia rota. Una **excepción en un nodo** detiene la ejecución, pero como el estado está persistido hasta el último nodo que sí terminó, no se pierde el trabajo: se reanuda desde ahí. Y un caso que no es un fallo técnico pero sí una parada: **baja confianza o ambigüedad**, donde lo correcto no es que el sistema decida solo, sino que pare y pregunte a un humano.

![S13-fig-05a-estrategias-fallo.jpg](https://media1-production-mightynetworks.imgix.net/asset/918ddd7c-47df-4a8c-b31b-b70c3767be8f/S13-fig-05a-estrategias-fallo.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Reintentos, timeouts y fallback**

Para los fallos transitorios, LangGraph permite adjuntar una política de reintento a un nodo. El framework reejecuta el nodo ante un fallo, con backoff exponencial, sin que tengas que escribir el bucle de reintento:

```python
from langgraph.types import RetryPolicy

builder.add_node(
    "search_one_budget",
    search_one_budget,
    retry_policy=RetryPolicy(
        max_attempts=3,
        backoff_factor=2.0,
    ),
)
```

Los timeouts son responsabilidad del nodo, porque el nodo es quien conoce la operación que puede colgarse. La clave es **degradar con gracia**: que una búsqueda que agota su tiempo no tumbe la estimación entera, sino que registre el hueco y deje que el flujo siga:

```python
import asyncio

async def search_one_budget(payload: dict) -> dict:
    try:
        match = await asyncio.wait_for(
            retrieve_reference_budget(payload["component"]),
            timeout=5.0,
        )

        return {
            "budget_matches": [match],
        }

    except asyncio.TimeoutError:
        # Degrade gracefully: record the gap,
        # do not kill the whole estimate.
        return {
            "errors": [
                f"Budget search timed out for component "
                f"{payload['component']['name']}"
            ]
        }
```

Fíjate en que el fallo se escribe en el campo de errores, que es un acumulador, no en una excepción que se propaga. La rama que falló aporta su hueco al estado, las demás aportan sus presupuestos, y el nodo de estimación recibe el conjunto con la información de qué falta. Ese es el patrón de **fallback**: cuando una pieza no está disponible, el flujo toma un camino alternativo en vez de morir. A nivel de dependencia externa, la extensión natural es el **circuit breaker**: si la base de recuperación falla repetidamente, dejas de llamarla durante un tiempo de enfriamiento y vas directo al camino degradado, en lugar de que cada estimación pague el coste de descubrir que sigue caída.

## **La puerta humana: interrupt**

Hay un tipo de parada que no se resuelve con más automatización. Cuando la estimación sale con baja confianza, presupuestos escasos, componentes que no casan bien con el histórico, la respuesta correcta no es que el sistema decida por su cuenta y siga, sino que **pare y le pregunte a una persona**. Para eso está `interrupt`.

`interrupt` pausa el grafo en mitad de un nodo, persiste el estado y expone un valor a quien invocó. La ejecución se queda esperando, indefinidamente si hace falta, hasta que alguien la reanuda con una decisión. Necesita un checkpointer, porque sin persistencia no hay dónde guardar el punto de pausa.

```python
from langgraph.types import interrupt

def validate_and_consolidate(state: EstimationState) -> dict:
    estimate = consolidate(state)

    if estimate["confidence"] >= CONFIDENCE_THRESHOLD:
        return {
            "estimate": estimate,
            "status": "validated",
        }

    # Low confidence: pause and ask a human before continuing.
    review = interrupt(
        {
            "reason": "low_confidence_estimate",
            "estimate": estimate,
        }
    )

    if review["action"] == "reject":
        return {
            "status": "needs_review",
        }

    return {
        "estimate": review.get("estimate", estimate),
        "status": "validated",
    }
```

La ejecución se reanuda pasando la decisión de la persona, que se convierte en el valor que devuelve `interrupt`:

```python
from langgraph.types import Command

result = await graph.ainvoke(
    Command(
        resume={
            "action": "approve",
        }
    ),
    config,
)
```

Un detalle que evita sorpresas: al reanudar, el nodo se vuelve a ejecutar desde el principio, y `interrupt` devuelve entonces el valor de la reanudación en lugar de volver a pausar. Es decir, el trabajo previo a `interrupt` se repite. Mantén ese trabajo barato e idempotente, y deja que lo caro viva después de la pausa.

![S13-fig-05b-puerta-humana.jpg](https://media1-production-mightynetworks.imgix.net/asset/ff77a7da-ef70-45f2-8a80-8f8067060413/S13-fig-05b-puerta-humana.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Automatizar todo o poner una puerta**

El trade-off honesto de este artículo no es técnico, es de criterio: ¿qué se resuelve solo y qué merece parar a un humano? Y la respuesta por defecto de mucha gente, automatizarlo todo, es tan equivocada como la contraria.

Automatizar todo falla en los casos donde el sistema no tiene la información para decidir bien: una estimación floja que se manda a un cliente como si fuera sólida es un problema de negocio, no un problema técnico que se arregle con otro reintento. Poner una puerta humana en cada paso falla por el lado opuesto: convierte un flujo que debía ser rápido en una cola de aprobaciones, y quema a la persona que tiene que aprobar cosas que el sistema resolvía perfectamente solo.

La regla que funciona es proporcional al coste del error. Los fallos transitorios y las degradaciones, cuyo peor caso es una estimación con un hueco anotado, se resuelven solos: reintento, fallback, circuit breaker. La puerta humana se reserva para el punto donde el coste de equivocarse es alto y el sistema no tiene certeza: la estimación de baja confianza que va a salir con el nombre de la empresa. Una puerta, en el sitio crítico, no diez repartidas por el flujo.

## **El siguiente paso**

Con reintentos para lo transitorio, fallback y circuit breakers para lo persistente, reanudación desde checkpoint para las excepciones y una puerta humana en el punto de baja confianza, el flujo ya no se cae a la primera: absorbe los fallos que puede y para donde debe. Pero hay una pregunta que todo esto deja abierta y que no se puede responder desde el código: ¿dónde está fallando de verdad, cuánto tarda cada nodo, cuánto cuesta cada estimación? Decidir qué hacer robusto, y comprobar que las estrategias funcionan, exige ver la ejecución por dentro. Ese es el último tramo: la observabilidad.

## **Resumen**

- **Cada tipo de fallo pide una respuesta distinta.** Transitorio → reintento con backoff. Dependencia caída → fallback y circuit breaker. Excepción → reanudar desde el último checkpoint. Baja confianza → puerta humana.
- **Los reintentos con backoff se declaran por nodo** con una política de reintento; el framework reejecuta sin que escribas el bucle.
- **Los timeouts viven en el nodo y degradan con gracia:** una búsqueda que expira registra el hueco en el acumulador de errores en vez de tumbar la estimación entera.
- `interrupt` **pausa, persiste y espera** una decisión humana; se reanuda con `Command(resume=...)`. Necesita checkpointer; el nodo se re-ejecuta al reanudar, así que el trabajo previo a la pausa debe ser barato e idempotente.
- **Ni automatizarlo todo ni una puerta en cada paso.** La puerta humana se reserva para el punto crítico de alto coste y baja certeza; lo demás se resuelve solo.

## **Referencias**

- LangGraph - políticas de reintento y tolerancia a fallos: `https://docs.langchain.com/oss/python/langgraph/graph-api`
- LangGraph - interrupts e intervención humana (human-in-the-loop): `https://docs.langchain.com/oss/python/langgraph/interrupts`
- Buenas prácticas de errores, ciclos y aprobación humana en LangGraph: `https://www.swarnendu.de/blog/langgraph-best-practices/`