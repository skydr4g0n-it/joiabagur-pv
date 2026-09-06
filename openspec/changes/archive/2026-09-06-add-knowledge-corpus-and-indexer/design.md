## Context

El sistema opera hoy sobre **un solo índice**, `ai.product_document`: una fila por producto, sin trocear, con embedding y `tsvector`. Responde a consultas sobre productos y no puede responder a preguntas sobre la joya o el servicio, porque esas respuestas no viven en ningún producto.

`ai.knowledge_document` y `ai.knowledge_chunk` **existen desde C05** con su forma final —`doc_type` restringido a cinco valores, borrado en cascada, unicidad de `(document_id, chunk_index)`, HNSW coseno, GIN sobre `tsv` y sobre `metadata`, `tsv` generada por el esquema con la configuración española— y **ningún código las escribe ni las lee**. C11 dejó el cliente de embeddings y lo congeló nombrando a este change en su docstring. C20 dejó una expansión de consulta que devuelve grupos de equivalencia sobre el vocabulario de materiales y piedras. C21 dejó un módulo de fusión puro cuyo docstring nombra a C23 como importador futuro. C22 pagó la deuda del cliente de embeddings por petición.

Tres restricciones gobiernan el diseño:

1. **La superficie `/v1` está congelada por un MUST** que enumera diez rutas, y añadir una obliga a regenerar `ai-service/openapi.json` y a acordarlo con el lado .NET.
2. **El corpus lo redacta un asistente.** Los textos comerciales que el §8.1 daba como *«a pedir al negocio»* nunca llegaron, igual que las fotografías. Y la verificación de citas que el §11.3 exige es **estructural, no semántica**: confirma que la fuente citada existía y se recuperó, no que diga la verdad. Un corpus inventado puede pasar la comprobación al 100 % citando algo falso **con sello de verificado**, que es peor que no citar.
3. **Un solo revisor.** El cuello de botella del §7.8 no es de calendario desde la prórroga, es de atención.

## Goals / Non-Goals

**Goals:**

- Construir el segundo índice —corpus, troceado, indexación y búsqueda— sin mover ningún contrato ni abrir ninguna migración.
- Que una cita **resuelva, localice y sea trazable** hasta el fichero del repositorio, en el sentido exacto del apunte de S11, y que siga haciéndolo después de reindexar.
- Que el sistema pueda **distinguir y declarar** qué afirmaciones son comprobables fuera y cuáles son compromisos de la casa hoy ilustrativos.
- Que la abstención sea demostrable: una pregunta fuera de dominio devuelve **cero** fragmentos.
- Dejar a C30 una función lista para ser su tool `consultar_conocimiento`, con la latencia medida.

**Non-Goals:**

- Generación con citas, `pitch`, avisos por reglas y placeholders de precio o stock — es **C30**.
- Golden set, tablas `ai.eval_*`, RAGAS y validador anti-alucinación — es **C24**.
- Cualquier ruta HTTP, cualquier migración, cualquier movimiento de `openapi.json`.
- Router de consultas, reranking, y fusión de los dos índices en una sola lista.
- Conocimiento por producto, en cualquier forma. La decisión 4 de la revisión es que este corpus es general.

## Decisions

### D0. Un solo esquema vectorial para productos y conocimiento — y un espacio de versiones separado

**La pregunta**: ¿necesitan `ai.product_document` y `ai.knowledge_chunk` esquemas vectoriales distintos?

**Qué especifica `ai-vector-schema`.** Quince requisitos en cinco grupos: **propiedad y aislamiento** (el esquema `ai` es el único que el servicio escribe; rol dedicado con privilegio mínimo; ninguna clave foránea hacia el esquema de negocio), **ciclo de migración** (provisión idempotente de extensión y esquema; reversibilidad sin objetos huérfanos), **garantías de índice que fallan en silencio si están mal** (clase de operador coseno alineada con el operador de consulta; GIN para arrays, texto completo y JSONB; B-tree para filtros estructurales), **texto completo** (la `tsvector` la produce el esquema como columna generada con la configuración española nombrada explícitamente, nunca el código de aplicación) y **forma de cada tabla**, más el pool acotado.

**Seis de ellos tocan el corpus directamente**, y tres tienen escenario propio para `knowledge_chunk`: el índice HNSW con clase coseno, el GIN sobre `tsv` **y sobre `metadata`**, y la `tsv` generada sobre `content` en español. Más la separación documento/fragmento con cascada y unicidad de `(document_id, chunk_index)`, la prohibición de acotar el conocimiento a un producto, y el pool.

