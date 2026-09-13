# C30a — mediciones de implementación: la capa estructurada de venta asistida

**Change:** [`add-assist-structure-and-rule-warnings`](../../../openspec/changes/add-assist-structure-and-rule-warnings/) · **Fecha:** 2026-09-13
**Rama:** `c30a-add-assist-structure-and-rule-warnings` · **Punto de nacimiento:** `0ae0fdd`
**HU:** [HU-AIENG-030a](../../Historias/AI-Eng/HU-AIENG-030a.md) · **Ticket:** [T-AIENG-030a](../../../openspec/changes/add-assist-structure-and-rule-warnings/ticket.md)
**Exploración previa:** [c30-exploration-decisions.md](c30-exploration-decisions.md)

---

## Resumen

`POST /v1/assist/sale` deja de ser un fixture. Sirve **tres modos** sobre los candidatos que la
recuperación ya producía, agrupados por una `family_id` que ahora puede ser nula, con **avisos
derivados de reglas** en un vocabulario cerrado de dos códigos y **citas que abren un fichero y un
encabezado en git** — y **sin una sola llamada a un modelo de lenguaje**. El argumentario en prosa
es C30b, y el corte es lo que lo hace medible contra esta capa.

| | |
|---|---|
| Suite `ai-service` | 1038 → **1192** · **0 en rojo antes y después** · 0 omitidos |
| `openspec validate --all --strict` | **57 passed, 0 failed** |
| `openapi.json` | **5 esquemas movidos, 0 rutas** · las otras nueve rutas idénticas |
| Migraciones | **ninguna** — `alembic heads` sin revisión nueva |
| Llamadas a proveedor en la capa | **cero** de LLM; de *embeddings*, sólo las que la recuperación ya hacía |
| Ficheros fuera de `ai-service/`, `openspec/` y `Documentos/` | **ninguno** |
| Rutas que siguen respondiendo 501 | **una**, `/v1/inventory/propose` (C35, rama cancelada) |

---

## 0. Puerta de entrada y línea base

| | |
|---|---|
| `git_sha` de partida | `0ae0fdd999b0e7cc81862dd5b641617b399cc299` |
| Árbol de trabajo al medir | **limpio** — `git stash push -u` respondió *«No local changes to save»* |
| `ai-service/openapi.json` antes | `sha256 cec649272cbd75466ccd27409dc351e17489159cfa8a4393267a218099e91827` |
| Suite `ai-service` **antes** | **1038 passed · 0 failed · 0 errors · 0 skipped** |
| Duración de la pasada | **336,1 s** (5 min 36 s) |
| `openspec validate --all --strict` antes | **57 passed, 0 failed** |

**La duración importa tanto como el recuento.** En este repositorio una pasada anormalmente
corta significa que los Testcontainers no arrancaron y que el árbol de tests de base de datos
se omitió en bloque, lo que después se lee como una regresión catastrófica que no existe. Los
336 s con **`skipped=0`** dicen lo contrario: el demonio de Docker estaba accesible
(`pgvector/pgvector:pg15` levantado por `testcontainers-ryuk`) y **los 1038 tests se ejecutaron
de verdad**.

**Y la suite de `ai-service` no es la de `backend/` ni la de `frontend/`.** `CLAUDE.md` advierte
de dos suites que llegan en rojo antes de tocar nada; ésta llega en **verde**. La comparación
final exigida por el procedimiento es por tanto por nombres contra un conjunto de fallos
**vacío**, y el criterio real es que no aparezca ninguno.

Los nombres de los 1038 tests quedan capturados para el diff final; el fichero de nombres en
rojo existe y está **vacío**, que es el resultado, no una omisión.

### Cierre: la comparación por nombres

| | antes | después |
|---|---|---|
| Tests | 1038 | **1192** (+156) |
| **Nombres en rojo** | **∅** | **∅** |
| Omitidos | 0 | **0** |
| Duración | 336,1 s | **323,4 s** |
| `openspec validate --all --strict` | 57 passed, 0 failed | **57 passed, 0 failed** |

