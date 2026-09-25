# T-AIENG-041: Keep `ai.pos_projection` fresh by schedule, report its age before the search, and give the administrator a manual drain (C41)

> **Idioma.** Título e identificadores técnicos en inglés, cuerpo en español — la regla que ya siguen
> [T-AIENG-040](../archive/2026-09-25-add-frontend-free-query-panel/ticket.md) y el resto de tickets
> del Proyecto Final.
>
> **Fuentes de verdad:** `openspec/project.md` (convenciones 14 y 17), las specs vivas
> [`pos-projection`](../../specs/pos-projection/spec.md),
> [`vector-retrieval`](../../specs/vector-retrieval/spec.md),
> [`ai-free-query-search`](../../specs/ai-free-query-search/spec.md) y
> [`assisted-search-panel`](../../specs/assisted-search-panel/spec.md), y **el código real**, que es
> de donde sale todo lo que este ticket afirma.

**Change:** `add-pos-projection-scheduled-drain` (C41) · **Épica:** EP15
**Abierto:** 2026-09-25 · **Origen:** no es una historia de producto — sale de una **sesión de
pruebas manuales** posterior al cierre de C40, y eso condiciona cómo hay que leerlo.

---

## 0 · Qué pide este ticket, en una frase

Que **la frescura de `ai.pos_projection` deje de ser un acto manual**: un servicio en segundo plano
que la drene por horario, la edad reportada en la lectura previa que C40 ya publicó, y —sólo para el
administrador y sólo si sobra sitio— un drenaje manual desde la pantalla de administración.

---

## 1 · Contexto y problema

### Cómo se encontró, que importa para dimensionarlo

Al levantar el entorno para las pruebas manuales de C40, **ninguna de las once tiendas activas tenía
la proyección fresca**. El umbral es `JPV_POS_PROJECTION_MAX_AGE_SECONDS`, con defecto **3 600 s**, y
el *checkpoint* `ai.sync_checkpoint.last_incremental_sync_at` del feed `pos-availability` venía del
**5 de septiembre**: veinte días. Hubo que drenarlo a mano (`python -m jbg_ai.indexing sync-pos
--full`, 34 páginas, 6 050 *upserts*, 0 páginas fallidas) para que las pruebas midieran el sistema y
no su desconfiguración.

No es la primera vez. El §8 del [informe de C40](../../../Documentos/Proyecto%20Final%20AIEng/informes/c40-implementation-measurements.md)
declara exactamente la misma manipulación como una de las **cuatro del entorno**: *«La proyección del
punto de venta se refrescó. Llegaba con 19,7 días y el servicio la declaraba `degraded=unscoped`, con
lo que se habría medido otra cosa»*. **Dos sesiones distintas, la misma causa, el mismo arreglo a
mano.** Eso es lo que convierte un detalle de operaciones en un ticket.

### Lo que la rancidez hace, y lo que NO hace

Conviene fijarlo antes de proponer nada, porque la primera lectura de este problema es alarmista y
está equivocada — la sesión que abrió este ticket la hizo y tuvo que corregirse.

**No es una fuga.** Un operario **nunca** ve una pieza que su tienda no lleva, pase lo que pase con la
proyección. Hay dos filtros y sólo uno es la frontera:

| | Dónde | Qué hace | ¿Frontera? |
|---|---|---|---|
| Prefiltro de `ai.pos_projection` | `retrieval/projection.py`, antes de ordenar | Estrecha la **ventana de candidatos** al surtido de la tienda | **No** |
| `Carried()` | [`AssistedSearchRepository.cs:156-162`](../../../backend/src/JoiabagurPV.Infrastructure/Data/Repositories/AssistedSearchRepository.cs) | Parte de `Inventories` con `PointOfSaleId == pointOfSaleId && IsActive && Product.IsActive` | **Sí** |

La segunda corre en **toda** respuesta, y su consulta arranca desde `Inventory` precisamente para que
la regla de visibilidad sea **estructural** y no una condición que alguien pueda olvidar. Es la
convención 14 de `openspec/project.md`: *el servicio de IA propone candidatos; el backend pone la
verdad*.

**Lo que hace es que la página llegue corta.** Con la proyección rancia la ventana se dibuja sobre el
catálogo entero y .NET descarta después lo que la tienda no lleva. Eso es, literalmente, el
comportamiento de **antes de C22**, y C22 lo midió: **ocho de los once puntos de venta** caían por
debajo de una página en al menos **seis de cada veinte** búsquedas, y en el peor caso **sobrevivía un
solo producto**.