**Veredicto: un solo esquema, y no por comodidad.**

- **No están obligados a compartir espacio.** Los dos índices **nunca se comparan entre sí** (D6), así que en teoría el corpus podría usar otro modelo y otra dimensión. La pregunta es real, no retórica.
- **Pero cambiar de dimensión cuesta una migración.** La columna es `vector(1536)` en las dos tablas. Este change declara cero migraciones, y no hay ninguna evidencia de que otra dimensión mejore nada sobre 161 fragmentos.
- **Y compartir modelo tiene un beneficio medible que un segundo modelo destruiría.** La caché de C11 está indexada por `(sha256(texto), modelo, versión)`. Con el mismo modelo, **el embedding de la pregunta que calculó la rama de productos es un acierto de caché para la rama de conocimiento**. Con modelos distintos serían dos llamadas al proveedor por consulta, sobre un presupuesto de recuperación que C16 dejó en 2.500 ms provisionales y que ya se estira en una de cada cuatro llamadas.
- Los parámetros de construcción HNSW (`m`, `ef_construction`) son los mismos y **se declaran explícitamente** en la migración, como el requisito exige. A 161 fragmentos ninguno importa; están bien como están.

**Lo que sí debe diferir, y es donde el esquema compartido falla en silencio si se comparte de más: `embedding_version`.**

`document_version_key(model)` de C11 devuelve `"<modelo>:1536:source-text/v1"`, y `source-text/v1` es la versión del **renderizador de texto de producto**. Si el indexador de conocimiento escribiera esa misma clave:

- subir `SOURCE_TEXT_VERSION` por un cambio en el texto de producto marcaría como caducado **todo el corpus de conocimiento**, que no ha cambiado — desperdicio, molesto pero visible;
- y al revés, que es el fallo grave: **cambiar las reglas de troceado no subiría `source-text/v1`**, así que cada fragmento conservaría una versión que dice describir un texto que ya no existe. La comprobación de caducidad respondería «al día» sobre vectores calculados a partir de otro texto. Silencioso, exactamente el modo de fallo contra el que `ai-vector-schema` protege en la clase de operador.

**Decisión**: misma tabla, mismo modelo, misma dimensión, mismo operador; y **una clave de versión propia, `knowledge/v1`**, calculada **dentro del paquete `knowledge/`** y escrita en la columna `embedding_version` que ya existe. `indexing/embeddings.py` no se toca. `model_version_key(model)` —sin versión de preprocesado— sigue siendo compartible y no se duplica.

**Consecuencia**: `ai-vector-schema` **no necesita delta**. Ninguna de sus frases queda falsa: este change consume sus garantías y no altera ni una columna, ni un índice, ni una restricción.

### D1. Ninguna ruta HTTP; la búsqueda es función de librería

El único consumidor es C30, en el mismo proceso Python. Añadir `POST /v1/knowledge/search` movería un contrato congelado y obligaría a coordinar con el lado .NET **para conectar dos módulos del mismo proceso**.

*Alternativa considerada*: exponer la ruta «para poder probarla desde fuera». Se resuelve con un subcomando de CLI, que es lo que ya hizo C22 con `sync-pos` — una sincronización que nadie llama por HTTP no necesita ruta.

### D2. Ningún router de consultas; decide el llamante

S10 ordena las soluciones por coste y coloca la primera en *«el mejor router es no tener router: el destino suele estar implícito en el contexto de quien pregunta»*. Aquí el diseño §9.1 ya asignó la decisión: `consultar_conocimiento` es una tool del agente de venta. C23 entrega el callable; C30 y C31 deciden cuándo llamarlo.

*Alternativa considerada*: recuperar conocimiento en toda búsqueda y dejar que el generador lo use o no. Añade una llamada al proveedor y latencia a **todas** las consultas para servir a una minoría.

### D3. Identidad determinista del fragmento, y un identificador de cita legible

- `knowledge_document.id = uuid5(NS, document_slug)`
- `knowledge_chunk.id = uuid5(NS, f"{document_slug}#{section_slug}")`
- `metadata.citation_id = "<document_slug>#<section_slug>"` — lo que viaja al consumidor.

S11 exige tres propiedades: *resuelve, localiza, es trazable*. Un `uuid4` cumple la primera, y solo a través de la base de datos. Con el corpus en git, el `citation_id` **es** el localizador: alguien abre `data/knowledge/material-plata.md`, busca `## Cuidados y limpieza` y comprueba la afirmación. Es la forma más fuerte de verificabilidad que el apunte describe, y aquí sale gratis.

