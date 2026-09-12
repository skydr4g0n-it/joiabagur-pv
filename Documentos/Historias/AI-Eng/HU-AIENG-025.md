# HU-AIENG-025: Recalibrar el ranking y la abstención — que la fusión fusione, que el stock pese y que el buscador sepa callar

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** corregir la fusión que hoy entierra a la rama semántica, **hacer que la disponibilidad real de la tienda pese en el orden** y dar al buscador una regla para no contestar cuando no tiene respuesta — todo medido contra el golden set de C24 y con cada efecto en su propia fila de la tabla,
**para** que el operador vea primero lo que puede vender de verdad, que el proyecto pueda atribuir cada mejora a su causa, y que «no hay nada» deje de ser indistinguible de «no lo he encontrado».

---

## Descripción

C24 entregó el juez y, al usarlo, encontró tres cosas que nadie buscaba. Esta historia las
resuelve. No es la historia que la ficha de C25 describía —*«disponibilidad, rotación y perfil de
POS como reordenación suave»*— porque la exploración **refutó dos de sus puntos y descubrió un
defecto mayor que todos ellos juntos**.

### El problema que gobierna la historia: la fusión no fusiona, concatena

`v2-hibrido` saca **nDCG@5 0,172** en `descripcion-sin-anclaje` —la categoría más grande del
golden set, 12 consultas— frente a **0,431** de `v1-vectorial`. **El híbrido es 2,5 veces peor
que la rama vectorial sola** justo en las consultas donde la semántica es la única que puede
responder.

No es un peso mal calibrado. Es aritmética:

```
  score(d) = Σᵢ wᵢ / (k + rangoᵢ(d))      k = 60, profundidad = 60
  rama léxica: w_typed 0,50 + w_expanded 0,50 = 1,00 votos
  rama vectorial:                    w_vector = 0,33 votos

  documento léxico en el rango 60 (el peor puesto posible) →  1,00/120 = 0,008333
  mejor documento que sólo vio la rama vectorial            →  0,33/61  = 0,005410
```

**Los 60 documentos léxicos ganan al #1 vectorial, en toda consulta, siempre.** La rama semántica
sólo puede colocar algo si la léxica también lo vio.

Y se comprobó en los datos del run publicado. El documento de grado 2 que la rama vectorial pone
en el #1 cae en la **posición 33** del híbrido en tres consultas distintas:

| consulta | pos. en `v1-vectorial` | pos. en `v2-hibrido` |
|---|---:|---:|
| `la campanita que se cuelga a los bebes para proteger` | 1 | **33** |
| `follaje seco que cae en septiembre` | 1 | **33** |
| `una bicicleta antigua` | 1 | **33** |
| `un molusco que se agarra a las piedras` | 9 | **53** |

Y el porqué del 33, verificado:

```
q06, q08, q10 — los 32 primeros del híbrido son SÓLO léxicos    : true
                la cola conserva EXACTAMENTE el orden vectorial  : true
```

**Los documentos léxicos primero y detrás la lista vectorial intacta.** No hay fusión: hay una
partición dura. El premio al consenso que justifica RRF sólo opera dentro del bloque léxico.
Ejecutando `fuse()` con `wC = 0,33` sobre una lista léxica de 32 documentos, el #1 vectorial cae
en la posición 33: el modelo predice el dato medido.

**Y hay un segundo sesgo que nadie había visto: los huecos.** `typed` aporta hasta 60 documentos
y `expanded` otros 60, cada uno truncado por separado, así que la rama léxica puede meter **120
documentos distintos** frente a los 60 de la vectorial. La configuración actual sobrepondera el
lado léxico por dos vías independientes: **el doble de huecos y el triple de voto**.

### El segundo problema: el juez es ciego a lo que esta historia añade

Se leyó [`criterion.md`](../../../ai-service/evals/golden/criterion.md) entero buscando *stock*,
*disponibilidad* o *rotación*. **No aparecen.** La relevancia se juzga contra lo que la pieza
**es**, nunca contra lo que la tienda **tiene**. Así que si A es grado 2 y está agotado y B es
grado 0 y hay cuatro, ordenar `B, A` **baja** el nDCG@5.

Un barrido que maximice nDCG@5 converge, por construcción, a **peso 0 en todas las señales de
negocio**. La instrucción de la ficha —*«pesos calibrados contra el golden set»*— tomada al pie
de la letra es una máquina para demostrar que la funcionalidad no debe existir.

### El tercer problema: hoy la señal no corre

`v2-hibrido.yaml` lleva `pos_prefilter: false`, y sin POS el SQL emite `NULL AS qty_bucket`.
**En las 192 filas del run publicado la penalización de disponibilidad que C22 entregó no se
disparó ni una vez.** Está sin medir.

### Y el criterio de aceptación que se hereda no es alcanzable

El `qa.md` de C24 lo dejó escrito: *«Recall@5 sobre la porción real es 0,483 contra 0,85 […] es
el dato que C25 tiene que mover.»* No se puede: el recall a 5 depende de **qué** entra en la
ventana, y las señales sólo reordenan lo que ya entró. La única palanca de relevancia medida
—subir `wC`— dio +0,057 y la regla la vetó.

