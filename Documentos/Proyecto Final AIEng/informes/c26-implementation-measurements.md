# C26 — mediciones de implementación: sustitutos sobre el embedding almacenado

**Change:** [`add-substitutes-retrieval`](../../../openspec/changes/add-substitutes-retrieval/) · **Fecha:** 2026-09-12
**Rama:** `c26-add-substitutes-retrieval` · **Punto de nacimiento:** `b6fe67c`
**Exploración previa:** [c26-exploration-measurements.md](c26-exploration-measurements.md)
**Rebanada publicada:** [`ai-service/evals/results/c26-substitutes-slice.md`](../../../ai-service/evals/results/c26-substitutes-slice.md)

---

## 0. Procedencia y puerta de entrada

| | |
|---|---|
| C22 (`add-pos-projection-soft-prefilter`) | **archivado** 2026-09-05 |
| C25 (`recalibrate-ranking-and-abstention`) | **archivado** 2026-09-12 |
| `index_set_hash` | `051a6b06021efc3fb18891ffc7acfa2c6e3499f161aa81e9e96dd061233e073b` |
| Golden set antes / después | `1:198c4af44506` → `1:89c178e55603` |
| `ai.product_document` vivos / con embedding | **1.168 / 1.168 (100 %)** |
| Suite ai-service **antes** | **997 passed, 0 failed** |
| Suite ai-service **después** | **1038 passed, 0 failed** (+41) |

La huella del conjunto indexado coincide **carácter por carácter** con la que registran
[`c24-baselines-2026-09-07.md`](../../../ai-service/evals/results/c24-baselines-2026-09-07.md) y
[`c25-baselines-2026-09-11.md`](../../../ai-service/evals/results/c25-baselines-2026-09-11.md)
(`051a6b06021efc3f…`), así que la rebanada se midió contra el mismo corpus que la tabla publicada.

> **Corrección de una cifra de la exploración.** El informe de exploración cita la huella del
> corpus como `e46249874fbc6ff2140e8c00ad19874e` — 32 caracteres. **No es el `index_set_hash`**,
> que tiene 64 y es el que la procedencia compara; era un resumen ad hoc tomado durante la
> exploración. No contradice nada: el corpus es el mismo. Se deja anotado porque una huella de
> otra longitud en un informe invita a concluir que el corpus se movió.

**Sobre la línea base de la suite.** `CLAUDE.md` advierte de suites que llegan en rojo antes de
tocar nada, y es cierto de `dotnet test` y de `npm run test`. **No lo es de `ai-service`**: la
medición previa al change da 997 passed y **0 failed**. La comparación por nombres exigida por el
procedimiento es por tanto trivial en ambos sentidos — el conjunto de tests en rojo es vacío
antes y después —, y el criterio real es que no aparezca ninguno.

---

## 1. El barrido de `w_size`: el recorrido completo, no sólo el ganador

Once puntos de rejilla sobre las cinco consultas ancladas. La tabla íntegra, con su procedencia,
está en la rebanada publicada; aquí va con la lectura.

| `w_size` | nDCG@5 | nDCG@5 **binario** | Recall@5 | P@3 |
|---:|---:|---:|---:|---:|
| `0` *(rollback)* | 0,7414 | 1,0000 | 0,4241 | 1,0000 |
| `0,02` | 0,7529 | 1,0000 | 0,4241 | 1,0000 |
| `0,04` | 0,8199 | 1,0000 | 0,4241 | 1,0000 |
| **`0,05`** ← adoptado | **0,8453** | **1,0000** | **0,4241** | **1,0000** |
| `0,06` | 0,8504 | 1,0000 | 0,4241 | 1,0000 |
| `0,07` | 0,8713 | 0,9738 | 0,4135 | 1,0000 |
| `0,075` ← máx. graduado | **0,8785** | 0,9738 | 0,4135 | 1,0000 |
| `0,08` | 0,8785 | 0,9738 | 0,4135 | 1,0000 |
| `0,1` | 0,8667 | 0,9398 | 0,4035 | 0,9333 |
| `0,12` | 0,8667 | 0,9398 | 0,4035 | 0,9333 |
| `0,2` | 0,7982 | 0,8179 | 0,2535 | 0,8000 |

