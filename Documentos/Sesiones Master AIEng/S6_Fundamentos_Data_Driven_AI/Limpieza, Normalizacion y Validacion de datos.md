# Limpieza, normalización y validación de datos

Creada: 24 de mayo de 2026 13:46
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S6. Fundamentos de data driven AI - Análisis, formateo y normalización de datos existentes (https://app.notion.com/p/S6-Fundamentos-de-data-driven-AI-An-lisis-formateo-y-normalizaci-n-de-datos-existentes-36aea9ca03c480e2b5addae1d84e60ac?pvs=21)

En el artículo anterior cerramos el subsistema `ingest/` que produce `Document`s canónicos a partir de cualquier formato. Esos `Document`s cumplen el contrato Pydantic: tienen un `content` no vacío y un `metadata` con los campos requeridos. El contrato es necesario, pero es solo el contrato de **forma**. No dice nada del contrato de **contenido**.

Dos `Document`s pueden cumplir perfectamente el contrato Pydantic y al mismo tiempo ser radicalmente incompatibles para el RAG. Un presupuesto con `client_name: "ACME Corp."` y otro con `client_name: "Acme Corp"` son válidos individualmente, pero cuando entran al espacio vectorial los embeddings los tratan como entidades distintas y el retrieval falla en silencio. Un campo `total_amount: -50000` pasa la validación de tipo (es un número) y rompe cualquier análisis aritmético posterior. Una fecha guardada como string `"15/03/2024"` y otra como `"2024-03-15"` son ambas strings, ambas válidas, y radicalmente diferentes para cualquier filtrado temporal del retrieval.

El contrato Pydantic es la primera línea de defensa, pero no es la última. Este artículo monta la segunda: **la capa de limpieza y validación que garantiza el contrato de contenido antes de que los datos lleguen al embedding**.

## **Cuatro familias de "suciedad" en datos para RAG**

Antes de elegir herramientas conviene tener un vocabulario común para los problemas que vamos a resolver. En sistemas RAG empresariales hay cuatro familias recurrentes de suciedad que merecen nombre propio porque cada una daña al sistema de una manera específica.

![sesion_06_article_4_visual_1_four_families.jpg](https://media1-production-mightynetworks.imgix.net/asset/d71cbf17-fd76-4bc6-9874-eab20b84cca0/sesion_06_article_4_visual_1_four_families.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Heterogeneidad de formato.** La misma cosa escrita de N maneras distintas. Fechas como `15/03/2024`, `2024-03-15`, `March 15, 2024` y `15-Mar-24` conviviendo en el mismo corpus. Monedas como `EUR`, `eur`, `€`, `euros`. Identificadores de cliente como `ACME`, `Acme Corp.`, `Acme Corp`, `acme-corp`. Para un sistema RAG esto es veneno porque los embeddings tratan cada variante como un token diferente: dos fragmentos sobre el mismo cliente acaban en regiones distantes del espacio vectorial, y el retrieval pierde precisamente la señal que el equipo asumía obvia.

**Duplicados con divergencias.** El mismo registro existe dos veces con valores distintos en algún campo. Un presupuesto está en el JSON exportado del ERP con `total: 80000` y en la copia manual del responsable con `total: 82500` (porque alguien hizo un ajuste a mano y nadie sincronizó). Si ambos entran al RAG, el sistema va a recuperar el que el chunker indexe primero, sin manera de saber cuál es la versión correcta. La respuesta al usuario va a depender de un orden de procesamiento que el equipo no controla. Diagnosticar este modo de fallo en producción puede llevar semanas porque el sistema no se rompe; simplemente da respuestas inconsistentes que parecen "ruido del LLM".

**Valores nulos disfrazados.** Campos que parecen rellenados pero no contienen información. La cadena `"N/A"`, `"-"`, `"unknown"`, `"TBD"`, `"pendiente"`, una cadena vacía, un único espacio en blanco. Estos valores son técnicamente válidos (son strings), pasan cualquier validación de tipo, y al llegar al pipeline de embedding se vectorizan como si fueran contenido real. El resultado es que el RAG aprende a "recuperar" estos valores como si tuvieran significado, y los presenta al usuario con la misma autoridad que el contenido real.

**Valores fuera de rango.** Presupuestos con `total: -50000`, fechas de finalización anteriores a las de inicio, porcentajes mayores de 100, campos `hours_estimated` con valores en el orden de los millones. La mayoría de estos errores se originan en transcripción manual o en bugs de sistemas upstream que el equipo del RAG no controla. Su impacto en el RAG es asimétrico: rara vez se recuperan (los embeddings los aíslan), pero cuando se recuperan generan respuestas con confianza alta sobre afirmaciones absurdas, que son las que más caro pagan los stakeholders en credibilidad del sistema.

Las cuatro familias se combaten con técnicas distintas, pero todas requieren una misma decisión arquitectónica: **un punto único del pipeline donde se aplican las reglas, con un contrato explícito de qué pasa y qué no pasa**.

## **Dónde colocar la capa de limpieza**

La tentación natural cuando uno descubre estos problemas es resolverlos donde los descubre: el chunker detecta un campo vacío, el embedder encuentra un duplicado, el retriever filtra valores fuera de rango. Cada capa va parcheando sobre la marcha.

Es exactamente lo que no hay que hacer.

Cuando la limpieza está repartida entre el chunker, el embedder y el retriever, pasan tres cosas predecibles. La primera es que **las reglas dejan de ser auditables**: no hay un sitio donde decir "estos son nuestros invariantes de datos", están dispersas en condicionales sueltos a lo largo de tres módulos. La segunda es que **los tests se vuelven imposibles**: testear el chunker requiere mockear validaciones que en realidad pertenecen a otra capa. La tercera, la más cara, es que **el sistema acaba sin un único punto donde un fallo pueda detenerlo**: un registro malformado se cuela en el chunker, sobrevive al embedder, y aparece en el retrieval con consecuencias visibles seis semanas más tarde.

La capa de limpieza tiene que ser un **módulo separado** del pipeline, con su propia ubicación clara, sus propios tests, y sus propias garantías formales. Recordando la arquitectura del Article 3 (`loaders → parsers → normalizers → Document`), la posición natural es **entre el parser y el normalizer**: el parser produce su representación intermedia, esa representación pasa por la capa de limpieza, y solo entonces se convierte al `Document` canónico. Para los formatos tabulares (los presupuestos JSON del Proyecto son el ejemplo paradigmático), la representación intermedia es naturalmente un `DataFrame` de pandas, y la capa de limpieza opera sobre él.

Esto no significa que los formatos no tabulares (PDF, DOCX, TXT) escapen a la validación. Sus representaciones intermedias son listas de elementos o texto, y sobre ellas se aplican técnicas diferentes (regex para formatos esperados, validación de encoding, longitud mínima, detección de placeholders). Pero el caso que ilumina mejor el patrón es el tabular, y es donde Pandera tiene su valor más alto, así que es donde voy a profundizar.

## **Limpieza con pandas sobre la representación intermedia**

El parser de presupuestos JSON del Proyecto produce un DataFrame con columnas como `budget_id`, `client_name`, `total_amount`, `currency`, `signed_at`, `status`. Antes de generar los `Document`s, ese DataFrame pasa por una secuencia de transformaciones que normalizan formatos y eliminan registros corruptos:

```python
import pandas as pd
import hashlib
from datetime import datetime

NULL_PLACEHOLDERS = {"", "n/a", "na", "-", "--", "unknown", "tbd", "pendiente"}

def clean_budget_records(df: pd.DataFrame) -> pd.DataFrame:
    """Apply canonical cleaning operations to budget records.

    Each step is intentionally narrow and side-effect free so it can be
    unit-tested in isolation. The order matters: nulls before dedup,
    formatting before validation downstream.
    """
    out = df.copy()

    # 1. Disguised nulls -> real NaN
    out["client_name"] = (
        out["client_name"].astype(str).str.strip().str.lower()
        .where(lambda s: ~s.isin(NULL_PLACEHOLDERS), other=pd.NA)
    )

    # 2. Currency normalization
    currency_map = {"eur": "EUR", "euros": "EUR", "€": "EUR",
                    "usd": "USD", "$": "USD"}
    out["currency"] = (
        out["currency"].astype(str).str.strip().str.lower()
        .map(currency_map).fillna(out["currency"])
    )

    # 3. Date parsing with explicit fallback
    out["signed_at"] = pd.to_datetime(
        out["signed_at"], errors="coerce", utc=True
    )

    # 4. Numeric coercion for amounts (string "80000" -> 80000.0)
    out["total_amount"] = pd.to_numeric(out["total_amount"], errors="coerce")

    # 5. Content-hash dedup: keep the latest version per budget_id
    out["content_hash"] = out.apply(
        lambda r: hashlib.sha256(
            f"{r['budget_id']}|{r['total_amount']}|{r['currency']}".encode()
        ).hexdigest(),
        axis=1,
    )
    out = out.sort_values("signed_at").drop_duplicates(
        subset=["budget_id"], keep="last"
    )

    return out.drop(columns=["content_hash"])
```

Tres detalles del diseño merecen comentario. Primero, **cada paso es estrechamente acotado**: se hace una cosa y se mueve. Esto facilita testear cada transformación en aislamiento y también facilita razonar sobre el resultado: si algo va mal, la lista de sospechosos es corta. Segundo, el **paso 5 (dedup por hash de contenido)** ataca específicamente la familia "duplicados con divergencias": si el mismo `budget_id` aparece dos veces con valores distintos, los hashes son distintos, y la regla "quédate con el último según `signed_at`" decide cuál sobrevive. La regla es discutible y debe ser una **decisión consciente del equipo** documentada en el catálogo. Tercero, **las coerciones permisivas** (`errors="coerce"`) convierten valores inválidos en `NaN` en lugar de tirar excepción. Esto separa la limpieza de la validación: aquí transformamos lo que se puede transformar; la validación posterior decide qué hacer con los `NaN` resultantes.

Esta función es la primera mitad. Es donde se aplican las reglas de normalización. Pero no decide nada: deja registros con campos vacíos, valores fuera de rango, fechas no parseables como `NaT`. La decisión de qué pasa con esos registros es de la capa de validación.

## **Pandera como contrato de datos**

Pandera es una librería de validación de dataframes que cumple con pandas (y polars, dask, etc.) el mismo papel que Pydantic con instancias individuales. Donde Pydantic dice "este objeto cumple este schema o tira excepción", Pandera dice "este DataFrame cumple este schema columna a columna y fila a fila, o produce un reporte detallado de qué filas fallan y por qué".

Para el Proyecto, el schema canónico de presupuestos en Pandera se ve así:

```python
import pandera.pandas as pa
from pandera.pandas import DataFrameModel, Field, Check
from pandera.typing.pandas import Series
import pandas as pd
from datetime import datetime, timezone

class BudgetRecord(DataFrameModel):
    """Canonical contract for budget records before normalization to Document.

    Any DataFrame produced by the budget cleaning pipeline must validate
    against this schema. Records that fail validation are routed to
    quarantine or discarded according to severity.
    """
    budget_id: Series[str] = Field(
        str_matches=r"^BUDGET-\\d{4}-\\d{4}$",
        description="Stable budget identifier in canonical format",
    )
    client_name: Series[str] = Field(
        nullable=False,
        str_length={"min_value": 2, "max_value": 200},
    )
    total_amount: Series[float] = Field(
        ge=0,
        le=10_000_000,
        nullable=False,
        description="Total in declared currency, non-negative",
    )
    currency: Series[str] = Field(isin=["EUR", "USD", "GBP"])
    signed_at: Series[pd.Timestamp] = Field(
        nullable=False,
        le=datetime.now(timezone.utc),
        description="Sign date must be in the past",
    )
    status: Series[str] = Field(isin=["draft", "signed", "rejected"])

    class Config:
        strict = True            # reject unknown columns
        coerce = False           # cleaning has already coerced types
        ordered = False

    @pa.dataframe_check
    def positive_amount_for_signed(cls, df: pd.DataFrame) -> Series[bool]:
        """Signed budgets must have positive amounts.

        Cross-column rule: status='signed' implies total_amount > 0.
        """
        return ~((df["status"] == "signed") & (df["total_amount"] == 0))
```

La diferencia conceptual con Pydantic es la dimensión sobre la que validan. Pydantic valida una instancia, devuelve éxito o excepción. Pandera valida un DataFrame entero, y al fallar devuelve un objeto `SchemaErrors` que detalla **qué filas fallaron, en qué columnas, y por qué**. Eso es exactamente la información que necesita la siguiente capa para decidir entre reparar, mandar a cuarentena o descartar.

Hay tres elementos del schema anterior que vale la pena destacar. El primero son los **checks de campo**: `ge=0`, `le=10_000_000`, `str_matches=r"^BUDGET-\\d{4}-\\d{4}$"`. Cada uno expresa un invariante de negocio que el equipo se ha comprometido a respetar. La forma del `budget_id` no es un detalle estético; es un contrato con el sistema upstream. El segundo son los **checks cross-column** vía `@pa.dataframe_check`: reglas que relacionan varias columnas, como "si el estado es `signed`, el total no puede ser cero". Estas reglas son las que detectan las inconsistencias más sutiles, y son las que un schema basado solo en Pydantic no puede expresar. El tercero es la **configuración** del schema: `strict=True` rechaza columnas no declaradas (defensa contra cambios silenciosos del parser), `coerce=False` asume que la limpieza previa ya hizo las coerciones (separación de responsabilidades clara).

El contrato Pandera es una pieza viva del proyecto. Cuando el equipo de negocio decide aceptar una nueva moneda, cuando se introduce un nuevo estado de presupuesto, cuando el límite máximo de proyecto cambia, el cambio se hace **en este fichero y solo en este fichero**, queda versionado en git, y todo el pipeline downstream lo respeta automáticamente. Es el equivalente para datos del `data_catalog.yaml` para fuentes.

## **La estrategia de fallo: reparar, cuarentena, descartar**

Cuando una fila falla la validación, hay tres respuestas posibles, y la decisión depende del tipo de fallo. La política tiene que ser explícita y documentada, no implícita en el código.

**Reparar automáticamente** cuando el fallo es recuperable sin pérdida semántica. Una fecha en formato `"15/03/2024"` que `pd.to_datetime` no parseó con el formato esperado pero que sí parsea con `dayfirst=True`. Un valor de currency `"euros"` que no estaba en el mapa pero claramente debe ir a `"EUR"`. Estos casos se resuelven con una pasada adicional de limpieza específica para los errores detectados, **sin intervención humana**.

**Mandar a cuarentena** cuando el fallo es grave pero el registro podría ser útil tras revisión. Un `client_name` con un valor nulo cuando el resto del registro está completo; un `total_amount` ligeramente por encima del límite máximo que podría ser un proyecto excepcional legítimo o un error de tipeo. Estos registros **no entran al RAG**, pero **se preservan** en una tabla separada con su motivo de cuarentena, accesible para que un humano decida después. Es el equivalente al limbo: ni dentro ni fuera, esperando arbitraje.

**Descartar** cuando el fallo indica contaminación clara y no aporta valor. Un registro con `budget_id` que no cumple el patrón canónico (probablemente un artefacto de migración mal hecha); un `total_amount` negativo o cien veces el límite máximo. Estos registros **se eliminan con log detallado** pero sin reserva: están más allá del rescate y no merecen ocupar espacio en cuarentena.

![sesion_06_article_4_visual_2_validation_routing.jpg](https://media1-production-mightynetworks.imgix.net/asset/5c950d44-b2ef-415a-b5b7-74f7bcad91c4/sesion_06_article_4_visual_2_validation_routing.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Materializar esta política en código necesita una capa más, el orquestador de la validación:

```python
from dataclasses import dataclass
from typing import Literal
import pandera.pandas as pa
import pandas as pd
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    valid: pd.DataFrame
    quarantined: pd.DataFrame
    discarded: pd.DataFrame
    report: dict

QUARANTINE_REASONS = {
    "nullable_violation": "missing required field",
    "client_name_str_length": "client name length out of range",
}

def validate_with_policy(
    df: pd.DataFrame, schema: type[pa.DataFrameModel]
) -> ValidationResult:
    """Validate a dataframe and route failures by policy.

    Reparable failures are not handled here — assume the cleaning step
    has already attempted recovery. Anything still failing is either
    quarantined (recoverable with human review) or discarded.
    """
    try:
        valid = schema.validate(df, lazy=True)
        return ValidationResult(
            valid=valid, quarantined=pd.DataFrame(), discarded=pd.DataFrame(),
            report={"total": len(df), "valid": len(df)},
        )
    except pa.errors.SchemaErrors as exc:
        failure_cases = exc.failure_cases
        failed_indices = failure_cases["index"].dropna().unique()
        failed_rows = df.loc[failed_indices].copy()

        # Discard policy: structural failures that signal contamination
        is_discard = failure_cases["check"].isin([
            "str_matches", "ge(0)", "le(10000000)"
        ])
        discard_indices = (
            failure_cases.loc[is_discard, "index"].dropna().unique()
        )
        quarantine_indices = [
            i for i in failed_indices if i not in discard_indices
        ]

        valid_indices = df.index.difference(failed_indices)
        valid = df.loc[valid_indices]
        discarded = df.loc[discard_indices].copy()
        quarantined = df.loc[quarantine_indices].copy()

        logger.warning(
            "validation: valid=%d quarantined=%d discarded=%d",
            len(valid), len(quarantined), len(discarded),
        )

        return ValidationResult(
            valid=valid, quarantined=quarantined, discarded=discarded,
            report={
                "total": len(df),
                "valid": len(valid),
                "quarantined": len(quarantined),
                "discarded": len(discarded),
                "failure_breakdown": failure_cases["check"].value_counts().to_dict(),
            },
        )
```

Dos detalles del diseño merecen subrayado. Primero, `lazy=True` en la llamada a `schema.validate()`: en lugar de fallar en el primer error, Pandera recoge todos los errores del DataFrame y los devuelve juntos. Esto es lo que permite la política diferenciada por tipo de fallo; sin `lazy=True` solo conoceríamos el primer error y la política sería ciega. Segundo, **el resultado siempre incluye el report**: el orquestador no solo decide qué pasa con los datos, también deja métricas para observabilidad. Cuántos registros válidos pasaron, cuántos quedaron en cuarentena, qué tipos de fallo predominan. Esa información es la que va a alertarte cuando una fuente empieza a degradarse, mucho antes de que el degradado llegue al RAG.

## **Trade-offs honestos**

**Pandera vs Great Expectations.** Ambas son librerías de validación de datos con tracciones diferentes. Pandera es **ligera, integrada en código Python, declarativa** mediante DataFrameModel: tu schema es una clase Python que vive con tu código y se versiona con él. Great Expectations es **más ambiciosa**: ofrece datadocs (documentación HTML auto-generada del estado del corpus), profiling automático, integración nativa con orquestadores como Airflow y Dagster, y un modelo de expectations que es más expresivo pero también más pesado de operar. Para un proyecto del tamaño del Proyecto (un servicio IA, un equipo pequeño, validación inline en el pipeline), Pandera es la elección correcta: zero infrastructure overhead, schemas que se entienden en cinco segundos y se modifican en cinco minutos. Great Expectations tiene sentido cuando el sistema escala a docenas de pipelines con stakeholders no técnicos que necesitan ver el estado del data quality, o cuando hay un equipo dedicado a data engineering que va a operarlo. Antes de migrar de Pandera a Great Expectations, conviene tener motivos concretos; migrar por defecto suele significar pagar la complejidad sin necesitar las features.

**Strict mode en producción vs permisividad en desarrollo.** En desarrollo es comprensible que un alumno quiera relajar el schema para que "todo pase mientras itero". El instinto correcto es **el opuesto**: el schema debe ser estricto **desde el primer día**, y lo que se relaja es la política ante fallos, no el contrato. En desarrollo, mandar a cuarentena en lugar de descartar permite ver los datos problemáticos sin que el pipeline se rompa; en producción, descartar evita que el corpus se contamine. Pero el contrato de qué es válido y qué no es el mismo, y es exactamente lo que estaba documentado y testeado en desarrollo. Cuando el contrato es laxo en desarrollo, los problemas aparecen el día del despliegue a producción.

**Cuánto normalizar sin perder señal.** La tentación de normalizar agresivamente para reducir variantes es real y peligrosa. Pasar todos los nombres de cliente a minúsculas resuelve "ACME Corp" vs "acme corp" pero borra deliberadamente la diferencia entre "Apple" (empresa) y "apple" (fruta) si por alguna razón ambas aparecen en el corpus. Sustituir todos los espacios múltiples por uno facilita la dedup pero borra estructura intencional en transcripciones formateadas. La regla heurística que aplico: **normalizar con el bisturí, no con la motosierra**. Normalizar primero los casos donde la heterogeneidad es claramente accidental (variantes de mayúsculas y minúsculas en monedas, espacios trailing, separadores de fecha) y dejar para una segunda iteración (o nunca) los casos donde la normalización podría borrar señal semántica.

## **Bridge a la siguiente etapa**

Llegados a este punto los `Document`s del Proyecto 2 cumplen el contrato de forma (Pydantic en el subsistema `ingest/`) y el contrato de contenido (Pandera en la capa de validación). Los registros que pasan están limpios, normalizados y dentro de los invariantes de negocio. Los que no pasan están en cuarentena o descartados con log. El corpus está, por primera vez, **en estado de pasar al embedding sin contaminar el espacio vectorial**.

Falta una última pieza antes de cerrar el módulo. Los `Document`s validados todavía contienen, sin excepción, información sensible: nombres de clientes, correos electrónicos en transcripciones, identificadores personales de interlocutores en las reuniones, condiciones contractuales confidenciales. Si vectorizamos esto tal cual, cualquier consulta semántica sobre el corpus puede recuperar esa información, y un atacante con acceso de usuario al RAG puede extraer un mapa completo de clientes y contratos haciendo preguntas inocentes. El problema no es teórico: es un patrón de filtración documentado en sistemas RAG en producción, y la mitigación tiene que pasar **antes** de la fase de vectorización, no después.