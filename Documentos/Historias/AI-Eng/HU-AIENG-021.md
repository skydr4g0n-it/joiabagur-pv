# HU-AIENG-021: Búsqueda híbrida — rama léxica, fusión RRF de tres listas y filtros estructurales que degradan

## Formato estándar

Como **Operador de la joyería**, quiero **que «Buscar con ayuda» encuentre la pieza cuando la nombro con mis palabras y también cuando la describo**, **para** **no tener que adivinar el vocabulario del catálogo ni salir del panel asistido hacia el buscador manual**.

---

## Descripción

Change OpenSpec `add-hybrid-search-rrf` / **C21**, épica **EP14 — Búsqueda Semántica Híbrida**. Prerrequisitos **C14** y **C20**, los dos archivados. Nunca se recorta (§6 del plan). C21 desbloquea a la vez **C24** (harness de evaluación), **C25** (señales de negocio) y **C30** (generación con avisos): es decir, las dos mitades del proyecto.

C05 creó la columna `tsv` —`to_tsvector('spanish', doc_text)`, generada y con índice GIN— **poblada en las 1.168 filas vivas y sin un solo consumidor** desde entonces. C14 construyó la rama vectorial. C20 fabricó el diccionario de expansión, que hoy **se calcula, se registra y no se consume**. C21 es el change que enchufa los dos cables: enciende la rama léxica sobre `tsv`, consume los grupos de equivalencia de C20 y funde los rankings.

**El valor de operador es directo y medible.** Hoy, con sólo la rama vectorial, «sortija de plata» devuelve *Pulsera Río de Plata* en primera posición y acierta **4 de 10**; «criollas de oro» acierta **1 de 10** — y en ambos casos **no abstiene**: devuelve diez candidatos bajo el umbral, así que el fallo llega a la pantalla con apariencia de acierto. Tras C21, esas dos consultas aciertan **10 de 10** y **6 de 10**.

### Lo que la exploración del 2026-09-02 midió, y que reencuadra la ficha

Medido contra el PostgreSQL local (1.168 documentos vivos) y contra el proveedor real de embeddings. El detalle completo, con los barridos de peso y profundidad, vive en [c21-hybrid-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md). **Seis** hallazgos cambian el alcance de esta historia: **dos refutan a la propia ficha**, **tres refutan recomendaciones que la exploración había dado antes de medir** —incluida una de la primera versión de esta misma historia— y el sexto desmonta un supuesto heredado de C14:

**1. La conjunción estricta deja la rama léxica muda ante las consultas reales.** `retrieval/measure.py` compone hoy `&&` entre grupos. Sobre las **10 consultas reales** de `public."ProductSearchEvents"`, **7 devuelven cero documentos**:

| consulta real del operador | AND estricto | *zero-drop* | OR + coordinación |
|---|---:|---:|---|
| un anillo de plata para regalar | **0** | **0** | 767 candidatos, anillos de plata en cabeza |
| collar elegante para una boda | **0** | **0** | 259 |
| joya con forma de concha marina | **0** | **0** | 175 |
| anillo de filigrana tradicional menorquina | **0** | **0** | 350 |
| algo dorado para el dia de la madre | **0** | 46 | 506 |

El fallo **no** es «una palabra desconocida»: es que la conjunción de palabras individualmente frecuentes no casa nada. `anillo & plata & regalar` da 0 porque en todo el catálogo sólo **7** documentos mencionan `regalo` y ninguno es un anillo de plata. La causa de fondo es de cobertura del corpus: la línea `Ocasiones:` existe en **150 de 1.168** documentos (13 %) y `Estilo:` en **133** (11 %), frente a `Tipo:` en 1.157 (99 %) y `Materiales:` en 1.042 (89 %).

**2. `@>` sobre materiales no es una semántica alternativa: es un precipicio de recall.** La ficha pide `materials && ARRAY[...]` por defecto y `@>` cuando la consulta nombra varios. Medido: `['plata','oro']` alcanza **913** documentos con `&&` y **60** con `@>`; `['oro','baño de oro']`, **376** frente a **1**. El 91,6 % del catálogo tiene un material o ninguno, así que `@>` sólo puede alcanzar a los 91 documentos con dos o más. Y **126 documentos (10,8 %) no tienen materiales extraídos** —36 anillos, 19 broches, 18 pulseras—, así que un `&&` *duro* los borraría de toda consulta de material.

**3. La paridad de peso entre ramas es la peor de las fusiones.** Barridas 36 configuraciones (`k` × peso vectorial × profundidad), con la **misma rúbrica que usó C20** —aciertos en el top-10 con `piece_type` y material correctos—:

| configuración | total /120 |
|---|---:|
| Sólo vectorial (lo que hay hoy en producción) | **67** |
| Fusión con peso vectorial **1,0** (paridad entre ramas) | **96** |
| Fusión con peso vectorial 0,5 | 102 |
| **Fusión con peso vectorial 0,33** | **105** |
| Sólo léxico (A + B, sin rama vectorial) | 107 |

La palanca dominante es **el peso de la rama vectorial**; `k` entre 20 y 60 mueve ≤2 puntos. La causa es estructural: **la rama vectorial llena siempre su cuota entienda o no la consulta**, así que bajo RRF vota siempre y con la misma fuerza.