*Alternativa considerada y rechazada*: `(document_id, chunk_index)`, que ya es único por restricción. **Insertar una sección en medio del documento desplaza el índice de todas las posteriores y repunta silenciosamente cada cita**, sin error y sin cambio visible. Es el peor fallo posible en un sistema de atribución.

`chunk_index` se sigue escribiendo, porque la restricción de unicidad lo exige y ordena los fragmentos dentro del documento. Simplemente **no es identidad de cita**.

### D4. Alcance de la afirmación por sección, no procedencia por documento

Dos ejes, y solo uno varía hoy:

| Eje | Pregunta | ¿Varía? | Dónde vive |
|---|---|---|---|
| Quién lo escribió | ¿LLM o el negocio? | **No.** Todo LLM más revisión | Sidecar `.meta.json` y README |
| De quién es el hecho | ¿Del mundo o de esta joyería? | **Sí, dentro de un mismo documento** | `metadata.claim_scope`, por sección |

El §8.1.1 ya enseñó la lección cuando el export real obligó a partir `data_origin` de `text_provenance`: una sola columna *«respondía a dos preguntas independientes y se rompía»*. Una constante repetida 161 veces no informa de nada por fila; su sitio es el sidecar. El alcance **sí** varía y **sí** cambia el comportamiento: un fragmento `general` se puede leer a un cliente, uno `establecimiento` no sin confirmarlo.

La prueba de que la unidad es la sección y no el documento está medida: en la ficha de tallas, *«la letra se aplica a pendientes, colgantes, collares y pulseras»* se comprueba contra los datos con un comando, y *«una `M` de anillo equivale a 54 mm»* es un compromiso inventado. Mismo documento, dos estatus.

*Alternativa considerada*: un tercer valor, `catalogo`, para las afirmaciones verificables contra los propios datos. Se descarta porque **no cambia el comportamiento** —se presentan igual que `general`— y una etiqueta que no cambia el comportamiento es decoración. Esa cualidad se registra donde ya tiene sitio: un `source_ref` opcional que nombra el comando que la re-mide.

### D5. Troceado por secciones, sin solape, con los títulos dentro del contenido indexado

- Una sección `##` = un fragmento. Sin solape: las secciones son autocontenidas por regla de autoría, y solapar fragmentos de 100 palabras duplicaría medio corpus.
- `content = "# <título del documento>\n## <título de la sección>\n\n<texto>"`.

Lo segundo es la decisión que más rinde y la menos obvia. `tsv` es **columna generada sobre `content`**, así que meter los dos títulos dentro del contenido los mete a la vez en el índice léxico y en el embedding. Es lo único que desambigua nueve fichas de material con el mismo esqueleto, el mismo registro y el mismo vocabulario, y no cuesta nada.

La marca de `claim_scope` se retira **antes** de construir `content`, para que no entre ni en el vector ni en la `tsvector`.

### D6. Los dos índices nunca se fusionan

Un producto es una entidad que se ordena y se hidrata; un fragmento es una afirmación que se cita. S10 advierte que las puntuaciones de colecciones distintas no son comparables y que *«muchas veces la respuesta correcta es no fusionar… la procedencia es información, y perderla en la fusión es perderla para siempre»*. Fusionarlos daría un ranking donde «ficha del níquel» compite con un anillo concreto, que no significa nada.

### D7. Búsqueda híbrida por RRF, importando el módulo de C21 — y medida antes de quedarse

Rama vectorial (k-NN coseno) más rama léxica (`tsquery` compuesta desde los grupos de C20), fusionadas con `retrieval/fusion.py` **sin reescribir una línea**: el módulo es puro, no abre sesión, no llama a proveedor y no sabe qué es un producto.

El argumento técnico es específico de este corpus: las nueve fichas de material son **estructuralmente idénticas**, y lo único que las distingue es el nombre del material, un token léxico corto ahogado en prosa compartida. El coseno colapsa por homogeneidad, que es la cara opuesta de la degradación por mezcla que describe S10.

**Pero se mide antes de darlo por bueno.** C20, C21 y C22 refutaron su propia ficha con medición; aquí se registra la predicción de antemano —*vectorial puro confundirá `plata` con `acero` en preguntas de cuidados*— y si el híbrido no mueve el número, **la rama léxica se retira** y el informe lo dice.

**Medido el 2026-09-06 al umbral calibrado de 0,81: la rama se queda.** Híbrido **Recall@3 78,1 %** (25 de 32) y **MRR 0,729**; vectorial solo **71,9 %** (23 de 32) y **0,688**. Diferencia **+6,2 pp y +0,042**, y la abstención es del 100 % en las dos configuraciones, de modo que la rama léxica gana recall **sin** costar abstención — que es exactamente lo que no se podía dar por supuesto.

