# C22 — mediciones de la exploración (prefiltro blando por punto de venta)

**Medido el 2026-09-05** contra el PostgreSQL local (`jpv-pv-postgres`, puerto 5433,
PostgreSQL 15.19 con `vector` **0.8.6**), sobre los **1.168 documentos vivos** de
`ai.product_document` y las **6.720 filas** de `public."Inventories"` del mundo de C10.

**Todo en solo lectura.** Las tablas auxiliares de las sondas se crearon como `TEMP` y murieron
con la sesión; no se escribió una fila en ninguna tabla real, ni en `public` ni en `ai`.

**Sin llamadas al proveedor de embeddings.** Los vectores de consulta de las sondas son
embeddings **ya persistidos** en el índice, usados como sonda de auto-similitud. Eso evita el
problema de TLS interceptado que documenta el informe de C21 y hace las mediciones
reproducibles sin credenciales.

---

## 1. Punto de partida verificado

| Objeto | Estado |
|---|---|
| `ai.product_document` | 1.168 filas, **todas** con embedding |
| `ai.pos_projection` | **0 filas** — nunca se ha escrito, como C13 declaró |
| `ai.sync_checkpoint` | una sola fila, `feed = 'catalog'`; no existe la de `pos-availability` |
| Índice HNSW | `ix_product_document_embedding_hnsw`, `vector_cosine_ops`, `m=16`, `ef_construction=128` |
| `hnsw.ef_search` | **40** (valor por defecto) — frente a una profundidad de rama de **60** |

`ai.sync_checkpoint` tiene `feed` como clave primaria —*una fila por feed*—, así que la
sincronización de la proyección **no necesita migración**.

---

## 2. Medición 1 — asignación e inventario por punto de venta

Predicado de la autoridad, tomado literalmente de
[`AssistedSearchRepository.Carried()`](../../../backend/src/JoiabagurPV.Infrastructure/Data/Repositories/AssistedSearchRepository.cs):
`Inventory.PointOfSaleId = pos ∧ Inventory.IsActive ∧ Product.IsActive`.

| POS | filas | asignados | **desasignados** | % desasig. | **stock 0** (de los asignados) |
|---|---:|---:|---:|---:|---:|
| MAO-TALLER | 1.176 | 1.082 | 94 | 8,0 % | 0 |
| CIU-CENTRE | 936 | 871 | 65 | **6,9 %** | 32 (3,7 %) |
| PALMA-JAIME3 | 888 | 813 | 75 | 8,4 % | 7 (0,9 %) |
| BINIBECA | 504 | 457 | 47 | 9,3 % | 33 (7,2 %) |
| HT-GALDANA | 504 | 469 | 35 | 6,9 % | 55 (11,7 %) |
| EIV-MARINA | 480 | 441 | 39 | 8,1 % | 39 (8,8 %) |
| HT-SONBOU | 480 | 434 | 46 | 9,6 % | 23 (5,3 %) |
| HT-ALCUDIA | 456 | 422 | 34 | 7,5 % | 20 (4,7 %) |
| MAO-AIR | 456 | 416 | 40 | **8,8 %** | **143 (34,4 %)** |
| PORT-MAO | 432 | 404 | 28 | 6,5 % | 47 (11,6 %) |
| FORNELLS | 264 | 241 | 23 | **8,7 %** | 29 (12,0 %) |
| HT-ARTRUTX *(cerrado)* | 144 | 0 | 144 | 100 % | — |
| **TOTAL** | **6.720** | **6.050** | **670** | 10,0 % | |

Los 6.050 pares activos cuadran exactamente con la cifra del §0 del plan.

**Dos consecuencias.**

**La primera decide la semántica del filtro duro.** Los desasignados son el **7-9 %** en los tres
puntos de venta con operador. Si el filtro duro fuese la mera existencia de fila —la lectura
literal de la ficha—, ese 7-9 % de la ventana de 60 candidatos se gastaría en productos que
`Carried()` tira **con total seguridad**. Se adopta el filtro sobre `is_assigned_hint`, que es
exactamente el predicado de la autoridad.