**4. La asimetría de profundidad —200 léxica frente a 60 vectorial— costaba 6-8 puntos**, y estaba en la primera versión de esta historia. Con profundidad **simétrica**:

| profundidad de las tres listas | `wC=0,33` | `wC=0,5` | `wC=1,0` |
|---:|---:|---:|---:|
| 200 léxica / 60 vectorial | **105** | 102 | 96 |
| 40 | **113** | 107 | 97 |
| 50 | **113** | 108 | 99 |
| **60** | **111** | 107 | 102 |
| 100 | 107 | 107 | 100 |
| 200 | 107 | 106 | 96 |

El óptimo es una meseta de **40-60** que decae a partir de 100. El motivo es que **`k` y la profundidad no son parámetros independientes**: con `k = 60`, el documento de la posición 200 conserva el 38 % del voto del primero, así que una lista larga no amplifica su cabeza pero **reparte voto positivo entre 140 documentos que la otra rama ni siquiera puntúa**, y ese caudal desplaza a los que dos ramas colocan bien sin colocar primero. La regla que se adopta es **`profundidad ≈ k`**. Y el peso quedaba confundido con la profundidad en la medición anterior: separados, `wC = 0,33` sigue ganando **a todas** las profundidades.

**5. El umbral de 0,65 no filtra nada, así que la profundidad *es* el corte.** Contando cuántos documentos pasan `distancia <= 0,65`: `sortija de plata` **1.168 de 1.168**, `gargantilla dorada` **1.168**, `collar elegante para una boda` 1.090. El umbral está **por encima de la mediana** de la distribución. Matiza además lo que C20 dejó escrito: el vector **sí** abstiene, pero sólo ante texto sin sentido —una consulta de control da `d_min = 0,700` y **cero** documentos—; lo que no hace es discriminar entre consultas plausibles. Un umbral que cortara de verdad tendría que ser un **cuantil por consulta** (0,445 para `gargantilla dorada`, 0,594 para `bano de oro`), que es lo que la ficha de C25 ya pide. **C21 lo declara y no lo recalibra.**

**6. Los campos subjetivos están cubiertos al 11-19 %, y la coordinación los convertía en dictadores.** `Ocasiones:` existe en **150 de 1.168** documentos, `Estilo:` en **133**, `Colores:` en **224**; `boda` casa **5** documentos en todo el catálogo. Bajo ordenación por coordinación, casar un grupo más adelanta a un documento por delante de **todos** los que casan menos: cinco piezas etiquetadas `boda` adelantarían a 1.163 igual de válidas para una boda pero sin etiquetar. En un campo al 99 % la ausencia **es** evidencia; en uno al 13 % **no lo es**. Restringiendo la coordinación a los campos de cobertura alta y a los términos que no resuelven: **113/120** excluyendo ocasión y estilo, **114/120** excluyendo también color, **sin una sola pérdida**.

**7. El realce de SKU y nombre exacto no compra nada.** Medido: `anillo Ses Salines plata` sitúa los cuatro *Ses Salines* en cabeza de **las dos** listas léxicas (`ts_rank` 0,99 en la tecleada, coordinación máxima en la expandida); igual `pulsera Cala Galdana`, `colgante conchiglie` y `pendientes erizo de mar`. Y para un SKU exacto (`SKU690`) la rama vectorial devuelve **cero** candidatos —todo queda por encima del umbral 0,65—, así que la lista de un elemento no compite contra 60 vecinos ruidosos.

### Alcance de esta historia (sí)

- **Rama léxica** sobre `ai.product_document.tsv`, consumiendo los grupos de equivalencia de C20. **Dos listas**: la tecleada por el operador y la expandida.
- **Fusión RRF** de tres listas ordenadas con **pesos por lista configurables**, `k` configurable y **profundidad por rama simétrica y acoplada a `k`**, distinta conceptualmente del overfetch de salida aunque su valor por defecto coincida.
- **Coordinación restringida a los campos cuya ausencia es evidencia**, de modo que un campo cubierto al 11-19 % no pueda decidir el orden y la consulta subjetiva quede en manos de la rama vectorial sin ponderación adaptativa que calibrar.
- **Filtros estructurales extraídos por reglas** del texto de la consulta —techo de precio, talla y materiales— que **degradan y nunca excluyen**, mediante ordenación por bloques estable.
- **`match_reasons` real por resultado** (`vector`, `lexical`, o ambos) en lugar de la constante `["vector"]`, y `debug.lexical_score` poblado.
- **`mode` deja de ser mentira**: `vector`, `lexical` e `hybrid` hacen lo que dicen, y desaparece la nota `vector_only_until_c21`.
- **Degradación honesta**: si el proveedor de embeddings falla en `mode=hybrid`, se sirve la rama léxica y **se dice en pantalla**, en lugar de devolver 503 o de pintar «Coincidencia semántica» sobre resultados que no la tuvieron.
- **`low_confidence` como señal de desacuerdo entre ramas**, en telemetría y `debug`, sin cambiar cuándo se devuelven resultados.
- **Singleton del cliente de embeddings** con **caché acotado inyectado**, pagando la deuda que `openspec/DEFERRED_TASKS.md` asigna a C21 o C22.
- **Insignia de origen por resultado** en el panel de C16, leída de `matchReasons` en lugar del `aiAvailable` global. Es la evolución que C16 dejó preparada por escrito.
- Logs `stage=lexical`, `stage=filters` y `stage=fuse` junto a los `stage=expand`, `stage=embed` y `stage=search` existentes.
- Tests unitarios *offline* en `ai-service/tests/retrieval/` y de componente en `frontend/`.

