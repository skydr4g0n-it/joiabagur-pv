# Testing y evaluación de sistemas con LLMs

Creada: 17 de mayo de 2026 13:47
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S5. Funcionalidades avanzadas (https://app.notion.com/p/S5-Funcionalidades-avanzadas-363ea9ca03c4809fa6b4c8d2a9413af9?pvs=21)

Cualquier desarrollador con cinco años de experiencia ha interiorizado un instinto operativo: si una pieza de software no tiene tests, no es producción. Tests unitarios, tests de integración, tests end-to-end, cobertura mínima, suite que corre en CI antes de cada merge. Esa disciplina es uno de los rasgos que define a un equipo senior.

Cuando ese desarrollador empieza a trabajar con LLMs, la disciplina choca con una pared. El test unitario clásico es:

```python
def test_estimate_basic_project():
		result = estimator.estimate("Build a simple landing page in HTML and CSS")
		assert result.total_hours == 16
```

Y este test va a fallar el 30% de las veces aunque el sistema esté funcionando perfectamente. La misma transcripción puede producir 14 horas, 16, 18 o un rango "10–22 horas con confianza media". Las tres son respuestas correctas. Ninguna iguala estrictamente a `16`. El test es **inadecuado para el sistema que evalúa**, no porque el sistema esté mal, sino porque los criterios de testing tradicionales no aplican a outputs probabilísticos.

Lo que va a pasar a continuación, si no se gestiona, es predecible. Algunos equipos abandonan la idea de testear el sistema de IA — "es no determinista, no se puede testear" — y la calidad del producto deriva sin que nadie lo note hasta que un usuario se queja. Otros equipos desarrollan paranoia: cada cambio de prompt requiere revisión manual de cien casos antes de salir a producción, lo cual mata la velocidad de iteración. Ninguna de las dos posiciones es sostenible.

Este artículo plantea la base mínima de testing y evaluación que cualquier sistema CAG en producción necesita. No es la versión completa —la disciplina seria de evals con golden datasets curados, monitoring en producción y CI/CD especializado se trata en sesión 15— pero es lo suficiente para dejar de iterar a ciegas y para detectar regresiones antes de que las detecten los usuarios.

## **1. Por qué `assert response == "expected"` no funciona**

El instinto del developer entrenado en testing tradicional es buscar igualdad estricta. Igualdad de strings, igualdad de structs, igualdad de hashes. En sistemas con LLM ese instinto produce dos clases de error que conviene nombrar para reconocerlos cuando aparecen.

**Falsos negativos masivos.** Tu test compara la respuesta del LLM contra una respuesta de referencia y falla porque el modelo dijo "16 horas" cuando esperabas "16h", o "los componentes principales son" cuando esperabas "componentes principales:". El sistema funciona perfectamente y la suite está roja. Después de la quinta vez, alguien añade `if "16" in result` y la suite pasa a "pasa por casualidad". La señal se ha perdido.

**Falsos positivos silenciosos.** Tu test pasa porque comparas que el resultado es un string de longitud > 0. El sistema en producción está devolviendo "Lo siento, no puedo ayudarte con eso" para cualquier transcripción y los tests siguen verdes. La suite no detecta el problema porque no estaba mirando la dimensión correcta.

La conclusión operativa: en sistemas con LLM, **el test no comprueba igualdad sino propiedades**. Una respuesta es válida si cumple un conjunto de propiedades verificables. Identificar y testar esas propiedades es lo que reemplaza al `assert == expected`.

Para el `estimator`, las propiedades naturales son: el output es un JSON válido contra el schema Pydantic, las horas estimadas caen en un rango razonable, la respuesta menciona los componentes técnicos identificados en la transcripción, no contradice los hechos establecidos en `project_metadata`, y mantiene consistencia entre invocaciones repetidas. Cada propiedad se testea de forma distinta. No hay un único "mejor" mecanismo.

## **2. Tres familias de tests**

El catálogo mental que necesitas tiene tres categorías. Cada una usa una técnica distinta y captura un tipo distinto de fallo.

### **Familia 1 — Tests deterministas hard**

Son tests donde la propiedad verificada **no depende del modelo**. La respuesta del LLM se trata como un input opaco y la verificación es una comprobación estructural o numérica que no involucra otra llamada al LLM.

Ejemplos para el `estimator`:

- El output es un JSON válido contra el schema Pydantic correspondiente al tier.
- Todos los campos obligatorios del schema están presentes.
- El rango de horas está dentro de límites razonables (no negativo, no superior a 100.000h, etc.).
- El número de componentes en la respuesta coincide con un mínimo y máximo esperados.
- Los nombres de componentes no están vacíos.

Estos tests son **determinísticos**: el mismo input siempre produce el mismo veredicto. No requieren llamadas extra al LLM. Son baratos, rápidos y siempre deberían formar la primera capa de tu suite.

```python
import pytest
from estimator.client import estimate
from estimator.schemas import DeveloperEstimate

@pytest.mark.asyncio
async def test_estimate_returns_valid_schema():
    transcript = "Build a simple landing page with contact form."
    result = await estimate(tier="developer", transcript=transcript)

    # Schema validation is the most basic hard test
    assert isinstance(result, DeveloperEstimate)

@pytest.mark.asyncio
async def test_estimate_hours_in_reasonable_range():
    transcript = "Build a simple landing page with contact form."
    result = await estimate(tier="developer", transcript=transcript)

    low, high = result.total_hours_range
    assert 0 < low <= high <= 200, (
        f"Unreasonable hours range for a small landing page: {low}-{high}"
    )

@pytest.mark.asyncio
async def test_estimate_components_present():
    transcript = "Build a simple landing page with contact form."
    result = await estimate(tier="developer", transcript=transcript)

    assert len(result.components) >= 1
    assert all(component.name.strip() for component in result.components)
```

Mucho de lo que necesita testarse en un sistema CAG cae aquí. Si el equipo no tiene cobertura mínima en esta familia, no hay nada que añadir; cualquier discusión sobre LLM-as-judge es prematura.

### **Familia 2 — Tests deterministas soft**

Esta familia introduce la idea de **propiedades estadísticas**. El test no verifica una respuesta concreta; ejecuta el sistema N veces sobre el mismo input y verifica que la distribución de respuestas tiene la forma esperada.

El caso paradigmático es la **consistencia**: ¿la misma transcripción produce estimaciones similares en N runs? "Similares" se define operativamente: la varianza del rango de horas estimadas no supera un umbral. Si al estimar diez veces el mismo proyecto el sistema responde "20–30h" siete veces y "60–80h" tres veces, hay un problema de consistencia que merece atención.

```python
import pytest
import statistics

@pytest.mark.asyncio
async def test_estimate_consistency():
    transcript = "Build a simple landing page with contact form."
    n_runs = 5

    results = [
        await estimate(tier="developer", transcript=transcript)
        for _ in range(n_runs)
    ]

    midpoints = [
        (r.total_hours_range[0] + r.total_hours_range[1]) / 2
        for r in results
    ]
    mean = statistics.mean(midpoints)
    coefficient_of_variation = statistics.stdev(midpoints) / mean

    # We accept up to 25% relative variability across runs for the same input
    assert coefficient_of_variation < 0.25, (
        f"Inconsistent estimates across runs: CV={coefficient_of_variation:.2f}, "
        f"midpoints={midpoints}"
    )
```

Estos tests son más caros que los de la familia 1 (cinco llamadas al LLM por test, en este caso) y más lentos. La compensación es que detectan una clase de fallo que ningún test hard puede capturar: que el sistema responda *correctamente* pero con una varianza inaceptable que en producción se traduce en usuarios perdiendo confianza en las cifras.

La regla operativa: corre estos tests con menos frecuencia que los hard. Quizás solo en CI antes de un merge a la rama principal, no en cada commit local.

### **Familia 3 — Tests de calidad subjetiva (LLM-as-judge)**

La tercera familia es donde la propiedad a verificar es genuinamente subjetiva. ¿La justificación de la estimación es coherente con el alcance descrito? ¿La explicación es comprensible para el tier indicado? ¿La respuesta menciona los riesgos relevantes? Ningún test estructural y ninguna métrica estadística captura esto. Solo un juez —humano o LLM— puede valorarlo.

El patrón canónico es **LLM-as-judge**: una segunda llamada al LLM, con un prompt específico de evaluación, que recibe el output del sistema y emite un veredicto. El juez puede operar en dos modos:

- **Pointwise:** asigna una puntuación (0 a 1, o 1 a 5) a la respuesta evaluada según un criterio definido.
- **Pairwise:** compara dos respuestas (la actual contra una referencia) y elige la mejor.

DeepEval encapsula este patrón en su métrica `GEval`, que automatiza el prompt del juez y normaliza el resultado a un score entre 0 y 1:

```python
from deepeval import assert_test
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval

def test_estimate_justification_coherence():
    transcript = "Build a simple landing page with contact form."
    estimate_result = run_estimate_sync(tier="developer", transcript=transcript)

    coherence = GEval(
        name="JustificationCoherence",
        criteria=(
            "Determine whether the technical risks listed in the actual output "
            "are coherent with the project scope described in the input. "
            "A coherent justification mentions risks that are plausible for the "
            "scope and avoids irrelevant risks."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=0.7,
    )

    test_case = LLMTestCase(
        input=transcript,
        actual_output=estimate_result.model_dump_json(),
    )

    assert_test(test_case, [coherence])
```

Tres precauciones operativas con esta familia.

**El juez también es un LLM y también se equivoca.** GEval es una herramienta excelente, pero no infalible. Un juez puede tener sesgos sistemáticos (preferir respuestas largas sobre concisas, o viceversa) que afecten todos los tests de la suite. Calibra el juez con un subconjunto de casos donde tú o un humano hayáis emitido el veredicto, y compara.

**El umbral importa más que la métrica.** Un threshold de 0.7 no es un número universal — depende del juez, del criterio y de tu tolerancia. Empieza con 0.5, mira los resultados sobre un conjunto de casos conocidos, y ajusta hasta que el threshold separe correctamente "respuesta aceptable" de "respuesta defectuosa" en tu dominio.

**No abuses.** Cada test de esta familia es una llamada extra al LLM (a veces dos). Multiplicado por casos de prueba, multiplicado por commits, el coste se acumula rápido. Reserva esta familia para las propiedades que **realmente** no se pueden capturar de otra forma. Si una propiedad puede testarse con un regex, no la testes con un juez.

## **3. El concepto de golden dataset**

Una observación que conviene adelantar: hasta ahora todos los ejemplos de tests usan una única transcripción de prueba. Eso es suficiente para entender la mecánica, pero insuficiente para evaluar un sistema en serio. Una transcripción buena puede esconder dos clases enteras de fallo que solo aparecen con transcripciones de otros tipos.

Aquí entra el concepto de **golden dataset**: un conjunto curado de casos de prueba representativos del dominio del sistema, donde cada caso está anotado con el comportamiento esperado.

Para el `estimator`, un golden dataset razonable contiene cinco a quince transcripciones que cubren el espectro real:

- Un proyecto simple bien acotado (landing page, formulario de contacto).
- Un proyecto medio con múltiples componentes (panel de administración con autenticación y reportes).
- Un proyecto grande con dependencias externas (integración con tres APIs de pago, cola de procesamiento asíncrono).
- Un caso ambiguo donde la transcripción no especifica detalles críticos.
- Un caso límite donde la transcripción contiene contradicciones internas.
- Un caso multilingüe si el sistema lo soporta.

Cada caso lleva metadata: la categoría, las horas que un humano experto estimaría, los riesgos clave que un buen output debería identificar, y los componentes que deberían aparecer. Esa metadata es lo que convierte el dataset en *golden* — no es una lista de inputs, es una lista de inputs **con sus criterios de éxito**.

Un esqueleto de golden dataset en formato consumible por DeepEval:

```python
from deepeval.dataset import EvaluationDataset, Golden

golden_dataset = EvaluationDataset(
    goldens=[
        Golden(
            input="Build a simple landing page with contact form.",
            expected_output=None,  # No exact answer expected
            additional_metadata={
                "category": "small_project",
                "expected_hours_range": (16, 40),
                "expected_components": ["frontend", "form_handling"],
            },
        ),
        Golden(
            input=(
                "We need an internal admin dashboard with user management, "
                "role-based permissions, audit log, and weekly email reports."
            ),
            additional_metadata={
                "category": "medium_project",
                "expected_hours_range": (200, 400),
                "expected_components": ["backend", "frontend", "auth", "email_jobs"],
            },
        ),
        # ... more goldens
    ]
)
```

Construir un golden dataset es trabajo. Un caso bien anotado puede costar una hora a un experto del dominio. Para un dataset de diez casos, son diez horas. **Es una inversión, no un coste**. Esa inversión se amortiza en la primera regresión que se evita: detectar antes de salir a producción que un cambio de prompt rompe los casos medios paga el dataset varias veces.

La construcción de golden datasets para un dominio concreto es un arte que se aprende construyendo. Las heurísticas básicas: representa la distribución real de inputs (no inventes casos exóticos que nadie envía), incluye al menos un caso límite por categoría, y revisa el dataset cada tres meses para corregir sesgos que aparecen con el uso.

## **4. Anatomía de una suite de evals con DeepEval y pytest**

DeepEval es la herramienta que vamos a usar para encadenar las tres familias de tests sobre un golden dataset. La elección no es casual: es nativa pytest, no requiere infraestructura externa para ejecutar localmente, y ofrece métricas listas para usar (`AnswerRelevancyMetric`, `FaithfulnessMetric`, `GEval`) que cubren los casos comunes sin escribir prompts de juez desde cero.

La estructura básica de un archivo de tests con DeepEval combina los tres niveles:

```python
import pytest
import statistics

from deepeval import assert_test
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import GEval

from estimator.client import estimate_sync
from estimator.schemas import DeveloperEstimate
from tests.fixtures import golden_dataset

# Family 1 — Hard determinism
@pytest.mark.parametrize("golden", golden_dataset.goldens)
def test_schema_validity(golden):
    result = estimate_sync(tier="developer", transcript=golden.input)
    assert isinstance(result, DeveloperEstimate)

@pytest.mark.parametrize("golden", golden_dataset.goldens)
def test_hours_within_expected_range(golden):
    result = estimate_sync(tier="developer", transcript=golden.input)
    low, high = result.total_hours_range
    expected_low, expected_high = golden.additional_metadata["expected_hours_range"]
    # Allow 50% overshoot in either direction — generous on a first pass
    assert low >= expected_low * 0.5
    assert high <= expected_high * 1.5

# Family 2 — Soft determinism
@pytest.mark.slow
@pytest.mark.parametrize("golden", golden_dataset.goldens[:3])  # only first 3 for cost
def test_consistency_across_runs(golden):
    n_runs = 3
    results = [
        estimate_sync(tier="developer", transcript=golden.input)
        for _ in range(n_runs)
    ]
    midpoints = [
        (r.total_hours_range[0] + r.total_hours_range[1]) / 2
        for r in results
    ]
    cv = statistics.stdev(midpoints) / statistics.mean(midpoints)
    assert cv < 0.25

# Family 3 — Subjective quality (LLM-as-judge)
coherence_metric = GEval(
    name="ScopeCoherence",
    criteria=(
        "Evaluate whether the components and risks in the actual output match "
        "the scope of the project described in the input. "
        "Penalize outputs that mention components or risks not implied by the input."
    ),
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
    threshold=0.7,
)

@pytest.mark.slow
@pytest.mark.parametrize("golden", golden_dataset.goldens)
def test_scope_coherence(golden):
    result = estimate_sync(tier="developer", transcript=golden.input)
    test_case = LLMTestCase(
        input=golden.input,
        actual_output=result.model_dump_json(),
    )
    assert_test(test_case, [coherence_metric])
```

Tres detalles operativos a notar.

**Marcado con** `@pytest.mark.slow`**.** Las familias 2 y 3 son significativamente más caras que la 1. Marcarlas explícitamente permite a los desarrolladores correr solo la suite rápida durante el desarrollo (`pytest -m "not slow"`) y reservar la suite completa para CI. Sin esta separación, el equipo deja de correr la suite en local y los problemas se acumulan.

**Parametrización con el golden dataset.** Cada test se ejecuta una vez por cada golden. Esto es lo que convierte tres tests en treinta o cuarenta casos efectivos sin duplicar código. Pytest reporta cada combinación por separado, así que cuando algo falla sabes exactamente qué caso del golden está roto.

**Tolerancias generosas en la primera pasada.** El test `test_hours_within_expected_range` acepta hasta un 50% de desviación en cada extremo del rango. Esto es deliberado: en una primera pasada quieres detectar fallos catastróficos (el sistema estima una landing page en 800 horas), no microajustes. Cuando el sistema esté maduro, ajustarás las tolerancias hacia abajo.

## **5. Anti-patrones frecuentes**

Tres errores que se ven en suites de evals reales y que conviene reconocer pronto.

![005-piramide-tests.jpg](https://media1-production-mightynetworks.imgix.net/asset/ae75ca6a-e2aa-4885-a0ce-98362b66b11f/005-piramide-tests.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Anti-patrón 1 — Testar la respuesta del modelo en lugar de las propiedades de tu sistema.** "El modelo respondió 16 horas en lugar de 18, ajusto el test". El test deja de medir si el sistema funciona correctamente y pasa a memorizar las salidas concretas del modelo en un momento dado. Cuando OpenAI actualiza el modelo (cosa que pasa sin avisar), todos los tests rompen y el equipo cree que ha aparecido un bug que en realidad no existe. La regla: testa propiedades del sistema (el rango de horas es plausible, el schema es válido, los componentes son coherentes), no salidas específicas del modelo.

**Anti-patrón 2 — Suite de evals que es solo familia 3.** "Todos nuestros tests son LLM-as-judge porque es lo que mejor captura calidad". El problema es doble: la suite es lentísima y carísima de correr, y todos los tests dependen del mismo punto de fallo (el LLM juez). Una suite sana es **piramidal**: muchos tests hard rápidos en la base, algunos tests soft en el medio, pocos tests subjetivos en la cima. Si el cuerpo de la suite está en la cima, algo está mal.

**Anti-patrón 3 — Construir el golden dataset una vez y olvidarlo.** El golden dataset que parecía representativo en febrero deja de serlo en agosto cuando los usuarios reales han empezado a enviar transcripciones de un tipo nuevo que el dataset no contempla. La consecuencia: tests verdes y producción fallando. Reservar tiempo para revisar y ampliar el dataset cada trimestre es disciplina estándar — la misma que se aplica a documentación o a CI/CD, solo que aplicada a evals.

## **6. Lo que esta primera exposición no cubre**

Una nota de honestidad sobre el alcance. Lo que has visto aquí es la base mínima viable para un sistema CAG: tres familias de tests, golden dataset pequeño, integración con pytest y DeepEval. Es lo suficiente para dejar de iterar a ciegas y para detectar regresiones gruesas antes de producción.

Lo que falta —y que se trata en sesión 15 cuando entremos en LLMOps y producción— incluye:

- **Métricas especializadas para RAG.** Faithfulness, contextual precision, answer relevancy con criterios específicos para sistemas que hacen retrieval. Frameworks como RAGAS están diseñados para esto.
- **Tests de regresión continuos en CI/CD.** Bloquear merges cuando el score de calidad cae por debajo de un umbral, comparar runs lado a lado, mantener historial de calidad en el tiempo.
- **Monitoring en producción.** Online evals que corren sobre un sample de tráfico real y alertan cuando aparecen fallos sistemáticos. Plataformas como Langfuse, Confident AI o Logfire llenan este espacio.
- **Red teaming automatizado.** Suites que generan inputs adversariales para descubrir fallos que ningún golden dataset humano va a anticipar. Promptfoo es la herramienta de referencia aquí.
- **Datasets sintéticos.** Generar casos de prueba con LLM a partir de un seed pequeño, multiplicando la cobertura sin el coste de anotación humana.

Llegar a esa madurez requiere infraestructura, disciplina de equipo y, normalmente, una persona dedicada al rol de evaluation engineer. Lo importante es entender que esa madurez se construye progresivamente desde la base que cubrimos aquí, no en sustitución de ella.

## **7. Resumen**

Cuatro afirmaciones operativas para llevarte:

1. **El test unitario clásico no aplica a outputs de LLM.** En su lugar, los tests verifican propiedades. Identificar las propiedades correctas para tu sistema es la primera disciplina del testing en sistemas CAG.
2. **Hay tres familias de tests con costes y propósitos distintos.** Hard (estructural, barato, rápido), soft (estadístico, medio), subjective (LLM-as-judge, caro). Una suite sana usa las tres en proporción piramidal.
3. **El golden dataset es la base de todo lo demás.** Un dataset pequeño pero curado y anotado vale más que cien casos generados al azar. Construirlo es inversión, no coste, y necesita revisión periódica.
4. **DeepEval con pytest cubre la base mínima sin infraestructura externa.** Es el punto de entrada razonable a la disciplina de evals para un equipo que arranca. Lo que viene después —monitoring, regression testing en CI, red teaming— se construye encima, no en lugar de.

La diferencia entre un sistema CAG que evoluciona con confianza y uno que da miedo tocar está en haber dado este primer paso. Sistemas sin evals derivan; sistemas con evals progresan. Es la única forma sostenible de iterar sobre prompts, modelos y arquitecturas sin temer romper algo que funcionaba sin que nadie lo note.