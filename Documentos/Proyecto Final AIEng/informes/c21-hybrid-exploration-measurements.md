# C21 — mediciones de la exploración (búsqueda híbrida y fusión RRF)

**Medido el 2026-09-02** contra el PostgreSQL local (`jpv-pv-postgres`, puerto 5433), sobre los
**1.168 documentos vivos** de `ai.product_document`, y contra el proveedor real de embeddings
(`openai/text-embedding-3-small`) para la rama vectorial. Todo en solo lectura; no se escribió
nada en la base ni en el índice.

> **Nota de entorno.** El TLS de esta máquina está interceptado y `certifi` no lo acepta. Para
> llamar al proveedor hay que exportar el almacén de raíces de Windows a un PEM y apuntar
> `SSL_CERT_FILE` a él (concatenado con el bundle de `certifi`). Es la misma causa del
> `--system-certs` que `CLAUDE.md` documenta para `uv`.

---

## 1. Las consultas reales del operador (`public."ProductSearchEvents"`)

31 filas, 12 textos distintos, todos escritos por el desarrollador — la limitación que C20 ya
declaró. Pero su **forma** sí es informativa, y es más descriptiva de lo que la ficha de C21 supone:

| veces | texto |
|---:|---|
| 9 | un anillo de plata para regalar |
| 4 | pendientes de oro con piedra azul |
| 4 | collar elegante para una boda |
| 2 | pendientes con motivo de caracola |
| 2 | pulsera de plata con motivos marinos |
| 2 | joya con forma de concha marina |
| 2 | algo dorado para el dia de la madre |
| 2 | anillo de filigrana tradicional menorquina |
| 1 | anillo de plata numero 1 / 2 / 3 · anillo de plata |

---

## 2. Cobertura del corpus por línea de `doc_text` — decide qué puede filtrar y qué no

| línea | documentos | % |
|---|---:|---:|
| `Descripción:` | 1.143 | 98 % |
| `Tipo:` | 1.157 | 99 % |
| `Materiales:` | 1.042 | 89 % |
| `Piedra:` | 630 | 54 % |
| `Talla:` | 529 | **45 %** |
| `Colores:` | 224 | 19 % |
| `Ocasiones:` | 150 | **13 %** |
| `Estilo:` | 133 | **11 %** |

**Consecuencia.** El enriquecimiento es fuerte en tipo y materiales y **débil en color, estilo y
ocasión**. Cualquier regla que exija un término de ocasión o estilo trabaja sobre un campo cubierto
al 11-13 %. `boda` casa **5** documentos y `regalo` **7** en todo el catálogo, pese a estar los dos
en `occasion_tags`.

Alcance de términos sueltos, para calibrar: `plata` 639 · `piedra` 630 · `talla` 537 · `anillo` 268 ·
`elegante` 149 · `dorado` 145 · `dia` 116 · `filigrana` 66 · `joya` 61 · `marino` 60 · `azul` 57 ·
`fiesta` 36 · `perla` 34 · `menorquina` 22 · `caracola` 22 · `tradicional` 10 · `regalo` 7 ·
`verano` 6 · `boda` 5 · **`madre` 0 · `concha` 0 · `bonito` 0 · `algo` 0 · `numero` 0**.

---

## 3. Medición 1 — política booleana de la rama léxica

Conteo de documentos por consulta. `A` = `tsquery` sobre el texto tecleado. `B` = grupos de
expansión de C20 combinados con distintas políticas.

### 3.1 AND estricto (lo que compone hoy `retrieval/measure.py`)

| consulta registrada | A (tecleada) | B · AND | B · zero-drop | B · OR |
|---|---:|---:|---:|---:|
| un anillo de plata para regalar | 0 | **0** | **0** | 767 |
| pendientes de oro con piedra azul | 1 | 1 | 1 | 882 |
| collar elegante para una boda | 0 | **0** | **0** | 259 |
| pendientes con motivo de caracola | 5 | 5 | 5 | 473 |
| pulsera de plata con motivos marinos | 0 | **0** | **0** | 832 |
| joya con forma de concha marina | 0 | **0** | **0** | 175 |
| algo dorado para el dia de la madre | 0 | **0** | 46 | 506 |
| anillo de filigrana tradicional menorquina | 0 | **0** | **0** | 350 |
| anillo de plata numero 3 | 0 | **0** | **0** | 763 |
| anillo de plata | 144 | 144 | 144 | 763 |

