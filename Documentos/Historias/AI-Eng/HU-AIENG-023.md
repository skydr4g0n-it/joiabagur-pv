# HU-AIENG-023: Corpus de conocimiento comercial e índice de citas verificables — lo que la joyería sabe, troceado, citable y con el alcance de cada afirmación declarado

## Formato estándar

**Como** Operador de un punto de venta de la joyería,
**quiero** que el asistente sepa responder con **conocimiento de la casa** —si una pieza se puede mojar, si lleva níquel, qué mide una talla `M`, qué cubre la garantía— y que **diga de dónde lo saca**,
**para** dejar de improvisar delante del cliente y, sobre todo, para no comprometer a la joyería con una respuesta que nadie ha aprobado.

---

## Descripción

El sistema tiene hoy **un solo índice**: `ai.product_document`, una fila por producto, sin trocear. Responde bien a «enséñame anillos de plata», y no puede responder a «¿este anillo se puede mojar?», porque esa respuesta no está en ningún producto: está en el conocimiento general de la joyería, que **no existe en el sistema**.

El §5 del diseño lo dice con precisión: *«no hay documentos largos que trocear»* en el catálogo, pero *«sí hay un segundo corpus con forma de documento: conocimiento comercial general —materiales y alergias, equivalencias de talla, políticas—, **general, no por producto**, que es exactamente lo que la revisión pide evitar. Ese sí se trocea y es lo que permite citas verificables»*.

Esta historia construye ese segundo índice: el corpus, su troceado, su indexación y su búsqueda con citas. Es **habilitadora**: quien la pone delante del operador es C30, que la consume como la tool `consultar_conocimiento` del agente de venta (§9.1 del diseño).

### El problema que gobierna la historia: una cita que resuelve no es una cita que sea cierta

El apunte de S11 lo formula sin rodeos: la integridad referencial es **estructural, no semántica**. Comprueba que el fragmento citado estuvo en el contexto recuperado; **no comprueba que diga lo que se le atribuye**. *«Una citación que apunta a una fuente real pero que esa fuente no respalda es una alucinación con coartada.»*

Y aquí el riesgo es más agudo, porque **el corpus lo escribe un LLM**: el §8.1 daba los textos comerciales de la joyería como *«a pedir al negocio»*, el mismo estado en el que estaban las fotografías, que nunca llegaron. Un corpus inventado puede pasar el 100 % de la verificación de citas y estar citando algo falso **con sello de verificado**, que es estrictamente peor que no citar.

La salida no es fingir que el corpus es real: es **distinguir dos clases de afirmación**, que no se rompen igual.

| Clase | Ejemplo | ¿Lo sabe un LLM? | Riesgo real |
|---|---|---|---|
| Hecho del mundo | «la plata de ley se oscurece por sulfuración»; «el níquel es el alérgeno de contacto más frecuente» | Sí, razonablemente | Detalles plausibles pero falsos |
| Hecho de **esta** joyería | el plazo de devolución; qué contorno es una `M` de anillo | **No, en absoluto** | El operador lee a un cliente **un compromiso inventado, con cita** |

### Lo que la exploración del 2026-09-06 midió, y que reencuadra la ficha

Mediciones completas en [c23-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c23-exploration-measurements.md), sobre los 1.200 productos de los dos corpus JSONL versionados.

**1. El corte pre-autorizado se expresó en la unidad equivocada.** La ficha pedía 30-45 documentos y el §13.4 del plan bajó el alcance a **15, aplicados desde el principio del change**. Pero la cifra que el diseño fija en D5 está **en chunks: 150-250**. Quince documentos dan ~80 chunks — la mitad del objetivo, y con un índice tan pequeño **la abstención no se puede demostrar**: cualquier pregunta cae cerca de algo. Se entregan **32 documentos ≈ 161 chunks**, que es el centro de D5. El corte no se ignora: se refuta por su propia unidad de medida.

**2. La letra de talla del catálogo no es una talla de dedo.** El cruce `piece_type × size_label` lo demuestra: el tipo de pieza que **más** etiquetas de talla lleva es `pendientes` (S 30, M 25, L 18, XL 20, `mini` 12), que no tiene talla en el sentido de ajuste; y la escala se aplica igual a `colgante`, `collar`, `pulsera` y `anillo`. La letra mide **el tamaño de la pieza**. El documento de medidas deja de ser «inventar una tabla de milímetros» y pasa a describir una convención que los datos demuestran. La escala de anillo se **fija** en la decisión 15 —tres tallas españolas enteras por letra, con `XXS` y `XXL` por encargo, que son justo los dos peldaños del vocabulario con cero apariciones—; de todo el documento, lo único ilustrativo es **la asignación de letras a tramos**, y va marcada.