---

### Alcance de esta historia (sí)

- **Fusión en dos etapas con pesos por rama** en `retrieval/orchestrator.py`: las dos listas
  léxicas se fusionan entre sí y el resultado se fusiona con la vectorial. **La fusión plana se
  conserva como modo seleccionable**, porque `v2-hibrido` tiene que seguir reproduciendo la línea
  base publicada.
- **Regla adaptativa por cobertura**, que baja el peso léxico en proporción a cuánto de la
  consulta casó su mejor documento. Consume `coordination`, que hoy se calcula, viaja y se tira.
- **Señal de punto de venta separada del alcance**: `signal_pos_id` por `LEFT JOIN` (lee) frente
  a `scope_pos_id` por `INNER JOIN` (restringe). El prefiltro sigue apagado en evaluación.
- **`sales_30d` en la ruta de recuperación**, como **desempate declarado** y no calibrado.
- **Score continuo en el último bloque de `demotion_rank`**, conservando lexicográfico lo que el
  operador tecleó.
- **Métrica `nDCG@5 operativo`** con ganancia efectiva función de (grado × disponibilidad), y
  `nDCG@5` de relevancia pura como **guardarraíl**. Las dos se publican.
- **Regla de abstención** re-fijada, tras medir primero la distribución de `min(distancia)` por
  consulta — la cantidad que decide y que **no existe en ningún artefacto**.
- **Golden set ampliado**: `fuera-de-dominio` de 5 a 15-20 consultas, y la partición de ajuste
  crecida. Más *pooling* de lo que `v2b` y `v3` promuevan, con juicios apendables.
- **Barrido en dos fases**: con proveedor para la fusión, y **re-puntuado offline** sobre ventanas
  persistidas para las señales.
- **Regla de decisión reformulada** antes de re-medir: la lectura que decide pasa a ser `new`.
- **Tabla de ablations de seis filas** con `v2b-fusion` aislando la fusión de las señales, y las
  seis re-corridas bajo la versión nueva del golden set.
- **Dos capacidades nuevas**: `business-signals-ranking` y `retrieval-abstention`, más deltas
  `MODIFIED` sobre `hybrid-fusion`, `pos-projection` y `retrieval-evaluation`.

### Fuera de alcance (no)

- **Penalizar la variante ambigua dentro de familia.** **Refutado por medición** (§9.2 del
  informe): el reparto real de familias acota la inundación a 2 de 156, el panel ya pinta
  `Talla {variantLabel}`, `variante-talla` ya es la mejor categoría (0,830) y diversificar
  **baja** el nDCG@5 cuando las hermanas son grado 2. La agrupación es **presentación** y
  pertenece a C30/C36.
- **Calibrar `1-2` frente a `3+`.** **Refutado por construcción**: con la ganancia efectiva los
  dos caen en la rama «hay stock», ninguno pierde grado y **no existe función objetivo que pueda
  ordenarlos**. Se conserva el binario y se confirma con una medición.
- **El perfil comercial por POS** que la ficha nombraba: anulado con la rama de C19 el
  2026-08-31.
- **El criterio absoluto del §11.2** (Recall@5 ≥ 0,85 · nDCG@5 ≥ 0,75): se sustituye por criterio
  relativo y la brecha se declara como limitación.
- **Sustitutos** (`POST /v1/retrieval/substitutes`): **C26**. Las 4 consultas `sustituto` del
  golden set siguen sin juzgar.
- **RAGAS, validador anti-alucinación y escenarios de agente**: **C38**, en este mismo runner.
- **Reranking.** C24 dejó el protocolo y el número (1 consulta de 48 con grado 2 en el top-20 y
  fuera del top-5); no se implementa.
- **Migración de Alembic.** Ninguna: `ai.pos_projection` ya tiene `sales_30d`, `sales_90d`,
  `last_sale_at` y `computed_as_of` por fila.
- **Ruta HTTP nueva ni `openapi.json` regenerado.** No se emite señal de familia al contrato: el
  consumidor no existe todavía.
- **Cualquier cambio en `backend/`, `frontend/`, `terraform/` o `.github/workflows/`.** Cero.
- **Tocar `indexing/embeddings.py`** (congelado desde C11), `enrichment/vocabularies.yaml`,
  `retrieval/synonyms.py` ni el paquete `knowledge/`.
- **Reindexar.** El corpus no se mueve.

### Decisiones de diseño ya acordadas

Las quince están razonadas con alternativas y con las mediciones que las sostienen en el
[informe de exploración](../../Proyecto%20Final%20AIEng/informes/c25-exploration-measurements.md).

