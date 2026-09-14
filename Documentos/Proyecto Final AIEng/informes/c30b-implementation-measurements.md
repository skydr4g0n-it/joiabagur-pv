# C30b — informe de implementación: el argumentario, y las tres cosas que la implementación refuta

**Change:** `add-assist-pitch-generation` (C30b) · **Rama:** `c30b-add-assist-pitch-generation`
**Fecha:** 2026-09-14 · **Artefacto del barrido:** [`c30b-assist-sweep-5a6e1b4b8621.json`](../../../ai-service/evals/results/c30b-assist-sweep-5a6e1b4b8621.json)
**Muestra declarada:** [`sweep-sample.yaml`](../../../ai-service/evals/assist/sweep-sample.yaml) · **Decisiones previas:** [`c30b-exploration-decisions.md`](c30b-exploration-decisions.md)

C30b entrega la capa de generación: argumentario en prosa en los dos modos anclados a pieza,
salida estructurada con tramo de apoyo verificado, tres comprobaciones deterministas, una sola
reparación, dos políticas de degradación, no persistencia ni en base ni en log, y regeneración
del `openapi.json` por **una descripción**.

Este informe recoge lo **medido**, no lo planeado. Y lo primero que hay que decir es que la
medición **refuta tres cosas** que los propios artefactos de este change daban por buenas: el
riesgo mayor declarado no se materializó ni una vez, el coste real es el doble del estimado, y
el *timeout* de 3 s estaba puesto a 1,05 × p95 sin que nadie hubiera medido la distribución. La
cuarta refutación es de la primera pasada del arnés y es mía: medí el *timeout* contra la
petición entera en vez de contra la llamada, y leí un 70 % donde había un 4,6 %.

---

## 1. Qué se entregó

| Pieza | Fichero | Líneas |
|---|---|---|
| Prompt versionado, sin una sola cifra | `prompts/assist/v1.md` | 55 |
| Prompt + objeto de payload que lee la puerta | `assist/prompt.py` | ~260 |
| Salida estructurada, interna | `assist/schema.py` | ~70 |
| Cliente propio, devuelve `usage` | `assist/llm.py` | ~190 |
| Las tres comprobaciones | `assist/verification.py` | ~250 |
| Reparación única y dos políticas | `assist/pitch.py` | ~250 |
| Runner del barrido | `evals/assist_sweep.py` | ~330 |

Más el cableado en `assist/orchestrator.py` y `api/routers/assist.py`, las constantes nuevas en
`assist/constants.py`, y **125 tests nuevos** en `tests/assist/`, `tests/api/` y `tests/evals/`.

**Ninguna migración**, ni Alembic ni EF Core — y por el motivo inverso al habitual: el
argumentario no se persiste, así que no necesita tabla. **`backend/`, `frontend/`,
`terraform/`, `.github/workflows/`, `retrieval/`, `knowledge/` y `enrichment/` no se tocan.**

**Una excepción de zona, declarada y pedida:** `jbg_ai/db/engine.py`, por el fallo del §6.1. No
es de C30b y no se coló — se arregla porque al comparar las suites por nombres apareció un
defecto real de aislamiento entre tests, y se dejó anotado en vez de convertirse en folclore.

---

## 2. El barrido: 120 generaciones reales, tres anchos de contexto

Muestra estratificada de 40 piezas —20 de un material, 20 de dos o más— declarada **antes** de
medir nada, con sus identificadores escritos y no re-derivados. `gpt-4o-mini`, temperatura 0,
modo «pieza sin pregunta», índice local con 1.168 piezas activas y el corpus de 161 fragmentos.

| Arm | Citas ofrecidas | Rechazo 1.ª pasada | Causas | **Retenidos** | Citas retiradas | Frases | USD/petición |
|---|---|---|---|---|---|---|---|
| **1 sección** | 2,0 | 5/40 = **12,5 %** | 7 × correspondencia | **0** | 5 | 4,38 | 0,00048 |
| **2 secciones** *(lo que se sirve)* | 3,5 | 22/40 = **55,0 %** | 40 × correspondencia | **0** | 29 | 4,55 | 0,00077 |
| **3 secciones** | 5,0 | 28/40 = **70,0 %** | 74 × correspondencia | **0** | 49 | 4,40 | 0,00099 |

