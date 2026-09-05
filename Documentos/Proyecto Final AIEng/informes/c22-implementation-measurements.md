# C22 — mediciones de la implementación (prefiltro blando por punto de venta)

**Medido el 2026-09-05**, después de implementar el change, contra el PostgreSQL local
(`jpv-pv-postgres`, puerto 5433, PostgreSQL 15.19 con `vector` **0.8.6**), los **1.168
documentos vivos** de `ai.product_document` y las **6.720 filas** de `public."Inventories"`
del mundo de C10.

Complementa a [`c22-exploration-measurements.md`](c22-exploration-measurements.md), que midió
el **antes** con la proyección vacía. Aquí se mide el **después**, con la proyección poblada
por el drenaje real, y se contrastan las tres predicciones de aquel informe que ahora pueden
comprobarse. **Dos se confirman y una no**, y la que no se confirma está en la §5.

**Sin llamadas al proveedor de embeddings.** Como en la exploración, las sondas usan vectores
**ya persistidos** en el índice (auto-similitud), así que estas cifras son reproducibles sin
credenciales.

---

## 1. El drenaje real

`python -m jbg_ai.indexing sync-pos --full` contra el feed servido por la API .NET local:

```
upserted=6050 soft_deleted=670 pages=34 failed_pages=0 computed_as_of=2026-08-23T23:59:59+00:00
exit=0   duración=10,9 s
```

| Magnitud | Valor | Contraste |
|---|---|---|
| Filas escritas | **6.720** | Exactamente las 6.720 filas de `Inventories` |
| Upserts | 6.050 | Las asignaciones activas |
| Borrados blandos | **670** | Los desasignados que la exploración contó: **670 de 6.720** |
| Páginas | 34 | 6.720 / 200, con la última parcial |
| Fallos por lote | 0 | |
| Duración | 10,9 s | Muy por debajo del presupuesto de 180 s |

**Ninguna fila se borró.** Los 670 tombstones se aplicaron como borrado blando
(`is_assigned_hint = false`, `qty_bucket = '0'`), que es lo que hace alcanzable un campo que
el feed sólo sabe emitir en `true`.

## 2. Deriva contra el `aggregateHash` del feed

El hash del feed y el calculado sobre `ai.pos_projection` **coinciden byte a byte**:

```
feed  = 3c239b0001ed2aeb6c061dd1b307de6a14e4eb8121e5115458a42e9207c4dd52
local = 3c239b0001ed2aeb6c061dd1b307de6a14e4eb8121e5115458a42e9207c4dd52
```

**Deriva = 0.** Se calcula sobre los pares `(pos_id, product_id)` con `is_assigned_hint`,
ordenados por bytes del identificador — el orden **sin signo** que documenta `set_hash.py` y
que C17 descubrió por las malas.

## 3. El surtido, por punto de venta

| POS | Asignados | Borrados blandos | Stock 0 | % a 0 | `sales_30d` ≠ 0 | % |
|---|---:|---:|---:|---:|---:|---:|
| BINIBECA | 457 | 47 | 33 | 7,2 | 107 | 23,4 |
| CIU-CENTRE | 871 | 65 | 32 | 3,7 | 241 | 27,7 |
| EIV-MARINA | 441 | 39 | 39 | 8,8 | 145 | 32,9 |
| FORNELLS | 241 | 23 | 29 | 12,0 | 61 | 25,3 |
| HT-ALCUDIA | 422 | 34 | 20 | 4,7 | 100 | 23,7 |
| **HT-ARTRUTX** | **0** | **144** | 0 | — | 0 | — |
| HT-GALDANA | 469 | 35 | 55 | 11,7 | 179 | 38,2 |
| HT-SONBOU | 434 | 46 | 23 | 5,3 | 142 | 32,7 |
| MAO-AIR | 416 | 40 | **143** | **34,4** | 168 | 40,4 |
| MAO-TALLER | 1.082 | 94 | 0 | 0,0 | 1 | 0,1 |
| PALMA-JAIME3 | 813 | 75 | 7 | 0,9 | 177 | 21,8 |
| PORT-MAO | 404 | 28 | 47 | 11,6 | 103 | 25,5 |

