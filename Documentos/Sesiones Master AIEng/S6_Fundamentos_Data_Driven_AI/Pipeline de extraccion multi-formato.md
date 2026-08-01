# Pipeline de extracción multi-formato

Creada: 24 de mayo de 2026 13:22
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S6. Fundamentos de data driven AI - Análisis, formateo y normalización de datos existentes (https://app.notion.com/p/S6-Fundamentos-de-data-driven-AI-An-lisis-formateo-y-normalizaci-n-de-datos-existentes-36aea9ca03c480e2b5addae1d84e60ac?pvs=21)

Con el catálogo cerrado tenemos un mapa de qué fuentes van a entrar al sistema. Ahora toca convertir el contenido físico de cada fuente en texto procesable. Para el Proyecto eso significa enfrentarse a cinco familias de formato: JSON (presupuestos históricos), TXT (transcripciones de reuniones), XLSX (tarifarios y maestros de datos), DOCX (plantillas de propuesta) y PDF (contratos firmados y propuestas con maquetación). Cada uno trae su propia maldición técnica.

Hay una tentación reconocible aquí: instalar `unstructured`, llamar a `partition()` y dar el problema por resuelto. Es la respuesta correcta a corto plazo y la incorrecta a medio plazo, por dos razones. Primera, `unstructured` con su modo de máxima precisión es lento y caro; usarlo indiscriminadamente sobre un corpus que mezcla JSON triviales con PDFs escaneados es despilfarrar recursos en los formatos que no lo necesitan. Segunda, y más importante, **delegar todo a una librería sin pensar en arquitectura es exactamente cómo se construyen los pipelines que dos meses después nadie entiende**. Este artículo propone el patrón opuesto: una arquitectura modular donde cada formato se trata con la herramienta correcta y todo confluye en un contrato común.

## **El contrato común: el `Document` canónico**

Antes de elegir un solo parser, conviene cerrar la pregunta más importante: ¿qué tiene que producir el subsistema `ingest/` para el resto del servicio IA? Si esa salida no está definida, cualquier diseño de los extractores es prematuro.

La respuesta es un objeto canónico que aparece en toda la literatura de RAG bajo nombres ligeramente distintos (`Document`, `Chunk`, `Passage`) y que tiene siempre dos campos esenciales: el contenido textual y los metadatos. En el caso del Proyecto:

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class DocumentMetadata(BaseModel):
    """Metadata propagated with every document through the pipeline.

    The first three fields come from the data catalog and are mandatory
    for every document, regardless of source format. The rest are
    populated by the parser when the format allows it.
    """
    source_name: str  # matches an entry in data_catalog.yaml
    source_location: str  # original physical path or URL
    ingested_at: datetime

    document_id: str  # stable identifier within the source
    document_title: Optional[str] = None
    document_created_at: Optional[datetime] = None
    document_author: Optional[str] = None

    page_number: Optional[int] = None  # for paginated formats
    section_title: Optional[str] = None  # for structured formats
    contains_pii: bool = False
    extra: dict = Field(default_factory=dict)

class Document(BaseModel):
    """The canonical output of the ingest subsystem.

    Every parser, regardless of input format, must produce instances
    of this class. Downstream chunking, embedding, and retrieval
    operate exclusively on Document objects.
    """
    content: str
    metadata: DocumentMetadata
```

Este modelo es deliberadamente plano. Tiene dos virtudes que conviene resaltar. Primera, **homogeneidad del contrato downstream**: el módulo de chunking no sabe (ni necesita saber) si el `Document` viene de un PDF escaneado o de un JSON estructurado. Procesa `content` y propaga `metadata` sin más. Segunda, **trazabilidad por construcción**: cada documento sabe de qué fuente del catálogo viene (`source_name`), dónde estaba originalmente (`source_location`) y, cuando el formato lo permite, en qué página o sección concreta. Esa información es la que llega hasta la respuesta final al usuario en forma de cita.

El campo `extra` como diccionario abierto es una válvula de escape consciente: permite que un parser específico (el de DOCX, por ejemplo) propague metadatos que no encajan en el schema canónico (campos de plantilla, comentarios, autoría de revisiones). Esos metadatos se preservan pero no se exigen a todos los parsers.

## **Arquitectura modular del subsistema `ingest/`**

Sobre el contrato canónico se monta una estructura de tres capas que separa responsabilidades por tipo de problema. Vamos a llamarlas `loaders`, `parsers` y `normalizers`, y conviene tener clara la frontera entre ellas porque mezclarlas es el error más común en pipelines de ingesta.

```
servicio_ia/
├── ingest/
│   ├── loaders/          # acceso físico a fuentes
│   │   ├── filesystem.py
│   │   ├── drive.py
│   │   └── http.py
│   ├── parsers/          # extracción por formato
│   │   ├── json_parser.py
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   ├── xlsx_parser.py
│   │   └── txt_parser.py
│   ├── normalizers/      # homogeneización a Document
│   │   └── canonical.py
│   ├── catalog.py        # loader del data_catalog.yaml (Article 2)
│   └── orchestrator.py   # pega todo y produce Document[]
└── ...
```

![sesion_06_article_3_visual_1_ingest_layers.jpg](https://media1-production-mightynetworks.imgix.net/asset/3af9c634-c6ff-4488-962e-391c5730910b/sesion_06_article_3_visual_1_ingest_layers.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Los **loaders** resuelven "cómo llego al fichero". Saben de paths de filesystem, URLs HTTP, autenticación de Drive, claves de S3. No saben qué hay dentro del fichero; solo lo entregan como bytes o stream. Esta separación importa porque un mismo formato (PDF, por ejemplo) puede vivir en Drive, en un bucket S3 o en disco local, y no queremos triplicar el parser de PDF por sitio donde vive.

Los **parsers** resuelven "qué hay dentro del fichero". Reciben bytes o un path local, eligen la librería adecuada según el formato, y producen una representación intermedia que ya es texto + metadatos del documento. Pero esa representación intermedia es específica del parser (un dataframe de pandas para Excel, una lista de elementos para PDF parseado con unstructured), no es el `Document` canónico todavía.

Los **normalizers** resuelven "cómo convierto la salida de mi parser al contrato canónico". Es la capa fina que toma la representación intermedia y la convierte en `Document` instances, propagando metadatos del catálogo y enriqueciéndolos con lo que aporta el parser.

La razón de tener tres capas en lugar de dos (parser que devuelve `Document` directamente) es testabilidad. Los parsers acaban siendo lógica compleja y dependiente de librerías externas pesadas; testearlos contra el contrato canónico significa tener que rellenar metadatos del catálogo en cada test. Separar la normalización permite testear los parsers contra su propia representación intermedia (fácil de mockear) y testear los normalizers contra el contrato canónico (también fácil). Cada test queda enfocado.

## **Estrategias de parsing por formato**

Cada formato pide una estrategia técnica distinta. La elección no es estética: tiene consecuencias en latencia, coste y calidad de la información extraída. Repaso las cinco familias del Proyecto.

**JSON** es el formato "fácil" porque ya tiene estructura. Para los presupuestos históricos del Proyecto, no hay que extraer texto: hay que decidir qué representación textual del JSON va a entrar al RAG. Volcar el JSON entero como string con `json.dumps()` genera embeddings ruidosos (mezcla claves técnicas con valores semánticos). Volcar solo los valores pierde el contexto de qué representa cada uno. La estrategia que mejor funciona en mi experiencia es **renderizar a markdown estructurado**: convertir cada presupuesto a un bloque legible con secciones, donde claves importantes se promueven a títulos y valores se ponen como prosa. Eso es trabajo de un parser que conoce el schema del JSON, no de un parser genérico.

**TXT** parece todavía más fácil pero esconde una trampa. Las transcripciones del Proyecto no son texto plano homogéneo: las que vienen del servicio automático de 2024 en adelante tienen `[hh:mm:ss] Speaker: ...`, las anteriores tienen formatos heterogéneos donde a veces se omite el speaker, a veces se agrupan turnos largos en un mismo bloque. Tratarlas todas como una bolsa de texto pierde una señal valiosísima: **quién dijo qué**. La estrategia correcta es un parser de transcripciones que detecta el formato y produce una representación con turnos identificados, donde cada turno se convierte después en un fragmento con metadatos `speaker` y `timestamp`. Lo que entra al RAG no es la transcripción cruda sino sus turnos enriquecidos.

**XLSX** es el formato más traicionero porque parece tabular pero rara vez lo es de verdad. Una hoja de Excel puede tener celdas combinadas, fórmulas que se evalúan en tiempo real, múltiples tablas en una misma hoja, comentarios flotantes, hojas ocultas, formato condicional que codifica información. Para el rate card del Proyecto (excluido del corpus, pero ilustrativo) la decisión correcta sería extraer la tabla principal con `openpyxl` o `pandas.read_excel()` y convertirla a markdown como tabla, perdiendo deliberadamente el resto. Si el Excel tiene contenido relevante en celdas no tabulares, hay que tratarlo como un caso especial. **La regla práctica: si el Excel es tabla pura, sale como tabla markdown; si tiene estructura compleja, no debería estar en el corpus o requiere conversión manual previa.**

**DOCX** es sorprendentemente amable. `python-docx` permite recorrer párrafos, tablas y headings con una API limpia, y los DOCX modernos tienen estructura semántica explícita (estilos de párrafo, niveles de heading) que se puede aprovechar para preservar la jerarquía del documento en la salida. Las plantillas de propuesta del Proyecto son un caso clásico: un parser DOCX bien hecho puede extraer secciones por heading (`Alcance`, `Entregables`, `Cronograma`) y emitir un `Document` por sección con el heading como `section_title`. Eso le da al RAG la posibilidad de recuperar la sección concreta, no la propuesta entera.

**PDF** es el infierno por motivos bien conocidos: el PDF es un formato de presentación, no de contenido. La estructura semántica está implícita en posiciones, fuentes y tamaños, no en una jerarquía explícita. Las opciones técnicas son tres:

1. `pypdf` o `pdfplumber` para texto plano: rápido y barato, pierde por completo tablas, columnas y estructura.
2. `pymupdf` (también conocido como `fitz`): mejor manejo de layout, soporta extracción de imágenes y bounding boxes. Buena opción cuando el PDF es texto digital limpio.
3. `unstructured` con strategy `hi_res`: usa modelos de visión por ordenador para detectar tablas, encabezados y secciones. Es la opción correcta cuando el PDF tiene tablas relevantes o cuando hay escaneos que requieren OCR. Es también la más lenta y cara con diferencia.

La regla que aplico para el Proyecto 2 (contratos firmados y propuestas finales en PDF): `pypdf` **por defecto para documentos generados digitalmente,** `unstructured` **con** `hi_res` **solo cuando se detecta que el PDF contiene tablas o es escaneado**. Esa decisión se toma una vez por fuente en el catálogo, no por documento.

## **El parser universal con `unstructured` como navaja suiza**

Existe una alternativa al patchwork anterior: usar `unstructured` para todo. La librería expone una función `partition()` que detecta el formato y aplica el extractor adecuado, devolviendo una lista de `Element` heterogéneos (`Title`, `NarrativeText`, `Table`, `ListItem`, etc.) con metadatos de localización.

Tiene ventajas reales: unifica el interface, soporta más de 20 formatos, tiene modelos de detección de estructura sorprendentemente buenos. Tiene también costes que conviene mirar de frente. El primero es de **peso**: instalar `unstructured[all-docs]` mete en la imagen Docker varios cientos de megabytes de dependencias (Tesseract, modelos de detección, PyTorch). El segundo es de **latencia y coste**: strategy `hi_res` es un orden de magnitud más lento que un parser nativo para PDFs simples, y para volúmenes grandes esto se nota en tiempo de indexación y factura de compute. El tercero, más sutil, es **opacidad**: cuando algo va mal con la extracción (una tabla que no se detecta, un heading que se categoriza como narrative), depurar es difícil porque buena parte del trabajo lo hace un modelo neuronal que no te explica sus decisiones.

Mi recomendación operativa para el Proyecto: **parsers nativos para los formatos cuya estructura es predecible** (JSON, TXT, XLSX simple, DOCX), `unstructured` **reservado para PDF cuando lo necesita** (tablas, escaneo) y como fallback opcional para formatos exóticos que aparezcan más adelante. El patrón es aprovechar la potencia de la librería sin convertirla en un punto único de dependencia que oscurece todo el pipeline.

## **Propagación de metadatos a través del pipeline**

Toda la decisión de tener un `Document` canónico se justifica en este punto: los metadatos que viajan con cada documento son los que permiten al RAG hacer citas y a los stakeholders verificarlas. La fuente de estos metadatos es triple.

**Metadatos del catálogo.** Son los que se conocen antes de tocar el documento concreto: nombre lógico de la fuente, owner de negocio, sensibilidad PII, restricciones de acceso, decisión de inclusión. Vienen del `data_catalog.yaml` que cerramos en el artículo anterior, y se aplican uniformemente a todos los documentos de esa fuente.

**Metadatos del parser.** Son los que se conocen después de procesar el documento concreto: título extraído de un encabezado, autor leído de los metadatos del fichero, fecha de creación, número de página, sección actual. Cada parser propaga los que el formato le permita.

**Metadatos del pipeline.** Son los que se conocen en el momento del procesamiento: `ingested_at` (timestamp del run de ingesta), versión del parser, configuración usada (strategy elegida, modelo de OCR). Estos son útiles para depuración y reproducibilidad.

![sesion_06_article_3_visual_2_metadata_propagation.jpg](https://media1-production-mightynetworks.imgix.net/asset/195e2e0a-7c86-4373-9a11-5a0c909625b9/sesion_06_article_3_visual_2_metadata_propagation.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El orquestador es quien combina las tres fuentes. Una implementación mínima del orquestador, asumiendo el `Document` y la arquitectura modular anteriores:

```python
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

class Parser(Protocol):
    """Contract that every format-specific parser must satisfy."""
    supported_formats: set[str]

    def parse(self, content: bytes, source_hint: str) -> list[Document]:
        """Parse raw bytes and return canonical Document instances.

        The parser populates content and the parser-known subset of
        metadata. The orchestrator enriches the result with catalog
        metadata and pipeline metadata before returning.
        """
        ...

def ingest_source(
    source: CatalogSource,
    loader: Loader,
    parsers: dict[str, Parser],
) -> list[Document]:
    """Run the full ingest pipeline for a single catalog source."""
    if source.decision != IngestionDecision.INCLUDE:
        return []

    parser = parsers.get(source.format)
    if parser is None:
        raise ValueError(f"No parser registered for format: {source.format}")

    raw_files = loader.list_files(source.location)
    documents: list[Document] = []
    pipeline_run_ts = datetime.now(timezone.utc)

    for file_ref in raw_files:
        content = loader.read(file_ref)
        parsed_docs = parser.parse(content, source_hint=file_ref.path)

        for doc in parsed_docs:
            # Enrich with catalog metadata (overrides parser defaults
            # where applicable).
            doc.metadata.source_name = source.name
            doc.metadata.source_location = source.location
            doc.metadata.ingested_at = pipeline_run_ts
            doc.metadata.contains_pii = source.sensitivity.contains_pii
            documents.append(doc)

    return documents
```

Tres detalles del diseño merecen comentario. Primero, `Parser` está definido como `Protocol` (structural typing) en lugar de clase abstracta. Esto permite que cualquier objeto que tenga el método `parse()` con la firma correcta sea un parser válido, sin forzar herencia. Es más flexible y se testea mejor. Segundo, el orquestador **respeta la decisión del catálogo**: una fuente con `decision: exclude` o `decision: review` no se procesa, sin importar que el fichero esté ahí. La disciplina arquitectónica del Article 2 se ejecuta automáticamente. Tercero, los metadatos del catálogo se aplican **después** del parser; esto significa que si un parser intentara falsificar el `source_name` (deliberadamente o por bug), el orquestador lo sobrescribe con el valor canónico del catálogo. Defensa en profundidad.

## **Trade-offs honestos**

**Parsers nativos vs** `unstructured` **universal.** Hay equipos que adoptan `unstructured` como interface único y otros que mantienen parsers por formato. La elección no es de tribu sino de contexto. Para un corpus con cinco o seis formatos predecibles (el caso del Proyecto), parsers nativos son más rápidos, más baratos y más fáciles de depurar. Para un corpus con docenas de formatos heterogéneos donde el equipo no va a invertir en cada uno, `unstructured` evita reinventar veinte ruedas. La regla que aplico es: cuento los formatos del catálogo, y si son menos de cinco-seis y todos se entienden bien, voy a parsers nativos; si son más o son impredecibles, voy a `unstructured` salvo en los casos donde el coste/latencia obligan a hacer una excepción específica.

**Strategy** `hi_res` **vs** `fast` **en PDF.** La tentación de usar `hi_res` para todo el corpus por seguridad es comprensible y peligrosa. Sobre cien PDFs, `hi_res` puede tardar veinte veces más que `fast` y costar veinte veces más en compute, mientras que sobre los noventa PDFs que son texto digital limpio no aporta nada respecto a `fast`. La regla práctica: clasificar los PDFs en el catálogo (digital limpio, digital con tablas, escaneado) y aplicar la strategy correspondiente. La clasificación es un trabajo manual de una vez; el ahorro es continuo.

**Pérdida de información estructural aceptable.** Hay información en los formatos originales que no va a sobrevivir al pipeline de ingesta, y conviene decidir conscientemente qué pierdes. Las imágenes embebidas en DOCX, los comentarios en revisiones de Word, las anotaciones en márgenes de PDF, el formato condicional en Excel. Para un RAG de estimación de proyectos como el del Proyecto, todo eso es ruido prescindible. Para un RAG de revisión legal de contratos, las anotaciones serían información crítica. La decisión depende del caso de uso; lo que no es aceptable es perder información estructural por descuido en lugar de por diseño.

## **Bridge a la siguiente etapa**

Llegados a este punto tenemos un subsistema `ingest/` capaz de leer cualquier fuente del catálogo, procesarla con el parser adecuado, y producir una lista de `Document` canónicos con metadatos propagados. Es un avance grande respecto al estado anterior, pero falta una pieza imprescindible antes de poder vectorizar nada.

El texto que producen los parsers está extraído pero no está limpio. Los presupuestos JSON tienen fechas en tres formatos distintos (`2024-03-15`, `15/03/2024`, `Mar 15 2024`), las monedas aparecen como `EUR`, `eur`, `€`, los nombres de clientes tienen variantes ortográficas, hay registros duplicados con valores divergentes en algún campo, y hay campos que el parser ha rellenado con `None` cuando el documento original tenía datos pero el extractor no los encontró. Si pasamos esto directamente al chunking y al embedding, el ruido se propaga al espacio vectorial y el retrieval se degrada de formas sutiles que el equipo va a tardar meses en diagnosticar.