Las dos preguntas que el híbrido recupera y el vectorial pierde son `material-cuero` y `material-resina`, dos de las cuatro fichas compactas: las de los materiales con menos surtido, cuyo texto es más corto y comparte esqueleto con las demás. Es la predicción registrada, cumplida en el sitio donde más apretaba.

**El coste es pequeño y está medido**: sobre PostgreSQL con el corpus indexado, la rama léxica añade unos 3 ms a una consulta en caliente (p50 60,7 ms frente a 57,7 ms).

*Alternativa considerada*: filtro duro por el material que la expansión resuelva en la consulta. Rechazada por el principio que la spec viva `query-expansion` ya fija —los filtros por regla *degradan, nunca excluyen*—: «¿puedo llevar plata y acero juntos?» nombra dos.

### D8. Umbral de abstención propio, calibrado y no elegido

`JPV_KNOWLEDGE_DISTANCE_THRESHOLD`, separado de `JPV_RETRIEVAL_DISTANCE_THRESHOLD` (0,65), que se calibró sobre documentos de producto de 40-120 palabras. Los fragmentos de conocimiento son prosa más larga y su distribución de distancias es otra.

**Regla de calibración**, no número a ojo: el valor **más estricto** que mantiene en cero las preguntas fuera de dominio sin perder ninguna de las que sí tienen respuesta en el corpus. Se fija con la mini-medición de D10 y se escribe aquí antes de mezclar.

**Calibrado el 2026-09-06: `JPV_KNOWLEDGE_DISTANCE_THRESHOLD = 0,81`.** Sustituye al 0,65 provisional de productos. Barrido sobre las 32 preguntas del fixture más 5 fuera de dominio, con `python -m jbg_ai.knowledge calibrate`:

| Umbral | Recall@3 | MRR | Abstención | Citas fuera de dominio |
|---|---:|---:|---:|---:|
| 0,70 | 31,2 % | 0,297 | 100 % | 0 |
| 0,75 | 59,4 % | 0,578 | 100 % | 0 |
| 0,78 | 71,9 % | 0,703 | 100 % | 0 |
| **0,81** | **78,1 %** | **0,729** | **100 %** | **0** |
| 0,83 | 78,1 % | 0,729 | 100 % | 0 |
| 0,84 | 78,1 % | 0,729 | 80 % | **1** |
| 0,90 | 78,1 % | 0,734 | 20 % | 4 |

La regla, tal como está escrita, es una **conjunción que ningún valor satisface**: el recall se agota en el 78 % mucho antes de que se rompa la abstención, así que leída al pie de la letra no calibraría nada. Se aplica por lo que significa: **cero citas fuera de dominio es una restricción**, no un término que se negocie contra el recall; dentro de esa banda se maximiza Recall@3; y **los empates los gana el valor más estricto**, que es la palabra que la propia regla usa. Aflojar de 0,81 a 0,83 no responde ni una pregunta más, y a partir de 0,84 empieza a citar lo que no debe.

**El número es provisional de otra manera, y hay que decirlo.** La especificación exige que la medición corra *offline*, sin llamar a ningún proveedor, así que el barrido usa el embebedor determinista de `knowledge/offline.py`, que puntúa solape léxico y no significado. Lo que queda calibrado es **la regla**; el **número** hay que volver a medirlo contra el embebedor de producción sobre un índice real antes de que C30 lo ponga delante de un cliente. Es una verificación posterior declarada, no un supuesto.

Por debajo del umbral: **cero fragmentos**. Para una pregunta que el corpus no cubre, la respuesta correcta es ninguna cita — y C30 depende de eso para no tener con qué inventar una atribución.

### D9. Paquete propio `jbg_ai/knowledge/` — desviación declarada de la ficha

La ficha asigna zona `data/` e `indexing/`, y a la vez pide `test_knowledge_search_returns_chunk_with_citation_id`: el change es dueño de **ingesta y consulta**.

| Opción | Problema |
|---|---|
| Todo en `indexing/knowledge.py` | Mete la ruta de consulta en el paquete de indexación |
| Partido entre `indexing/` y `retrieval/` | Pisa la zona de C25 y C26, que trabajan los dos en `retrieval/` |
| **Paquete `knowledge/`** | Ninguno, y es la convención del repo: `enrichment/`, `families/`, `retrieval/` son paquetes por capacidad |

