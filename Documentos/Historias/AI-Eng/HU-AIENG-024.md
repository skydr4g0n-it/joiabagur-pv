# HU-AIENG-024: Arnés de evaluación, golden set y líneas base — convertir «parece que va mejor» en una tabla que pueda desmentirme

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** un **juez imparcial** —un conjunto de consultas etiquetadas a mano y un arnés que mida cualquier configuración contra él— que arbitre las decisiones de recuperación que hoy están tomadas por argumento,
**para** poder afirmar con un número, y no con una impresión, si la búsqueda semántica mejora lo que la joyería tenía, y para que cada cambio posterior se juzgue por lo que le hace al conjunto y no por el caso que arregla.

---

## Descripción

El sistema tiene un recuperador híbrido completo —expansión de consulta (C20), fusión RRF de tres listas (C21), prefiltro por punto de venta (C22)— y **ninguna de sus decisiones se tomó con una métrica de relevancia**. Se tomaron con una rúbrica de conveniencia que los propios informes declararon insuficiente, y todos ellos escribieron la misma frase: *«C24 lo re-mide»*.

Esta historia construye ese juez. No añade una función al producto: **añade la capacidad de saber si el producto funciona**, que es lo que separa un proyecto que aprueba de uno que destaca según los criterios del PF (*«el sistema tiene evals reales, no sólo pruebas manuales»*).

### El problema que gobierna la historia: los jueces actuales tienen parentesco con una de las partes

El [informe de exploración de C21 §6](../../Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md) midió, sobre 12 consultas y contando aciertos en el top-10:

| Configuración | aciertos / 120 |
|---|---:|
| Vectorial sola | **67** |
| Léxica sola | **107** |
| Mejor fusión (`wC=0,33`, profundidad 40-50) | **113-114** |

Leído sin contexto, ese cuadro dice que la rama vectorial —el proveedor externo, los 170-1707 ms por consulta, el índice HNSW y la mitad de la arquitectura— **aporta siete puntos de ciento veinte**. Pero el propio informe recusa a su juez:

> *«La rúbrica es la función objetivo de la propia rama léxica. `doc_text` lleva líneas canónicas `Tipo:` y `Materiales:`, y la expansión apunta justo ahí; medir "tipo correcto y material correcto" premia por construcción a quien casa esas líneas.»*

Y el mecanismo está medido en su §2: en el corpus, **`concha` casa 0 documentos, `madre` 0, `bonito` 0, `algo` 0**. Las consultas donde la rama vectorial es la única que puede responder son, por construcción, invisibles para una rúbrica léxica. El informe lo enseña con un caso: en `joya con forma de concha marina` la rama léxica entierra en las posiciones 23 y 24 los *Colgante Caracola Marina* y *Pendientes caracola Marina* que la vectorial pone en 1 y 2, y la fusión los sube al top-5 — *«la rúbrica no tiene diana para esa consulta, así que ese acierto no aparece en la tabla»*.

**Y esto ya no es una hipótesis: pasó el 2026-09-06 en el otro índice de este mismo sistema.** En el corpus de conocimiento, C23 midió con un embebedor sustituto que *«la rama léxica gana +6,2 pp de Recall@3»*. Al re-medir contra el proveedor real, el veredicto **se dio la vuelta**: el recall es 93,8 % en las dos configuraciones y la rama léxica ya no gana recuperación, sólo orden. El informe lo escribe sin rodeos — *«el +6,2 pp del §1 era un efecto del sustituto léxico, no una propiedad del sistema»*—, y el umbral que aquel sustituto calibró resultó **citar 4 de las 5 preguntas fuera de dominio**: no un número impreciso, sino el mecanismo de abstención inoperante.

De ahí la primera regla de la historia: **el juez se mide contra el proveedor real y el índice real, nunca contra un sustituto**.

### Los ocho pleitos que este juez tiene que dirimir

Detalle completo en [c24-exploration-measurements.md §2](../../Proyecto%20Final%20AIEng/informes/c24-exploration-measurements.md).

| # | Pleito | Estado hoy |
|---|---|---|
| **P1** | ¿La rama vectorial vale lo que cuesta? | 67 vs 107 vs 114 — con juez recusado |
| **P2** | ¿`wC = 0,33` y profundidad 40-60 son el óptimo? | 36 configuraciones barridas con la misma rúbrica |
| **P3** | La regla de coordinación y los campos escasos; **¿`stone_type` cuenta?** | 111 → 114, y C21 declara que *«ninguna de las doce consultas lo aísla»* |
| **P4** | ¿Qué vale la expansión de sinónimos **en ranking**? | Medida en **alcance** (candidatos), nunca en orden |
| **P5** | ¿El sistema sabe callarse? | El umbral 0,65 deja pasar **1.168 de 1.168** |
| **P6** | ¿Qué cuesta el prefiltro por punto de venta en recall? | Medida la **tasa de llenado**, no la calidad |
| **P7** | ¿La búsqueda semántica bate a la que había? (decisión 12) | **Cero mediciones.** Es la pregunta central del PF |
| **P8** | ¿Compensaría un reranking? | Argumentado y protocolizado, nunca medido |

