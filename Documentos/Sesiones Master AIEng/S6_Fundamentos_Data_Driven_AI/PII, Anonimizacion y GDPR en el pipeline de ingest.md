# PII, anonimización y GDPR en el pipeline de ingest

Creada: 26 de mayo de 2026 8:40
Módulo: M3. Data Driven AI (https://app.notion.com/p/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S6. Fundamentos de data driven AI - Análisis, formateo y normalización de datos existentes (https://app.notion.com/p/S6-Fundamentos-de-data-driven-AI-An-lisis-formateo-y-normalizaci-n-de-datos-existentes-36aea9ca03c480e2b5addae1d84e60ac?pvs=21)

El corpus que tenemos ahora ya pasó por inventario, extracción y validación. Los registros son consistentes, están limpios y respetan los invariantes de negocio. Pero contienen, sin excepción, información personal y comercial sensible. Nombres de clientes en las transcripciones, correos electrónicos en presupuestos, números de teléfono de interlocutores en propuestas, identificadores internos de proyecto que revelan estructura organizativa, condiciones contractuales que el departamento legal pidió no compartir.

Hay una intuición común que conviene desmontar de entrada: muchos equipos asumen que el control de acceso al sistema (autenticación, autorización, ACLs en la aplicación) es suficiente para proteger esos datos. La intuición funciona en bases de datos tradicionales. **No funciona en RAG**, y el motivo es estructural, no de implementación. Una vez que un dato sensible está en el espacio vectorial, está disponible para cualquier consulta semántica que se acerque a él, sin importar cómo se haya formulado la pregunta original. La protección tiene que ocurrir **antes** del embedding, y este artículo construye esa capa.

## **El problema real: filtración semántica vía RAG**

La diferencia entre una filtración de PII en una base de datos relacional y una filtración en un sistema RAG es la siguiente. En la base relacional, el atacante necesita formular una query específica que apunte a la tabla o columna sensible. Si la columna `email` de la tabla `clients` está protegida por permisos, no hay query SQL que la devuelva, sin importar cuán hábil sea el atacante.

En RAG el ataque es **indirecto**. El usuario no consulta tablas; hace preguntas en lenguaje natural. El sistema busca semánticamente, recupera los chunks más relevantes, y los presenta al modelo generativo como contexto. Si los chunks contienen el dato sensible (literalmente, en el texto), el modelo lo va a usar en su respuesta. No hay un nivel de permisos en el vector que pueda ocultarlo, porque el vector no sabe qué es sensible.

Conviene distinguir tres modos de filtración para diseñar las defensas correctas.

![sesion_06_article_5_visual_1_pii_leakage_modes.jpg](https://media1-production-mightynetworks.imgix.net/asset/c9f950fd-9473-4ecd-96f0-035ec4473064/sesion_06_article_5_visual_1_pii_leakage_modes.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Filtración directa** es la más obvia. Un usuario pregunta *"¿qué clientes nos han contratado proyectos de migración a cloud?"* y el RAG devuelve una respuesta que enumera "Banco Sabadell, Inditex y Repsol" porque esos nombres están literalmente en los chunks recuperados. Es trivial de explotar y trivial de prevenir si la anonimización está en su sitio.

**Filtración por agregación** es más sutil. Cada query individual parece inocua, pero el atacante combina varias consultas para reconstruir información sensible. *"¿Qué proyectos completamos en 2024?"*, *"¿Cuál fue el más caro?"*, *"¿En qué sector?"*, *"¿Qué tecnologías usamos?"*. Cada pregunta devuelve datos parciales; el atacante los une en una imagen completa. Defenderse requiere pensar en términos de **superficie de información agregada**, no de chunks individuales.

**Filtración por inferencia** es la más peligrosa porque ocurre incluso después de la anonimización ingenua. Si reemplazas el nombre "Juan García, CEO de Acme Corp" por "[PERSON], CEO de [ORG]", parece que la información se ha protegido. Pero el contexto que rodea al token sigue ahí: el sector, las fechas, los importes, la geografía. Combinado con metadatos del catálogo y del parser, eso puede ser suficiente para que un atacante con conocimiento del dominio identifique al individuo. La defensa contra este modo no es solo anonimizar, sino **reducir la combinatoria de pistas que rodean al individuo**.

Las tres familias de ataque comparten una característica: ninguna requiere acceso administrativo al sistema. Bastan credenciales legítimas de usuario y preguntas en lenguaje natural. Por eso la anonimización tiene que ocurrir antes del embedding, no como filtro en la respuesta.

## **El marco GDPR mínimo aplicado al pipeline**

GDPR es la regulación europea que gobierna el tratamiento de datos personales. Su texto completo da para mucho, pero hay cuatro conceptos que cualquier AI Engineer trabajando con datos empresariales en la UE necesita tener interiorizados, porque condicionan decisiones técnicas concretas del pipeline.

**Datos personales.** La definición de GDPR es deliberadamente amplia: cualquier información que pueda identificar, directa o indirectamente, a una persona física. Nombres, emails y teléfonos son obvios. Menos obvios son los identificadores indirectos: una dirección IP, una cookie, un número de empleado, e incluso combinaciones de datos que individualmente no identifican pero juntos sí. Para el Proyecto, eso significa que las transcripciones de reuniones (con nombres de interlocutores) son trivialmente datos personales, pero también lo pueden ser presupuestos que combinan sector, importe, fecha y geografía si el conjunto reduce la población candidata a un único cliente identificable.

**Anonimización vs pseudonimización.** La distinción es técnica y legal a la vez. **Anonimización irreversible** significa que ni siquiera el operador del sistema puede recuperar el dato original; el dato anonimizado deja de ser "dato personal" en el sentido de GDPR, y la regulación deja de aplicar sobre él (con condiciones). **Pseudonimización** significa que el dato real se sustituye por uno ficticio mediante un mapping reversible que se conserva por separado; sigue siendo dato personal a efectos de GDPR (la mapping table es información personal), pero su gestión es más sencilla operativamente. Para RAG, la pseudonimización suele ganar porque preserva la coherencia semántica del corpus: "Juan García" no se reemplaza por `<PERSON>` (que destruye estructura), sino por "Carlos Martínez" siempre, en todo el corpus.

**Derecho al olvido.** El artículo 17 de GDPR da a cualquier persona el derecho a pedir que sus datos personales sean eliminados de un sistema. Para una base de datos tradicional esto es un `DELETE`. Para RAG, **es un problema arquitectónico**: los chunks que mencionan al individuo están vectorizados y dispersos en el índice. Sin un mapeo explícito que diga "estos chunks contienen información sobre Juan García", la eliminación es imposible. Esta es una de las razones (no la única) por las que la mapping table de pseudonimización es una pieza arquitectónica, no un detalle de implementación.

**Minimización.** El principio dice que solo se deben procesar los datos estrictamente necesarios para el propósito declarado. Para el Proyecto, esto se traduce en una pregunta operativa: ¿necesita el sistema de estimación los nombres reales de los clientes para hacer su trabajo? La respuesta razonable es no: el sistema necesita los **patrones** de proyectos pasados (sector, alcance, tecnologías, complejidad), no la identidad concreta del cliente. Esa observación es la que justifica la pseudonimización agresiva desde el principio: no estamos perdiendo nada útil, estamos eliminando un riesgo.

## **Microsoft Presidio: detección y anonimización en pipeline**

Presidio es la librería de Microsoft para detección y anonimización de PII. Existen alternativas (`spaCy` puro, `nltk`, soluciones comerciales como AWS Comprehend), pero Presidio tiene tres características que la hacen la elección práctica para un pipeline como el del Proyecto: arquitectura modular (analyzer + anonymizer son intercambiables), recognizers preconstruidos para PII común (email, teléfono, IBAN, IPs, números de tarjeta, fechas, ubicaciones, personas, organizaciones), y soporte explícito para custom recognizers que extienden el catálogo de entidades detectables.

El uso básico tiene dos pasos. El **analyzer** detecta entidades PII en un texto y devuelve sus posiciones; el **anonymizer** aplica una operación de transformación sobre esas posiciones.

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_analyzer.nlp_engine import NlpEngineProvider

# Spanish-aware NLP engine (default ships with English only)
nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "es", "model_name": "es_core_news_md"}],
}
nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()

analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["es"])
anonymizer = AnonymizerEngine()

text = (
    "El cliente Juan García (CEO de Acme Corp) confirmó el presupuesto "
    "BUDGET-2024-0315 por correo a contacto@acme.com el 12 de marzo."
)

results = analyzer.analyze(text=text, language="es")
# results contiene una lista de RecognizerResult con start, end, entity_type, score

anonymized = anonymizer.anonymize(
    text=text,
    analyzer_results=results,
    operators={"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]")}},
)
print(anonymized.text)
# "El cliente [REDACTED] (CEO de [REDACTED]) confirmó el presupuesto
#  [REDACTED] por correo a [REDACTED] el [REDACTED]."
```

Dos detalles del setup merecen atención. Primero, **la configuración explícita del modelo spaCy en español**. Por defecto, Presidio carga `en_core_web_lg` (inglés) y los recognizers están afinados para ese idioma. Sin esta configuración, sobre texto en español la tasa de falsos negativos en entidades `PERSON` y `LOCATION` se dispara: el sistema no detecta nombres que para un hispanohablante son obvios. Segundo, `supported_languages=["es"]` es necesario para que el analyzer no intente cargar el modelo inglés como fallback.

La operación `replace` con `[REDACTED]` es la más simple y la peor para RAG, por las razones que ya hemos discutido. La usamos aquí solo para demostrar el flujo. La estrategia que aplicamos al Proyecto es distinta y aparece más adelante.

## **Recognizers custom para el dominio del Proyecto**

Los recognizers default cubren bien las categorías universales: emails, teléfonos, IBANs, nombres genéricos. No conocen los identificadores específicos del dominio del proyecto. Para el Proyecto hay al menos dos categorías de identificadores propios que conviene detectar y tratar:

- **Budget IDs**: el patrón `BUDGET-YYYY-NNNN` que ya quedó documentado como invariante en el schema Pandera del Article 4. Estos identificadores no son PII en sentido estricto, pero revelan información comercial sensible (volumen de proyectos cerrados, estructura de numeración interna).
- **Códigos de cliente internos**: identificadores como `CLI-1042` o `CLT-INT-A047` que aparecen en transcripciones y presupuestos, y que mapean uno-a-uno a clientes reales.

Presidio permite añadir estos recognizers con `PatternRecognizer`, que envuelve una o varias expresiones regulares:

```python
from presidio_analyzer import PatternRecognizer, Pattern