`corpus.py` (carga y validación), `chunking.py` (troceado puro), `indexer.py` (persistencia y embeddings), `search.py` (consulta). La superficie de roce con otros changes queda en **un subcomando de `indexing/cli.py` y dos imports**.

### D10. Mini-medición propia, sin las tablas de C24

~32 preguntas —una por documento— más 4-5 **fuera de dominio** que deben devolver cero, en fixture versionado. Salida: Recall@3, MRR y tasa de abstención, más la comparación vectorial-solo contra híbrido.

**Sin tocar `ai.eval_run` / `eval_case` / `eval_result`**: las crea C24, y usarlas convertiría a C24 en prerrequisito, con lo que C23 dejaría de ser el change libre que hoy es. Cuando C24 exista podrá absorber el fixture.

### D11. Idempotencia y ciclo de vida

Upsert por documento; los fragmentos que una ejecución no produce **se borran**; borrar un documento arrastra los suyos por la clave foránea, sin lógica de aplicación. Se re-embebe solo si `metadata.content_hash` cambió o si `embedding_version` no coincide.

`content_hash` va **en `metadata`**, no en columna nueva: `knowledge_chunk` no la tiene, y este change declara cero migraciones. Es exactamente el episodio que C22 protagonizó al declarar «sin migración de ninguna clase» y acabar abriendo una revisión aditiva; aquí el `jsonb` con su GIN ya da la salida.

### D12. Cobertura derivada del vocabulario, no elegida a mano

Una ficha por término canónico de `materials` en `vocabularies.yaml`. Convierte la cobertura en **invariante testeable**: si entra `titanio` en el vocabulario, el test pide su ficha. La profundidad sí varía con la frecuencia medida —`plata` 630 productos frente a `cuero` 1—, y eso es una decisión, no un descuido.

Las ocho piedras del vocabulario **sin una sola aparición** en el catálogo no reciben sección: el corpus describe el surtido que existe.

### D13. Cero documentos `guion_venta`

**No es un corte de alcance.** Un guion de venta es texto **imperativo**, y un fragmento imperativo recuperado dentro de un prompt es indistinguible de una instrucción: haría del propio corpus una superficie de inyección, con C31 (guardrails) todavía sin existir. La línea:

> el corpus guarda **hechos para citar**; el prompt guarda **instrucciones para obedecer**.

El tono comercial va a `ai-service/prompts/`, versionado e iterable, que es donde el §11.6 ya lo pide.

### D14. Tamaño de sección: 1.200 caracteres, y por encima falla la ingesta

En el espíritu del tope de 1.000 caracteres que C06b ya aplica al copy sintético. **El código no trocea por su cuenta**: parte el autor, que es quien sabe dónde acaba una afirmación. Un troceado automático produciría fragmentos sin encabezado propio, o sea sin localizador.

### D15. El corpus se genera por bloques, en ventanas separadas

161 secciones de 80-250 palabras son ~25.000 palabras de salida, más las reglas de autoría, el esqueleto y la evidencia medida **en cada petición**. De una sola vez, las primeras fichas se olvidan y las últimas derivan del esqueleto: se pierde la homogeneidad que hace comparables a nueve fichas de material, y las invariantes lo cazarían tarde y caro.

**Ocho encargos, uno por bloque, cada uno en su subagente o ventana nueva.** Nunca el corpus entero; nunca un documento suelto por encargo, porque partir por documento perdería la coherencia interna del bloque. Un prompt versionado **por bloque**, con las reglas completas y no resumidas. Revisión humana bloque a bloque según llega.

### D16. La convención de talla de anillo de la casa

Era la última pregunta genuinamente abierta. Se cierra con criterio de oficio sobre la evidencia del catálogo, en lugar de dejar el documento de tallas flotando en lo ilustrativo.

**Lo que la escala del catálogo es, y lo que no.** `XS`/`S`/`M`/`L`/`XL` **no es ningún sistema normalizado de talla de anillo**. No es la española (número), ni la ISO 8653 (circunferencia en milímetros), ni la estadounidense (número), ni la británica (letras `A`–`Z`, donde `L`, `M` y `N` sí son tallas pero `XS` y `XL` no existen). Es una **escala de prenda**, aplicada a todo el catálogo por igual — la medición lo confirma: la letra viaja en pendientes, colgantes, collares, pulseras y anillos, y el tipo que más la usa es `pendientes`, que no tiene ajuste.

