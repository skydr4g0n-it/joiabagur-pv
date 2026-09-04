# Citación y atribución verificable

Creada: 27 de junio de 2026 11:54
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S11. RAG Avanzado - Generación y Calidad (https://app.notion.com/p/S11-RAG-Avanzado-Generaci-n-y-Calidad-38cea9ca03c48049a493d33b89499a1d?pvs=21)

La estimación que produce el sistema ya no es una cifra suelta. Cada componente llega con la lista de identificadores de los fragmentos de los que se derivó: `["fin-2024-07#c3", "ecom-2023-02#c1"]`. Es un buen principio. Pero un identificador no es una citación. El jefe de proyecto que recibe "módulo de pagos: 40 h" y, al lado, `fin-2024-07#c3` no sabe nada que no supiera antes: ese código no le dice de qué presupuesto sale, de qué año, ni qué línea exacta lo respalda. Y el sistema que consume la estimación tampoco puede comprobar nada con él si no resuelve a algo real.

Una citación que un humano no puede resolver y un sistema no puede verificar no es una citación: es decoración. Da una sensación de rigor, "mira, cita fuentes", sin aportar lo único que importa, que es poder ir a la fuente y comprobar que el número es de verdad. En un sistema de estimaciones esto no es un adorno académico. Es la diferencia entre "confía en mí" y "compruébalo tú mismo", y lo segundo es lo que hace que alguien comprometa horas y dinero apoyándose en la salida.

Este artículo trata de convertir esos identificadores en citaciones verificables: que resuelvan a una fuente real, que apunten a la línea concreta que respalda cada afirmación, y que el sistema garantice que ninguna cita apunta al vacío.

## **Qué hace verificable a una citación**

Una citación decorativa dice "basado en datos históricos". Una citación verificable cumple tres propiedades, y las tres son comprobables.

La primera es que **resuelve**: el identificador apunta a una fuente que existe de verdad y que el sistema puede recuperar. Si el modelo cita `fin-2024-07#c3` pero ese fragmento nunca estuvo en el contexto recuperado, la citación está colgando del vacío. Resolver no es opcional: es la línea entre atribución y ficción.

La segunda es que **localiza**: la citación no apunta solo a un documento de cuarenta páginas, sino a la línea o el fragmento concreto que respalda la afirmación. "Basado en el proyecto X (2024)" es mejor que nada, pero "proyecto X (2024), línea: *Módulo de pagos (Stripe), 40h*" es lo que permite a un humano abrir el documento y encontrar el dato en diez segundos. El localizador es lo que separa una atribución vaga de una verificable.

La tercera es que **es trazable hasta el origen**: existe un camino, desde el número en la estimación hasta el presupuesto original, que cualquiera con permiso puede recorrer. No basta con que el sistema sepa de dónde sale el dato; el consumidor de la estimación tiene que poder llegar a la fuente, idealmente con un clic.

![art3-fig7-escala-verificabilidad.jpg](https://media1-production-mightynetworks.imgix.net/asset/fa240ced-1d80-4b11-9678-f6e2817c7138/art3-fig7-escala-verificabilidad.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Las tres juntas convierten "40 h para pagos" en una afirmación auditable. Vamos a construirlas.

## **Del id a la citación resoluble**

El primer paso es resolver el identificador a un objeto con significado. El fragmento recuperado ya arrastra la metadata que necesitamos, de qué documento es, de qué año, y, si se capturó en la ingesta, qué línea original representa. La citación es la proyección de esa metadata en una forma pensada para ser leída y comprobada por un humano.

```python
class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str            # human-meaningful: "Presupuesto Fintech App — Cliente X"
    project_year: int
    locator: str                   # the exact source line backing the claim
    char_span: tuple[int, int] | None  # offsets into the source document, if captured

def resolve_citation(chunk_id: str, retrieved: dict[str, RetrievedChunk]) -> Citation:
    """Project a retrieved chunk into a human-meaningful, verifiable citation.

    A KeyError here means the id was never in the retrieved context: a
    dangling citation, handled by the integrity check, not silently.
    """
    chunk = retrieved[chunk_id]
    return Citation(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_title=chunk.document_title,
        project_year=chunk.project_year,
        locator=chunk.source_line,
        char_span=chunk.char_span,
    )
```

El `locator` es el campo que decide si la citación es de verdad verificable o solo presentable. Y aquí hay una dependencia honesta que conviene mirar de frente: solo puedes citar a nivel de línea si en su día capturaste el localizador. Si los fragmentos se indexaron guardando la línea original o el rango de caracteres del que salieron, la citación puede ser exacta. Si no se capturó, lo máximo a lo que puedes aspirar es a citar a nivel de documento, "basado en el proyecto X (2024), "y la verificación se vuelve más tosca, porque el lector tiene que buscar el dato a mano en todo el documento. La citación verificable a nivel de línea no es algo que decidas en la generación: es algo que habilitas mucho antes, en cómo guardaste tus fuentes.

## **Integridad referencial: ninguna cita colgante**

Resolver una citación supone que el identificador existe en el contexto recuperado. Pero los modelos, incluso instruidos para citar solo fuentes provistas, a veces inventan un identificador con buena pinta que nunca estuvo ahí. Una cita colgante, un id que no pertenece al contexto que se le pasó al modelo, es el fallo de citación más peligroso, porque tiene exactamente el mismo aspecto que una cita legítima.

Por eso la integridad referencial no se confía al modelo: se verifica en código, después de generar.

```python
class CitationIntegrityReport(BaseModel):
    resolved: list[str]
    dangling: list[str]   # cited ids that were never in the retrieved context

def check_citation_integrity(
    estimate: Estimate,
    retrieved_ids: set[str],
) -> CitationIntegrityReport:
    resolved, dangling = [], []
    for component in estimate.components:
        for cid in component.source_chunk_ids:
            (resolved if cid in retrieved_ids else dangling).append(cid)
    if dangling:
        log.warning("dangling_citations", ids=dangling)
    return CitationIntegrityReport(resolved=resolved, dangling=dangling)
```

![art3-fig8-cita-colgante.jpg](https://media1-production-mightynetworks.imgix.net/asset/e9dc8505-44f4-4861-8dce-70cf7e13bdee/art3-fig8-cita-colgante.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Detectar la cita colgante es la mitad del trabajo; la otra mitad es la política de qué hacer con ella. Las opciones razonables, de más a menos estricta: rechazar la estimación entera y reintentar con una instrucción más dura; degradar el componente afectado a "sin fuente verificable" y rebajar su confianza; o, como mínimo, no dejar salir del servicio una estimación con una citación que no resuelve. La que nunca es aceptable es ignorarla, porque entonces estás entregando al usuario una atribución falsa con sello de verificada.

Conviene ser preciso sobre lo que esta comprobación garantiza y lo que no. La integridad referencial confirma que **la fuente citada existe y estuvo en el contexto**. No confirma que la fuente diga lo que la citación afirma que dice. Es una verificación estructural, no semántica: necesaria, pero no suficiente. Volveremos a esto al final, porque es justo donde empieza el problema más difícil.

## **Formatos: estructura primero, presentación después**

La pregunta "¿inline, notas al pie o enlaces?" suele plantearse mal, como si fueran alternativas excluyentes. No lo son. La estimación es una estructura de datos, JSON con componentes y, ahora, citaciones por componente, y los formatos son maneras distintas de *renderizar* la misma estructura. La fuente de verdad es la citación estructurada; inline y notas al pie son decisiones de presentación que se toman encima.

Esta separación importa porque distintas partes de la salida piden distinto formato. Los componentes de la estimación son datos: sus citaciones viajan como datos estructurados y el frontend decide si las muestra como chips, como una columna o como un panel lateral. El campo de resumen en prosa, en cambio, sí se beneficia de marcadores inline que resuelven a una lista de fuentes al pie, como en un artículo.

```python
def render_sources_block(citations: list[Citation]) -> str:
    """Render structured citations as a numbered sources block.

    The same Citation objects can feed inline markers in the prose summary;
    this is presentation over a single structured source of truth.
    """
    lines = []
    for index, citation in enumerate(citations, start=1):
        lines.append(
            f"[{index}] {citation.document_title} ({citation.project_year}) — {citation.locator}"
        )
    return "\n".join(lines)
```

Cada formato tiene su compromiso. Los **marcadores inline** (`40 h [1]`) son compactos y naturales en prosa, pero ensucian si cada número lleva el suyo y se vuelven ambiguos cuando una afirmación se apoya en varias fuentes a la vez, que, después de sintetizar, es lo normal, Las **notas al pie** separan limpiamente la afirmación de su respaldo y escalan bien a muchas fuentes, a costa de obligar al lector a saltar. Los **enlaces al documento original** dan la máxima verificabilidad, un clic y estás en la fuente, pero abren una cuestión que no es cosmética: los presupuestos históricos suelen ser confidenciales, y no todo el que ve una estimación tiene permiso para abrir el presupuesto del que sale.

Y ahí aparece una frontera de responsabilidad que conviene respetar. El servicio IA no debería emitir URLs ni dar por hecho que el consumidor puede ver cada documento: emite `document_id` y `locator`, datos neutros. Es la capa de negocio la que sabe quién es el usuario y qué tiene permiso de ver, y la que resuelve ese `document_id` a un enlace real y autorizado. El patrón es independiente del stack, cualquier backend HTTP puede hacer esta resolución, pero en la implementación de referencia, en Rails, se ve así:

```ruby
# Business backend (Rails): resolve a citation's document to a link the
# current user is actually allowed to open. The AI service emits document_id
# and locator; it never emits URLs or assumes visibility. Stack-agnostic:
# any HTTP backend can perform the same permission-checked lookup.
class CitationLinkResolver
  def initialize(user)
    @user = user
  end

  def link_for(document_id)
    document = HistoricalBudget.find(document_id)
    return nil unless @user.can_view?(document)

    Rails.application.routes.url_helpers.historical_budget_path(document)
  end
end
```

![art3-fig9-contrato-capas-enlace.jpg](https://media1-production-mightynetworks.imgix.net/asset/8fc05bed-6bc9-42ca-830c-1dfc1efd972f/art3-fig9-contrato-capas-enlace.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Si el usuario no tiene permiso, el enlace simplemente no se ofrece, y la citación se queda en su forma textual verificable, documento, año, línea, sin exponer un recurso que no debería ver. La verificabilidad y el control de acceso no se contradicen; cada capa hace su parte.

## **Trade-offs honestos**

**Citar a nivel de línea es una promesa que se paga en la ingesta.** Toda la elegancia del `locator` depende de que alguien, antes, guardara la procedencia exacta de cada fragmento. Si tu corpus no la tiene, no improvises citaciones de línea sobre datos que no la soportan: cita a nivel de documento y sé honesto sobre la granularidad. Una citación de línea inventada es peor que una citación de documento sincera.

**La citación estructurada es trabajo extra que el modelo a veces se salta.** Obligar al modelo a emitir, por cada componente, los identificadores correctos del contexto es una restricción que cumple peor cuanto más larga es la generación. La verificación de integridad es la red que recoge esos fallos, pero conviene asumir que existirán y diseñar la política de respuesta antes de verlos en producción, no después.

**El enlace al original es la mejor verificación y la más frágil.** Un clic a la fuente es lo que de verdad cierra el bucle de confianza, pero depende de que los documentos sigan existiendo, de que las rutas sean estables y de que el control de acceso funcione. Un enlace roto o, peor, un enlace que expone un presupuesto confidencial a quien no debe, hace más daño que no tener enlace. Si no puedes garantizar la persistencia y los permisos, la citación textual verificable es una opción digna.

**Demasiada citación cansa y deja de leerse.** Si cada número de la estimación arrastra tres marcadores, el lector deja de mirarlos, y una citación que nadie lee no verifica nada. Citar bien también es decidir el grano: a nivel de componente suele ser el equilibrio correcto entre rigor y legibilidad, y se reserva el detalle línea a línea para cuando alguien quiere auditar.

## **Lo que esto deja sin resolver**

Con todo esto, la estimación tiene citaciones que resuelven, que localizan la línea y que son trazables hasta el presupuesto original con el control de acceso de cada capa en su sitio. La integridad referencial garantiza que ninguna afirmación cita una fuente que no existe.

Y sin embargo, hay una grieta que ninguna de estas comprobaciones cierra. La integridad referencial confirma que `fin-2024-07#c3` estuvo en el contexto y resuelve a un presupuesto real. No confirma que ese presupuesto diga "40 h para pagos". El modelo podría haber citado, con un identificador perfectamente válido, un fragmento que en realidad habla de otra cosa, o atribuirle una cifra que no aparece en él. La citación estaría impecable, bien formada, resoluble, con su enlace, y la atribución sería falsa.

Una citación que apunta a una fuente real pero que esa fuente no respalda es una alucinación con coartada. Detectarla ya no es comprobar identificadores: es comprobar que el contenido de la fuente sostiene de verdad lo que la estimación afirma. Ese es un problema distinto, más profundo, y es donde se juega la última capa de confianza del sistema.