**Totales:** 120 generaciones · 175 llamadas al proveedor · **0 errores de proveedor** ·
**0 argumentarios retenidos** · coste total **0,0897 USD**.

### 2.1 · La refutación grande: la puerta numérica no rechazó nada

**0 de 120.** Ni un `figure_not_in_context`, ni un `currency_adjacent_figure`, ni un
`stock_adjacent_figure`, ni un `enumeration_format`, ni un `decimal_form`. Las 121 violaciones
del barrido son **todas** de correspondencia.

Esto contradice lo que el diseño declara como **el riesgo mayor del change**:

> *«La puerta numérica se come los argumentarios buenos y el change no entrega prosa. Es el
> riesgo mayor: un falso positivo cuesta el argumentario entero.»*

No ocurrió ni una vez. La lectura honesta no es «la puerta sobra», sino que **la prevención
funcionó y por eso la detección no tuvo que actuar**, que es exactamente la división de trabajo
que S11 fija y que D1 eligió a propósito: prosa corrida impuesta en el prompt, placeholders
obligatorios, y un fichero de prompt **sin un solo dígito** para que los numerales de las
instrucciones no tienten al modelo. El embudo funcionó por arriba.

Lo que **no** se puede concluir con estas cifras es que la puerta sea innecesaria. El barrido
corre en el modo sin pregunta, a temperatura 0, con un contexto estrecho y sin texto de
operario; la regla de adyacencia existe por una medición del corpus —`750` y `585` viven en
`material-oro.md`— y esa medición sigue siendo cierta. La puerta está probada por los tests
unitarios, incluido el caso de `750 €` que la motivó; lo que el barrido dice es que **su tasa de
falso positivo en producción es cero en 120 generaciones**, que es justo el número que el riesgo
declarado exigía conocer.

### 2.2 · La correspondencia es la única que dispara, y crece con el ancho del contexto

La comprobación que D9 añadió —el modelo declara el tramo de su propio texto que cada cita
sostiene, y el código verifica que ese tramo es subcadena literal— es la única que actúa. Y su
tasa escala con cuántas citas se ofrecen:

```
citas ofrecidas   2,0 ──────► 3,5 ──────► 5,0
rechazo 1.ª pasada 12,5 % ──► 55,0 % ──► 70,0 %
citas retiradas       5   ──►   29   ──►   49
```

**Y no costó un solo argumentario.** Los 120 se publicaron: la política proporcionada retira la
cita y publica la prosa, que es exactamente para lo que se eligió.

### 2.3 · La decoración que D9 existía para prohibir, medida

De las citas **ofrecidas** al modelo, cuántas acaban publicadas:

| Arm | Ofrecidas | Declaradas y verificadas | Declaradas y no verificables | Nunca declaradas | **% publicado** |
|---|---|---|---|---|---|
| 1 sección | 80 | 68 | 5 | 7 | **85,0 %** |
| 2 secciones | 140 | 60 | 29 | 51 | **42,9 %** |
| 3 secciones | 200 | 61 | 49 | 90 | **30,5 %** |

Esta tabla es el argumento de D9 convertido en cifra. En el ancho que se sirve, **el modelo usa
de forma verificable menos de la mitad de lo que se le entrega**: emitir todo lo recuperado
—que es lo que una respuesta sin esta comprobación haría— habría publicado 140 citas donde 60
sobreviven a la verificación. El resto no es atribución: es decoración, y ahora hay un número
delante.

### 2.4 · Coste, y la segunda refutación

El ticket estimaba **~0,0004 USD por petición**. Medido en el ancho que se sirve: **0,00077
USD**, es decir **1,9 ×** la estimación. Dos motivos, los dos visibles en el artefacto: el
contexto real es mayor que los ~1.500 tokens estimados (**2.245 de media por llamada** en el arm
de 2 secciones) y **el 55 % de las peticiones gasta la reparación**, o sea dos llamadas — y la
reparación es más cara que la primera, porque arrastra la salida anterior y la lista de
violaciones.