Y para este negocio es la elección correcta, no un descuido: la red de puntos de venta son **hoteles y aeropuerto de Menorca**. Quien compra allí no vuelve a por un ajuste, no sabe su talla española y a menudo compra para regalar. Una escala de cuatro o cinco peldaños, generosa y bien documentada, sirve a ese canal mejor que veinte números que nadie recuerda.

**La convención, entonces, tiene tres capas** y cada una con su alcance:

1. **La letra mide la pieza, en todo el catálogo.** Una capa, no dos: la joyería no mantiene dos sistemas de etiquetado.
2. **El anillo es la única pieza donde la letra además compromete un ajuste**, y por eso es la única con tabla de equivalencia. Se expresa en **tallas españolas enteras, tres por letra, sin solape**:

   | Letra | Talla española | Circunferencia interior | Diámetro interior |
   |---|---|---|---|
   | `XXS` * | 4 – 6 | 44 – 46 mm | 14,0 – 14,6 mm |
   | `XS` | 7 – 9 | 47 – 49 mm | 15,0 – 15,6 mm |
   | `S` | 10 – 12 | 50 – 52 mm | 15,9 – 16,6 mm |
   | `M` | 13 – 15 | 53 – 55 mm | 16,9 – 17,5 mm |
   | `L` | 16 – 18 | 56 – 58 mm | 17,8 – 18,5 mm |
   | `XL` | 19 – 21 | 59 – 61 mm | 18,8 – 19,4 mm |
   | `XXL` * | 22 – 24 | 62 – 64 mm | 19,7 – 20,4 mm |

   \* `XXS` y `XXL` son **por encargo y no de surtido**, que es exactamente lo que la medición encontró: los dos únicos peldaños del vocabulario **con cero apariciones** en 1.200 productos. La convención los explica en vez de fingir que no existen.

3. **La aritmética es estándar y la asignación es de la casa.** `circunferencia (mm) = talla española + 40` es la regla española de toda la vida y el diámetro se deriva de la circunferencia: comprobable fuera, luego **`general`**. Que `M` sean las tallas 13-15 y no las 12-14 es una decisión del establecimiento, luego **`establecimiento`**. Es el mejor ejemplo del corpus de por qué el alcance se declara por sección y no por documento (D4).

**Reglas de oficio que modulan la elección** (todas `general`, y todas de las que un joyero responde a diario):

- Una **banda ancha** —más de 6 mm— calza más prieta: se sube una talla española.
- **Nudillo marcado**: se elige por el nudillo y se sube una talla; con bolas de ajuste el aro no gira después.
- Se mide **al final del día y a temperatura normal**, nunca tras el baño en agua fría. **En verano el dedo varía hasta una talla entera**, que es precisamente el caso de esta red de puntos de venta.
- **Entre dos tallas, se sube.** En verano, siempre.

**Y qué se puede ajustar y qué no**, que es la mitad que convierte la escala gruesa en algo defendible:

- **Ajustable ±2 tallas**: aro liso, o con labrado parcial, en plata u oro.
- **No ajustable**: alianza con piedras en todo el contorno; aro cuyo motivo recorre la banda entera, porque el dibujo se rompería; aro hueco; **cualquier pieza con baño de oro**, porque el ajuste quema el baño y obliga a rebañarla; y latón y acero, que en la práctica no se ajustan.

Esto **ata tres documentos entre sí**: la tabla vive en `tallas-anillos`, el límite por material sale de las fichas de `material-bano-de-oro`, `material-laton` y `material-acero`, y el servicio lo recoge `politica-reparaciones-y-ajustes`. Los tres deben decir lo mismo, y el catálogo respalda que ese servicio existe: `Composturas` es una de las 28 «colecciones» reales, con 19 productos.

*Alternativa considerada*: adoptar la talla española numérica y abandonar las letras. Rechazada por dos motivos, y ninguno es de gusto. Uno, **contradiría el catálogo**: los productos ya están etiquetados con letras y cambiarlo sería un reetiquetado del surtido, muy fuera de este change. Dos, la letra **también** etiqueta pendientes, colgantes y pulseras, donde una talla numérica no significa nada — se perdería la escala única que el catálogo sí tiene.

*Alternativa considerada*: adoptar la escala británica de letras, que sí es un estándar de anillo. Rechazada porque `A`–`Z` con medias tallas es más fina que `XS`–`XL`, no coincide con las letras que el catálogo usa, e induciría a error a quien conozca el sistema británico de verdad: allí una `M` es 52,5 mm y aquí sería un tramo de 53 a 55.

### D17. El corpus no cuenta el catálogo — la mitad de la regla 5 que apareció al escribirlo

**Descubierta durante el apply, y es una decisión de diseño, no una corrección de estilo.**