budget_id_pattern = Pattern(
    name="budget_id_canonical",
    regex=r"\\bBUDGET-\\d{4}-\\d{4}\\b",
    score=0.95,
)
budget_id_recognizer = PatternRecognizer(
    supported_entity="BUDGET_ID",
    name="budget_id_recognizer",
    patterns=[budget_id_pattern],
    supported_language="es",
)

client_code_pattern = Pattern(
    name="client_code_internal",
    regex=r"\\b(?:CLI|CLT-INT)-[A-Z0-9]{3,8}\\b",
    score=0.9,
)
client_code_recognizer = PatternRecognizer(
    supported_entity="CLIENT_CODE",
    name="client_code_recognizer",
    patterns=[client_code_pattern],
    supported_language="es",
)

analyzer.registry.add_recognizer(budget_id_recognizer)
analyzer.registry.add_recognizer(client_code_recognizer)
```

Dos cosas a notar. Primero, `score` **es un parámetro decisivo**: indica la confianza con la que el recognizer afirma haber detectado la entidad. Cuando hay varios recognizers que se solapan (por ejemplo, un patrón genérico de "código alfanumérico" y nuestro patrón específico de `BUDGET-`), Presidio se queda con el de mayor score. Empezar con scores altos (0.9-0.95) en patrones muy específicos y bajos (0.4-0.6) en patrones genéricos es buena higiene operativa. Segundo, **el** `supported_entity` **que declaras (**`BUDGET_ID`**,** `CLIENT_CODE`**) es la etiqueta semántica que vas a usar después en la fase de pseudonimización** para aplicar la transformación correcta. Un budget ID se reemplaza con otro budget ID falso pero coherente; un email con otro email; un nombre con otro nombre. La etiqueta es la que decide qué generador usar.

Para nombres específicos de clientes que no siguen patrón regular (como "Banco Sabadell" o "Inditex"), hay una segunda herramienta complementaria: `RecognizerResult` cargados desde un diccionario explícito. Mantener ese diccionario como parte del proyecto (en el catálogo, en una tabla referenciada) es operativamente trivial y atrapa los casos que ni la NLP ni los regex detectan.

## **Pseudonimización reversible con Faker y una mapping table**

Aquí entra la pieza arquitectónica clave. En lugar de reemplazar las entidades detectadas con tokens genéricos (`[PERSON]`, `[EMAIL]`), las reemplazamos con **valores ficticios consistentes** generados por Faker, manteniendo en paralelo una **mapping table** que registra cada sustitución para poder revertirla cuando sea necesario.

![sesion_06_article_5_visual_2_pseudonymization_flow.jpg](https://media1-production-mightynetworks.imgix.net/asset/6d8d518b-4c6e-4024-8979-462659b2fea2/sesion_06_article_5_visual_2_pseudonymization_flow.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

```python
from dataclasses import dataclass
from typing import Optional
from faker import Faker
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