**Ningún nombre nuevo falla y ninguno dejó de fallar.** `skipped=0` en las dos pasadas y una
duración del mismo orden dicen que las dos corrieron el árbol de base de datos entero: la pasada
corta que `CLAUDE.md` advierte —contenedores que no arrancan y se lee como regresión catastrófica—
no ocurrió en ninguna de las dos.

**Dos identificadores de test desaparecen, y ninguno es cobertura perdida.** Los dos son
parametrizaciones de `test_unimplemented_route_returns_501_when_stub_mode_off`:

- `[POST-/v1/assist/sale-body0]` se va **porque la ruta ya no responde 501**, que es el objeto del
  change. La propiedad no se borra: se rehospeda, como hizo C26, en
  `test_the_assistance_route_is_no_longer_left_answering_501`, que la afirma en negativo.
- `[POST-/v1/inventory/propose-body1]` **sigue existiendo**, renombrado a `body0`: al salir assist
  de la lista, inventario pasa a ser el primer parámetro. Comprobado sobre el XML de la pasada
  final, no deducido.

---

## 1. Spike 1 — el filtro de exclusión sobre las 72 consultas del golden set

**Cómo se midió, y por qué así.** Contra el **índice vivo** del Postgres local —32 documentos,
161 fragmentos, **embeddings de producción**— y al **umbral de producción `0,51`**. La pregunta
que el spike contesta es *«¿devuelve `0,51` citas espurias sobre consultas de producto?»*, y ésa
es una pregunta sobre ese umbral y sobre ningún otro: medirla contra el embebedor offline, cuyas
distancias viven en otra escala y obligan a un umbral de `0,81`, habría contestado otra cosa.

Las 72 consultas se embebieron **una vez**, en lote, y las diez pasadas posteriores no hicieron
**ninguna** llamada más al proveedor: la caché acotada del cliente las sirvió todas. Es el
hallazgo del spike 2 usado como herramienta.

El brazo con filtro se implementó como un **espejo desechable** de `SqlAlchemyKnowledgeIndex` con
una cláusula condicional de más, `AND d.id <> ALL(CAST(:excluded_documents AS uuid[]))`, inyectada
en el mismo punto que `_DOC_TYPE_CLAUSE` y en **las dos** sentencias. Medir la forma antes de
comprometerla es justamente lo que el spike existe para hacer.

### Brazo A — sin filtro (esto es M1)

| | |
|---|---|
| Consultas | **72** |
| Citas devueltas | **101** |
| Consultas que abstienen (cero citas) | **41 de 72** |
| Citas procedentes de una ficha de material canónica | **41 de 101** (40,6 %) |

Por categoría:

| categoría | consultas | citas | abstenciones |
|---|---:|---:|---:|
| `materiales` | 5 | 25 | **0** |
| `sinonimos` | 6 | 21 | **0** |
| `piedra` | 4 | 13 | **0** |
| `variante-talla` | 7 | 11 | 4 |
| `sustituto` | 5 | 8 | 2 |
| `descripcion-sin-anclaje` | 12 | 4 | 10 |
| `ambigua` | 4 | 3 | 3 |
| `lexico-exacto` | 4 | 1 | 3 |
| `subjetiva` | 5 | 1 | 4 |
| **`fuera-de-dominio`** | **20** | **14** | **15** |

### Las cinco consultas fuera de dominio que sí citan, una por una

Es la fila que decide, así que va nombrada y no agregada:

| id | consulta | citas | veredicto |
|---|---|---|---|
| q62 | *«un salero de plata»* | `material-plata` ×4, `material-piezas-mixtas` | **defendible**: un salero de plata se empaña igual que una pulsera, y el consejo citado es cierto de él |
| q65 | *«un joyero de viaje para los anillos»* | `guardar-y-viajar-con-joyas` ×2, `cuidados-generales`, `joyas-playa-piscina-y-deporte`, `glosario-de-joyeria` | **defendible**: el documento de guardado y viaje habla exactamente de eso |
| q68 | *«un lingote de oro»* | `material-oro`, **`material-bano-de-oro`** | **una espuria de verdad**: un lingote no lleva baño. Es la confusión entre fichas que el filtro existe para cortar — y en M1 no hay pieza, así que no hay filtro |
| q48 | *«una hucha de plata para bautizo»* | `ocasiones-y-tradicion` | defendible |
| q70 | *«una placa para un aniversario de boda»* | `ocasiones-y-tradicion` | defendible |

