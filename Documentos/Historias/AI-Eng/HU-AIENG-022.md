# HU-AIENG-022: Prefiltro blando por punto de venta — la proyección pondera, el surtido acota y el reloj deja de derivar

## Formato estándar

**Como** Operador de un punto de venta de la joyería,
**quiero** que la búsqueda asistida me devuelva una página llena de productos que **puedo vender aquí**, en lugar de una lista recortada de candidatos del catálogo entero,
**para** dejar de ver pantallas con uno o dos resultados —o ninguno— cuando mi tienda sí tiene surtido que ofrecer al cliente que tengo delante.

---

## Descripción

Hoy la recuperación trabaja sobre el catálogo completo y **.NET recorta después**. El retriever produce 60 candidatos ordenados por relevancia global, y `AssistedSearchRepository.Carried()` descarta todo lo que no tenga inventario activo en ese punto de venta. El resultado es aritmético: cuanto más pequeño es el surtido, más vacía llega la página.

**El valor de operador es directo y está medido.** Sobre 20 consultas sonda contra el índice real, con los parámetros vivos (umbral 0,65, ventana de 60):

| POS | supervivientes de 60 (media) | peor caso | **consultas por debajo de una página de 10** |
|---|---:|---:|---:|
| FORNELLS | **10,5** | **1** | **12 de 20** |
| PORT-MAO | 20,1 | 3 | 8 de 20 |
| MAO-AIR | 24,7 | 2 | 7 de 19 **+ 1 página vacía** |
| HT-GALDANA | 27,0 | 1 | 6 de 20 |
| CIU-CENTRE | 43,5 | 23 | 0 |

**No era un problema de FORNELLS: lo tienen ocho de los once puntos de venta.** Y una de las veinte consultas de MAO-AIR no deja **ningún** superviviente — una página completamente vacía que el panel de C16 pinta con su pantalla de «no hemos encontrado nada», indistinguible de una abstención legítima del modelo.

Esta historia mueve el alcance del punto de venta **dentro de la consulta de recuperación**, que es lo que el §7.6 del diseño pide y el apunte de S10 formula como *«lo barato y excluyente, al principio; lo blando, al cierre»*. Y respeta la promesa que le da nombre: **la proyección pondera y nunca excluye** — lo que excluye es el surtido, que es el mismo predicado que la autoridad ya aplica.

### Lo que la exploración del 2026-09-05 midió, y que reencuadra la ficha

Mediciones completas en [c22-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c22-exploration-measurements.md).

**1. El filtro duro correcto es `is_assigned_hint`, no la mera existencia de fila.** La ficha pide que un producto desasignado *«se penalice y no se elimine»*. Pero el predicado de la autoridad es literal —`Carried()` filtra `Inventory.IsActive`—, así que un desasignado que sobreviviera en Python sería descartado por .NET de todas formas: sólo gastaría ventana. Y no son cuatro: **los desasignados son el 6,9 % en CIU-CENTRE, el 8,7 % en FORNELLS y el 8,8 % en MAO-AIR**, 670 filas de 6.720 en total.

**2. Lo que de verdad hay que penalizar sin eliminar es el stock, y ahí la ficha acierta de pleno.** `Carried()` **no filtra por cantidad**: un producto a cero llega hoy al operador marcado con `HasStock: false`. Y la señal es gruesa: **MAO-AIR tiene 143 de sus 416 productos asignados a stock cero, el 34,4 %**; HT-GALDANA el 11,7 %, FORNELLS el 12,0 %. El test de la ficha se renombra en consecuencia.

**3. `is_assigned_hint` es hoy una constante `true` y el feed no puede producir otro valor.** `IndexFeedService.MapPosItem` devuelve tombstone si `!row.IsActive` y, en la rama de upsert, fija `IsAssignedHint = true` literalmente. La spec viva lo corrobora: *«Active `Inventory` rows in the cursor window MUST be upserts»* más *«`isAssignedHint` MUST reflect `Inventory.IsActive`»*. Por eso el tombstone `unassigned` se aplica como **borrado suave** y no como `DELETE`: es lo único que hace el campo alcanzable, conserva la historia que C26 necesitará para decir «esto no lo llevas aquí, pero mira lo que sí», y hace el estado observable.