Las tres cifras que la exploración usó para decidir D3 se reproducen **exactas**: MAO-AIR
**34,4 %** a cero, FORNELLS **12,0 %**, HT-GALDANA **11,7 %**. Igual los desasignados por
punto de venta con operador: CIU-CENTRE 65, MAO-AIR 40, FORNELLS 23.

**HT-ARTRUTX aparece con surtido cero y 144 filas borradas en blando**, y es la única
consecuencia operativa que no estaba en la ficha: un token emitido para ese punto de venta
recibe **503** por la guardia de proyección vacía. Es la respuesta correcta —no tiene nada que
vender— pero conviene que esté escrita antes de que alguien la encuentre en un log.

## 4. Tasa de llenado, antes y después

20 sondas de auto-similitud, profundidad 60, umbral 0,65, página de 10. **Antes** = el
comportamiento de hoy: se ordena todo el catálogo y .NET descarta en la hidratación lo que el
punto de venta no lleva. **Después** = la sentencia escopada que este change entrega.

| POS | Surtido | Sondas < 10 (antes → después) | Peor caso | Mediana |
|---|---:|---|---|---|
| BINIBECA | 457 | 4/20 → **0** | 7 → 60 | 25 → 60 |
| CIU-CENTRE | 871 | 0/20 → 0 | 24 → 60 | 52 → 60 |
| EIV-MARINA | 441 | 6/20 → **0** | 6 → 60 | 21 → 60 |
| FORNELLS | 241 | 8/20 → **0** | 3 → 60 | 10 → 60 |
| HT-ALCUDIA | 422 | 6/20 → **0** | 2 → 60 | 22 → 60 |
| HT-GALDANA | 469 | 6/20 → **0** | 3 → 60 | 22 → 60 |
| HT-SONBOU | 434 | 5/20 → **0** | 3 → 60 | 19 → 60 |
| MAO-AIR | 416 | 6/20 → **0** | 3 → 60 | 18 → 60 |
| MAO-TALLER | 1.082 | 0/20 → 0 | 49 → 60 | 54 → 60 |
| PALMA-JAIME3 | 813 | 0/20 → 0 | 21 → 60 | 49 → 60 |
| PORT-MAO | 404 | 6/20 → **0** | 3 → 60 | 20 → 60 |

**Ocho de los once puntos de venta** tenían al menos una sonda por debajo de la página, que es
exactamente lo que midió la exploración. Después: ninguno.

**Y aquí hay que ser preciso sobre lo que la columna «después» significa.** El 60 no es una
medida de calidad: es la profundidad de rama, y se alcanza siempre porque el surtido más
pequeño (FORNELLS, 241) es mayor que la ventana **y** porque el umbral de 0,65 deja pasar
prácticamente todo el corpus —lo que C21 ya documentó al fijar el peso del vector en 0,33—.
Es decir: **el change garantiza que la página se llena, no que se llene bien.** Ordenar bien
dentro del surtido es la pregunta que C24 mide con el golden set, y el golden set está
etiquetado **sin escopar** precisamente para no mezclar calidad de recuperación con cobertura
de surtido.

## 5. El plan escopado: la predicción que no se confirma

La exploración predijo **7,3 ms** escopado frente a **10,8 ms** sin escopar. Medido ahora, en
la misma máquina y sobre la proyección poblada, con `TIMING OFF` para no pagar la
instrumentación por nodo:

| Sentencia | 3 ejecuciones |
|---|---|
| Sin escopar | 18,0 · 19,3 · 33,1 ms |
| **Escopada** | **17,3 · 14,8 · 16,0 ms** |

**La dirección se sostiene** —la escopada no es más lenta, es algo más rápida— **pero las
cifras absolutas de la exploración eran optimistas**, por un factor de dos, y conviene no
citarlas. Ambas están holgadamente dentro del presupuesto de 2.500 ms de `AiGateway`.

Más importante que el número es lo que dice el plan, porque **matiza D2**:

```
Sort (top-N heapsort, rows=60)
  Hash Join (rows=239)
    CTE Scan on scope (rows=241)
    Hash → Seq Scan on product_document (rows=1168)
             Filter: embedding <=> $2 <= 0.65
```