### El riesgo número uno, y cómo se contiene

Si el golden set se etiqueta con el mismo sesgo que la rúbrica de C21 —premiar tipo y material— **confirmará C21 por construcción y no habrá arbitrado nada**. La contención no es una buena intención: es una **matriz de trazabilidad comprobable por código antes de etiquetar**, que exige, por ejemplo, que al menos doce consultas tengan un documento perfecto cuyo texto **no contiene ningún término de la consulta tras expansión**.

### Alcance de esta historia (sí)

- **Paquete `ai-service/src/jbg_ai/evals/`** con carga y validación del golden set, *pooling*, métricas, configuraciones, runner, informe y persistencia opcional.
- **Golden set de 48 consultas juzgadas y 56 escritas** en `ai-service/evals/golden/`, versionado en git, con **relevancia graduada 0-2** y su criterio de anotación escrito **antes** de etiquetar.
- **Una revisión de Alembic**: `ai.eval_run`, `ai.eval_case`, `ai.eval_result`, que la migración fundacional no creó.
- **Cinco configuraciones**: `v0-nombre` (el buscador que la joyería tenía), `v0-fts` (el degradado en español), `v0-cag` (acotado), `v1-vectorial`, `v2-hibrido`.
- **CLI** `uv run evals run --config vX [--persist] [--repeat 3]`, e **informe versionado** en `ai-service/evals/results/` con la tabla de ablations v0→v2.
- **Métricas**: nDCG@5, Recall@5, MRR, P@3, abstención, `unjudged@5`, `desplazamiento_sintetico@5`, `p50`/`p95` en dos columnas y coste por consulta — todas **desglosadas por `data_origin`**.
- **Vectores de consulta congelados** y **tupla de procedencia** por ejecución, que es lo que hace comparable un run con otro.
- **Desempate determinista** en las dos sentencias de recuperación — desviación declarada, toca ruta viva.
- **Posible cambio de defaults** en `Settings` bajo una regla escrita antes de medir.
- Las dos mediciones que [C21 §12](../../Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md) dejó sin dueño: latencia real de la rama léxica dentro del orquestador y efecto del singleton del cliente de embeddings sobre el `p95`, en frío y en caliente.

### Fuera de alcance (no)

- **Calibrar el umbral de distancia.** Es **C25**, que ya lo pide en su ficha. C24 entrega la **distribución de distancias por grado de relevancia**, que es el insumo que hoy no existe.
- **`v3-señales`** (disponibilidad, rotación, perfil de POS): **C25**.
- **RAGAS, validador anti-alucinación, escenarios de agente y adversarios**: **C38**, que se integra en este mismo runner.
- **Reranking.** Se deja el protocolo ejecutable y el número que lo haría decidible; no el reranker.
- **Ruta HTTP nueva ni `openapi.json` regenerado.** `GET /v1/evals/runs` **ya está publicado** y su stub nombra a C24: deja de ser stub, no se mueve el contrato.
- **Cualquier cambio en `backend/`, `frontend/`, `terraform/` o `.github/workflows/`.** Cero.
- **Tocar `indexing/embeddings.py`** (congelado desde C11), `enrichment/vocabularies.yaml`, `retrieval/synonyms.py`, `retrieval/fusion.py` ni el paquete `knowledge/`.
- **Las dos categorías que hoy no son medibles** —sustituto/sin stock (C26) y ambigua/requiere aclaración (C30)—: se **escriben** las consultas, no se juzgan.
- **Etiquetar escopado por punto de venta.** El golden set va **sin escopar**, decisión ya tomada en C22 para no mezclar calidad de recuperación con cobertura de surtido.

### Decisiones de diseño ya acordadas

Las trece están razonadas con alternativas en el [informe de exploración §4](../../Proyecto%20Final%20AIEng/informes/c24-exploration-measurements.md).