**4. El índice HNSW no se ha usado nunca, y forzarlo es peor.** Cuatro planes medidos con el vector de consulta como literal:

| Consulta | Plan elegido | Tiempo | Filas |
|---|---|---:|---:|
| Sin escopar, forma canónica | **Seq Scan** + top-N | 8,2 ms | 60 |
| Sin escopar, forma viva de C14 | **Seq Scan** + top-N | 10,8 ms | 60 |
| Sin escopar, **HNSW forzado** | Index Scan HNSW | **113,7 ms** | **40** |
| **Escopado a FORNELLS** (239 docs) | Hash Join + Seq Scan + top-N | **7,3 ms** | 60 |

Desde C14 el planificador elige escaneo secuencial exacto, porque a 1.168 filas le sale más barato. Así que **escopar con un CTE y calcular la distancia exacta sobre el subconjunto no cambia de motor: hace explícito lo que la base de datos ya venía haciendo**, y encima acelera. Forzar el índice cuesta 13× y devuelve **40 de las 60 filas pedidas**, que es `ef_search = 40` recortando: la trampa de post-filtrado que describe S10 —*«el índice puede devolver sus 50 vecinos más cercanos, el filtro descartar 48, y la consulta entregar 2 resultados sin ningún error visible»*— es real y reproducible aquí, sólo que no está en el camino vivo.

> **Se refuta una hipótesis de la propia exploración.** Se conjeturó que las mediciones planas de profundidad de C21 (40 → 113/120, 60 → 111, 100 → 107) podían ser `ef_search` recortando. Es falso: la rama vectorial nunca tocó el índice. Aquellos números son comportamiento genuino de RRF.

**5. La frescura no puede salir de `refreshed_at`.** El feed es **incremental por keyset**: una asignación que no cambia jamás vuelve a emitirse, así que su `refreshed_at` se queda en el instante en que cambió por última vez. `max(now − refreshed_at)` reportaría meses de antigüedad sobre una proyección sincronizada hace treinta segundos. La frescura sale de `ai.sync_checkpoint.last_incremental_sync_at` con `feed = 'pos-availability'`, que mide *cuándo miramos* y no *cuándo cambió esto*.

**6. Las ventanas de venta se están vaciando, y hay fecha.** El mundo de C10 tiene horizonte fijo: última venta real **2026-08-23**, más 7 ventas sueltas del 2026-08-29 que son las pruebas manuales de C16. Los agregados se calculan contra el **reloj de pared**, así que sobre los 6.050 pares activos:

| `as_of` | `sales_30d` ≠ 0 | `sales_90d` ≠ 0 |
|---|---:|---:|
| **2026-09-05 (hoy)** | 985 (**16,28 %**) | 2.533 (41,87 %) |
| 2026-09-22 | 80 (**1,32 %**) | 2.239 (37,01 %) |
| 2026-10-10 | **0 (0,00 %)** | 1.839 (30,40 %) |

`sales_30d` **es cero para todo el catálogo a partir del 26 de septiembre**. Si C25 barre pesos sobre una señal idénticamente nula, encontrará que el peso óptimo de la rotación es 0 y la tabla de ablations dirá que las señales de negocio no mejoran el ranking. Eso no es una casilla vacía —que se declara—: es **un número falso, que se cita**. Por eso el reloj inyectado entra en esta historia.

**7. Y el reloj inyectado no es un parche.** C24 exige `test_run_is_reproducible_for_same_config_and_seed`, y el §16 del diseño pide *«tabla de ablations v0→v3 reproducible con un comando»*. Si el ranking lee `now()`, la misma configuración con la misma semilla da resultados distintos según el día: **la tabla no es reproducible, y no lo es por diseño**. El horizonte fijo del mundo sólo hace urgente un defecto que ya estaba ahí.