**Bajo AND estricto, 7 de las 10 consultas reales devuelven cero documentos.** Y el *zero-drop*
—descartar de la conjunción los grupos que no casan ningún documento— **rescata sólo una**: el
fallo no es «una palabra desconocida», es que la conjunción de palabras individualmente frecuentes
no casa nada (`anillo & plata & regalar` = 0 porque sólo 7 documentos mencionan `regalo` y ninguno
es un anillo de plata).

Las 12 consultas curadas del informe de C20 no vieron esto porque son todas cortas y enteramente
en vocabulario.

### 3.2 OR con ordenación por coordinación

Conjunto de candidatos = OR de los grupos; orden = `(nº de grupos que casan) DESC, ts_rank DESC`.

Propiedades verificadas:

- **Contiene el resultado del AND y lo pone en cabeza**: los documentos que casan *todos* los
  grupos tienen la coordinación máxima, así que encabezan la lista. OR+coord **domina** a AND.
- **Hace innecesario el zero-drop**: un grupo que no casa nada suma 0 a la coordinación de *todos*
  los documentos, luego no altera el orden. Es un no-op, no un caso a tratar.
- **Rescata la coincidencia discriminante**. `anillo de filigrana tradicional menorquina`:
  con `ts_rank` solo, los seis primeros son anillos genéricos (coord 1) y los *Anillo de Filigrana*
  aparecen en 7.º y 8.º; **con coordinación, los dos anillos de filigrana suben a 1.º y 2.º**.

---

## 4. Medición 2 — materiales: `&&` frente a `@>`

| cardinalidad de `materials` | documentos |
|---|---:|
| 0 | **126** (10,8 %) |
| 1 | 951 |
| 2 | 90 |
| 3 | 1 |

Los 126 sin materiales se reparten por todos los tipos: anillo 36, broche 19, pulsera 18,
collar 17, pendientes 14, colgante 11, tobillera 3, sin tipo 8.

| par de materiales | `&&` (alguno) | `@>` (todos) |
|---|---:|---:|
| plata, oro | 913 | **60** |
| plata, baño de oro | 658 | **14** |
| oro, baño de oro | 376 | **1** |

**`@>` no es una semántica alternativa: es un precipicio de recall.** El 91,6 % del catálogo tiene
un material o ninguno, así que una consulta de dos materiales bajo `@>` sólo puede alcanzar a los
91 documentos con ≥2 materiales. Y un `&&` **duro** borraría 36 anillos de toda consulta de anillo
de plata, porque no tienen materiales extraídos.

---

## 5. Medición 3 — talla y precio

- `size_label` presente en **529 de 1.168 (45 %)**. Distribución: S 122 · M 103 · L 87 · XL 83 ·
  `pequeno` 71 · mini 21 · grande 14 · XS 10 · mediano 6 · y tres numéricas sueltas (42, 9, 10).
- **`numero` casa 0 documentos**: la talla de anillo por número que el operador teclea
  («anillo de plata numero 3») **no tiene representación en el índice**. Es un hueco de
  vocabulario, no un problema de C21.
- `price`: **presente en las 1.168 filas**. Mínimo 2,50 € · mediana **230 €** · máximo 4.175 €.
  Por debajo de 80 € hay **228 documentos (20 %)**; por debajo de 150 €, 390.

---

## 6. Medición 4 — fusión RRF de tres listas, y barrido de pesos

Listas: **A** = tecleada (`websearch_to_tsquery`, orden `ts_rank`, profundidad 200) ·
**B** = expandida (OR + coordinación, profundidad 200) ·
**C** = vectorial (`<=>`, umbral 0,65, profundidad 60). Fusión `Σ w_i /(k + rank_i)`, k=60.

Rúbrica: aciertos en el top-10, contando acierto = `piece_type` correcto **y** material correcto.
Es la **misma rúbrica que C20** usó para medir la rama vectorial, así que las cifras son comparables.