**3. Las colecciones llevan nombre de calas y cabos reales de Menorca — y esto corrige a la propia exploración.** La primera pasada descartó un documento sobre Menorca con el argumento de que *«describe el catálogo, y el catálogo ya está indexado»*. La medición lo desmiente: de las 28 colecciones reales, `Es Caló Blanc` (31), `Biniacolla` (26), `Sa Mesquida` (23), `Cala Pregonda` (20), `Cala Presili` (19), `Binibeca` (14) y `Cavalleria` (12) son topónimos verificables, más `Menorca` (70) y `Fiestas Menorca` (15). Lo inventado sería atribuir a cada línea una intención de diseño, y eso queda aislado en **una sola sección** marcada como afirmación de la casa.

**4. Once de las 28 «colecciones» no son líneas de diseño**, sino cajones operativos: `Varios`, `Composturas` (19 productos, o sea reparaciones), `Tienda`, `Aros plata`, `Anillos`, `Pedida`, `Kit Huella`, `Cursos`, `Maternidad`, `Melia`, `Papelería`, `Envío`. Hallazgo de calidad de catálogo que no se buscaba. `Composturas` confirma **desde los datos** que el servicio de reparación existe.

**5. El reparto de materiales es muy desigual y la profundidad no puede ser uniforme.** `plata` 630 · `oro` 418 · `latón` 77 · `hilo` 63 · `baño de oro` 36 · `perla` 8 · `resina` 4 · `acero` 3 · `cuero` 1. La invariante «una ficha por canónico» se mantiene —es lo que hace la cobertura *testeable* en vez de opinable— pero cuatro materiales con menos de diez productos no sostienen seis secciones.

**6. Las dos piedras más frecuentes son materia orgánica, y ocho canónicos están vacíos.** `coral` 102 y `ámbar` 75 encabezan la lista, y son la categoría de cuidado más frágil. `malaquita`, `howlita`, `aventurina`, `ojo de tigre`, `piedra luna`, `amazonita`, `jaspe` y `calcedonia` **no aparecen en ningún producto** y no reciben sección: el corpus describe el surtido que existe, no el vocabulario que podría existir.

**7. La ficha declara zona solo de indexación, y pide un test de búsqueda.** `test_knowledge_search_returns_chunk_with_citation_id` está en la propia ficha: el change es dueño de **los dos lados**, ingesta y consulta.

**8. Nada de esto necesita migración.** `ai.knowledge_document` y `ai.knowledge_chunk` existen desde C05 con `doc_type` restringido a cinco valores, borrado en cascada, único `(document_id, chunk_index)`, HNSW coseno, GIN sobre `tsv` **y sobre `metadata`**. Lo que falte va en `metadata jsonb`.

### Alcance de esta historia (sí)

- **Corpus de 32 documentos Markdown** versionados en `data/knowledge/`, ~161 secciones, con el desglose cerrado en el §5 del informe: 9 fichas de material (una por canónico) · 2 de combinaciones y marcajes · 3 de piedras · 4 de medidas y tallas · 4 de uso y entorno · 2 de piel y seguridad · 4 de servicio · 2 de regalo · 1 glosario · 1 de Menorca y el origen de las colecciones.
- **`claim_scope` por sección**, con dos valores: `general` (comprobable fuera) y `establecimiento` (compromiso de la joyería, hoy ilustrativo). Declarado por el autor, obligatorio, y **gobierna cómo se presenta la cita**.
- **Chunking por secciones**: una sección `##` = un chunk, sin solape, con el título del documento y el de la sección **dentro de `content`**, y tope de tamaño que **falla la ingesta** en lugar de trocear por su cuenta.
- **Identidad determinista del chunk**: `uuid5` derivado de `<doc_slug>#<section_slug>`, más `citation_id` legible en `metadata`. La cita resuelve, localiza y es trazable hasta el fichero del repositorio.
- **Indexación idempotente** en `ai.knowledge_document` / `ai.knowledge_chunk`, reutilizando el cliente de embeddings de C11 **sin tocarlo**, con `content_hash` en `metadata` para no re-embeber lo que no cambió, y borrado de chunks que una ejecución ya no produce.
- **CLI** `python -m jbg_ai.indexing sync-knowledge [--full]`, en el patrón de `sync` y `sync-pos`.
- **Búsqueda de conocimiento** como función de librería: vectorial y léxica, fusionadas por RRF importando `retrieval/fusion.py`, con umbral de abstención propio y devolución de chunks con su `citation_id`, su `claim_scope` y sus títulos.
- **Mini-medición propia**: ~32 preguntas (una por documento) más 4-5 **fuera de dominio** que deben devolver cero, en fixture, con Recall@3, MRR y abstención al informe.
- **Prompts versionados** en `ai-service/prompts/knowledge/`, uno por bloque, y sidecar `.meta.json` que sella modelo, versión de prompt y recuentos por `doc_type` y por `claim_scope`.