| # | Decisión | Motivo |
|---|---|---|
| **D1** | **Dos capacidades, no una**: `business-signals-ranking` y `retrieval-abstention` | Comparten el golden set y nada más. Ponderar el orden y decidir si contestar son preocupaciones distintas, con tests distintos y requisitos distintos |
| **D2** | **Criterio de aceptación relativo**: `v2b` bate a `v2` y `v3` bate a `v2b` en las tres lecturas por encima del margen. La brecha absoluta se declara | Recall@5 real 0,483 contra 0,85 es +0,37, y la única palanca de relevancia medida dio +0,057. Precedente: C18 ya encontró que *«el umbral del §7.5 no existe, y el plan se contradecía»* |
| **D3** | **Métrica objetivo `nDCG@5 operativo`**: `g_efectivo = máx(grado−1, 0)` si `qty_bucket = '0'`, el grado intacto si no. **Guardarraíl**: `nDCG@5` de relevancia pura no cae más de 0,05 | **No introduce una constante: reutiliza la escala.** El grado 1 ya es *«sustituto plausible que el operador ofrecería como segunda opción»*, y una pieza que no puedes poner sobre el paño es eso. Precedente: C24 ya publica dos lecturas de la misma anotación |
| **D4** | **`signal_pos_id` (LEFT JOIN) separado de `scope_pos_id` (INNER JOIN)**. Calibrar en **MAO-AIR** (34,4 % a cero), validar en **FORNELLS** (12,0 %) y **HT-GALDANA** (11,7 %) | Mide la reordenación **sin** pagar el coste de recall del prefiltro, que es la confusión que C22 se negó a introducir. Calibrar donde la señal apenas aparece es calibrar sobre ruido; calibrar sólo en el extremo es ajustar a una tienda atípica |
| **D5** | **Fusión en dos etapas con pesos por rama.** Reparto interno léxico 0,5/0,5 **fijo y no barrido** | Hace que el voto total de la rama sea exactamente `w_lex` **sin depender de cuántas de sus listas dispararon** —hoy el umbral de cruce es 0,469 o 0,938 según si el AND de `websearch` casó, una propiedad de la consulta que nadie declaró—. Y arregla el reparto de huecos: 60 por rama, no 120 contra 60. La evidencia de C21 dice que las dos listas son *necesarias*, no que una valga más |
| **D6** | **Sólo importa el cociente `ρ = w_vec / w_lex`**, así que el barrido es de **una dimensión**. Rejilla `{0,6 · 0,8 · 0,9 · 0,95 · 1,0 · 1,05 · 1,1 · 1,25}`, arranque en **`ρ = 1,0`** | Medido con `fuse()`: escalar los dos pesos preserva el orden. Y la banda útil es **`ρ ∈ [0,9 ; 1,1]`** —a 0,95 el #1 vectorial entra en el top-5, a 0,90 cae al 8— donde la rejilla de C24 tenía **un solo punto**. Por eso su óptimo parecía un filo de cuchillo. `ρ = 1` se explica en una frase: *cada rama tiene un voto* |
| **D7** | **Regla adaptativa `w_lex × cobertura`**, con `cobertura = coordinación del mejor documento / grupos contables cuya tsquery no es vacía`. **Cero parámetros** | Ataca el daño donde está en lugar de pagarlo en todas las consultas, que es lo que hace `wC = 1,0` global (`sinonimos` −0,039, `materiales` −0,010). La señal ya se calcula y se tira. Y el apunte de S10 avisa: *«si no puedes explicar en una frase por qué un boost vale 1,3 y no 1,5, no estaba listo»* |
| **D8** | **El denominador excluye los grupos cuya `tsquery` es vacía**, y se calcula en la misma sentencia con `numnode(...) > 0` | Medido: las palabras vacías **cuentan como grupo** (`['de']`, `['una']`, `['y']`, `['que']`). Con el denominador ingenuo, `sortija de plata` daría cobertura 0,67 y la regla **recortaría un tercio del peso léxico en una consulta que puntúa nDCG 1,000** — destruiría justo las categorías que existe para no tocar |
| **D9** | **Score continuo sólo en el último bloque de `demotion_rank`**; el orden lexicográfico de precio, talla y material se conserva | El MUST vivo de `pos-projection` exige que *«dentro del techo precede a fuera, sea cual sea el stock»*. Y no pierde alcance: `demote()` hace *early return* cuando ningún filtro tecleado se dispara, que es el caso mayoritario, así que el bloque de cola **es la lista entera** donde importa |
| **D10** | **Rotación como desempate declarado con peso fijo, no calibrado**, y el README dice por qué | No hay gancho en la rúbrica —una pieza que rota no es *más relevante*—, la vía online tiene **31 filas y 12 textos** escritos por el desarrollador, y la señal es no nula en el **23,54 %** de los pares. La frase que justifica un desempate existe; la que justificaría un peso continuo, no |
| **D11** | **Abstención: medir primero** `min(distancia)` por consulta, contestables frente a fuera-de-dominio. Y **ampliar `fuera-de-dominio` de 5 a 15-20** | C24 midió el solape **por documento** (hueco −0,4739) y concluyó que un escalar no sirve. Pero la abstención la decide el **mejor acierto por consulta**, que **no está en ningún artefacto** — y C23 separó limpiamente con exactamente esa cantidad (0,5062 contra 0,5145). Son preguntas distintas. Y n=5 no calibra nada: por la rúbrica, fuera-de-dominio es todo grado 0, así que ampliar no cuesta etiquetado |
| **D12** | **La medición de D11 gobierna la secuencia**: si el umbral es un escalar en el `WHERE`, **mueve la ventana** y va en la fase A; si es una regla post-recuperación, no la mueve y va en la fase D | El barrido barato de las señales depende de que la ventana no cambie. Asignar mal la fase invalida todas las ventanas capturadas |
| **D13** | **Barrido en dos fases**: `capture` (una recuperación por consulta con la fusión congelada, persistiendo la ventana de 60 con sus señales) y `rescore` (re-puntuado en memoria) | Las señales no cambian qué se recupera, sólo el orden. Cientos de combinaciones en segundos, cero proveedor, y `test_calibration_sweep_is_reproducible` pasa de promesa sobre semillas a **propiedad estructural** |
| **D14** | **Regla de decisión reformulada, escrita y fechada antes de re-medir**: la lectura que decide es **`new`** (40 consultas); `tuning` se reporta como **diagnóstico de contaminación** y no veta | Medido: **6 de 8** consultas de ajuste están en el techo del nDCG@5 y **las 8** en el de Recall@5, P@3 y MRR; y **7 de 8 salen de la lista curada de C20/C21**, con 10/10 en la rama léxica. La condición veta subir el peso vectorial con las consultas elegidas para que la léxica ganase. C24 ya publicó 0,942 en ajuste contra 0,535 en nuevas y lo llamó *contaminación cuantificada*: **una partición contaminada es evidencia de sobreajuste del titular, no un grupo de control**. El argumento es visible sin mirar el resultado del barrido, que es lo que lo distingue de un ajuste *post hoc* |
| **D15** | **Tabla de seis filas**, con `v2b-fusion` aislando la fusión. **Las seis se re-corren** bajo la versión nueva del golden set, `v0-cag` incluida, y el ganador del barrido se **re-confirma** en esa versión | Sin `v2b`, un `v3` que mejorase sería **inatribuible**. Y al profundizar el *pool* se mueve `golden_set_version`, así que ninguna fila del informe de C24 sigue siendo comparable. `v0-cag` son 12 consultas a $0,002673: **tres céntimos** por que la tabla entera comparta una procedencia |

