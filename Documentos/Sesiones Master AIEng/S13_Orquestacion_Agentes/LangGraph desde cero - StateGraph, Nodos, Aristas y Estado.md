# LangGraph desde cero: StateGraph, nodos, aristas y estado

Creada: 16 de julio de 2026 17:43
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S13. Orquestación de Agentes (https://app.notion.com/p/S13-Orquestaci-n-de-Agentes-39fea9ca03c480a9b543f627044858ef?pvs=21)

El flujo de estimación, contado como una lista de pasos, es sencillo de enunciar: de la transcripción de una reunión se extraen los requisitos; los requisitos se agrupan en componentes; para cada componente se buscan presupuestos de referencia; con esos presupuestos se genera una estimación; y por último la estimación se valida y se consolida. Cinco pasos, cada uno con una responsabilidad clara.

Enunciarlo es fácil; expresarlo en código de forma que siga siendo legible cuando haya ramas y paralelismo, no tanto. Un bucle imperativo funciona, pero mezcla en el mismo sitio el trabajo de cada paso y la lógica de qué va después de qué. LangGraph separa esas dos cosas: **el trabajo vive en los nodos, el control vive en las aristas, y el dato vive en un estado compartido**. Este artículo construye ese modelo desde cero sobre el flujo de estimación.

## **Cuatro primitivas y nada más**

El modelo de LangGraph es deliberadamente pequeño. Son cuatro piezas:

- **Estado**: un objeto compartido y tipado que todos los nodos leen y actualizan.
- **Nodo**: una función que recibe el estado y devuelve una actualización parcial de ese estado.
- **Arista**: la conexión entre nodos. Las aristas directas fijan una secuencia; las condicionales deciden a dónde ir mirando el estado.
- **Checkpointer**: persiste el estado tras cada paso (lo tratamos aparte; aquí basta con saber que existe).

`StateGraph` es el constructor que junta las tres primeras. Lo instancias con un esquema de estado, le añades nodos, dibujas las aristas, fijas el punto de entrada y lo compilas. El resultado es un grafo ejecutable.

## **El estado: la decisión más consecuente**

En un proyecto LangGraph, el diseño del esquema de estado es la decisión de más peso. Todo lo demás, qué hace cada nodo, cómo se enrutan las aristas, se lee y se escribe contra ese objeto. Un esquema mal pensado se paga en cada nodo.

El estado es un `TypedDict` (también admite Pydantic o dataclasses; elige uno y sé consistente). Para el flujo de estimación:

```python
from typing import Annotated, Optional, TypedDict
import operator

class Component(TypedDict):
    name: str
    category: str

class BudgetMatch(TypedDict):
    component: str
    reference_budget_id: str
    amount: float

class EstimationState(TypedDict):
    transcript: str
    requirements: list[str]
    components: list[Component]

    # Accumulator: each search appends its matches.
    budget_matches: Annotated[list[BudgetMatch], operator.add]

    estimate: Optional[dict]

    # "validated" | "needs_review"
    status: Optional[str]

    errors: Annotated[list[str], operator.add]
```

La clave está en los campos anotados. Por defecto, cuando un nodo devuelve un valor para un campo, ese valor **sobrescribe** lo que hubiera. Es lo que quieres para `status` o `estimate`: el último valor manda. Pero para `budget_matches` no quieres sobrescribir: quieres **acumular**, porque cada búsqueda aporta sus resultados y todos deben sumarse. Eso es un **reducer**. `Annotated[list[BudgetMatch], operator.add]` le dice a LangGraph que, cuando un nodo devuelva `budget_matches`, en lugar de reemplazar la lista la concatene con la existente. El reducer `operator.add` es el que hace que la ejecución en paralelo tenga sentido: varias ramas pueden escribir a la vez sin pisarse.

Una disciplina que ahorra disgustos: **mantén el estado ligero**. Todo lo que hay en el estado se serializa en cada transición entre nodos. Si metes ahí respuestas crudas del modelo con sus metadatos, el objeto de estado engorda y la persistencia se convierte en el cuello de botella. Guarda identificadores y datos ya destilados; lo transitorio, déjalo en el ámbito de la función.

![S13-fig-02a-flujo-grafo.jpg](https://media1-production-mightynetworks.imgix.net/asset/939c6364-750d-40d9-a40b-7f35c5a6e666/S13-fig-02a-flujo-grafo.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Los nodos: funciones puras que devuelven un trozo de estado**

Un nodo es una función normal de Python. Recibe el estado y devuelve un diccionario con **solo los campos que cambia**, no el estado entero. Trátalo como una función pura: no mutes lo que recibes, devuelve la actualización. Eso hace los nodos triviales de testear y mantiene el enrutado predecible.

```python
def classify_components(state: EstimationState) -> dict:
    components = group_requirements_into_components(
        state["requirements"]
    )

    return {
        "components": components,
    }

def search_budgets(state: EstimationState) -> dict:
    matches: list[BudgetMatch] = []

    for component in state["components"]:
        matches.append(
            retrieve_reference_budget(component)
        )

    # Only the changed field is returned;
    # the reducer merges it in.
    return {
        "budget_matches": matches,
    }
```

Cada nodo reutiliza la lógica de dominio que ya existe en el servicio IA, la recuperación sobre la base vectorial, el cálculo determinista de la estimación, envuelta en esta forma. El nodo no orquesta: hace su trabajo y devuelve su trozo de estado. Quién va después lo deciden las aristas.

## **Las aristas: secuencia fija y decisiones**

Las aristas directas fijan el orden cuando el orden es fijo. Las condicionales enrutan cuando hay que decidir. `START` y `END` son los centinelas de entrada y salida del grafo.

```python
from langgraph.graph import StateGraph, START, END

def route_after_validation(state: EstimationState) -> str:
    # A routing function inspects the state
    # and returns the next node's name.
    return END if state["status"] == "validated" else "flag_for_review"

builder = StateGraph(EstimationState)

builder.add_node(
    "extract_requirements",
    extract_requirements,
)

builder.add_node(
    "classify_components",
    classify_components,
)

builder.add_node(
    "search_budgets",
    search_budgets,
)

builder.add_node(
    "generate_estimate",
    generate_estimate,
)

builder.add_node(
    "validate_and_consolidate",
    validate_and_consolidate,
)

builder.add_node(
    "flag_for_review",
    flag_for_review,
)

builder.add_edge(
    START,
    "extract_requirements",
)

builder.add_edge(
    "extract_requirements",
    "classify_components",
)

builder.add_edge(
    "classify_components",
    "search_budgets",
)

builder.add_edge(
    "search_budgets",
    "generate_estimate",
)

builder.add_edge(
    "generate_estimate",
    "validate_and_consolidate",
)

# Conditional edge: the routing function decides
# where validation leads.
builder.add_conditional_edges(
    "validate_and_consolidate",
    route_after_validation,
)

builder.add_edge(
    "flag_for_review",
    END,
)

graph = builder.compile()
```

La función de enrutado es el mecanismo de todo el control dinámico: inspecciona el estado y devuelve el nombre del siguiente nodo. Aquí decide si la estimación validada termina o si se desvía a un nodo que la marca para revisión. Ese mismo mecanismo, una función que mira el estado y elige, es lo que después soporta reintentos, ciclos y bifurcaciones más ricas.

Compilar cierra el diseño y produce un grafo ejecutable. A partir de ahí se invoca (de forma síncrona o asíncrona), se puede transmitir en streaming y se puede persistir. El estado tipado que definiste es el contrato que atraviesa toda la ejecución.

![S13-fig-02b-anatomia-nodo.jpg](https://media1-production-mightynetworks.imgix.net/asset/a35e4940-73db-4312-99a1-329bbcde392c/S13-fig-02b-anatomia-nodo.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **El coste del diseño previo**

Hay un trade-off honesto en todo esto. Un bucle a mano lo escribes de un tirón; un grafo te obliga a decidir de antemano el esquema de estado, qué es un nodo y dónde va una arista condicional. Ese diseño previo es trabajo real, y para un flujo trivial es trabajo que no rinde.

La contrapartida es que ese diseño previo es exactamente lo que te da el control después. Un par de reglas mantienen el grafo sano. Reducers, solo donde de verdad necesitas acumular; para lo demás, sobrescritura simple. Aristas condicionales, solo en los puntos de decisión reales, no en cada transición. Y estado mínimo, tipado y validado, porque cada byte se serializa en cada paso. Un grafo que respeta esto se lee de un vistazo y se depura por nodo; uno que mete lógica de más en el estado o ramas donde no hacían falta pierde justo la ventaja por la que se adoptó.

## **El siguiente paso**

Con esto, el flujo de estimación deja de ser un bucle que hay que leer con cuidado y pasa a ser una estructura explícita: un estado tipado, cinco nodos con responsabilidad propia y unas aristas que dicen, sin ambigüedad, qué va después de qué. Esa estructura es visible y se razona sola. Lo que falta para que aguante en producción es que ese estado no viva solo en memoria: que se persista tras cada paso, que sobreviva a un reinicio y que distinga entre lo que dura una sesión y lo que dura para siempre. Ese es el terreno del checkpointer y la memoria.

## **Resumen**

- **LangGraph separa trabajo, control y dato:** los nodos hacen el trabajo, las aristas deciden el control, el estado compartido lleva el dato.
- **El esquema de estado es la decisión de más peso.** Es un `TypedDict`; los reducers deciden cómo se combinan las actualizaciones. `operator.add` acumula (imprescindible para el paralelismo); por defecto se sobrescribe.
- **Un nodo es una función pura** que recibe el estado y devuelve solo los campos que cambia. Fácil de testear, enrutado predecible.
- **Las aristas directas fijan la secuencia; las condicionales enrutan** con una función que inspecciona el estado y devuelve el nombre del siguiente nodo. `START` y `END` son los centinelas.
- **Compilar produce un grafo ejecutable** con el estado tipado como contrato de toda la ejecución.
- **El diseño previo es el coste y también la ventaja.** Reducers solo donde acumulas, aristas condicionales solo en decisiones reales, estado mínimo: así el grafo se lee de un vistazo y se depura por nodo.

## **Referencias**

- LangGraph - StateGraph, nodos, aristas y estado (documentación oficial): `https://docs.langchain.com/oss/python/langgraph`
- LangGraph - reducers y esquema de estado: `https://docs.langchain.com/oss/python/langgraph/graph-api`
- Buenas prácticas de diseño de estado y aristas en LangGraph: `https://www.swarnendu.de/blog/langgraph-best-practices/`