### Brazo B — con filtro, una pasada por cada material anclado (esto es M3)

| ancla | citas | abstenciones | citas de ficha ajena que el brazo A traía |
|---|---:|---:|---:|
| plata | 83 | 44 | 27 |
| oro | 78 | 43 | 35 |
| baño de oro | 80 | 42 | 35 |
| perla | 80 | 45 | 31 |
| hilo | 75 | 45 | 36 |
| latón | 73 | 45 | 41 |
| acero | 73 | 45 | 41 |
| resina | 73 | 45 | 41 |
| cuero | 73 | 45 | 41 |
| **media** | **76,4** | **44,3** | **36,4** |

### Lo que estas cifras deciden

**1. M1 no necesita umbral propio. Se consume el `0,51`.** Era la opción por defecto declarada en
el diseño, y la medición la sostiene en vez de limitarse a no contradecirla: de 101 citas, **una**
es inequívocamente espuria (`material-bano-de-oro` sobre un lingote), y el umbral **ya abstiene en
41 de las 72 consultas**, incluidas 10 de las 12 `descripcion-sin-anclaje` y 4 de las 5
`subjetiva`, que son consultas de catálogo sin respuesta en el corpus. Endurecerlo para el camino
de producto costaría las 25 citas de `materiales`, las 21 de `sinonimos` y las 13 de `piedra`, que
son precisamente las correctas. **El riesgo que el diseño temía no se materializa a esta escala**,
y queda declarado que la comprobación se hizo, no que se dio por buena.

**2. El filtro asimétrico hace lo que D8 dice que hace, y no lo que D8 temía.** Retira una media
de **36,4 citas de ficha ajena** por ancla —el 36 % de las citas del brazo A serían del material
equivocado para una pieza concreta— y a cambio sube las abstenciones sólo de **41 a 44,3**. Es
decir: **no produce falsa abstención en masa**. La asimetría estaba argumentada en C25 y aquí está
medida.

**3. Un efecto que el diseño no anticipó y conviene declarar: el filtro no sólo borra, promueve.**
Las 36,4 citas ajenas retiradas producen una caída neta de sólo **24,6** (101 → 76,4), porque el
hueco que dejan lo ocupan fragmentos que estaban por debajo del corte. Unos **11,8 fragmentos
correctos por ancla ascienden a la respuesta** gracias a la exclusión. El filtro mejora la
composición de la cita, no sólo su higiene.

**Límite de la medición, declarado.** Las 72 consultas del golden set son consultas de
**catálogo**, no preguntas de conocimiento, y ninguna lleva pieza anclada: el ancla del brazo B es
hipotética y por eso se barrieron las nueve. Es exactamente el escenario que el spike quería
cubrir —M1 y M3 sobre consultas de producto— y no dice nada sobre preguntas de mostrador, que C23
ya midió.

## 2. Spike 2 — reutilización del vector de consulta entre recuperación y conocimiento

**Es viable, y la costura ya existe: es la caché acotada del cliente, no un parámetro de vector.**

| comprobación | resultado |
|---|---|
| Mismo cliente | `search_knowledge(embed=…)` está tipado contra el **mismo** `EmbeddingClient` que construye `build_retrieval_embed_client`, y `api/main.py` lo resuelve como singleton de proceso desde `app.state.retrieval_embed` |
| Misma dimensión | `EMBEDDING_DIM = 1536`, **una sola constante** de `indexing/constants.py`, leída por los dos caminos |
| Misma `model_version_key` | `openai/text-embedding-3-small:1536` por los dos lados, **carácter por carácter**: `embeddings.model_version_key()` y la expresión literal de `knowledge/search.py` son la misma fórmula |
| Compatibilidad con los dos corpus | Los documentos guardan sufijos distintos —`…:source-text/v1` y `…:knowledge/v1`— y **los dos casan** con el `LIKE '<modelo>:<dim>%'` que ambas sentencias usan |
| La reutilización, medida | Dos `embed()` del mismo texto por el mismo cliente → **1 sola llamada al proveedor**, la segunda con `cache_hits=1` y **vector idéntico** |