@dataclass
class PseudonymMapping:
    """Single mapping entry to be persisted to a secure store."""
    original_value: str
    pseudonym: str
    entity_type: str
    first_seen_at: str  # ISO timestamp
    source_name: str    # catalog source where it appeared first

class ConsistentPseudonymizer:
    """Replaces detected entities with stable fake values.

    The same input value always maps to the same fake output across
    the entire corpus, so semantic relations are preserved. The mapping
    is persisted to allow reverse lookup and right-to-be-forgotten.
    """

    def __init__(self, mapping_store, locale: str = "es_ES"):
        self.faker = Faker(locale)
        self.store = mapping_store  # backed by an encrypted store
        self.generators = {
            "PERSON": self.faker.name,
            "EMAIL_ADDRESS": self.faker.email,
            "PHONE_NUMBER": self.faker.phone_number,
            "LOCATION": self.faker.city,
            "ORGANIZATION": self.faker.company,
            "BUDGET_ID": lambda: f"BUDGET-{self.faker.year()}-{self.faker.random_number(digits=4, fix_len=True)}",
            "CLIENT_CODE": lambda: f"CLI-{self.faker.random_number(digits=4, fix_len=True)}",
        }

    def get_or_create_pseudonym(
        self, original: str, entity_type: str, source_name: str
    ) -> str:
        existing = self.store.lookup(original, entity_type)
        if existing:
            return existing.pseudonym

        generator = self.generators.get(entity_type, self.faker.word)
        pseudonym = generator()
        self.store.save(PseudonymMapping(
            original_value=original,
            pseudonym=pseudonym,
            entity_type=entity_type,
            first_seen_at=self._now_iso(),
            source_name=source_name,
        ))
        return pseudonym
