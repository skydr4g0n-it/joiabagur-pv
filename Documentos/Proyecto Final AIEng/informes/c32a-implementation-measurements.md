# C32a — informe de implementación: el registro de tools, y las seis cosas que la implementación refuta

**Change:** `add-sales-assistant-tool-registry` (C32a) · **Rama:** `c32a-add-sales-assistant-tool-registry`
**Fecha:** 2026-09-20 · **Historia:** [HU-AIENG-032a](../../Historias/AI-Eng/HU-AIENG-032a.md) · **Ticket:** [T-AIENG-032a](../../../openspec/changes/add-sales-assistant-tool-registry/ticket.md)
**Capability nueva:** `sales-assistant-tools` — 13 requisitos, 25 escenarios, todos `ADDED`

C32a entrega la mitad baja de C32: **seis herramientas de solo lectura, su registro con el
conjunto de nombres congelado, la validación de argumentos antes de tocar ningún puerto, los
fallos como observaciones con causa de vocabulario cerrado, la disponibilidad como etiqueta
cualitativa sin dígitos y el invariante de solo-lectura comprobado por introspección del grafo
de objetos.** No entrega el bucle, no añade ruta y `ai-service/openapi.json` no se ha movido.

Este informe recoge lo verificado contra el árbol. **Lo primero que hay que decir es que el
invariante de solo-lectura, escrito al pie de la letra, es insatisfacible con los puertos que el
propio diseño obliga a inyectar** — y que arreglarlo no requirió tocar el vocabulario de
escritura, sino decidir cómo se compara. Lo segundo es que **la trampa que el ticket anunciaba
como la más cara —ampliar `ProductSearchPort` rompe los dobles— no costó nada**, y la que sí
costó no estaba escrita en ningún artefacto.

---

## 1 · Qué se entregó

| Pieza | Fichero | Estado |
|---|---|---|
| Descriptor, observación, registro e invariante | `assist/tools.py` | **nuevo**, 845 líneas |
| Las seis tools, con puertos inyectados | `assist/tools.py` | **nuevo** |
| Vocabulario de disponibilidad (4 valores) y mapa desde `QTY_BUCKETS` | `assist/constants.py` | ampliado |
| Vocabulario de causas de fallo (4 códigos) | `assist/constants.py` | ampliado |
| `TOOL_NAMES` congelado y `WITHDRAWN_TOOL_NAMES` | `assist/constants.py` | ampliado |
| Vocabulario de métodos de escritura y de verbos HTTP | `assist/constants.py` | ampliado |
| `document_by_sku()` y `availability_bucket()` en el `Protocol` | `retrieval/ports.py` | ampliado, **nada modificado** |
| Sus dos sentencias SQL y sus dos métodos | `retrieval/search.py` | ampliado, **nada modificado** |
| Los dos métodos en el doble compartido | `tests/support/fake_product_search.py` | ampliado |
| La suite de la capability | `tests/assist/test_tools.py` | **nuevo**, 51 tests |

**Suite:** línea base **1.418 passed / 0 failed**; al cierre **1.468 passed / 0 failed**,
comparada **por nombres** y no por recuento. **50 tests nuevos, todos en `test_tools.py`, y
ningún test retirado ni renombrado**: los 1.418 nombres de la línea base están los 1.418 al
cierre, y en verde.

**Tras la verificación independiente: 1.469 passed / 0 failed.** Una prueba más —la de abstención
del §2.4— y **cero nombres desaparecidos**, comparado otra vez con `comm` sobre los *node id*. Los
cuatro hallazgos de esa pasada, con su medición y su control, están en el §11 del
[QA](../../../openspec/changes/add-sales-assistant-tool-registry/qa.md); dos de ellos —la exclusión
por categoría del §2.2 y la unicidad de `sku` del §3— eran defectos de código y no de redacción.

**La suite de `ai-service` está verde de fábrica** — 1.418 de 1.418 — y conviene decirlo porque
[CLAUDE.md](../../../CLAUDE.md) documenta líneas base **rojas** para el backend (decenas de
fallos) y para el frontend (113 de 595) y no dice nada de ésta. Aquí no hay ruido de fondo: un
rojo habría sido mío.