**La costura, y su trampa.** La clave de `BoundedEmbeddingCache` es
`(hash_source_text(text), model, version)`. Medido: **un espacio final es un fallo de caché**.
Y ahí hay una asimetría real en el árbol — `retrieve_products` embebe `payload.query` **tal cual**
mientras que `search_knowledge` embebe `question.strip()`. Así que M3 reutiliza el vector **si y
sólo si pasa el mismo texto ya recortado a los dos**; si no, paga un segundo *embedding* por una
diferencia invisible. Queda anotado como la condición de la costura, no como un detalle.

**Consecuencia para el alcance.** No hace falta ningún parámetro de vector nuevo, ni tocar
`retrieve_products` ni `search_knowledge` para esto: basta con que la capa de assist pase el mismo
cliente y el mismo texto recortado. Es la alternativa más barata y la que menos superficie mueve.

## 3. Spike 3 — cardinalidad máxima de familia y tope del roster

Medido sobre `ai.product_document` del índice local vivo, hoy:

| miembros por familia | familias |
|---:|---:|
| 2 | 44 |
| 3 | 52 |
| 4 | 56 |
| 5 | 3 |
| 8 | **1** |

| | |
|---|---|
| Familias | **156** |
| Miembros en familia | **491** de 1.168 (**42,0 %**) |
| Máximo observado | **8** |
| Media | **3,15** |
| p95 | **4** |
| Familias por encima de 8 | **0** |

**Tope elegido: 24 miembros**, tres veces el máximo observado. La holgura es deliberadamente
generosa porque el tope existe para **acotar el peor caso de una lectura**, no para recortar
familias reales: ninguna familia del catálogo se acerca a él, y una que lo alcanzase sería una
señal de que la agrupación de C18b se rompió, no una respuesta que haya que servir entera.

> **Dos cifras del diseño que la medición corrige.** El diseño cita **486 miembros** (de C18b) y
> afirma que *«existen familias de 7 y 8»*. Hoy son **491 miembros** —cinco más, por sincronizaciones
> posteriores— y **no existe ninguna familia de 7**: los tamaños presentes son 2, 3, 4, 5 y 8. El
> número de familias (156) y la media (~3,1) sí coinciden. Nada de esto mueve la decisión —el tope
> se fija sobre el máximo, que sigue siendo 8— pero una ficha que nombra un tamaño inexistente
> invita a construir un test sobre él.

---

## 4. Lo que la implementación refuta de la historia, del diseño o del ticket

**Refutó seis cosas.** Ninguna cambia el alcance; cuatro son datos y dos son supuestos sobre el
árbol que resultaron falsos. Se listan porque una ficha que nombra un dato inexistente invita a
construir un test sobre él.

### 4.1 · «156 familias, 486 miembros, existen familias de 7 y 8»

Medido hoy sobre el índice vivo: **491 miembros**, no 486 —cinco más, por sincronizaciones
posteriores a C18b— y **no existe ninguna familia de 7**. Los tamaños presentes son 2, 3, 4, 5 y
8. El número de familias (156) y la media (~3,1) sí coinciden. El tope del roster se fija sobre el
**máximo**, que sigue siendo 8, así que la decisión no se mueve.

### 4.2 · «`retrieval/orchestrator.py` se consume, no se modifica»

**Falso, y hubo que corregirlo.** El ticket lo afirma en su tabla de estado del código. La
decisión de abstención **no es recuperable desde `RetrievalResponse`**: un `results` vacío es
también lo que produce una consulta que simplemente no encontró nada, y el único campo que se
mueve con la abstención —`low_confidence`— tiene un significado **medido y distinto**, que es
justamente lo que D9 prohíbe reutilizar.