**La segunda salva la promesa del §7.6, y la sitúa donde de verdad aplica.** `Carried()` **no
filtra por cantidad**: un producto sin stock llega hoy al operador con `HasStock: false`. Luego
`qty_bucket = 0` **debe** ponderar y nunca excluir. Y no es una señal teórica: **MAO-AIR tiene
un tercio de su surtido a cero** (143 de 416), y cuatro puntos de venta pasan del 8 %.

---

## 3. Medición 2 — el índice HNSW no se usa, y forzarlo es peor

Cuatro planes, con el vector de consulta como **literal** (condición necesaria para que el
índice sea siquiera candidato: si el vector viene de un `JOIN`, pgvector no puede usarlo).

| Consulta | Plan elegido | Tiempo | Filas devueltas |
|---|---|---:|---:|
| Sin escopar, forma canónica (`ORDER BY … LIMIT 60`) | **Seq Scan** + top-N heapsort | 8,2 ms | 60 |
| Sin escopar, **forma viva de C14** (con umbral 0,65) | **Seq Scan** + top-N heapsort | 10,8 ms | 60 |
| Sin escopar, **HNSW forzado** (`enable_seqscan=off`) | Index Scan HNSW | **113,7 ms** | **40** ⚠ |
| **Escopado a FORNELLS** (239 documentos) | Hash Join + Seq Scan + top-N | **7,3 ms** | 60 |

**Tres conclusiones.**

1. **El índice HNSW no se ha usado nunca en la ruta viva.** Desde C14, el planificador elige
   escaneo secuencial exacto, porque a 1.168 filas le sale más barato. La decisión de escopar
   con un CTE y calcular la distancia exacta sobre el subconjunto **no cambia de motor**: hace
   explícito lo que la base de datos ya venía haciendo.
2. **Forzar HNSW cuesta 13× más y trunca la respuesta.** 113,7 ms para devolver **40 de las 60
   filas pedidas**: es `ef_search = 40` recortando, que es exactamente la trampa de
   post-filtrado que describe el apunte de S10 —*«el índice puede devolver sus 50 vecinos más
   cercanos, el filtro descartar 48, y la consulta entregar 2 resultados sin ningún error
   visible»*—. Real y reproducible aquí; simplemente no está en el camino vivo.
3. **Escopar acelera**: 7,3 ms frente a 10,8 ms. El prefiltro no es un coste, es un ahorro.

> **Se refuta una hipótesis de la propia sesión de exploración.** Se conjeturó que las
> mediciones planas de profundidad de C21 (40 → 113/120, 60 → 111, 100 → 107) podían ser
> `ef_search` recortando el índice. **Es falso:** la rama vectorial nunca tocó el índice. Aquellos
> números son comportamiento genuino de RRF, tal como el propio módulo de fusión explica.

**Nota de implementación, no decisión.** En el plan escopado la distancia se calcula sobre las
1.168 filas y el `Hash Join` filtra después. Un bucle anidado dirigido por el alcance la
calcularía sólo 239 veces. A 7 ms da igual; conviene mirarlo al implementar, no antes.

---

## 4. Medición 3 — la aritmética de página, que es la razón de ser del change

20 consultas sonda sobre el índice real, umbral 0,65, ventana de over-retrieval de 60 —los
mismos parámetros que la ruta viva—, contando cuántos candidatos sobreviven a `Carried()`.