| Puerta | Resultado |
|---|---|
| `uv run pytest` | **1.468 passed / 0 failed**, sin proveedor, sin red y sin base de datos |
| `openspec validate --all --strict` | **58 passed / 0 failed** (misma cifra que en la línea base) |
| `ai-service/openapi.json` | **`sha256 43f70fda…68c684`, idéntico byte a byte**, verificado contra el hash guardado antes de empezar y confirmado por `git status` |
| `test_openapi_snapshot_is_stable` | **verde sin regenerar nada** |
| Comprobador de enlaces | **1.026 enlaces, 0 rotos** |

---

## 2 · Las seis refutaciones

### 2.1 · El vocabulario de escritura, leído literalmente, es insatisfacible

**Lo que decían el diseño y el ticket.** D-6, con el vocabulario entre paréntesis: *«ningún
puerto capturado por una herramienta expone método alguno del vocabulario de escritura
(`insert|update|delete|write|save|upsert|persist|sync|apply`)»*. El ticket lo repite igual.

**Lo que hay en el árbol.** `sync` aparece **dentro** de dos lecturas:

| Método | Qué hace | Coincide por |
|---|---|---|
| `ProductSearchPort.projection_synced_at()` | lee `ai.sync_checkpoint` | subcadena `sync` |
| `ProjectionFreshness.synced_at()` | cachea la lectura anterior | subcadena `sync` |

Las dos son lecturas, y la primera está **en el puerto que `consultar_disponibilidad` está
obligada a capturar**. Con comparación por subcadena, el invariante rechaza el registro que el
propio diseño manda construir: no es que fallara un caso raro, es que no hay registro posible.

**Qué se hizo.** El vocabulario **no se toca** —está en dos artefactos y es una decisión tomada—
y lo que se fija es la **regla de comparación**: se compara **token a token** contra el nombre en
`snake_case`, con igualdad exacta. `projection_synced_at` da `{projection, synced, at}`, y
`synced ≠ sync`. Sigue cazando todas las grafías naturales de una escritura —`save_profile`,
`bulk_insert`, `upsert_projection`, `delete_row`, `sync_now`, `apply_changes`— y eso está
**pinchado como comportamiento** en `test_the_write_vocabulary_catches_every_natural_spelling_of_a_write`,
que incluye los dos falsos positivos como casos negativos para que nadie los reintroduzca.

**Lo que se pierde, dicho en voz alta:** una forma flexionada (`saves`, `updated`, `syncing`) se
escaparía. No existe ninguna en el árbol, y el coste de cazarlas era volver a la subcadena que
acabamos de descartar.

### 2.2 · `Settings` tampoco pasa la comprobación, y es configuración

Medido sobre los objetos reales:

```
Settings   -> ['blank_index_sync_time_budget_is_default', 'update_forward_refs']
Cache      -> []
Freshness  -> []
```

`update_forward_refs` es el **shim deprecado de pydantic v1**, que está ahí lo quiera uno o no, y
`blank_index_sync_time_budget_is_default` es un validador. `Settings` se captura en cuatro de las
seis tools porque `retrieve_products()` y `retrieve_substitutes()` lo exigen.

**Qué se hizo.** La comprobación distingue **colaborador** de **dato inerte**, y lo hace
**estructuralmente**: se excluyen primitivos, contenedores, módulos, clases, funciones, y **dos
tipos nombrados uno a uno** — `Settings` y `ServicePrincipal`. Los dos son configuración e
identidad, ninguno hace E/S, y los dos tropiezan con el vocabulario sólo por el *shim* de
pydantic v1.

**Por qué nombrados y no por categoría, que es lo que se escribió primero y era un fallo.** La
primera versión excluía todo modelo de pydantic y toda *dataclass*, y una verificación
independiente lo midió: `InMemoryKnowledgeIndex` es una dataclass, es el puerto que
`consultar_conocimiento` captura, y **quedaba fuera de los tres ejes** sin que ninguna aserción se
pusiera roja. Peor: un puerto que escribiera, escrito como dataclass o como modelo de pydantic,
**construía el registro**. La frase que ocupaba este sitio —*«lo que queda dentro es exactamente lo
que puede alcanzar un sistema de registro»*— era falsa, y la corrección es la que la hace cierta:
**un puerto se inspecciona sea cual sea la construcción con la que esté escrito.** El registro de
la medición, con su control al lado, está en el §11.1 del [QA](../../../openspec/changes/add-sales-assistant-tool-registry/qa.md).