**El término hace algo, y eso es lo primero que el barrido establece.** De `0` a `0,05` el
nDCG@5 graduado sube **+0,1039**. La conclusión de C25 —*«el valor del peso no cambia el orden,
sólo su signo»*— **no se traslada**, exactamente como la exploración advirtió: allí el score
tomaba dos valores; aquí un término binario se mezcla con una similitud continua y el peso fija
un tipo de cambio real.

**Las dos lecturas discrepan, y `criterion.md` dice que eso se publica como hallazgo.**

- El **graduado** premia `0,075` (0,8785).
- El **binario**, `Recall@5` y `P@3` se mantienen en su máximo **hasta `0,06` inclusive** y se
  rompen a partir de `0,07`.

Lo que ocurre en `0,07` es concreto y se puede nombrar: entra **`SKU334 Anillo plata M`** en el
top-5 de `q49`. Es un anillo liso, talla correcta y **nada más** — el caso que `criterion.md`
nombra explícitamente como grado 0 (*«un anillo cualquiera … es 0»*). El peso ha dejado de
comprar relevancia y ha empezado a comprar la métrica.

**La decisión.** C25 sentó el precedente: optimizar la métrica de cabecera **con la relevancia
pura como guardarraíl**. Bajo esa regla el mejor punto que no degrada el guardarraíl es `0,06`.
Y `0,06` supera a `0,05` en **0,0051 de nDCG@5**, con todas las demás métricas idénticas, por un
único intercambio de posiciones en **una** consulta. Eso está por debajo del ruido, así que se
aplica la regla declarada en la pregunta abierta 1 de la ficha —*«si la diferencia queda bajo el
ruido, `0,05`»*— y **`w_size = 0,05` queda adoptado**.

Coincide con el valor que el diseño proponía, pero **no por el motivo que el diseño daba**. El
diseño lo justificaba por *interleave*; lo que lo sostiene tras medir es que es el mayor peso
que no mete ningún documento de grado 0 en ningún top-5, empatado con `0,06` dentro del ruido.

### Lo que el barrido no puede decidir

**Sólo dos de las cinco consultas se mueven.** `q51`, `q52` y `q72` dan la misma cifra en los
once puntos: `q51` y `q72` tienen origen **sin talla** —el término es inerte por diseño— y en
`q52` los cuatro documentos relevantes son los cuatro lapislázuli, que el coseno ya ordena. La
base efectiva del barrido es **n = 2**. Es una limitación real y no se corrige aquí: cubrirla
pide consultas de sustituto con origen con talla y familia ajena, que es ampliar el golden set.

---

## 2. El bloque entero, medido sobre el catálogo real

El riesgo principal que la ficha nombró. Reordenando los **diez vecinos reales** de `SKU13`
(distancias del índice vivo, filtro por `piece_type` ya aplicado) bajo las dos formas:

```
  continuo (w=0,05):  SKU14, SKU12, SKU50, SKU85, SKU15, SKU334, SKU04, ...
  bloque entero:      SKU50, SKU85, SKU334, SKU14, SKU12, SKU15, SKU04, ...
                      └── las tres tallas M primero, POR CONSTRUCCIÓN
```

| | continuo | bloque |
|---|---|---|
| Hermano más cercano `SKU14` (talla L, dist. 0,0868) | **puesto 1** | puesto **4** |
| Hermano más lejano `SKU15` (talla XL) | puesto 5 — **dentro de la ventana** | puesto **6** — fuera |
| ¿Algún candidato de talla correcta por debajo del hermano? | **sí** | **no** |

