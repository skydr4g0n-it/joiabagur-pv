# HU-AIENG-020: Diccionario de sinónimos de consulta para la rama léxica

## Formato estándar

Como **desarrollador del proyecto**, quiero **una capa de expansión de consulta que traduzca la palabra del operador al vocabulario canónico que el índice guardó, entregada como grupos de equivalencia y tras un flag** **para** **que la rama léxica de C21 no nazca devolviendo cero a frases tan ordinarias como «gargantilla dorada» o «collares de plata»**.

---

## Descripción

Change OpenSpec `add-synonym-dictionary` / **C20**, épica **EP14 — Búsqueda Semántica Híbrida**. Pintado 🟢 pero **es el tapón del grafo**: es el único prerrequisito que le falta a C21, y C21 bloquea a la vez a C24 (harness de evaluación) y a C30 (generación), o sea las dos mitades del proyecto. Nunca se recorta (§6 del plan). Prerrequisito: **C14** (archivado).

Sustituye a `SearchAliases`, que la decisión 4 de la revisión sacó del perfil de producto por ser texto generado por IA y persistido por producto. El sustituto no es persistir alias sino **un diccionario del dominio aplicado en expansión de consulta**: una sola lista, cero generación por IA, cero deriva, corregible en un commit y aplicable a productos futuros sin reindexar.

**La sesión de exploración del 2026-09-01 midió contra el Postgres local —1.168 documentos vivos en `ai.product_document`— y contra el proveedor real, y obligó a reencuadrar la ficha.** El detalle completo vive en el §0 del plan de changes; lo que cambia el alcance de esta historia es esto:

1. **`doc_text` ya está canonicalizado**, así que la expansión tiene diana garantizada. `build_source_text` escribe las líneas `Tipo:` y `Materiales:` con el vocabulario cerrado de C09 — presentes en 1.157 y 1.042 de 1.168 documentos —, y buscar léxicamente el término canónico **equivale exactamente a filtrar por `piece_type`**: `anillo` 268 = 268, `pendientes` 275 = 275, `pulsera` 207 = 207, `collar` 140 = 140.

2. **Sin diccionario la rama léxica contesta cero.** Medido: `gargantilla dorada` 0 → 64, `collares de plata` 0 → 66, `criollas de oro` 1 → 102, `sortija de plata` 3 → 144, `aros de plata` 22 → 205.

3. **El stemmer español rompe dos sustantivos del dominio**, lo que no es un problema de sinónimos sino de tokenizador: `collar`→`'coll'` frente a `collares`→`'collar'` da **140 documentos frente a 1**; `baño`→`'bañ'` frente a `bano`→`'ban'` deja `bano de oro` en **0** frente a 38. El stemmer **sí** pliega tildes agudas (`ámbar`=`ambar`, `ónix`=`onix`) **pero no la `ñ`**: un operador de TPV que teclea sin `ñ` obtiene cero.

4. **Una sola `tsquery` ensanchada destruye la coincidencia exacta.** Con `(sortij|anill) & plat` los **tres** productos que se llaman literalmente «Sortija» caen fuera del top-10, porque `ts_rank` deja de premiar el término que el operador escribió. Fusionando por RRF las dos listas —original y expandida— vuelven a las posiciones **1, 2 y 3** conservando los 144 candidatos. De ahí que la expansión entregue **grupos**, no una cadena reescrita: la fusión es de C21 y C20 no puede quitarle la información con la que fusionar.

5. **La rama vectorial no cubre el hueco y además no abstiene.** Con doce embeddings reales de `text-embedding-3-small`, aciertos en el top-10 contra la diana: `criollas de oro` **1/10**, `sortija de plata` **4/10**, `gargantilla dorada` **6/10** — y siempre devuelve diez candidatos por debajo del umbral, así que el fallo llega a la pantalla con apariencia de acierto.

El valor no es de operador: no hay pantalla y, hasta que C21 encienda la rama léxica, **la expansión se calcula, se registra y no se consume**. Se declara así en lugar de disimularlo.

**Alcance de esta historia (sí):**