**Y degradar es la decisión correcta**, no un descuido. El *docstring* de
[`projection.py:139-142`](../../../ai-service/src/jbg_ai/retrieval/projection.py) lo escribe así:

> **Stale** — older than the ceiling. The scope is dropped for this request and the age is reported.
> The page may come back short; **no valid product is hidden from the authority that hydrates it**,
> which is the promise staleness has to keep.

Filtrar con una proyección de veinte días esconderría las piezas asignadas después del último
drenaje: un **falso negativo invisible**. Mostrar candidatos de más es recuperable porque .NET los
tira; esconder algo vendible no lo es. **Este ticket no toca esa decisión.**

### El problema real, entonces

**La frescura no tiene dueño.** No hay drenaje programado en ninguna parte: `sync-pos` es **sólo
CLI** y alguien tiene que acordarse. Mientras nadie se acuerda, el sistema funciona **correctamente y
peor**: sirve resultados válidos sobre una ventana mal dibujada, y **nada en pantalla lo dice**.

Eso último es lo que emparenta este ticket con C40. C40 existió porque `aiAvailable` viajaba *dentro*
de una respuesta y la única forma de saber que una vía estaba apagada era usarla. La edad de la
proyección está hoy en la misma situación: el servicio **la calcula y la reporta** en su línea de
etapa, y **no llega a ninguna pantalla**. Es un dato que el sistema conoce, paga y descarta en la
frontera — la misma infracción de completitud que el §11 de C40 persiguió cuatro veces.

---

## 2 · Lo que se pide, en tres tramos

### Tramo 1 · El drenaje programado (el núcleo, no se corta)

Un `BackgroundService` en la API de .NET que drene el feed de disponibilidad por horario, con el
patrón que el repositorio **ya tiene**: `ModelTrainingBackgroundService`
([`ServiceCollectionExtensions.cs`](../../../backend/src/JoiabagurPV.Application/Extensions/ServiceCollectionExtensions.cs)
lo registra).

Por qué en .NET y no en Python: el drenaje **consume** `GET /api/ai/index-feed/pos-availability`, que
es de .NET, y `jbg-ai` es quien lo llama hoy desde su CLI. Las dos ubicaciones son defendibles y la
decisión es del `design.md`. Lo que **no** es negociable:

- **Un lock, o no se construye.** `ai.sync_checkpoint` es **una fila por feed** (`PRIMARY KEY (feed)`),
  con `watermark` y `since_id`. Dos drenajes concurrentes escriben el keyset entrelazado, y un keyset
  corrupto **no falla: se salta filas en silencio**, que es peor que la rancidez que veníamos a
  arreglar. El lock protege del solape consigo mismo y de cualquier disparo manual del tramo 3.
- **Intervalo por configuración, con defecto por debajo del umbral.** El umbral son 3 600 s; un
  intervalo de 15–30 min deja margen para que un drenaje lento no cruce la línea.
- **Un fallo del drenaje no rompe nada.** La rancidez ya tiene comportamiento definido y correcto;
  el servicio que falla debe registrarlo y volver a intentarlo, nunca tumbar el arranque.
- **`failed_pages` no se puede tragar.** El CLI ya devuelve 1 cuando hay páginas fallidas, con su
  razón escrita: *«una página que falló es una página que nadie drenó; reportar éxito dejaría que una
  proyección parcialmente sincronizada pareciera completa»*. El servicio hereda esa lectura.

### Tramo 2 · La edad, dicha antes de buscar (aditivo y pequeño)

`GET /api/ai/search/availability` es el sitio natural: **ya existe**, lo creó C40 exactamente para
que se pueda saber qué se va a obtener **antes** de gastar, no llama a la IA y lleva
`[DisableRateLimiting]` a propósito. Gana un campo aditivo con la edad de la proyección de esa tienda
—o su ausencia— y la insignia de disponibilidad puede decir «resultados posiblemente incompletos»
cuando esté rancia.

Es **informar, no delegar**: el operario no tiene que arreglar nada, pero deja de interpretar una
página corta como que el buscador es malo. Nótese que `resolve_scope` ya calcula `reported_age` y
`stale`; el trabajo es transportarlos, no computarlos.

### Tramo 3 · El botón manual, **sólo administrador** y primer candidato a corte

Aquí está la petición original del usuario, y hay que ser exacto con lo que se puede y no se puede
construir:

**Para el administrador es viable** y tiene sentido: es el perfil que ya puede operar en ámbito
catálogo, es una persona y no un mostrador, y la pantalla de administración es donde se mira un dato
de sistema. Sería un drenaje **completo**, el mismo que se corrió a mano.

