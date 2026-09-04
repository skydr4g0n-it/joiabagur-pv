# Auditoría e inventario de datos empresariales

Creada: 24 de mayo de 2026 12:57
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S6. Fundamentos de data driven AI - Análisis, formateo y normalización de datos existentes (https://app.notion.com/p/S6-Fundamentos-de-data-driven-AI-An-lisis-formateo-y-normalizaci-n-de-datos-existentes-36aea9ca03c480e2b5addae1d84e60ac?pvs=21)

La decisión arquitectónica está tomada: vamos a construir RAG con una capa residual de CAG. La tentación natural en este momento es escribir el primer loader, instalar pgvector y empezar a ver vectores. Vamos a resistir esa tentación durante un artículo más.

Imagina que el equipo te entrega lo que tienen. Hay una carpeta en Drive con presupuestos históricos en JSON. Hay un directorio en Dropbox con transcripciones de reuniones acumuladas durante tres años, algunas con nombres de fichero descriptivos y otras llamadas `meeting_final_v3_FINAL.txt`. Hay un repositorio Git con plantillas de propuesta en DOCX. Hay un Excel maestro donde alguien anotó las tarifas oficiales hace dos años y nadie está seguro de si sigue vigente. Hay una API interna que devuelve el listado de proyectos en curso, pero está documentada en una página de Confluence de hace año y medio que no se ha tocado desde entonces. ¿Por dónde empiezas?

Este artículo es la respuesta a esa pregunta. La respuesta, conviene decirlo de entrada, no es "empieza a vectorizar". Es "construye el inventario antes de tocar nada".

## **El antipatrón: vectorizar primero, mirar después**

El reflejo profesional del ingeniero senior, cuando le entregan un montón de datos, es ponerse manos a la obra. Hay un sesgo cultural en favor de la acción visible: una primera versión funcionando, aunque sea mala, se valora más que una semana invertida en inventariar. El problema es que en RAG ese reflejo tiene un coste asimétrico. Los errores derivados de saltarse la auditoría no aparecen el día 1; aparecen el día 60, cuando ya hay un pipeline construido sobre supuestos que nadie verificó.

Los modos de fallo típicos del antipatrón son tres. El primero es **mezcla silenciosa de versiones**: el corpus contiene dos versiones contradictorias del mismo presupuesto (la propuesta inicial y la firmada con cambios) y el RAG recupera la equivocada porque no hay metadato que las distinga. El segundo es **fuentes podridas**: documentos que parecen válidos pero contienen información obsoleta (políticas que cambiaron, tarifas que se actualizaron, clientes que ya no son clientes) y que generan respuestas seguras a preguntas para las que la verdad es lo contrario de lo que el sistema dice. El tercero es **gaps invisibles**: el sistema responde bien a las queries para las que hay datos, pero genera información plausible y falsa para las que no, porque nadie supo decirle al alumno que esa categoría de pregunta no está cubierta por el corpus.

Los tres modos de fallo tienen la misma raíz: el equipo nunca se sentó a mirar lo que había antes de procesarlo. La auditoría no es un trámite previo al trabajo real; **es el trabajo real**, y el coste de saltársela aparece amplificado en producción.

## **Inventario de fuentes: el censo de lo que tienes**

El primer paso operativo es construir un censo. Un censo es exactamente lo que parece: una lista de qué fuentes existen, dónde viven, quién las mantiene, qué formato tienen y qué volumen ocupan. Es información factual y verificable, no opinión.

Los campos mínimos que el censo debe capturar por cada fuente son:

- **Nombre lógico:** un identificador estable que vas a usar internamente (`historical_budgets`, no "los presupuestos viejos del Drive").
- **Localización física:** path o URL exacto donde vive la fuente, incluido el sistema de almacenamiento (Drive, Dropbox, S3, BBDD).
- **Owner técnico:** persona o equipo responsable de que la fuente exista y sea accesible. Es a quién llamas cuando la fuente se cae.
- **Owner de negocio:** persona o equipo responsable del contenido. Es a quién preguntas cuando el contenido es ambiguo o necesita interpretación.
- **Formato físico:** JSON, CSV, PDF, DOCX, TXT, fila de BBDD, respuesta de API.
- **Volumen actual:** número aproximado de registros y tamaño en disco.
- **Método de acceso:** FTP, API, descarga manual, query SQL.
- **Periodicidad declarada:** cada cuánto cambia oficialmente la fuente.
- **Periodicidad observada:** cada cuánto cambia realmente (no siempre coincide con la declarada).

Esa última pareja (declarada vs observada) suele revelar problemas que el equipo no había mirado nunca. Una fuente que oficialmente se actualiza mensualmente pero cuya última modificación es de hace siete meses no es una fuente con periodicidad mensual; es una fuente abandonada que alguien todavía piensa que está viva. Esa información es decisiva antes de meter sus contenidos al RAG.

El censo no se hace de cabeza; se hace ejecutando un script de inspección sobre las fuentes y completando manualmente los campos que el script no puede deducir. Para una fuente en sistema de ficheros, por ejemplo:

```python
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

@dataclass
class FilesystemSourceFacts:
    name: str
    path: Path
    file_count: int
    total_size_mb: float
    latest_modified: datetime
    formats_detected: set[str]

def inspect_filesystem_source(name: str, root: Path) -> FilesystemSourceFacts:
    """Collect verifiable facts about a filesystem-based source.

    Subjective fields (owner, sensitivity, reliability) are left to
    the human reviewer; this function only reports what can be
    measured directly from disk.
    """
    files = [f for f in root.rglob("*") if f.is_file()]
    total_bytes = sum(f.stat().st_size for f in files)
    latest_ts = max((f.stat().st_mtime for f in files), default=0)
    formats = {f.suffix.lower().lstrip(".") for f in files if f.suffix}

    return FilesystemSourceFacts(
        name=name,
        path=root,
        file_count=len(files),
        total_size_mb=round(total_bytes / (1024 * 1024), 2),
        latest_modified=datetime.fromtimestamp(latest_ts),
        formats_detected=formats,
    )
```

El script no es sofisticado. Su valor no está en lo que hace sino en que produce información factual y comparable entre fuentes, sin opinión. Sobre esa base se monta el resto de la auditoría.

## **Evaluación de calidad por dimensiones**

Una vez tienes el censo, toca evaluar la calidad de cada fuente. Y aquí conviene distinguir entre "datos abundantes" y "datos buenos", porque no son lo mismo. Una fuente con cien mil registros puede ser inservible para RAG si esos registros son inconsistentes entre sí. Una fuente con cincuenta registros puede ser oro si están bien estructurados, validados y trazados.

La evaluación se articula sobre cuatro dimensiones, cada una valorada en una escala simple (yo uso 1-5 por convención, pero cualquier escala consistente sirve):

**Completitud.** ¿Cuántos registros tienen todos los campos esperados? Si la fuente declara un schema (explícito o implícito), ¿qué porcentaje lo cumple? En el caso de presupuestos JSON, ¿cuántos tienen el campo `total_amount` rellenado correctamente, cuántos lo tienen como string en lugar de número, cuántos lo tienen vacío?

**Consistencia.** ¿El mismo concepto se representa de la misma forma a lo largo de la fuente? Si el mismo cliente aparece en treinta documentos, ¿se llama igual en los treinta? Si hay un campo `currency`, ¿toma los mismos valores normalizados (`EUR`, `USD`) o aparecen variantes (`euros`, `€`, `EUR`, `eur`)? Las inconsistencias son veneno para el chunking y el retrieval: dos fragmentos sobre el mismo cliente pueden quedar en regiones distintas del espacio vectorial porque su nombre se escribe distinto.

**Actualidad.** ¿Qué fecha tiene el último dato relevante? ¿La periodicidad declarada se cumple en la práctica? Una fuente con `last_modified` de hace dos años, aunque siga existiendo, probablemente no es una fuente viva. Decidir si merece la pena vectorizarla es una decisión arquitectónica: hay casos en que los datos antiguos son justo lo que el RAG necesita (precedentes históricos), y otros en que son contaminación pura (políticas obsoletas).

**Fiabilidad.** ¿La fuente es autoritativa o derivada? Una hoja de cálculo que alguien rellena a mano cada trimestre es menos fiable que el output de un sistema transaccional con validación. Las fuentes derivadas (extractos, resúmenes, copias) tienen además el problema añadido de quedarse desactualizadas respecto a su origen sin que nadie se dé cuenta.

Estas cuatro dimensiones se materializan en una estructura simple que se rellena por inspección manual de cada fuente, ayudándose del censo automático:

```python
from dataclasses import dataclass
from enum import IntEnum

class QualityScore(IntEnum):
    UNUSABLE = 1
    POOR = 2
    ACCEPTABLE = 3
    GOOD = 4
    EXCELLENT = 5

@dataclass
class QualityAssessment:
    completeness: QualityScore
    consistency: QualityScore
    actuality: QualityScore
    reliability: QualityScore
    notes: str

    @property
    def is_rag_ready(self) -> bool:
        """A source is RAG-ready when no dimension drags below acceptable.

        A single dimension at 1 or 2 typically poisons retrieval even if
        the others are excellent.
        """
        return all(
            score >= QualityScore.ACCEPTABLE
            for score in (
                self.completeness,
                self.consistency,
                self.actuality,
                self.reliability,
            )
        )
```

La regla de `is_rag_ready` es deliberadamente estricta. Un alumno familiarizado con métricas suele querer promediar las dimensiones, pero el promedio engaña: una fuente con `completeness=5` y `reliability=1` no es una fuente "de calidad 3"; es una fuente cuyos datos están completos pero pueden ser mentira, y eso es exactamente lo peor para RAG. Las dimensiones no se compensan entre sí; cada una es condición necesaria.

## **Linaje y context erosion**

Hay un quinto criterio que no encaja en la rúbrica anterior porque opera en otro plano. Se llama **linaje**, y su importancia para RAG es difícil de exagerar.

El linaje de un dato es el rastro de su origen y sus transformaciones: de dónde vino originalmente, qué procesos lo modificaron, quién fue el último en tocarlo y cuándo. En sistemas de business intelligence el linaje es una buena práctica; en RAG es una **condición de utilidad** del sistema.

El motivo es directo. Cuando un sistema RAG recupera un fragmento y lo presenta como evidencia para justificar una respuesta, el usuario necesita poder verificar la procedencia. Si el sistema dice *"este proyecto similar costó 80.000 €"* y la respuesta tiene que defender la cifra ante un cliente, hay tres preguntas que necesitan respuesta inmediata: ¿de qué documento concreto viene este dato? ¿cuándo se generó ese documento? ¿qué nivel de autoridad tiene (presupuesto inicial, propuesta revisada, contrato firmado)? Un RAG que no pueda contestar esas tres preguntas para cada chunk recuperado es un RAG inutilizable para casos serios.

El fenómeno opuesto, que destruye la utilidad del linaje, tiene también nombre: **context erosion**. Es la pérdida progresiva de contexto sobre el dato a medida que se mueve entre sistemas. El presupuesto firmado por el director comercial el 15 de marzo de 2024 sale de su sistema de gestión documental con todos sus metadatos intactos, pasa a una carpeta de Drive donde queda como `presupuesto_v3.pdf`, alguien lo descarga y lo renombra a `cliente_acme_2024.pdf`, alguien más lo procesa con un script que extrae solo el texto y produce `cliente_acme.txt`, y para cuando llega al pipeline de ingesta del RAG el sistema ya no tiene forma de saber si era una propuesta inicial o un contrato firmado. La información sigue ahí, pero el contexto que la hacía interpretable se ha evaporado.

![sesion_06_article_2_visual_1_context_erosion (1).jpg](https://media1-production-mightynetworks.imgix.net/asset/40f734f4-d17a-4db2-ba69-387d78898ad1/sesion_06_article_2_visual_1_context_erosion__1_.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Combatir la context erosion es la razón fundamental por la que el catálogo es un artefacto necesario. El catálogo es el sitio donde se preserva, por construcción y de forma versionada, todo el contexto que va a perderse si confías solo en los nombres de fichero y los metadatos sueltos de cada fuente.

## **El catálogo mínimo viable como YAML versionado**

Toda la información que hemos ido recolectando (censo factual, evaluación de calidad, decisiones de inclusión, notas de linaje) tiene que vivir en algún sitio. Mi recomendación, para programas como el nuestro y proyectos de tamaño medio, es: en el propio repositorio, como un YAML versionado.

La estructura del catálogo es sencilla, y deliberadamente plana:

```yaml
# data_catalog.yaml
version: 1
last_audited: "2026-05-15"

sources:
  - name: historical_budgets
    description: >
      Closed project budgets since 2020 stored as JSON.
      Source of truth for similar-project retrieval in the estimation system.
    location: drive://AI-Eng/budgets/
    owner_technical: data-platform@company.com
    owner_business: ops-lead@company.com
    format: json
    volume:
      records: 80
      size_mb: 12.4
    refresh:
      declared: monthly
      observed_last_update: "2026-04-15"
      observed_lag_days: 3
    quality:
      completeness: 4
      consistency: 3
      actuality: 5
      reliability: 5
    sensitivity:
      contains_pii: true
      pii_types: [client_names, hourly_rates, internal_margins]
      access_restrictions: internal-only
    lineage:
      upstream: erp-finance-module
      transformations: [export_to_json_quarterly]
    decision: include
    notes: >
      Budgets prior to 2022 use a legacy schema. Filter them out during
      ingestion until the migration script is rerun. Tracked in JIRA-1421.

  - name: meeting_transcripts
    description: >
      Verbatim transcripts of client kickoff and scoping meetings.
    location: dropbox://AI-Eng/transcripts/
    owner_technical: it-ops@company.com
    owner_business: pre-sales@company.com
    format: txt
    volume:
      records: 142
      size_mb: 38.7
    refresh:
      declared: weekly
      observed_last_update: "2026-05-12"
      observed_lag_days: 2
    quality:
      completeness: 5
      consistency: 2
      actuality: 5
      reliability: 4
    sensitivity:
      contains_pii: true
      pii_types: [client_names, personal_names, emails, phone_numbers]
      access_restrictions: internal-only
    lineage:
      upstream: automated-transcription-service
      transformations: [speech_to_text, manual_review]
    decision: review
    notes: >
      Inconsistent format across years: pre-2024 transcripts have no
      speaker tags. Review needed before deciding whether to include
      the legacy block.

  - name: official_rate_card
    description: >
      Official hourly rates per role and seniority.
    location: drive://AI-Eng/rates/rate_card_2024.xlsx
    owner_technical: finance@company.com
    owner_business: cfo-office@company.com
    format: xlsx
    volume:
      records: 1
      size_mb: 0.3
    refresh:
      declared: yearly
      observed_last_update: "2024-01-12"
      observed_lag_days: 480
    quality:
      completeness: 5
      consistency: 5
      actuality: 1
      reliability: 5
    sensitivity:
      contains_pii: false
    lineage:
      upstream: finance-spreadsheet-manual
      transformations: []
    decision: exclude
    notes: >
      Officially the source of truth for rates, but last update is from
      January 2024. CFO office confirms it does not reflect 2025 changes.
      Excluded until a refreshed version is provided.
```

El catálogo es más que documentación: es un artefacto de software. Cualquier código que toque las fuentes del proyecto debería leer este YAML al arrancar para saber qué procesar, qué excluir, y qué metadatos propagar a cada chunk. Eso significa que el catálogo también necesita un loader tipado:

```python
from pathlib import Path
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import yaml

class IngestionDecision(str, Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    REVIEW = "review"

class Volume(BaseModel):
    records: int
    size_mb: float

class Refresh(BaseModel):
    declared: str
    observed_last_update: str
    observed_lag_days: int

class Quality(BaseModel):
    completeness: int = Field(ge=1, le=5)
    consistency: int = Field(ge=1, le=5)
    actuality: int = Field(ge=1, le=5)
    reliability: int = Field(ge=1, le=5)

class Sensitivity(BaseModel):
    contains_pii: bool
    pii_types: list[str] = []
    access_restrictions: Optional[str] = None

class Lineage(BaseModel):
    upstream: str
    transformations: list[str] = []

class CatalogSource(BaseModel):
    name: str
    description: str
    location: str
    owner_technical: str
    owner_business: str
    format: str
    volume: Volume
    refresh: Refresh
    quality: Quality
    sensitivity: Sensitivity
    lineage: Lineage
    decision: IngestionDecision
    notes: Optional[str] = None

class DataCatalog(BaseModel):
    version: int
    last_audited: str
    sources: list[CatalogSource]

    def included_sources(self) -> list[CatalogSource]:
        return [s for s in self.sources if s.decision == IngestionDecision.INCLUDE]

def load_catalog(path: Path) -> DataCatalog:
    """Load and validate the data catalog from disk."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return DataCatalog(**raw)
```

Tres ventajas de tener el catálogo como código tipado y no como documento muerto. Primera, **validación automática**: un PR que rompe el schema del catálogo no llega a producción. Segunda, **acoplamiento explícito**: el pipeline de ingesta itera sobre `catalog.included_sources()` y propaga `lineage.upstream` y `sensitivity` como metadatos de cada chunk, sin intervención manual. Tercera, **trazabilidad de cambios**: el `git log` del YAML es el historial de cómo ha ido evolucionando el corpus del Proyecto 2, con quién decidió incluir o excluir cada fuente y por qué.

![sesion_06_article_2_visual_2_catalog_pipeline.jpg](https://media1-production-mightynetworks.imgix.net/asset/3f0bb2e0-2e90-4e51-bdb3-8a4fd0afb802/sesion_06_article_2_visual_2_catalog_pipeline.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **El reporte de auditoría como deliverable**

Sobre el catálogo se monta una pieza más, opcional pero recomendable: un reporte de auditoría que se genera automáticamente y que sirve para comunicar el estado del corpus a personas que no leen YAML. Un equipo de producto, un comité ejecutivo, un cliente que pide ver qué fuentes alimentan el sistema. El reporte se construye en seis o siete líneas, leyendo el catálogo y formateándolo a Markdown:

```python
def generate_audit_report(catalog: DataCatalog) -> str:
    """Generate a human-readable audit report from the catalog."""
    included = catalog.included_sources()
    excluded = [s for s in catalog.sources if s.decision == IngestionDecision.EXCLUDE]
    review = [s for s in catalog.sources if s.decision == IngestionDecision.REVIEW]

    lines = [
        f"# Data audit report — {catalog.last_audited}",
        f"\\n**Sources audited:** {len(catalog.sources)} | "
        f"**included:** {len(included)} | "
        f"**excluded:** {len(excluded)} | "
        f"**under review:** {len(review)}\\n",
        "## Included sources\\n",
    ]
    for s in included:
        lines.append(
            f"- **{s.name}** ({s.format}, {s.volume.records} records) — "
            f"owner: {s.owner_business}, last update: {s.refresh.observed_last_update}"
        )
    if excluded:
        lines.append("\\n## Excluded sources\\n")
        for s in excluded:
            lines.append(f"- **{s.name}** — reason: {s.notes or 'see catalog'}")
    return "\\n".join(lines)
```

Generar este reporte cada vez que el catálogo cambia (en CI, idealmente) es lo que convierte la auditoría en una práctica viva en lugar de una entrega de una sola vez. El catálogo no es un documento que se escribe al principio y se olvida; es un artefacto que respira con el proyecto.

## **Trade-offs honestos**

**Catálogo formal vs YAML en repo.** En el mercado existen plataformas profesionales de catalogación: Atlan, DataHub, Collibra, Microsoft Purview. Hacen mucho más que lo que hemos descrito aquí: descubrimiento automático de fuentes, linaje a nivel de columna, integración con sistemas de governance, glosarios de negocio. Tienen sentido en entornos con cientos de fuentes y equipos de data governance dedicados. Para un proyecto del tamaño del Proyecto (una o dos docenas de fuentes, un equipo pequeño), la sobrecarga operativa de mantener una herramienta así supera con creces el valor que aporta. El YAML versionado en repo es la opción correcta hasta que el número de fuentes empieza a crecer en serio o aparece un mandato regulatorio que obliga a una herramienta certificada. Cuando eso pase, migrar de YAML a una plataforma profesional es relativamente trivial; saltar directamente a la plataforma sin haber pasado por el YAML suele resultar en una herramienta cara y vacía.

**Auditoría exhaustiva vs suficiente para arrancar.** La tentación del ingeniero meticuloso es documentar todo perfectamente antes de empezar a procesar nada. El problema es que las fuentes son móviles: lo que documentes hoy va a estar desactualizado en dos meses. La auditoría inicial debe cubrir solo las fuentes que vas a incluir en el primer release del sistema, no todas las que existen en la organización. Las fuentes adicionales se incorporan al catálogo en el momento en que se decide incluirlas, no antes. El catálogo crece con el proyecto, no antes que él.

**Decidir qué dejar fuera deliberadamente.** Hay una falacia común entre alumnos que vienen de proyectos de data science clásica: pensar que toda fuente disponible debe ser usada. En RAG la falacia es especialmente peligrosa porque las fuentes malas no se manifiestan como ruido aleatorio (eso sería fácil de detectar) sino como respuestas seguras a información incorrecta. Excluir fuentes deliberadamente, dejando en el catálogo el registro escrito de por qué se excluyeron, es una práctica de higiene profesional que conviene normalizar desde el principio. El `rate_card_2024.xlsx` del ejemplo anterior es el caso típico: oficialmente es la fuente de la verdad para tarifas, pero está tan desactualizado que incluirlo introduciría errores sistemáticos. La decisión de excluirlo no es desidia; es disciplina arquitectónica.