- **Base + overlay.** Leer `enrichment/vocabularies.yaml` como clases de equivalencia base, **sin modificarlo**, y añadir `ai-service/src/jbg_ai/retrieval/query_synonyms.yaml`, versionado y **sólo de consulta**.
- Contenido del overlay, en tres familias: **artefactos del stemmer** (`collares`, `aros`, `bano de oro`, `pequeño`/`pequeno`), **sinónimos comerciales que la base no tiene** (`arete`, `aretes`, `criolla`, `zarcillos`, `aro de dedo`, `choker`, `dije`, `medalla`, `prendedor`, `alfiler`, `cordon`, `cuerda`, `bronce`, `acrilico`, `acero inoxidable`, `banado en oro`) y **el puente `dorado` → {`dorado` color, `baño de oro`, `oro`}**.
- **Singularización en ambos lados al cargar**, que resuelve `sortijas`, `gargantillas`, `brazaletes`, `esclavas` y `dorados` sin una entrada por forma.
- `expand_query` como **función pura**: sin base de datos, sin proveedor, sin sockets. Devuelve **grupos de equivalencia** (una lista de formas de superficie por token) **y los términos resueltos** (`término → campo, canónico`), que es lo que C21 necesita para su extracción de filtros por reglas sin construir una segunda tabla de consulta.
- Emisión de **formas de superficie con sus tildes**: el emparejamiento se hace sobre texto plegado con `fold()`, pero lo que sale son las formas que el índice contiene.
- **Token desconocido pasa intacto** como grupo de un solo elemento.
- **Flag**: default en `Settings` (`JPV_QUERY_EXPANSION_ENABLED`, encendido) y **parámetro en la firma del orquestador**, para que C24 barra configuraciones en el mismo proceso sin reiniciar y sin tocar `RetrievalRequest`.
- **Observe-only**: log estructurado `stage=expand` junto a `stage=embed` y `stage=search`, con `trace_id`, número de términos resueltos y estado del flag. La consulta del operador sólo en Debug.
- **CLI de medición** que reproduce sobre el índice real el alcance del diccionario y deja **informe versionado**, que C24 reutiliza como categoría de sinónimos del golden set.
- Tests unitarios offline en `ai-service/tests/retrieval/`.

**Fuera de alcance (no):**

- **La rama léxica**, `ts_rank`, la fusión RRF, el *boost* de SKU y la extracción de filtros desde el texto → **C21**. C20 fabrica la pieza; C21 la enchufa.
- **La rama vectorial.** La expansión no llega al embedding. Duplicar la consulta duplicaría los embeddings sobre un cliente que aún se construye **por petición**, con un presupuesto ya en los 2500 ms temporales de C16 y 1707 ms medidos en una de cada cuatro llamadas.
- **`enrichment/vocabularies.yaml`**, el salto a `enrichment/v2` y los huecos de `piece_type` (`llavero`, `diadema`, `gemelos`, `cinturon`) y de `style_tags` (`filigrana`) → **`fix-enrichment-vocabulary-gaps`**.
- Instalar `unaccent` o crear una configuración `ts` propia: `tsv` es **columna generada**, y cambiar la configuración exigiría migración que la reescribe y reconstruye el GIN. C20 **no es** 🗄️.
- El **singleton del cliente de embeddings** y revertir `AiGateway:RetrievalTimeoutMs` de 2500 a 800 ms → **C21/C22**, anotado en `openspec/DEFERRED_TASKS.md`.
- Erratas y `pg_trgm`. Reformulación de consulta con LLM. `ai.query_log`. Persistir nada.
- Regenerar `ai-service/openapi.json`, migración Alembic, migración EF Core, `backend/`, `frontend/`, UI.

**Decisiones de diseño ya acordadas** (exploración 2026-09-01, registradas en el §0 del plan):