Sigue siendo despreciable en absoluto —el barrido entero costó **0,0897 USD**— y ninguna
decisión de este change se tomó por coste. Pero la cifra de la ficha era optimista y conviene
que quede corregida en vez de repetida.

---

## 3. Las dos decisiones que el barrido tenía que tomar (tarea 11.4)

### 3.1 · Plegado de signos en la correspondencia: **NO**

Umbral declarado **antes** de medir: se añade si más del 10 % de los fallos de correspondencia
son de puntuación. Medido: **3 de 121 = 2,5 %**. Por arm: 2/7, 0/40, 1/74.

La normalización se queda en `casefold()` + colapso de espacios. El fallo de correspondencia
**no es de puntuación**: es paráfrasis — el modelo resume su propia frase en vez de copiarla —,
y ablandar la comparación no lo arreglaría, sólo la haría más permisiva con lo que sí debe
rechazar. El clasificador que responde esta pregunta vive en el runner y **no toca la
comprobación**: clasificar no es admitir.

### 3.2 · El *timeout* de 3 s: **sí cortaba, y se corrige**

Medido sobre 175 llamadas reales, **por llamada**, que es como se aplica:

| | p50 | p95 | máx | > 3 s | > 4 s |
|---|---|---|---|---|---|
| todas las llamadas | 2.216 ms | 2.863 ms | 10.082 ms | **8/175 = 4,6 %** | 1/175 = 0,6 % |

Tres segundos estaban a **1,05 × p95**. Un umbral puesto encima del p95 no corta generaciones
lentas: corta *jitter*, y lo hace en una de cada veinte llamadas.

**Decisión, con la cifra delante:** el valor sube a **4 s** y pasa a ser **ajustable**
(`JPV_ASSIST_PITCH_TIMEOUT_SECONDS`), que es literalmente lo que el diseño decía hacer *«sólo si
el barrido mide que corta generaciones buenas»*. La asimetría que lo decide: **subir un timeout
no ralentiza ninguna llamada rápida**. La espera típica sigue siendo ~2,2 s, que es de lo que
habla el argumento «no sirve en un mostrador»; lo único que cambia es la cola, que a 3 s se
servía sin argumentario y a 4 s se sirve con uno.

**Nota de procedencia, para que nadie se confunda al releer el artefacto:** el JSON del barrido
declara `serving_timeout_seconds: 3.0`, que es el valor **en vigor cuando se tomó la medición**,
y su campo `calls_over_serving_timeout` cuenta contra ese 3. Es la medición que movió el valor,
no una medición del valor nuevo — y por eso la procedencia se escribe en el artefacto en vez de
reconstruirse de memoria.

**Y una advertencia que hay que leer con la cifra:** esta latencia está tomada desde una máquina
de desarrollo en España, secuencialmente, contra la API pública y **a través de un interceptor
TLS de Norton**. Es una cota superior de la latencia del proveedor, no la de un despliegue en
`eu-*`. Por eso el valor pasa a `Settings`: quien despliegue debe medir su propia distribución y
ajustarlo, sin tocar código.

---

## 4. Lo que la implementación refuta de sus propios artefactos

### 4.1 · El *backoff* de proveedor de C09 no cabe en el presupuesto de esta capa

Las tareas piden *«replicando la costura de `LiteLlmEnrichClient`: temperatura 0, `num_retries: 0`,
**backoff de proveedor propio**»*. Se replicó todo salvo eso, y el motivo es aritmético:
`ENRICH_BACKOFF_BASE_SECONDS` son **2 segundos**, y el presupuesto de una llamada de esta capa
es 4. Una espera que consume la mitad del presupuesto antes de que arranque la llamada
reintentada no es resiliencia en un mostrador; degradar sí, y es gratis.

Además, mantenerlo haría **falsa** la garantía que la spec sí exige: *«The provider MUST NOT be
called more than twice for one request»*. Con reintentos transitorios debajo, dos «llamadas de
generación» pueden ser cuatro HTTP. Sin ellos, el techo es literal y hay un test que lo mide
(`test_a_transient_provider_fault_degrades_instead_of_being_retried`). Un bucle de reintento
configurado para no reintentar habría sido andamio, que es lo que este repositorio ya pagó una
vez con `C25bis`.