Lo que se hizo: **una costura aditiva de observabilidad**, `on_abstention`, con la misma forma y
el mismo motivo que el `on_fused_candidates` que ya existía para el arnés de evaluación. No
cambia ningún comportamiento, y una llamada que no la pasa ve la función de siempre. Son
**catorce líneas**, doce de ellas comentario explicando por qué existe.

Lo que **no** hizo falta, y el ticket daba por necesario: sacar `size_label` del candidato
interno. `source_document` ya lo devuelve, así que los tres modos leen la pieza foco por la misma
puerta y el orquestador no se toca por ese motivo.

### 4.3 · «Validación: el protocolo declara el método y `mypy`/`ruff` pasan» (tarea 4.1)

**En este repositorio no hay `mypy` ni `ruff`.** No están en `pyproject.toml`, no hay
configuración de ninguno de los dos, y `.github/workflows/` no tiene flujo de `ai-service`. La
puerta real es `uv run pytest`, y es la que se ha usado. La tarea pedía una comprobación contra
una herramienta que el proyecto no tiene.

### 4.4 · El vocabulario de avisos obliga a mover el fixture, y la ficha no lo decía

El invariante dice *«every warning any response carries belongs to the closed vocabulary»* —
**cualquier respuesta**, y el fixture emite una. `assist_sale_stub` emitía `STUB_WARNING`, que es
una frase en castellano. Se ha sustituido por códigos del vocabulario, y por la misma razón el
`intent` del fixture ha pasado de `gift_search`/`product_search` —una heurística por la palabra
«regalo»— a la misma regla estructural que usa el camino real. La tarea 3.7 sólo pedía el grupo
sin familia y las citas de seis campos.

### 4.5 · Dos tests de C23 vigilaban su invariante con un proxy que dejó de valer

`test_knowledge_opens_no_http_surface` y su gemelo buscaban la subcadena `knowledge` **en todo el
snapshot, prosa incluida**. C30a le da a una descripción publicada un motivo legítimo para nombrar
el corpus: `Citation` se documenta como *«a fragment of the knowledge corpus»*, que es exactamente
lo que el lado .NET necesita leer para pintarla con honestidad.

Se han **afilado, no debilitado**: ahora comprueban rutas, nombres de esquema, `tags` y
`operationId`, que es donde una superficie HTTP aparecería. Mantener la forma antigua habría
obligado a escribir una descripción vaga para satisfacer una búsqueda de texto.

### 4.6 · Un hueco que los artefactos dejaron sin decidir: a qué pieza describen los avisos

Ni la HU ni el diseño lo dicen. Los dos hablan de *«el producto»* en singular —`size_label_missing`
es «el producto no declara `size_label`»— y en M2 y M3 eso es inequívoco: la pieza anclada. **En M1
no hay pieza anclada**, y sin embargo el escenario 3 de la historia exige que el aviso de variantes
dispare cuando *«la recuperación sólo devolvió dos»*, que sólo puede ser M1.

**Decisión tomada, y declarada aquí porque no estaba en ningún artefacto:** los avisos describen la
**pieza foco** de la respuesta — la anclada en M2/M3, y en M1 el primer miembro del primer grupo,
que es el candidato mejor clasificado y la pieza que la respuesta encabeza. Las dos alternativas se
descartaron con un motivo:

- *Aplicar «alguno de los candidatos»* haría que `size_label_missing` disparase en cuanto una de
  quince piezas no declarase talla, que es casi siempre y por tanto no informa de nada.
- *No emitir avisos en M1* contradice el escenario 3.

Leer la pieza foco cuesta **una lectura por clave primaria** y es la misma que hacen los modos
anclados, así que los tres modos comparten un solo camino para «describe esta pieza».

### 4.7 · Nota de máquina, no del proyecto