| # | Tema | Decisión |
|---|---|---|
| 1 | Fuente del diccionario | **Base + overlay.** `vocabularies.yaml` se lee y **no se modifica**; el overlay lleva lo que no debe entrar en el contrato de extracción. Un segundo fichero suelto sería la segunda definición que diverge: el motivo por el que se anuló C19 |
| 2 | Qué devuelve la expansión | **Grupos de equivalencia + términos resueltos.** Nunca una cadena reescrita, nunca una `tsquery` construida por concatenación. Medido: la cadena ensanchada saca del top-10 los productos que el operador nombró |
| 3 | Dirección de la expansión | **Clase completa**, no sólo el canónico. `pequeño` (134 documentos) y `pequeno` (71) son ambas legítimas; canonicalizar tiraría las primeras |
| 4 | Dónde vive el flag | **Default en `Settings`, parámetro en la firma del orquestador.** Un interruptor sólo de entorno obliga a reiniciar por configuración; llevarlo a `RetrievalRequest` movería el `openapi.json` congelado |
| 5 | Valor por defecto del flag | **Encendido.** Con la rama léxica aún apagada no cambia nada hoy; cuando C21 la encienda, lo correcto por defecto es no contestar cero. La ablación de C24 puede apagarlo |
| 6 | Qué se puede observar en C20 | **Observe-only + informe medido.** No cabe endpoint nuevo: `openapi.json` es contrato congelado. La expansión se calcula y se registra; C21 la consume |
| 7 | Rama vectorial | **No se toca.** Los números quedan como hipótesis para la ablación de C24, defendible en cuanto el cliente de embeddings sea singleton |
| 8 | `piel` → `cuero` | **Excluido con motivo medido.** Los 7 documentos que casan dicen «sobre la piel», piel humana en prosa comercial, y `cuero` tiene un solo producto |
| 9 | `unaccent` / configuración `ts` propia | **No.** El problema de la `ñ` se resuelve en el overlay por tres entradas, sin migración |
| 10 | Medición de C24 | C24 está aguas abajo por C21: **C20 trae su propia evidencia** y C24 la re-mide con relevancia graduada |

**Cortes que no se reabren:** `vocabularies.yaml` no se modifica · `openapi.json` no se regenera · `indexing/embeddings.py` sigue congelado desde C11 · Python no lee el esquema `public` · no hay migración de ninguna clase · la expansión no se aplica en indexación.

**Referencias:**