| POS | **HOY** media supervivientes | peor | mejor | **consultas cortas** (< 10) | **CON C22** |
|---|---:|---:|---:|---:|---:|
| FORNELLS | **10,5** | **1** | 37 | **12 de 20** | 60 |
| PORT-MAO | 20,1 | 3 | 42 | 8 de 20 | 60 |
| BINIBECA | 23,2 | 7 | 51 | 6 de 20 | 60 |
| HT-ALCUDIA | 23,3 | 1 | 51 | 7 de 20 | 60 |
| EIV-MARINA | 23,6 | 6 | 46 | 7 de 20 | 60 |
| HT-SONBOU | 24,6 | 4 | 50 | 7 de 20 | 60 |
| MAO-AIR | 24,7 | 2 | 47 | 7 de 19 **+ 1 vacía** | 60 |
| HT-GALDANA | 27,0 | 1 | 56 | 6 de 20 | 60 |
| PALMA-JAIME3 | 40,4 | 21 | 56 | 0 | 60 |
| CIU-CENTRE | 43,5 | 23 | 59 | 0 | 60 |
| MAO-TALLER | 54,0 | 49 | 59 | 0 | 60 |

**No era un problema de FORNELLS: era un problema de ocho de los once puntos de venta.** Con la
recuperación escopada al catálogo entero, ocho POS tienen **al menos 6 de cada 20 búsquedas por
debajo de una página de 10**, el peor caso de FORNELLS deja **un solo producto**, y una de las
veinte consultas de MAO-AIR **no deja ninguno** — página completamente vacía, indistinguible
desde el panel de una abstención legítima.

La verificación manual de C16 (CIU-CENTRE 60 → 32, FORNELLS 60 → 8) cae dentro de estos rangos.

**Lo que la columna «CON C22» dice y lo que no dice.** Dice que con el alcance aplicado en SQL
los tres canales entregan su ventana completa. **No** dice que la página siempre se llene: con
un umbral estrecho (0,35), que representa una consulta discriminante, los candidatos
disponibles dentro del POS son:

| POS | media | **peor caso** |
|---|---:|---:|
| FORNELLS | 65,6 | **18** |
| PORT-MAO | 117,9 | 28 |
| MAO-AIR | 121,8 | 21 |
| CIU-CENTRE | 254,9 | 103 |
| MAO-TALLER | 321,6 | 104 |

Sigue llenando una página de 10 en las veinte consultas, pero la holgura real de FORNELLS es
esa —18 candidatos en el peor caso—, no infinita. **La página corta no desaparece: deja de ser
el caso normal y pasa a ser honesta**, porque cuando ocurra será porque el punto de venta no
tiene surtido, no porque el ranking mirase a otro sitio.

---

## 5. Medición 4 — el reloj: las ventanas de venta se están vaciando

**El mundo de C10 tiene horizonte fijo.** Primera venta **2025-04-23**, última venta real
**2026-08-23** (80 ese día), más **7 ventas sueltas del 2026-08-29** que son las pruebas
manuales de C16. Esas 7 son exactamente las que hacen que `sales_7d` valga 3 pares de 6.050 —el
0,05 % que el §0 midió el 31 de agosto—. `public."InventoryMovements"` confirma la misma
historia: 29.688 filas frente a las 29.681 del informe de C10, siete más.

Los agregados los calcula
[`IndexFeedRepository`](../../../backend/src/JoiabagurPV.Infrastructure/Data/Repositories/IndexFeedRepository.cs)
contra el **reloj de pared**. Proyección de la cobertura sobre los 6.050 pares activos:

| `as_of` | `sales_30d` ≠ 0 | | `sales_90d` ≠ 0 | |
|---|---:|---:|---:|---:|
| **2026-09-05 (hoy)** | 985 | **16,28 %** | 2.533 | **41,87 %** |
| 2026-09-12 | 653 | 10,79 % | 2.426 | 40,10 % |
| 2026-09-19 | 287 | 4,74 % | 2.302 | 38,05 % |
| **2026-09-22** | 80 | **1,32 %** | 2.239 | 37,01 % |
| 2026-09-26 | 3 | 0,05 % | 2.166 | 35,80 % |
| 2026-10-10 | **0** | **0,00 %** | 1.839 | 30,40 % |
| 2026-10-31 | 0 | 0,00 % | 1.150 | 19,01 % |
| 2026-11-21 | 0 | 0,00 % | 80 | **1,32 %** |