**Por qué esto no es la bandera `writes: bool` con otro nombre.** La exclusión vive en el módulo
del invariante y nombra **objetos concretos**, no una propiedad que la tool declare sobre sí misma
ni una categoría a la que un puerto pueda pertenecer por casualidad. Una tool no puede sacar sus
dependencias de la comprobación; para hacerlo habría que editar el fichero cuya única razón de
existir es comprobar, y añadir un nombre a esa lista se lee en el diff.

### 2.3 · Faltaba una cuarta causa de fallo, y el árbol la impone

La spec y el ticket enumeran tres situaciones: argumento inválido, referencia desconocida y
dependencia caída. El árbol obliga a una cuarta.

`_resolve_sku()` tiene que distinguir **tres** casos, que es exactamente la distinción que C26 ya
hace con `UnusableSourceProductError`: la pieza no existe, existe pero está descatalogada, o
existe e indexada sin *embedding*. Colapsar las dos últimas en `referencia_desconocida` sería
mentir —la pieza existe— y colapsarlas en `dependencia_no_disponible` también. Son **dos
movimientos distintos** para el consumidor: otra referencia, u otra pregunta sobre ésta.

El vocabulario queda en cuatro: `argumento_invalido`, `referencia_desconocida`,
**`referencia_no_utilizable`** y `dependencia_no_disponible`.

### 2.4 · `low_confidence` **no** es la abstención, y emitirlo habría dicho lo contrario de la verdad

Éste es el hallazgo que no estaba en ningún artefacto y el que más cerca estuvo de colarse.

La primera versión de `buscar_catalogo` emitía `confianza_baja: response.low_confidence`. El
propio `retrieval/orchestrator.py` avisa, en un comentario, de por qué eso está mal:

> *«An empty `results` is also what a query that simply found nothing produces, and the one field
> that does move with an abstention — `low_confidence` — carries a DIFFERENT, measured meaning
> (cross-branch consensus: 1 of 20 out-of-domain against 10 of 43 answerable). A caller reading
> it as abstention would report the opposite of the truth on the judged set.»*

Es decir: sobre el conjunto juzgado, `low_confidence` se mueve **al revés** de lo que un lector
ingenuo esperaría. Y la abstención **sí** vacía la lista de candidatos, así que una observación
con cero candidatos y `confianza_baja: true` es exactamente la confusión contra la que C30a creó
la costura `on_abstention`.

**Qué se hizo.** La tool usa esa costura —igual que `assist_sale`— y emite **`abstenido`**, que
es la señal que un bucle puede usar para decidir si reformula o concluye que no hay nada.
`low_confidence` **no se reexporta bajo ningún nombre**, y
`test_the_catalogue_search_reports_abstention_and_not_the_consensus_flag` lo pincha.

**Y la prueba que faltaba, que es la que hace que esto no sea circular.** Ese test conducía sólo
el caso respondible: afirmaba que `abstenido` estaba y era un booleano, y que el otro campo no
estaba. **Todas esas aserciones habrían pasado sobre un `"abstenido": False` cableado a mano** —
que es, literalmente, el modo de fallo que dejó colarse `low_confidence` la primera vez. Una
verificación independiente lo señaló y se cerró con
`test_the_catalogue_search_reports_an_abstention_when_the_retriever_abstains`, que construye un
mundo de perfil de distancias plano —la forma sobre la que abstiene la regla relativa de C25— y
afirma `content["abstenido"] is True` con la lista de candidatos vacía. Las dos direcciones, ahora
sí, son `True` y `False` y no «está» y «no está».

### 2.5 · La ampliación del `Protocol` **no** rompió los dobles, y la razón importa

El ticket, el diseño y las instrucciones de la sesión anunciaban esto como trabajo previsto:
*«los fakes existentes dejan de satisfacerlo hasta ampliarlos»*.