**Medido en el barrido:** 0 errores de proveedor en 175 llamadas, así que la ruta de reintento
no se habría ejercitado ni una vez.

### 4.2 · La consulta del operario **no** entra en la lista blanca numérica

La spec dice *«the set of numerals present in the structured payload handed to the model»*. La
consulta se entrega al modelo, así que la primera implementación la incluyó. Se corrigió, y el
motivo no es de estilo:

- La consulta es **qué contestar, no qué es cierto**. Una cifra que el cliente dice en voz alta
  no es un hecho sobre la pieza, y admitirla convierte la pregunta en fuente de evidencia sobre
  aquello que pregunta.
- Es **la única superficie que controla alguien fuera de este código** — la superficie de
  inyección que D8 declara. Dejar que ensanche la puerta es exactamente la misma forma de
  apertura que la regla de adyacencia existe para cerrar, una capa más arriba.

El coste es un falso positivo cuando la respuesta repite una cifra de la pregunta. Comprobado
contra el corpus: las cifras que un operario repite sobre una pieza —`18 mm`, una talla, una
ley— **ya están en el payload**, porque son lo que la pieza declara. La consulta sigue llegando
al modelo como dato delimitado; lo que no hace es dar permiso.

### 4.3 · La capa no hereda ni el modelo ni la credencial de C09, y las dos son suyas

El ticket lista `JPV_RAG_LLM_*` como existentes desde C09 y por tanto reutilizables. **Ninguno de
los dos se hereda**, y por motivos distintos.

**El modelo.** `JPV_RAG_LLM_MODEL` es el de enriquecimiento —`gpt-4o` en este despliegue— y
heredarlo dejaría que un ajuste del enriquecimiento moviera, sin que nadie se entere, el modelo
de una llamada de mostrador cuyo coste, latencia y tasa de rechazo se han medido sobre otro.
Nació como constante del módulo por ese motivo, y **en revisión se promovió a ajuste propio**,
`JPV_ASSIST_LLM_MODEL`, con `openai/gpt-4o-mini` —el modelo sobre el que está medida cada cifra
de este informe— como defecto. Es la misma corrección que el *timeout*: el argumento era contra
**heredar en silencio**, no contra **poder cambiarlo**, y confundir las dos cosas dejaba una
constante donde hacía falta una variable propia.

**La credencial.** `JPV_ASSIST_LLM_API_KEY`, también nueva y también opcional. Separarla es lo
que permite atribuir el gasto, limitar la tasa y rotar la generación de mostrador aparte del
enriquecimiento por lotes: son dos llamadas de forma muy distinta, una sin nadie esperando y
otra con un cliente delante. **Opcional a propósito**: hacerla obligatoria habría dejado de
generar en cualquier despliegue existente el mismo día en que apareció el campo, y lo habría
hecho **de forma invisible**, porque esta ruta degrada a 200 sin prosa en vez de fallar. Por eso
repliega a `JPV_RAG_LLM_API_KEY` **y deja constancia de cuál está en vigor**, una vez por
proceso: `stage=assist_client model=… timeout_s=… credential=assist|rag_fallback`. Un repliegue
silencioso dejaría creer a un despliegue que ha separado sus credenciales cuando no lo ha hecho.

**Lo que queda fuera y está anotado** —y aquí hay que corregir lo que esta misma sección dijo en
su primera redacción—: **`terraform/` no hace falta tocarlo**. El rol de instancia ya lee todo el
prefijo `/jbg-demo/`, así que no hay cambio de IAM, y los secretos **no se declaran en Terraform a
propósito**, porque un valor pasado a Terraform se escribe en claro en el fichero de estado. Lo
que falta son cuatro pasos pequeños en `deploy/demo/` y `compose.demo.yaml`, detallados en
[`openspec/DEFERRED_TASKS.md`](../../../openspec/DEFERRED_TASKS.md). Comprobado además que **la
demo no genera hoy**: no pasa ninguna credencial de proveedor al contenedor, así que sirve la
respuesta de C30a con 200 — el comportamiento declarado, no un fallo. Hasta que se aprovisione,
el repliegue mantiene todo funcionando y el log dice que está replegado.