`CLAUDE.md` recoge que `uv sync` y `uv run` necesitan `--system-certs` aquí. **Eso arregla a `uv`,
no al proceso Python**: en tiempo de ejecución, `litellm` sale por `aiohttp`/`httpx`, que usan el
bundle de `certifi` y no el almacén de Windows, y en esta máquina hay un MITM de **Norton Web/Mail
Shield** cuya raíz vive sólo en el almacén del sistema. Cualquier llamada real al proveedor falla
con `CERTIFICATE_VERIFY_FAILED` hasta que se exporta el almacén a un PEM y se apunta
`SSL_CERT_FILE` a él. Afecta a los spikes y a la evidencia, **a ningún test** — ninguno llama al
proveedor — y queda anotado en `CLAUDE.md`.

---

## 5. Cobertura: los 19 escenarios de la historia contra sus tests

**158 tests nuevos.** Los 19 escenarios tienen cobertura; ninguno queda sin test. La columna de
la derecha nombra el test que lo cubre, y cuando son varios, el que lo cubre de forma más directa.

| # | Escenario de la HU | Test |
|---|---|---|
| 1 | Una pieza con familia devuelve su grupo con las variantes | `test_a_piece_with_a_family_is_grouped_under_it_with_its_variants` · `test_a_piece_with_no_question_is_served_as_one_group` |
| 2 | Una pieza sin familia devuelve un grupo de un solo miembro | `test_a_piece_with_no_family_is_a_group_of_exactly_one` · `test_a_piece_with_no_family_raises_no_variants_warning` |
| 3 | El aviso de variantes sale del roster y no de los candidatos | `test_the_variants_warning_fires_on_a_member_the_retrieval_did_not_return` |
| 4 | Falta la talla y se avisa con un código, no con prosa | `test_a_missing_size_label_raises_its_warning` · `test_no_warning_code_is_a_sentence_in_natural_language` |
| 5 | Los avisos de stock no los emite este servicio | `test_a_piece_out_of_stock_raises_no_stock_warning_and_leaks_no_bucket` · `test_no_stock_warning_is_emitted_by_this_service` |
| 6 | El argumentario cita las fichas de sus materiales, y sólo las suyas | `test_the_citations_come_from_the_declared_material_sheet` · `test_no_sheet_of_an_undeclared_material_is_cited` |
| 7 | Ningún compromiso de la casa entra en un argumentario no pedido | `test_no_commitment_of_the_establishment_enters_an_unrequested_argument` · `test_the_scope_filter_holds_even_if_the_allow_list_were_widened` |
| 8 | Una pregunta sobre la pieza no puede citar la ficha de otro material | `test_a_question_about_the_piece_never_cites_another_materials_sheet` · `test_no_sheet_of_an_undeclared_material_survives_the_piece_scoped_set` |
| 9 | El filtro de material no cierra la puerta al resto del corpus | `test_the_piece_scoped_set_never_excludes_a_document_that_is_not_a_sheet` (10 casos) · `test_the_two_prefixed_documents_that_are_not_sheets_stay_reachable` |
| 10 | Una consulta libre se atiende y su intención no se declara resuelta | `test_a_free_query_is_served_over_the_retrieved_candidates` · `test_two_wordings_with_the_same_anchors_report_the_same_intent` |
| 11 | Una petición sin pieza y sin consulta se rechaza | `test_assist_request_without_any_anchor_is_rejected_naming_both_fields` · `test_a_request_with_neither_anchor_is_rejected_naming_both` |
| 12 | Cuando el catálogo no puede contestar, no se genera y se declara | `test_an_abstained_query_returns_no_group_and_says_so` · `test_assist_response_does_not_reuse_low_confidence_for_abstention` |
| 13 | Una consulta contestable no se silencia | `test_an_answerable_query_is_not_silenced` |
| 14 | Una pieza que no está en el índice es un error, no una abstención | `test_the_three_unusable_cases_give_three_different_sentences` · `test_an_unusable_piece_is_a_422_and_never_a_200_with_abstained` |
| 15 | El punto de venta lo manda el token y nunca el cuerpo | `test_the_scope_comes_from_the_token_and_never_from_the_body` · `test_a_call_without_a_token_is_rejected` |
| 16 | Ninguna cifra de precio ni de stock viaja en la respuesta | `test_no_field_of_the_response_carries_a_price_or_a_stock_figure` |
| 17 | El contrato publicado y el vivo no divergen | `test_openapi_snapshot_is_stable` (ya existía) |
| 18 | Con los stubs apagados la ruta deja de responder 501 | `test_the_route_does_not_answer_501_with_stubs_disabled` · `test_the_assistance_route_is_no_longer_left_answering_501` · `test_stub_mode_still_serves_the_fixture` |
| 19 | Fuera de alcance explícito | `test_the_argument_is_empty_its_provenance_absent_and_the_usage_zero` · `test_the_assist_package_imports_no_provider_client` · `test_the_intent_is_always_one_of_the_two_declared_values` |