```
%  ┤
50 ┤ ●─────●─────●─────●─────●──────●
   │  sales_90d          ╲                     ← aguanta hasta el 21-nov
40 ┤                      ●─────╲
30 ┤                             ●────╲
20 ┤                                   ●
16 ┤ ○                                         ← sales_30d HOY
10 ┤    ○
 5 ┤        ○
 0 ┤            ○──○──✕──────────────────────  ← cero el 26-sep
   └──┬────┬────┬────┬────┬─────┬─────┬─────
    05/9 12/9 19/9 22/9 26/9  10/10  21/11
```

---

## 6. Medición 5 — los cuatro relojes del repositorio caducan el mismo día

| Reloj | Fichero | Ventana | A qué afecta |
|---|---|---|---|
| `since30` / `since90` | `IndexFeedRepository.cs:174-175` | 30 / 90 d | **el RAG.** Es el único que importa para este change, y es **un solo sitio** |
| `DefaultDaysBack` | `InventoryMovementService.cs:18` | 30 d | informe de movimientos de inventario |
| `ReturnWindowDays` | `ReturnService.cs:27` | 30 d | **poder devolver una venta histórica en la demo** |
| hoy / semana / mes | `DashboardService.cs:43` | ≤ 30 d | dashboards por rol — **ya están a cero** |

Los tres primeros tienen ventana de 30 días. **Caducan juntos alrededor del 2026-09-22.** Es
decir: 17 días desde esta medición para que la demo empiece a mentir en tres sitios a la vez.

---

## 7. Hallazgos de código que no son mediciones

### 7.1 `is_assigned_hint` nace siempre `true`, así que el campo es hoy una constante

[`IndexFeedService.MapPosItem`](../../../backend/src/JoiabagurPV.Application/Services/IndexFeedService.cs)
devuelve tombstone si `!row.IsActive`, y en la rama de upsert fija `IsAssignedHint = true`
literalmente. La spec viva lo corrobora: *«Active `Inventory` rows in the cursor window MUST be
upserts»* más *«`isAssignedHint` MUST reflect `Inventory.IsActive`»*. Las dos frases juntas hacen
el campo constante.

**Consecuencia:** el test `test_unassigned_product_is_penalised_not_removed` de la ficha **no se
puede satisfacer** sin decidir antes qué hace la sincronización con el tombstone. Se resuelve
aplicándolo como **borrado suave** (§8, decisión 1).

### 7.2 Dos specs vivas prohíben literalmente lo que este change hace

| Spec viva | Frase normativa | Estado tras C22 |
|---|---|---|
| `vector-retrieval` | «**AND** the search SQL does not filter by `pos_id`» | **falsa** |
| `product-document-indexer` | «MUST NOT invoke the POS availability feed and MUST NOT write `ai.pos_projection`» | **falsa** |

Y al entrar el reloj inyectado en el mismo change se suma una tercera:

| `index-feed` | «`sales30d` and `sales90d` MUST be `SUM(Sale.Quantity)` … **over the last 30 and 90 days**» | **falsa**: pasan a contarse contra el instante de referencia |

Es el patrón que `CLAUDE.md` describe y por el que FIX1 exige change propio:
`openspec validate --all --strict` **seguiría en verde**, porque valida estructura y no verdad.
C22 lleva obligatoriamente **tres deltas `## MODIFIED Requirements`**.

### 7.3 El `pos_id` del token es un GUID en producción y `"POS-B"` en los tests

[`AiServiceTokenFactory`](../../../backend/src/JoiabagurPV.Application/Services/AiServiceTokenFactory.cs)
firma `pointOfSaleId.ToString()`, un GUID canónico. `ai-service/tests/support/settings.py` define
`TOKEN_POS_ID = "POS-B"`. Hoy da igual, porque el claim se transporta y se devuelve en
`effective_pos_id` sin tocar SQL. **El día que se parsee como UUID se cae la batería de retrieval
que usa el token por defecto.** Y hay que decidir qué hacer con un `pos_id` que no parsea: el
módulo de auth ya dejó escrito el criterio —*«a wildcard `pos_id` is exactly what must never
exist, because from the soft-prefilter change onward that claim is the retriever's only hard
filter»*—, así que **se rechaza, nunca se desescopa en silencio**.