### Fuera de alcance (no)

- **Revertir `AiGateway:RetrievalTimeoutMs` de 2500 a 800 ms.** Exige desplegar a la demo, re-medir en frío y en caliente y confirmar el embudo: es otra clase de trabajo y otro riesgo. Change propio, después del singleton. Sigue anotado en `DEFERRED_TASKS.md`.
- **Aplicar el techo de precio sobre el precio real.** Python **degrada** y **declara** lo que extrajo; aplicarlo con la verdad es de .NET y mueve `openapi.json`. Queda como disparador escrito, no como tarea.
- **Señales de negocio en el ranking** —`qty_bucket`, `sales_30d`, penalización por stock cero— → **C25**. C21 deja la costura de reordenación donde C25 la sustituirá por pesos calibrados.
- **`ai.pos_projection` y el prefiltro blando por punto de venta** → **C22**.
- **Sustitutos** (`POST /v1/retrieval/substitutes`, que sigue en 501) → **C26**. **Corpus de conocimiento** → C23. **Golden set y métricas graduadas** → C24.
- **Reranking con cross-encoder**: no se implementa; el diseño ya documenta la hipótesis y el protocolo (§11.2).
- **Erratas y `pg_trgm`**; reformulación de consulta con LLM; `ai.query_log`; persistir nada.
- **`enrichment/vocabularies.yaml`** y los huecos `llavero`, `diadema`, `gemelos`, `cinturon`, `filigrana` → `fix-enrichment-vocabulary-gaps`.
- **`setweight` sobre `tsv`**: es columna **generada** sobre `doc_text` plano; ponerle pesos por campo exigiría reescribirla y reconstruir el GIN. C21 **no es** 🗄️.
- Instalar `unaccent`; regenerar `ai-service/openapi.json`; revisión de Alembic; migración de EF Core; **ningún cambio en `backend/`**.

### Decisiones de diseño ya acordadas

*(Exploración 2026-09-02, medida en [c21-hybrid-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md).)*