El bloque manda a `SKU14` detrás de `SKU334 Anillo plata M` (distancia 0,1854, **más del doble**
de lejos) por el único mérito de coincidir en talla. Eso es el destierro que C25 midió con la
rotación. `test_different_size_sibling_stays_inside_the_visible_window` falla **las dos**
aserciones bajo el bloque y pasa las dos bajo el término continuo; se verificó reordenando la
misma fixture con las dos claves antes de darlo por bueno.

---

## 3. El etiquetado: qué se aplicó y qué sesgo queda

`criterion.md` **no se modificó** — la tarea lo pedía y su grado 1 ya estaba redactado en
términos de sustituto. Lo que hubo que registrar es **cómo se proyecta su escala sobre una
consulta cuyo sujeto es una pieza que ya no está**:

- La **talla** que la consulta nombra (o, si no nombra ninguna, el **material** o la **piedra**)
  es un requisito **del cliente**: un anillo que no entra no se vende hoy, represente lo que
  represente. `criterion.md` ya nombra la talla como el degradador canónico a grado 1.
- El **motivo** describe la pieza **que falta**. Un sustituto es por definición otra pieza, así
  que compartir el motivo no es lo que lo hace la respuesta: es lo que lo hace *«la segunda
  opción»* del propio ejemplo de `criterion.md` (*«pendientes de erizo de mar → el colgante de
  erizo de la misma colección es 1, no 2»*).

| grado | regla aplicada |
|---|---|
| **2** | cumple el requisito del cliente **y** pertenece al registro marino del catálogo |
| **1** | falla exactamente uno: mismo motivo en otra talla, o pieza marina con talla **no declarada** (no se puede afirmar que entre) |
| **0** | falla los dos, o es *«mismo tipo de pieza y nada más»* |

Las tallas se comparan **dentro de un mismo vocabulario**. El catálogo usa dos —`XS/S/M/L/XL` y
`mini/pequeño/mediano/grande`— y equipararlos sería inventar una conversión que el feed no
publica, así que una comparación cruzada cuenta como **no declarada** y nunca como coincidencia.

**Resultado:** 126 juicios nuevos sobre 5 consultas, profundidad de *pool* 20 sobre la unión de
las once configuraciones del barrido.

| consulta | origen | n | grado 2 | grado 1 | grado 0 |
|---|---|---:|---:|---:|---:|
| `q49` | `SKU13` Anillo erizo de mar M | 26 | 3 | 16 | 7 |
| `q50` | `SKU77` Colgante estrella de mar S | 27 | 7 | 13 | 7 |
| `q51` | `SKU106` Pulsera hilo caracola | 20 | 11 | 9 | 0 |
| `q52` | `SKU159` Anillo lapislázuli mediano | 33 | 1 | 3 | 29 |
| `q72` | `SKU102` Anillo caracola *(sin familia, sin talla)* | 20 | 8 | 6 | 6 |

**`q51` discrimina poco y hay que decirlo:** su *pool* son veinte pulseras de hilo y ninguna cae
en grado 0, así que da 0,7600 en los once puntos. Contribuye cobertura, no capacidad de arbitrar.

### El sesgo que queda, declarado

**El etiquetado lo hizo el mismo agente que diseñó el orden.** La tabla de riesgos del diseño ya
lo declaraba como real y no mitigado, y aquí no se mitiga: se acota.

1. La rúbrica de la que se deriva se escribió el **2026-09-07**, antes de que este change
   existiera, y ya nombraba la talla como degradador. La alineación entre el orden y las
   etiquetas es con una rúbrica **preexistente**, no con una escrita para el orden.
2. El etiquetado se aplicó sobre los **atributos** de cada documento leídos del índice —tipo,
   talla, materiales, motivo, origen— y **nunca sobre su posición** en ninguna lista ordenada.
   La regla es una función de `(atributos de la consulta, atributos del documento)` y está
   escrita en código, así que es reproducible y auditable.
3. Aun así: quien escribe la regla y quien escribe el orden son el mismo, y ninguna de las dos
   cosas anteriores lo elimina. **El número que más depende de esto es `w_size`.**

