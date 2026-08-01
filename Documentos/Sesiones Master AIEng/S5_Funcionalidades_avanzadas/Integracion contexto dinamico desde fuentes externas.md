# Integración de contexto dinámico desde fuentes externas

Creada: 17 de mayo de 2026 11:44
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S5. Funcionalidades avanzadas (https://app.notion.com/p/S5-Funcionalidades-avanzadas-363ea9ca03c4809fa6b4c8d2a9413af9?pvs=21)

Hasta ahora, el `estimator` ha funcionado con un contrato cerrado: el cliente envía una transcripción, el servicio IA monta el system prompt con el contexto CAG estático, y el LLM produce la estimación. Todo el conocimiento que entra en la decisión vive en dos sitios: la transcripción que envía el usuario, y el contexto cargado por el equipo de producto en los templates Jinja2.

Ese modelo se rompe en cuanto el sistema sale del laboratorio. Nadie estima un proyecto a partir de una transcripción aislada — siempre hay un PDF de especificación técnica, una propuesta comercial previa, un benchmark reciente de la base de datos que el equipo está considerando, o un histórico de proyectos parecidos en la BBDD interna. El usuario espera que la estimación incorpore todo ese material, y la única alternativa a integrarlo es pedirle que copie y pegue su contenido en la transcripción, lo cual es exactamente la mala experiencia que llevamos toda la sesión 04 evitando.

Este artículo cubre los tres mecanismos canónicos para enriquecer el contexto de un sistema CAG en tiempo de ejecución sin saltar todavía a una arquitectura RAG: archivos adjuntos, búsqueda web y consultas a la BBDD del backend de negocio. Cada uno resuelve un tipo distinto de necesidad. Saber cuándo elegir cada uno —y cuándo combinarlos— es lo que separa un prototipo de un producto.

## **1. La distinción crítica: contexto estático vs contexto dinámico**

Hasta la sesión 04, todo el contexto que ha viajado al LLM ha sido **estático**: vive en código (templates Jinja2, ejemplos hardcoded en el system prompt) o en parámetros tipados que el formulario produce. Es predecible, versionable y testeable.

El contexto **dinámico** es el que el sistema obtiene en tiempo de ejecución, en respuesta a una petición concreta. No vive en código; vive en sistemas externos: el sistema de archivos del usuario, la web, una BBDD, un sistema de tickets. Y hay tres reglas operativas que debes interiorizar antes de seguir:

**Regla 1 — el contexto dinámico es input, no programa.** Tratarlo como código (concatenarlo a ciegas en el prompt, dejar que el usuario inyecte instrucciones disfrazadas de adjunto) es la receta para `prompt injection` clásico. Cualquier contenido que entra desde fuera de tu sistema debe estar claramente delimitado en el prompt y nunca se le da al LLM la capacidad de interpretarlo como instrucciones.

**Regla 2 — el contexto dinámico tiene coste real por petición.** Mientras el contexto estático se paga una vez en token caching, el dinámico se reincluye en cada llamada y consume tokens nuevos. Adjuntar un PDF de 30 páginas a cada turno de una conversación duplica fácilmente el coste de la sesión.

**Regla 3 — el contexto dinámico introduce latencia que tu usuario nota.** Procesar un PDF puede llevar 1–3 segundos antes de que llegue al LLM. Hacer una búsqueda web añade otros 2–5 segundos. Y consultar la BBDD del backend de negocio, otro round-trip. La diferencia entre un producto que se siente vivo y uno que se siente roto está aquí.

Con esas tres reglas asumidas, vamos a por los tres mecanismos.

## **2. Archivos adjuntos**

El usuario sube un PDF con la especificación técnica del proyecto. Tu servicio IA tiene que incorporar ese contenido al contexto del LLM. Hay dos caminos canónicos para hacerlo, y la elección no es trivial.

![002-caminos-a-b-adjuntos.jpg](https://media1-production-mightynetworks.imgix.net/asset/9380fe2b-a0a9-4144-94c7-b5a108764309/002-caminos-a-b-adjuntos.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

### **Camino A — Multimodal directo: el PDF viaja al LLM**

Los proveedores grandes han añadido soporte nativo para PDFs en los últimos meses. Le pasas el archivo a la API y el modelo extrae texto, interpreta diagramas y razona sobre el contenido visual sin que tú tengas que hacer ningún preprocesado.

En Anthropic, el patrón canónico es subir el archivo a través de la Files API y luego referenciarlo en el bloque de contenido del mensaje:

```python
import anthropic

client = anthropic.Anthropic()

with open("specification.pdf", "rb") as f:
    uploaded = client.beta.files.upload(
        file=("specification.pdf", f, "application/pdf"),
    )

response = client.beta.messages.create(
    model="claude-opus-4-7",
    max_tokens=2048,
    betas=["files-api-2025-04-14"],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "file", "file_id": uploaded.id},
                },
                {
                    "type": "text",
                    "text": "Use this technical specification as additional context when producing the estimate.",
                },
            ],
        }
    ],
)
```

OpenAI ofrece el mismo patrón en la Responses API, con el archivo subido vía la Files API y referenciado en el `input` del mensaje. La diferencia conceptual con Anthropic es mínima; la diferencia de SDK la encapsula tu wrapper de proveedores de la sesión 03.

Las ventajas son claras. Cero código de extracción. El modelo ve los diagramas y los interpreta — un diagrama de arquitectura ASCII, un gráfico de Gantt, una captura de un wireframe — y lo incorpora al razonamiento. La latencia de carga del archivo se paga una sola vez (la Files API mantiene el archivo durante la conversación, sólo subes una vez) y el resto de turnos referencian el `file_id`.

Las desventajas son menos obvias pero importantes. Estás acoplado al proveedor multimodal: cambiar de OpenAI a un modelo open-source local que no soporte PDF nativo te obliga a cambiar la arquitectura. El consumo de tokens es mayor que el de un texto extraído equivalente, porque el modelo internamente tokeniza tanto el contenido textual como una representación visual de cada página. Y tienes menos control sobre qué partes del documento entran al contexto: o todo o nada.

### **Camino B — Extracción local: solo el texto viaja al LLM**

El otro camino es extraer el contenido del documento en tu servicio IA, antes de la llamada al LLM, y enviar solamente texto. Para PDFs nativos de texto, `pypdf` o `PyMuPDF` resuelven el caso simple en pocas líneas; para PDFs escaneados o con layout complejo, librerías como `Docling` o `MarkItDown` producen markdown estructurado que conserva tablas, encabezados y jerarquía. Para Word existe `python-docx`.

```python
from pypdf import PdfReader
from io import BytesIO

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    parts = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"--- Page {index} ---\\n{text}")
    return "\\n\\n".join(parts)
```

Una vez tienes el texto, lo concatenas al prompt con un delimitador claro que el LLM pueda reconocer:

```python
attachments_blocks = []

for attachment in attachments:
    extracted_text = extract_text_from_pdf(
        attachment.bytes
    )
    attachments_blocks.append(
        f"""
<attachment filename="{attachment.filename}">
{extracted_text}
</attachment>
""".strip()
    )

attachments_block = "\n\n".join(
    attachments_blocks
)

user_prompt = f"""
<transcript>
{transcript}
</transcript>

<attachments>
{attachments_block}
</attachments>

Produce a software estimate based on the transcript.
Use the attachments as additional context.
""".strip()
```

Las ventajas se invierten respecto al camino A. Eres independiente del proveedor: tu wrapper sigue funcionando con cualquier modelo, multimodal o no. Tienes control fino sobre qué pasa al contexto: puedes filtrar páginas, redactar secciones sensibles, recortar a un budget de tokens. Y, crucialmente, **estás preparando el terreno para RAG**: la lógica de extracción de texto que escribes hoy es exactamente la primera pieza del pipeline de chunking que vas a montar en el módulo 3.

Las desventajas son el código que tienes que mantener (extracción para PDF, extracción para Word, extracción para imágenes…) y la pérdida de información visual: si el documento contiene un diagrama de arquitectura crítico, una extracción de texto plano no lo capta. Hay un middle ground —`Docling`, `MarkItDown` y `LlamaParse` usan internamente modelos multimodales para producir markdown enriquecido— pero entonces vuelves a depender de servicios externos.

### **Cómo elegir**

**Cualquiera de los dos caminos es defendible** dentro de una arquitectura CAG madura. La elección operativa:

- Si lo que prima es velocidad de desarrollo y no te importa el lock-in con un proveedor multimodal: camino A.
- Si quieres entender mejor el flujo completo de procesamiento de documentos y prepararte conceptualmente para el módulo de RAG: camino B.

Lo que **no** se hace es implementar los dos en paralelo. Es una decisión arquitectónica, no una característica que se acumule.

## **3. Búsqueda web**

El segundo mecanismo de contexto dinámico es la búsqueda web. La necesidad surge cuando la estimación involucra tecnologías, precios o benchmarks que el modelo no tiene en su corte de conocimiento. Imagina que la transcripción menciona "queremos usar Bun en lugar de Node" y necesitas estimar la curva de aprendizaje para un equipo que viene de Node — los datos relevantes son recientes y el modelo, sin acceso a la web, va a alucinar o a responder con cautela exagerada.

Hay tres aproximaciones, y otra vez la elección depende de cuánto control quieras y cuánto acoplamiento tolere tu arquitectura.

### **Aproximación 1 — Herramienta nativa del proveedor**

OpenAI y Anthropic exponen búsqueda web como herramienta de primera clase dentro de la Responses API y la Messages API respectivamente. La habilitas en la lista de `tools` y el modelo decide cuándo usarla:

```python
response = client.responses.create(
		model="gpt-4.1",
		input=user_prompt,
		tools=[{"type": "web_search"}]
)
```

Es la opción más simple y la que tiene mejor integración con el razonamiento del modelo: el LLM puede decidir que necesita buscar, formular la query, recibir los resultados y citarlos en su respuesta como parte de un único flujo. El coste se factura en la misma cuenta del proveedor.

La pega: lock-in total. Si mañana cambias de proveedor, pierdes la herramienta. Y la calidad de los resultados depende del índice del proveedor (Bing en el caso de OpenAI/Azure, una mezcla en Anthropic), que no controlas.

### **Aproximación 2 — Servicio de búsqueda independiente**

La alternativa es delegar la búsqueda a un servicio especializado en LLMs como **Tavily**, **Exa** o **Firecrawl**. Estos servicios devuelven resultados optimizados para consumo por modelos: snippets más largos, contenido extraído en markdown limpio, ranking semántico, filtros por dominio.

```python
from tavily import TavilyClient

tavily = TavilyClient(api_key=settings.tavily_api_key)

def web_search(query: str, max_results: int = 5) -> list[dict]:
    results = tavily.search(query=query, max_results=max_results)
    return [
        {"title": r["title"], "url": r["url"], "snippet": r["content"]}
        for r in results["results"]
    ]
```

Luego expones la función al LLM como una `tool` definida por ti, igual que cualquier otro function calling. El LLM decide cuándo invocarla, tu servicio IA la ejecuta contra Tavily, y devuelve los resultados al modelo en el siguiente turno.

La ventaja: independencia del proveedor, calidad de resultados orientada a IA, mismo wrapper sirve para cualquier LLM. La pega: tienes que cablear el function calling tú, mantener una clave más, y pagar otra factura.

### **Aproximación 3 — SERP API tradicional**

`SerpAPI` o `Serper` son la opción más cruda: te devuelven los resultados estructurados de Google o Bing tal cual. Tienes que hacer tú mismo el fetch del contenido, la limpieza, y el resumen antes de pasarlo al LLM. Es la opción de máximo control y máxima carga de mantenimiento. Para el `estimator` rara vez tiene sentido — la inversión no compensa salvo que tengas requisitos de búsqueda muy específicos.

### **Cuándo activar la búsqueda**

La búsqueda web no es gratis: añade latencia (2–5 segundos) y tokens en el contexto del LLM. La regla práctica es activarla solo cuando el system prompt no pueda responder con información del propio modelo y la pregunta sea sensible al tiempo. Para el `estimator`, esto se traduce en:

- Tecnologías recientes (versiones de frameworks salidas en los últimos 6 meses).
- Comparativas de precios de SaaS.
- Benchmarks recientes de hardware o servicios cloud.
- Disponibilidad o estabilidad de librerías concretas.

Para todo lo demás —patrones arquitectónicos, prácticas de equipo, riesgos típicos por tipo de proyecto— el modelo ya tiene la información en su corte de entrenamiento, y activar búsqueda web solo añade ruido.

## **4. Consultas a la BBDD del backend de negocio**

El tercer mecanismo es el más interesante desde el punto de vista de arquitectura porque expone con claridad la separación de capas del programa. La necesidad: cuando el sistema estima un proyecto, quieres que considere los proyectos similares que tu empresa ha hecho antes — sus horas reales, sus desviaciones, sus riesgos materializados. Esos datos viven en la BBDD del backend de negocio (PostgreSQL, MySQL, lo que sea), no en el servicio IA.

### **Qué NO hacer: que el servicio IA acceda directamente a la BBDD**

La tentación es darle al servicio IA acceso directo a la BBDD del backend de negocio. Es un error arquitectónico que se paga caro:

- **Acoplamiento de schema:** el servicio IA acaba conociendo la estructura interna del modelo de datos del backend de negocio, y cualquier cambio de schema rompe ambos.
- **Permisos:** el servicio IA termina con credenciales de BBDD que sobreviven más de lo debido y que tienen permisos demasiado amplios.
- **Lógica duplicada:** las reglas de negocio sobre qué proyectos contar, cómo agregar horas o cómo filtrar acaban implementadas en dos sitios.

Cuando lleguemos al módulo 3-4 con RAG, la BBDD vectorial sí va a vivir cerca del servicio IA — pero esa es la BBDD de **conocimiento del servicio IA**, no la BBDD operacional del backend de negocio. La distinción importa.

### **Qué SÍ hacer: function calling contra el backend de negocio**

El patrón correcto es expresar la consulta como una **herramienta** que el LLM puede invocar, donde la implementación de la herramienta hace una llamada HTTP al backend de negocio, que es quien resuelve la consulta contra su propia BBDD y devuelve un payload limpio.

En diagrama:

```
LLM
 │  (decide invocar tool)
 ▼
Servicio IA (Python)
 │  (llamada HTTP autenticada)
 ▼
Backend de negocio (Rails u otro stack)
 │  (consulta su BBDD aplicando reglas de negocio)
 ▼
PostgreSQL del backend de negocio
```

El servicio IA define la herramienta:

```python
similar_projects_tool = {
    "type": "function",
    "function": {
        "name": "find_similar_projects",
        "description": (
            "Find historical projects with similar scope, technologies and team size. "
            "Returns aggregated metrics on actual hours, deviations and materialized risks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "technologies": {"type": "array", "items": {"type": "string"}},
                "team_size": {"type": "integer"},
                "scope_summary": {"type": "string"},
            },
            "required": ["technologies", "scope_summary"],
        },
    },
}
```

Y la implementación es un cliente HTTP al backend de negocio:

```python
async def find_similar_projects(
    technologies: list[str],
    scope_summary: str,
    team_size: int | None = None,
) -> dict:

    response = await http_client.post(
        f"{settings.business_backend_url}/api/internal/similar_projects",
        json={
            "technologies": technologies,
            "scope_summary": scope_summary,
            "team_size": team_size,
        },
        headers={"Authorization": f"Bearer {settings.internal_api_token}"},
    )
    
    response.raise_for_status()
    return response.json()
```

Por su parte, el backend de negocio expone el endpoint interno (en Ruby on Rails, alineado con la implementación de referencia del programa):

```ruby
# app/controllers/internal/similar_projects_controller.rb
module Internal
  class SimilarProjectsController < InternalApiController
    def create
      similar = Project.completed
        .with_any_technology(params[:technologies])
        .with_scope_similar_to(params[:scope_summary])
        .limit(5)

      render json: {
        projects: similar.map { |p| ProjectMetricsSerializer.new(p).as_json }
      }
    end
  end
end
```

Recuerda: el patrón es independiente del stack del backend de negocio. El cliente HTTP del servicio IA habla con cualquier backend que exponga un endpoint REST autenticado, sea Rails, NestJS, Spring, Django o un servicio Go.

### **Por qué este patrón es el correcto**

Esta arquitectura preserva las tres capas del programa de forma limpia. El servicio IA no sabe nada del schema de proyectos: solo sabe que existe una herramienta `find_similar_projects` que recibe ciertos parámetros y devuelve ciertos datos. El backend de negocio mantiene su autoridad sobre las reglas de qué cuenta como "proyecto similar" y qué métricas devolver. Y la BBDD operacional sigue siendo accedida solo desde donde debe.

Cuando construyamos RAG en el módulo 3, el patrón se va a complicar — la BBDD vectorial vivirá en el servicio IA y consultará por similitud semántica — pero la regla de aislamiento entre capas se mantiene: el servicio IA y el backend de negocio se hablan por contrato HTTP, nunca por BBDD compartida.

## **5. Combinando los tres mecanismos**

En un caso real del `estimator`, los tres mecanismos pueden coexistir en una misma petición. El usuario sube una transcripción y un PDF de especificación (mecanismo 1), el LLM decide que necesita los precios actuales de AWS para ciertos servicios mencionados (mecanismo 2), y también consulta los proyectos similares del histórico (mecanismo 3) antes de producir la estimación final.

![001-tres-mecanismos-contexto-dinamico.jpg](https://media1-production-mightynetworks.imgix.net/asset/4820cdea-f453-428f-b26f-a551af1140b0/001-tres-mecanismos-contexto-dinamico.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El patrón general que orquesta esto es el `agentic loop` que la Responses API ya implementa por defecto: el LLM razona, decide qué herramienta invocar, recibe los resultados, razona de nuevo, y o bien llama otra herramienta o bien produce la respuesta final. Tú expones las herramientas y dejas que el modelo decida la secuencia.

Hay dos disciplinas que cualquier sistema CAG enriquecido con contexto dinámico necesita interiorizar para funcionar bien en producción:

- **Budget de tokens.** La suma del system prompt + transcript + adjuntos + resultados de búsqueda + resultados de BBDD puede explotar la ventana de contexto rápidamente. Define un budget máximo por turno y aplica truncado o resumen cuando se supere.
- **Trazabilidad.** Cada herramienta invocada es un nuevo span observable. Conecta esto con la observabilidad estructurada que montaste en sesión 03 (`structlog` + Logfire/Langfuse). Un turno del `estimator` deja de ser una llamada al LLM y pasa a ser un grafo de invocaciones que necesita visibilidad de extremo a extremo.

## **6. Resumen: cuándo cada mecanismo**

Los tres mecanismos cubren tres tipos distintos de necesidad y deberías tenerlos clasificados mentalmente para elegir bien:

![image.png](https://media1-production-mightynetworks.imgix.net/asset/2218e7e5-36ac-4824-8ed6-4117da1137d1/9ad73802628d7859.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Las dos preguntas que debes hacerte antes de añadir cualquier mecanismo de contexto dinámico al sistema son siempre las mismas: ¿el modelo *podría* responder bien sin esta información, y solo va a responder mejor con ella, o sin esta información va a fallar de forma sistemática? Y, ¿la latencia añadida va a degradar la experiencia más que el valor que añade el contexto extra?

El instinto en sistemas con LLM tiende a ser "añade más contexto, no puede hacer daño". Sí puede. Más contexto significa más tokens en cada turno, más latencia, más superficie para `prompt injection`, más complejidad de debugging cuando algo va mal. La regla operativa es la opuesta: arranca con el mínimo contexto necesario, mide la calidad de las respuestas, y solo añade contexto dinámico cuando tengas evidencia de que el sistema lo necesita.

Los tres mecanismos que has visto aquí son las herramientas. La disciplina arquitectónica para usarlas con criterio es lo que separa un sistema CAG que escala de uno que se ahoga.