| # | Tema | Decisión |
|---|---|---|
| 1 | **Qué se funde** | **Tres listas ordenadas**: `A` tecleada, `B` expandida, `C` vectorial. C20 midió que fundir A con B devuelve a las posiciones 1-2-3 los productos que el operador nombró literalmente; sin `A`, la lista expandida no coloca ninguno en su top-6 |
| 2 | **Pesos de la fusión** | `A = 0,5 · B = 0,5 · C = 0,33`, `k = 60`, todo en `Settings` y en la firma del orquestador. **La paridad entre ramas (`C = 1,0`) queda refutada**: 96/120 frente a 105/120, y sigue perdiendo a cualquier profundidad. Ponderar **recíprocos de rango** no es lo que S10 desaconseja —que es ponderar puntuaciones brutas de distribución cambiante—: el peso no calibra escalas, declara cuántos votos tiene cada rama |
| 2b | **Profundidad por rama: simétrica, 60** | **Refuta la primera versión de esta misma historia**, que daba 200 a las listas léxicas y 60 a la vectorial. Medido, esa asimetría cuesta **6-8 puntos de 120**: 105/120 con 200/60 frente a **111/120** con 60/60/60, y el óptimo está en una meseta de 40-60 que decae monótonamente a partir de 100. El motivo es que **`k` y la profundidad no son independientes**: con `k=60`, el documento de la posición 200 conserva el 38 % del voto del primero, así que una lista larga reparte voto positivo entre 140 documentos que la otra rama ni siquiera puntúa, y ese caudal desplaza a los que dos ramas colocan bien. **Regla: `profundidad ≈ k`.** Se elige 60 y no 50 —2 puntos dentro del ruido de una muestra de 12 consultas— porque coincide con el `OVER_RETRIEVAL_CAP` que ya existe, y así hay **un número arbitrario menos** |
| 2c | **El umbral de distancia no es el corte** | Medido: `JPV_RETRIEVAL_DISTANCE_THRESHOLD = 0,65` está **por encima de la mediana** de distancias y deja pasar **el corpus entero** (1.168 de 1.168) en las consultas ordinarias. Sí abstiene ante texto sin sentido (`d_min = 0,700` → cero documentos), pero no discrimina entre consultas plausibles. Lo que corta la lista vectorial es el `LIMIT`, no el umbral, así que **la profundidad vectorial es un parámetro de ranking de primera clase**. C21 lo **declara y no lo recalibra**: un umbral que cortara de verdad tendría que ser un **cuantil por consulta** (0,445 para `gargantilla dorada`, 0,594 para `bano de oro`), que es literalmente lo que la ficha de **C25** ya pide |
| 3 | **Política booleana de la rama léxica** | **OR entre grupos, ordenado por `(nº de grupos que **cuentan** y casan) DESC, ts_rank DESC`**. Contiene al AND y lo pone en cabeza, así que lo domina; hace innecesario el *zero-drop* (un grupo que no casa nada suma 0 a **todos**, luego no altera el orden); y rescata el término discriminante — con `ts_rank` solo, los *Anillo de Filigrana* caen a 7.º y 8.º; con coordinación suben a 1.º y 2.º |
| 3b | **Qué grupos pueden decidir el orden** | **La coordinación sólo cuenta los grupos cuya ausencia es evidencia.** Cuenta un grupo si resolvió a un campo de **cobertura alta** (`piece_type` 99 %, `materials` 89 %) **o si no resolvió en absoluto** —palabra literal del operador, el caso que rescató los anillos de filigrana—. **No** cuenta si resolvió a un campo **escaso**: `occasion_tags` 13 %, `style_tags` 11 %, `color_tags` 19 % — ni a `size_label` (45 %), que ya es propiedad del filtro que degrada, y un campo, un mecanismo. Esos términos siguen puntuando en `ts_rank`; lo que pierden es el derecho a saltarse la cola. **Motivo:** en un campo al 99 % la ausencia es evidencia —un documento sin `anillo` no es un anillo—; en uno al 13 % no lo es —`boda` casa **5** documentos, y los otros 1.163 pueden ser perfectos para una boda sin que nadie los etiquetara—. Sin esta regla, cinco piezas etiquetadas adelantarían a todo el catálogo. Medido: **113/120** frente a 111 excluyendo ocasión y estilo, **114/120** excluyendo también color, **sin una sola pérdida** en las doce consultas |
| 3c | **Adaptación al tipo de consulta, sin un segundo peso** | Consecuencia **emergente** de 3b y no un mecanismo aparte: cuando la consulta es mayoritariamente subjetiva (*«algo elegante para una ceremonia»*) quedan pocos grupos que cuenten o ninguno, la coordinación deja de discriminar, la lista léxica degenera a `ts_rank` sobre un OR ancho —señal débil— y **la rama vectorial decide por defecto**. Es la ponderación dinámica que S10 describe, **sin el número mágico que S10 advierte que hay que justificar, recalibrar y depurar**. Una ponderación adaptativa explícita queda como configuración `v3-adaptativa` para la ablación de C24, no como alcance de C21 |
| 4 | **Filtros estructurales** | **Degradan, nunca excluyen.** Regla de una frase: *lo que un humano pulsó, filtra; lo que una regla dedujo del texto, degrada*. Los filtros del body (`filters.materials`, `filters.category`) siguen siendo duros porque los pulsó el operador en el panel; los extraídos del texto ordenan por bloques estables, conservando el orden RRF dentro de cada bloque, y **nunca sacan un candidato de la ventana de overfetch** |
| 5 | **`@>` sobre materiales** | **No entra**, ni siquiera como defecto de consulta multi-material. Medido: 60 de 913. Queda como flag apagado hasta que C24 lo mida con relevancia graduada. **Discrepa de la ficha y del §7.3 del diseño**, con la medición delante |
| 6 | **`piece_type` extraído** | **No se filtra en absoluto.** La medición de C20 demuestra que buscar léxicamente el canónico **equivale** a filtrar por `piece_type`; añadirlo como `WHERE` sólo constriñe la rama vectorial, que es la que rescata la paráfrasis |
| 7 | **Realce de SKU y nombre exacto** | **No entra.** Refuta a la ficha, con medición: un nombre exacto ya encabeza las dos listas léxicas por sí solo, y la rama vectorial abstiene ante un SKU. `test_exact_sku_query_ranks_target_first` se conserva y **cambia de naturaleza**: verifica una propiedad emergente, y si algún día deja de cumplirse, el fallo aparece y **entonces** se discute el anclaje |
| 8 | **Composición de la `tsquery`** | `websearch_to_tsquery` para la lista **A** —regala `"comillas"` y `-negación` gratis, y un error de sintaxis no puede vaciar el resultado porque **B no interpreta sintaxis**—; `plainto_tsquery` **por forma emitida** para la lista **B**. **`phraseto_tsquery` queda descartado con medición**: aniquila `aro de dedo` (6 documentos → **0**), que es la entrada del overlay a la que C20 atribuye +262 |
| 9 | **Seguridad de la consulta** | Los términos viajan **siempre como parámetros**; nunca se concatena sintaxis de consulta. Se hereda la forma segura que `retrieval/measure.py` ya usa |
| 10 | **Abstención** | `low_confidence` pasa a significar **«ningún candidato aparece en más de una rama»** — la firma exacta del fallo medido, donde el vector dice *pulsera* y el léxico dice las tres *sortijas* con solape 0/10. **Sólo señal**: no cambia cuándo se devuelven resultados, porque apagar la pantalla en las consultas conceptuales sería peor |
| 11 | **Caída del proveedor de embeddings** | En `mode=hybrid`, se sirve **sólo la rama léxica** con 200 y `match_reasons: ["lexical"]`, y la insignia de la pantalla lo dice. **Si además la rama léxica no produce nada, 503**: no hay nada que servir y la dependencia está rota, y devolver 200 vacío sería indistinguible de una abstención legítima |
| 12 | **Concurrencia** | La consulta léxica corre **en paralelo con la llamada al proveedor de embeddings**, no con la consulta vectorial. Esconde la rama léxica entera detrás de los 170-1707 ms del proveedor y retiene **una sola** conexión del *pool* de 5 sin *overflow*. Paralelizar rama contra rama optimizaría lo que no cuesta: sobre 1.168 filas con GIN, la léxica es ruido |
| 13 | **Singleton del cliente de embeddings** | **Entra en C21**, que es quien añade trabajo al camino caliente. Pero **no son tres líneas**: `InMemoryEmbeddingCache` es un `dict` sin cota ni TTL, inofensivo por petición y una fuga de memoria de por vida como singleton, en un contenedor capado a 512 MiB que ya usa 232. Se inyecta un caché **acotado** por constructor, **sin tocar `indexing/embeddings.py`**, congelado desde C11 |
| 14 | **Contrato** | **`openapi.json` no se mueve.** Todo cabe en `match_reasons` (lista de cadenas), `debug.lexical_score` y `debug.notes`, que existen desde C02. Los pesos, `k` y las profundidades van a `Settings` + parámetro, el mismo asiento que C20 fijó para su flag |
| 15 | **Reparto de specs** | Delta **MODIFIED** de `vector-retrieval` (comportamiento del endpoint) más capacidad nueva **`hybrid-fusion`** (fusión por rango, procedencia, consenso y degradación de filtros). C23, C25 y C26 van a fundir listas **sin pasar por `POST /v1/retrieval/products`**: si la fusión vive dentro de la spec del endpoint, esos changes tendrían que citar una spec que habla de otro endpoint |
| 16 | **Significado de `score`** | Deja de ser `clamp(1 − distancia coseno)` y pasa a ser la **puntuación RRF normalizada al primer resultado**. Sigue en `[0,1]` y sigue monótona con el orden, que es lo que el contrato promete; `debug.vector_score` conserva la distancia cuando la rama vectorial vio el candidato, y `debug.lexical_score` lleva el `ts_rank` |