### Fuera de alcance (no)

- **Ruta HTTP.** Nada de `/v1/knowledge/*`. La spec viva `ai-service-api-contracts` enumera los diez endpoints **en un MUST**, y el único consumidor (C30) vive en el mismo proceso Python: mover `openapi.json` y coordinar con el lado .NET para conectar dos módulos del mismo proceso no compra nada.
- **Router LLM.** El destino lo decide el llamante, que ya tiene nombre en el diseño §9.1: la tool `consultar_conocimiento`.
- **`guion_venta`.** Cero documentos. **No es un corte de alcance:** un guion de venta es texto **imperativo**, y un chunk imperativo recuperado dentro de un prompt es indistinguible de una instrucción — convertiría el propio corpus en superficie de inyección, y C31 (guardrails) todavía no existe. El tono comercial se lleva al prompt versionado, que es donde el §11.6 ya lo pide.
- **Generación con citas** (`pitch`, `citations[]`, placeholders `{{price}}`/`{{stock}}`, avisos por reglas): es **C30**. Esta historia entrega el conocimiento y su recuperación, no la redacción.
- **RAGAS y validador anti-alucinación**: §11.3, territorio de **C24**.
- **Tablas `ai.eval_run` / `eval_case` / `eval_result`**: las crea C24. Usarlas convertiría a C24 en prerrequisito y C23 dejaría de ser el 🟢 libre que es.
- **Migración de ninguna clase**, ni Alembic ni EF Core. Las dos tablas existen desde C05 y lo que falte va en `metadata jsonb`.
- **Fusionar los dos índices.** Un producto es una entidad que se ordena y se hidrata; un chunk es una afirmación que se cita. Aplanarlos en una lista destruye la procedencia, que es justo lo que S10 advierte que no se recupera después.
- **Tocar `indexing/embeddings.py`** —congelado desde C11, y su propio docstring nombra a C23 para prohibírselo—, `enrichment/vocabularies.yaml`, `retrieval/orchestrator.py`, `retrieval/search.py` ni el árbol `frontend/`.
- **Reranking**, índices nuevos, y conocimiento **por producto**: la decisión 4 de la revisión es que este corpus es general, y ninguna sección nombra un SKU, un producto ni un precio.

### Decisiones de diseño ya acordadas