**No ocurrió.** `ProductSearchPort` es un `typing.Protocol` sin `@runtime_checkable` y nada hace
`isinstance` contra él, así que ampliarlo **no rompe nada en tiempo de ejecución**; sólo rompería
una comprobación estática, y este repositorio **no tiene `mypy` en las dependencias de desarrollo
ni un workflow de CI para `ai-service`**. Verificado: `pyproject.toml` declara `pytest` y
`testcontainers` y nada más, y `.github/workflows/` contiene backend y frontend únicamente.

`FakeProductSearch` se amplió igualmente, y sigue siendo la tarea 3.5 — pero por otro motivo, que
es el que había que escribir: **sin los dos métodos, las tools no tienen contra qué correr**. La
ampliación es necesaria porque la suite los **llama**, no porque un `Protocol` la rechace. Un
lector que confíe en la formulación del ticket buscará un error de tipos que no existe.

Hay un corolario que conviene dejar dicho: **nada en esta suite protege el `Protocol`**. Una
implementación futura que olvide uno de los dos métodos fallará en tiempo de ejecución, donde se
use, y no en la construcción.

### 2.6 · Una pieza sin familia no es un fallo, y una tool no puede capturar nada

Dos huecos menores que los artefactos no cubrían y que hubo que decidir.

**`listar_familia` sobre una pieza sin familia.** `family_id` es nulable, y ninguna spec dice qué
pasa. Devolver un fallo sería falso —la pregunta tiene respuesta— así que devuelve una
observación correcta con `familia: null` y `miembros: []`. El siguiente movimiento del consumidor
es dejar de preguntar, y una lista vacía lo dice.

**`pedir_aclaracion` no captura ningún colaborador.** Resuelve una plantilla de un catálogo
cerrado con funciones de módulo, así que los tres ejes del invariante se ejecutan **sobre una
lista vacía** y pasan **vacuamente**. No es un fallo —esa tool no puede escribir precisamente
porque no tiene con qué— pero sí es un límite de una comprobación por introspección que conviene
que esté escrito. `test_the_read_only_check_reaches_every_port_the_registry_was_handed` fija qué
puertos se ve capturar a cada tool, para que las dos aserciones del invariante no puedan quedar
verdes sobre la nada.

---

## 3 · Decisiones tomadas donde los artefactos callaban

Ninguna de éstas contradice nada escrito; son huecos que hubo que rellenar.

| # | Hueco | Decisión | Por qué |
|---|---|---|---|
| 1 | Idioma de los códigos de causa | **Castellano** (`argumento_invalido`…) | El ticket pide *«el mismo patrón que los códigos de aviso de C30a»*, y el patrón es *código y no prosa*, no el idioma. Sus vecinos en el mismo fichero —nombres de tool, descripciones, etiquetas de disponibilidad— son castellano, y mezclar `sin_ambito` con `unknown_reference` sería leer dos vocabularios donde hay uno. **Es una desviación de C30a en idioma**, cuyos códigos son ingleses |
| 2 | Tipo de retorno de la lectura por SKU | **`SourceDocument`**, reutilizado | Es la misma pregunta que `source_document()` sobre la misma tabla: *¿hay fila, y sirve?* Un tipo nuevo habría duplicado diez campos para no añadir ninguno |
| 3 | Un `pos_id` del token que no parsea | **`sin_ambito`** y traza en el log | Es la respuesta **más estrecha** disponible y no revela nada; inventar ausencia dispararía el pivote a sustitutos sobre una pieza que la tienda puede vender. El fallo sobrevive en el log y no en la observación |
| 4 | Dónde se ata el principal | **En `build_registry`**, no en `invoke` | El ámbito de lectura es del token, como en todo `/v1`; pasarlo por llamada lo convertiría en un argumento que el llamante elige. Construir un registro por petición no cuesta E/S |
| 5 | Validación de argumentos | **Modelos de pydantic** con `extra="forbid"` | Dependencia ya usada; el esquema se **deriva** del modelo, así que una cota declarada y una cota publicada no pueden discrepar. `extra="forbid"` hace que un parámetro inventado sea una llamada rechazada y no una ignorada en silencio |
| 6 | Profundidad de la introspección | **Lo que la tool recibe**, sin recorrer atributos | Recorrer atributos convierte la comprobación en un barrido del proceso entero: `Settings` sola arrastra toda la configuración. Está declarado en el docstring qué caza y qué no |
| 7 | Un SKU que devolviera dos filas | **`one_or_none()`**, que lanza | *Corregido tras la verificación independiente.* `sku` **no es único en el esquema `ai`**: no hay restricción única ni índice alguno sobre esa columna en ninguna migración, y la unicidad la impone .NET sobre su propia tabla (`ProductConfiguration`: `HasIndex(p => p.SKU).IsUnique()`). No es un olvido de aquella migración sino una decisión archivada: el ticket de `add-pgvector-schema-foundation` pregunta por ese índice y responde *«no se crea; la unicidad es del corpus»*. El comentario, por tanto, **contradecía una decisión tomada** para justificar el `first()`. El `first()` original devolvía ante un duplicado **una fila arbitraria de un resultado sin `ORDER BY`** —una pieza distinta en llamadas distintas, por la puerta que resuelven cuatro de las seis tools— que es justo lo que el comentario decía querer evitar. `one_or_none()` lanza `MultipleResultsFound`, que llega al llamante como `dependencia_no_disponible` con el mensaje real: un feed roto se lee como roto |