| # | Decisión | Motivo |
|---|---|---|
| **D1** | **Dos líneas base léxicas, no una**: `v0-nombre` (`Name.Contains` + SKU exacto, el buscador que la joyería tenía) y `v0-fts` (FTS español sobre `name ‖ sku ‖ descripción`, el degradado que construyó C15/C16) | Sólo la primera responde la decisión 12; sólo la segunda evita la objeción de hombre de paja. **Y juntas informan de algo que ninguna sola puede**: qué parte de la mejora es tokenizar en español —gratis, sin IA— y qué parte es recuperación semántica |
| **D2** | **Vectores de consulta congelados** (JSONL, 6 decimales) + **tupla de procedencia** como «seed»: `(golden_set_version, config_id, index_set_hash, embedding_model_version_key, git_sha)`. Y **`, d.product_id`** en los dos `ORDER BY` de `retrieval/search.py` | El sustituto offline está descartado por lo que le pasó a C23. Y sin tercera clave de orden, con `LIMIT 60`, **qué filas sobreviven al empate no está definido en PostgreSQL**: sin esto el arnés no detecta regresiones, que es su función principal |
| **D3** | **Graduado 0-2 con anclas mecánicas** en `criterion.md`, **publicando también la lectura binaria** (`relevante ⇔ grado ≥ 1`) | El binario que recomienda S10 destruye el caso crítico del dominio —«anillo correcto, talla equivocada» no es 0 ni 2—. La lectura binaria sale gratis y contesta la objeción con datos: si las dos ordenan igual las configuraciones, la robustez queda demostrada |
| **D4** | **48 juzgadas / 56 escritas**, derivadas de los pleitos y no de la ficha; las 24 consultas de C20/C21 entran **marcadas `in_tuning_set`** y se reporta con y sin | Las 60-70 del diseño se fijaron antes de que existieran las mediciones que dicen qué hay que medir. Y aquellas 24 **se usaron para calibrar** `wC`, la profundidad y la coordinación: incluirlas sin marcar sería medir sobre el conjunto de ajuste |
| **D5** | **Agrupar por consulta, contar por juicio**: la recuperación corre **siempre sobre los 1.168 documentos**; las consultas se agrupan por el origen de sus relevantes. Más la métrica `desplazamiento_sintetico@5` | Restringir el corpus a `data_origin='real'` daría 436 documentos —**más fácil**— e inflaría el número del titular. La frase del §8.1.1 del diseño sólo tiene sentido si ambos corren sobre el mismo corpus |
| **D6** | **`v0-cag` acotado**: tokens, coste y **curva de escala**, más Recall@5 sobre 12 consultas. Contexto compactado `sku · nombre · tipo · materiales`, **sin precio** | CAG no aparece en ninguna línea de código del sistema, y el PF exige describir *«CAG/RAG»* como componentes. No es una fila de calidad: es **la prueba medida de por qué existe RAG**. El precio queda fuera porque `RetrievalResult` no lo emite: la autoridad es .NET |
| **D7** | ***Pooling* de profundidad adaptativa**: base 20, +10 mientras el bloque anterior dé algún relevante, tope 60; `judged_depth` registrado. Juicios **apendables** por `(query_id, product_id)` y **`unjudged@5`** reportado | Profundidad fija 10 da un denominador optimista; fija 60 son siete horas de las que la mayoría son ceros evidentes. Y **lo no juzgado cuenta 0**: sin juicios apendables, `v3-señales` de C25 se mediría con un handicap invisible |
| **D8** | **C24 mide la abstención y publica la distribución de distancias por grado; C25 calibra** | Con 0,65 dejando pasar el corpus entero, el número dirá que `v0-nombre` abstiene al 100 % —no encuentra nada nunca— y que el híbrido no: cierto y engañoso. La re-fijación por cuantil ya está en la ficha de C25 |
| **D9** | Cada juicio guarda el **`source_hash`** que el documento tenía al etiquetarse | `FIX1` reenriqueció 22 productos con el plazo *«antes de que C24 etiquete»*. Esa ventana se cumplió **por planificación**; con el hash deja de depender de ella |
| **D10** | ***Artifact-first***: el `Report` se serializa **siempre** a Markdown y JSONL en git, y las tres tablas se escriben **sólo con `--persist`**. El golden set es un fichero, nunca una tabla | No es de utilidad, es de contrato: `GET /v1/evals/runs` está publicado en el `openapi.json` congelado y su stub **nombra a C24**. Y cambiar la vara de medir tiene que pasar por revisión de código |
| **D11** | **`pricing.yaml`** versionado con fecha y fuente; **cero es un valor registrado, no un hueco** | La columna de coste sólo informa porque existe `v0-cag`: embeber una consulta son cinco millones de consultas por dólar. Es lo que permite leer la ganancia contra un coste, que es el marco de decisión de S10 |
| **D12** | **Dos columnas de latencia siempre**: `p95_retrieval` (a la que se aplica el criterio) y `p95_e2e`. **En caliente**, con **3 ejecuciones** por consulta | Con el proveedor en 170-1707 ms, un `p95` extremo a extremo será ~1.700 ms y el criterio del diseño (*«p95 de retrieval < 500 ms»*) se declararía incumplido sin querer. La instrumentación por etapa **ya existe** en el orquestador |
| **D13** | C24 **cambia el default** en `Settings` si el veredicto es material, bajo regla escrita **antes** de medir: delta de nDCG@5 > 0,05 **y** mismo signo en las tres lecturas de D4 **y** ninguna categoría empeorada en más de 0,05 | Es para lo que se construyeron los knobs como parámetros. Con la regla escrita, «el barrido de C21 se rehízo con el juez bueno» queda respaldado por un criterio y no por una impresión |