Se registra junto a la ausencia de acuerdo entre anotadores que el README ya declara para el
golden set entero.

---

## 4. Lo que se comprobó del perímetro

| Comprobación | Resultado |
|---|---|
| `openspec validate --all --strict` | **55 passed, 0 failed** |
| `test_openapi_snapshot_is_stable` | verde · `ai-service/openapi.json` **sin diff** contra `b6fe67c` |
| Migraciones Alembic / EF Core | **ninguna** |
| Diff en `backend/`, `frontend/`, `terraform/`, `.github/workflows/` | **vacío** contra `b6fe67c` |
| `evals/results/` y `evals/configs/` publicados | **sin diff** — ni una cifra, ni una configuración |
| `judgements.jsonl` | **126 añadidos, 0 borrados**; los 3.926 previos byte a byte idénticos |
| `queries.jsonl` | sólo `q49`–`q52` y la nueva `q72` |
| Pesos calibrados por C25 | sin tocar; `settings.py` es **50 líneas añadidas, 0 borradas** |

---

## 5. Dos cosas que la implementación descubrió y las tareas no preveían

### 5.1 El *docstring* de una ruta es contrato

`test_openapi_snapshot_is_stable` se puso **en rojo** al documentar el handler nuevo. FastAPI
publica el *docstring* de un handler como `description` de la operación, y esta operación **no
tenía ninguna** en el snapshot congelado: se escribió cuando era un stub de dos líneas. La
explicación pasó a un comentario sobre el decorador. `retrieve_products`, en cambio, conserva su
*docstring* porque el snapshot ya lo lleva.

Es la puerta funcionando: nada se regeneró, se corrigió el código.

### 5.2 `price_band` **es** una cifra de precio, y se estaba emitiendo

La tarea 4.5 pide comprobar que `match_reasons` no transporta ninguna cifra de precio ni de
stock. La primera versión emitía `otra banda de precio (30-80)`, razonando que una banda es una
etiqueta y no una cifra. **Contra el catálogo vivo eso es falso:** los cinco valores de
`price_band` son `lt-30`, `30-80`, `80-150`, `150-300` y `gte-300` — rangos en euros, es decir
cifras de precio, justo lo que `api/schemas/common.py` prohíbe por escrito (*«No model here
carries a price or stock figure»*). La razón pasa a declarar **sólo que difieren**: `otra banda
de precio`, sin valor.

**Lo que lo destapó, y por qué el test no.** El test de 4.5 afirmaba «ninguna razón contiene un
dígito», y pasaba — porque su *fixture* usaba tallas con letras. Sobre el catálogo real esa
aserción es a la vez **demasiado débil y demasiado fuerte**: no veía `30-80` porque el *fixture*
no lo tenía, y habría rechazado `misma talla (17)`, que es legítima, porque las tallas reales
llevan dígitos (`05`, `6`, `17`, `45`, `2mm`). El test se reapuntó a lo que de verdad no puede
viajar —valores de banda y buckets de proyección— con un *fixture* de las formas reales.

Se encontró con una comprobación de humo contra el índice vivo, que es la única del trabajo que
no usa el doble: **todo lo demás corre contra `FakeProductSearch`**, y un doble no puede
contradecir una suposición sobre cómo son los datos, porque la suposición está también en el
doble.

### 5.3 El denominador de la tabla publicada se movía solo — y hubo que impedirlo en código

**Tarea 6.7 pedía *verificar* que la tabla de ablations no cambia. Verificarlo no bastaba.** Los
ficheros publicados son estáticos y por supuesto no cambian, pero `runner.py` y `sweep.py`
iteraban `golden.judged_queries`, que pasó de **63 a 68** al etiquetar las cinco consultas de
sustituto. Una re-ejecución de la tabla de C24/C25 habría absorbido cinco consultas que
`v0-fts` y `v0-nombre` **no pueden ejecutar** y habría publicado cifras distintas sin que ninguna
configuración hubiera cambiado. Justo lo que D8 prohíbe.