**Cortes que no se reabren:** `indexing/embeddings.py` congelado desde C11 ·
`enrichment/vocabularies.yaml` intacto · `retrieval/synonyms.py` intacto · sin ruta HTTP nueva ni
`openapi.json` regenerado · sin migración · sin reindexar · sin tocar `backend/`, `frontend/`,
`terraform/` ni `.github/workflows/` · Python no lee el esquema `public` por SQL ·
`HT-ARTRUTX` excluido (surtido cero, responde 503).

**Referencias:**

- Mediciones y las quince decisiones: [c25-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c25-exploration-measurements.md).
- Diseño RAG [§7.6, §11.1, §11.2 y §15](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — recuperación, golden set, ablations y limitaciones a declarar.
- Plan de changes, [ficha C25](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) y la entrada del §0 de esta exploración.
- Informes que dejaron el trabajo preparado: [c24-implementation-measurements.md](../../Proyecto%20Final%20AIEng/informes/c24-implementation-measurements.md) (la brecha de aceptación, el solape de distancias y el veto del barrido), [c22-implementation-measurements.md](../../Proyecto%20Final%20AIEng/informes/c22-implementation-measurements.md) (23,54 % de rotación no nula, reparto de ceros por POS), [c21-hybrid-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md) (la rúbrica que fijó los pesos y que se recusa a sí misma), [c18b-family-review-report.md](../../Proyecto%20Final%20AIEng/informes/c18b-family-review-report.md).
- Specs vivas que enmarcan el change: `openspec/specs/hybrid-fusion/`, `openspec/specs/pos-projection/`, `openspec/specs/retrieval-evaluation/`, `openspec/specs/vector-retrieval/`, `openspec/specs/query-expansion/`.
- Historias previas: [HU-AIENG-020](HU-AIENG-020.md) (diccionario de sinónimos), [HU-AIENG-021](HU-AIENG-021.md) (fusión híbrida), [HU-AIENG-022](HU-AIENG-022.md) (prefiltro por punto de venta), [HU-AIENG-024](HU-AIENG-024.md) (arnés y golden set).
- Apuntes: [S10 · Filtrado contextual y temporal](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Filtrado%20contextual%20y%20temporal.md), [S10 · Búsqueda híbrida](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Busqueda%20hibrida.md), [S16 · Un sistema debe saber decir «No lo sé»](../../Sesiones%20Master%20AIEng/S16_Produccion_II/Un%20sistema%20debe%20saber%20decir%20%E2%80%9CNo%20lo%20se%E2%80%9D.md), [S16 · Tratamiento de regresiones](../../Sesiones%20Master%20AIEng/S16_Produccion_II/Tratamiento%20de%20regresiones.md).
- Change: [`recalibrate-ranking-and-abstention`](../../../openspec/changes/archive/2026-09-12-recalibrate-ranking-and-abstention/) · ticket [T-AIENG-025](../../../openspec/changes/archive/2026-09-12-recalibrate-ranking-and-abstention/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: La rama semántica puede colocar un resultado sin permiso de la léxica

**Dado que** una consulta describe una pieza sin usar ninguna palabra de su ficha —`una bicicleta antigua`, cuyo grado 2 la rama vectorial pone en el #1
**Y** la rama léxica devuelve documentos que casan una sola palabra de la consulta
**Cuando** se sirve la recuperación con la fusión por rama
**Entonces** ese documento de grado 2 aparece **dentro del top-5**
**Y** no en la posición 33, que es donde lo deja la fusión plana
**Y** el informe publica el antes y el después de las tres consultas medidas

### Escenario 2: La corrección de la fusión no cobra peaje donde la rama léxica acierta

**Dado que** las categorías `materiales`, `sinonimos`, `lexico-exacto` y `piedra` tienen cobertura 1,00 —su mejor documento casa todos los grupos expresables
**Cuando** se aplica la regla adaptativa por cobertura
**Entonces** el peso léxico de esas consultas **no se modifica**
**Y** su nDCG@5 se mueve en **cero**
**Y** si alguna se moviera, el test falla en lugar de dejarlo pasar

### Escenario 3: Una palabra vacía no rebaja el peso de una consulta bien anclada

**Dado que** la consulta `sortija de plata` produce tres grupos contables y uno de ellos es `['de']`, cuya `tsquery` es vacía y no puede casar con ningún documento
**Cuando** se calcula la cobertura
**Entonces** el denominador cuenta **dos** grupos y no tres
**Y** la cobertura es 1,00 y el peso léxico queda intacto
**Y** lo mismo ocurre con `anillo de plata y oro`, que tiene dos grupos vacíos de cinco

### Escenario 4: Un producto agotado baja en la lista y sigue estando

**Dado que** el punto de venta lleva productos con stock y productos a cero que casan la consulta
**Y** la consulta se sirve con `signal_pos_id` puesto y `scope_pos_id` sin poner
**Cuando** se ordenan los candidatos
**Entonces** los agotados siguen presentes entre los resultados
**Y** aparecen después de los comparables con stock
**Y** **ningún candidato se elimina** por su disponibilidad

### Escenario 5: Leer la señal no reduce el conjunto de candidatos

**Dado que** una consulta se sirve con `signal_pos_id` puesto y `scope_pos_id` sin poner
**Cuando** se compara el conjunto de candidatos con el de la misma consulta sin ninguna de las dos
**Entonces** los dos conjuntos son **idénticos**
**Y** en el primero los candidatos asignados traen su `qty_bucket` y su `sales_30d`
**Y** los no asignados los traen a nulo, que no es lo mismo que a cero

### Escenario 6: Lo que el operador tecleó manda sobre lo que no preguntó

**Dado que** una consulta expresa un techo de precio y los resultados difieren en precio y en stock
**Cuando** se ordenan los candidatos con las señales de negocio activas
**Entonces** los que están dentro del techo preceden a los que están fuera, **sea cual sea su stock**
**Y** las señales de negocio deciden el orden **sólo** entre candidatos que los filtros tecleados empatan

### Escenario 7: La rotación desempata y nunca derriba

**Dado que** dos candidatos empatan en la fusión y en su bucket de disponibilidad, y uno vendió y el otro no
**Cuando** se ordenan
**Entonces** el que vendió precede al que no
**Y** si en cambio difieren en disponibilidad, la disponibilidad decide y la rotación no la puede revertir
**Y** el peso de la rotación está declarado en configuración y **no** sale de un barrido

### Escenario 8: La métrica operativa no toca las etiquetas

**Dado que** un documento de grado 2 está agotado en el punto de venta de referencia
**Cuando** se calcula el `nDCG@5 operativo`
**Entonces** su ganancia efectiva es la del grado 1
**Y** el fichero de juicios **no se modifica**: el grado etiquetado sigue siendo 2
**Y** el informe publica la métrica operativa y la de relevancia pura **una al lado de la otra**

### Escenario 9: Un peso que cuesta relevancia se rechaza

**Dado que** una combinación de pesos de negocio sube el `nDCG@5 operativo`
**Y** hace caer el `nDCG@5` de relevancia pura más del margen acordado
**Cuando** se aplica la regla de decisión
**Entonces** esa combinación **no** se adopta
**Y** el informe registra la diferencia medida y la decisión de no actuar sobre ella

### Escenario 10: El barrido de señales no llama al proveedor

**Dado que** las ventanas de candidatos están capturadas con la fusión ya congelada
**Cuando** se recorre la rejilla de pesos de negocio
**Entonces** no se hace ninguna llamada al proveedor de *embeddings* ni ninguna consulta a la base
**Y** dos recorridos de la misma rejilla sobre las mismas ventanas dan **exactamente** el mismo resultado

### Escenario 11: La línea base publicada sigue siendo reproducible

**Dado que** la fusión por rama es ahora el camino recomendado
**Cuando** se ejecuta la configuración `v2-hibrido`
**Entonces** corre la fusión **plana** con los pesos de C21
**Y** reproduce las cifras del informe de C24 sobre la misma versión del golden set
**Y** la tabla conserva su fila de referencia

### Escenario 12: Cada efecto tiene su fila

**Dado que** el change corrige la fusión **y** añade señales de negocio
**Cuando** se publica la tabla de ablations
**Entonces** existe una fila `v2b-fusion` con la fusión corregida y **sin** señales de negocio
**Y** una fila `v3-senales` con `v2b` más las señales
**Y** la mejora de cada una se puede atribuir a su causa sin ambigüedad

### Escenario 13: La abstención se diseña después de medir, no antes

**Dado que** la cantidad que decide la abstención es el mejor acierto por consulta, y no existe en ningún artefacto
**Cuando** se ejecuta la primera tarea del change
**Entonces** se publica la distribución de `min(distancia)` de las consultas contestables frente a las de fuera de dominio
**Y** el informe declara si un solo valor las separa
**Y** la forma de la regla —escalar o relativa por consulta— se elige con esa cifra delante

### Escenario 14: El buscador contesta «no tengo eso» y no lo confunde con no encontrarlo

**Dado que** una consulta es plausible en joyería y el catálogo no la puede satisfacer
**Cuando** se sirve la recuperación con la regla de abstención activa
**Entonces** no se devuelve ningún candidato y la respuesta queda marcada de baja confianza
**Y** la tasa de abstención sobre fuera-de-dominio sube por encima de la de la línea base
**Y** las consultas contestables **siguen** devolviendo resultados: la regla no gana abstención a costa de callar cuando sí hay respuesta

### Escenario 15: Una fila con resultados que nadie juzgó no se presenta como comparable

**Dado que** las configuraciones nuevas promueven documentos que no estaban en el *pool* de C24
**Cuando** se publica la tabla
**Entonces** cada fila informa de su `unjudged@5`
**Y** la que supere el umbral queda marcada como no comparable
**Y** el *pooling* se profundiza y los juicios se **añaden** sin re-etiquetar lo ya hecho

### Escenario 16: Dos ejecuciones con distinta procedencia no se comparan

**Dado que** ampliar el golden set y añadir juicios mueve `golden_set_version`
**Cuando** se publica la tabla nueva
**Entonces** las seis filas comparten una sola tupla de procedencia
**Y** el ganador del barrido se **re-confirma** contra el titular en esa versión antes de fijarse
**Y** el informe de C24 se cita como histórico y no como fila comparable

### Escenario 17: La partición de ajuste informa y no veta

**Dado que** seis de las ocho consultas de ajuste están en el techo de la métrica de decisión y siete de las ocho se usaron para calibrar la rama léxica
**Cuando** se aplica la regla de decisión reformulada
**Entonces** la lectura que decide es la de las consultas nuevas
**Y** la lectura de ajuste se publica como diagnóstico de contaminación
**Y** la regla, con su argumento y su fecha, está escrita **antes** de ejecutar la medición

### Escenario 18: Fuera de alcance explícito

**Dado que** la ficha del change pedía penalizar la variante ambigua dentro de familia y calibrar los dos buckets no nulos
**Cuando** se cierra el change
**Entonces** ninguna de las dos se ha implementado
**Y** las dos están refutadas **con una medición** y anotadas en el §0 del plan
**Y** no se ha creado ninguna migración, ninguna ruta HTTP nueva ni se ha regenerado `openapi.json`
**Y** `backend/`, `frontend/`, `terraform/` y `.github/workflows/` quedan sin diff

---

## Notas adicionales

- **Actor: el desarrollador del proyecto**, como en C24 — pero a diferencia de aquélla, **el
  operador sí nota esto**. Tres cosas cambian en su pantalla: encuentra piezas que describe con
  sus palabras y que antes quedaban en la posición 33, lo que su tienda no tiene baja en la lista
  en vez de competir de igual a igual, y cuando el catálogo no puede responder se lo dicen en vez
  de servirle cinco cosas que no valen.

- **Es el sexto change consecutivo cuya exploración refuta lo escrito antes**, tras C21, C22,
  FIX1, C23 y C24. Y es el primero que refuta **a su propia ficha en dos puntos por medición**
  —la penalización de variante y la calibración de buckets— en lugar de reencuadrarla.

- **Decimotercera vez que la zona de una ficha se queda corta.** La ficha declara `retrieval/`; el
  change toca además `evals/`, `config/settings.py` y `evals/golden/`. Va tras C08, C07, C15,
  C16, C17, C18b, C20, C21, C22, C23 y C24.

- **El nombre del change cambia y el número no.** `add-business-signals-ranking` describiría un
  tercio de lo que hace, así que pasa a **`recalibrate-ranking-and-abstention`**. **C25 se
  conserva como número**: renumerar rompería las referencias de C26 (`prereq C22, C25`) y C27
  (`C10, C25`) y las aristas del §4 a cambio de nada.

- **El etiquetado necesita planificación propia**, más ligero que el de C24 porque no se parte de
  cero:
  - **Ampliar `fuera-de-dominio` de 5 a 15-20**: sólo hay que **escribir** consultas plausibles e
    imposibles, porque por la rúbrica todo es grado 0. ~45 min.
  - **Profundizar el *pool*** con lo que `v2b` y `v3` promuevan, juzgando **sólo lo nuevo**.
    Depende de cuánto promuevan; se estima tras la fase A.
  - **Crecer la partición de ajuste**, que con 8 consultas no arbitra nada en ninguna dirección.
  - Agrupado por categoría y con relectura diferida de las dudosas, como C24.

- **`design.md` obligatorio** en el change. Hay quince decisiones con alternativa real, dos
  refutaciones de la propia ficha, una reformulación de una regla de decisión heredada y un
  cambio de defaults de producción.

- **El orden de las fases no es una preferencia, es una restricción.** El barrido barato de las
  señales depende de que la ventana de candidatos no cambie, y la fusión la cambia. Invertir las
  fases invalida todas las ventanas capturadas, y la medición M1 decide en qué fase entra el
  trabajo del umbral.

- **Limitaciones a declarar en el README**, hermanas de las de C20, C21, C23 y C24:
  - **El criterio absoluto del §11.2 no se cumple.** Se declara la brecha y por qué la palanca de
    este change no podía cerrarla, en vez de re-etiquetar hasta que el número salga.
  - **El coste del prefiltro por punto de venta en recall sigue sin medir**, porque la evaluación
    lee la señal sin aplicar el alcance. Es deliberado: mezclarlos daría una cifra que no dice
    nada de ninguno de los dos.
  - **La rotación no está calibrada** y no puede estarlo contra este golden set. Entra como
    desempate declarado.
  - **Los pesos se calibran en un punto de venta y se validan en dos.** No son once.
  - **Sigue sin haber acuerdo entre anotadores** y el etiquetador escribió parte del corpus.
    Irreducible, heredado de C24.

- **Verificación posterior (no DoD de merge):** volver a ejecutar el arnés tras C26 para comprobar
  que las 4 consultas `sustituto` se pueden juzgar sobre el ranking nuevo; y medir si la
  corrección de la fusión mueve la comparación online de `SearchOrigin` que C04 dejó disponible.

---

## Tareas

1. **Verificar el entorno antes de nada** (base en el 5433 con los 1.168 documentos y la
   proyección de los 11 POS, clave de *embeddings* operativa, `SSL_CERT_FILE`). **Si algo falla,
   parar y configurarlo**: las cuatro mediciones de la fase 0 y el barrido lo necesitan.
2. Completar artefactos OpenSpec del change `recalibrate-ranking-and-abstention`: `proposal`,
   **`design.md` obligatorio**, `specs` (dos capacidades nuevas más tres deltas `MODIFIED`) y
   `tasks`.
3. **Fase 0 · M1** — distribución de `min(distancia)` por consulta, contestables frente a
   fuera-de-dominio. **Decide la forma de la regla de abstención y su fase.**
4. **Fase 0 · M2** — cobertura por consulta y categoría con el denominador corregido, para
   confirmar que la adaptativa dispara donde debe y nunca donde no.
5. **Fase 0 · M3** — hermanas de familia en el top-10 por consulta, cruzando los `ranked`
   publicados con `product_document.family_id`. Refuta o resucita la penalización de variante.
6. **Fase 0 · M4** — reparto de `1-2` frente a `3+` sobre los 6.050 pares asignados. Confirma el
   binario con una cifra.
7. **Escribir la regla de decisión reformulada**, con su argumento y su fecha, **antes** de
   ejecutar ningún barrido.
8. **Python — `retrieval/fusion.py`:** sin cambios en la fórmula; se verifica que soporta la
   composición en dos etapas.
9. **Python — `retrieval/orchestrator.py`:** fusión en dos etapas con pesos por rama, **modo
   plano conservado**, lectura de `coordination` y regla adaptativa por cobertura.
10. **Python — `retrieval/lexical.py` y `search.py`:** denominador de cobertura con
    `numnode(...) > 0` en la misma sentencia; `LEFT JOIN` de señal separado del `INNER JOIN` de
    alcance; `sales_30d` en el `SELECT`.
11. **Python — `retrieval/ports.py`:** `sales_30d` en `SearchHit` y `LexicalHit`; **cae el test
    guardián** `test_the_retrieval_path_cannot_read_the_sales_figures`.
12. **Python — `retrieval/filters.py`:** score continuo en el último bloque de `demotion_rank`,
    conservando lexicográfico lo tecleado.
13. **Python — `config/settings.py`:** `FUSION_DEFAULTS` reformulado por rama, `BUSINESS_DEFAULTS`
    nuevo, y el umbral según lo que dicte M1.
14. **Python — `evals/metrics.py`:** `nDCG@5 operativo` con la ganancia efectiva de D3, publicado
    junto a la relevancia pura.
15. **Python — `evals/configs.py`:** `signal_pos_id` y `fusion` como perillas; configuraciones
    `v2b-fusion` y `v3-senales`.
16. **Python — `evals/sweep.py`:** rejilla de `ρ` de una dimensión, fases `capture` y `rescore`, y
    la regla de decisión reformulada.
17. **Fase A** — barrido de la fusión sobre la rejilla de D6, con las variantes adaptativa
    continua y binaria. **Congelar `v2b`.**
18. **Fase B** — capturar las ventanas de 60 con sus señales, con la fusión ya congelada.
19. **Fase C** — barrido de señales por re-puntuado offline. **Congelar `v3`.**
20. **Fase D** — regla de abstención, si M1 la situó aquí.
21. **Ampliar el golden set**: `fuera-de-dominio` a 15-20, partición de ajuste crecida, y
    *pooling* de lo que `v2b` y `v3` promuevan con juicios apendables.
22. **Re-correr las seis filas** bajo la versión nueva y **re-confirmar** los ganadores de las
    fases A y C contra el titular.
23. **Informe versionado** en `ai-service/evals/results/` con la tabla v0→v3 de seis filas, las
    lecturas de D14, la distribución de D11 y el antes/después de las consultas sin anclaje.
24. **Tests** en `ai-service/tests/retrieval/` y `tests/evals/`, todos ejecutables sin proveedor.
25. Corregir el desfase de un día en `judged_at` que C24 dejó a propósito: **sale gratis aquí**,
    porque la corrida nueva ya se hace contra la versión corregida.
26. Actualizar `ai-service/README.md` y `ai-service/tests/README.md`, y renombrar las referencias
    a C25 en los comentarios de código que lo nombran como sucesor.
27. Enlazar la HU en [`Documentos/epicas.md`](../../epicas.md) (EP14, con nota en EP17).
28. `openspec validate --all --strict` en `0 failed` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** **5** — es el primer change de la rama de IA que
  mejora lo que el operador ve **y** puede demostrarlo con una métrica. La corrección de la
  fusión arregla un defecto vivo en la categoría más grande del golden set, y la abstención da al
  sistema el derecho a decir «no lo sé» que el apunte de S16 trata como requisito de seguridad
  antes que de calidad.
- **Urgencia (mercado / feedback):** **5** — con C24 archivado, **la cadena crítica arranca aquí**:
  `C25 → C26 → C34 → C36`. Bloquea a C26 y a C27.
- **Complejidad / esfuerzo:** **5** — es el change más complejo de la rama hasta ahora. Tres
  subsistemas (fusión, señales, abstención), dos capacidades nuevas, tres deltas sobre specs
  vivas, un orden de fases que no se puede invertir, y una regla de decisión heredada que hay que
  reformular con argumento antes de medir. Lo barato es el código; lo caro es la secuencia.
- **Riesgos y dependencias:**
  - **El denominador de la cobertura es el riesgo número uno.** Con el ingenuo, la regla
    adaptativa **degrada las categorías que existe para proteger** y lo hace pareciendo que
    funciona, porque el agregado global podría incluso subir. Se mitiga con M2 antes de
    implementar y con el test de cobertura 1,00.
  - **Invertir el orden de las fases** invalida las ventanas capturadas y hace que el barrido de
    señales mida una fusión que ya no es la vigente. Es un fallo silencioso: el barrido corre y da
    números.
  - **Reformular la regla de decisión después de que vetara algo** es indistinguible de un ajuste
    *post hoc* si no se escribe el argumento y la fecha **antes**. El argumento —partición
    saturada y contaminada— es visible sin mirar el resultado, y ahí está la defensa; perderla por
    orden de escritura sería un error de proceso, no de criterio.
  - **Perder la reproducibilidad de la línea base** si la fusión plana no se conserva como modo.
    La tabla se quedaría sin fila de referencia y el change sin forma de demostrar su propia
    mejora.
  - **El *pooling* nuevo puede ser grande.** No se sabe cuánto promoverán `v2b` y `v3` hasta
    terminar la fase A, así que el etiquetado no se puede dimensionar por adelantado. Se estima
    tras congelar `v2b`.
  - **La abstención tiene dos lados y sólo uno es fácil.** Subir la tasa sobre fuera-de-dominio es
    trivial bajando el umbral; hacerlo **sin** empezar a callar en las 43 contestables es el
    trabajo. Con la categoría a 5 consultas no se puede medir, de ahí la ampliación.
  - **Dependencia dura del entorno**: sin base levantada, sin la proyección de los 11 POS y sin
    clave de *embeddings* no hay fase 0 ni barrido. C23 se exploró con el contenedor apagado y
    tuvo que corregir cifras después.
  - **Zona compartida con C26** en `retrieval/`, que construirá sustitutos sobre este ranking; y
    con C38, que se integrará en este mismo runner.
  - **`HT-ARTRUTX` responde 503** por surtido cero: hay que excluirlo de la validación por POS.
