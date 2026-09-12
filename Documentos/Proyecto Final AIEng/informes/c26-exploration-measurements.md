# C26 — mediciones de exploración: sustitutos, y por qué la familia no va primero

**Change:** [`add-substitutes-retrieval`](../../../openspec/changes/archive/2026-09-12-add-substitutes-retrieval/) · **Fecha:** 2026-09-12
**Árbol explorado:** `ai-eng` en `d825a8d` · **Rama de implementación:** `c26-add-substitutes-retrieval`
**Corpus:** Postgres local `:5433/joiabagur_pv` · 1.168 documentos vivos · huella `e46249874fbc6ff2140e8c00ad19874e`

Seis mediciones tomadas antes de escribir una línea del change. **Tres puntos de la ficha del plan
resultan falsos del árbol**, y el más caro invierte el orden que la ficha pedía.

---

## 1. Lo que ya está puesto: el change es más barato de lo que su ficha sugiere

| Pieza que necesita | Estado medido |
|---|---|
| `POST /v1/retrieval/substitutes` | **En `openapi.json` congelado**, hoy **501** vía `require_stub_mode` |
| Embedding por producto | **1.168 de 1.168** · índice HNSW `vector_cosine_ops` (m=16, ef_construction=128) |
| `family_id` | 491 (42,0 %) · **156 familias** · tamaños 2 (44), 3 (52), 4 (56), 5 (3), 8 (1) |
| `materials` | 1.046 (89,6 %) · índice GIN |
| `price_band` | 1.168 (100 %) |
| Disponibilidad por POS | `ai.pos_projection`, **6.720 filas** (C22) |

**El punto que cambia el coste:** sustituto es **producto→producto**, y el embedding de origen ya
está almacenado. **Cero llamadas al proveedor en tiempo de consulta**, sin rama léxica, sin
expansión y sin fusión: una sentencia SQL. Es la capacidad más barata que queda viva en el plan.

---

## 2. El orden que la ficha pide lidera con los candidatos invendibles

Vecinos por coseno de los cuatro productos origen de las consultas reservadas, con el tipo de pieza
y la talla anotados. Sin ninguna regla aplicada.

| origen | # | candidato | dist | familia | mismo tipo | misma talla |
|---|---:|---|---:|:---:|:---:|:---:|
| **SKU13** `Anillo erizo de mar M` | 1 | Anillo erizo de mar **L** | 0,0868 | ✅ | ✅ | ❌ |
| | 2 | Anillo erizo de mar **S** | 0,0908 | ✅ | ✅ | ❌ |
| | 3 | Anillo Erizo de mar **XL** | 0,1229 | ✅ | ✅ | ❌ |
| | 4 | **Colgante** erizo de mar M | 0,1306 | ❌ | **❌** | ✅ |
| | 5 | Anillo Erizo oro **S** | 0,1375 | ❌ | ✅ | ❌ |
| | **6** | **Anillo oreja de mar M** | 0,1535 | ❌ | ✅ | ✅ |
| **SKU77** `Colgante estrella de mar S` | 1-3 | estrella de mar **L / M / XS** | 0,063–0,091 | ✅ | ✅ | ❌ |
| | **4** | **Colgante oreja de mar S** | 0,0940 | ❌ | ✅ | ✅ |
| | 5 | **Anillo** estrella de mar S | 0,1005 | ❌ | **❌** | ✅ |
| | **6** | **Colgante estrella de mar S oro** | 0,1124 | ✅ | ✅ | ✅ |
| **SKU159** `Anillo lapislázuli mediano` | **1** | **lapislázuli mediano oro** | 0,0473 | ✅ | ✅ | ✅ |
| | 2-4 | lapislázuli **grande / pequeño** | 0,085–0,092 | ✅/❌ | ✅ | ❌ |
| **SKU106** `Pulsera hilo caracola` *(sin talla)* | 1 | hilo caracola **oro** | 0,0734 | ✅ | ✅ | — |
| | 2 | **plata** caracola | 0,0878 | ✅ | ✅ | — |

**Tres lecturas, y las tres apuntan igual.**

1. **Para `SKU13` el top-5 del vector puro no contiene un solo sustituto usable.** Los tres primeros
   son el mismo anillo en otra talla. Un anillo que no entra no es una segunda opción: es
   invendible. El primer candidato real es el **#6**.
2. **La familia es, por construcción, el conjunto de piezas que se diferencian justo en el atributo
   que descalifica.** Por eso *«misma familia primero»* no está matizada de más: está **invertida**.
3. **Pero no se puede excluir la familia.** El mejor sustituto de `SKU159` es su hermano `mediano
   oro` — **misma talla, otro material** — y es el **#1**. Ése es el patrón ideal de sustituto.

> **La pertenencia a familia es ortogonal. El discriminante es la talla**, y cruza la frontera de la
> familia en las dos direcciones.

**Y el vector viola el tipo de pieza** en 2 de los 4 casos (#4 de `SKU13` es un colgante; #5 de
`SKU77` es un anillo), lo que obliga a un filtro duro por `piece_type`.

### La rúbrica de anotación ya decía lo mismo

