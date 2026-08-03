# Memoria conversacional vs historial: estrategias para sistemas CAG

Creada: 17 de mayo de 2026 12:15
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S5. Funcionalidades avanzadas (https://app.notion.com/p/S5-Funcionalidades-avanzadas-363ea9ca03c4809fa6b4c8d2a9413af9?pvs=21)

En la sesión 02 trabajamos la arquitectura de conversaciones: el array de mensajes que viaja a la API, los roles `system`/`user`/`assistant`, el problema del crecimiento del historial y las tres estrategias clásicas para gestionarlo (ventana deslizante, resumen acumulativo, híbrida). Si vuelves a esos materiales con la sesión 05 en la cabeza, vas a notar algo: en aquel artículo todo era *historial*. La palabra "memoria" aparecía como sinónimo aproximado, sin distinción operativa.

Esa elipsis era deliberada — en la fase inicial del `estimator` no necesitabas más. Pero al introducir un sistema multi-turno que conversa sobre un proyecto en curso, la simplificación se rompe. El usuario espera que el sistema *recuerde* el nombre del proyecto, las tecnologías acordadas, el equipo asumido, el alcance pactado, sin necesidad de repetirlos cada turno. Y lo espera incluso cuando el turno donde mencionó esas cosas ya cayó fuera de la ventana deslizante.

La conclusión es que **historial y memoria son dos cosas distintas** que conviene tratar de forma separada en arquitectura. Confundirlas es uno de los errores más caros que se ven en sistemas CAG en producción: se gestiona un solo blob creciente que se trunca a ojo, el sistema pierde coherencia sobre el proyecto en curso, y el equipo termina inflando el system prompt con instrucciones del tipo "no olvides el nombre del proyecto" que no resuelven el problema de fondo.

Este artículo formaliza esa distinción y la convierte en piezas de código concretas para el `estimator`.

## **1. Definiciones operativas**

Empecemos por anclar el vocabulario.

**Historial conversacional** es el array de mensajes (`system`, `user`, `assistant`, `user`, `assistant`…) que viaja a la API del LLM en cada llamada. Es una estructura *bruta*: cada mensaje contiene exactamente lo que el usuario escribió y lo que el modelo respondió, en orden cronológico. Su gestión —cuántos turnos sobreviven, cómo se truncan, cómo se resumen— es lo que cubrimos en el artículo de la sesión 02.

**Memoria conversacional** es el conjunto de *hechos relevantes* que el sistema ha aprendido sobre el dominio de la conversación a lo largo de los turnos. Los hechos no son turnos; son afirmaciones destiladas. "El proyecto se llama BookFlow", "el equipo asumido son 3 personas full-time", "la stack acordada es Rails + React + PostgreSQL", "el cliente ha rechazado explícitamente el uso de microservicios para la primera fase". Cada hecho tiene un origen (un turno donde se mencionó) pero la memoria es independiente del turno: persiste aunque el turno original se haya descartado del historial.

La distinción es sutil pero crítica. El historial responde a la pregunta *"¿qué dijo el usuario en el turno 7?"*. La memoria responde a *"¿qué sabemos sobre este proyecto?"*. Son dos preguntas distintas y los sistemas que las mezclan acaban respondiendo mal a las dos.

### **Por qué las dos por separado**

Hay tres razones operativas para mantenerlas como estructuras independientes:

**Coste y latencia.** El historial crece linealmente con la conversación; la memoria, no. Un proyecto bien acotado puede tener veinte hechos relevantes después de cien turnos. Si los hechos viajan en una estructura compacta y separada del historial, los reenvías en cada llamada al LLM sin pagar el coste del historial completo.

**Resistencia al truncado.** Cuando aplicas ventana deslizante, los turnos antiguos desaparecen. Si la memoria depende del historial, también desaparece. Si la memoria es una estructura independiente, sobrevive al truncado. Esto es lo que evita que el sistema "olvide" el nombre del proyecto cuando la conversación se alarga.

**Auditabilidad.** En un sistema CAG en producción, te van a preguntar "¿por qué el LLM asumió X?". Si los hechos asumidos están explícitamente en una estructura inspeccionable, puedes responder. Si están dispersos en un array de turnos brutos, no.

## **2. Anatomía del estado conversacional en el `estimator`**

Vamos a aterrizarlo. Una sesión del `estimator` tiene tres componentes de estado, no uno:

![003-anatomia-estado-conversacional.jpg](https://media1-production-mightynetworks.imgix.net/asset/3a8ab7f8-2424-4be9-b501-bd3f8b07c600/003-anatomia-estado-conversacional.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

`ConversationHistory` es lo que ya conoces: la lista de mensajes con la lógica de ventana deslizante. `ProjectMetadata` es la novedad de esta sesión: una estructura tipada que captura los hechos del proyecto en curso.

En código:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

class ProjectMetadata(BaseModel):
    """Distilled facts about the project under estimation.

    Survives history truncation. Updated after each turn.
    """
    project_name: str | None = None
    assumed_team_size: int | None = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = None
    explicit_constraints: list[str] = Field(default_factory=list)
    rejected_options: list[str] = Field(default_factory=list)

class Message(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str

class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    history: list[Message] = Field(default_factory=list)
    project_metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

La separación es estructural, no decorativa. Cuando el sistema recibe un nuevo turno, hace tres cosas en orden:

1. Inyecta `project_metadata` en el system prompt vía template Jinja2, junto con la ventana actual de `history`.
2. Llama al LLM y obtiene la respuesta.
3. Actualiza tanto `history` (añadiendo el nuevo par user/assistant) como `project_metadata` (extrayendo hechos nuevos).

Los pasos 1 y 3 son donde vive la pieza interesante. El paso 2 es la llamada al LLM que ya conoces.

## **3. Inyectar memoria en el system prompt**

El template Jinja2 del system prompt se actualiza para recibir un bloque `<project_metadata>` con los hechos conocidos. Cuando la sesión arranca, el bloque está vacío; con los turnos, se va poblando.

jinja2

`You are a senior software estimation expert. Produce realistic, well-justified estimates for software projects based on meeting transcripts and complementary documentation.

{% if project_metadata %} <project_metadata> {% if project_metadata.project_name %} Project name: {{ project_metadata.project_name }} {% endif %} {% if project_metadata.assumed_team_size %} Assumed team size: {{ project_metadata.assumed_team_size }} full-time engineers {% endif %} {% if project_metadata.mentioned_technologies %} Technologies mentioned: {{ project_metadata.mentioned_technologies | join(", ") }} {% endif %} {% if project_metadata.agreed_scope %} Agreed scope: {{ project_metadata.agreed_scope }} {% endif %} {% if project_metadata.explicit_constraints %} Explicit constraints: {% for constraint in project_metadata.explicit_constraints %}

- {{ constraint }} {% endfor %} {% endif %} {% if project_metadata.rejected_options %} Rejected options (do not propose these again): {% for option in project_metadata.rejected_options %}
- {{ option }} {% endfor %} {% endif %} </project_metadata> {% endif %}

<context_examples> {# CAG static reference estimates as in previous sessions #} {% include "reference_estimates.j2" %} </context_examples>

When producing the estimate, treat the project_metadata as established facts. Do not contradict them unless the user explicitly revises them in the current turn.`

Dos detalles que conviene notar:

**Renderizado condicional.** Cada campo de la metadata se incluye solo si tiene valor. Esto evita que el LLM vea fragmentos del tipo "Project name: None", que ensucian el contexto y a veces inducen al modelo a inventar valores para los campos vacíos.

**Tratamiento explícito como hechos establecidos.** La última instrucción del system prompt — "treat the project_metadata as established facts" — no es decorativa. Sin esa instrucción, el LLM tiende a tratar la memoria como una sugerencia más entre otras y a renegociar hechos que ya están cerrados. Con esa instrucción, el modelo entiende que la memoria tiene autoridad sobre interpretaciones nuevas.

El resultado: aunque el turno donde el usuario dijo "vamos a usar Rails" haya desaparecido de la ventana deslizante, el hecho `mentioned_technologies: ["Rails"]` sigue en el system prompt y el modelo no se vuelve a preguntar qué stack se va a usar.

## **4. Actualizar la memoria después de cada turno**

Inyectar la memoria es la parte fácil. **Mantenerla viva** es donde está la pieza interesante. Después de cada respuesta del LLM, el sistema necesita inspeccionar el nuevo turno (lo que el usuario dijo + lo que el modelo respondió) y actualizar `project_metadata` con los hechos relevantes.

Hay dos aproximaciones canónicas, con perfiles de coste y robustez muy distintos.

### **Aproximación 1 — Heurística simple**

Defines reglas explícitas que extraen hechos del turno. Por ejemplo: si el usuario o el modelo mencionan un nombre propio que aparece como sujeto de "the project is called" o "named X", lo capturas como `project_name`. Si aparecen tokens conocidos como nombres de tecnología (de una lista mantenida), los añades a `mentioned_technologies`.

```python
import re

KNOWN_TECHNOLOGIES = {
    "rails",
    "react",
    "postgresql",
    "redis",
    "node",
    "python",
    # ...
}

PROJECT_NAME_PATTERN = re.compile(
    r'(?:project\s+(?:is\s+)?(?:called|named)\s+)["\']?([\w\s\-]+?)["\']?(?:[.,]|$)',
    re.IGNORECASE,
)

def update_metadata_heuristic(
    metadata: ProjectMetadata,
    user_turn: str,
    assistant_turn: str,
) -> ProjectMetadata:

    combined = f"{user_turn}\n{assistant_turn}".lower()

    # Project name extraction
    if metadata.project_name is None:
        match = PROJECT_NAME_PATTERN.search(combined)
        if match:
            project_name = match.group(1).strip()

            metadata = metadata.model_copy(
                update={
                    "project_name": project_name,
                }
            )

    # Technology detection
    found = {
        tech
        for tech in KNOWN_TECHNOLOGIES
        if re.search(rf"\b{re.escape(tech)}\b", combined)
    }
    if found:
        merged = sorted(
            set(metadata.mentioned_technologies) | found
        )
        metadata = metadata.model_copy(
            update={
                "mentioned_technologies": merged,
            }
        )

    return metadata
```

**Ventajas.** Coste cero por turno (no hay llamada extra al LLM), latencia despreciable, comportamiento predecible y depurable.

**Desventajas.** Frágil. La regex de project_name asume una formulación concreta en inglés y se rompe con cualquier variación. Si el usuario dice "let's call it Bookflow internally", la regex no captura. Las heurísticas crecen en complejidad rápidamente y acaban siendo un pequeño NLP propio difícil de mantener.

### **Aproximación 2 — LLM extractor**

Usas una segunda llamada al LLM, con un prompt específico, para que devuelva un JSON con los campos del `ProjectMetadata` actualizado. La entrada es la metadata actual + el último turno; la salida es la metadata nueva.

```python
EXTRACTION_PROMPT = """\
You receive the current ProjectMetadata of a software estimation session and the latest conversation turn.
Your task: produce an updated ProjectMetadata that incorporates any new facts revealed in the turn.
Rules:
- Only update fields when the turn provides clear evidence.
- Preserve existing values unless the user explicitly revises them.
- If the user retracts a previous fact, remove it.
- For lists (technologies, constraints, rejected_options), append new items without duplicating existing ones.
Current metadata: {current_metadata_json}
Latest turn: USER: {user_turn} ASSISTANT: {assistant_turn}
Return ONLY a valid JSON matching the ProjectMetadata schema."""

async def update_metadata_llm(
		metadata: ProjectMetadata,
		user_turn: str,
		assistant_turn: str,
		client
) -> ProjectMetadata:

		response = await client.responses.create(
				model="gpt-4o-mini",
				input=EXTRACTION_PROMPT.format(
						current_metadata_json=metadata.model_dump_json(),
						user_turn=user_turn,
						assistant_turn=assistant_turn
				),
				response_format={"type": "json_object"},
		)
		
		return ProjectMetadata.model_validate_json(response.output_text)

```

**Ventajas.** Robusto frente a variaciones de lenguaje, multilingüe sin trabajo extra, captura hechos sutiles que ninguna regex razonable atraparía. Y reutiliza un patrón que ya conoces de la sesión 04 (datos estructurados con schema).

**Desventajas.** Coste real: una llamada extra al LLM por turno. Con `gpt-4o-mini` en la sesión 04 estimamos un coste por llamada en céntimos, así que multiplicado por turnos sigue siendo muy barato — pero no cero. Latencia adicional de 500–1500 ms por turno. Y un riesgo nuevo: la extracción puede equivocarse. Si el extractor invent un hecho falso, lo metes en la memoria y de ahí afecta a todas las llamadas siguientes.

### **Cómo elegir**

La regla práctica:

- Si el dominio es muy acotado y los hechos relevantes encajan en patrones formulaicos predecibles: heurística.
- Si el dominio es abierto, multilingüe o con variabilidad alta de lenguaje: LLM extractor.
- Si tienes presupuesto para los dos: usa el LLM extractor con una validación heurística posterior que descarte extracciones obviamente erróneas (campos que cambian de tipo, valores absurdamente largos, contradicciones internas).

Para el `estimator`, el dominio tiene cierta estructura pero la conversación es libre y posiblemente bilingüe. La balanza se inclina ligeramente hacia el LLM extractor — pero la heurística es completamente defendible si quieres minimizar coste y latencia en esta fase.

## **5. La estrategia de gestión de historial vuelve**

Recordatorio rápido del artículo de sesión 02: hay tres estrategias canónicas para gestionar el historial cuando crece.

![image.png](https://media1-production-mightynetworks.imgix.net/asset/421c7866-b73a-4bdd-9570-4caf31d865b2/f1ada7a14125375b.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Estrategia Cómo funciona / Cuándo elegirla:

- **Ventana deslizante** Mantienes los últimos N turnos, descartas los más antiguos Conversaciones cortas o cuando los hechos relevantes ya están en `project_metadata`
- **Resumen acumulativo** Cuando el historial crece, resumes los turnos antiguos en un único mensaje compacto Conversaciones largas donde los matices del lenguaje original importan
- **Híbrida con anclas** Resumen acumulativo de lo más antiguo + ventana de los últimos N + turnos críticos que nunca se descartan Producción seria, con conversaciones que se alargan días o semanas

Lo que cambia ahora respecto a la sesión 02 es que **la decisión sobre qué estrategia usar se vuelve menos crítica** cuando tienes `project_metadata` separado. La ventana deslizante simple deja de ser arriesgada porque los hechos que importan no se pierden cuando un turno cae de la ventana — los hechos viven en la memoria, que es independiente.

Esta es la consecuencia más práctica de separar memoria e historial: te permite usar la estrategia más simple de gestión de historial sin sufrir las consecuencias clásicas. Ventana deslizante con `MAX_TURNS = 6` y `project_metadata` actualizado por turno es una arquitectura completamente razonable para producción inicial.

## **6. Cuándo olvidar**

Una pieza que se subestima sistemáticamente: los sistemas necesitan **políticas explícitas para olvidar**. Sin políticas de olvido, la memoria crece sin control, los hechos viejos contaminan decisiones nuevas, y la sesión termina respondiendo basándose en información obsoleta.

Tres políticas que el `estimator` debe implementar desde el principio:

**Política 1 — Revisión explícita por el usuario.** Si el usuario dice "ya no vamos a usar Rails, vamos a ir con Node", la memoria debe reflejarlo: `mentioned_technologies` actualizada y, si la estructura lo permite, `rejected_options` ampliada con "Rails". Tanto la heurística como el LLM extractor deben reconocer este patrón de revisión.

**Política 2 — TTL por sesión.** La sesión completa debe tener un tiempo de vida razonable. Una sesión inactiva durante 24 horas probablemente ya no es la misma conversación de negocio: el contexto del usuario ha cambiado, y reanudar con la memoria antigua puede inducir asunciones erróneas. Una política simple: cualquier sesión sin actividad durante 24 horas se archiva, y al reanudar se ofrece al usuario crear una sesión nueva con la memoria heredada o partir de cero.

**Política 3 — Reset explícito.** El usuario debe poder decir "olvida todo lo de antes y empezamos otra vez" y obtener una sesión limpia. Esto se materializa con un endpoint `POST /sessions` que crea una sesión nueva, dejando la anterior intacta para auditoría pero fuera del flujo activo.

La política 1 vive dentro de la lógica de actualización de memoria. La política 2 vive en el ciclo de vida de la sesión (job programado que archiva sesiones expiradas). La política 3 es un endpoint REST normal y corriente.

Tres políticas, tres ubicaciones distintas en la arquitectura. La tentación es tratar todo el problema del olvido como una sola pieza; la realidad es que son tres mecanismos independientes que conviene mantener separados.

## **7. Persistencia: lo que no entra todavía**

Una pregunta natural a estas alturas: ¿dónde vive todo este estado?

En una arquitectura madura, las sesiones viven en una base de datos persistente —Redis para acceso rápido, PostgreSQL para auditoría a largo plazo, o ambas— gestionada por el backend de negocio. El servicio IA recibe el `session_id` en cada petición y carga el estado correspondiente. Esto permite continuidad entre reinicios del servicio, distribución horizontal y trazabilidad histórica.

En la fase actual del programa, sin embargo, la elección razonable es mantener las sesiones en un diccionario en memoria del proceso del servicio IA. Es deliberadamente simple, no escala más allá de un único proceso, y se pierde con cada reinicio. Se acepta porque la persistencia y la federación de sesiones son temas que pertenecen al módulo de despliegue y producción, no a la fase de arquitectura CAG.

Lo importante a nivel arquitectónico es que la separación entre `history` y `project_metadata` que estamos defendiendo sobrevive intacta cuando se introduce persistencia. Los dos componentes se serializan y se cargan independientemente. Migrar de un dict en memoria a Redis no requiere refactorizar nada del modelo; solo cambia el backend de almacenamiento.

## **8. Anti-patrones frecuentes**

Tres errores que se ven repetidamente en sistemas CAG conversacionales y que esta arquitectura previene.

**Anti-patrón 1 — Memoria en el system prompt como string libre.** "El proyecto se llama X, el equipo es de 3 personas, las tecnologías son…" como bloque de texto plano dentro del system prompt, actualizado a mano. Funciona en el primer turno. En el turno 20 el bloque está lleno de inconsistencias y nadie sabe cómo se llegó hasta ahí. Una estructura tipada con campos explícitos es más larga de escribir pero infinitamente más mantenible.

**Anti-patrón 2 — Confiar en que el LLM "se acordará".** El razonamiento del tipo "el LLM ya leyó que el proyecto se llama X en el turno 3, no hace falta repetirlo en cada llamada". Es falso. El LLM no tiene estado entre llamadas. Si el turno 3 ha caído fuera de la ventana deslizante, ese hecho desaparece a menos que vivas explícitamente en otro lado. La memoria explícita no es redundancia; es la única forma de que el hecho sobreviva.

**Anti-patrón 3 — Mezclar memoria e historial en una única estructura.** "Voy a guardar todo el historial bruto en BBDD y también voy a guardar los hechos extraídos en el mismo blob para no tener dos tablas". Pasa todo el tiempo, especialmente en proyectos pequeños donde la separación parece sobreingeniería. La factura llega cuando necesitas truncar el historial sin tocar la memoria, o cuando un cambio en el schema de un hecho te obliga a migrar conversaciones antiguas. Dos estructuras desde el principio salen baratas comparado con esa migración.

## **9. Resumen**

Lo central de esta pieza son cuatro afirmaciones operativas que merecen viajar a tu modelo mental:

1. **Historial y memoria son dos estructuras distintas con responsabilidades distintas.** El historial es el array de mensajes; la memoria es el conjunto de hechos destilados sobre el dominio.
2. **La memoria sobrevive al truncado del historial.** Esa es la propiedad que hace que el sistema mantenga coherencia en conversaciones largas sin pagar el coste de un contexto creciente.
3. **La memoria se materializa como una estructura tipada (Pydantic) que se inyecta en el system prompt vía template y se actualiza después de cada turno.** Las dos formas de actualizar (heurística simple, LLM extractor) son válidas y se eligen según contexto.
4. **El olvido necesita políticas explícitas.** Tres mecanismos distintos: revisión por usuario, TTL de sesión, reset explícito. Cada uno en su lugar.

Aplicar estas cuatro afirmaciones convierte una conversación que "se va olvidando de las cosas" en un sistema que mantiene coherencia sobre el dominio mientras controla el coste y la latencia. Es la diferencia entre un chat funcional y una herramienta de producto.