### Alcance de esta historia (sí)

- **Sincronización de `ai.pos_projection`** desde `GET /api/ai/index-feed/pos-availability`, que C12 dejó especificado y servido y C13 dejó sin consumir. Cliente tipado sobre el `fetch_pos_page` que ya existe, cursor keyset propio en `ai.sync_checkpoint` con `feed = 'pos-availability'`, y **CLI** `python -m jbg_ai.indexing sync-pos` con cron documentado.
- **Tombstone `unassigned` como borrado suave**: la fila se conserva con `is_assigned_hint = false` y `qty_bucket = '0'`.
- **Alcance por punto de venta como único filtro duro**, tomado del claim `pos_id` del token y aplicado en SQL **en las tres ramas** —la tecleada, la expandida y la vectorial— mediante CTE de alcance más distancia exacta sobre el subconjunto.
- **`qty_bucket = '0'` degrada y nunca elimina**, como bloque adicional de `demotion_rank`, en clave única de ordenación y en última prioridad.
- **`projection_age_seconds` en la respuesta**, con origen en el checkpoint, y **gobernando comportamiento**: proyección vacía → 503; proyección más vieja que el techo configurado → se desactiva el filtro duro y se declara; fresca → se aplica.
- **Reloj inyectado** `IndexFeed:SalesAsOf`, constante configurada y declarada `2026-08-23T23:59:59Z`, más `computedAsOf` en la página del feed, persistido en la proyección y declarado.
- **Flag de ablación** con default en `Settings` y valor por parámetro del orquestador, como C20 y C21, para que C24 barra configuraciones sin reiniciar y sin mover el contrato.
- **Informe versionado** con la tasa de llenado por punto de venta, antes y después.

### Fuera de alcance (no)

- **Señales de negocio en el ranking** — `sales_30d`, `sales_90d` y `last_sale_at` se **almacenan** y no se leen: es **C25**, que además calibra los pesos contra el golden set.
- **Sustitutos** (C26) y **complementarios** (C27), aunque el borrado suave exista precisamente para que C26 pueda distinguir «nunca lo llevaste» de «lo llevabas».
- **Planificador en proceso**: sin tarea de fondo, sin APScheduler. CLI y cron documentado. En producción hará falta otra cosa; para la demo, no.
- **Ruta HTTP nueva de sincronización**: nada de `POST /v1/index/sync-pos`. La spec viva `ai-service-api-contracts` **enumera los endpoints en un MUST**, y añadir uno es un cambio normativo que esta historia no compra.
- **Recalibración del umbral de distancia por cuantil**, que C21 dejó anotada para C25.
- **Revertir `AiGateway:RetrievalTimeoutMs` a 800 ms**: sigue siendo un change propio, con su medición en el entorno de demostración (`DEFERRED_TASKS.md`).
- **Índice HNSW parcial por punto de venta** y `hnsw.iterative_scan`: la medición dice que a 1.168 filas no hacen falta. Se declaran como techo de escalado en el README.
- **Migración de ninguna clase**: ni Alembic ni EF Core. `ai.pos_projection` y `ai.sync_checkpoint` existen desde C05 y C13, y el checkpoint ya tiene `feed` como clave primaria.
- **Arreglar los otros tres relojes del repositorio** —informe de movimientos, ventana de devolución y dashboards—. Están inventariados en el informe y el desplazamiento de fechas previo a la grabación del vídeo es una operación de demo, ajena a las métricas.

### Decisiones de diseño ya acordadas