[`criterion.md`](../../../ai-service/evals/golden/criterion.md) define el grado **1** como *«falla UN
atributo que la consulta nombró explícitamente (**talla**, uno de varios materiales, color,
piedra)»*. **Una talla distinta ya estaba clasificada como segunda opción, no como respuesta.** El
criterio de etiquetado del proyecto coincide con la medición y discrepa de la ficha.

### La familia de `SKU77` está contaminada y partida

`Colgante estrella de mar` tiene 8 miembros, **uno de ellos el sintético `SKU610`** — el caso que el
informe de C18b ya nombró (*«la que se comió un sintético»*) —, mientras las variantes «dorado»
viven en una **segunda familia de 2** y `SKU91 XS dorado` es huérfano. Con partición dura por
familia, `SKU610` subiría al bloque de cabeza; **el vector lo entierra fuera del top-12**, y
recupera al huérfano `SKU92` en el puesto 8. Se deja como está, a propósito, para observar el
comportamiento: corregir familias es de C28.

---

## 3. El peso de la degradación por talla, simulado

`sim = 1 − distancia coseno`, con el filtro duro por `piece_type` ya aplicado.

| origen | `w = 0` | `w = 0,02` | **`w = 0,05`** | `w = 0,08` |
|---|---|---|---|---|
| **SKU13** anillo M | L, S, XL, oro S, **oreja M**⁵, **estrella M**⁶ | apenas mueve: **oreja M**⁴ | L, S, **oreja M**³, **estrella M**⁴, XL⁵, **plata M**⁶ | **oreja M**¹, **estrella M**², L³, S⁴ |
| **SKU77** colgante S | L, M, XS, **oreja S**⁴, **S oro**⁵ | L, **oreja S**², M³ | **oreja S**¹, **S oro**², L³, **mejillón S**⁴, **S dorado**⁵, M⁶ | **oreja S**¹, **S oro**², …, M⁸, XS¹⁰ |
| **SKU159** anillo mediano | **mediano oro**¹ | sin cambios | sin cambios | sin cambios |
| **SKU102** anillo sin talla | — | casi sin cambios | casi sin cambios | casi sin cambios |

- **`0,02`** es inerte en la práctica: `oreja M` sube del #5 al #4.
- **`0,08`** manda la `M` de `SKU77` al puesto **8** y la `XS` al **10**. Eso ya es «a la cola».
- **`0,05` interleava**: los candidatos de talla correcta entran en el top-4 y **el hermano de otra
  talla sigue visible dentro del top-5**.

**Valor propuesto: `w_size = 0,05`**, configurado y **barrido** contra las cinco consultas antes de
adoptarse. La casa no fija pesos por argumento.

### Una guarda que la simulación destapó

En `SKU102` (sin talla) la simulación degrada a `Anillo Pie Caracola mini` porque `'mini' IS
DISTINCT FROM NULL`. **Si el origen no declara talla, no hay desajuste que observar**: penalizar a
un candidato por *tener* talla es tratar la ausencia como valor, la regla que `ports.py` ya prohíbe
por escrito para las señales de negocio.

No es cosmético. Cobertura de `size_label` por tipo de pieza:

| tipo | productos | con talla |
|---|---:|---:|
| pendientes | 275 | 139 — 51 % |
| **anillo** | 268 | **123 — 46 %** |
| pulsera | 207 | 87 — 42 % |
| colgante | 160 | 84 — 53 % |
| collar | 138 | 59 — 43 % |

**El 54 % de los anillos no tiene `size_label`.** Sin la guarda, media población del tipo más
afectado se ordenaría por un desajuste inexistente.

### Y una advertencia sobre un hallazgo de C25 que NO se traslada

C25 concluyó que *«el valor del peso no cambia el orden, solo su signo»*. Era cierto **allí**:
`business_score` era un único término binario y todo lo demás eran bloques enteros, así que el score
tomaba dos valores. **Aquí la cola mezcla similitud continua con un término binario**, de modo que
el peso fija un tipo de cambio real —cuánta similitud vale una talla equivocada— y sí mueve el
orden. La tabla de arriba lo demuestra con tres valores y tres órdenes distintos.

---

## 4. Las señales: una sirve y la otra no tiene dato

Contando cuántos productos tienen **algún candidato del mismo `piece_type` con el que compartir
etiqueta**:

| `data_origin` | productos | por **material** | por **estilo** |
|---|---:|---:|---:|
| **`real`** | 404 | **395 — 97,8 %** | **1 — 0,2 %** |
| `synthetic` | 764 | 646 — 84,6 % | 122 — 16,0 % |

Cobertura bruta de las etiquetas en el catálogo: `color_tags` **226 (19,4 %)**, `style_tags` **131
(11,2 %)**, ambas **61 (5,2 %)**, **ninguna 872 (74,7 %)**.

`material_overlap` es una señal sólida. **`style_similarity` como Jaccard de `style_tags` sería 0,0
para 403 de 404 productos reales, por construcción** — y el contrato lo declara **requerido y no
nulable**, mientras que `visual_similarity` sí es nulable.