| consulta | C solo | B solo | wC=1,0 | wC=0,5 | wC=0,33 | sin C |
|---|---:|---:|---:|---:|---:|---:|
| sortija de plata | 4 | 10 | 10 | 10 | 10 | 10 |
| gargantilla dorada | 6 | 10 | **5** | 5 | 5 | 10 |
| criollas de oro | **1** | **3** | 6 | 5 | 5 | 3 |
| aros de plata | 9 | 10 | 10 | 10 | 10 | 10 |
| collares de plata | 10 | 10 | 10 | 10 | 10 | 10 |
| un anillo de plata para regalar | 9 | 10 | 10 | 10 | 10 | 10 |
| collar elegante para una boda | 8 | 10 | 9 | 9 | 9 | 10 |
| anillo de filigrana tradicional menorquina | 6 | 10 | 10 | 10 | 10 | 10 |
| pendientes de oro con piedra azul | **3** | **6** | 8 | 8 | 8 | 6 |
| pulsera de plata con motivos marinos | 8 | 8 | **9** | 9 | 9 | 8 |
| bano de oro | 3 | 10 | 7 | 10 | 10 | 10 |
| dije de plata | 0 | 10 | **2** | 6 | 9 | 10 |
| **TOTAL / 120** | **67** | **107** | **96** | 102 | **105** | **107** |

Barrido completo de `k` × peso vectorial × profundidad vectorial (36 configuraciones):

| palanca | efecto |
|---|---|
| **peso de la rama vectorial** | **dominante**: 67-77/120 con `wC=1,0`; 104-106/120 con `wC=0,33` |
| `k` (5, 10, 20, 60) | marginal: ≤ 2 puntos de diferencia entre 20 y 60 |
| profundidad vectorial (10, 20, 60) | marginal: ≤ 4 puntos |

Mejor configuración fusionada: `k=20, wC=0,33` → **106/120**. La rama léxica sola: **107/120**.

### Lectura honesta de estos números

1. **`wC = 1,0` (paridad entre ramas) queda refutado.** Es la peor de las configuraciones
   fusionadas y pierde 11 puntos contra la léxica sola. La causa es estructural: la rama vectorial
   **devuelve siempre 60 candidatos aunque no entienda la consulta** (el «no abstiene» que C20 ya
   midió), así que bajo RRF vota siempre y con la misma fuerza.
2. **La rúbrica es la función objetivo de la propia rama léxica.** `doc_text` lleva líneas
   canónicas `Tipo:` y `Materiales:`, y la expansión apunta justo ahí; medir «tipo correcto y
   material correcto» premia por construcción a quien casa esas líneas. Estas cifras **fijan un
   punto de partida, no dictan un veredicto**: el juez es el golden set con relevancia graduada y
   categoría de paráfrasis de C24.
3. **La fusión gana donde la rúbrica puede verlo**: `criollas de oro` (C=1, B=3 → **6**),
   `pendientes de oro con piedra azul` (C=3, B=6 → **8**), `pulsera de plata con motivos marinos`
   (C=8, B=8 → **9**). Son los tres casos en que ninguna rama sola acierta.
4. **Y gana donde la rúbrica no puede verlo.** En `joya con forma de concha marina` la rama léxica
   entierra en B23/B24 los *Colgante Caracola Marina* y *Pendientes caracola Marina* que la
   vectorial pone en C1/C2, y la fusión los sube al top-5. La rúbrica no tiene diana para esa
   consulta, así que ese acierto no aparece en la tabla.

---

## 7. Medición 5 — SKU y nombre exacto

| consulta | lista A (tecleada) | lista B (OR+coord) | lista C (vectorial) |
|---|---|---|---|
| `SKU690` | **1 documento**: Sortija Olas de Onix (0,061) | **1 documento**, el mismo | **0 documentos** |
| `Sortija Inferno` | 1: Sortija Inferno (0,188) | 1.º de 4, coord 2 | — |
| `anillo Ses Salines plata` | los 4 Ses Salines (0,99 / 0,99 / 0,96 / 0,95) | los mismos 4, coord 4 | — |
| `pulsera Cala Galdana` | las 2 (0,92 / 0,70) | las mismas 2, coord 3 | — |
| `colgante conchiglie` | los 4 conchiglie (0,49…) | los mismos 4, coord 2 | — |
| `pendientes erizo de mar` | 4 erizo de mar (0,81…) | los mismos, coord 3 | — |