| # | Decisión | Motivo |
|---|---|---|
| 1 | Filtro duro = **`is_assigned_hint`**, replicando `Carried()`. Tombstone como **borrado suave** | Excluir lo que la autoridad excluye no cuesta nada; el 7-9 % de desasignados sí gastaría ventana. El borrado suave hace el campo alcanzable y conserva la historia para C26 |
| 2 | **CTE de alcance + KNN exacto** sobre el subconjunto, en las tres ramas | No es cambio de motor: es lo que Postgres ya elegía. Forzar HNSW cuesta 13× y trunca a 40 de 60 |
| 3 | `qty_bucket = '0'` como **bloque adicional de `demotion_rank`**, clave única, **binario** y en última prioridad | Un solo `sorted` estable con prioridad explícita. Binario porque ordenar entre `1-2` y `3+` sería un número mágico sin evidencia; los tres niveles se almacenan y los calibra C25 |
| 4 | Sincronización por **CLI** más cron documentado | La honestidad la aporta `projection_age_seconds`, no un cron oculto. Sin ruta nueva, sin planificador, sin mover `ai-service-api-contracts` |
| 5 | **`projection_age_seconds`** opcional en `RetrievalResponse`, regenerando `openapi.json`. Origen: `ai.sync_checkpoint.last_incremental_sync_at`, **nunca** `max(refreshed_at)` | Con un feed incremental, `refreshed_at` mide cuándo cambió la asignación, no cuándo miramos |
| 6 | El campo **gobierna comportamiento**: vacía → 503; vieja → filtro duro desactivado y declarado; fresca → aplicado | Un campo sin consumidor sería el patrón del cable puesto y sin conectar que C21 criticó. Y cierra la abstención falsa sobre proyección vacía |
| 7 | **`pos_id` que no parsea como UUID se rechaza**, nunca se desescopa en silencio | El módulo de auth ya lo dejó escrito: *«a wildcard `pos_id` is exactly what must never exist»* |
| 8 | **Reloj inyectado dentro de este change**: `IndexFeed:SalesAsOf = 2026-08-23T23:59:59Z`, constante configurada y declarada; `computedAsOf` en la página | Arreglo mínimo: `sales_30d` recupera su 16,28 % de forma estable y C25 no rediseña su señal. Y es un requisito de reproducibilidad que C24 ya imponía |
| 9 | Golden set de C24 **sin escopar**; el efecto de C22 se reporta como **tasa de llenado por POS** | Dos números que responden dos preguntas, en vez de uno que mezcla recuperación con surtido |

**Cortes que no se reabren:** `indexing/embeddings.py` sigue congelado desde C11 · `enrichment/vocabularies.yaml` no se modifica · Python no lee el esquema `public` por SQL · sin migración de ninguna clase · sin `ai.query_log` · sin tocar `frontend/` · sin ruta HTTP nueva.

**Referencias:**