[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C20 reescrita, entrada de §0 del 2026-09-01, §4 grafo, §6 nunca se recorta),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§7.3 filtro por materiales, §7.4 diccionario de sinónimos, §7.6 recuperación),
[Búsqueda híbrida](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Busqueda%20hibrida.md) y [Expansión y descomposición de consultas](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Expansion%20y%20descomposicion%20de%20consultas.md) (guía avanzada, no dogma: los apuntes proponen multi-query con LLM; aquí se elige diccionario por latencia, coste y reproducibilidad del golden set),
[epicas.md](../../epicas.md) (EP14),
[modelo-de-datos.md](../../modelo-de-datos.md) (`ai.product_document`, `tsv` generada, GIN),
[HU-AIENG-009.md](HU-AIENG-009.md) (vocabulario cerrado), [HU-AIENG-011.md](HU-AIENG-011.md) (`source-text/v1`), [HU-AIENG-014.md](HU-AIENG-014.md) (retriever vectorial),
specs vivas `vector-retrieval`, `catalog-enrichment-pipeline`, `catalog-source-text`, `ai-vector-schema`, `ai-service-runtime`,
change OpenSpec [`openspec/changes/add-synonym-dictionary/`](../../../openspec/changes/add-synonym-dictionary/) y su [ticket técnico](../../../openspec/changes/add-synonym-dictionary/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: Un término del operador se expande a la clase que el índice contiene
**Dado que** el diccionario carga las clases base de `enrichment/vocabularies.yaml` más el overlay de consulta
**Y** el flag de expansión está activo
**Cuando** se llama a `expand_query("sortija de plata")`
**Entonces** el resultado contiene un grupo que incluye la forma tecleada `sortija` **y** el canónico `anillo`
**Y** contiene un grupo con `plata`
**Y** `matched` registra `sortija → (piece_type, anillo)`
**Y** el texto original viaja intacto en el resultado, para que C21 pueda fusionar la lista original con la expandida
**Y** no se ha construido ninguna cadena de consulta reescrita ni ninguna sintaxis de `tsquery`

### Escenario 2: Los artefactos del stemmer se expanden como cualquier otro término
**Dado que** `to_tsvector('spanish', 'collar')` produce `'coll'` y `to_tsvector('spanish', 'collares')` produce `'collar'`, que no casan entre sí
**Cuando** se llama a `expand_query("collares de plata")`
**Entonces** el grupo del primer token contiene **ambas** formas, `collares` y `collar`
**Y** con `expand_query("bano de oro")` el grupo contiene la forma acentuada `baño de oro`
**Y** con `expand_query("pequeño")` el grupo contiene `pequeño` **y** `pequeno`, porque las dos aparecen en el corpus y canonicalizar sólo a una perdería documentos
**Y** ninguna de esas entradas ha exigido tocar `enrichment/vocabularies.yaml`

### Escenario 3: Un plural se resuelve sin una entrada dedicada
**Dado que** el cargador singulariza en ambos lados: las claves del diccionario y el token de la consulta
**Cuando** se llama a `expand_query` con `sortijas`, `gargantillas`, `brazaletes`, `esclavas` o `dorados`
**Entonces** cada uno alcanza su clase de equivalencia
**Y** el fichero de overlay **no** contiene una entrada por cada una de esas formas

### Escenario 4: Un término desconocido pasa intacto
**Dado que** el diccionario no conoce la palabra
**Cuando** se llama a `expand_query("anillo Ses Salines")`
**Entonces** `Ses` y `Salines` viajan como grupos de un solo elemento, con la forma exacta tecleada
**Y** `anillo` sí lleva su clase
**Y** la función no falla, no descarta tokens y no inventa un canónico

### Escenario 5: Con el flag apagado la consulta sale como entró
**Dado que** el flag de expansión está desactivado, por `Settings` o por el parámetro de la llamada
**Cuando** se llama a `expand_query`
**Entonces** cada token es un grupo de un solo elemento con su forma original
**Y** `matched` está vacío
**Y** el log `stage=expand` deja constancia de que el flag estaba apagado, para que una ablación de C24 sea legible después

### Escenario 6: La expansión no toca la indexación, ni la base, ni el contrato
**Dado que** C20 se ha implementado
**Cuando** se revisa el entregable
**Entonces** `ai.product_document.doc_text`, `tsv` y `source_hash` son idénticos antes y después: **ningún documento se ha reindexado**
**Y** `enrichment/vocabularies.yaml` no tiene diff
**Y** `ai-service/openapi.json` no se ha regenerado y `test_openapi_snapshot_is_stable` sigue verde
**Y** no hay revisión de Alembic nueva ni migración de EF Core
**Y** `indexing/embeddings.py` no tiene diff

### Escenario 7: La expansión es una función pura y la suite sigue offline
**Dado que** los tests de `ai-service/tests/retrieval/` no deben abrir sockets
**Cuando** se ejecuta la suite
**Entonces** `expand_query` no abre sesión de base de datos ni llama a ningún proveedor
**Y** la CLI de medición, que sí necesita el índice, se **salta** —no falla— cuando Docker no responde
**Y** ningún test exige que el índice tenga 1.168 filas

### Escenario 8: Fuera de alcance explícito
**Dado que** C20 entrega el diccionario y su expansión
**Cuando** se revisa el entregable
**Entonces** **no** existe rama léxica, ni `ts_rank`, ni fusión RRF, ni extracción de filtros desde el texto
**Y** la expansión **no** llega al embedding de la consulta: el vector se calcula sobre el texto original
**Y** `piel` **no** figura en el diccionario
**Y** `llavero`, `diadema`, `gemelos`, `cinturon` y `filigrana` **no** figuran: son huecos de vocabulario de otro change
**Y** no se ha instalado `unaccent` ni creado una configuración de búsqueda de texto propia
**Y** `AiGateway:RetrievalTimeoutMs` sigue en 2500 ms

---

## Notas adicionales

- **Actor:** equipo del Proyecto Final. Nada visible para el operador: el panel de C16 sigue sirviendo de la rama vectorial hasta que C21 encienda la léxica.

- **Por qué diccionario y no reformulación con LLM.** Los apuntes de S10 proponen multi-query generada por un modelo pequeño, y lo dicen con razón para su caso. Aquí pierde por tres motivos medibles: mete 200–1000 ms en un camino crítico que ya mide 1707 ms en una de cada cuatro llamadas; rompe `test_run_is_reproducible_for_same_config_and_seed`, que C24 exige; y un modelo que reescribe puede inventar un filtro que la consulta no pedía, justo lo que C21 prohíbe con `test_never_invents_filter_absent_from_query`. Queda como arma de C24 si sobra sesión, no como alcance de C20.

- **`ClosedVocab.phrases_for()` no sirve tal cual para emitir.** Devuelve las frases **plegadas** —`fold()` quita las tildes y convierte `ñ` en `n`—, que es exactamente lo que hace falta para *emparejar* y exactamente lo que no sirve para *emitir*: `to_tsvector('spanish','bano')` da `'ban'` y no casa con `'bañ'`. Las formas de superficie con tilde salen de `ClosedVocab.canonical` y del overlay. Es la trampa más fácil de este change.

- **`resolve()` ya resuelve la `ñ` de entrada.** `ClosedVocab.resolve("bano de oro")` devuelve `"baño de oro"` **hoy**, porque el emparejamiento es sobre texto plegado. Ese es el motivo técnico por el que reutilizar la base sale gratis y duplicarla saldría caro.

- **`dorado` es ambiguo entre vocabularios**, y no por descuido: es canónico en `color_tags` y sinónimo de `baño de oro` en `materials` — y el §0 del 2026-08-31 ya nombró que su ausencia en `materials` deja familias sin agrupar. Medido: la clase completa `{dorado, baño de oro, oro}` alcanza **64** documentos frente a **22** de la canonicalización simple. Es decisión de contenido del overlay, no de mecanismo.

- **El diccionario se cura contra el corpus, no contra demanda observada.** `public."ProductSearchEvents"` tiene **31 filas y 12 textos distintos**, todos escritos por el desarrollador y todos en vocabulario canónico. Las 300–400 consultas de operador del D10 del diseño no existen. Es una limitación a declarar en el README, hermana de la ausencia de acuerdo entre anotadores que C24 ya declara.

- **Conflicto de zona con C21.** Los dos trabajan en `ai-service/src/jbg_ai/retrieval/`. No se abren a la vez, aunque los abra la misma persona (regla superviviente del §1 del plan). C20 crea ficheros nuevos y toca el orquestador en un punto acotado; C21 hereda.

- **`design.md` obligatorio** en el change. La lista del §7 del plan no lo asignaba a C20, pero hay al menos cuatro decisiones con alternativas defendibles y coste asimétrico —base+overlay frente a fichero suelto, grupos frente a cadena, dónde vive el flag, y no tocar el vector— que no caben en `tasks.md`. Es la séptima vez que esa lista se queda corta, tras C08, C07, C15, C16, C17, C18a y C18b.

- **Verificación posterior (no DoD de merge):** ejecutar la CLI de medición contra el índice local y comprobar que reproduce los números del §0 — `gargantilla dorada` de 0 a 64 y `collares de plata` de 0 a 66 —, y que el informe queda versionado en el repositorio.

---

## Tareas

1. Completar artefactos OpenSpec del change `add-synonym-dictionary`: `proposal`, **`design.md` obligatorio**, `specs` (delta de `vector-retrieval` o capability nueva de expansión de consulta, más delta de `ai-service-runtime` si el flag entra en spec) y `tasks`.
2. Curar `retrieval/query_synonyms.yaml` con las tres familias de entradas, cada una con su motivo, y las exclusiones declaradas (`piel` la primera).
3. Cargador de clases de equivalencia: base desde `vocabularies.yaml` + overlay, singularización en ambos lados, formas de superficie con tilde, precedencia declarada del overlay sobre la base.
4. `expand_query` como función pura, devolviendo grupos y términos resueltos; token desconocido intacto.
5. Setting `JPV_QUERY_EXPANSION_ENABLED` con default y pin en `canonical_openapi_settings`; parámetro equivalente en la firma del orquestador.
6. Log `stage=expand` en el pipeline real, junto a `stage=embed` y `stage=search`.
7. CLI de medición y su informe versionado, con *skip* limpio cuando no hay base de datos.
8. Tests offline en `ai-service/tests/retrieval/`, incluidos los de fijación que impiden modificar `vocabularies.yaml` y regenerar `openapi.json`.
9. Enlazar la HU en `Documentos/epicas.md` (EP14) **en el apply**.
10. `openspec validate --all --strict` en `0 failed` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 4 — invisible hoy; sin él, la búsqueda asistida contestará cero a frases ordinarias en cuanto C21 encienda la rama léxica
- **Urgencia (mercado / feedback):** **5** — es el tapón del grafo: lo único que separa a C21 de arrancar, y C21 bloquea a C24 y a C30
- **Complejidad / esfuerzo:** 2 — un cargador, una función pura, un flag y una CLI; sin migración, sin contrato, sin interfaz. El trabajo real es de **curación y medición**, no de algoritmo
- **Riesgos y dependencias:** C14 archivado e índice local poblado (1.168 documentos; si se recrea el volumen, la CLI de medición no tiene contra qué medir) · no tocar `vocabularies.yaml` bajo ninguna circunstancia, porque arrastra `enrichment/v2` y reenriquecimiento · no abrir C21 en paralelo, misma zona · resistir la tentación de emitir con `phrases_for()`, que pliega las tildes · resistir la tentación de expandir la rama vectorial, que duplicaría los embeddings sobre un cliente que aún se construye por petición