### 4.4 · Y una refutación mía, del propio arnés

La primera pasada del runner marcaba `would_be_cut_by_serving_timeout` comparando el
**tiempo total de la petición** contra un *timeout* que se aplica **por llamada**. Como el 55 %
de las peticiones gasta la reparación y por tanto hace dos llamadas, la métrica contaba casi
toda reparación como un corte: **leía 70 % donde había 4,6 %**, y esa lectura habría justificado
mover el umbral tres veces más de lo que la medición sostiene.

Se corrigió instrumentando la latencia **por llamada** (`PitchOutcome.call_latencies_ms`), se
repitió el barrido entero, y el error quedó fijado con un test que no deja volver:
`test_the_timeout_is_measured_per_call_and_never_per_request`.

---

## 5. Contrato: una descripción, verificada campo a campo

`openapi.json` regenerado con `canonical_openapi_settings()`. La verificación **no** fue leer el
diff, sino aplanar los dos documentos a hojas y compararlas:

```
hojas antes = 1102     hojas después = 1102
añadidas 0 · retiradas 0 · cambiadas 1
  $.components.schemas.AssistResponse.properties.prompt_version.description
    - "Version of the prompt that wrote the pitch. Null while there is no pitch"
    + "Version of the prompt the generation layer ran with; null when it did not run"
forma de prompt_version sin la descripción: IDÉNTICA
  {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Prompt Version"}
campos añadidos [] · retirados [] · con el tipo cambiado []
bloques `required` idénticos: sí · rutas idénticas: sí
```

`test_openapi_snapshot_is_stable` en verde. `supported_claim` **no viaja al cable** y hay un test
que recorre la respuesta serializada para comprobarlo, así que la verificación entera cuesta
**cero** movimiento de forma.

---

## 6. Suites, comparadas por nombres

| Suite | Línea base | Al cierre | Criterio |
|---|---|---|---|
| `ai-service` | **1195 pasan, 0 en rojo** | **1320 pasan, 0 en rojo** | conjunto en rojo **idéntico** (vacío) |
| `frontend/` | **113 en rojo de 597**, 14 de 48 ficheros | sin tocar | este change no toca `frontend/` |

### 6.1 · Dos tests que parecían dependientes del orden, y eran un fallo real — diagnosticado y corregido

Al comparar por nombres apareció algo que ninguna comparación por recuento habría visto.
`tests/evals/test_reproducibility.py::test_a_persisted_report_can_be_read_back_through_the_repository`
y `::test_the_zero_cost_baselines_are_persisted_like_any_other_row` **fallaban** con la selección
`tests/config tests/assist tests/api tests/evals`, intentando resolver el host `db`, y **pasaban**
en la suite completa y en aislamiento. Comprobado con el árbol limpio y con el modificado: mismos
dos nombres en los dos, así que **no eran de este change**.

La tentación era anotarlo como *flakiness* y seguir. No lo es. Es **reproducible en un comando**:

```
pytest tests/api/test_retrieval_real.py tests/evals/test_reproducibility.py  → 2 failed
pytest tests/evals/test_reproducibility.py tests/api/test_retrieval_real.py  → 19 passed
```

**La causa.** `jbg_ai/db/engine.py` mantiene un motor **global de proceso** y `get_engine` recibe
un `Settings`… **que ignoraba** si ya había motor construido. `tests/api/test_retrieval_real.py`
configura a propósito `postgresql+psycopg://u:p@db:5432/jpv` —un host inalcanzable, para
demostrar que la ruta responde 503— y con eso **construía el motor global**. Cualquier consumidor
posterior del mismo proceso recibía ese motor: el test de evaluación, que corre contra un
contenedor real, moría con `failed to resolve host 'db'`. En la suite completa no se veía porque
un test de `tests/db/` que corre en medio **llamaba a `dispose_engine()`** y limpiaba el estado
por casualidad.