**Decisión:** se emite el Jaccard y **la ausencia se declara en `match_reasons`**. Derivarlo del
embedding lo convertiría en una copia de `score` — una señal que no explica nada nuevo, y la segunda
definición que diverge, que es el error por el que se anuló C19.

**`match_reasons` es además la vía para la talla**, que `SimilaritySignals` no puede expresar y que
discrimina en 2 de las 4 consultas reservadas.

---

## 5. No hay abstención posible, y está medido

Distancia al vecino más próximo, muestra de 300 documentos:

| | n | mín | p25 | mediana | p95 | **máx** |
|---|---:|---:|---:|---:|---:|---:|
| **con** familia | 120 | 0,0168 | 0,0337 | **0,0491** | 0,0995 | 0,1227 |
| **sin** familia | 180 | 0,0275 | 0,0914 | **0,1209** | 0,2248 | **0,2545** |

**Todo producto del catálogo tiene algún vecino a menos de 0,255**, y el rango de «sin familia»
**contiene** el de «con familia». Es la misma firma de contención que C25 encontró al intentar
re-fijar su umbral escalar (*«el rango de las imposibles cae dentro del de las contestables»*).

En un catálogo de 1.168 piezas de joyería marina menorquina, **todo se parece a algo**. Un umbral
absoluto o acepta todo o empieza a rechazar casos buenos.

**Decisión:** el endpoint **no abstiene**, `low_confidence` se emite falso, y se declara con esta
distribución detrás — por decisión medida y no por aplazamiento, el precedente exacto de C25.

---

## 6. Cómo se mide, y por qué en rebanada aparte

El golden set tiene **71 consultas, 63 juzgadas** y **8 declaradas sin juicios**: **4 de sustituto**
(`q49`–`q52`, con la nota escrita *«responde 501 y no existe configuración que la recupere, así que
etiquetarla produciría juicios sesgados. La hereda C26»*) y 4 ambiguas, reservadas a C31.

**El problema:** las consultas son **texto** y el endpoint recibe **`product_id`**. Y el arnés llama
a `retrieve_products` **en proceso**, no por HTTP.

| Opción | Veredicto |
|---|---|
| Resolver el texto con el buscador y encadenar | **No.** Mediría la cadena, que es de C32, e imputaría a C26 el fallo del primer paso |
| Anclar cada consulta con `source_product_id` explícito | **Sí.** Aísla la calidad del sustituto y es barato |
| Integrar en la tabla de ablations publicada | **No.** Movería su denominador, y `v0-fts`/`v1-vectorial` ni siquiera pueden ejecutar este endpoint |

**Los cuatro orígenes resueltos:** `SKU13` (familia de 4), `SKU77` (familia de 8, contaminada),
`SKU106` (familia de 3, discrimina por material), `SKU159` (familia de 4, mezcla talla y material).

**Los cuatro tienen familia**, así que el camino sin familia —**el 58 % del catálogo**— no lo cubre
ninguna consulta reservada. **Entra una quinta**, anclada en `SKU102 Anillo caracola` (real,
huérfano).

---

## 7. Dos correcciones de código que la exploración deja pedidas

1. **`fusion.py` predice un consumidor que no existirá.** Su docstring dice *«C26 (substitutes) is
   the next caller»*. Con **una sola lista** no hay nada que fusionar. Se corrige el comentario para
   que no quede una predicción falsa en el código.
2. **`demotion_rank` no se reutiliza.** Su segundo componente es `int(_size_mismatch(...))`, un
   **bloque entero**, y un bloque entero manda a la cola por construcción — exactamente lo que C25
   midió con la rotación (11.067 pares invertidos, el 71,2 % a más de diez puestos). C26 reutiliza
   `business_score` y `OUT_OF_STOCK_BUCKET`, pero compone su propia clave con la talla **continua**.

---

## 8. Las tres refutaciones de la ficha, en una tabla

| Lo que decía la ficha | Lo que la medición obliga | Motivo |
|---|---|---|
| «**Misma familia primero**, luego similitud» | Familia **en el conjunto, sin prioridad**; el orden lo decide similitud + talla + disponibilidad | Lidera con los invendibles en 3 de 4 casos y expulsa a `SKU39`, mejor sustituto que media familia |
| `test_same_family_variant_ranks_first_when_available` | `test_no_live_family_member_is_dropped_from_the_result` | Lo sostenible es la garantía de recall, no un orden que la medición desmiente |
| `test_excludes_out_of_stock_when_flag_enabled` | **Retirado**; lo cubre `Substitutes_ExcludeProductsWithoutStockAtTargetPos` de C34 | La exclusión estaba especificada **dos veces**, y la de .NET respeta la frontera del §6.2 y el invariante del §15.10 |
| **Zona:** `retrieval/` | `retrieval/` **+ `evals/` + `evals/golden/`** | **Decimocuarta vez** que la zona de una ficha se queda corta |
| *(nada sobre la talla)* | Término continuo, suave, inerte sin dato en ambos lados | La talla discrimina en 2 de las 4 consultas y el contrato congelado no la expresa: va en `match_reasons` |
| *(nada sobre abstención)* | **No abstiene**, declarado con la distribución | Todo producto tiene vecino a < 0,255 |