Hay **9 productos** cuyo nombre empieza por «Sortija», todos con `piece_type = anillo`.
`websearch_to_tsquery('spanish','sortija de plata')` alcanza **3** de ellos y los ordena
1.º-2.º-3.º dentro de la lista A; la lista expandida **no coloca ninguno en su top-6**, que
reproduce exactamente el hallazgo 4 de C20 y justifica que la lista A entre en la fusión.

**El caso del SKU se resuelve solo por una razón que no era obvia:** la rama vectorial
**devuelve cero candidatos** para `SKU690` (todo queda por encima del umbral 0,65), así que la
lista de un elemento no compite contra 60 vecinos ruidosos. Sin esa abstención, la aritmética RRF
daría empate exacto entre el SKU (0,5/61 + 0,5/61) y el primer vecino vectorial (1,0/61).

---

## 8. Medición 6 — los tres constructores de `tsquery`

| texto | `plainto_tsquery` | `phraseto_tsquery` | `websearch_to_tsquery` |
|---|---|---|---|
| `baño de oro` | `'bañ' & 'oro'` | `'bañ' <2> 'oro'` | `'bañ' & 'oro'` |
| `aro de dedo` | `'aro' & 'ded'` | `'aro' <2> 'ded'` | `'aro' & 'ded'` |
| `acero inoxidable` | `'acer' & 'inoxid'` | `'acer' <-> 'inoxid'` | `'acer' & 'inoxid'` |
| `collar elegante para una boda` | `'coll' & 'eleg' & 'bod'` | `'coll' <-> 'eleg' <3> 'bod'` | `'coll' & 'eleg' & 'bod'` |
| `anillo -oro` | `'anill' & 'oro'` | `'anill' <-> 'oro'` | **`'anill' & !'oro'`** |
| `"erizo de mar"` | `'eriz' & 'mar'` | `'eriz' <2> 'mar'` | **`'eriz' <2> 'mar'`** |

Documentos alcanzados:

| forma emitida | `plainto` | `phraseto` |
|---|---:|---:|
| `baño de oro` | 38 | 38 |
| `acero inoxidable` | 1 | 1 |
| **`aro de dedo`** | **6** | **0** |

**`phraseto_tsquery` destruye `aro de dedo`**, que es justo la entrada del overlay a la que el
informe de C20 atribuye +262 documentos. La pregunta «¿cuándo se decide que es multi-palabra?»
se disuelve: **`plainto` para todas las formas emitidas, siempre**.

---

## 9. Medición 7 — el umbral de 0,65 no filtra: la profundidad **es** el corte

*(Añadida el 2026-09-02 al preguntar por el efecto de dar profundidades distintas a las tres listas.)*

Tamaño **natural** de la lista vectorial, contando cuántos documentos pasan `distancia <= 0,65`:

| consulta | `d_min` | p5 | p25 | mediana | pasan 0,65 | umbral que dejaría 60 |
|---|---:|---:|---:|---:|---:|---:|
| `sortija de plata` | 0,387 | 0,447 | 0,488 | 0,521 | **1.168 / 1.168** | 0,447 |
| `gargantilla dorada` | 0,366 | 0,445 | 0,485 | 0,508 | **1.168** | 0,445 |
| `collar elegante para una boda` | 0,396 | 0,493 | 0,563 | 0,596 | **1.090** | 0,493 |
| `dije de plata` | 0,517 | 0,583 | 0,616 | 0,642 | 673 | 0,583 |
| `bano de oro` | 0,508 | 0,593 | 0,656 | 0,693 | 268 | 0,594 |
| `xyzzy quimbombo alfanumerico` | 0,700 | 0,778 | 0,814 | 0,840 | **0** | 0,778 |

**Tres lecturas, y las tres corrigen algo escrito antes.**

