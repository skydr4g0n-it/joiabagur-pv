# C27 — mediciones que disparan el corte nº 1: complementarios sale del alcance

**Change afectado:** C27 `add-complementary-recommendations` · **Fecha:** 2026-09-12
**Árbol medido:** `ai-eng` en `d825a8d` · **Corpus:** Postgres local `:5433/joiabagur_pv`
**Huella del índice:** `e46249874fbc6ff2140e8c00ad19874e` · 1.168 documentos vivos

El §6 del plan llevaba a C27 marcado como **corte nº 1 pre-autorizado** desde el 31 de agosto, con
un disparador redactado en términos de juicio: *«si el núcleo peligra»*. Este informe lo sustituye
por un disparador de **medición**. Las cinco comprobaciones de abajo se hicieron antes de escribir
una línea del change, y las cinco salen en contra.

La distinción importa porque cambia lo que el README puede afirmar. Un corte por plazo es una
concesión; un corte medido es una decisión técnica justificada, que es lo que el rubro del PFM
premia por escrito. **C27 no se recorta por falta de sesión: se retira porque sus dos señales
están vacías y su propio proyecto nunca previó medirlo.**

---

## 1. El generador no tiene modelo de afinidad — tiene lo contrario

La ficha de C27 pide *«señal adicional de co-ocurrencia desde `ai.co_occurrence`»*, y el diseño la
llama *«co-venta histórica»*. La co-ocurrencia se deriva del `BulkOperationId` de las ventas, y
**todas las ventas del sistema las escribe el simulador de C10**. Así las agrupa
[`simulate.py:313-343`](../../../ai-service/src/jbg_ai/data/world/simulate.py):

```python
remaining = list(lines)
rng.shuffle(remaining)                     # (1) barajado aleatorio
...
while len(picked) < size and remaining:
    target_stems = {name_stem(sku_by_code[item[0]].name) for item in picked}
    target_cols  = {sku_by_code[item[0]].collection_name for item in picked}
    distinct = next(
        (index for index, item in enumerate(remaining)
         if name_stem(sku_by_code[item[0]].name) not in target_stems
         or sku_by_code[item[0]].collection_name not in target_cols),   # (2)
        0,
    )
    picked.append(remaining.pop(distinct))
```

Las líneas del día se muestrean **independientemente** —`_weighted_choice` pondera sólo por
colección y perfil de POS, nunca por lo ya elegido—, se **barajan** (1), y el empaquetador escoge
activamente el siguiente artículo **cuyo lexema de nombre o cuya colección difieran** (2).

> **No existe ningún modelo de «lo que se compra junto».** La matriz de co-ocurrencia es, por
> construcción, el producto exterior de la popularidad marginal dentro de cada POS, con un
> empujón **anti**-correlativo contra los pares afines.

Leer esa matriz como evidencia de que dos piezas se venden juntas es circular, y circular en la
peor dirección: el generador fue escrito para *evitar* emparejar lo parecido. La señal no es
débil — está sesgada en contra de lo que se le pide medir.

**Esto no es un defecto de C10.** Su ficha nunca prometió afinidad, y diversificar la cesta es lo
correcto para lo que C10 sí tenía que producir: stock coherente, movimientos que cuadran y picos
estacionales. El error está en que C27 dé por supuesta una propiedad que nadie generó.

---

## 2. Y aunque la tuviera, la señal es un booleano casi vacío

```sql
WITH pairs AS (
  SELECT LEAST(a."ProductId", b."ProductId") AS pa, GREATEST(a."ProductId", b."ProductId") AS pb
  FROM public."Sales" a JOIN public."Sales" b
    ON a."BulkOperationId" = b."BulkOperationId" AND a."ProductId" < b."ProductId"
  WHERE a."BulkOperationId" IS NOT NULL
), counted AS (SELECT pa, pb, count(*) AS n FROM pairs GROUP BY pa, pb)
SELECT n AS co_ventas, count(*) AS num_pares FROM counted GROUP BY n ORDER BY n;
```

| Métrica | Valor |
|---|---:|
| Ventas totales | 22.968 |
| Ventas con `BulkOperationId` | 5.641 (24,6 %) |
| Operaciones bulk distintas | 2.381 |
| **Pares distintos observados** | **4.078** de ~719.400 posibles — **0,57 %** |
| Pares vistos **una sola vez** | **4.019 — 98,6 %** |
| Pares vistos dos veces | 59 — 1,4 % |
| **Pares vistos tres o más veces** | **0. Ninguno, en 16 meses de histórico** |

Y desde la perspectiva de la consulta, que es la que decide si la señal sirve — restringido a
pares de **`piece_type` distinto**, que es la regla de la ficha:

| Métrica | Valor |
|---|---:|
| Pares con tipo distinto | 3.364 de 4.059 con tipo conocido |
| **Productos con algún socio** | **705 de 1.168 — 60,4 %** |
| Productos **sin ningún socio** | **463 — 39,6 %** |
| Socios por producto (mediana / media / máx) | 9 / 9,5 / 32 |
| **Productos con algún socio repetido (`n ≥ 2`)** | **84 — 7,2 %** |