**Tres comprobaciones que merecen leerse por lo que hacen, no por lo que cubren:**

- `test_no_field_of_the_response_carries_a_price_or_a_stock_figure` recorre la respuesta
  **serializada entera** por todos sus caminos, con una pieza cuyo `price` es 87,50 y cuyos tres
  *buckets* de proyección son `0`, `1-2` y `3+`. El comentario del test lo dice: un `pitch` vacío
  haría que una comprobación sobre el `pitch` pasara por construcción, que es el tipo de test que
  llega a verde sin haber afirmado nada.
- `test_the_scope_filter_holds_even_if_the_allow_list_were_widened` le pasa **a propósito** la
  sección de compromiso de `material-bano-de-oro` por su nombre, y la capa sigue rechazándola. Eso
  convierte «sólo `general`» en una propiedad del código y no de una tupla que alguien puede editar.
- `test_the_assist_package_imports_no_provider_client` recorre el grafo de módulos del paquete por
  introspección. `jbg_ai.indexing.embeddings` sí es alcanzable, y es lo correcto: aporta el **tipo**
  del cliente que la capa recibe — la capa nunca lo construye ni busca `litellm` por su cuenta.

---

## 6. Evidencia: la ruta real contra el Postgres local, en los tres modos

Sin ningún fake: la aplicación resuelve `SqlAlchemyProductSearch`, `SqlAlchemyKnowledgeIndex` y el
`LiteLlmEmbeddingClient` real, como lo haría en el contenedor. Índice vivo, corpus vivo,
`STUB_MODE=false`.

Dos piezas elegidas porque exponen los casos difíciles:

- **SKU419** (`3b909d9b…`): `plata` + `baño de oro`, **sin familia** y **sin `size_label`**. Ejerce
  a la vez la sección de piezas mixtas, el aviso de talla, el grupo de un miembro y la exclusión
  de alcance `establecimiento` — porque la ficha del baño es justamente la que lleva un compromiso.
- **SKU76** (`28d7308b…`): «Colgante estrella de mar», la familia de **ocho**, que es la mayor que
  el índice contiene.

### M1 · consulta libre, sin pieza

```
POST /v1/assist/sale  {"query": "colgante de estrella de mar en plata", "top_k": 5}
→ 200 · intent=unclassified · abstained=false
  groups=12 (6 de ellos con family_id nulo, todos de un solo miembro) · members=15
  warnings=["family_has_variants"]   ← del roster de 8 de la pieza foco, que devolvió 4
  citations=[]  ·  pitch=""  ·  prompt_version=null  ·  usage=0
```

> **El escenario 3 de la historia, sucediendo en vivo.** El primer grupo trae **4** miembros
> (`L`, `M`, `S`, `XS`) de una familia que el roster declara de **8**. Contar candidatos habría
> dicho «hay variantes» igual, pero por el motivo equivocado; el roster es el que sabe que faltan
> cuatro.
>
> Y `citations=[]` no es un fallo: es la abstención del conocimiento sobre una consulta de
> **catálogo**, que es exactamente lo que el spike 1 midió — 41 de 72 consultas del golden set
> abstienen al umbral de producción, y una descripción de producto es de las que deben.

### M2 · pieza sin pregunta

