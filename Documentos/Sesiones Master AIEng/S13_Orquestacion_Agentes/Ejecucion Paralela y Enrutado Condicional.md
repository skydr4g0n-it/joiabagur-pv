# Ejecución paralela y enrutado condicional

Creada: 16 de julio de 2026 17:56
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S13. Orquestación de Agentes (https://app.notion.com/p/S13-Orquestaci-n-de-Agentes-39fea9ca03c480a9b543f627044858ef?pvs=21)

De los cinco pasos del flujo de estimación, hay uno que arrastra al resto: la búsqueda de presupuestos. Recorre los componentes uno a uno y, para cada uno, hace una recuperación sobre la base vectorial. Si un proyecto tiene ocho componentes, son ocho recuperaciones en fila, cada una esperando a que termine la anterior. El resto de nodos son rápidos; este es el que marca el tiempo total.

Y lo curioso es que ese trabajo no tiene por qué ser secuencial. Buscar el presupuesto del componente A no depende del resultado de buscar el del componente B: son tareas independientes. Cuando el trabajo es independiente, ejecutarlo en serie es una decisión que se paga en latencia sin recibir nada a cambio. Este artículo trata las dos herramientas que el grafo pone para esto: **ejecutar en paralelo lo que es independiente** y **enrutar según lo que el estado va diciendo**.

## **Fan-out con la Send API**

El patrón para paralelizar trabajo por elemento es el **fan-out**: en lugar de un nodo que recorre la lista, se despacha una rama de ejecución por cada elemento, todas a la vez. LangGraph lo expresa con la **Send API**.

La idea es dividir `search_budgets` en dos piezas. Una función de despacho que, dada la lista de componentes, emite un `Send` por cada uno hacia un nodo trabajador. Y un nodo trabajador que procesa **un solo** componente. LangGraph ejecuta todos los `Send` en paralelo.

```python
from langgraph.types import Send

def fan_out_budget_search(state: EstimationState) -> list[Send]:
    """One parallel branch per component."""
    return [
        Send(
            "search_one_budget",
            {"component": component},
        )
        for component in state["components"]
    ]

def search_one_budget(payload: dict) -> dict:
    match = retrieve_reference_budget(payload["component"])

    # Return only the accumulator field;
    # the reducer concatenates all branches.
    return {
        "budget_matches": [match],
    }
```

El despacho se conecta como una arista condicional que sale del nodo de clasificación, y el trabajador enlaza con el nodo de estimación:

```python
builder.add_conditional_edges(
    "classify_components",
    fan_out_budget_search,
    ["search_one_budget"],
)

builder.add_edge(
    "search_one_budget",
    "generate_estimate",
)
```

Aquí es donde el reducer del artículo anterior deja de ser un detalle y pasa a ser lo que hace posible el paralelismo. Cada rama devuelve `{"budget_matches": [match]}`. Si `budget_matches` fuera un campo de sobrescritura, las ramas se pisarían y solo sobreviviría el último resultado. Como está anotado con `operator.add`, LangGraph **concatena** las salidas de todas las ramas en una sola lista. Ese es el **fan-in**: las ramas convergen y el reducer las funde. El nodo de estimación se ejecuta una sola vez, cuando todas las ramas han terminado, con todos los presupuestos ya reunidos.

El impacto es directo: ocho recuperaciones que antes iban en fila ahora ocurren a la vez, y el tiempo de ese paso pasa de ser la suma de todas a ser, aproximadamente, la más lenta de ellas. En flujos con recuperaciones independientes, esta es de las optimizaciones con mejor relación entre esfuerzo y resultado.

![S13-fig-04b-condicional-ciclos_1.jpg](https://media1-production-mightynetworks.imgix.net/asset/06ef23b7-a1b8-4bac-81dd-e927a70eba22/S13-fig-04b-condicional-ciclos_1.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Aristas condicionales: enrutar según el estado**

El paralelismo resuelve el "hacer varias cosas a la vez". El enrutado condicional resuelve el "decidir qué va después". Una arista condicional es una función que **inspecciona el estado y devuelve el nombre del siguiente nodo**. Es el mismo mecanismo que despacha el fan-out, usado ahora para bifurcar.

En el flujo de estimación, el punto de decisión natural es la validación. Si la estimación pasa, el flujo termina; si no, se desvía a un nodo que la marca para revisión:

```python
from langgraph.graph import END

def route_after_validation(state: EstimationState) -> str:
    return END if state["status"] == "validated" else "flag_for_review"

builder.add_conditional_edges(
    "validate_and_consolidate",
    route_after_validation,
)
```

La función de enrutado no llama al modelo ni hace trabajo: solo lee el estado y decide. Esa separación —el trabajo en los nodos, la decisión en las aristas— es lo que mantiene el grafo legible. Una consecuencia práctica: pon aristas condicionales solo en los puntos de decisión reales. Si cada transición se convierte en una función de enrutado, el grafo pierde justo la claridad por la que se adoptó.

## **Ciclos, pero acotados**

Las aristas condicionales permiten algo que un pipeline lineal no permitía: **volver atrás**. Si la validación falla, en lugar de terminar podrías reenrutar hacia un paso anterior para reintentar con otros parámetros. Los ciclos son normales y útiles en sistemas agénticos.

El peligro es obvio: un ciclo sin freno es un bucle infinito, y en un flujo que llama a un modelo, un bucle infinito es una factura infinita. Por eso todo ciclo necesita un tope explícito. LangGraph trae un límite global de recursión que corta la ejecución si se dispara, una red de seguridad que evita el bucle desbocado:

```python
config = {
    "configurable": {
        "thread_id": estimation_id,
    },
    "recursion_limit": 25,
}

result = await graph.ainvoke(
    {"transcript": transcript},
    config,
)
```

Ese límite es la última línea de defensa, no la estrategia. La estrategia es acotar el ciclo en tu propia lógica: un contador de intentos en el estado, y una función de enrutado que, superado el tope, deja de reintentar y desvía a revisión.

```python
from langgraph.graph import END

def route_after_validation(state: EstimationState) -> str:
    if state["status"] == "validated":
        return END

    if state["retry_count"] >= 2:
        # Give up cleanly after two attempts.
        return "flag_for_review"

    # Bounded retry.
    return "generate_estimate"
```

Así el ciclo tiene una salida garantizada por diseño, no solo por la red de seguridad del framework.

![S13-fig-04b-condicional-ciclos.jpg](https://media1-production-mightynetworks.imgix.net/asset/f80b1f9e-3085-45cc-82ca-8a42ae8e3842/S13-fig-04b-condicional-ciclos.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **El coste del paralelismo**

Paralelizar no sale gratis en complejidad, aunque el código parezca sencillo. El coste está en el **merge del estado**. En cuanto varias ramas escriben a la vez, tienes que garantizar que sus salidas se combinan de forma predecible, y eso impone dos disciplinas.

La primera: los campos que reciben escrituras concurrentes **tienen que** ser acumuladores. Un campo de sobrescritura bajo paralelismo es un bug esperando a ocurrir, porque el resultado depende de qué rama terminó última. La segunda: cada rama debe consumir una entrada compatible y devolver la misma forma que el agregador espera. Si una rama devuelve algo con una estructura distinta, el fan-in se rompe o, peor, se combina de forma silenciosamente incorrecta. La regla que resume ambas: mantén la salida del trabajador mínima y confinada al campo acumulador. Un trabajador que solo devuelve `{"budget_matches": [match]}` es trivial de combinar; uno que además toca `status` o `estimate` mete condiciones de carrera donde no las había.

Es el mismo principio de siempre, estado mínimo y bien tipado, visto ahora bajo la lente de la concurrencia. El paralelismo premia a los grafos con estado limpio y castiga a los que arrastran campos de más.

## **El siguiente paso**

Con el fan-out, el paso más lento del flujo deja de marcar el tiempo total; con las aristas condicionales, el grafo decide su camino según lo que el estado dice; y con los ciclos acotados, puede reintentar sin desbocarse. El flujo ya es rápido y flexible. Lo que aún no es, es robusto: falta decidir qué ocurre cuando una de esas ramas paralelas falla, cuando una recuperación agota su tiempo o cuando un nodo lanza una excepción a mitad de camino. Enrutar el camino feliz es una cosa; sostener el flujo cuando algo se rompe es otra, y es el siguiente terreno.

## **Resumen**

- **El fan-out paraleliza el trabajo independiente.** La Send API despacha una rama por elemento; el nodo trabajador procesa uno solo. Las recuperaciones por componente pasan de ir en fila a ocurrir a la vez.
- **El reducer hace posible el fan-in.** `operator.add` concatena las salidas de todas las ramas en una lista; el nodo siguiente se ejecuta una vez, con todo reunido. Sin acumulador, las ramas se pisan.
- **Una arista condicional lee el estado y devuelve el siguiente nodo.** El trabajo vive en los nodos, la decisión en las aristas. Úsalas solo en puntos de decisión reales.
- **Los ciclos deben ir acotados.** El límite de recursión de LangGraph es la red de seguridad; la estrategia es un contador en el estado y una función de enrutado que abandona limpiamente tras N intentos.
- **El coste del paralelismo es el merge del estado.** Campos concurrentes acumuladores, salidas de forma compatible, trabajador mínimo. Estado limpio se paraleliza bien; estado gordo mete condiciones de carrera.

## **Referencias**

- LangGraph — Send API y ejecución en paralelo (map / fan-out): `https://docs.langchain.com/oss/python/langgraph/graph-api`
- LangGraph — aristas condicionales y límite de recursión: `https://docs.langchain.com/oss/python/langgraph/graph-api`
- Buenas prácticas de fan-out, aristas y ciclos acotados: `https://www.swarnendu.de/blog/langgraph-best-practices/`