Traducido a comportamiento: para **el 40 % de los productos la señal no existe**, y para el 60 %
restante ofrece una mediana de **nueve socios todos empatados a 1**, es decir **no puede
ordenarlos**. `co_sales_count` no es una señal de ranking: es un booleano presente/ausente, con
una cola de 59 pares que nada distingue del ruido de muestreo.

**El precedente está dentro de este mismo proyecto, y es literal.** C25 retiró la rotación como
criterio de orden porque *«como desempate estricto decidía **cero** pares del top-5 en las 48
consultas»*. La co-ocurrencia es peor: la rotación al menos salía de agregados reales sobre el
feed, y ésta sale de un simulador que diversifica a propósito (§1).

**Estado de la tabla:** `ai.co_occurrence` tiene hoy **0 filas**. Los 4.075 pares del informe de
C10 son un JSONL efímero que nunca se persistió — persistirlos es, precisamente, trabajo de C27.

---

## 3. La otra mitad de la regla también está vacía, y sobre todo en lo real

La regla de la ficha es *«distinto `piece_type`, **solape de `color_tags`/`style_tags`**, banda de
precio compatible, disponible en el POS»*. Cobertura medida de las dos etiquetas que sostienen el
solape:

| `data_origin` | documentos | con `color_tags` | con `style_tags` |
|---|---:|---:|---:|
| **`real`** | 404 | **37 — 9,2 %** | **1 — 0,2 %** |
| `synthetic` | 764 | 189 — 24,7 % | 130 — 17,0 % |
| **total** | 1.168 | 226 — 19,4 % | 131 — 11,2 % |

| Corte | documentos |
|---|---:|
| Con **ambas** etiquetas | 61 — 5,2 % |
| Con **alguna** | 296 — 25,3 % |
| **Con ninguna** | **872 — 74,7 %** |

En la porción **real** —la que el criterio de aceptación del §11.2 del diseño designa como
resultado principal— **un solo producto tiene etiqueta de estilo**. El solape de etiquetas está
indefinido para entre el 91 % y el 99,8 % del catálogo que decide.

**Quitadas las dos señales vacías, lo que queda de C27 es:**

```sql
WHERE piece_type <> :tipo_origen AND price_band IN (:bandas) AND stock > 0
```

Una cláusula `WHERE`, sin una sola llamada a un LLM. Es exactamente el criterio con el que el 31 de
agosto se anularon cinco changes: *«cinco changes de los que tres no tienen ni una llamada a un
LLM»*.

---

## 4. Nunca hubo intención de medirlo, y eso es información sobre el change

| Instrumento | Categoría de **sustituto** | Categoría de **complementario** |
|---|---|---|
| Diseño §11.1, tabla del golden set | **6 consultas** | **no figura** |
| Golden set real (71 consultas, 63 juzgadas) | **4** — `q49`–`q52`, con nota escrita | **0** |
| `criterion.md`, definición del grado 1 | *«sustituto plausible que el operador ofrecería como segunda opción»* | nada |
| `openapi.json` congelado | `/v1/retrieval/substitutes` ✅ | **ausente** |

Las 8 consultas sin juzgar del golden set se reparten **4 para C26** (sustitutos) y **4 para C31**
(ambiguas, router de intención). **Cero para C27.** Ni el diseño, escrito antes de implementar, ni
C24, escrito con el plan delante, reservaron hueco para complementarios.

> **C27 es, por construcción del propio proyecto, una funcionalidad no medible.** En un PFM cuyo
> rubro dice *«se evalúa con métricas objetivas, no con intuición»* y *«el sistema tiene evals
> reales, no solo pruebas manuales»*, entregar una capacidad que no puede entrar en la tabla de
> ablations es un intercambio estrictamente negativo: cuesta la última migración viva y no añade
> ni una fila a la evidencia.

---

## 5. No hay cestas reales, ni las habrá sin un export nuevo

El export recibido el 2026-08-17 fue **catálogo y nada más**: `data/catalog/real/product-JoiaBagur.xlsx`,
436 productos y 28 colecciones. **Cero ventas reales.** Las 22.968 ventas del sistema son todas de
C10, y las 63 que involucran un producto del ancla real son ventas sintéticas sobre productos
reales, no tickets observados.

La fila del §8.3 del diseño que dice *«D8 Histórico de ventas · Co-ocurrencia por operación de
venta»* describe un dataset **generado**, no recibido. La pregunta abierta nº 2 del §14 se cerró
con *«sí, de tamaño desconocido»* refiriéndose al catálogo; el histórico no llegó.

**Consecuencia:** no existe ninguna ruta para que la co-ocurrencia signifique algo dentro del
alcance actual. Es una condición de datos, no de esfuerzo, y por eso el corte es firme y no
aplazado.

---

## 6. Coste comparado, para dejar el intercambio por escrito