**Para el operario, limitado a su tienda, NO se puede hoy**, y no por una decisión de diseño sino por
la forma de las piezas. Tres razones, las tres verificadas:

1. **No existe ruta HTTP para ese drenaje.** El contrato congelado publica doce rutas;
   `POST /v1/index/sync` es la del **catálogo**. El drenaje de POS no tiene ruta: es CLI.
2. **El feed no sabe filtrar por tienda.** `GET /api/ai/index-feed/pos-availability` acepta
   **sólo** `since` y `sinceId` — es un feed **paginado por keyset sobre todas las tiendas**, no una
   consulta puntual. «Sólo su tienda» no es una variante del botón: es un parámetro nuevo en el feed,
   en el servicio que lo sirve, en el cliente que lo consume y en el contrato congelado.
3. **El perfil de auth no encaja.** Las rutas de índice usan el principal de **catálogo**, que no
   lleva `pos_id`; un token de operario sí. Dar a un operario una ruta de ámbito catálogo es
   exactamente la puerta que `AiCallScope` existe para no abrir — y es la razón de que `ForCatalog` y
   `ForAllPointsOfSale` lleven los mismos campos y sean **dos clases distintas** (C40, grupo 12).

**Y un argumento que pesa más que los tres:** un botón «refrescar» en la pantalla del mostrador le
entrega al operario un problema que **no es suyo**. La rancidez no le esconde piezas; lo único que le
pasa es que la página llega corta. El botón le enseñaría que cuando la búsqueda da poco la culpa es
de un dato que él debe arreglar, y le invitaría a pulsarlo cuando el buscador simplemente no encontró
mucho — que es otra cosa. Con el tramo 1 hecho, **el botón del operario no tiene caso de uso**.

---

## 3 · Lo que este ticket declara y no pide

- **No cambia la decisión de degradar** ante una proyección rancia. Es correcta y está argumentada.
- **No toca `Carried()`** ni la convención 14. La frontera de autorización se queda donde está.
- **No añade migración**: `ai.pos_projection` y `ai.sync_checkpoint` existen desde C22.
- **No propone botón para el operario**, y el §2 dice por qué. Si alguien lo reabre, tendrá que mover
  el feed, el contrato y el perfil de auth, y responder primero para qué.

---

## 4 · Preguntas abiertas para el `design.md`

| # | Pregunta | Por dónde tirar |
|---|---|---|
| 1 | ¿El drenaje vive en .NET (`BackgroundService`) o en `jbg-ai` (tarea propia)? | .NET tiene el patrón y es el dueño del feed; `jbg-ai` es el dueño del esquema `ai`. Decidir por quién puede fallar sin arrastrar al otro |
| 2 | ¿Cómo se implementa el lock con una sola instancia y con varias? | `pg_advisory_lock` sobre el feed es lo más barato y sobrevive a varias instancias |
| 3 | ¿Incremental por defecto y completo sólo a mano? | El incremental es keyset y baratísimo; el completo son 34 páginas. Probablemente sí |
| 4 | ¿El campo del tramo 2 es la edad en segundos o un booleano `stale`? | La edad informa y el booleano decide. `reported_age` ya existe; un booleano derivado en el cliente duplicaría el umbral |
| 5 | ¿El tramo 3 reutiliza el servicio del tramo 1 o expone el CLI? | Reutilizar, o el lock tendría dos dueños |
| 6 | ¿Qué dice la insignia, y en qué estados? | La copia es del `design.md`; ojo con no convertir un aviso en una alarma, que es el error que C36 evitó con `size_label_missing` |

---

## 5 · Una nota de método, porque costó una corrección

**La frescura NO se mide leyendo `MAX(refreshed_at)` de las filas.** El guard lee
`ai.sync_checkpoint.last_incremental_sync_at`, y el *docstring* de `projection.py` advierte
explícitamente del error: el feed es **incremental por keyset**, así que una asignación que no cambia
nunca se re-emite y `refreshed_at` registra cuándo cambió **la asignación**, no cuándo se miró la
proyección. Leerlo de las filas *«reportaría meses de rancidez sobre una proyección sincronizada hace
treinta segundos, y el guard desactivaría el ámbito sobre una proyección perfectamente al día, de
forma permanente»*.

La sesión que abrió este ticket cometió ese error al diagnosticar. La conclusión resultó correcta
**por casualidad** —el checkpoint venía del mismo drenaje del 5 de septiembre que las filas—, pero el
instrumento era el equivocado. Cualquier verificación de este change debe leer el checkpoint.