| # | Decisión | Motivo |
|---|---|---|
| 1 | **Ninguna ruta HTTP**; `search_knowledge()` es función de librería | La superficie `/v1` está congelada por un MUST y el único consumidor está en el mismo proceso |
| 2 | **Ningún router LLM**: decide el llamante | S10: *«el mejor router es no tener router»*. El diseño §9.1 ya asignó la decisión a `consultar_conocimiento` |
| 3 | **Identidad doble del chunk**: `id = uuid5(NS, "<doc_slug>#<section_slug>")` y `metadata.citation_id` legible | S11 exige que la cita *resuelva, localice y sea trazable*. Con el corpus en git, el `citation_id` **es** el localizador: abre el fichero, busca el encabezado. Un `uuid4` solo resuelve, y solo a través de la base de datos |
| 4 | **Nunca `(document_id, chunk_index)` como identidad de cita** | Insertar una sección en medio desplaza el índice de todas las posteriores y **repunta silenciosamente cada cita**, sin error y sin cambio visible. Es el peor fallo posible en un sistema de atribución |
| 5 | **Híbrido vector + léxico por RRF**, importando `fusion.py`, con la rama léxica compuesta desde los grupos de expansión de C20 | Las nueve fichas de material son **estructuralmente idénticas**: mismo esqueleto, mismo registro, mismo vocabulario. El coseno colapsa, y lo único que las distingue es el nombre del material, que es un token léxico |
| 6 | **Se mide vectorial solo primero**; la rama léxica se queda solo si mueve el número | Cultura del proyecto: C20, C21 y C22 refutaron su ficha con medición. Predicción registrada de antemano: vectorial puro confundirá `plata` con `acero` en preguntas de cuidados |
| 7 | **Nada de filtro duro por material detectado en la consulta** | La spec viva `query-expansion` ya fija que los filtros por regla *degradan, nunca excluyen*. «¿Puedo llevar plata y acero juntos?» nombra dos |
| 8 | **`claim_scope` por sección**, dos valores; el **origen** del texto vive en el sidecar y en el README, no en una columna | El origen es hoy una constante —todo LLM más revisión— y una constante repetida 161 veces no informa. El alcance **sí varía dentro de un mismo documento**, y cambia el comportamiento: `general` se puede leer a un cliente, `establecimiento` no sin confirmarlo. Es la lección del §8.1.1, que ya tuvo que partir `data_origin` de `text_provenance` |
| 9 | **Umbral de abstención propio**, `JPV_KNOWLEDGE_DISTANCE_THRESHOLD` | El 0,65 de productos se calibró sobre documentos de 40-120 palabras. Para una pregunta que el corpus no cubre, **la respuesta correcta es ninguna cita**, y C30 depende de eso |
| 10 | **Paquete `jbg_ai/knowledge/`**, no `indexing/knowledge.py` — **desviación declarada de la ficha** | El change es dueño de ingesta y consulta. Meter la consulta en `indexing/` la misfila; partirla a `retrieval/` pisa la zona de C25 y C26. Los paquetes por capacidad son la convención del repo (`enrichment/`, `families/`, `retrieval/`) |
| 11 | **`content_hash` en `metadata`**, no en columna nueva | Evita repetir el episodio de C22, que declaró «sin migración de ninguna clase» y acabó abriendo una revisión aditiva |
| 12 | **Cobertura de materiales derivada de `vocabularies.yaml`**, no elegida a mano | Convierte la cobertura en una **invariante testeable**: si entra `titanio` en el vocabulario, el test pide su ficha |
| 13 | **Corpus en git**, con sidecar `.meta.json` | Es la fuente de la cita. El patrón ya existe en `data/catalog/*/generated/*.meta.json` |
| 14 | **`guion_venta` a cero**, y el tono comercial al prompt versionado | El corpus guarda **hechos para citar**; el prompt guarda **instrucciones para obedecer**. Mezclarlos hace de cada chunk recuperado una instrucción potencial |
| 15 | **La convención de talla de anillo de la casa**: la letra mide la pieza en todo el catálogo; el anillo es el único tipo con tabla de equivalencia; **tres tallas españolas enteras por letra, sin solape** (`XXS` 4-6 · `XS` 7-9 · `S` 10-12 · `M` 13-15 · `L` 16-18 · `XL` 19-21 · `XXL` 22-24), con `XXS` y `XXL` **por encargo** | `XS`–`XL` no es ningún sistema normalizado de anillo —ni el español, ni ISO 8653, ni el estadounidense, ni el británico de letras—: es una escala de prenda, y para una red en hoteles y aeropuerto es la correcta, porque quien compra allí no vuelve a por un ajuste. `circunferencia = talla + 40` es la regla española de siempre (`general`); que `M` sean las 13-15 es de la casa (`establecimiento`). Y `XXS`/`XXL` por encargo **explica** los dos únicos peldaños del vocabulario con cero apariciones en el catálogo, en vez de fingir que no existen |

**Cortes que no se reabren:** `indexing/embeddings.py` congelado desde C11 · `enrichment/vocabularies.yaml` intacto · sin migración de ninguna clase · sin ruta HTTP nueva ni regeneración de `openapi.json` · sin tocar `frontend/`, `terraform/` ni `.github/workflows/` · sin `ai.query_log` · Python no lee el esquema `public` por SQL.

**Referencias:**

