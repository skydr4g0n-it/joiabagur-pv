# Cómo saber si el reranking compensa: medición artesanal de relevancia

Creada: 20 de junio de 2026 9:32
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S10. Técnicas de recuperación (https://app.notion.com/p/S10-T-cnicas-de-recuperaci-n-385ea9ca03c4806b8530fd77248bbb31?pvs=21)

## **"Parece que va mejor" no es un argumento**

Imagina la situación. Has añadido una etapa de reranking al pipeline de recuperación del sistema de estimación: ahora un segundo modelo reordena los presupuestos candidatos antes de pasárselos al LLM. Lanzas tres consultas de prueba, miras los resultados y, efectivamente, los presupuestos que aparecen arriba tienen mejor pinta. La tentación es cerrar el ticket y seguir.

Ahora imagina la conversación dos semanas después. Alguien de tu equipo pregunta por qué cada estimación tarda medio segundo más que antes. Tu respuesta es que la recuperación mejoró. La siguiente pregunta es inevitable: ¿cuánto? Y "parece que va mejor" no sobrevive a esa pregunta. Tampoco sobrevive a una code review seria, ni a un comité de arquitectura, ni al cliente que paga la factura de infraestructura.

Este artículo trata de cómo convertir "parece que va mejor" en "la precisión de recuperación subió de 0,48 a 0,80 a cambio de 250 milisegundos por consulta". La buena noticia: no hace falta un framework de evaluación, ni un equipo de datos, ni semanas de trabajo. Hace falta una tarde, criterio de dominio y una hoja de cálculo. A esa práctica la llamaremos **medición artesanal**: deliberadamente pequeña, deliberadamente manual, y suficiente para tomar la decisión que tienes delante.

## **Por qué la intuición engaña midiendo relevancia**

Antes de construir la solución conviene entender por qué el ojímetro falla precisamente aquí, porque no falla por descuido: falla por diseño de cómo funciona nuestra atención.

**Probamos con las consultas equivocadas.** Cuando evaluamos a mano, elegimos consultas que se nos ocurren en el momento — y se nos ocurren las fáciles, las que nosotros mismos formularíamos bien. Los usuarios reales escriben consultas vagas, mezclan temas, usan terminología de su sector y no del nuestro. Un sistema puede brillar con nuestras tres consultas de prueba y tropezar con la mitad de las reales.

**Recordamos lo memorable, no lo representativo.** Si el reranking rescata espectacularmente un presupuesto que antes quedaba enterrado, esa anécdota domina nuestra percepción aunque en el resto de consultas no haya cambiado nada. La memoria humana pondera por impacto emocional; una métrica pondera por frecuencia. Para decidir sobre un sistema, lo segundo es lo que cuenta.

**Comparamos contra una referencia que se mueve.** Evaluar "a ojo" la configuración nueva el martes y la antigua el jueves introduce todo tipo de ruido: distinto estado de ánimo, distinto recuerdo de qué era "aceptable". Sin una referencia fija, cada comparación es contra una vara de medir distinta.

La solución a los tres problemas es la misma: fijar de antemano un conjunto de consultas representativas con sus respuestas correctas conocidas, y medir todas las configuraciones contra ese mismo conjunto. Ese conjunto tiene nombre.

## **El golden set: tu verdad de referencia en miniatura**

Un **golden set** es una colección pequeña de consultas reales del dominio, cada una anotada a mano con los documentos que de verdad son relevantes para ella. Es la verdad de referencia contra la que se mide cualquier configuración de recuperación: si el sistema devuelve los documentos anotados, acierta; si devuelve otros, falla. Sin ambigüedad y sin depender de la memoria de nadie.

Para el sistema de estimación, una entrada del golden set tiene esta forma: la consulta es la descripción de un proyecto a estimar ("plataforma de e-commerce con catálogo, carrito y panel de administración") y la anotación es la lista de presupuestos históricos que un estimador experimentado consideraría útiles como referencia para ese proyecto. Ni los semánticamente parecidos, ni los de la misma tecnología: los que usarías de verdad para estimar.

Tres decisiones definen la calidad de un golden set, y ninguna es técnica:

**Qué consultas entran.** La selección debe cubrir el uso real, no el uso cómodo. Una mezcla sana para empezar: dos o tres consultas frecuentes y directas (el caso típico que el sistema verá a diario), un par de consultas difíciles conocidas (esas en las que ya has visto al sistema confundirse — por ejemplo, dominios colindantes como e-commerce y pagos), y al menos una consulta con términos exactos que deban respetarse (nombres de tecnologías, siglas, productos concretos). Si el sistema procesa transcripciones de reuniones, alguna consulta debe ser larga y desordenada como lo son las transcripciones, no una frase de laboratorio.

**Cuántas consultas.** Menos de las que crees. Entre cinco y veinte consultas bien elegidas bastan para decidir si una técnica compensa; el error que de verdad invalida la medición no es el tamaño de la muestra, sino que la muestra no se parezca al uso real. Un golden set de cinco consultas representativas informa más que uno de cincuenta consultas inventadas en diez minutos. Empieza pequeño: ampliar un golden set vivo es trivial; tirar a la basura uno grande y mal construido, doloroso.

**Quién anota y con qué criterio.** La anotación es un juicio de dominio: decidir qué presupuestos son relevantes para una consulta exige saber estimar proyectos, no saber Python. Debe hacerla quien usaría el resultado — el estimador, el responsable técnico — y antes de anotar conviene escribir el criterio en una frase ("es relevante si serviría como referencia directa de esfuerzo para este proyecto"). El criterio escrito evita el desplazamiento silencioso: que la tercera consulta se anote con una vara distinta a la primera. La relevancia se anota en binario — relevante o no — resistiendo la tentación de escalas de matices: el binario es menos expresivo, pero es consistente entre anotaciones y suficiente para la decisión que perseguimos.

## **Precisión sobre los k primeros: la métrica que cabe en una servilleta**

Con el golden set fijado, la métrica casi se define sola. Lo que le importa al pipeline es la calidad de los documentos que finalmente llegan al LLM — los k primeros del ranking, donde k es el tamaño del contexto que pasamos (cinco presupuestos, por ejemplo). La métrica natural es la **precisión en los k primeros** (precision@k): de los k documentos devueltos, qué fracción es relevante según el golden set.

El cálculo, con un ejemplo. Para la consulta del e-commerce, el golden set marca cuatro presupuestos como relevantes. El sistema devuelve su top-5; comprobamos cada posición contra la anotación:

![image.png](https://media1-production-mightynetworks.imgix.net/asset/432cac15-8ed7-4a3f-abf5-a3208ea7abfc/8fff32f8dc169560.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Tres aciertos entre cinco devueltos: precision@5 = 3/5 = 0,60. Se repite el cálculo para cada consulta del golden set y se promedia: ese promedio es el número que describe la configuración. Una configuración alternativa — con reranking, con otra estrategia de búsqueda — se mide contra el mismo golden set y los dos promedios se comparan en igualdad de condiciones.

![articulo-02-figura-01-golden-set.jpg](https://media1-production-mightynetworks.imgix.net/asset/197f17c5-5289-4c00-9c63-0e65ae582690/articulo-02-figura-01-golden-set.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Dos matices que elevan la medición sin complicarla:

**Elegir k con intención.** La k de la métrica debe ser la k del sistema: si pasas cinco presupuestos al LLM, mide precision@5. Medir precision@10 cuando solo usas cinco documentos responde una pregunta que nadie ha hecho. Y si dudas entre pasar tres o cinco documentos al generador, medir ambas (precision@3 y precision@5) convierte también esa duda en una decisión con datos.

**La exhaustividad como complemento.** La precisión pregunta "de lo que devolviste, ¿cuánto vale?"; su métrica espejo, la exhaustividad (recall), pregunta "de lo que valía, ¿cuánto devolviste?". Si al anotar el golden set has identificado *todos* los presupuestos relevantes para cada consulta — viable en un corpus de empresa, inviable en uno de millones de documentos —, calcular recall@k es gratis y detecta un fallo que la precisión no ve: el documento valioso que no aparece por ninguna parte. Existen métricas más sofisticadas que además premian el orden dentro del top-k, pero para decidir si una técnica entra o no en el pipeline, precisión y exhaustividad sobre tus k reales llegan de sobra. La sofisticación métrica tiene su momento; este no es.

## **La otra columna de la tabla: latencia**

La relevancia es la mitad de la decisión. La otra mitad es lo que cuesta conseguirla, y en recuperación el coste dominante es la latencia: cada técnica que añade calidad — un segundo modelo, una búsqueda adicional, una fusión — añade tiempo en el camino crítico de cada consulta.

Medirla artesanalmente exige solo dos precauciones. La primera: **medir en caliente**. La primera consulta tras arrancar el servicio paga costes fijos (carga de modelos, conexiones, cachés frías) que no representan la operación normal; se descarta y se mide a partir de la segunda. La segunda: **quedarse con la mediana de varias ejecuciones, no con la media**. Tres a cinco ejecuciones por consulta bastan; la mediana resiste el valor atípico de un pico puntual de la máquina, que con muestras tan pequeñas arrastraría la media sin piedad.

El resultado es la tabla completa que sostiene la decisión: una fila por configuración, una columna de precisión, una columna de latencia mediana. Todo lo que viene después es leer esa tabla con criterio.

## **El arnés de medición en el servicio IA**

Llevar esto a código es deliberadamente poco glamuroso. El golden set es un archivo de datos versionado junto al código — cambiarlo debe pasar por revisión, porque cambiar la vara de medir es cambiar el significado de todas las mediciones anteriores:

```json
{
  "annotation_criterion": "Relevant if it would serve as a direct effort reference for estimating this project",
  "queries": [
    {
      "id": "q01",
      "query": "E-commerce platform with product catalog, cart and admin panel",
      "relevant_budget_ids": ["budget-2023-014", "budget-2024-002", "budget-2022-031", "budget-2023-027"]
    },
    {
      "id": "q02",
      "query": "Mobile app with Stripe payment integration and push notifications",
      "relevant_budget_ids": ["budget-2024-011", "budget-2023-019"]
    }
  ]
}
```

Y el arnés es un script que recorre el golden set, ejecuta el pipeline de recuperación y calcula las dos columnas:

```python
# scripts/measure_retrieval.py
"""Artisanal retrieval measurement against a hand-annotated golden set."""

import json
import time
from pathlib import Path
from statistics import median

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
TOP_K = 5
RUNS_PER_QUERY = 3

def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of the top-k retrieved documents that are relevant."""
    top = retrieved_ids[:k]
    if not top:
        return 0.0
    hits = sum(1 for budget_id in top if budget_id in relevant_ids)
    return hits / len(top)

async def measure(pipeline) -> None:
    golden_set = json.loads(GOLDEN_SET_PATH.read_text())
    precisions: list[float] = []
    latencies_ms: list[float] = []

    for entry in golden_set["queries"]:
        relevant_ids = set(entry["relevant_budget_ids"])

        for _ in range(RUNS_PER_QUERY):
            start = time.perf_counter()
            results = await pipeline.retrieve(entry["query"])
            latencies_ms.append((time.perf_counter() - start) * 1000)

        retrieved_ids = [chunk.budget_id for chunk in results]
        precision = precision_at_k(retrieved_ids, relevant_ids, TOP_K)
        precisions.append(precision)
        print(f"{entry['id']}: precision@{TOP_K} = {precision:.2f}")

    print(f"mean precision@{TOP_K}: {sum(precisions) / len(precisions):.2f}")
    print(f"median latency: {median(latencies_ms):.0f} ms")
```

Una decisión de diseño merece defensa explícita: **esto vive en** `scripts/`**, no en las capas de la aplicación**. Es deliberado. Un arnés artesanal es una herramienta de decisión puntual, no infraestructura: no necesita endpoint, ni tests propios, ni abstracción para futuros casos de uso. Convertirlo prematuramente en un "módulo de evaluación" del servicio es el clásico exceso de ingeniería que después nadie quiere mantener. Cuando el sistema necesite evaluación continua de verdad — automatizada, en CI, con histórico — esa será otra pieza con otro diseño; este script habrá cumplido su función: responder una pregunta concreta, hoy.

## **El marco de decisión: ganancia frente a coste**

Con la tabla delante, la decisión se reduce a situar cada técnica en dos ejes: cuánta relevancia gana y cuánta latencia cuesta. Supón estos resultados en el sistema de estimación:

![image.png](https://media1-production-mightynetworks.imgix.net/asset/c314f1d4-1065-427d-833d-d4d52dc3e7ac/2a8ac037ab5ebfd6.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La lectura ingenua es "el reranking multiplica la latencia por ocho", y es aritméticamente cierta e irrelevante. La lectura correcta usa el denominador adecuado: **el presupuesto de latencia de la experiencia completa**. En este sistema, tras la recuperación viene la generación de la estimación por el LLM, que tarda varios segundos. Los 255 ms añadidos son menos del 5% del tiempo total que percibe el usuario — y a cambio, dos de cada cinco documentos del contexto pasan de ser ruido a ser señal. La estimación se genera sobre referencias correctas. La decisión es obvia en esta dirección.

Cambia el escenario y la misma tabla decide lo contrario. En un autocompletado interactivo con presupuesto total de 300 ms, esos mismos 255 ms son el 85% del presupuesto: inasumible aunque la ganancia de relevancia fuera el doble. La técnica no es buena ni mala; es cara o barata *respecto a un presupuesto*, y el presupuesto lo fija el producto, no el pipeline.

![articulo-02-figura-02-cuadrante-decision.jpg](https://media1-production-mightynetworks.imgix.net/asset/99548da3-bf3d-4a6f-9d4e-7f9d4d9d051a/articulo-02-figura-02-cuadrante-decision.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

[FIGURA 2: Cuadrante de decisión — ganancia de relevancia (eje vertical) frente a latencia añadida como fracción del presupuesto total (eje horizontal), con las cuatro zonas: activar sin dudar, evaluar contra presupuesto, descartar, y la zona de ganancia marginal donde la complejidad añadida no se paga]

El cuadrante deja una zona traicionera que conviene nombrar: la de **ganancia pequeña con coste pequeño**. La tentación es activar la técnica "porque algo suma y apenas cuesta". Pero el coste de una técnica nunca es solo su latencia: es también el modelo extra que operar, la dependencia que actualizar, el modo de fallo nuevo que diagnosticar a las tres de la mañana. Una mejora de 0,02 en precisión rara vez paga ese peaje de complejidad. Si la tabla no muestra una ganancia que se note, la respuesta senior es no añadir la pieza — y la tabla es precisamente lo que te permite decir "no" con fundamento, que es para lo que se construyó.

## **Lo que esta medición no te da (y por qué no pasa nada)**

Seamos honestos con los límites de la herramienta, porque usarla más allá de ellos sí sería un error.

Un golden set de diez consultas **no tiene potencia estadística**: una diferencia de 0,05 entre dos configuraciones puede ser ruido de anotación. Las diferencias que justifican decisiones con esta herramienta son las grandes y consistentes — de 0,48 a 0,80 —, no las décimas. La anotación **arrastra el sesgo de quien anota**: un solo anotador con un criterio escrito es suficiente para decidir, pero su juicio no es la verdad universal del dominio. Y la medición **se detiene en la recuperación**: dice qué documentos llegan al LLM, no qué hace el LLM con ellos; una recuperación perfecta no garantiza una estimación correcta, solo la hace posible.

Nada de esto invalida la práctica, porque la práctica no pretende más de lo que da. La medición artesanal responde una pregunta de diseño — ¿esta técnica entra en el pipeline? — con el rigor justo para esa pregunta. La evaluación sistemática de un sistema RAG completo, con frameworks dedicados, métricas sobre la generación y ejecución continua, es una disciplina en sí misma y tiene su propio espacio más adelante en el programa. Llegar a ella habiendo interiorizado la versión artesanal es llegar entendiendo qué miden los frameworks por dentro, en lugar de consumir sus números con fe.

## **El número que cambia la conversación**

La idea para llevarse: la diferencia entre un sistema de recuperación que evoluciona con criterio y uno que acumula técnicas de moda no está en las técnicas — está en que cada incorporación se decidió contra una tabla con dos columnas: cuánto gana, cuánto cuesta. Construir esa tabla cuesta una tarde: un puñado de consultas reales, anotación manual con un criterio escrito, una métrica que cabe en una servilleta y una mediana de latencias. Es la herramienta más rentable de todo el arsenal RAG, y es la única de este módulo que no requiere escribir código de producción.

En la sesión en vivo esa tabla será protagonista: cada técnica de recuperación que incorporemos al sistema de estimación pasará por ella, y veremos en directo cómo los números — y no las sensaciones — deciden qué se queda en el pipeline y qué se descarta.