Se añadió `GoldenSet.retrieval_queries` —las consultas juzgadas **del recuperador de productos**,
excluyendo `sustituto`— y el *runner*, el barrido y la medición CAG pasan a medir esa. La
separación queda **en código y no en una convención que el siguiente runner tenga que recordar**:
antes de C26 los dos conjuntos coincidían, así que el alcance era correcto por accidente, y un
accidente no es una garantía. `test_the_published_ablation_denominator_is_the_one_c25_measured`
lo fija en 63 con un literal, a propósito: derivarlo del fichero que protege no afirmaría nada.

---

## 6. Desviaciones respecto de `tasks.md`

| Tarea | Qué se hizo |
|---|---|
| 6.7 | **Ampliada de verificación a corrección** — ver §5.2. Verificar no bastaba |
| 3.5 / spec «declare la edad de la proyección» | `SubstitutesResponse` **no tiene** `projection_age_seconds` y el contrato está congelado (`RetrievalResponse` sí lo tiene). La edad viaja en `debug.notes` de cada resultado, que **sí** está en el contrato congelado. Es la válvula que D5 ya designa para lo que el contrato no expresa |
| 2.4 «una sola conexión por petición» | Se verificó lo comprobable: la sentencia abre **una** sesión, no lee el esquema `public`, y el planificador resuelve el embedding origen en **un solo `InitPlan`**. La petición completa abre varias sesiones **secuenciales** (`source_document`, `resolve_scope`, `neighbours_of`), que es el patrón que `retrieve_products` ya sigue: el límite del pool es de conexiones **simultáneas** y nunca hay más de una |
| 4.4 | Además de los cuatro motivos que la tarea enumera, `match_reasons` declara **que la banda de precio difiere** —sin nombrar la banda, ver §5.2—, que es la decisión aplicada de la pregunta abierta 2 de la ficha. Sin ella `price_band` —que la tarea 2.1 manda leer— no tendría lector |
| — (añadido) | `material_overlap` entra como **desempate estricto**, detrás de la clave compuesta. Lo pide el escenario *«Material overlap breaks a tie»* de la spec, que el diseño no recoge en su fórmula. Va como desempate y no como cuarto término porque fijar cuánta similitud vale un material compartido es un peso que **ninguna consulta del golden set puede calibrar** — el mismo motivo por el que la banda de precio se quedó fuera del orden |

---

## 7. Una observación que no se actúa

`w_availability` se reutiliza de C25 tal como la ficha pide, con su valor por defecto **1,0**.
En la clave lexicográfica de C25 ese valor era irrelevante —sólo importaba el signo—, pero
**aquí no**: la similitud vive en `[0, 1]`, así que un peso de 1,0 hace que el término de
disponibilidad domine a la similitud entera y **particione** en la práctica, agotados detrás de
disponibles siempre.

No se cambia, por tres razones: la spec exige reutilizar `business_score` tal cual; el
comportamiento resultante es defendible en mostrador —una pieza que no está no se vende— y sigue
sin **eliminar** nada, que es el invariante; y el golden set está etiquetado **sin alcance de
punto de venta**, así que la rebanada no puede calibrar ese peso. Se anota para que quien
implemente **C34** sepa que el término está en ese régimen y no lo descubra midiendo.

> **Cerrado en la spec, no sólo anotado aquí** *(2026-09-12, tras `/opsx:verify`)*. La
> verificación leyó el título del requisito —*«never partitions on a boolean»*— contra este
> párrafo y encontró que la spec viva iba a afirmar lo contrario de lo que el código hace. El
> requisito pasa a llamarse *«no integer block enters the key»* y lleva el recorte explícito:
> el término de disponibilidad **particiona de hecho y se acepta**, por ser continuo en la
> forma, restar sólo, no eliminar nada, y no tener en el golden set —etiquetado sin alcance de
> punto de venta— ningún dato con el que calibrar su peso. Lo que la prohibición veta es un
> **bloque entero** en la clave, y ese sitio es el de la talla.