**Cortes que no se reabren:** `indexing/embeddings.py` congelado desde C11 · `enrichment/vocabularies.yaml` intacto · sin ruta HTTP nueva ni `openapi.json` regenerado · sin tocar `backend/`, `frontend/`, `terraform/` ni `.github/workflows/` · sin `ai.query_log` · Python no lee el esquema `public` por SQL · el golden set se etiqueta **sin escopar**.

**Referencias:**

- Mediciones y las trece decisiones: [c24-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c24-exploration-measurements.md).
- Diseño RAG [§7.6, §8.1.1, §11.1, §11.2 y §15](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — recuperación, corpus híbrido, golden set, ablations y limitaciones a declarar.
- Plan de changes, [ficha C24](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) y la entrada del §0 del 2026-08-31 que retiró el doble etiquetado.
- Informes que dejaron pleitos abiertos: [c21-hybrid-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md), [c22-implementation-measurements.md](../../Proyecto%20Final%20AIEng/informes/c22-implementation-measurements.md), [c23-implementation-measurements.md](../../Proyecto%20Final%20AIEng/informes/c23-implementation-measurements.md).
- Specs vivas que enmarcan el change: `openspec/specs/vector-retrieval/`, `openspec/specs/hybrid-fusion/`, `openspec/specs/query-expansion/`, `openspec/specs/pos-projection/`, `openspec/specs/ai-vector-schema/`, `openspec/specs/ai-service-api-contracts/`.
- Historias previas: [HU-AIENG-014](HU-AIENG-014.md) (recuperador vectorial), [HU-AIENG-020](HU-AIENG-020.md) (diccionario de sinónimos), [HU-AIENG-021](HU-AIENG-021.md) (fusión híbrida), [HU-AIENG-022](HU-AIENG-022.md) (prefiltro por punto de venta), [HU-AIENG-023](HU-AIENG-023.md) (corpus de conocimiento).
- Apuntes: [S10 · Cómo saber si el reranking compensa](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Como%20saber%20reranking%20compensa%20-%20medicion%20artesanal%20relevancia%20.md), [S16 · Tratamiento de regresiones](../../Sesiones%20Master%20AIEng/S16_Produccion_II/Tratamiento%20de%20regresiones.md), [S16 · Un sistema debe saber decir «No lo sé»](../../Sesiones%20Master%20AIEng/S16_Produccion_II/Un%20sistema%20debe%20saber%20decir%20%E2%80%9CNo%20lo%20se%E2%80%9D.md).
- Change: [`add-eval-harness-golden-set-and-baselines`](../../../openspec/changes/add-eval-harness-golden-set-and-baselines/) · ticket [T-AIENG-024](../../../openspec/changes/add-eval-harness-golden-set-and-baselines/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: La tabla separa lo que la joyería tenía de lo que aporta tokenizar y de lo que aporta la IA

**Dado que** el repositorio contiene dos buscadores léxicos distintos y sólo uno de ellos es anterior al trabajo de IA
**Cuando** se ejecuta el arnés sobre todas las configuraciones
**Entonces** la tabla incluye una línea base que reproduce el buscador que la joyería tenía —coincidencia de subcadena sobre el nombre, más el código exacto— y otra que reproduce el buscador degradado en español
**Y** las dos se identifican con nombres que no confunden una con la otra
**Y** la línea base en español se compone sobre el mismo texto que ve el buscador de .NET, y no sobre el documento canónico completo, que contiene más campos
**Y** existe una comprobación automática de que esa equivalencia de texto se mantiene si el renderizador del documento cambia

### Escenario 2: Dos ejecuciones de la misma configuración dan el mismo resultado

**Dado que** un arnés que no puede repetir una medición no puede detectar una regresión
**Cuando** se ejecuta la misma configuración dos veces sin que cambien el índice, el golden set ni el modelo de embeddings
**Entonces** las métricas son idénticas
**Y** cada ejecución registra la procedencia con la que se obtuvo: versión del golden set, configuración, huella del índice, modelo de embeddings y revisión del código
**Y** dos ejecuciones cuya procedencia no coincide se marcan como no comparables en lugar de compararse igualmente

### Escenario 3: Un empate en la puntuación léxica no altera qué documentos sobreviven al corte

**Dado que** la rama léxica produce empates frecuentes y la lista se trunca antes de fusionar
**Cuando** dos documentos comparten la misma puntuación y el corte cae entre ellos
**Entonces** el que sobrevive es siempre el mismo
**Y** lo mismo ocurre en la rama vectorial ante distancias iguales
**Y** el orden relativo de los documentos con puntuaciones distintas no cambia respecto al comportamiento anterior

### Escenario 4: La relevancia se lee de dos maneras y las dos se publican

**Dado que** el dominio tiene respuestas parcialmente correctas —la pieza correcta en la talla equivocada— que una escala de dos valores no puede expresar
**Y** que un solo anotador corre riesgo de desplazar su criterio a lo largo de la sesión
**Cuando** se etiqueta el golden set
**Entonces** cada juicio toma uno de tres grados, con un criterio escrito y versionado **antes** de empezar a etiquetar
**Y** el grado intermedio se define por una condición comprobable sobre la consulta y la ficha, no por una impresión
**Y** el informe publica las métricas dos veces: con los grados y con la lectura de dos valores derivada de ellos
**Y** si las dos lecturas ordenan las configuraciones de forma distinta, eso se señala como hallazgo

### Escenario 5: El golden set no puede nacer sesgado a favor de una de las ramas

**Dado que** la rúbrica con la que se calibró la fusión premia por construcción a la rama léxica
**Y** que un golden set escrito por quien conoce el vocabulario del catálogo tiende a producir consultas con anclaje léxico
**Cuando** se carga el golden set
**Entonces** se comprueba automáticamente que un número mínimo de consultas tiene al menos un documento del grado máximo cuyo texto **no contiene ningún término de la consulta**, ni siquiera tras la expansión de sinónimos
**Y** se comprueba que existen consultas cuya respuesta depende de un campo de baja cobertura, y otras que aíslan el tipo de piedra
**Y** se comprueba que la categoría de sinónimos cubre las tres clases de entrada del diccionario
**Y** si alguna de esas comprobaciones falla, la carga del golden set falla en lugar de continuar

### Escenario 6: Las consultas que sirvieron para calibrar están marcadas y no se esconden

**Dado que** un grupo de las consultas disponibles se usó para fijar los pesos de fusión, la profundidad y la regla de coordinación
**Cuando** esas consultas entran en el golden set
**Entonces** quedan marcadas como pertenecientes al conjunto de ajuste
**Y** el informe publica cada métrica tres veces: sobre el conjunto completo, sólo sobre las de ajuste y sólo sobre las nuevas
**Y** una decisión de configuración sólo se considera confirmada si el resultado apunta en el mismo sentido en las tres lecturas

### Escenario 7: La porción real se mide sobre el catálogo entero, no sobre un catálogo más pequeño

**Dado que** el corpus mezcla productos reales y sintéticos y el resultado principal del proyecto es el de la porción real
**Cuando** se calculan las métricas desglosadas por origen
**Entonces** la recuperación se ejecuta siempre sobre el catálogo completo, con independencia del desglose
**Y** las consultas se agrupan según el origen de sus documentos relevantes
**Y** el recuento considera únicamente los documentos relevantes de ese origen
**Y** restringir el corpus a un solo origen no es una configuración disponible

### Escenario 8: Si el corpus sintético estorba, se ve

**Dado que** un corpus sintético puede ser más fácil, pero también puede ser ruido que desplaza a la respuesta buena
**Cuando** se evalúa una consulta cuya respuesta correcta es un producto real
**Entonces** se registra si algún producto sintético irrelevante aparece por delante de la primera respuesta correcta
**Y** ese recuento se publica como métrica propia
**Y** el informe distingue explícitamente «el sintético es más fácil» de «el sintético estorba»

### Escenario 9: La configuración sin recuperación demuestra por qué existe la recuperación

**Dado que** el proyecto debe describir la progresión desde un prototipo sin recuperación hasta el sistema actual, y esa etapa no existe en el código
**Cuando** se ejecuta la configuración que pone el catálogo entero en el contexto del modelo
**Entonces** se registra el tamaño en tokens del catálogo completo y el coste por consulta
**Y** se registra la proyección de ese tamaño para catálogos mayores, hasta el punto en que deja de caber
**Y** el contexto no incluye el precio de ningún producto, porque la autoridad sobre el precio no es este servicio
**Y** si el catálogo excede el presupuesto de contexto, se recorta de forma determinista y se registra cuántos documentos quedaron fuera, en lugar de fallar o de recortar en silencio

### Escenario 10: El etiquetado profundiza donde hay algo que encontrar, y declara hasta dónde llegó

**Dado que** juzgar a la misma profundidad todas las consultas gasta la mayor parte del esfuerzo en descartes evidentes
**Y** que un conjunto juzgado demasiado poco produce un denominador optimista
**Cuando** se construye el conjunto de documentos a juzgar
**Entonces** se parte de una profundidad base común a todas las configuraciones
**Y** se continúa profundizando en una consulta mientras el último tramo siga aportando documentos relevantes
**Y** se detiene en la profundidad máxima que el recuperador puede llegar a mostrar
**Y** cada consulta registra hasta qué profundidad fue juzgada

### Escenario 11: Una configuración cuyos resultados nadie ha juzgado no se presenta como comparable

**Dado que** los documentos que nadie juzgó cuentan como irrelevantes, y una configuración futura puede promover documentos que no estaban en el conjunto juzgado
**Cuando** se evalúa cualquier configuración
**Entonces** se informa qué proporción de sus primeros resultados carece de juicio
**Y** una configuración con una proporción alta se señala como no comparable en el informe
**Y** los juicios se pueden ampliar más adelante sin volver a etiquetar los existentes, identificándolos por consulta y documento

### Escenario 12: La abstención se mide, se explica y no se calibra todavía

**Dado que** el umbral de distancia vigente deja pasar prácticamente todo el catálogo, de modo que la abstención observada responde a la mecánica de las ramas y no a una decisión de confianza
**Cuando** se evalúan las consultas que el catálogo no puede satisfacer
**Entonces** esas consultas son plausibles dentro del dominio y no texto sin sentido, para que las configuraciones puedan diferenciarse
**Y** el informe publica la distribución de distancias separando los documentos relevantes de los irrelevantes
**Y** el informe declara que las cifras de abstención son provisionales y que su recalibración corresponde al change siguiente
**Y** no se modifica el umbral vigente

### Escenario 13: Un documento que cambia después de etiquetarse no pasa desapercibido

**Dado que** el texto de un producto puede reescribirse por un reenriquecimiento posterior
**Cuando** se ejecuta el arnés
**Entonces** se compara la huella del texto de cada documento juzgado con la que tenía al etiquetarse
**Y** se informa cuántos juicios se apoyan en un texto que ya ha cambiado
**Y** esa cifra aparece en el informe junto a las métricas, no en un registro aparte

### Escenario 14: El resultado vive en el repositorio, y la base de datos es opcional

**Dado que** el resultado de una evaluación es evidencia del proyecto y debe poder compararse entre revisiones
**Cuando** termina una ejecución
**Entonces** el informe y el detalle por consulta quedan escritos como ficheros versionables
**Y** la escritura en la base de datos ocurre únicamente si se solicita de forma explícita
**Y** el arnés produce su informe aunque no se escriba nada en la base de datos
**Y** el conjunto de consultas y sus juicios viven como ficheros del repositorio, de modo que modificarlos exige revisión de código

### Escenario 15: La latencia se informa dos veces, y el criterio se aplica a la que corresponde

**Dado que** la llamada al proveedor de embeddings domina el tiempo total y no depende de este servicio
**Cuando** se mide el tiempo por consulta
**Entonces** se informa por separado el tiempo del recuperador y el tiempo total percibido
**Y** el criterio de aceptación de latencia se aplica al primero, y el segundo se publica junto al presupuesto acordado
**Y** la medición descarta la primera ejecución y promedia varias, para que el resultado no dependa del arranque en frío

### Escenario 16: Un valor por defecto sólo cambia si el veredicto es lo bastante grande

**Dado que** un conjunto de este tamaño no distingue diferencias pequeñas de ruido de anotación
**Cuando** el barrido de configuraciones señala un óptimo distinto del vigente
**Entonces** el valor por defecto sólo se modifica si la diferencia supera el umbral acordado
**Y** si el sentido de la diferencia es el mismo en las tres lecturas del conjunto
**Y** si ninguna categoría empeora más de lo acordado
**Y** el criterio estaba escrito antes de ejecutar la medición

### Escenario 17: Fuera de alcance explícito

**Dado que** esta historia entrega el juez y las líneas base, no las mejoras que el juez vaya a aprobar
**Cuando** se revisa el entregable
**Entonces** **no** se ha recalibrado el umbral de distancia: eso es el change siguiente
**Y** **no** existen señales de negocio en el ranking, ni sustitutos, ni validador anti-alucinación, ni escenarios de agente
**Y** **no** hay ruta HTTP nueva ni `openapi.json` regenerado
**Y** **no** se ha tocado `backend/`, `frontend/`, `terraform/` ni `.github/workflows/`
**Y** las consultas de las dos categorías que hoy no son medibles están escritas pero sin juicios

---

## Notas adicionales

- **Actor: el desarrollador del proyecto**, y es la primera historia de la rama de IA cuyo beneficiario no es el operador ni el administrador. No es una excepción caprichosa: el §11 del diseño y los criterios del PF tratan la evaluación como componente entregable, y el §16 exige *«tabla de ablations v0→v3 reproducible con un comando»*. El operador se beneficia de rebote, porque cada decisión posterior sobre el buscador que usa se tomará contra este juez.

- **Este change arbitra a cuatro changes ya archivados.** C20, C21, C22 y el propio C23 escribieron en sus informes que C24 re-mediría sus decisiones. Es la primera vez en el proyecto que un change tiene autoridad para **cambiar los defaults de otros** (D13), y por eso la regla que lo permite se escribe antes de medir y no después.

- **Duodécima vez que la zona de una ficha se queda corta.** La ficha declara zona `evals/`; el change toca además `retrieval/search.py` (desempate, D2) y posiblemente `config/settings.py` (defaults, D13). Va tras C08, C07, C15, C16, C17, C18b, C20, C21, C22 y C23.

- **El etiquetado necesita planificación propia, y no cabe en una sesión.** Es requisito del change, no una nota:
  - Con profundidad adaptativa, **~3 h 15** estimadas para 48 consultas.
  - **Tres sesiones de aproximadamente una hora, agrupadas por categoría.** Etiquetar seguidas las seis de sinónimos mantiene la vara más quieta que seis dispersas entre 48, y evita el modo de fallo que el plan nombra: *«un etiquetador cansado y único es exactamente el fallo que el doble etiquetado ya no puede corregir»*.
  - **El tope de 2 h de la ficha no es vinculante**: se escribió cuando la restricción era un calendario que dejó de existir el 2026-08-31.
  - **Relectura diferida** de las consultas etiquetadas con dudas, que es lo que sustituye a la conciliación entre anotadores.

- **`design.md` obligatorio** en el change. Hay trece decisiones con alternativa real y coste asimétrico, y **dos de ellas contradicen la ficha**: el desempate toca ruta viva en un change declarado de evaluación, y el cambio de defaults toca configuración de producción.

- **Limitaciones a declarar en el README**, hermanas de las de C06b, C20, C21 y C23:
  - **No hay acuerdo entre anotadores.** El diseño prometía doble etiquetado con conciliación entre dos personas; el proyecto lo desarrolla una sola, así que esa mitigación **no se aplicó**. Se conserva el *pooling* y la relectura diferida. Los valores absolutos llevan el sesgo de un único juicio; **lo comparable entre configuraciones sigue siendo válido, porque el sesgo es el mismo en todas las filas**.
  - **El etiquetador escribió parte del corpus**: los 764 productos sintéticos salieron de C06b. Es irreducible.
  - **El conjunto es pequeño y su porción real más aún.** Con ~25-30 consultas reales, el intervalo de confianza del criterio de aceptación es de ±0,13: **no distingue 0,80 de 0,88**.
  - **El coste del prefiltro por punto de venta en recall queda sin medir** si la fila escopada se recorta.

- **Verificación posterior (no DoD de merge):** repetir la evaluación con consultas escritas por alguien que no construyó el sistema, que es la única mitigación real del sesgo del anotador único; y volver a ejecutar el arnés tras C25 para comprobar que los juicios apendables funcionan como se diseñaron.

---

## Tareas

1. **Verificar el entorno antes de nada** (base levantada en el 5433 con los 1.168 documentos, clave de embeddings operativa, `SSL_CERT_FILE` configurado). **Si algo falla, parar y configurarlo**: sin base y sin clave no hay *pooling* posible.
2. Completar artefactos OpenSpec del change `add-eval-harness-golden-set-and-baselines`: `proposal`, **`design.md` obligatorio**, `specs` y `tasks`.
3. **Escribir `criterion.md`** con las anclas de grado, **antes** de etiquetar nada.
4. **Redactar las 56 consultas** por categoría, marcando `in_tuning_set` y dejando sin juicios las dos categorías no medibles.
5. **Python — `evals/golden.py`:** carga, validación y **comprobación automática de la matriz de trazabilidad**; la carga falla si el golden set no cumple los requisitos por pleito.
6. **Python — `retrieval/search.py`:** desempate determinista en las dos sentencias, con su test. *(Desviación declarada: toca ruta viva.)*
7. **Python — `evals/configs.py`:** las cinco configuraciones, con `v0-nombre` y `v0-fts` replicando las semánticas de .NET.
8. **Python — `evals/pooling.py`:** unión de listas, profundidad adaptativa con regla de parada, `judged_depth` y detección de no juzgados.
9. **Congelar los vectores** de las 48 consultas contra el proveedor real y versionarlos.
10. **Etiquetar en tres sesiones agrupadas por categoría**, con relectura diferida de las dudosas.
11. **Python — `evals/metrics.py`:** nDCG@5, Recall@5, MRR, P@3, abstención, `unjudged@5`, `desplazamiento_sintetico@5`, lectura binaria derivada, y desglose por origen según D5.
12. **Python — `evals/runner.py` y `report.py`:** orquestación, tupla de procedencia, medición de latencia en dos columnas y en caliente, y serialización a Markdown y JSONL.
13. **Alembic:** una revisión con `ai.eval_run`, `ai.eval_case` y `ai.eval_result`.
14. **Python — `evals/repository.py`:** sumidero opcional bajo `--persist`; el runner no lo importa.
15. **Python — `evals/cli.py`:** `uv run evals run --config vX [--persist] [--repeat 3]`, con documentación en `ai-service/README.md`.
16. **`GET /v1/evals/runs`** deja de ser stub y sirve las ejecuciones persistidas, **sin mover `openapi.json`**.
17. **`pricing.yaml`** con precios verificados contra la fuente el día de la implementación.
18. **Ejecutar el barrido** y aplicar la regla de D13 sobre los defaults, documentando el resultado se muevan o no.
19. **Informe versionado** en `ai-service/evals/results/` con la tabla de ablations v0→v2, las tres lecturas de D4, la distribución de distancias por grado y la curva de escala de CAG.
20. **Tests** en `ai-service/tests/evals/`, todos ejecutables sin proveedor.
21. Enlazar la HU en [`Documentos/epicas.md`](../../epicas.md) (EP17) **en el apply**.
22. `openspec validate --all --strict` en `0 failed` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** **5** — es la historia que convierte el proyecto en defendible. Sin ella, la arquitectura RAG entera está justificada por argumento y la pregunta central del PF —¿mejora sobre lo que había?— no tiene respuesta. No baja de 5 aunque el operador no vea nada: el §16 del diseño la pone en el checklist de entrega y los criterios del PF la nombran como lo que separa aprobar de destacar.
- **Urgencia (mercado / feedback):** **5** — está en la **cadena crítica** `C21 → C24 → C25 → C26 → C34 → C36` y bloquea a C25 y a C38. Es el único change pendiente que bloquea a dos.
- **Complejidad / esfuerzo:** **4** — el código es acotado (un paquete, una migración, sin contrato nuevo); lo caro es el **etiquetado** —48 consultas con profundidad adaptativa, tres sesiones— y las **dos desviaciones** que tocan ruta viva y configuración de producción.
- **Riesgos y dependencias:**
  - **El golden set etiquetado con el sesgo de la rúbrica de C21** es el riesgo estructural: confirmaría a C21 por construcción y el change no arbitraría nada. Se mitiga con la matriz de trazabilidad comprobada por código antes de etiquetar, no con buena intención.
  - **El desempate no determinista** de `retrieval/search.py`: sin corregirlo, el test de reproducibilidad pasa en verde mientras el arnés produce ruido. Es el mismo patrón que C23 acaba de sufrir con su constante compartida entre escalas distintas.
  - **Lo no juzgado cuenta cero**, y el daño es **diferido**: se manifiesta en C25 cuando `v3-señales` promueva documentos que nadie juzgó.
  - **Fatiga del anotador único**, mitigada por el reparto en tres sesiones por categoría.
  - **Dependencia dura del entorno**: sin base levantada y sin clave de embeddings no se puede construir el *pooling*. C23 se exploró con el contenedor apagado y tuvo que corregir cifras después.
  - **`HT-ARTRUTX` tiene surtido cero** y responde 503: hay que excluirlo si se ejecuta la fila escopada.
  - **Zona compartida con C25 y C26 en `retrieval/`**, limitada a dos líneas de `ORDER BY`; y con C38, que se integrará en este mismo runner.
  - **El criterio de aceptación del diseño puede resultar inalcanzable tal como está escrito** (`p95 < 500 ms`): se resuelve informando dos columnas, pero si se leyera a una sola el change entregaría un rojo que no es suyo.