- Diseño RAG [§6.2, §6.3, §7.2 y §7.6](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — frontera de responsabilidad, contrato de sincronización, esquema del índice y prefiltro blando.
- Plan de changes, [ficha C22](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) y decisión 11 de la revisión.
- Mediciones: [c22-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c22-exploration-measurements.md).
- Specs vivas afectadas: `openspec/specs/vector-retrieval/`, `openspec/specs/product-document-indexer/`, `openspec/specs/index-feed/`, `openspec/specs/hybrid-fusion/`.
- Historias previas: [HU-AIENG-012](HU-AIENG-012.md) (feed de POS), [HU-AIENG-013](HU-AIENG-013.md) (indexador de catálogo), [HU-AIENG-014](HU-AIENG-014.md) (retriever vectorial), [HU-AIENG-015](HU-AIENG-015.md) (hidratación autoritativa), [HU-AIENG-021](HU-AIENG-021.md) (fusión híbrida).
- Apuntes: [S10 · Filtrado contextual y temporal](../../Sesiones%20Master%20AIEng/S10_Tecnicas_Recuperacion/Filtrado%20contextual%20y%20temporal.md), [S8 · Anatomía de un índice vectorial](../../Sesiones%20Master%20AIEng/S8_BBDD_Vectoriales/Anatomia%20de%20un%20Indice%20Vectorial%20HNSW,%20IVFFlat%20y%20el%20horizonte%20DiskANN.md).
- Change: [`add-pos-projection-soft-prefilter`](../../../openspec/changes/add-pos-projection-soft-prefilter/) · ticket [T-AIENG-022](../../../openspec/changes/add-pos-projection-soft-prefilter/ticket.md).

---

## Criterios de Aceptación

### Escenario 1: La página se llena con lo que el operador puede vender

**Dado que** el operador atiende en un punto de venta con surtido reducido, como FORNELLS con 239 de los 1.168 documentos indexados
**Y** que hoy 12 de cada 20 búsquedas le devuelven menos productos de los que caben en la página
**Cuando** busca cualquier consulta ordinaria en modo híbrido
**Entonces** los candidatos que produce el retriever pertenecen todos al surtido de su punto de venta
**Y** la ventana de sobre-recuperación se llena con productos que la hidratación de .NET no va a descartar
**Y** la página que ve tiene el tamaño que pidió, salvo que su punto de venta realmente no tenga tantos productos que casen

### Escenario 2: Un producto sin stock se ve, pero se ve el último

**Dado que** el punto de venta tiene productos asignados con cantidad cero — 143 de 416 en MAO-AIR
**Y** que la hidratación de .NET **no** los descarta: los devuelve marcados como sin existencias
**Cuando** el operador busca algo que casa tanto con productos con stock como sin él
**Entonces** los productos sin stock **siguen apareciendo** en los resultados
**Y** quedan ordenados por detrás de los equivalentes con existencias
**Y** una restricción que el operador escribió en el texto —un techo de precio, una talla— sigue mandando por delante de la señal de stock, porque el stock no se lo preguntó nadie
**Y** en ningún caso la cantidad exacta viaja en la respuesta del retriever: sólo el tramo

### Escenario 3: Un producto retirado del surtido deja de ofrecerse, y la proyección lo recuerda

**Dado que** una asignación de inventario se desactiva en .NET y el feed la emite como tombstone `unassigned`
**Cuando** se sincroniza la proyección
**Entonces** la fila **no se borra**: se conserva marcada como no asignada y con el tramo de existencias a cero
**Y** ese producto deja de aparecer en las búsquedas de ese punto de venta, que es exactamente lo que la hidratación de .NET haría con él
**Y** la fila conservada permite más adelante distinguir «nunca se llevó aquí» de «se dejó de llevar»

### Escenario 4: Una proyección que nunca se ha sincronizado no se disfraza de abstención

**Dado que** `ai.pos_projection` está vacía, o no tiene ninguna fila para el punto de venta del token
**Cuando** el operador busca
**Entonces** la respuesta es un error de dependencia y **no** un 200 con la lista vacía
**Y** el detalle nombra la causa, en lugar de dejar que el panel pinte «no hemos encontrado nada» sobre un fallo de sincronización
**Y** `GET /health` sigue respondiendo correctamente

### Escenario 5: Una proyección vieja degrada y lo dice, en lugar de esconder productos

**Dado que** la proyección se sincroniza periódicamente y puede quedarse atrás
**Y** que un producto recién asignado que la proyección no conoce quedaría invisible si se filtrase con ella
**Cuando** la antigüedad de la sincronización supera el techo configurado
**Entonces** el alcance por punto de venta **deja de aplicarse como filtro duro** en esa petición
**Y** la respuesta declara la antigüedad de la proyección, de modo que la degradación es visible y no silenciosa
**Y** la página puede quedar corta, pero ningún producto válido desaparece antes de que .NET lo vea
**Cuando** la sincronización es reciente
**Entonces** el alcance se aplica con normalidad y la antigüedad se declara igualmente

### Escenario 6: La frescura mide cuándo miramos, no cuándo cambió el inventario

**Dado que** el feed de disponibilidad es incremental y sólo emite las asignaciones que cambiaron
**Y** que una asignación estable puede llevar meses sin reescribirse
**Cuando** la respuesta declara la antigüedad de la proyección
**Entonces** ese número procede del instante de la última sincronización del feed de disponibilidad
**Y** **no** del instante en que se escribió por última vez alguna de las filas devueltas
**Y** una proyección recién sincronizada declara una antigüedad de segundos aunque sus filas lleven meses sin cambiar

### Escenario 7: Un token sin punto de venta utilizable no abre una búsqueda global

**Dado que** el alcance por punto de venta es el único filtro duro del retriever
**Y** que un alcance comodín es precisamente lo que nunca debe existir
**Cuando** llega una petición de recuperación cuyo `pos_id` no es un identificador válido
**Entonces** la petición se rechaza
**Y** **no** se sirve una búsqueda sobre el catálogo entero
**Y** el punto de venta que la respuesta declara sigue siendo el del token y nunca el del cuerpo de la petición

### Escenario 8: Las ventanas de venta se cuentan contra un instante declarado

**Dado que** el histórico de ventas del mundo sintético termina en una fecha fija
**Y** que contarlas contra el reloj de pared las vacía por completo antes de un mes
**Cuando** el feed de disponibilidad calcula los agregados de venta
**Entonces** las ventanas se cuentan contra el instante de referencia configurado y no contra la hora actual
**Y** ese instante viaja en la página del feed, se persiste en la proyección y queda declarado
**Y** la misma configuración con la misma semilla produce el mismo resultado ejecutada en días distintos
**Y** cuando no se configura ningún instante, el comportamiento es el de hoy: el reloj de pared

### Escenario 9: El prefiltro se puede apagar para poder medirlo

**Dado que** C24 tiene que medir por ablación qué aporta el alcance por punto de venta
**Cuando** se desactiva el prefiltro por configuración
**Entonces** la recuperación se comporta exactamente como antes de esta historia
**Y** el valor efectivo viaja como parámetro de la llamada de orquestación, de modo que se pueden barrer configuraciones sin reiniciar el proceso
**Y** el esquema de la petición congelado **no** se mueve para conseguirlo

### Escenario 10: Fuera de alcance explícito

**Dado que** esta historia entrega el prefiltro y la sincronización de la proyección
**Cuando** se revisa el entregable
**Entonces** las señales de venta se **almacenan** y **no** se leen para ordenar: eso es C25
**Y** **no** hay sustitutos, ni complementarios, ni corpus de conocimiento, ni golden set
**Y** **no** existe planificador en proceso ni ruta HTTP nueva de sincronización
**Y** **no** hay índice HNSW parcial ni escaneo iterativo
**Y** `indexing/embeddings.py`, `enrichment/vocabularies.yaml` y el árbol `frontend/` no tienen diff
**Y** no hay revisión de Alembic nueva ni migración de EF Core
**Y** `AiGateway:RetrievalTimeoutMs` sigue en 2500 ms

---

## Notas adicionales

- **Actor:** el **Operador**, por segunda vez consecutiva tras C21. La diferencia es que C21 mejoró *qué* se encuentra y C22 mejora *cuánto llega a la pantalla*: es la mitad de la calidad percibida que ninguna medida de relevancia captura.

- **Décima vez que la zona de una ficha se queda corta, y esta vez cruza de lenguaje.** La ficha declara zona `ai-service/src/jbg_ai/retrieval/` e `indexing/`. Con la decisión 8 se suman `backend/src/JoiabagurPV.Application` (opción `SalesAsOf`, `IndexFeedService`, DTO del feed) y `backend/src/JoiabagurPV.Infrastructure` (`IndexFeedRepository`). Van tras C08, C07, C15, C16, C17, C18b, C20 y C21.

- **El punto de inyección del reloj es de una línea, y ya estaba preparado.** `IIndexFeedRepository.GetSalesAggregatesAsync(pairs, now, ct)` **recibe `now` como parámetro** desde C12, y `IndexFeedService.LoadSalesAsync` lo alimenta con `_timeProvider.GetUtcNow().UtcDateTime`. El cambio es leer la opción cuando está configurada. No hay que refactorizar nada.

- **La página corta no desaparece: deja de ser el caso normal y pasa a ser honesta.** Con un umbral estrecho (0,35), que representa una consulta discriminante, FORNELLS escopado tiene una media de 65,6 candidatos y un **peor caso de 18**. Sigue llenando una página de 10 en las veinte consultas, pero la holgura real es esa. Cuando la página quede corta será porque el punto de venta no tiene surtido, no porque el ranking mirase a otro sitio — y ese es el mensaje que el aviso de C16 ya sabe dar.

- **El aviso de interfaz que consume la frescura no entra aquí.** «El surtido de este punto de venta se sincronizó hace N minutos» vive en `AssistedSearchService` y en el panel, que son las zonas de C34 y C36; la regla del §5 del plan prohíbe abrirlas a la vez que C15 y C16. Dentro de esta historia el campo ya tiene consumidor propio: **gobierna el comportamiento del retriever** (decisión 6).

- **`TOKEN_POS_ID` vale `"POS-B"` en los tests y en producción el claim es un GUID.** `AiServiceTokenFactory` firma `pointOfSaleId.ToString()`. Mientras el claim no tocaba SQL daba igual; en cuanto se parsee como UUID, la batería de recuperación que usa el token por defecto se cae entera. Es trabajo previsto, no un imprevisto.

- **La medición del llenado se hizo con sondas de auto-similitud**, no con consultas de operador contra el proveedor real. Eso evita el problema de TLS interceptado y hace las cifras reproducibles sin credenciales, pero la verificación de cierre debe repetirse con consultas reales, y la línea base «antes» se computa con lo que C04 ya persiste: `% de búsquedas con ResultsCount < página` agrupado por `PointOfSaleId`.

- **Limitación a declarar en el README**, hermana de las de C20, C21 y C24: el mundo sintético tiene horizonte fijo, las ventanas de venta se computan contra un instante de referencia declarado y no contra el reloj de pared, y las métricas de rotación describen el mundo **en su horizonte**, no «hoy».

- **`design.md` obligatorio** en el change. Hay al menos seis decisiones con alternativa real y coste asimétrico —semántica del filtro duro, tratamiento del tombstone, forma de la consulta escopada, dónde y cómo penaliza el stock, origen de la frescura, y el reloj inyectado—, y **tres de ellas contradicen la ficha original**.

- **Verificación posterior (no DoD de merge):** ejecutar la sincronización completa contra el feed real, comprobar la deriva entre `ai.pos_projection` y el `aggregateHash` del feed de POS, y repetir la medición de llenado con consultas de operador para confirmar las cifras del informe.

---

## Tareas

1. Completar artefactos OpenSpec del change `add-pos-projection-soft-prefilter`: `proposal`, **`design.md` obligatorio**, `specs` (capacidad nueva `pos-projection` más **tres deltas MODIFIED**: `vector-retrieval`, `product-document-indexer` e `index-feed`) y `tasks`.
2. **.NET — reloj inyectado:** `SalesAsOf` en `IndexFeedOptions`, consumo en `IndexFeedService.LoadSalesAsync`, `computedAsOf` en el DTO de página del feed de disponibilidad, y validación de arranque.
3. **Python — cliente tipado del feed de POS:** dataclasses de upsert y tombstone y `parse_pos_item`, sobre el `fetch_pos_page` que ya existe.
4. **Python — repositorio de `ai.pos_projection`:** upsert idempotente por `(pos_id, product_id)` y borrado suave del tombstone, sin tocar el esquema `public`.
5. **Python — orquestación de la sincronización** con cursor keyset propio en `ai.sync_checkpoint` (`feed = 'pos-availability'`), contadores y registro de fallos.
6. **Python — CLI** `python -m jbg_ai.indexing sync-pos`, con `--full`, y receta de cron documentada en el README de `ai-service`.
7. **Python — alcance en el puerto de búsqueda:** CTE de alcance más distancia exacta sobre el subconjunto, aplicado en las tres ramas; `pos_id` parseado desde el principal y rechazo si no es UUID.
8. **Python — bloque de stock en `demotion_rank`**, en clave única y última prioridad, sin romper la ordenación estable existente.
9. **Python — frescura y guardias:** lectura cacheada del checkpoint, `projection_age_seconds` en `RetrievalResponse`, 503 sobre proyección vacía y degradación declarada sobre proyección vieja.
10. **Python — settings nuevos** (flag de ablación, techo de antigüedad) con default en `Settings`, parámetro en la firma del orquestador, pin en `canonical_openapi_settings` y fila en la tabla de entorno del README.
11. **Regenerar `ai-service/openapi.json`** y actualizar el snapshot de `test_openapi_snapshot_is_stable`.
12. **Logs** `stage=projection` y ampliación de `stage=search` con la cardinalidad escopada, con `trace_id`.
13. **Arreglar `TOKEN_POS_ID`** en `ai-service/tests/support/settings.py` y la batería que dependa de él.
14. **Tests** *offline* en `ai-service/tests/indexing/` y `ai-service/tests/retrieval/`, y de integración en `backend/src/JoiabagurPV.Tests` para el reloj inyectado.
15. **Informe versionado** con la tasa de llenado por punto de venta, antes y después, que C24 reutilice.
16. Enlazar la HU en [`Documentos/epicas.md`](../../epicas.md) (EP14) **en el apply**.
17. `openspec validate --all --strict` en `0 failed` antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** **5** — ocho de los once puntos de venta tienen hoy al menos 6 de cada 20 búsquedas por debajo de una página, con un peor caso de un solo producto y una página completamente vacía. Es la mitad de la calidad percibida que ninguna métrica de relevancia captura.
- **Urgencia (mercado / feedback):** **5** — desbloquea C25 y C26, y **arrastra una fecha dura**: `sales_30d` es cero para todo el catálogo a partir del 26 de septiembre de 2026.
- **Complejidad / esfuerzo:** **4** — una sincronización nueva con su cursor y su CLI, un alcance en tres sentencias SQL, un bloque de degradación, dos guardias de dependencia, un movimiento de contrato y un cambio quirúrgico en .NET. Sin migración, pero con **seis decisiones** que hay que dejar escritas y **tres specs vivas que quedan falsas si no se emiten sus deltas**.
- **Riesgos y dependencias:**
  - **Tres specs vivas contradicen literalmente lo que este change hace** —`vector-retrieval` («the search SQL does not filter by `pos_id`»), `product-document-indexer` («MUST NOT … write `ai.pos_projection`») e `index-feed` («over the last 30 and 90 days»)—. Sin sus deltas, `openspec validate --all --strict` **seguiría en verde** sobre specs falsas, que es el fallo de agosto en su versión peor: bien formado y mentiroso.
  - **La tentación de borrar la fila en el tombstone** «porque ya no está asignado»: deja `is_assigned_hint` inalcanzable para siempre y le quita a C26 la única forma de distinguir «nunca» de «ya no».
  - **La tentación de leer la frescura de `max(refreshed_at)`**: reportaría meses sobre una proyección sincronizada hace segundos, porque el feed es incremental.
  - **La tentación de confiar en el planificador con HNSW**: forzado devuelve 40 de 60 filas **sin error visible**, que es el modo de fallo que S10 advierte que es el más desconcertante de depurar.
  - **`TOKEN_POS_ID = "POS-B"`** rompe la batería de recuperación en cuanto el claim se parsee como UUID.
  - **Zona compartida con C21 (archivado) y C25**, los tres en `retrieval/`: no se abren en paralelo, aunque los abra la misma persona (regla del §1 del plan). Y con `indexing/`, que comparte con C23.
  - **`openapi.json` se mueve**, por primera vez desde C13. Es un acto deliberado y el test de snapshot existe para forzarlo, pero hay que regenerarlo con la receta del README y no a mano.
  - **El índice local poblado** (1.168 documentos y 6.720 filas de inventario): si se recrea el volumen, las mediciones de verificación no tienen contra qué medirse.