- Diseño RAG [§5, §7.2, §7.7, §8.2, §8.3 (D5), §9.1 y §11.3](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — el segundo corpus, el esquema del índice, generación con citas, datasets y evaluación.
- Plan de changes, [ficha C23](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) y el corte pre-autorizado del §13.4.
- Mediciones y decisiones: [c23-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c23-exploration-measurements.md).
- Specs vivas que enmarcan el change: `openspec/specs/ai-vector-schema/` (las dos tablas ya especificadas), `openspec/specs/hybrid-fusion/`, `openspec/specs/query-expansion/`, `openspec/specs/ai-service-api-contracts/`.
- Historias previas: [HU-AIENG-011](HU-AIENG-011.md) (texto canónico y cliente de embeddings), [HU-AIENG-020](HU-AIENG-020.md) (diccionario de sinónimos), [HU-AIENG-021](HU-AIENG-021.md) (fusión híbrida), [HU-AIENG-022](HU-AIENG-022.md) (prefiltro por punto de venta).
- Apuntes: [S11 · Citación y atribución verificable](../../Sesiones%20Master%20AIEng/S11_RAG_avanzado/Citacion%20y%20Atribucion%20verificable.md), [S10 · Multi-índice y routing](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Multi-indice%20y%20routing.md), [S11 · Reindexación y versionado de embeddings](../../Sesiones%20Master%20AIEng/S11_RAG_avanzado/Reindexacion%20y%20Versionado%20Embeddings.md).
- Change: [`add-knowledge-corpus-and-indexer`](../../../openspec/changes/archive/2026-09-06-add-knowledge-corpus-and-indexer/) · ticket [T-AIENG-023](../../../openspec/changes/archive/2026-09-06-add-knowledge-corpus-and-indexer/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: Una pregunta de cuidados encuentra la ficha del material correcto

**Dado que** el corpus tiene nueve fichas de material con el mismo esqueleto de secciones y el mismo registro
**Y** que lo único que las distingue es el nombre del material
**Cuando** se consulta el conocimiento con una pregunta que nombra un material concreto —«¿se puede mojar una pulsera de plata?»—
**Entonces** el primer resultado procede de la ficha de ese material y no de la de otro
**Y** el fragmento devuelto es la sección que responde la pregunta, no el documento entero
**Y** el resultado viaja con el título de su documento y el de su sección

### Escenario 2: La cita resuelve, localiza y llega hasta el fichero

**Dado que** una cita que un humano no puede resolver y un sistema no puede verificar no es una cita
**Cuando** la búsqueda devuelve un fragmento
**Entonces** lleva un identificador de cita legible que nombra el documento y la sección de la que sale
**Y** ese identificador corresponde a un fichero y a un encabezado que existen en el corpus versionado
**Y** el fragmento indica también el documento del que procede, de modo que la trazabilidad no depende de consultar la base de datos

### Escenario 3: Una afirmación de la casa no se confunde con un hecho del mundo

**Dado que** el corpus mezcla hechos comprobables fuera —química de los metales, alérgenos, longitudes— con compromisos que solo la joyería puede confirmar —plazos, garantía, equivalencias de talla propias—
**Y** que hoy los segundos son ilustrativos
**Cuando** la búsqueda devuelve un fragmento
**Entonces** el fragmento declara a cuál de las dos clases pertenece
**Y** la clase se declara **por sección**, de modo que un mismo documento puede tener secciones de las dos
**Y** un consumidor puede presentar de forma distinta lo que se puede afirmar y lo que no

### Escenario 4: Una pregunta que el corpus no cubre no devuelve ninguna cita

**Dado que** para una pregunta fuera del dominio la respuesta correcta es ninguna cita, y no la cita menos mala
**Y** que el umbral de conocimiento es propio y no el que se calibró para productos
**Cuando** se consulta algo que el corpus no trata
**Entonces** no se devuelve ningún fragmento
**Y** la abstención es explícita, de modo que quien genere después no tenga con qué inventar una atribución

### Escenario 5: Reindexar no cambia las citas

**Dado que** el corpus se reindexa cada vez que se corrige una errata o se añade un documento
**Cuando** se vuelve a indexar sin que una sección haya cambiado
**Entonces** su identificador de cita y su clave son los mismos que antes
**Y** no se vuelve a calcular su embedding, porque su contenido no ha cambiado
**Y** los fragmentos de secciones que ya no existen en el corpus dejan de estar indexados

### Escenario 6: Renombrar una sección no deja citas apuntando al vacío en silencio

**Dado que** el identificador de cita se deriva del título de la sección
**Cuando** se renombra o se elimina una sección del corpus
**Entonces** la comprobación de trazabilidad detecta que un identificador indexado ya no resuelve a un encabezado del repositorio
**Y** falla de forma visible, en lugar de dejar la cita colgando

### Escenario 7: La cobertura de materiales no es una opinión

**Dado que** el vocabulario cerrado del enriquecimiento enumera los materiales canónicos
**Cuando** se comprueba el corpus
**Entonces** existe exactamente una ficha por material canónico
**Y** si se añadiera un material nuevo al vocabulario sin su ficha, la comprobación falla
**Y** ninguna ficha de material está acotada a un producto concreto

### Escenario 8: El corpus no puede contener lo que no debe citarse

**Dado que** el conocimiento es general y la autoridad sobre precio y existencias es de .NET
**Cuando** se valida el corpus antes de indexarlo
**Entonces** se rechaza cualquier sección que nombre un SKU, un producto concreto o un precio
**Y** se rechaza cualquier documento con texto antes de su primera sección, porque sería un fragmento sin localizador
**Y** se rechaza cualquier sección que supere el tamaño máximo, en lugar de trocearla automáticamente

### Escenario 9: El corpus describe, no ordena

**Dado que** un fragmento recuperado acaba dentro del contexto de un modelo
**Y** que un texto imperativo es indistinguible de una instrucción una vez está ahí
**Cuando** se revisa el corpus
**Entonces** ningún documento contiene guiones de venta
**Y** las secciones están redactadas en modo descriptivo y no como órdenes al operador

### Escenario 10: Las dos ramas se pueden apagar para poder medirlas

**Dado que** hay que demostrar si la rama léxica aporta algo sobre un corpus tan pequeño
**Cuando** se desactiva la fusión por configuración
**Entonces** la búsqueda se comporta como una recuperación puramente vectorial
**Y** el valor efectivo viaja como parámetro de la llamada, de modo que se pueden barrer configuraciones sin reiniciar el proceso
**Y** la medición de las dos configuraciones queda registrada en un informe versionado

### Escenario 11: El corpus declara de qué está hecho

**Dado que** el corpus lo redacta un asistente y lo revisa una persona
**Cuando** se termina de generar
**Entonces** un fichero acompañante sella el modelo, la versión de prompt, el instante de generación y los recuentos por tipo de documento y por clase de afirmación
**Y** esos recuentos son los que el README publica al declarar la composición del corpus

### Escenario 12: La escala de tallas se explica una sola vez y es comprobable

**Dado que** la letra del catálogo mide el tamaño de la pieza y se aplica a varios tipos
**Y** que el anillo es el único tipo donde además compromete un ajuste
**Cuando** se valida el corpus
**Entonces** existe **una sola** tabla de equivalencia de anillo, en un único documento
**Y** cada letra corresponde a tallas españolas enteras, con tramos contiguos y sin solape
**Y** la circunferencia declarada para cada talla cumple la relación estándar entre talla y milímetros
**Y** las letras que el catálogo no usa aparecen en la tabla marcadas como disponibles por encargo
**Y** ninguna sección presenta una palabra de escala de motivo como medida de ajuste de un anillo
**Y** los materiales que la tabla excluye del ajuste son los mismos que excluyen sus fichas y la política de reparaciones

### Escenario 13: Fuera de alcance explícito

**Dado que** esta historia entrega el corpus, su índice y su búsqueda
**Cuando** se revisa el entregable
**Entonces** **no** hay argumentario generado, ni `citations[]` en una respuesta de venta, ni placeholders de precio o stock: eso es C30
**Y** **no** hay ruta HTTP nueva, ni `openapi.json` regenerado, ni router LLM
**Y** **no** hay migración de ninguna clase, ni de Alembic ni de EF Core
**Y** **no** se han tocado `indexing/embeddings.py`, `enrichment/vocabularies.yaml` ni el árbol `frontend/`
**Y** los dos índices siguen sin fusionarse en ninguna lista

---

## Notas adicionales

- **Actor:** el **Operador**, por tercera vez consecutiva tras C21 y C22, aunque esta historia sea habilitadora. C21 mejoró *qué* se encuentra, C22 *cuánto llega a la pantalla*, y C23 abre lo que hasta ahora el sistema no sabía contestar en absoluto: las preguntas que no son sobre un producto sino sobre **la joya y el servicio**.

- **Undécima vez que la zona de una ficha se queda corta.** La ficha declara `data/` e `indexing/`; el change entrega además un paquete nuevo, `jbg_ai/knowledge/`, porque su propia lista de tests pide búsqueda. Va tras C08, C07, C15, C16, C17, C18b, C20, C21 y C22.

- **La producción del corpus necesita planificación propia, y no cabe en una ventana de contexto.** Es requisito del change, no una nota:
  - 161 secciones de 80-250 palabras son **~25.000 palabras de salida útil**, y a eso hay que sumar, **en cada petición**, las reglas de autoría completas, el esqueleto del bloque y la evidencia medida que lo justifica. De una sola vez, las primeras fichas se olvidan y las últimas derivan del esqueleto: se pierde exactamente la homogeneidad que hace comparables a nueve fichas de material, y las invariantes lo cazarían tarde.
  - **Reparto: un subagente o una ventana de chat nueva por bloque** — ocho encargos, detallados en el §7 del informe. Nunca el corpus entero de una vez, y nunca un documento por encargo: partir por documento perdería la coherencia interna del bloque, que es justo lo que hay que preservar.
  - **Prompts versionados en `ai-service/prompts/knowledge/`**, uno **por bloque** y no por documento, siguiendo el patrón de `catalog-synth/` y `enrichment/`. Cada prompt lleva el esqueleto exacto con sus `claim_scope`, las siete reglas de autoría **completas y no resumidas**, la evidencia medida de ese bloque, la prohibición de nombrar SKU, producto o precio, y la instrucción de devolver **solo ficheros Markdown**.
  - **Revisión por bloque según llega**, no acumulada al final: son ~4-6 minutos por documento y ~2-3 horas en total, y el cuello de botella de atención de un solo revisor ya está identificado en el §7.8 del diseño.

- **`design.md` obligatorio** en el change. Hay al menos siete decisiones con alternativa real y coste asimétrico —identidad del chunk, híbrido frente a vectorial, `claim_scope` frente a procedencia de documento, umbral propio, paquete propio, dónde vive el hash, y el tamaño del corpus frente al corte pre-autorizado—, y **dos de ellas contradicen la ficha o el plan**.

- **Limitación a declarar en el README**, hermana de las de C06b, C20, C21 y C24: **el corpus de conocimiento es sintético**. Lo redacta un asistente y lo revisa una persona; la joyería no aportó sus textos comerciales. Aproximadamente el **16 % de las secciones son compromisos de la casa hoy ilustrativos** y viajan marcados como tales. La verificación de citas que el §11.3 exige es **estructural**: garantiza que la fuente citada existía y se recuperó, no que diga la verdad sobre el negocio.

- **Verificación posterior (no DoD de merge):** re-medir las cifras del §2 del informe contra `ai.product_document` con la base levantada —el proxy de texto infla `oro` (absorbe los de baño), duplica `perla` y engorda `pequeño`, `grande` y `mediano` con usos de prosa—, y repetir la mini-medición con preguntas escritas por alguien que no redactó el corpus.

---

## Tareas

1. Completar artefactos OpenSpec del change `add-knowledge-corpus-and-indexer`: `proposal`, **`design.md` obligatorio**, `specs` (capacidad nueva `knowledge-corpus`) y `tasks`.
2. **Definir el formato de autoría**: encabezados, marca de `claim_scope`, tope de sección, y las siete reglas del §6 del informe, escritas en un `README` corto dentro de `data/knowledge/`.
3. **Redactar los ocho prompts de bloque** en `ai-service/prompts/knowledge/v1/`, cada uno con esqueleto, reglas completas y evidencia medida.
4. **Generar el corpus por bloques**, un subagente o ventana nueva por encargo, con revisión humana bloque a bloque según llega.
5. **Sellar el sidecar** `.meta.json` con modelo, versión de prompt, instante y recuentos por `doc_type` y `claim_scope`.
6. **Python — `knowledge/corpus.py`:** carga y validación del corpus (tipo de documento, `claim_scope` obligatorio, tope de sección, prohibición de SKU/producto/precio, rechazo de preámbulo sin sección).
7. **Python — `knowledge/chunking.py`:** una sección `##` = un chunk, sin solape, `content` con los dos títulos, marca de `claim_scope` retirada antes de construir el contenido.
8. **Python — `knowledge/indexer.py`:** identidad determinista, upsert idempotente por documento, borrado de chunks no producidos, `content_hash` en `metadata`, reutilización del cliente de embeddings de C11 **sin modificarlo**.
9. **Python — CLI** `python -m jbg_ai.indexing sync-knowledge [--full]`, con la misma carga de entorno que `sync` y `sync-pos`, y documentación en `ai-service/README.md`.
10. **Python — `knowledge/search.py`:** rama vectorial, rama léxica compuesta desde los grupos de C20, fusión por RRF importando `retrieval/fusion.py`, umbral propio y devolución con `citation_id`, `claim_scope` y títulos.
11. **Python — settings nuevos** (umbral de conocimiento, flag de fusión) con default en `Settings`, valor efectivo por parámetro, y fila en la tabla de entorno del README. **Sin tocar `canonical_openapi_settings` si no entra en el contrato.**
12. **Logs** `stage=knowledge` junto a los existentes, con `trace_id`.
13. **Tests** *offline* en `ai-service/tests/knowledge/`: chunker, invariante de cobertura de materiales, trazabilidad de citas, no-scoping a producto, identidad estable ante reindexación, validaciones de corpus, y búsqueda con cita.
14. **Mini-medición**: fixture de ~32 preguntas más 4-5 fuera de dominio, comando que imprime Recall@3, MRR y abstención, y comparación vectorial-solo frente a híbrido.
15. **Informe versionado** con el resultado de la mini-medición y la decisión sobre la rama léxica.
16. Enlazar la HU en [`Documentos/epicas.md`](../../epicas.md) (EP12) **en el apply**.
17. `openspec validate --all --strict` en `0 failed` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** **4** — abre una clase de pregunta que el sistema hoy no puede contestar en absoluto, y es lo que hace posible la única promesa del proyecto que se apoya en citas. No es 5 porque el operador no lo ve hasta C30.
- **Urgencia (mercado / feedback):** **3** — desbloquea C30 y con él toda la rama de generación (`C30 → C31 → C32 → C38 → C39`), pero no está en la cadena crítica `C21 → C24 → C25 → C26 → C34 → C36`. Entra por el lado.
- **Complejidad / esfuerzo:** **4** — el código es modesto y muy acotado (un paquete nuevo, sin migración, sin contrato); lo caro es **el corpus**: 32 documentos, ocho encargos con revisión humana bloque a bloque, y siete decisiones que hay que dejar escritas, dos de ellas contra la ficha.
- **Riesgos y dependencias:**
  - **La cita bien formada sobre un corpus inventado** es el riesgo estructural de la historia. Se mitiga con `claim_scope` por sección y con la limitación declarada en el README; no desaparece.
  - **La tentación de un `uuid4` por fila**: la cita dejaría de localizar y cada reindexación rompería toda referencia previa.
  - **La tentación de `(document_id, chunk_index)`**: insertar una sección repunta en silencio todas las citas posteriores.
  - **La tentación de abrir `/v1/knowledge/search` «ya que estamos»**: mueve un contrato congelado y obliga a coordinar con .NET a cambio de nada.
  - **La tentación de meter el guion de venta**: es la puerta de la inyección desde el propio corpus.
  - **Deriva del corpus si se genera en una sola ventana**: las últimas fichas dejan de parecerse a las primeras y la comparabilidad entre materiales se pierde.
  - **Zona compartida con C13 (archivado) en `indexing/cli.py`** y con C25 y C26 en `retrieval/` — de ahí el paquete propio, que reduce la superficie de roce a un subcomando y un import.
  - **`data/knowledge/` no existe todavía**: el corpus va ahí, en la raíz junto a `data/catalog/` y `data/world/`, y no en `ai-service/data/`, que tampoco existe. **No hace falta tocar `.gitignore`**: sus reglas son específicas de `data/catalog/` y `data/world/`, y `git check-ignore` confirma que un fichero bajo `data/knowledge/` no queda ignorado.
  - **Las mediciones del informe son un proxy sobre texto**, no los atributos extraídos: la re-medición contra `ai.product_document` puede mover cifras que citan tres documentos del corpus.