1. **`JPV_RETRIEVAL_DISTANCE_THRESHOLD = 0,65` está por encima de la mediana** de la distribución de distancias en las consultas ordinarias: deja pasar **el corpus entero**. Lo que corta la lista vectorial no es el umbral, es el `LIMIT`.
2. **La afirmación de C20 «el vector no abstiene nunca» necesita un matiz.** Sí abstiene — pero sólo ante **texto sin sentido**: la consulta de control da `d_min = 0,700` y **cero** documentos. Lo que no hace es discriminar entre consultas plausibles, y por eso el fallo llega a pantalla con apariencia de acierto.
3. **Un umbral que cortara de verdad tendría que ser por consulta**, no una constante: haría falta 0,445 para `gargantilla dorada` y 0,594 para `bano de oro`. Es un cuantil, no un escalar. Encaja con lo que la ficha de C25 ya pide — *«re-fijación del umbral con la distribución empírica»*— y no es trabajo de C21.

**Consecuencia de diseño:** la profundidad de la lista vectorial es un **parámetro de ranking de primera clase**, no un tope de seguridad. Y por tanto la simetría entre las tres profundidades es una decisión, no un detalle.

---

## 10. Medición 8 — profundidad: la asimetría 200 / 60 era un error

Separando peso y profundidad sobre las mismas 12 consultas y la misma rúbrica:

| profundidad A y B | profundidad C | `wC=1,0` | `wC=0,5` | `wC=0,33` |
|---:|---:|---:|---:|---:|
| **200** | **60** | 96 | 102 | **105** ← lo que decía el ticket |
| 200 | 200 | 96 | 106 | 107 |
| 200 | 400 | 96 | 106 | 108 |
| 400 | 400 | 95 | 106 | 108 |

Barrido fino con profundidad **simétrica**:

| profundidad (las tres) | `wC=0,33` | `wC=0,5` | `wC=1,0` |
|---:|---:|---:|---:|
| 20 | 108 | 94 | 76 |
| 30 | 109 | 102 | 92 |
| **40** | **113** | 107 | 97 |
| **50** | **113** | 108 | 99 |
| **60** | **111** | 107 | 102 |
| 80 | 109 | 106 | 103 |
| 100 | 107 | 107 | 100 |
| 150 | 107 | 106 | 98 |
| 200 | 107 | 106 | 96 |

**La asimetría costaba 6-8 puntos de 120.** El óptimo está en una meseta de **40-60**, y a partir de 100 la calidad decae monótonamente.

**El mecanismo, que es lo que hay que retener.** RRF con `k = 60` es **muy plano**: el documento en la posición 200 conserva `1/260` frente a `1/61` del primero — el **38 %** del voto del mejor. Una lista de 200 no amplifica su cabeza, pero **reparte voto positivo entre 140 documentos que la otra rama ni siquiera puntúa**, y ese caudal desplaza a los que dos ramas colocan bien sin colocar primero. Truncar las tres al mismo punto convierte la pertenencia a un top-N en el requisito de entrada, que es donde la prima al consenso de RRF tiene mordida.

De ahí la regla que se adopta: **`profundidad ≈ k`**. Con `k = 60` y profundidad 60, el peor documento de una lista vale la mitad que el mejor — un reparto sano —; con profundidad 200 vale el 38 % repartido sobre una lista tres veces más larga, que es lo que inunda. `k` y profundidad **no son parámetros independientes** y no deben barrerse por separado.

**Y el peso y la profundidad estaban confundidos en la medición anterior:** el `wC = 0,33` compensaba en parte la asimetría. Separados, `wC = 0,33` sigue ganando **en todas** las profundidades, así que la decisión se mantiene — pero ahora está medida limpia.

---

## 11. Medición 9 — qué grupos pueden decidir el orden: la trampa de los campos poco cubiertos

*(Añadida el 2026-09-02 al preguntar si ocasión y estilo son demasiado subjetivos para casarlos léxicamente.)*

**El problema, planteado con las cifras del §2.** La línea `Ocasiones:` existe en **150 de 1.168** documentos (13 %) y `Estilo:` en **133** (11 %). `boda` casa **5** documentos en todo el catálogo. Bajo ordenación por coordinación, casar un grupo más adelanta a un documento **por delante de todos los que casan menos**, sea cual sea su `ts_rank`. Es decir: **cinco piezas etiquetadas `boda` adelantarían a 1.163 igual de válidas para una boda pero sin etiquetar.**