Y había un segundo escalón: `get_sessionmaker` devolvía su fábrica cacheada **antes** de
preguntar por el motor, así que aunque `get_engine` supiera decidir, nunca se le preguntaba.

**El arreglo**, en `jbg_ai/db/engine.py` y fuera de la zona declarada de C30b —se hace porque se
pidió expresamente, y se declara en vez de colarse—:

- El motor cacheado recuerda **la URL con la que se construyó** y se reconstruye cuando la URL
  cambia, lo que convierte el argumento `settings` en una promesa cierta. Un servicio tiene una
  configuración para toda su vida, así que allí no cuesta nada; lo que compra es que **ningún
  llamante pueda recibir un motor apuntando a la base de datos de otro**.
- El *pool* antiguo se libera con `sync_engine.dispose(close=False)`, que es la forma que
  SQLAlchemy documenta para abandonar un *pool* desde un contexto que no puede esperar.
- `get_sessionmaker` pregunta por el motor **primero y siempre**, para no cortocircuitar esa
  decisión.

**Cuatro tests de regresión** en `tests/db/test_engine.py` lo fijan: que una URL distinta da un
motor distinto, que la fábrica no sobrevive al motor al que estaba atada, que **una URL idéntica
sigue reutilizando el mismo motor** —el singleton es el objetivo y no debía romperse— y que el
caso de URL **ausente** se comporta igual que antes, porque lo que nos mordió fue una URL
distinta y ensanchar el arreglo habría movido una frontera que nadie pidió mover.

Las dos selecciones que fallaban pasan ahora, y la suite completa va de 1303 a **1307**, y con los ajustes de credencial y modelo del §4.3 cierra en **1320**.

---

## 7. Los 19 escenarios de la HU, uno a uno

| # | Escenario | Test |
|---|---|---|
| 1 | Pieza sin pregunta recibe argumentario con sus citas | `test_a_piece_with_no_question_receives_its_argument_and_the_citations_it_used` |
| 2 | Pregunta sobre la pieza, en prosa y con cita | `test_a_question_about_the_piece_is_answered_in_prose_with_a_citation` |
| 3 | Precio y stock como placeholder, ningún campo con cifra | `test_the_generated_argument_carries_the_placeholders_and_never_a_figure` · `test_response_contains_no_literal_price_or_stock_number` |
| 4 | Cifra ausente rechazada aunque plausible | `test_figure_absent_from_context_is_rejected_even_if_plausible` · `test_a_surviving_invented_figure_drops_the_pitch` |
| 5 | Cifra pegada a moneda rechazada aunque esté en la lista blanca | `test_price_adjacent_figure_is_rejected_even_when_whitelisted` · `test_the_recorded_cause_tells_currency_adjacency_from_absence_from_the_context` |
| 6 | Cita colgante: una reparación y luego sin argumentario | `test_dangling_citation_is_never_published` · `test_dangling_citation_triggers_single_repair_then_drops_the_pitch` |
| 7 | Tramo ausente: se retira esa cita y la prosa se publica | `test_unverifiable_claim_withdraws_its_citation_not_the_pitch` · `test_unverifiable_claim_withdraws_its_citation_and_the_prose_is_served` |
| 8 | Dos puertas comparten una sola reparación | `test_two_failed_checks_share_a_single_repair` |
| 9 | Al degradar, las citas no se pierden | `test_degraded_response_keeps_the_citations_that_grounded_it` |
| 10 | El contrato distingue «no redactamos» de «se rechazó» | `test_rejected_pitch_still_reports_its_prompt_version` · `test_a_deployment_without_a_generation_client_serves_the_structured_response` |
| 11 | La consulta libre no genera y no llama | `test_free_query_mode_calls_no_provider` |
| 12 | La abstención no llama | `test_abstained_request_calls_no_provider` |
| 13 | Fallo del proveedor: 200 y nunca 5xx | `test_provider_failure_degrades_to_structure_without_prose` · `test_a_provider_failure_is_answered_with_two_hundred_and_the_structured_response` |
| 14 | El argumentario no se persiste | `test_pitch_is_not_persisted_anywhere` |
| 15 | El texto no llega a ningún log | `test_pitch_text_is_never_written_to_the_log` · `test_the_argument_is_not_written_to_any_log_by_the_http_path` |
| 16 | Prompt y constante no pueden divergir | `test_prompt_version_matches_the_loaded_prompt_file` |
| 17 | La consulta es dato y nunca instrucción | `test_prompt_injection_in_the_query_does_not_change_the_system_message` · `test_an_instruction_shaped_query_reaches_the_provider_as_delimited_data` |
| 18 | El uso de tokens se acumula sobre la reparación | `test_usage_is_accumulated_across_the_repair` · `test_the_reported_usage_is_the_sum_of_both_calls` |
| 19 | Fuera de alcance explícito | `test_out_of_scope_is_declared_and_not_quietly_performed` |