---

## 4 · La disponibilidad, que era la única tool sin servicio detrás

Resuelta como fija D-1: **desde `ai.pos_projection` y no desde .NET**, difiriendo con motivo la
decisión que el §6.1 del diseño llevaba abierta desde agosto. El endpoint .NET queda
**identificado, acotado y no hecho**, con su ficha en
[`openspec/DEFERRED_TASKS.md`](../../../openspec/DEFERRED_TASKS.md).

```
QTY_BUCKETS del feed          →  etiqueta cualitativa (vocabulario cerrado, SIN dígitos)
    "0"                       →  sin_existencias
    "1-2"                     →  ultimas_unidades
    "3+"                      →  disponible
    fila ausente / sin pos_id →  sin_ambito        ← NO es "agotado"
```

Tres cosas que la implementación fija y conviene que consten:

**El mapa se escribe con las claves a mano, y no se importa `QTY_BUCKETS`.** `assist/constants.py`
declara en su docstring que **no importa nada en absoluto**, y ésa es la propiedad que permite que
todo lo demás lea de él sin ciclo. La duplicación no se pierde, se **mueve a donde puede fallar a
gritos**: `test_every_bucket_the_feed_can_store_has_a_label` compara las claves contra
`QTY_BUCKETS` mismo, así que un cuarto bucket rompe un test en vez de caer en silencio a «sin
ámbito».

**`sin_ambito` no es valor de ese mapa.** Nunca se deriva de un bucket, sólo de la ausencia de
uno, y hay una aserción dedicada a ello.

**La lectura es por pieza y nunca `scope_buckets()`.** `test_the_availability_tool_reads_one_piece_and_never_the_whole_assortment`
comprueba que se llama exactamente una vez con `(product_id, pos_id)`.

---

## 5 · El contrato, verificado y no supuesto

| Comprobación | Resultado |
|---|---|
| `sha256` guardado **antes** de empezar | `43f70fdadd2bd9aa90068d3e74ec2ee25c8d3b3b530f6d33907b1e73d068c684` |
| `sha256` al cierre | **idéntico** |
| `sha256sum -c` | `ai-service/openapi.json: OK` |
| `git status ai-service/openapi.json` | **vacío** |
| `test_openapi_snapshot_is_stable` | verde, **sin regenerar** |
| Ruta `/v1/assist/agent` en el documento generado | **ausente**, pinchado por test |
| Campos de `AssistResponse` | **los once que dejó C31**, pinchados como conjunto |

`assist/tools.py` **no lo importa nadie desde `jbg_ai.api`**, que es lo que hace que la ausencia
de contrato sea estructural y no una promesa.

---

## 6 · Trazabilidad de los nueve escenarios de la HU

Todos en [`ai-service/tests/assist/test_tools.py`](../../../ai-service/tests/assist/test_tools.py)
salvo donde se indica.