Y ahí está el error de razonamiento: en un campo cubierto al 99 % —`piece_type`— **la ausencia es evidencia**: un documento sin `anillo` no es un anillo. En un campo cubierto al 13 %, la ausencia **no es evidencia de nada**: un collar de filigrana sin línea `Ocasiones:` puede ser perfecto para una boda; simplemente nadie lo etiquetó. La coincidencia léxica sobre un campo escaso fabrica **precisión falsa**.

**Regla adoptada:** un grupo cuenta para la coordinación **si y sólo si la ausencia de su término es evidencia**. Operativamente, cuenta si resolvió a un campo de cobertura alta (`piece_type` 99 %, `materials` 89 %) **o si no resolvió en absoluto** —una palabra literal que el operador tecleó, que es el caso Stripe y el que rescató los anillos de filigrana—. **No** cuenta si resolvió a un campo escaso (`occasion_tags` 13 %, `style_tags` 11 %, `color_tags` 19 %), que sigue puntuando en `ts_rank` pero ya no puede saltarse la cola.

Medido, con profundidad 60 y `wC = 0,33`:

| consulta | campos que resuelve | coord. sobre todos | sin ocasión+estilo | sin ocasión+estilo+color |
|---|---|---:|---:|---:|
| `collar elegante para una boda` | piece_type, occasion_tags | 9 | **10** | **10** |
| `pulsera de plata con motivos marinos` | piece_type, materials, style_tags | 9 | **10** | **10** |
| `pendientes de oro con piedra azul` | piece_type, materials, stone_type, color_tags | 8 | 8 | **9** |
| las otras nueve | — | sin cambio | sin cambio | sin cambio |
| **TOTAL / 120** | | **111** | **113** | **114** |

**Sin una sola pérdida en las doce.**

**Y la propiedad emergente, que es el verdadero premio.** Cuando la consulta es *mayoritariamente subjetiva* —`algo elegante para una ceremonia`— quedan pocos grupos o ninguno que cuenten, la coordinación deja de discriminar, la lista léxica degenera a `ts_rank` sobre un OR ancho —señal débil— y **la rama vectorial decide por defecto**. Es decir: **la ponderación se adapta al tipo de consulta sin un segundo peso que calibrar**, que es exactamente lo que el apunte de S10 advierte que hay que evitar (*«cada peso es un número mágico que alguien tendrá que justificar, recalibrar y depurar»*).

**Dos honestidades sobre esta medición:**

- **La rúbrica no puede juzgar lo que la pregunta plantea.** «Es un collar» es lo que se puntúa; «sirve para una boda» no. La ganancia de 111 → 113/114 mide recuperación del tipo de pieza, no adecuación a la ocasión. El juez real es una **categoría subjetiva en el golden set de C24**, que hoy no existe.
- **En `collar elegante para una boda` la patología no llega a dispararse**, porque ninguno de los 5 documentos etiquetados `boda` es un collar: la coordinación de 2 viene de `collar` + `elegante`. El mecanismo es real y el argumento a priori es sólido, pero en esta consulta concreta la ganancia viene de reordenaciones más abajo en la lista, no del salto que se describe. Se declara así en lugar de presentarlo como demostrado.

---

## 12. Qué queda pendiente de medir

- Relevancia **graduada** y **categoría subjetiva** (ocasión, estilo, «para regalar») en el golden set: es C24, y es el juez real de la §6 y de la §11.
- **Re-fijación del umbral de distancia con la distribución empírica** —por cuantil y no por constante—, que la ficha de C25 ya reclama y la §9 acaba de justificar con números.
- Latencia real de la rama léxica dentro del orquestador (aquí se midió corrección, no tiempo).
- Efecto del singleton del cliente de embeddings sobre el p95, en frío y en caliente.
- Si `stone_type` (54 % de cobertura) debe contar para la coordinación o no: está en la frontera entre el bloque alto (89-99 %) y el escaso (11-19 %), y ninguna de las doce consultas lo aísla.