Dos tests merecen mención porque son los que C30a **no podía** escribir:

- **`test_response_contains_no_literal_price_or_stock_number`** corre sobre la respuesta completa
  y con un argumentario **no vacío**. Su equivalente de C30a corría sobre un `pitch` vacío y
  pasaba por construcción sin afirmar nada sobre la prosa.
- **`test_pitch_is_not_persisted_anywhere`** cuenta DML con un listener `before_cursor_execute`
  sobre la clase `Engine` —así ve cualquier motor creado durante la petición, incluido uno que
  la capa se construyera— y **demuestra que el contador está vivo** ejecutando un `INSERT` de
  control: una comprobación de importaciones rota daría el mismo resultado limpio que una capa
  que de verdad no escribe.

---

## 8. Lo que queda declarado y no resuelto

- **La alucinación con coartada.** Una cita válida, usada de verdad en una frase escrita de
  verdad, que aun así no dice lo que la frase afirma. Ninguna de las tres comprobaciones la caza
  y **está declarada como requisito en la capability**, con esas palabras. Se mide con RAGAS en
  **C38**; no hay juez en el camino del mostrador.
- **La atribución cruzada entre materiales que la pieza sí declara.** Heredada de C30a, mitigada
  por el tope de dos materiales y por la sección de piezas mixtas. El barrido da una pista útil
  sin resolverla: en el estrato de ≥2 materiales el contexto es mayor y la tasa de
  correspondencia peor, lo que apunta a que **estrechar el contexto ayuda**, que es lo que la
  tabla del §2.3 ya sugiere por otro camino.
- **El argumentario de la consulta libre y `clarification_question`** son de **C31**, y quedan
  escritos en su ficha en vez de sólo propuestos.
- **`2 secciones / 2 materiales` siguen siendo punto de partida, ahora con cifras al lado.** El
  barrido no recalibra: mide. Lo que muestra es que 1 sección rechaza mucho menos (12,5 % contra
  55,0 %) y publica mucha más de la cita que ofrece (85,0 % contra 42,9 %), a cambio de la mitad
  del contexto. Es una decisión de producto con datos, y este change no la toma.
- **El golden set no puede evaluar generación**: 72 consultas, 0 con ancla de pieza. La muestra
  de C30b es de donde deben salir los escenarios de C38, y así queda anotado en su ficha.

---

## 9. La trampa de máquina, resuelta y escrita

El barrido es la primera llamada real a un proveedor en mucho tiempo en este repositorio, y en
esta máquina muere con `CERTIFICATE_VERIFY_FAILED` salvo que `SSL_CERT_FILE` apunte a un PEM con
las raíces del almacén de Windows: `--system-certs` arregla a `uv`, **no al proceso Python**.
Resuelto antes de escribir el código que dependía de ello y comprobado con **una llamada real de
una sola petición**:

```python
# certifi + ssl.enum_certificates('ROOT'|'CA') SIN filtrar por bandera de confianza:
# la raíz de Norton no la lleva y el bundle sale incompleto.
SSL_CERT_FILE=REQUESTS_CA_BUNDLE=C:\Users\sergi\.jbg-ai\ca-bundle.pem   # certifi + 131 certificados
```

**Ningún test lo nota**, porque ninguno llama al proveedor: los 108 tests de la capa conducen el
cliente real sobre un `complete` guionizado.