| # | Escenario de la HU | Test |
|---|---|---|
| **1** | El registro contiene exactamente las seis herramientas | `test_the_registry_holds_exactly_the_six_frozen_tools` |
| | …cada entrada publica esquema y descripción | `test_every_registered_tool_publishes_a_schema_and_a_spanish_description` |
| | …una séptima se rechaza | `test_a_tool_outside_the_frozen_set_is_refused_at_construction` · `test_a_registry_missing_one_of_the_six_is_refused_at_construction` |
| **2** | Ninguna herramienta registrada puede escribir | `test_no_collaborator_captured_by_a_tool_exposes_a_write_method` |
| | …ningún cliente HTTP emite otro verbo que `GET` | `test_no_collaborator_captured_by_a_tool_can_issue_a_write_http_verb` |
| | …la comprobación **falla** aunque el descriptor diga lo contrario | `test_a_tool_capturing_a_writing_port_is_refused_however_it_describes_itself` |
| | *(anti-vacuidad y regla de comparación)* | `test_the_read_only_check_reaches_every_port_the_registry_was_handed` · `test_the_write_vocabulary_catches_every_natural_spelling_of_a_write` |
| | *(que el puerto de conocimiento entre en el barrido — §2.2)* | `test_the_read_only_check_reaches_every_port_the_registry_was_handed`, que nombra `InMemoryKnowledgeIndex` |
| **3** | Un fallo de dependencia vuelve como observación | `test_a_dependency_failure_comes_back_as_a_failed_observation_and_not_an_exception` |
| | …con causa de vocabulario cerrado | `test_a_failure_cause_is_always_a_code_of_the_closed_vocabulary` · `test_an_unknown_tool_name_is_an_observation_and_not_an_exception` |
| **4** | Disponibilidad con etiqueta del vocabulario cerrado | `test_availability_answers_with_the_label_of_the_stored_bucket` |
| | …la etiqueta no contiene ningún dígito | `test_no_availability_label_contains_a_digit` |
| | …ninguna cantidad aparece en la observación | `test_the_availability_observation_carries_no_stock_quantity_anywhere` |
| | …declara la antigüedad de la proyección | `test_the_availability_observation_declares_the_age_of_the_projection` · `test_a_stale_projection_still_answers_and_carries_its_age` |
| | *(cobertura del mapa)* | `test_every_bucket_the_feed_can_store_has_a_label` |
| **5** | Sin punto de venta, «sin ámbito» y no «agotado» | `test_a_principal_with_no_point_of_sale_gets_the_unscoped_value` |
| | …y se distingue de una pieza realmente agotada | `test_a_piece_the_point_of_sale_does_not_carry_is_not_reported_as_out_of_stock` |
| **6** | La repregunta es determinista y sale del catálogo | `test_the_same_axis_always_produces_the_same_question` |
| | …un eje fuera del enum se rechaza **antes** de ejecutar | `test_an_axis_outside_the_closed_set_is_rejected_before_execution` |
| | *(el enum publicado es el catálogo de C31)* | `test_the_clarification_schema_publishes_the_axes_of_the_closed_catalogue` |
| **7** | Las tools se direccionan por SKU | `test_a_piece_anchored_tool_resolves_the_piece_from_its_sku` |
| | …una referencia desconocida es observación fallida | `test_an_unknown_sku_is_a_failed_observation_with_its_cause` · `test_a_discontinued_piece_is_told_apart_from_an_unknown_one` |
| | …ningún esquema acepta identificador interno | `test_no_tool_schema_declares_an_internal_product_identifier` |
| **8** | Todas completan sin credencial de proveedor | `test_every_tool_produces_its_observation_with_no_chat_provider_configured` |
| | …ninguna llama a un proveedor de chat | `test_no_tool_calls_a_chat_provider` |
| | …los *embeddings* se cuentan aparte de `usage.calls` | `test_embedding_calls_are_counted_in_a_counter_of_their_own` · `test_the_assistance_layer_provider_call_figure_is_untouched_by_this_capability` |
| **9** | No hay bucle ni presupuesto de vueltas, ni ruta nueva | `test_the_registry_publishes_no_route_and_declares_no_iteration_budget` |
| | …`POST /v1/assist/sale` idéntico | `test_the_sale_assistance_response_shape_is_the_one_the_router_change_left` |
| | …`openapi.json` byte a byte igual | `tests/api/test_openapi_snapshot.py::test_openapi_snapshot_is_stable` *(preexistente, verde sin regenerar)* |