```

Cuatro elementos del diseño merecen comentario. Primero, **la consistencia es por valor original, no por chunk**. La misma cadena `"Juan García"` siempre se pseudonimiza al mismo `"Carlos Martínez"` aunque aparezca en cientos de chunks distintos. Sin esto, dos chunks sobre el mismo cliente acabarían en regiones distantes del espacio vectorial y el retrieval volvería a romperse por la misma razón que rompió la "heterogeneidad de formato" del Article 4. Segundo, **los generadores son específicos por tipo de entidad**: un nombre se reemplaza por otro nombre, no por un email o por una fecha. La señal semántica del tipo de campo se preserva. Tercero, **la mapping store es un componente separado del pipeline**, encriptado, con su propio control de acceso. Si tienes que demostrar a un auditor GDPR que sabes qué datos de qué persona viven en tu sistema, la consulta es contra esa store, no contra el corpus vectorial. Cuarto, **el** `source_name` **se persiste con el mapping**, lo que permite responder a la pregunta "qué fuentes del catálogo mencionan a esta persona" sin tener que recorrer el índice vectorial.

La integración con el pipeline de ingest se hace al final, después de la validación del Article 4 y antes del chunking de la Sesión 07. El orquestador toma cada `Document` validado, mira `metadata.contains_pii` (propagado desde el catálogo en el Article 3), y si es `True` aplica la pseudonimización antes de devolverlo a la siguiente etapa. El `Document` que sale tiene el mismo `content` que el de entrada salvo por los tokens reemplazados, y el resto del pipeline downstream no necesita saber nada de Presidio o Faker; consume `Document`s con `content` ya seguro.

## **El derecho al olvido en RAG: un caso práctico**

El alumno que llegue a producción con este sistema va a recibir antes o después una petición de derecho al olvido. Un cliente o un empleado dice "quiero que mis datos no estén más en vuestro sistema de IA". La pregunta operativa es: ¿qué pasos ejecuta el equipo?

Con la arquitectura que hemos descrito, los pasos son cinco. Primero, **consultar la mapping store** con el nombre del solicitante para identificar todos los pseudónimos asociados. Pueden ser varios si la persona aparece con variantes (nombre completo, nombre y apellido, alias). Segundo, **buscar en el índice vectorial los chunks que contienen esos pseudónimos** o que están asociados a documentos con esos pseudónimos en metadatos. Tercero, **eliminar esos chunks del índice vectorial**. Cuarto, **eliminar las entradas correspondientes de la mapping store**: el mapping deja de existir, y si la persona vuelve a aparecer en un nuevo documento recibirá un nuevo pseudónimo sin relación con el anterior. Quinto, **registrar la operación en un audit log** que demuestre que la petición se atendió en plazo y forma.

Cada uno de estos pasos es operativamente trivial **gracias a la mapping table**. Sin ella, los pasos primero, segundo y cuarto son imposibles, y el sistema queda en incumplimiento permanente del artículo 17 de GDPR. Por eso la mapping table no es un detalle; es la pieza que sostiene el cumplimiento.

## **Trade-offs honestos**

**Anonimización irreversible vs pseudonimización reversible.** Hay equipos que defienden la anonimización irreversible por simplicidad: sustituyes con `<PERSON>`, no hay mapping store, no hay riesgo de filtración del mapping, ya no es "dato personal" según GDPR. El problema es que los embeddings de un corpus con `<PERSON>` se degradan significativamente respecto a un corpus con pseudónimos consistentes. Pruebas internas (no publicables, pero replicables) muestran caídas del 15-25% en métricas de retrieval cuando se usa la sustitución genérica. Para sistemas en producción con compromiso de calidad, la pseudonimización reversible es casi siempre la respuesta correcta. La anonimización irreversible queda reservada para corpus que el equipo entiende como "públicos por defecto" (publicaciones internas anonimizadas para difusión externa, por ejemplo) o para casos donde el contrato legal con un proveedor lo exige explícitamente.

**Falsos positivos de Presidio en español.** Presidio funciona considerablemente peor en español que en inglés. El modelo NLP base (`es_core_news_md`) etiqueta nombres comunes como entidades PERSON con frecuencia molesta: palabras como "Mar", "Sol", "Cruz", "Alba" se detectan como nombres propios incluso cuando aparecen como sustantivos comunes. Los datasets de entrenamiento de spaCy en español tienen menos volumen y menos diversidad que los de inglés, y eso se nota. Tres estrategias mitigan el problema: aumentar el umbral de score para confirmar entidades (subir de 0.5 a 0.7 reduce falsos positivos a costa de algunos falsos negativos), añadir una blacklist de palabras conocidas que no deben tratarse como PII aunque el modelo las detecte, y entrenar un modelo NER ligeramente customizado con datos del propio dominio si el volumen del corpus lo justifica. La elección depende del coste-beneficio del proyecto; para el Proyecto, las dos primeras estrategias son suficientes.

**Impacto en la calidad de los embeddings.** Aunque la pseudonimización consistente preserva la mayor parte de la señal semántica, introduce algo de ruido inevitablemente. Un nombre real lleva micro-información que un nombre falso no replica (origen geográfico, género percibido, frecuencia en el corpus). Para un sistema RAG de estimación de proyectos como el del Proyecto, ese ruido es despreciable: el retrieval funciona en términos de patrones de proyecto, no de identidad nominal. Para sistemas donde la identidad sí importa (asistentes personales, sistemas de relación con cliente individualizada), el coste de la pseudonimización es mayor y conviene cuantificarlo con benchmarks específicos antes de adoptarla. La regla práctica para el Proyecto: pseudonimizar primero, medir después con un set de queries representativas, decidir caso por caso si algún tipo de entidad (rara vez) merece dejarse sin tratar.

## **Cierre del Módulo 3**

Llegados al final del módulo, el corpus del Proyecto está en un estado que sostendría una auditoría seria. Hemos pasado por seis decisiones acumulativas: justificamos arquitectónicamente la transición de CAG a RAG (Article 1), construimos el catálogo versionado de fuentes con políticas explícitas de inclusión (Article 2), montamos el subsistema `ingest/` con el `Document` canónico como contrato compartido (Article 3), implementamos la capa de limpieza y validación con Pandera como guardián de los invariantes (Article 4), y cerramos con la anonimización mediante Presidio y la mapping table que sostiene el cumplimiento GDPR (Article 5).

Lo que tenemos al final del módulo no es código brillante; es **un corpus que un equipo de producción podría defender ante cualquier interlocutor**: legal, comercial, técnico, regulatorio. Cada decisión está versionada, cada exclusión tiene motivo registrado, cada dato sensible tiene mapping reversible, cada invariante de negocio tiene un schema que lo hace cumplir. Ese es el estado mínimo desde el que tiene sentido convertir el corpus en vectores. Antes de eso, vectorizar es construir sobre arena.

En el siguiente módulo, a partir de la Sesión 07, atacamos la vectorización propiamente dicha: embeddings, chunking, modelos, espacio vectorial. Y luego, en el Módulo 4, las bases de datos vectoriales y las arquitecturas RAG completas que cierran el sistema. El trabajo del Módulo 3 va a seguir siendo el cimiento sobre el que se monta todo lo que viene, y la calidad de ese cimiento es la que va a determinar cuánto vale el sistema final en producción.