Las ocho peticiones de generación llevan la evidencia medida de su bloque —productos por material, pares multi-material, el cruce `piece_type × size_label`, los topónimos— porque es lo que justifica **qué** documentos existen y con **cuánta** profundidad. Los documentos generados hicieron lo natural: citarla. Cuatro secciones acabaron diciendo cosas como *«`pequeño` encabeza con 108 etiquetas»* o *«el 44,6 % del surtido no depende de talla»*.

**Y eso convierte al corpus en una foto del catálogo de hoy.** Entra un producto de oro, se agota el último zafiro, y una sección queda falsa — **en silencio**, que es lo grave: la cita sigue resolviendo y sigue localizando, así que el mecanismo de verificación la sella como comprobada. Es la misma familia de fallo que D3 evita con la identidad determinista y que el §2 del contexto describe: *una cita bien formada sobre algo falso es peor que no citar*. El corpus de conocimiento y el índice de catálogo tienen ritmos de cambio distintos **a propósito**; atarlos por una cifra los sincroniza sin que nadie lo haya decidido.

**Decisión: la regla 5 tiene dos mitades y la ingesta comprueba las dos.** Ni SKU, producto o precio; **ni recuento ni proporción del surtido**. Se rechazan `144 piezas`, `1.168 productos`, `veintiocho colecciones`, `el 24,4 % del catálogo`. Lo que se escribe es la forma duradera del hecho —*la mayoría*, *buena parte*, *a bastante distancia*, *la excepción*—, que es además mejor prosa de mostrador.

**El detector lee el vecindario, no el símbolo.** Prohibir el porcentaje a secas habría borrado mineralogía legítima: *«el ópalo lleva entre un tres y un diez por ciento de agua»* seguirá siendo verdad dentro de veinte años. Un porcentaje solo cae si está a menos de cuarenta caracteres de un sustantivo que cuenta catálogo (`productos`, `piezas`, `fichas`, `colecciones`, `surtido`, `índice`). Y los numerales escritos con letra cuentan **a partir de once**: *«dos piezas de oro que comparten cajón se rayan»* es prosa corriente, *«veintiocho colecciones»* es un censo.

*Alternativa considerada*: dejarlo como regla de estilo en la guía de autoría, sin comprobación. Rechazada por lo mismo que las otras seis: el corpus lo escriben ocho encargos distintos en ocho ventanas distintas, y una regla que solo vive en la prosa del prompt se cumple siete veces de ocho. Las cuatro secciones que la incumplieron habían recibido la evidencia medida **y** la instrucción de no copiarla no existía todavía; ahora existe en los ocho prompts, en la guía de autoría y en el validador.

**Consecuencia sobre la spec**: el requisito de conocimiento general gana la cláusula y tres escenarios, incluido el que enuncia la propiedad de verdad —*añadir o retirar un producto no invalida ningún documento*—. Sin él, la spec viva describiría un corpus que sí se puede romper desde el catálogo.

## Risks / Trade-offs

- **[La cita bien formada sobre un corpus inventado — el riesgo estructural del change]** → `claim_scope` por sección, sidecar que sella cómo se generó, y limitación explícita en el README: la verificación de citas es estructural y no garantiza la verdad de lo citado. **No desaparece**, se declara.
- **[Un compromiso de la casa leído a un cliente como si fuera un hecho]** → `claim_scope` viaja con cada fragmento y C30 está obligado a propagarlo. El bloque de servicio es íntegramente `establecimiento`, de modo que el mecanismo se demuestra desde el primer documento.
- **[Deriva del corpus si se genera en una sola ventana]** → D15: ocho encargos, prompts por bloque, revisión incremental.
- **[La rama léxica añadida por intuición y no por evidencia]** → D7: se mide vectorial solo primero y se retira si no mueve el número.
- **[Reindexar rompe las citas]** → D3: identidad determinista, más un test que comprueba que cada `citation_id` indexado resuelve a un fichero y a un encabezado del repositorio.
- **[Compartir `embedding_version` con el texto de producto]** → D0: espacio de versiones propio, `knowledge/v1`. Sin él, cambiar el troceado dejaría vectores caducados que se declaran al día.
- **[Que alguien «aproveche» para abrir `/v1/knowledge/search`]** → D1, y la definición de hecho exige `openapi.json` **sin diff**.
- **[Las cifras del informe son un proxy sobre texto, no los atributos extraídos]** → tarea de re-medición contra `ai.product_document` con la base levantada; afecta a `oro` (absorbe los de baño), `perla` (contada dos veces) y `pequeño`/`grande`/`mediano` (inflados por prosa). Tres documentos citan esas cifras.
- **[Latencia añadida a la ruta de venta]** → la consulta solo se dispara cuando el agente la pide, y comparte modelo, cliente y caché con la rama de productos (D0). **Medida** sobre PostgreSQL con los 161 fragmentos indexados, en caliente y sobre cinco preguntas: **p50 60,7 ms y p95 67,0 ms** con las dos ramas, frente a p50 57,7 ms sin la léxica — es decir, la rama léxica cuesta unos **3 ms**. Excluye el embebido de la pregunta, que comparte cliente y caché de proceso con la rama de productos. C30 hereda ese número y el presupuesto de recuperación de C16 (2.500 ms) no se toca.

