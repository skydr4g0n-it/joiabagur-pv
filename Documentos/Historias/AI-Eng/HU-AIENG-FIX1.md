# HU-AIENG-FIX1: Cerrar las lagunas del vocabulario de enriquecimiento — cuatro tipos de pieza, `enrichment/v2` y una cohorte de veintidós

## Formato estándar

**Como** Operador de un punto de venta de la joyería,
**quiero** poder filtrar por **diadema, gemelos, cinturón y llavero** —y que al filtrar por *broche* no me salgan diademas—,
**para** que el desplegable «Tipo de pieza» describa el catálogo que tengo delante en lugar de un catálogo de ocho categorías que el extractor tuvo que forzar.

---

## Descripción

`piece_type` es un vocabulario **cerrado** de ocho hiperónimos, fijado por C09 en [`vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml) y replicado en el prompt, en el espejo del frontend y en dos specs vivas. El catálogo contiene piezas que esos ocho términos **no saben nombrar**, y el extractor hace ante ellas exactamente lo que se le pidió: o deja `piece_type` en nulo, o elige el hiperónimo más plausible.

C18a destapó la mitad del problema —once productos sin tipo— y lo anotó como change propio. **La exploración del 2026-09-05 midió la otra mitad, que nadie había mirado.**

### Lo que la exploración midió, y que reencuadra la ficha

Mediciones completas en [fix1-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/fix1-exploration-measurements.md).

**1. La población afectada es de veintidós productos, no de once.** De los que llevan uno de los cuatro términos en el nombre:

```
Productos cuyo nombre lleva uno de los cuatro términos:  22
├── 11  piece_type NULL      ← lo que la ficha ve
├──  9  piece_type ERRÓNEO   ← lo que la ficha no ve
└──  2  piece_type CORRECTO  ← falsos amigos que NO se deben tocar
```

**2. El nulo no es el peor síntoma: la etiqueta equivocada sí.** Un nulo es honesto —no casa con ningún facet y nadie miente—, pero el filtro de categoría es **duro** (`AND d.piece_type = :category` en [`search.py:135`](../../../ai-service/src/jbg_ai/retrieval/search.py)), así que una diadema etiquetada `broche` **aparece cuando el operador filtra por broche**. Hoy:

| tipo | documentos | impostores | qué son |
|---|---:|---:|---|
| **broche** | 85 | **6** (7,1 %) | 3 diademas, 2 gemelos, 1 llavero |
| collar | 140 | **2** | 2 diademas |
| colgante | 161 | **1** | 1 diadema |

Corregirlos lleva el acuerdo entre nombre y tipo de `broche` de **76/85 (89 %)** a **76/79 (96 %)**.

**3. Reenriquecer sólo los once nulos entregaría un facet al 45 %.** Es el punto que decide el alcance:

| término | en el catálogo | cohorte «sólo nulos» | cohorte de esta historia |
|---|---:|---:|---:|
| diadema | 11 | 5 (**45 %**) | 11 (100 %) |
| gemelos | 4 | 2 (**50 %**) | 4 (100 %) |
| llavero | 3 | 2 (**67 %**) | 3 (100 %) |
| cinturon | 1 | 1 (100 %) | 1 (100 %) |

Un desplegable que ofrece «Diadema» y devuelve cinco de once es exactamente el fallo que el docstring de `materials-vocabulary.test.ts` declara intolerable —*«"nothing of this in your shop", a sentence that would be false»*— en su versión peor: no dice cero, dice cinco. Sin error, sin traza y con resultados en pantalla. **Es la firma de C17 otra vez.** El coste de evitarlo son nueve llamadas al modelo.

**4. Hay dos falsos amigos medidos, y `cinturon` en el vocabulario los pone en riesgo.** `Broche Cinturón de Orión` (SKU822) y `Anillo Cinturón de Orión` (SKU882) están **bien etiquetados**: el «cinturón» es la constelación. Es el mismo patrón que la exclusión `piel → cuero` del overlay de C20, pero éste no estaba documentado. Entran en la corrida **como grupo de control que debe no moverse**.

**5. El criterio de aceptación de la ficha ya pasa hoy.** La ficha promete *«buscar "diadema" pasa de cero a resultados»*. Medido contra el `tsv` vivo: `diadema` alcanza **11 documentos**, `gemelos` 4, `cinturon` 3, `llavero` 3. La rama léxica de C21 ya las devuelve, porque el nombre está en `doc_text`. Un verificador que ejecute ese criterio firmará **verde por el motivo equivocado**. Lo que esta historia cambia es **estructural, no léxico**.

**6. Los alambres que saltan son cuatro, no dos.** Además de los dos tests fijados que la ficha nombra, `test_vocabulary_gaps_are_recorded_as_exclusions_not_smuggled_in` exige que los cuatro términos estén en las `exclusions` del overlay, y `test_overlay_anchor_absent_from_the_base_is_a_vocabulary_gap` **usa `diadema` como ejemplo de canónico desconocido**: al añadirlo al base deja de lanzar y falla con `DID NOT RAISE`. Ése es el peligroso, porque falla en la dirección contraria a la esperada y la tentación es borrarlo.

**7. Y por eso el overlay de C20 entra en el alcance**, pese a que la ficha lo lista fuera: sus cuatro `exclusions` dicen literalmente *«pertenece a `fix-enrichment-vocabulary-gaps`»*. Dejarlas es documentación bien formada y falsa, el pecado exacto que justifica que esto sea un change.

**8. `PROMPT_VERSION` y la ruta del prompt están desacopladas.** `constants.py` declara `enrichment/v1` y `pipeline.py` abre `prompts/enrichment/v1.md` por separado. Bumpear una y no la otra sella los perfiles como `v2` habiendo sido producidos por `v1` — y desmonta en silencio el argumento que sostiene todo el versionado de prompts: *el perfil problemático es el que no dice con qué prompt nació*. Diría con cuál nació, y sería mentira.

### Alcance de esta historia (sí)

- **Cuatro términos canónicos nuevos** en `piece_type.terms`: `diadema`, `gemelos`, `cinturon` y `llavero`.
- **Prompt `enrichment/v2`**, fichero nuevo, con la lista ampliada y **una línea que advierte de que el catálogo puede contener servicios, consumibles y artículos de regalo**, para los que `piece_type` es nulo.
- **`load_prompt()` deriva la ruta de `PROMPT_VERSION`**, con test de que el encabezado del fichero cargado coincide con la constante.
- **Espejo del frontend**: `PIECE_TYPE_OPTIONS` pasa de 8 a 12 opciones, con `value` canónico y `label` legible («Cinturón» con tilde, `cinturon` sin ella).
- **Overlay de consulta de C20**: cierre de las cuatro `exclusions` que reclamaban este change, más la forma de superficie `gemelo` para el canónico plural.
- **Reenriquecimiento de una cohorte enumerada de 22 SKU** con `force: true` y `reviewMode: AutoBulk`, en **un solo lote** de los 50 que admite `AiEnrichRequest`, seguido de **una sola sincronización incremental**.
- **Deltas de dos specs vivas**: `catalog-enrichment-pipeline` (dos requisitos `MODIFIED` más uno `ADDED`) y `query-expansion` (uno `MODIFIED`).
- **Actualización de los cuatro tests fijados**, incluida la sustitución del ejemplo de `diadema` por un término que siga siendo desconocido.
- **Informe versionado** `fix1-vocabulary-gaps-measurements.md` con la tabla de las 22 filas antes y después, incluidos los dos de control.

### Fuera de alcance (no)

- **Reenriquecer los 1.200 con `v2`.** Serían ~1.200 llamadas y podría reclasificar productos existentes de forma **difusa**, cambiando el comportamiento de búsqueda sin que nadie lo pidiera. La cohorte de 22 es lo contrario de difusa: enumerada, nominal y auditable fila a fila.
- **`filigrana`**, la única laguna que queda viva tras esta historia. Es un hueco de `style_tags` —otro eje del vocabulario, con sus propias puertas de cobertura en el auditor— y alcanza sus **66 documentos** sola por vía léxica. Se conserva como exclusión con su motivo actualizado.
- **Nuevos ejes de clasificación.** Nada de un campo `product_category` que distinga joya de accesorio, servicio o consumible: sería schema, DTO, feed, columna de índice y migración, desproporcionado para cuatro términos. El nulo sigue significando «no es una pieza» o «no sé nombrarla», y tras esta historia el residuo es **un solo producto**.
- **`source-text/v1`, `embedding_version` e `indexing/embeddings.py`.** La plantilla del documento no cambia: cambia el contenido de veintidós filas. Mezclar `embedding_version` es comparar dos espacios geométricos y es la corrupción silenciosa que S11 describe; **mezclar `PromptVersion` es seguro y trazable**, y el campo existe para eso.
- **Migración**, ni de Alembic ni de EF Core. Ninguna tabla, columna ni índice cambia.
- **Reejecutar la sugerencia de familias de C18a**, aunque esta historia deje a `Llavero Cape Nao Grande` y `Llavero Cape Nao pequeño` en condiciones de formar una por primera vez.
- **El endpoint que agregue los tipos realmente presentes en el surtido del punto de venta.** Es la respuesta mejor a la triple réplica del vocabulario, está anotada desde C16 y **no está en el alcance de C28**, cuya ficha es pantalla de revisión de perfiles y métricas. Esta historia le sube el precio a no hacerla y le entrega la primera prueba de que hace falta.
- **Regenerar `ai-service/openapi.json`.** El contrato no se mueve: no hay ruta, campo ni esquema nuevo.
- **Tocar `backend/src/`**, más allá de ejecutar la corrida de reenriquecimiento por el endpoint que ya existe.

### Decisiones de diseño ya acordadas

Tomadas el **2026-09-05** sobre las mediciones del informe.

| # | Decisión | Motivo |
|---|---|---|
| 1 | **Cohorte de 22 SKU**, con SKU822 y SKU882 como **grupo de control que no debe moverse** | Los 1.200 siguen fuera por el motivo que la ficha escribió —reclasificación difusa—, que no aplica a nueve filas nominales. Y reenriquecer los dos de Orión convierte el riesgo mayor de `v2` de suposición en medición: si se mueven, el prompt está sobreajustado y se sabe **dentro** del change |
| 2 | **`filigrana` fuera** | Es gap de `style_tags`, no de `piece_type`, y alcanza sus 66 documentos sin expansión. Una idea por change |
| 3 | **Los cuatro términos entran en el desplegable** | Medido: `diadema` está en 11 de 11 POS con surtido y `gemelos` también; `cinturon` en 10; `llavero` en 6. La línea de flotación es **`cadena`** —7 productos, 6 de 11 POS— que lleva en el desplegable desde C16 sin que nadie lo cuestione. Ninguno de los cuatro es un caso peor que el ya aceptado |
| 4 | Canónico **`gemelos`**, en plural como `pendientes` | La reducción de plurales del diccionario va singular←plural, así que `diademas`, `llaveros` y `cinturones` resuelven solos y **`gemelo` no**: necesita forma de superficie en el overlay |
| 5 | **`cinturon` sin tilde**, label «Cinturón» | Sigue el precedente de `pequeno`. El `value` viaja al filtro duro por **igualdad exacta**, así que debe ser byte a byte el canónico; la tilde vive sólo en lo que el operador lee |
| 6 | **Informe propio** con la tabla de 22 filas antes/después | Es la única evaluación real del prompt: la suite unitaria inyecta un `EnrichLlm` falso y no puede probar el enunciado |
| 7 | **`load_prompt()` deriva la ruta de `PROMPT_VERSION`** | Una línea que cierra un modo de fallo que corrompe la trazabilidad del propio campo que da seguridad a mezclar versiones |
| 8 | **`v1.md` no se edita ni se borra** | 1.178 perfiles seguirán declarando que vienen de él; esa afirmación tiene que seguir siendo verificable |
| 9 | La spec fija **`enrichment/v2` literal**, no «la versión vigente» | Hace que cada salto de prompt exija un change, que es justo la disciplina que este proyecto quiere |

**Cortes que no se reabren:** `indexing/embeddings.py` sigue congelado desde C11 · `source-text/v1` y `embedding_version` intactos · sin migración de ninguna clase · sin ruta HTTP nueva · sin regenerar `openapi.json` · sin tocar el motor de familias.

**Referencias:**

- Mediciones y decisiones: [fix1-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/fix1-exploration-measurements.md).
- Plan de changes, [ficha FIX1](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) del §3 y su propuesta en el §0 — **cuya población y criterio de extremo a extremo esta historia corrige**.
- Origen del hallazgo: [c18a-family-suggestion-report.md](../../Proyecto%20Final%20AIEng/informes/c18a-family-suggestion-report.md), hallazgos (b) y (c).
- Specs vivas afectadas: `openspec/specs/catalog-enrichment-pipeline/`, `openspec/specs/query-expansion/`.
- Historias previas: [HU-AIENG-009](HU-AIENG-009.md) (pipeline de enriquecimiento y vocabularios cerrados), [HU-AIENG-016](HU-AIENG-016.md) (panel de búsqueda asistida y espejo del vocabulario), [HU-AIENG-018a](HU-AIENG-018a.md) (donde nace el hallazgo), [HU-AIENG-020](HU-AIENG-020.md) (diccionario de consulta y sus exclusiones), [HU-AIENG-021](HU-AIENG-021.md) (rama léxica que hace visible el efecto).
- Change: [`fix-enrichment-vocabulary-gaps`](../../../openspec/changes/fix-enrichment-vocabulary-gaps/) · ticket [T-AIENG-FIX1](../../../openspec/changes/fix-enrichment-vocabulary-gaps/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: El operador filtra por un tipo de pieza que antes no existía

**Dado que** el catálogo contiene once diademas, cuatro gemelos, tres llaveros y un cinturón
**Y** que hoy el desplegable «Tipo de pieza» sólo ofrece ocho categorías, ninguna de las cuales los nombra
**Cuando** el operador abre la búsqueda asistida y despliega el filtro de tipo
**Entonces** ve las cuatro categorías nuevas junto a las ocho existentes
**Y** al seleccionar «Diadema» la búsqueda devuelve **las once** diademas del catálogo que su punto de venta lleva, no una parte de ellas
**Y** el término que viaja al recuperador es el canónico sin tilde, aunque en pantalla lea «Cinturón»

### Escenario 2: Un producto mal etiquetado deja de contaminar la categoría ajena

**Dado que** hoy seis piezas etiquetadas `broche` son tres diademas, dos gemelos y un llavero
**Y** que dos diademas están etiquetadas `collar` y una `colgante`
**Cuando** el operador filtra por «Broche»
**Entonces** ninguna diadema, gemelos ni llavero aparece en el resultado
**Y** los productos que abandonan la categoría son exactamente los que la corrida enumeró, y no otros
**Y** el recuento de la categoría baja en el número de impostores corregidos, no en más

### Escenario 3: Un nombre propio no se convierte en tipo de pieza

**Dado que** el catálogo contiene `Broche Cinturón de Orión` y `Anillo Cinturón de Orión`, donde «Cinturón» es la constelación
**Y** que ambos están hoy correctamente etiquetados como `broche` y `anillo`
**Cuando** se reenriquecen con el prompt que ya conoce el término `cinturon`
**Entonces** su `piece_type` **no cambia**
**Y** ese resultado se comprueba explícitamente y se publica en el informe, en lugar de excluirlos de la corrida para no arriesgar

### Escenario 4: Una joya que el vocabulario sigue sin poder nombrar se queda sin tipo, y eso es correcto

**Dado que** el catálogo contiene un producto llamado `Joya del Zodiaco`, sin descripción
**Y** que ninguno de los cuatro términos nuevos lo nombra
**Cuando** se reenriquece con el prompt nuevo
**Entonces** su `piece_type` sigue siendo nulo
**Y** ése es el resultado esperado y está declarado como tal, no como un pendiente
**Y** después de la corrida es **el único** producto del índice sin tipo de pieza

### Escenario 5: Ampliar el vocabulario es un acto consciente en todos los sitios donde está replicado

**Dado que** la lista canónica de tipos de pieza está replicada en el vocabulario, en el prompt, en el espejo del frontend y en dos specs vivas
**Y** que existen tests que fijan esa lista precisamente para que ningún cambio pase inadvertido
**Cuando** se añaden los cuatro términos
**Entonces** los tests fijados **fallan**, y esa es la señal correcta
**Y** se actualizan uno a uno, incluido el que usa uno de los términos nuevos como ejemplo de término desconocido, al que se le da otro ejemplo en lugar de eliminarlo
**Y** las dos specs vivas se corrigen mediante deltas del change, porque la validación estructural las daría por buenas siendo falsas

### Escenario 6: La versión del prompt no puede mentir sobre qué prompt produjo el perfil

**Dado que** la versión del prompt y la ruta del fichero se declaran hoy por separado
**Y** que actualizar una sin la otra sellaría los perfiles con una versión que no los produjo
**Cuando** se salta a la versión nueva
**Entonces** la ruta del prompt se deriva de la versión declarada, de modo que no pueden divergir
**Y** existe una comprobación de que el fichero efectivamente cargado se identifica a sí mismo con esa versión
**Y** el prompt de la versión anterior permanece en el repositorio sin modificar, porque los perfiles que no se reenriquecen siguen declarando que vienen de él

### Escenario 7: El corpus se mueve una sola vez y sólo para la cohorte

**Dado que** el texto de origen de los productos no cambia, así que el salto de reenriquecimiento se omitiría por hash
**Cuando** se lanza la corrida sobre la cohorte enumerada, forzando el reenriquecimiento
**Entonces** se reenriquecen exactamente los productos de la cohorte y ninguno más
**Y** una única sincronización incremental posterior recalcula el texto canónico y el embedding **sólo** de las filas cuyo contenido cambió
**Y** la versión de embedding y la del texto canónico no se tocan
**Y** ninguna migración se crea ni se aplica

### Escenario 8: Dos generaciones de perfiles conviven sin que ninguna métrica las mezcle en silencio

**Dado que** tras la corrida el catálogo tiene perfiles de dos versiones de prompt
**Cuando** se calculan métricas agregadas de enriquecimiento sobre el corpus
**Entonces** se reportan **por versión de prompt**, igual que otras métricas se reportan por origen del dato
**Y** la convivencia se declara como dato trazable y no se resuelve reenriqueciendo el catálogo entero

### Escenario 9: El extractor deja de dar por hecho que todo lo que entra es una joya

**Dado que** el prompt abre declarando que extrae atributos de joyería y no contempla otra cosa
**Y** que ante un servicio o un consumible el extractor elige el hiperónimo más plausible porque es lo que se le pidió
**Cuando** el enunciado advierte de que el catálogo puede contener servicios, consumibles y artículos de regalo
**Entonces** para esas filas el tipo de pieza es nulo en lugar de una conjetura
**Y** se declara que esta mejora es **prospectiva**: las filas que la motivaron ya fueron retiradas del índice, así que no hay población viva sobre la que medirla hoy

### Escenario 10: Fuera de alcance explícito

**Dado que** esta historia amplía el vocabulario y mueve veintidós productos
**Cuando** se revisa el entregable
**Entonces** los 1.200 perfiles **no** se reenriquecen
**Y** `filigrana` sigue siendo una exclusión declarada, con su motivo actualizado
**Y** no hay campo nuevo de clasificación, ni migración, ni ruta HTTP nueva
**Y** `ai-service/openapi.json` no tiene diff
**Y** `indexing/embeddings.py`, el constructor de texto canónico y la versión de embedding no tienen diff
**Y** la sugerencia de familias no se reejecuta, aunque la pareja de llaveros quede por primera vez en condiciones de formar una

---

## Notas adicionales

- **Actor: el Operador, por tercera vez consecutiva** tras C21 y C22. La progresión es coherente: C21 mejoró *qué* se encuentra, C22 *cuánto* llega a la pantalla, y esto mejora *cómo se puede acotar* lo que llega. Es la parte del sistema que el operador manipula con el dedo, no con el teclado.

- **El valor real no es léxico y conviene no fingir lo contrario.** Buscar «diadema» ya devuelve las once. Lo que esta historia compra es el **facet**, la limpieza de tres categorías y el fin del nulo como estado mayoritario del hueco. Los criterios de aceptación están escritos sobre eso a propósito.

- **Esta historia contradice su propia ficha en dos puntos**, y ambos con medición delante: la población (22 y no 11) y el criterio de extremo a extremo (que ya pasa hoy). Es el tercer change consecutivo en el que la exploración refuta lo escrito antes —C21 refutó cuatro puntos, C22 tres— y el mecanismo que lo hace posible es el mismo: medir contra el índice vivo antes de redactar.

- **`design.md` es obligatorio en el change.** Hay al menos cinco decisiones con alternativa real y coste asimétrico: el tamaño de la cohorte, el grupo de control, la forma canónica de los términos, qué hacer con la triple réplica del vocabulario y cómo versionar el prompt. Dos de ellas contradicen la ficha.

- **La suite unitaria no puede probar el prompt.** La spec viva prohíbe abrir sockets a proveedores y los tests inyectan un `EnrichLlm` falso que devuelve lo que se le programe. Un test llamado «los servicios reciben tipo nulo» probaría el pipeline, no el enunciado. Por eso el nombre del test debe decir lo que realmente comprueba y **la corrida de reenriquecimiento es la evaluación**.

- **La zona de la ficha se queda corta otra vez, y van once.** Declara `enrichment/`, `prompts/`, `frontend/src/lib/` y una pasada por `backend/`. Hay que sumar `ai-service/src/jbg_ai/retrieval/` (el overlay de C20 y sus dos tests) y un segundo árbol de specs.

- **Riesgo a comprobar, no a suponer:** reenriquecer con `v2` puede mover **otros campos** de los veintidós —materiales, piedra, etiquetas— además del tipo. El informe publica el diff completo, no sólo `piece_type`.

- **Comprobación previa a la corrida:** que ningún perfil de la cohorte tenga revisión humana registrada. El reenriquecimiento la borra y lo deja en el log; los 1.200 se aprobaron en modo masivo, así que no debería haber ninguna, pero es algo a verificar y no a dar por hecho.

- **Limitación a declarar en el README**, hermana de las de C20, C21 y C22: el catálogo convive con dos versiones de prompt de enriquecimiento, y cualquier métrica agregada sobre atributos extraídos debe reportarse por versión.

- **Plazo duro heredado del plan:** antes de que **C24** etiquete su línea base. El texto canónico sigue siendo `source-text/v1` y no delataría el cambio, así que un golden set etiquetado antes de esta historia describiría un corpus que ya no existe.

---

## Tareas

1. Completar los artefactos OpenSpec del change `fix-enrichment-vocabulary-gaps`: `proposal`, **`design.md` obligatorio**, `specs` (deltas de `catalog-enrichment-pipeline` y `query-expansion`) y `tasks`.
2. **Vocabulario:** cuatro términos nuevos en `piece_type.terms` de `vocabularies.yaml`, en la forma canónica acordada.
3. **Prompt:** crear `prompts/enrichment/v2.md` con la lista ampliada y la línea sobre servicios, consumibles y regalo. **No modificar `v1.md`.**
4. **Versionado del prompt:** `PROMPT_VERSION` a `enrichment/v2` y `load_prompt()` derivando la ruta de la constante, más el test que comprueba que el fichero cargado se identifica con ella.
5. **Overlay de consulta:** cerrar las cuatro `exclusions` que reclamaban este change, actualizar el motivo de `filigrana`, y añadir la forma de superficie `gemelo`.
6. **Tests fijados:** actualizar los cuatro, incluido el cambio de ejemplo en el que comprueba que un canónico desconocido se rechaza.
7. **Espejo del frontend:** cuatro opciones nuevas en `PIECE_TYPE_OPTIONS` con su `label`, y su test fijado.
8. **Deltas de specs:** `catalog-enrichment-pipeline` (lista canónica y versión de prompt en `MODIFIED`, más un requisito `ADDED` sobre filas que no son joyería) y `query-expansion` (el escenario de las lagunas de vocabulario).
9. **Corrida de reenriquecimiento** de los 22 SKU enumerados, en un solo lote, con `force` y modo masivo, previa comprobación de que ninguno tiene revisión humana registrada.
10. **Una sola sincronización incremental** del índice, verificando que el número de documentos reembebidos coincide con el de perfiles cuyo contenido cambió.
11. **Informe** `fix1-vocabulary-gaps-measurements.md` con la tabla de las 22 filas antes/después —diff completo, no sólo `piece_type`— y el veredicto de los dos de control.
12. **Verificación de extremo a extremo** por la interfaz: filtrar por «Diadema» y por «Broche» y comprobar los recuentos, no sólo que la consulta devuelve algo.
13. Actualizar [`Documentos/epicas.md`](../../epicas.md) (EP12) y la limitación del README de `ai-service`.
14. `openspec validate --all --strict` en `0 failed` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** **3** — no desbloquea ninguna arista del grafo y afecta al 1,8 % del corpus, pero es lo único que el operador manipula directamente y hoy le ofrece ocho categorías para un catálogo que tiene doce. Corrige además un facet que devuelve resultados falsos.
- **Urgencia (mercado / feedback):** **4** — no está en la cadena crítica, pero **arrastra un plazo duro**: tiene que estar antes de que C24 etiquete su línea base, porque el texto canónico no delataría el cambio y el golden set describiría un corpus que ya no existe.
- **Complejidad / esfuerzo:** **2** — no hay algoritmo, ni migración, ni interfaz nueva, ni movimiento de contrato. Lo que hay es **cinco réplicas del mismo dato que hay que mover a la vez**, cuatro tests fijados que saltan, dos specs vivas que quedan falsas y una corrida de datos de veintidós filas que hay que revisar a mano.
- **Riesgos y dependencias:**
  - **Dos specs vivas quedan falsas si no se emiten sus deltas**, y `openspec validate --all --strict` **seguiría en verde** sobre ellas, porque valida estructura y no verdad. Sería peor que las tres specs malformadas de agosto: aquéllas rompían el formato y el validador las cazó; éstas quedarían bien formadas y mintiendo.
  - **`test_overlay_anchor_absent_from_the_base_is_a_vocabulary_gap` falla en la dirección contraria** a la esperada (`DID NOT RAISE`) y la tentación es borrarlo. Borrarlo elimina la guarda que impide colar lagunas de vocabulario disfrazadas de sinónimos, que es justo el mecanismo que hizo visible este change.
  - **La tentación de reenriquecer los 1.200** «ya que estamos»: reclasificaría productos de forma difusa y sin petición, y ninguna revisión manual cubre mil doscientas filas.
  - **La tentación de excluir los dos de Orión** «para no arriesgar»: convierte la comprobación más valiosa del change en una suposición.
  - **La tentación de editar `v1.md` en lugar de crear `v2.md`**: deja a 1.178 perfiles declarando una procedencia que ya no se puede verificar.
  - **Colisión con `PROMPT_VERSION` a medias**: si se bumpea la constante sin derivar la ruta, la corrida sella veintidós perfiles con una versión que no los produjo, y el defecto es indetectable después.
  - **Zona compartida con C23**, que también entra en `enrichment/`, y con C25, que comparte `retrieval/` por el overlay. No se abren en paralelo, aunque los abra la misma persona.
  - **Dependencia de entorno:** la corrida necesita `STUB_MODE=false` y `JPV_RAG_LLM_API_KEY`, con el contenedor recreado según el runbook de C12. Sin eso, el reenriquecimiento devuelve el ciclo del stub y el informe describiría una ficción.

---