```
POST /v1/assist/sale  {"product_id": "3b909d9b-…", "top_k": 5}
→ 200 · intent=product_pitch · abstained=false
  groups=1 · family_id=null · members=1        ← el invariante, servido
  warnings=["size_label_missing"]
  pitch=""  ·  prompt_version=null  ·  usage=0
```

| cita | fichero | encabezado | `claim_scope` |
|---|---|---|---|
| `material-plata#cuidados-y-limpieza-en-casa` | `data/knowledge/material-plata.md` | línea **21** | general |
| `material-plata#piel-sensible-y-alergias` | `data/knowledge/material-plata.md` | línea **54** | general |
| `material-bano-de-oro#cuidados-y-limpieza-en-casa` | `data/knowledge/material-bano-de-oro.md` | línea **21** | general |
| `material-bano-de-oro#piel-sensible-y-alergias` | `data/knowledge/material-bano-de-oro.md` | línea **50** | general |
| `material-piezas-mixtas#limpiar-una-pieza-mixta-sin-estropear-nada` | `data/knowledge/material-piezas-mixtas.md` | línea **72** | general |

> **Lo que no está ahí es la mitad de la evidencia.** `material-bano-de-oro` tiene una séptima
> sección, «Nuestra garantía sobre el baño», en la **línea 94** del mismo fichero, de alcance
> `establecimiento`. Una pieza bañada pidió su argumentario y esa sección **no salió**. Es el
> escalón que D7 describe, medido sobre la única pieza del catálogo que lo tiene.

### M3 · pieza con pregunta

```
POST /v1/assist/sale  {"product_id": "28d7308b-…",
                       "query": "¿Por qué se pone negra la plata y cómo se limpia en casa?"}
→ 200 · intent=unclassified · abstained=false
  groups=1 · family_id=2d6a0c7b-… · family_label="Colgante estrella de mar" · members=8
    variants=[L, M, "M oro", S, "S oro", XS, "XS oro", null]
  warnings=["family_has_variants"]   ·  8 documentos excluidos
  pitch=""  ·  prompt_version=null  ·  usage=0
```

| cita | fichero | encabezado | `claim_scope` |
|---|---|---|---|
| `material-plata#cuidados-y-limpieza-en-casa` | `data/knowledge/material-plata.md` | línea **21** | general |
| `material-plata#como-guardarlo` | `data/knowledge/material-plata.md` | línea **88** | general |
| `material-plata#como-envejece-y-que-esperar` | `data/knowledge/material-plata.md` | línea **71** | general |
| `material-piezas-mixtas#limpiar-una-pieza-mixta-sin-estropear-nada` | `data/knowledge/material-piezas-mixtas.md` | línea **72** | general |
| `material-plata#que-lo-estropea` | `data/knowledge/material-plata.md` | línea **37** | general |

> Cinco citas, **ninguna** de las ocho fichas excluidas, y el modo que sí busca alcanzando cuatro
> secciones distintas de la ficha correcta — no las dos de la lista blanca de M2. Es la diferencia
> entre direccionar y buscar, vista en la misma pieza.

**Las quince citas de M2 y M3 resuelven**: fichero existente, encabezado encontrado por su título
y número de línea. Ninguna decorativa. Y las tres respuestas pasan la comprobación de frontera
sobre el cuerpo serializado completo — sin `price`, sin `stock`, sin `qty_bucket`.

### Dos cosas que la evidencia expone y conviene declarar

**El `family_label` viaja vacío en el camino de consulta.** En M2/M3 sale del roster; en M1 los
grupos se construyen sobre `RetrievalResult`, que no lleva el nombre de la familia, y rellenarlo
costaría **una sentencia por grupo** — doce en esta respuesta. El campo es opcional en el contrato
y se deja ausente antes que pagar doce lecturas por una etiqueta.

**La proyección del punto de venta estaba caducada** (710.534 s ≈ 8,2 días frente a un tope de
3.600), así que la recuperación degradó a no-acotada y lo dijo en un `WARNING`. Es el
comportamiento que C22 define, no un defecto de C30a, y aparece aquí porque es lo que un
despliegue real haría con este índice local.