### 7.4 Una proyección vacía produce una abstención indistinguible de la legítima

Con el filtro duro en SQL y la proyección sin sincronizar, todas las consultas devuelven cero con
`200 OK` y `low_confidence: true`, y el panel de C16 pinta su pantalla de «no hemos encontrado
nada» sobre un fallo de dependencia. El código ya resuelve el caso análogo para los embeddings, y
con estas palabras: *«refusing to abstain over an empty or foreign index»*.

---

## 8. Decisiones tomadas con estas mediciones

| # | Decisión | Apoyo |
|---|---|---|
| 1 | **Filtro duro = `is_assigned_hint`**, replicando `Carried()`. Tombstone aplicado como **borrado suave** (`is_assigned_hint = false`, `qty_bucket = '0'`), que conserva la historia para C26 y hace el estado observable. El test se renombra a `test_out_of_stock_product_is_penalised_not_removed`, que es el que protege el principio de verdad | §2 |
| 2 | **CTE de alcance + KNN exacto** sobre el subconjunto del POS, en lugar de confiar en el planificador con HNSW. No es cambio de motor: es lo que Postgres ya elegía, y escopado va más rápido | §3 |
| 3 | El stock **penaliza por bloque dentro de `demotion_rank`**, clave única de ordenación, en último lugar de prioridad. Binario (`qty_bucket = '0'` frente al resto); los tres niveles se almacenan y los calibra C25 | §2 |
| 4 | Sincronización por **CLI** (`python -m jbg_ai.indexing sync-pos`) más cron documentado. Sin ruta HTTP nueva, sin planificador en proceso. La honestidad la aporta `projection_age_seconds`, no un cron oculto | — |
| 5 | **`projection_age_seconds` como campo opcional de `RetrievalResponse`**, regenerando `openapi.json`. Su origen es `ai.sync_checkpoint.last_incremental_sync_at`, **nunca** `max(refreshed_at)`: con un feed incremental por keyset, una asignación que no cambia jamás se reescribe, así que `refreshed_at` mide «cuándo cambió esto», no «cuándo miramos» | §1 |
| 6 | El campo **gobierna comportamiento**, no decora: proyección vacía → 503; proyección más vieja que el techo configurado → se desactiva el filtro duro para esa petición y se declara; fresca → filtro aplicado | §7.4 |
| 7 | El golden set de C24 se etiqueta y se mide **sin escopar**; el efecto de C22 se reporta aparte como **tasa de llenado por POS** | §4 |
| 8 | **El reloj inyectado entra en este change** (no choca de zona): constante configurada y declarada **`2026-08-23T23:59:59Z`** —el horizonte del mundo de C10— en lugar de `max(SaleDate)`, que hoy sería 2026-08-29, está contaminado por las 7 ventas de prueba de C16 y derivaría cada vez que se grabe una venta en la demo. **Arreglo mínimo:** con el reloj fijo, `sales_30d` vuelve a valer 16,28 % de pares no nulos de forma estable y C25 no necesita rediseñar su señal | §5, §6 |
| 9 | Antes de grabar el vídeo se **desplazarán las fechas** del mundo, para que dashboards, devoluciones e informe de movimientos no aparezcan muertos. Es una operación de demo, ajena a las métricas del RAG, y se declara | §6 |

**Consecuencia de alcance de la decisión 8:** C22 deja de ser un change sólo de Python. Su zona
pasa a ser `ai-service/src/jbg_ai/retrieval/`, `ai-service/src/jbg_ai/indexing/` **y** un cambio
quirúrgico en `IndexFeedRepository` / `IndexFeedService` / configuración. Sigue sin migración, ni
de EF Core ni de Alembic.