**Cortes que no se reabren:** `indexing/embeddings.py` sigue congelado desde C11 · `enrichment/vocabularies.yaml` no se modifica · Python no lee el esquema `public` · sin migración de ninguna clase · sin `setweight` ni configuración `ts` propia · sin `unaccent` ni `pg_trgm` · sin `ai.query_log` · sin tocar `backend/`.

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C21, §4 grafo, §6 nunca se recorta, §7 `design.md` obligatorio),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§5 problema de recuperación, §6.4 degradación, §7.3 filtro por materiales, §7.6 prefiltro blando y sobre-recuperación),
[c21-hybrid-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md) (**las seis mediciones que gobiernan el diseño**),
[Búsqueda híbrida](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Busqueda%20hibrida.md) y [Filtrado contextual y temporal](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Filtrado%20contextual%20y%20temporal.md) (guía avanzada, no dogma: los apuntes proponen RRF sin pesos y paralelizar rama contra rama; aquí se mide y se corrige),
[epicas.md](../../epicas.md) (EP14),
[modelo-de-datos.md](../../modelo-de-datos.md) (`ai.product_document`, `tsv` generada, GIN, HNSW),
[HU-AIENG-014.md](HU-AIENG-014.md) (retriever vectorial), [HU-AIENG-015.md](HU-AIENG-015.md) (hidratación autoritativa), [HU-AIENG-016.md](HU-AIENG-016.md) (panel e insignia de origen), [HU-AIENG-020.md](HU-AIENG-020.md) (diccionario de expansión),
specs vivas `vector-retrieval`, `query-expansion`, `ai-vector-schema`, `ai-service-runtime`, `assisted-search-panel`,
change OpenSpec [`openspec/changes/add-hybrid-search-rrf/`](../../../openspec/changes/add-hybrid-search-rrf/) y su [ticket técnico](../../../openspec/changes/add-hybrid-search-rrf/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: El operador nombra la pieza con su palabra y la encuentra

**Dado que** el índice contiene 268 anillos y ninguno se llama «sortija» salvo nueve por nombre propio
**Y** el diccionario de C20 resuelve `sortija → anillo`
**Cuando** el operador busca `sortija de plata` en modo híbrido
**Entonces** los resultados del top-10 son anillos de plata
**Y** los productos llamados literalmente «Sortija» que también son de plata **no** quedan fuera del top-10, porque la lista tecleada entra en la fusión con voto propio
**Y** cada resultado lleva en `match_reasons` la procedencia real (`vector`, `lexical` o ambas), nunca la constante `["vector"]`

### Escenario 2: El operador describe la pieza y la rama léxica no se queda muda

**Dado que** la consulta contiene palabras que no casan ningún documento junto a las que sí
**Cuando** el operador busca `un anillo de plata para regalar`
**Entonces** la rama léxica devuelve candidatos en lugar de cero
**Y** los documentos que casan **más** grupos de la consulta encabezan la lista léxica, por delante de los que casan menos
**Y** un grupo que no casa ningún documento no altera el orden de los demás
**Y** con `anillo de filigrana tradicional menorquina`, los anillos de filigrana quedan por delante de los anillos genéricos

### Escenario 3: Un término subjetivo aporta, pero no manda

**Dado que** la línea de ocasiones existe en 150 de 1.168 documentos y la de estilo en 133, y que `boda` casa 5 documentos en todo el catálogo
**Y** que la ausencia de una etiqueta en un campo así **no** es evidencia de que la pieza no sirva
**Cuando** el operador busca `collar elegante para una boda`
**Entonces** los documentos etiquetados con esa ocasión **no** se adelantan a todos los que no la llevan por el mero hecho de llevarla
**Y** sí conservan la ventaja de puntuación de texto que les corresponde
**Y** el tipo de pieza y el material, que sí están en campos cubiertos casi por completo, siguen decidiendo el orden
**Cuando** la consulta es casi enteramente subjetiva, como `algo elegante para una ceremonia`
**Entonces** apenas queda señal estructural que ordenar y **la rama vectorial pasa a decidir**, sin que haya un segundo peso configurado para ello

### Escenario 4: La profundidad de las tres listas es la misma

**Dado que** la fusión por rango premia el consenso, y una lista más larga reparte votos entre documentos que las demás no puntúan
**Cuando** se funden las tres listas
**Entonces** las tres se truncan a la misma profundidad
**Y** esa profundidad está acoplada a la constante de suavizado de la fusión, no elegida por separado
**Y** el tamaño de la ventana de sobre-recuperación que se devuelve es un parámetro distinto, aunque su valor por defecto coincida
**Y** ningún candidato entra en la respuesta por aparecer en la cola larga de una sola rama

### Escenario 5: Un techo de precio degrada, pero no borra

**Dado que** el operador escribe una restricción de precio en el texto, como `menos de 80`
**Cuando** se ejecuta la búsqueda
**Entonces** los candidatos que cumplen el techo quedan por delante de los que no
**Y** el orden de la fusión se conserva **dentro** de cada bloque
**Y** ningún candidato que supera el techo desaparece de la ventana de sobre-recuperación, porque el precio del índice es una proyección y **.NET es la autoridad**
**Y** el techo extraído queda declarado en `debug.notes` y en el log, para que se pueda auditar si la regla acertó

### Escenario 6: Un filtro que el operador pulsó sí excluye

**Dado que** el operador ha seleccionado materiales en los filtros rápidos del panel
**Cuando** se ejecuta la búsqueda
**Entonces** esos materiales se aplican como filtro duro con solape (`&&`), como hasta ahora
**Y** un material **deducido del texto** no excluye a nadie: sólo degrada
**Y** en ningún caso se exige que el producto contenga **todos** los materiales nombrados

### Escenario 7: La fusión no deja que una rama ciega mande

**Dado que** la rama vectorial devuelve siempre su cuota de candidatos, entienda o no la consulta
**Cuando** se funden las tres listas
**Entonces** el peso de cada lista se lee de la configuración y **no** está escrito en el código
**Y** el peso por defecto de la rama vectorial es menor que el de la rama léxica
**Y** la profundidad de candidatos por rama es un parámetro distinto del tamaño de la ventana de sobre-recuperación que se devuelve
**Y** cambiar la configuración no exige reiniciar el proceso, para que C24 pueda barrer configuraciones

### Escenario 8: Si el proveedor de embeddings cae, se sirve lo que hay y se dice

**Dado que** la búsqueda se pide en modo híbrido
**Y** el proveedor de embeddings falla
**Cuando** la rama léxica sí produce candidatos
**Entonces** la respuesta es 200 con esos candidatos
**Y** ninguno lleva `vector` en `match_reasons`
**Y** el panel muestra la insignia de búsqueda por texto en esos resultados, no la de coincidencia semántica
**Cuando** además la rama léxica no produce ningún candidato
**Entonces** la respuesta es 503 y **no** un 200 vacío, que sería indistinguible de una abstención legítima

### Escenario 9: Los modos del contrato dejan de mentir

**Dado que** el contrato congelado acepta `vector`, `lexical` e `hybrid`
**Cuando** se pide `mode=lexical`
**Entonces** no se llama al proveedor de embeddings en absoluto
**Cuando** se pide `mode=vector`
**Entonces** no se consulta la columna de texto
**Y** en ningún caso aparece ya la nota `vector_only_until_c21`
**Y** `ai-service/openapi.json` no se ha regenerado

### Escenario 10: El desacuerdo entre ramas se registra como señal

**Dado que** las dos ramas pueden proponer conjuntos disjuntos, que es la firma del fallo medido
**Cuando** ningún candidato del resultado aparece en más de una rama
**Entonces** la respuesta lo marca como baja confianza
**Y** eso **no** cambia cuántos resultados se devuelven ni en qué orden
**Y** el embudo de .NET y la telemetría lo conservan, para que C24 pueda cruzarlo con la relevancia graduada

### Escenario 11: El cliente de embeddings se comparte sin fugarse

**Dado que** hasta ahora se construía un cliente por petición y la caché nacía vacía y moría con la respuesta
**Cuando** el servicio arranca
**Entonces** el cliente de recuperación es único para el proceso
**Y** su caché tiene **cota máxima**, para que un contenedor de 512 MiB no se llene con una entrada por consulta distinta
**Y** `indexing/embeddings.py` no tiene diff, porque sigue congelado desde C11
**Y** `AiGateway:RetrievalTimeoutMs` sigue en 2500 ms: revertirlo es otro change

### Escenario 12: Fuera de alcance explícito

**Dado que** C21 entrega la búsqueda híbrida
**Cuando** se revisa el entregable
**Entonces** **no** hay señales de negocio en el ranking, ni proyección por punto de venta, ni sustitutos, ni corpus de conocimiento, ni golden set
**Y** **no** existe realce ni anclaje de SKU o nombre exacto
**Y** **no** se ha usado `phraseto_tsquery` para las formas emitidas del diccionario
**Y** **no** se ha aplicado `@>` sobre materiales por defecto
**Y** `ai-service/openapi.json`, `enrichment/vocabularies.yaml`, `indexing/embeddings.py` y el árbol `backend/` no tienen diff
**Y** no hay revisión de Alembic nueva ni migración de EF Core

---

## Notas adicionales

- **Actor:** el **Operador** de la joyería, por primera vez en toda la cadena C14-C20. C14, C15 y C20 fueron habilitadores; C21 es el change en el que el trabajo acumulado llega a la pantalla y cambia lo que el operador ve.

- **Novena vez que la zona de una ficha se queda corta.** La ficha declara zona `ai-service/src/jbg_ai/retrieval/`. Son además `api/main.py` (singleton), `config/settings.py` (pesos y profundidades) y **`frontend/`**: sin leer la insignia de origen desde `matchReasons`, la pantalla seguiría diciendo «Coincidencia semántica» sobre resultados servidos sólo por la rama léxica, que es exactamente la mentira que la decisión 11 existe para evitar. Van tras C08, C07, C15, C16, C17, C18b y C20.

- **El cambio de frontend es de una línea de lógica, y C16 lo dejó escrito.** El comentario de `assisted-search-result-row.tsx` dice literalmente que el mapa de insignias es *«una búsqueda en vez de un condicional para que un origen posterior —la rama léxica de C21— sea una entrada nueva aquí en lugar de un cambio en la fila»*. Y `matchReasons` **ya viaja** por `AssistedSearchService` hasta el DTO y hasta el tipo de TypeScript: no hace falta tocar .NET.

- **La rúbrica de la medición es la función objetivo de la propia rama léxica.** `doc_text` lleva líneas canónicas `Tipo:` y `Materiales:`, y la expansión de C20 apunta justo ahí; medir «tipo correcto y material correcto» premia por construcción a quien casa esas líneas. Los 105/120 fijan un **punto de partida**, no un veredicto: el juez es el golden set con relevancia graduada y categoría de paráfrasis de **C24**. Que la fusión no supere a la rama léxica sola **en esa rúbrica** es esperable y no es motivo para quitar la rama vectorial, que gana justo donde la rúbrica no la ve: en `joya con forma de concha marina`, el léxico entierra en las posiciones 23 y 24 los *Colgante Caracola Marina* que el vector pone 1.ª y 2.ª.

- **Por qué la fusión y no elegir una rama.** Tres consultas medidas donde ninguna rama sola acierta y la fusión sí: `criollas de oro` (vector 1, léxico 3, **fusión 6**), `pendientes de oro con piedra azul` (3, 6, **8**) y `pulsera de plata con motivos marinos` (8, 8, **9**). Es exactamente el argumento del artículo de búsqueda híbrida de S10: RRF premia el consenso.

- **`k = 60` se conserva por higiene, no por convicción.** Medido, `k` entre 20 y 60 mueve ≤2 puntos sobre 120. Se deja el valor de la literatura para no tener que defender un número propio, y se hace configurable para que C24 lo barra si le sobra sesión.

- **La talla se extrae pero cubre menos de la mitad del catálogo.** `size_label` está presente en **529 de 1.168** documentos (45 %): S 122, M 103, L 87, XL 83, `pequeno` 71, mini 21, grande 14, XS 10, mediano 6. Y **`numero` casa cero documentos**, así que «anillo de plata numero 3» —una consulta real registrada— no tiene diana en el índice. Es un hueco de vocabulario, no un fallo de C21; se declara y se pasa a `fix-enrichment-vocabulary-gaps`.

- **El precio del índice está completo pero es una proyección.** Las 1.168 filas tienen precio (mínimo 2,50 €, mediana 230 €, máximo 4.175 €) y 228 están por debajo de 80 €. Que esté completo es lo que hace *posible* degradar por precio; que sea proyección del feed es lo que hace *obligatorio* no excluir con él.

- **Limitación a declarar en el README, heredada de C20 y hermana de la de C24.** Las mediciones se hacen contra el corpus y contra 12 textos escritos por el desarrollador, no contra demanda observada. Los pesos por defecto son un punto de partida medido sobre esas 12 consultas, no una calibración.

- **`design.md` obligatorio** en el change. La ficha ya lo asigna a C21 en la lista del §7 del plan, y hay al menos seis decisiones con alternativa real y coste asimétrico —qué se funde, con qué pesos, política booleana, filtros duros frente a degradación, anclaje de exacto, y qué hacer cuando cae el proveedor— de las que **cuatro contradicen** a la ficha original o a una recomendación previa de la exploración.

- **Verificación posterior (no DoD de merge):** ejecutar la CLI de medición ampliada contra el índice local y comprobar que reproduce las cifras del informe —`sortija de plata` de 4/10 a 10/10 y `criollas de oro` de 1/10 a 6/10—, y medir la latencia del pipeline completo, en frío y en caliente, para dejar la línea base que decidirá el revert de los 800 ms en el change siguiente.

---

## Tareas

1. Completar artefactos OpenSpec del change `add-hybrid-search-rrf`: `proposal`, **`design.md` obligatorio**, `specs` (delta MODIFIED de `vector-retrieval` más capacidad nueva `hybrid-fusion`) y `tasks`.
2. Composición segura de la `tsquery` a partir de los grupos de C20: `plainto_tsquery` por forma emitida, OR entre grupos, términos siempre como parámetros.
3. Rama léxica en el puerto de búsqueda: candidatos por OR, orden por coordinación y `ts_rank`, profundidad propia; y la lista tecleada con `websearch_to_tsquery`.
4. Fusión RRF como **función pura**, con pesos por lista, `k` y procedencia por candidato.
5. Extracción por reglas de techo de precio, talla y materiales desde el texto, reutilizando los términos ya resueltos por C20 en lugar de construir una segunda tabla de consulta.
6. Ordenación por bloques estable que degrada sin excluir, y declaración de lo extraído en `debug.notes` y en el log.
7. `match_reasons` real por resultado, `debug.lexical_score`, `score` como puntuación RRF normalizada, y retirada de la nota `vector_only_until_c21`.
8. Semántica honesta de `mode`, y degradación a rama léxica cuando el proveedor de embeddings falla, con 503 sólo si tampoco hay léxico.
9. `low_confidence` como ausencia de consenso entre ramas, sólo como señal.
10. Concurrencia de la rama léxica con la llamada al proveedor, respetando el *pool* de 5 sin *overflow*.
11. Singleton del cliente de embeddings de recuperación con caché acotado inyectado, sin tocar `indexing/embeddings.py`.
12. Settings nuevos —pesos, `k`, profundidades— con default y pin en `canonical_openapi_settings`, y fila en la tabla de entorno del README.
13. Logs `stage=lexical`, `stage=filters` y `stage=fuse` con `trace_id`.
14. Insignia de origen por resultado en el panel, leída de `matchReasons`.
15. Tests *offline* en `ai-service/tests/retrieval/` y de componente en `frontend/`, incluidos los de fijación que impiden regenerar `openapi.json` y modificar los ficheros congelados.
16. Ampliar la CLI de medición de C20 con la comparación de configuraciones, y dejar informe versionado que C24 reutilice.
17. Enlazar la HU en `Documentos/epicas.md` (EP14) **en el apply**.
18. `openspec validate --all --strict` en `0 failed` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** **5** — es el primer change de la cadena que el operador nota. Medido, «sortija de plata» pasa de acertar 4 de 10 a 10 de 10 y «criollas de oro» de 1 a 6, y desaparece el caso en que la búsqueda falla con apariencia de acierto
- **Urgencia (mercado / feedback):** **5** — desbloquea C24, C25 y C30 a la vez; es el cuello del grafo tras C20
- **Complejidad / esfuerzo:** **4** — dos consultas SQL nuevas, una función de fusión pura, un extractor por reglas, una costura de reordenación, un singleton con caché acotado y un retoque de frontend. Sin migración y sin contrato, pero con **seis decisiones** que hay que dejar escritas y defendidas
- **Riesgos y dependencias:**
  - **Índice local poblado** (1.168 documentos): si se recrea el volumen, las mediciones de verificación no tienen contra qué medirse.
  - **La tentación de subir el peso vectorial a 1,0 «por simetría»** es la trampa principal, y está medida: cuesta 9 puntos de 120 y hunde `dije de plata` de 10 a 2.
  - **La tentación de volver al AND estricto «por precisión»**: deja mudas 7 de las 10 consultas reales.
  - **El *pool* de 5 conexiones sin *overflow***: paralelizar rama contra rama retendría dos conexiones por petición; la léxica va contra el embedding, no contra el vector.
  - **El caché sin cota del singleton**: es la parte de la deuda de `DEFERRED_TASKS.md` que su descripción de «tres líneas en `main.py`» no anticipa.
  - **Zona compartida con C22 y C25**, que también viven en `retrieval/`: no se abren en paralelo, aunque los abra la misma persona (regla superviviente del §1 del plan).
  - **`score` cambia de significado**, y la telemetría de C04 lo persiste: hay que declararlo, porque comparar puntuaciones de antes y después de C21 no significa nada.