---

## 7 · Lo que NO se hizo, y por qué

1. **El bucle, sus tres presupuestos, `partial: true`, `POST /v1/assist/agent` y la transcripción
   multi-turno.** Son **C32b** por el corte del 2026-09-20, y no se ha escrito ni una vuelta.
2. **El endpoint .NET de disponibilidad puntual.** Identificado, acotado y **no hecho**, con su
   motivo y lo que hará falta en [`DEFERRED_TASKS.md`](../../../openspec/DEFERRED_TASKS.md). La
   tool está diseñada para que sea un reemplazo directo — y con una advertencia que conviene
   repetir: **un cliente HTTP de propósito general no pasará el tercer eje del invariante**,
   porque expone `post`, `put`, `patch` y `delete`. Habrá que envolverlo en una superficie de
   sólo lectura, que es precisamente la restricción que se quería dejar puesta.
3. **Iterar las descripciones de las tools contra un modelo real.** Esta mitad no llama a
   ninguno. Son *prompts*, y un *prompt* se itera con medición: eso ocurre en C32b.
4. **Medir si la granularidad de seis es la correcta.** Limitación estructural del corte, no
   descuido. Los puertos quedan inyectados para que C32b pueda reagrupar sin tocarlos.
5. **Proteger el `Protocol` con una comprobación estática.** Añadir `mypy` es un cambio de la
   puerta de calidad del repositorio y no cabe en un change de esta zona. Queda dicho en §2.5.

---

## 8 · Limitaciones que se declaran y no se cierran

1. **La disponibilidad la sirve una proyección que puede desfasarse minutos.** La autoridad sobre
   el stock sigue siendo de .NET (§6.2). Por eso la observación declara su frescura, **degrada y
   nunca elimina**.
2. **Las descripciones de las tools no se han medido contra un modelo.** Ver §7.3.
3. **El invariante de solo-lectura caza lo que puede cazar**, y los cuatro límites están en el
   docstring del módulo, en §2.6 y en el §9.6 del QA:
   - **No recorre atributos** de un colaborador, así que un puerto escondido dentro de otro objeto
     se le escaparía — y quien esté dispuesto a esconder una escritura tiene caminos más fáciles.
   - **Sólo ve lo que el ejecutor cierra.** Una función de módulo que alcanzara un puerto por
     búsqueda global no tiene celda de cierre y pasaría los tres ejes sobre una lista vacía. Hoy es
     inocuo —las seis son *closures* anidadas en `build_registry`, la única costura de
     construcción— y es la razón de que una tool futura deba construirse igual.
   - **Sobre `pedir_aclaracion` pasa vacuamente**, porque esa tool no captura nada.
   - **El vocabulario de escritura no es exhaustivo.** Y el hueco no es una flexión sino un verbo
     que la lista nunca tuvo: `SqlAlchemyPosProjection.put_checkpoint()` es un `INSERT … ON
     CONFLICT DO UPDATE` de este repositorio y no casa nada, **ni por token ni por subcadena**, así
     que no es la regla de comparación del §2.1 la que lo pierde. Con él se pierde su familia:
     `put_`, `store_`, `record_`, `commit`, `flush`. Ensancharla es una decisión de D-6, no un
     parche; lo que no se puede es leer el conjunto como si fuera exhaustivo. **Es un suelo bajo el
     grafo de objetos, no una demostración de que ningún método escribe.**
4. **`style_similarity` sigue en cero para 403 de 404 productos reales** (C26), así que las
   observaciones de `buscar_sustitutos` heredan esa limitación ya declarada. No es de aquí.
5. **El recuento de seis no es lo que el PF evalúa.** Lo evaluable son el bucle, el presupuesto
   duro, el invariante de solo-lectura y el `partial: true`. De los cuatro, este change entrega
   **uno**.