| | **C26** sustitutos | **C27** complementarios |
|---|---|---|
| Lenguajes | Python | **Python + .NET** (+ frontend implícito para curar) |
| Migración EF Core | no | **sí — la última viva del plan** |
| Contrato congelado | **ya lo tiene**, hoy responde 501 | **hay que moverlo**: `/v1/retrieval/complementary` no está en `openapi.json`, así que `test_openapi_snapshot_is_stable` falla y exige acuerdo con el dueño del cliente .NET |
| Tubería nueva | no | persistir `ai.co_occurrence` (hoy 0 filas) con mapeo SKU→UUID |
| Zona declarada en la ficha | `retrieval/` | *«Python + `Domain/`»* — pero el §0 ya avisa: *«un change 🗄️ siempre toca `Infrastructure/` y `Tests/`»* |
| Señales que entrega | 4, sobre 90-100 % de cobertura | 2, ambas medidas vacías |
| Filas que añade a la evaluación | **4 consultas reservadas a su nombre** | **0** |

---

## 7. Cinco contraargumentos, y por qué no aguantan

| Contraargumento | Por qué no aguanta |
|---|---|
| *«La curación manual es el punto, no la co-ocurrencia»* | Es HITL sin LLM, y el HITL ya está demostrado dos veces con volumen real (156 familias en C18a/b; C28 lo repite con métricas). Y el 65 % del catálogo es sintético: **curar pares complementarios de joyería inventada es fabricar dato sobre un mundo que no existe**, un renglón más junto al *«los atributos no derivables son plausibles, no verificados»* del §15.1 |
| *«Un empate a 1 sigue siendo mejor que nada»* | El 98,6 % está a 1: es un booleano, no un ordenador. Y el caso exacto ya lo resolvió C25 con la rotación |
| *«C32, C34 y C36 lo referencian; caerse cuesta retrabajo»* | **El corte ya está precableado por escrito en las tres fichas.** C34: *«si cae, se retira la ruta `.../recommendations` y su test, y el resto del change no se toca»*. C32: *«`buscar_complementarios` se retira también si se dispara el corte nº 1»*. C36 pierde uno de cuatro bloques. Disparar el corte cuesta tres líneas |
| *«El agente se queda con seis tools en vez de siete»* | Ya bajó de ocho a siete sin daño. Lo que el rubro evalúa del agente es el bucle, el presupuesto duro, el invariante de solo-lectura y el `partial: true`, no el recuento |
| *«La card de venta queda más pobre en el vídeo»* | Es el más fuerte, y aun así pierde: el rubro premia *«se identifican limitaciones actuales y se propone cómo resolverlas»*, y este proyecto ya convirtió eso en activo con el §10 del diseño. Un §15 que diga **«complementarios: diseñado, medido con cinco cifras, descartado porque el corpus no puede sostener la señal, reactivable el día que llegue un export con tickets reales»** vale más que enviar una señal de ruido |

**Y el punto de fondo:** C27 sería el **primer change de este proyecto que entrega una señal que su
propia medición declara vacía**. Eso es una regresión precisamente en lo que el proyecto hace
mejor, y es lo contrario de *«decisiones técnicas justificadas, no asumidas por defecto»*.

---

## 8. Lo que se conserva, y en qué forma

El corte **retira la implementación, no el diseño**, siguiendo el precedente del §10 (inventario
anulado con su diseño íntegro conservado como próximo paso):

| Artefacto | Destino |
|---|---|
| Ficha de C27 en el §3 | **Se conserva** con sello de corte disparado y enlace a este informe |
| `ai.co_occurrence` (tabla vacía en la migración de C05) | **Se conserva**. No cuesta nada, y es el enganche del día que lleguen tickets reales |
| [`cooccurrence.py`](../../../ai-service/src/jbg_ai/data/world/cooccurrence.py) y su test | **Se conservan**: derivan correctamente lo que se les pide, y el defecto está en el generador de cestas, no en ellos |
| `/v1/retrieval/complementary` | **No se añade** al contrato congelado. Un 501 menos, no uno más |
| Entrada en el §15 del diseño | **Se añade** — limitación declarada con su medición y su condición de reactivación |
| Tool `buscar_complementarios` de C32 | **Se retira del registro**, por la misma regla que retiró `perfil_punto_venta`: una tool que falla siempre es peor que una ausente |
| Ruta `.../recommendations` y test `Recommendations_ManualPairsRankedFirst` de C34 | **Se retiran**, como su propia ficha ya instruía |
| Bloque «También puede encajar» de C36 | **Se retira**; la card conserva argumentario, avisos, citas, variantes de familia y sustitutos |

**Condición de reactivación, escrita para que sea comprobable y no opinable:** un export con
histórico de ventas **reales a nivel de ticket**, del que se pueda derivar una matriz de
co-ocurrencia con al menos una cola no degenerada — como listón operativo, que el percentil 95 de
`co_sales_count` sea ≥ 3. Con la matriz actual ese percentil es **1**.