## Migration Plan

**Ninguna migración, ni de Alembic ni de EF Core.** Las dos tablas existen desde C05 con su forma final, y todo campo que falta vive en `metadata jsonb`, que ya tiene su índice GIN.

Despliegue: indexar el corpus es ejecutar la CLI, y es idempotente. **Reversión**: no indexar, o borrar las filas de las dos tablas de conocimiento — ninguna otra parte del sistema las lee todavía, así que revertir no puede degradar nada en producción. El corpus vive en git, de modo que reconstruir el índice desde cero es un comando.

## Open Questions

Las cuatro que el ticket dejó abiertas quedan **resueltas con su opción por defecto** el 2026-09-06:

| # | Pregunta | Resolución |
|---|---|---|
| 1 | Valor de `JPV_KNOWLEDGE_DISTANCE_THRESHOLD` | **Calibrado el 2026-09-06 en 0,81** (D8). Recall@3 78,1 %, MRR 0,729, abstención 100 %; las citas fuera de dominio empiezan en 0,84 y aflojar de 0,81 a 0,83 no responde ni una pregunta más. Medido con el embebedor *offline* que la spec exige, así que la **regla** queda calibrada y el **número** hay que revisarlo contra el proveedor real |
| 2 | ¿Se queda la rama léxica? | **Se queda, y por medición** (D7): **+6,2 pp de Recall@3** y **+0,042 de MRR** frente a vectorial solo, con la misma abstención del 100 % y unos 3 ms de coste. Recupera precisamente las dos fichas compactas que el vectorial pierde |
| 3 | Tope de tamaño de sección | **1.200 caracteres** (D14), revisable con el corpus real delante |
| 4 | ¿`ai-vector-schema` necesita delta? | **No** (D0). Leídos sus quince requisitos: seis tocan el corpus y este change los **consume** sin alterar columna, índice ni restricción. Si durante el apply apareciera una frase que queda falsa, se emite el delta antes de archivar — una spec viva bien formada y mentirosa es el fallo de agosto |

La quinta —**qué convención de talla de anillo usa la joyería**— era la única genuinamente abierta y **queda cerrada en D16** el 2026-09-06, con criterio de oficio sobre la evidencia del catálogo: la letra mide la pieza en todo el surtido, el anillo es el único tipo con tabla de equivalencia, y esa tabla son **tres tallas españolas enteras por letra, sin solape**, con `XXS` y `XXL` reservadas para encargo porque son los dos peldaños del vocabulario que el catálogo no usa. La aritmética (`circunferencia = talla + 40`) es `general` y la asignación de letras a tramos es `establecimiento`.

No queda ninguna pregunta que bloquee. Quedan **dos verificaciones posteriores**, que no es lo mismo — ninguna de las dos impide archivar:

- **Confirmar la tabla de tallas con el negocio antes del vídeo de la demo.** Si la joyería usa otros tramos, cambia **una** sección de **un** documento —`tallas-anillos#nuestra-escala-de-letras-que-talla-es-cada-una`— y su marca `establecimiento` ya la señala como compromiso de la casa y no como hecho. El test de coherencia aritmética seguirá comprobando los tramos nuevos igual que los de hoy. Si además aportara sus textos comerciales, el eje «quién lo escribió» dejaría de ser constante y ganaría su campo, de forma aditiva y sin migración (D4).
- **Re-calibrar `JPV_KNOWLEDGE_DISTANCE_THRESHOLD` contra el embebedor de producción** sobre un índice real, antes de que C30 exponga la tool. La spec obliga a que la medición corra sin proveedor, así que el 0,81 sale del embebedor determinista de `knowledge/offline.py`, que puntúa solape léxico y no significado: lo que queda calibrado es **la regla**, y el **número** hay que confirmarlo. Es un ajuste de entorno, sin cambio de código y sin reindexar.
