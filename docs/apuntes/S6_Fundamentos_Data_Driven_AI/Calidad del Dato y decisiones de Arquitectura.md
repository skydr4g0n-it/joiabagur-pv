# Calidad del dato y decisiones de arquitectura

Creada: 24 de mayo de 2026 12:33
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S6. Fundamentos de data driven AI - Análisis, formateo y normalización de datos existentes (https://app.notion.com/p/S6-Fundamentos-de-data-driven-AI-An-lisis-formateo-y-normalizaci-n-de-datos-existentes-36aea9ca03c480e2b5addae1d84e60ac?pvs=21)

Si has hecho el ejercicio pre-sesión, has pasado las últimas horas mirando una hoja de cálculo de resultados que probablemente te ha sorprendido. Tu CAG, que cerraste en la Sesión 05 con la sensación legítima de que funcionaba bien, ha hecho cosas raras al alimentarlo con un corpus realista. Quizá ha alucinado sobre proyectos que no existen, quizá ha respondido con seguridad excesiva a preguntas para las que no tenía datos, quizá ha tardado quince segundos en una consulta que antes resolvía en dos, quizá te ha costado dos euros una respuesta. O quizá todo lo anterior a la vez.

Este artículo no va a explicarte qué es RAG. Va a explicarte por qué ese CAG se ha roto exactamente por donde se ha roto, y a darte un marco de decisión arquitectónica que vas a poder defender ante cualquier stakeholder. La diferencia es importante: a estas alturas del programa, *aplicar* RAG es lo fácil; lo difícil es saber cuándo aplicarlo, cuándo no, y cuándo combinarlo con lo que ya tienes.

## **El verdadero techo del CAG: no es solo el context window**

Cuando un ingeniero junior mira los modos de fallo del CAG sobre un corpus grande, su primera reacción suele ser identificar un único culpable: "no cabe en el contexto". Es una simplificación útil para empezar a hablar, pero engañosa. El CAG tiene un techo compuesto por cuatro restricciones que operan a la vez, y entender cada una es lo que permite tomar decisiones arquitectónicas no triviales.

La **primera restricción** es la que todo el mundo conoce: el context window. Tu modelo declara una capacidad máxima de tokens por llamada, y cuando el corpus supera ese umbral, el sistema no puede inyectarlo entero. Esta restricción es binaria y obvia.

La **segunda restricción** es el coste por consulta. Con corpus grandes y muchas consultas, el coste se dispara linealmente con los tokens de entrada. Un sistema que cuesta tres céntimos por consulta es perfectamente desplegable a producción; uno que cuesta dos euros no lo es para casi ningún caso de uso. Esta restricción es continua y suele ser la que mata el proyecto antes que la primera.

La **tercera restricción** es la latencia. Procesar un contexto de 100K tokens lleva varios segundos incluso en modelos optimizados. Para un asistente conversacional síncrono, eso es inviable. Para un proceso batch nocturno, irrelevante. La restricción depende del producto, no de la arquitectura.

La **cuarta restricción**, y la más subestimada, es la **degradación de atención sobre contextos largos**. Los modelos no procesan un contexto de 200K tokens con la misma fidelidad con la que procesan uno de 5K. El fenómeno está documentado como *lost in the middle*: la información colocada en la mitad del contexto se recupera peor que la colocada en los extremos. En términos prácticos, esto significa que aunque tu corpus *quepa* en el context window, no se está procesando con la misma calidad que si se inyectaran solo los fragmentos relevantes.

Conviene fijar las cuatro restricciones como un objeto formal antes de seguir:

python

```
from dataclasses import dataclass

@dataclass
class CAGViability:
    fits_in_context_window: bool      # ¿Cabe técnicamente?
    cost_per_query_acceptable: bool   # ¿Es viable económicamente?
    latency_acceptable: bool          # ¿Responde dentro del SLA del producto?
    quality_holds_with_load: bool     # ¿La calidad se mantiene con el corpus completo?

    def is_viable(self) -> bool:
        return all([
            self.fits_in_context_window,
            self.cost_per_query_acceptable,
            self.latency_acceptable,
            self.quality_holds_with_load,
        ])
```

Si has rellenado `CAG_LIMITS.md` con números reales, ya tienes los cuatro booleanos para tu caso. La conclusión empírica que probablemente has alcanzado es que basta con que uno falle para que la arquitectura no sea viable en producción. Y casi nunca falla solo uno.

## **Por qué la calidad del dato es la verdadera variable de control**

Hay una afirmación que aparece de forma recurrente en la literatura de RAG en producción y que merece la pena interiorizar: *no amount of clever chunking or fancy architecture can fix fundamentally bad data*. La cita es de un artículo de Towards Data Science que recoge lecciones de equipos que han operado sistemas RAG durante meses, y resume bien por qué el Módulo 3 abre el bloque de RAG con tres sesiones dedicadas a datos antes de tocar embeddings o bases vectoriales.

El razonamiento es directo. Un sistema RAG no genera información: la *recupera* y la *presenta*. Si lo que se recupera es ruido, lo que se presenta es ruido bien formateado. Si lo que se recupera es información desactualizada, lo que se presenta es desinformación con apariencia de respuesta autorizada. Si lo que se recupera está duplicado, inconsistente o mal estructurado, ningún reranker ni ningún cross-encoder van a arreglarlo en el momento de la consulta.

Esta es la diferencia operativa entre un equipo que pone un RAG en producción y un equipo que lo intenta. El primero invierte semanas o meses en la auditoría, normalización y validación del corpus antes de vectorizar nada. El segundo vectoriza inmediatamente para ver resultados rápido y luego pasa los siguientes seis meses intentando entender por qué el sistema responde mal de forma intermitente.

Lo que hace especialmente traicionero el problema de la calidad de datos en RAG es que **el sistema parece funcionar bien al principio**. Con un corpus pequeño y queries de prueba elegidas por el equipo, las respuestas son aceptables. La degradación aparece cuando el corpus crece, cuando los usuarios reales empiezan a hacer preguntas que el equipo no había anticipado, y cuando los datos se vuelven incongruentes consigo mismos (dos versiones contradictorias del mismo presupuesto coexistiendo en el índice, por ejemplo). En ese momento es muy tarde para arreglarlo, porque el pipeline ya está construido sobre supuestos que no se cumplen.

## **El pipeline RAG como abstracción de seis pasos**

Para razonar arquitectónicamente sobre RAG, conviene tener en la cabeza un modelo mental compartido del pipeline completo. La descomposición canónica, popularizada por equipos como Databricks, consta de seis pasos:

1. **Ingest** — recoger los datos de las fuentes empresariales (bases de datos, ficheros, APIs externas, sistemas de archivos).
2. **Parse** — extraer texto y metadatos limpios de cada formato (PDF, DOCX, JSON, transcripciones).
3. **Chunk** — trocear los documentos en fragmentos de tamaño adecuado para la vectorización.
4. **Embed** — convertir cada fragmento en un vector mediante un modelo de embeddings.
5. **Retrieve** — dada una consulta, recuperar los fragmentos más relevantes.
6. **Generate** — pasarle al LLM la consulta junto con los fragmentos recuperados para que componga la respuesta.

La trampa de esta lista es que parece sugerir un flujo lineal en tiempo real. No lo es. Los seis pasos se reparten en **dos pipelines distintos** que operan en momentos distintos y bajo restricciones distintas. Esta distinción es la primera decisión arquitectónica seria del Módulo 3.

## **Offline vs online: la línea que cambia toda la arquitectura**

![sesion_06_article_1_visual_1_rag_pipeline.jpg](https://media1-production-mightynetworks.imgix.net/asset/a36ab9c5-5461-4543-b9e1-1bb55b79fa41/sesion_06_article_1_visual_1_rag_pipeline.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Los pasos 1-4 (ingest → parse → chunk → embed) constituyen el **pipeline offline de indexación**. Se ejecuta en background, sin que haya un usuario esperando una respuesta. Puede tardar minutos u horas. Se dispara por eventos del sistema: subida de un nuevo documento, ejecución programada nocturna, refresco semanal de una fuente.

Los pasos 5-6 (retrieve → generate) constituyen el **pipeline online de consulta**. Se ejecuta síncronamente cuando un usuario hace una pregunta. Tiene presupuesto de latencia estricto (típicamente bajo 3 segundos para una experiencia conversacional aceptable). No tiene acceso a los datos crudos, solo a los vectores y metadatos previamente indexados.

Materializar esta separación en el servicio IA cambia radicalmente la estructura del proyecto. No es lo mismo un endpoint que hace todo en una sola llamada que dos endpoints con responsabilidades claramente disjuntas:

```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

app = FastAPI()

# ============================================================
# OFFLINE: indexing pipeline
# Triggered by ingestion events, not by user queries.
# Time budget: minutes to hours. No user waiting.
# ============================================================

class IngestRequest(BaseModel):
    source: str  # "budgets_json", "transcripts_txt", "proposals_pdf"
    document_ids: list[str]

@app.post("/index/run")
async def trigger_indexing(req: IngestRequest, tasks: BackgroundTasks):
    """Offline pipeline: parse -> chunk -> embed -> store."""
    tasks.add_task(run_indexing_pipeline, req.source, req.document_ids)
    return {"status": "scheduled", "documents": len(req.document_ids)}

async def run_indexing_pipeline(source: str, doc_ids: list[str]):
    documents = await load_documents(source, doc_ids)
    parsed = await parse_documents(documents)
    chunks = await chunk_documents(parsed)
    embeddings = await embed_chunks(chunks)
    await store_in_vector_db(chunks, embeddings)

# ============================================================
# ONLINE: retrieval + generation pipeline
# Triggered by user queries through the backend de negocio.
# Time budget: under 3 seconds. User is waiting.
# ============================================================

class QueryRequest(BaseModel):
    user_question: str
    top_k: int = 5

@app.post("/query")
async def answer_query(req: QueryRequest):
    """Online pipeline: retrieve -> augment -> generate."""
    relevant_chunks = await retrieve(req.user_question, top_k=req.top_k)
    augmented_prompt = build_prompt(req.user_question, relevant_chunks)
    answer = await call_llm(augmented_prompt)
    return {
        "answer": answer,
        "sources": [c.metadata for c in relevant_chunks],
    }
```

Esta separación tiene consecuencias prácticas inmediatas. El pipeline offline puede usar modelos pesados (extractores OCR, modelos de embeddings grandes, validadores estrictos) porque la latencia no importa. El pipeline online tiene que ser quirúrgico: solo búsqueda vectorial rápida, construcción del prompt y llamada al LLM. La mezcla de responsabilidades es uno de los antipatrones más comunes en sistemas RAG mal arquitecturados.

Para el backend de negocio (Rails u otro stack), esto significa que va a invocar al servicio IA por dos vías completamente distintas. La invocación de indexación es asíncrona (dispara y olvida, o consulta el estado después). La invocación de query es síncrona y bloqueante. Si esta distinción no está clara desde el primer día, terminas con un servicio IA que se cuelga porque está intentando indexar 200 PDFs mientras procesa una consulta de usuario.

## **La decisión arquitectónica: CAG, RAG, fine-tuning y combinaciones**

Hasta aquí hemos establecido el marco. Toca ahora el árbol de decisión, que es lo que un AI Engineer tiene que ser capaz de defender ante un Director de Producto cuando le pregunte por qué se gasta dinero en una arquitectura y no en otra.

La decisión se articula sobre cuatro ejes:

1. **Volumen del corpus** relativo al context window del modelo (con margen razonable: cargar el 95% del contexto es técnicamente posible pero degrada calidad).
2. **Frecuencia de actualización** de los datos (cada cuánto cambia el corpus).
3. **Requisito de trazabilidad** (si el sistema tiene que citar la fuente concreta de cada afirmación).
4. **Sensibilidad de los datos** (presencia de PII, requisitos de control de acceso por usuario).

![sesion_06_article_1_visual_2_decision_tree.jpg](https://media1-production-mightynetworks.imgix.net/asset/ae4eefe2-89d1-4fa6-bca7-d32203645f36/sesion_06_article_1_visual_2_decision_tree.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Materializar el árbol como código ayuda a clarificar la lógica:

```python
from dataclasses import dataclass
from enum import Enum

class Architecture(Enum):
    PURE_CAG = "pure_cag"
    HYBRID_CAG_RAG = "hybrid_cag_rag"
    PURE_RAG = "pure_rag"

@dataclass
class CorpusProfile:
    total_tokens: int
    update_frequency_days: int
    requires_source_attribution: bool
    requires_per_user_access_control: bool

@dataclass
class ModelProfile:
    context_window: int
    cost_per_million_input_tokens: float

def recommend_architecture(
    corpus: CorpusProfile, model: ModelProfile
) -> Architecture:
    context_usage = corpus.total_tokens / model.context_window

    # Si la trazabilidad es obligatoria, no hay decisión: RAG.
    # CAG no puede atribuir respuestas a fragmentos concretos.
    if corpus.requires_source_attribution:
        return Architecture.PURE_RAG

    # Si necesitamos control de acceso por usuario sobre el corpus,
    # CAG es inviable (todo el corpus va en cada llamada).
    if corpus.requires_per_user_access_control:
        return Architecture.PURE_RAG

    # Si no cabe con margen razonable, RAG.
    if context_usage > 0.7:
        return Architecture.PURE_RAG

    # Si cabe pero cambia muy a menudo, RAG (evita re-inyectar todo).
    if corpus.update_frequency_days < 7:
        return Architecture.PURE_RAG

    # Si cabe y es muy estable, CAG puro sigue siendo válido.
    if corpus.update_frequency_days > 90 and context_usage < 0.3:
        return Architecture.PURE_CAG

    # Resto de casos: híbrido. Contexto estable y pequeño en CAG;
    # corpus dinámico y voluminoso en RAG.
    return Architecture.HYBRID_CAG_RAG
```

La función es deliberadamente simple y no captura todos los matices. Su valor pedagógico es obligarte a explicitar los criterios. Cuando defiendas la elección de RAG ante un stakeholder, vas a hablar de esos cuatro ejes con números concretos, no de generalidades.

Falta un ángulo que no aparece en la función: **fine-tuning**. La razón de la omisión es que fine-tuning no es una alternativa a RAG; es una capa que puede sumarse encima de RAG (o de CAG) cuando se detectan limitaciones específicas que no se resuelven con mejor retrieval. Los casos típicos son: estilo de respuesta muy específico de la empresa, terminología propia que el modelo base no maneja bien, o formato estructurado que el modelo no respeta de forma consistente. Si la respuesta del modelo base sobre los fragmentos correctamente recuperados ya es buena, no hace falta fine-tuning. Si lo que recuperas es correcto pero el modelo lo presenta mal, sí lo necesitas. Lo que nunca funciona es usar fine-tuning como sustituto de un retrieval mal diseñado: estás enseñándole al modelo a memorizar lo que debería estar buscando.

## **El caso del Proyecto sobre el árbol**

Apliquemos el árbol al caso de uso del programa. Estamos construyendo un sistema que recibe transcripciones de reuniones de cliente y genera estimaciones de proyectos software basadas en histórico de presupuestos pasados.

- **Volumen:** crece linealmente con el negocio. Cada cliente nuevo aporta una transcripción más y, eventualmente, un presupuesto firmado más. Año a año son cientos de documentos.
- **Frecuencia de actualización:** alta. Cada semana hay reuniones nuevas; cada mes presupuestos cerrados.
- **Trazabilidad:** crítica. Si el sistema propone una estimación de 80.000 € para un proyecto, el equipo comercial necesita saber qué precedentes la justifican para defenderla ante el cliente. Una estimación sin referencias es inutilizable.
- **Sensibilidad:** alta. Las transcripciones contienen información comercial confidencial, nombres de clientes, condiciones contractuales. El control de acceso por proyecto y por equipo es un requisito.

Tres de los cuatro ejes empujan directamente a RAG. El árbol no deja margen: la elección está justificada. Pero hay un matiz que conviene preservar: hay partes del contexto que sí son pequeñas y estables, y para esas el CAG tradicional sigue siendo la mejor opción. Pienso por ejemplo en el glosario de tecnologías de la empresa, las plantillas estándar de presupuesto, los rangos de tarifas oficiales. Inyectarlo como contexto estático en cada llamada al LLM es más simple, más barato y más predecible que vectorizarlo. Por eso el árbol contempla la opción **híbrida**: el sistema final del Proyecto va a tener una capa de CAG conviviendo con la capa de RAG, no una sustituyendo a la otra.

## **Trade-offs honestos**

Quiero cerrar el artículo con tres trade-offs que se omiten habitualmente en la literatura promocional de RAG y que conviene mirar de frente antes de cerrar la decisión.

**El coste oculto de la trazabilidad.** Citar fuentes no es gratis. Requiere preservar metadatos en cada chunk (origen, página, fecha, autor), propagarlos por todo el pipeline, devolverlos al backend de negocio junto con la respuesta, y construir una UI que los presente al usuario. Es trabajo de diseño que muchos equipos infravaloran cuando estiman el coste de un RAG. Si tu producto puede permitirse no citar, el sistema entero se simplifica notablemente. Si no puede, ese coste va en el presupuesto.

**El coste real de operar RAG.** Las comparativas que ponen CAG y RAG en columnas adyacentes suelen ser tramposas. RAG no es solo el coste de la inferencia: añade el coste de embeddings (uno por chunk, una vez por ingesta), el coste de la base de datos vectorial (almacenamiento y compute), el coste de operación del pipeline de indexación, y el coste de las re-indexaciones cuando el modelo de embeddings cambia o cuando la estrategia de chunking se ajusta. Sumado todo, RAG puede ser más caro que CAG en corpus que caben en el context window, no más barato. La elección no se hace por coste; se hace por viabilidad y por funcionalidad.

**El CAG no muere, cambia de papel.** Una conclusión que sorprende a muchos alumnos es que el sistema final del programa no es "RAG en lugar de CAG", sino "RAG además de CAG". En cualquier arquitectura RAG seria coexisten dos tipos de contexto: el contexto estático del sistema (instrucciones, esquemas, glosarios) que se inyecta tal cual como en el Módulo 2, y el contexto recuperado dinámicamente que entra por la vía de RAG. Lo que has construido en el Módulo 2 no se tira; se reposiciona. Esa es la razón por la que el ejercicio pre-sesión te ha pedido pensar qué partes del corpus podrían quedarse en CAG. No era una pregunta retórica.

## **Bridge a la siguiente etapa**

Llegados a este punto, la decisión arquitectónica está tomada y justificada: RAG con capa estática residual de CAG. La tentación natural es saltar inmediatamente a la fase de implementación: instalar la base vectorial, elegir el modelo de embeddings, escribir el primer loader. Vamos a resistir esa tentación.

Antes de procesar ningún documento, antes de elegir un modelo de embeddings, antes de tocar una sola línea de pipeline, necesitamos hacer algo que muchos equipos saltan y luego pagan caro: **auditar lo que tenemos en la mesa**. Qué fuentes existen, en qué estado están, qué calidad tienen, qué falta. Sin esa fotografía, el resto del módulo se construye sobre arena.