### Por qué el reloj inyectado no es un parche

El §0 del plan lo prescribió al anular C19 —*«necesita primero decidir el reloj (`asOf` inyectado
y `computedAsOf` declarado en la respuesta, como `projection_age_seconds` en C22)»*— y lo dejó
anotado para una rama muerta, sin ver que aplicaba igual a la rama viva. Hay un segundo motivo,
independiente del mundo que caduca:

> C24 exige `test_run_is_reproducible_for_same_config_and_seed`, y el §16 del diseño pide
> **«tabla de ablations v0→v3 reproducible con un comando»**. Si el ranking lee `now()`, la misma
> configuración con la misma semilla da resultados distintos según el día. **La tabla no es
> reproducible, y no lo es por diseño.** El reloj inyectado es un requisito que el proyecto ya se
> había comprometido a cumplir; el horizonte fijo del mundo sólo lo hace urgente.

### Qué se habría caído del PF sin esto, y qué no

**No se cae C22.** `qty_bucket` e `is_assigned_hint` son **fotos, no ventanas**: no caducan.

| Pieza | ¿Afectada? | Motivo |
|---|---|---|
| **C25** `add-business-signals-ranking` | 🔴 de lleno | su señal es `sales_30d`; está en la lista de *nunca se recorta* |
| **§11.2, fila `v3-señales`** | 🔴 sí | «disponibilidad + rotación + perfil de POS»: el perfil cayó con C33, la rotación caería ahora → quedaría `v2 + stock` |
| **§16, ablations reproducibles** | 🔴 sí | ver arriba |
| C33 *(anulado, «el único rescatable»)* | 🟠 si se rescata | usa `sales_30d` y `lastSaleAt` |
| C24 golden set | 🟢 no | no toca ventas |
| C26 sustitutos | 🟢 no | stock actual, no ventana |
| **C27 complementarios** | 🟢 no | `ai.co_occurrence` se deriva del **histórico completo** (4.075 pares) |
| C30 avisos («stock crítico») | 🟢 no | stock actual |
| C32 · siete tools | 🟢 no | ninguna con ventana; `perfil_punto_venta` ya está retirada |
| C38 | 🟢 no | — |

**El daño no habría sido una funcionalidad ausente, sino un falso negativo medido.** Con
`sales_30d` idénticamente cero en los 6.050 pares, el barrido de pesos de C25 encontraría que el
peso óptimo de la rotación es 0, y la tabla de ablations diría que las señales de negocio no
mejoran el ranking. Una casilla vacía se declara; un número falso se cita.

---

## 9. Qué queda pendiente de medir

- **Tasa de llenado real por POS, antes y después, con consultas de operador** y no con sondas de
  auto-similitud. La línea base «antes» se computa con lo que C04 ya persiste —`% de búsquedas con
  ResultsCount < página` agrupado por `PointOfSaleId`— y distinguir abstención de sin-surtido se
  resuelve uniendo por `TraceId` con el log `stage=search`.
- **Latencia del pipeline completo escopado**, en frío y en caliente, contra el proveedor real.
  Aquí se midió el coste de la sentencia SQL (7,3 ms), no el de la petición.
- **Población de tombstones `unassigned` que llegan por el feed en una sincronización real.** La
  §2 mide el estado, no el flujo: cuántas transiciones a inactivo caen dentro de una ventana de
  cursor es otra cosa, y es lo que ejercita de verdad el borrado suave.
- **Deriva entre `ai.pos_projection` y el `aggregateHash` del feed de POS** tras la primera
  sincronización completa, que es para lo que ese hash existe.
- Si el bucle anidado dirigido por el alcance mejora los 7,3 ms lo suficiente para justificar
  escribir la consulta de otra forma (§3, nota de implementación).
- **Cobertura de `sales_30d` por punto de venta** con el reloj ya fijado: el 16,28 % es global, y
  un POS pequeño como FORNELLS puede quedarse sin señal aunque el agregado la tenga.