El planificador **filtra por distancia sobre los 1.168 documentos y hace el join después**, así
que la CTE **no** reduce el número de distancias calculadas. La justificación de D2 no es, por
tanto, el ahorro de cómputo: es la **corrección**. La CTE materializada garantiza que el
subconjunto existe antes de ordenar, de modo que la profundidad de rama se respeta por
construcción y no por suerte del planificador — que es exactamente la trampa de S10 que la
exploración reprodujo forzando el índice HNSW (40 filas de 60, sin error visible).

## 6. El reloj de referencia

`computedAsOf` viaja en la página del feed con el valor configurado y se persiste **en cada
fila**:

```
computedAsOf en la página     = 2026-08-23T23:59:59Z
computed_as_of en 6.720 filas = 2026-08-23 23:59:59+00 .. 2026-08-23 23:59:59+00
```

Rango de un solo valor: la proyección entera se contó contra el mismo reloj. Ése es
exactamente el estado que la columna existe para poder afirmar — y para poder desmentir el día
que alguien fije el instante después de un primer drenaje incremental.

**`lastSaleAt` también está acotado por el instante, y no lo estaba al principio.** La
verificación posterior a la implementación encontró que las dos ventanas usaban el instante
inyectado pero `MAX(SaleDate)` no, así que **3 filas de la proyección llevaban un
`last_sale_at` de 2026-08-29 contra un `computed_as_of` de 2026-08-23**: las ventas manuales
de C16. Era conforme a la letra de la spec —que pedía `MAX(SaleDate)`— y contrario a su
propósito, porque era la única cifra de la página que seguía derivando cada vez que se
registra una venta en la demo, y es candidata a alimentar el decaimiento de C25. Acotada y
redrenado:

| | Antes | Después |
|---|---:|---:|
| Filas con `last_sale_at` > `computed_as_of` | 3 | **0** |
| `last_sale_at` máximo | 2026-08-29 10:13 | 2026-08-23 19:56 |
| Filas con `last_sale_at` no nulo | 4.021 | 4.021 |
| `sales_30d` no nulos | 1.424 | 1.424 |

La frase de la spec de `index-feed` se enmendó en el mismo movimiento.

Con el instante aplicado, sobre los 6.050 pares asignados:

| Señal | No nulos | % |
|---|---:|---:|
| `sales_30d` | 1.424 | **23,54 %** |
| `sales_90d` | 2.666 | 44,07 % |

**El diseño predijo que `sales_30d` «recupera un 16,28 % estable», y el valor estable real es
23,54 %.** No es un error del cambio: el 16,28 % era la medida contra el reloj de pared *hoy*
(ventana 2026-08-06 → 2026-09-05), mientras que la ventana anclada al horizonte es 2026-07-24
→ 2026-08-23, que cae de lleno en el pico de verano que el mundo de C10 modela. Lo estable es
el mecanismo, no la cifra que el diseño citó. **C25 calibra sobre 23,54 %, no sobre 16,28 %.**

## 7. Lo que queda declarado

- **La medición de llenado usa sondas de auto-similitud**, no consultas reales de operador
  contra el proveedor. Es reproducible sin credenciales y comparable con la exploración, que es
  para lo que sirve; no sustituye a la telemetría de C04 como línea base de «antes».
- **MAO-TALLER** (1.082 asignados, 0,1 % de rotación) es el taller, no una tienda. Sus cifras
  no describen a un operador de mostrador.
- **`sales_30d`, `sales_90d` y `last_sale_at` se escriben y no se leen.** Es deliberado: son la
  entrada de C25, y escribirlas ahora es lo que permite que C25 sea un cambio de ranking en vez
  de un cambio de sincronización.

---

## Reproducir

```bash
# 1. API .NET local en 127.0.0.1:5056
dotnet run --project backend/src/JoiabagurPV.API --launch-profile http

# 2. Drenaje completo
cd ai-service
APP_ENV=local SERVICE_VERSION=0.1.0 JWT_SECRET=... \
DATABASE_URL="postgresql+psycopg://jbg_ai:...@localhost:5433/joiabagur_pv" \
JPV_INDEX_FEED_BASE_URL="http://127.0.0.1:5056" \
JPV_INDEX_FEED_API_KEY="local-dev-index-feed-key-0123456789ab" \
uv run --system-certs python -m jbg_ai.indexing sync-pos --full
```

Las consultas de las §3 a §6 son SQL de sólo lectura contra `ai.pos_projection` y
`ai.product_document`; las sondas de la §4 crean únicamente tablas `TEMP`.
