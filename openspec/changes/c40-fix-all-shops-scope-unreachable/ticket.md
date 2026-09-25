# T-AIENG-040-FIX: The every-point-of-sale scope is unreachable from the panel — give it a control, and give the spec the requirement that was missing (C40_FIX)

> **Idioma.** Título e identificadores técnicos en inglés, cuerpo en español — la regla de los
> tickets del Proyecto Final.
>
> **Fuentes de verdad:** las specs vivas
> [`ai-free-query-search`](../../specs/ai-free-query-search/spec.md) y
> [`assisted-search-panel`](../../specs/assisted-search-panel/spec.md), el
> [change archivado de C40](../archive/2026-09-25-add-frontend-free-query-panel/) con su
> [ticket](../archive/2026-09-25-add-frontend-free-query-panel/ticket.md) y su
> [informe](../../../Documentos/Proyecto%20Final%20AIEng/informes/c40-implementation-measurements.md),
> y **el código real**, que es de donde sale todo lo que sigue.

**Change:** `c40-fix-all-shops-scope-unreachable` (C40_FIX) · **Épica:** EP15
**Abierto:** 2026-09-25 · **Corrige:** C40, archivado el mismo día
**Origen:** pruebas manuales del usuario sobre el entorno levantado tras el cierre de C40.

---

## 0 · El defecto, en una frase

**El ámbito «todas las tiendas» que C40 construyó no se puede alcanzar desde la pantalla, por ningún
rol, ni siquiera administrador.** El backend lo acepta, la autorización lo permite a operarios y
administradores, los DTO se volvieron anulables para ello y la fila tiene sus tres estados — y **el
selector del panel no ofrece la opción**, así que nadie puede usarlo.

> **El fix son DOS piezas, no una.** Añadir sólo la opción al selector entregaría el ámbito global con
> **la ruta generativa apagada y sin motivo que enseñar**, porque `GET /api/ai/search/availability`
> rechaza la ausencia de punto de venta con un 400. Está en el §1.2, y es lo que dimensiona este
> ticket: no es un `SelectItem`.

---

## 1 · La evidencia, capa por capa

> Exploración hecha en una revisión posterior al cierre de C40, con las líneas comprobadas una a una
> contra el árbol. **No hace falta repetirla.** Las referencias de abajo se verificaron al escribir
> este ticket: el controlador de la sonda, el `IsEnabled` del servicio, la nulabilidad del request, el
> efecto de disponibilidad, el patrón `'all'` de la categoría y los tests de la fila.

### 1.1 · Hallazgo 1 — la opción no existe en el selector

Tres cosas del frontend lo bloquean, y basta una para que el ámbito sea inalcanzable:

| Dónde | Qué impide |
|---|---|
| [`assisted.tsx:365-369`](../../../frontend/src/pages/sales/assisted.tsx) | El `<SelectContent>` mapea **sólo** `pointsOfSale`. **No existe** una opción «Todas las tiendas» |
| [`assisted.tsx:196`](../../../frontend/src/pages/sales/assisted.tsx) | `if (!trimmed \|\| !pointOfSaleId) return;` — la búsqueda **no se dispara** sin tienda |
| [`assisted.tsx:403`](../../../frontend/src/pages/sales/assisted.tsx) | El botón *Buscar* está `disabled` sin tienda |
| [`ai-search.types.ts:284`](../../../frontend/src/types/ai-search.types.ts) | `pointOfSaleId: string` — **obligatorio**, con el comentario *«Required: searching every shop is a scope of its own»* |

Añádase que el efecto de carga **fija la tienda a la primera activa** (`assisted.tsx` ~152-154:
`if (active.length > 0) { setPointOfSaleId(active[0].id); }`), así que el estado «sin tienda» no es
que sea difícil de alcanzar: **no se alcanza nunca**. Todo lo que hay aguas abajo de él no se ejecuta
en la aplicación real, ni una vez.

### 1.2 · Hallazgo 2 — **el importante**: añadir sólo la opción entrega la ruta generativa apagada

**La sonda de disponibilidad exige punto de venta**, y lo rechaza con un 400
([`AiSearchController.cs:239-250`](../../../backend/src/JoiabagurPV.API/Controllers/AiSearchController.cs)):

```csharp
public IActionResult Availability([FromQuery] Guid pointOfSaleId)
{
    ...
    if (pointOfSaleId == Guid.Empty)
        return BadRequest(new { errors = new[] { "El punto de venta es obligatorio." } });
```

Y el panel, sin tienda, **se pone en blanco a sí mismo** ([`assisted.tsx:171-176`](../../../frontend/src/pages/sales/assisted.tsx)):

```tsx
useEffect(() => {
  if (!pointOfSaleId) { setAvailability(null); setAvailabilitySettled(false); return; }
```

Que desemboca en el toggle ([`assisted.tsx:378-385`](../../../frontend/src/pages/sales/assisted.tsx)):

```tsx
assistedAvailable={availability?.assistedAnswerAvailable ?? false}
assistedUnavailableReason={availability?.assistedAnswerUnavailableReason}
```

**Con «todas las tiendas» seleccionada, `availability` es `null` → el interruptor de la respuesta
asistida sale deshabilitado y sin motivo que enseñar.** Es **la misma forma de avería que C40 existió
para corregir**: un camino que se apaga solo y no lo dice.

Y el servicio **ya sabe contestar** ese caso
([`FreeQuerySearchService.cs:418`](../../../backend/src/JoiabagurPV.Application/Services/FreeQuerySearchService.cs)):

```csharp
private static bool IsEnabled(AiFreeQuerySearchOptions options, Guid? pointOfSaleId) =>
    pointOfSaleId is { } named ? options.IsEnabledFor(named) : options.EnabledByDefault;
```

El único que no deja preguntar es **el controlador de la sonda**. De ahí que el fix sean dos piezas: la
opción en el selector **y** que `GET /availability` acepte la ausencia de punto de venta y devuelva el
ámbito por defecto.

### 1.3 · Lo que YA funciona y no hay que reconstruir

Comprobado en el código y en el §12 del
[informe de C40](../../../Documentos/Proyecto%20Final%20AIEng/informes/c40-implementation-measurements.md):

- `AiCallScope.ForAllPointsOfSale` / `AiCallScopeKind.AllPointsOfSale`, aceptado en recuperación y
  assist, rechazado en ficha, sustitutos e inventario. El test por reflexión fija que hay exactamente
  tres caminos de construcción y ninguno acepta centinela.
- `FreeQuerySearchService.ScopeOf`: `pointOfSaleId is null → ForAllPointsOfSale`.
- `AssistedSearchResultDto.QuantityAtPointOfSale` y `HasStock` anulables; la hidratación sin tienda
  **agrupa por producto** — sin agrupar, un producto que tres tiendas llevan vuelve tres veces y el
  `ToDictionary` del llamador revienta por clave duplicada.
- `assisted-search-result-row.tsx` con sus **tres** estados y sus tests: no pinta cero, nombra la
  tienda cuando la hay y deshabilita el botón de ficha sin ella.
- **Autorización: el ámbito global está abierto a operarios y administradores** (tarea 12.4 de C40,
  tests `FreeQuery_ForOperatorWithAllPointsOfSale_IsServed` y
  `FreeQuery_WhenNamingAnUnassignedPointOfSale_IsRefused`). **No lo endurezcas a sólo administrador**:
  la frontera que se protege es no poder **nombrar** una tienda no asignada, no el ensanchado.
- El hueco de telemetría ya está declarado: una búsqueda global **no se registra**
  (`ProductSearchEvent.PointOfSaleId` es no nulo e indexado; registrarla exige migración de EF Core).
  Está en `openspec/DEFERRED_TASKS.md`, y el embudo ya tiene la línea «Sin registrar: búsqueda en
  todas las tiendas».
- `POST /api/ai/search/assisted` **sin** `pointOfSaleId` responde 200 y sirve resultados de todo el
  catálogo, con cantidad e indicador de stock nulos — comprobado contra el servicio en marcha.

**Un tramo entero de C40 —el grupo 12, con su frontera de autorización, su cambio de anulabilidad en
el contrato interno y su copia— existe y nadie puede llegar a él.**

---

## 2 · Por qué no falló nada, que es el hallazgo de verdad

Fui a las specs esperando una violación y **no la hay**. Los tres escenarios del panel están
condicionados así:

> **WHEN** the search is scoped to every point of sale → **THEN** the stock label states that a point
> of sale must be selected to read stock…

Describen qué hace el panel **estando** en ese estado. **Ninguno exige que el panel ofrezca la forma
de entrar en él.** Y el requisito de `ai-free-query-search` dice *«The route SHALL accept a request
scoped to every point of sale»* — **la ruta**, que sí lo hace.

Así que la letra se cumple, y por eso los **136 escenarios de C40 salieron verdes** y su verificación
independiente —que sí encontró una cuarta infracción de completitud y dos afirmaciones falsas del
informe— **pasó por encima de esto**. El hueco está **en la spec**, no en la implementación: nadie
escribió el requisito de que el control exista.

**Y es la tercera aparición del mismo modo de fallo en esta familia de cambios.** El §11 de C40
declara que su barrido de completitud **empareja por nombre**, de modo que un campo leído en una
superficie cuenta como leído en todas — así se le escapó que `FreeQuerySearchResponse.searchEventId`
no tenía lector. Su verificación arregló eso y cometió la variante: auditó **el estado** sin
comprobar su **alcanzabilidad**. Los tres casos son la misma cosa — *verificar la pieza en
aislamiento en vez del camino hasta ella*. Eso debería dejar rastro en la spec, no sólo en el código.

---

## 3 · Lo que se pide

### 3.1 · El requisito que falta (esto primero, y es el núcleo)

Un requisito en `assisted-search-panel` que exija **el control**, no sólo el comportamiento en el
estado. Algo de la forma: *el panel SHALL ofrecer, a quien esté autorizado a usarlo, una manera
explícita de buscar en todas las tiendas, distinguible de haber elegido una*. Con escenario propio
que se pueda fallar si el control desaparece.

Escribir el código sin el requisito **reproduce la condición que dejó el hueco**: si nadie lo exige,
la próxima vez vuelve a faltar.

### 3.2 · El control

Una opción «Todas las tiendas» en el selector del panel, y los dos guards relajados para que el
ámbito sin tienda sea un estado válido de la pantalla y no un formulario incompleto.

**Quién debe verla.** La spec de `ai-free-query-search` autoriza el ámbito a **operarios y
administradores**, con su razón escrita: la disponibilidad de un producto por tiendas ya es legible
por cualquier llamante autenticado, así que una búsqueda que las abarque no revela nada nuevo. El
`design.md` decide si el control se ofrece a los dos o sólo al administrador, pero **si se limita al
administrador hay que enmendar la spec**, no dejar el requisito diciendo una cosa y la pantalla otra.

### 3.3 · La sonda de disponibilidad, que es la segunda pieza

`GET /api/ai/search/availability` tiene que **aceptar la ausencia** de punto de venta y devolver el
ámbito por defecto. Es un cambio de tres líneas en el controlador —`Guid` pasa a `Guid?`, y el
`BadRequest` deja de dispararse cuando no viene— porque **el servicio ya sabe contestarlo**:
`IsEnabled` tiene su rama para `null` y resuelve a `options.EnabledByDefault`.

Sin esto, el tramo 3.2 entrega el ámbito global con **el toggle asistido deshabilitado y sin motivo**,
que es exactamente la avería que C40 vino a retirar. No es opcional y no es cortable.

### 3.4 · Una restricción que no se puede violar

**El centinela no sale al cable.** En el `Select` hará falta un valor para la opción —y la propia
página **ya usa ese patrón** para la categoría, en
[`assisted.tsx:456`](../../../frontend/src/pages/sales/assisted.tsx):
`value={category || 'all'}` con `onValueChange={(v) => setCategory(v === 'all' ? '' : v)}`— pero tiene
que traducirse a **ausencia** antes de la petición. `FreeQuerySearchRequest.PointOfSaleId` es `Guid?`.

**Un `Guid.Empty` viajando sería el comodín por accidente que C40 dedicó un grupo entero a cerrar.** La
propiedad que hace seguro este ámbito es que **la ausencia de `pos_id` hace que el prefiltro no se
aplique**, no que case con todo. Ver `test_a_blank_pos_claim_is_never_read_as_its_absence` y la regla
que lo gobierna: *ausencia es que la clave no esté en el payload; cualquier otra cosa es un valor, y un
valor tiene que ser usable*.

### 3.5 · Tests

**Los existentes no cubrían esto, y no era descuido**: los de la fila pasan `pointOfSaleName` —y el
`hasStock` nulo— **directamente al componente**
([`assisted-search-result-row.test.tsx:167`](../../../frontend/src/components/sales/__tests__/assisted-search-result-row.test.tsx)),
así que nunca ejercitaron el camino del panel. Es la misma lección del §2 en forma de test: el
componente estaba probado, el camino hasta él no.

Los nuevos van **a nivel de página**, en `frontend/src/pages/sales/__tests__/assisted.test.tsx`:

- que la opción de ámbito global **exista y sea seleccionable**;
- que seleccionarla **no emita ninguna petición de búsqueda** — regla del panel: sólo se busca cuando
  el operario lo pide;
- **que el toggle de respuesta asistida siga habilitado** con el ámbito global — es el hallazgo 1.2, y
  es el test que de verdad cierra este ticket;
- que la fila deje de nombrar tienda y deshabilite el botón de ficha;
- que **no viaje `Guid.Empty`** al backend.

Y del lado .NET, el caso nuevo de la sonda: **sin punto de venta devuelve 200 con el ámbito por
defecto en vez de 400**.

### 3.6 · Antes de cerrar

- `openspec validate --all --strict` en **0 failed** — la forma de un solo change no es la puerta.
- Las suites **vienen rojas de fábrica**: comparar **nombres**, no recuentos, contra la línea base del
  propio commit. Frontend ~113-114; backend ~50. Detalle en `CLAUDE.md`.
- Si se escriben deltas de spec: la descripción que sigue a `### Requirement:` se valida leyendo
  **sólo su primera línea física**. Va en una línea larga, sin ajustar a 90 columnas.

---

## 4 · Lo que este ticket NO pide

> **Corrección.** Una versión anterior de este ticket decía «no toca el backend». **Es falso**, y lo
> descubrió la exploración del §1.2: toca `AiSearchController.Availability`, que es la segunda pieza
> del fix. Lo que no toca es todo lo demás del backend.

- **No toca el endpoint de búsqueda, la autorización ni los DTO.** Están hechos y comprobados; lo
  único que cambia en .NET es que la **sonda de disponibilidad** deje de rechazar la ausencia de
  tienda.
- **No endurece la autorización a sólo administrador.** La spec la abre a operarios y administradores
  con su razón escrita, y la frontera que se protege es no poder **nombrar** una tienda no asignada,
  no el ensanchado.
- **No reabre** la decisión de que la cantidad viaje **nula** y no cero. Es correcta y es la razón de
  que el ámbito exista como clase aparte.
- **No añade telemetría** para el ámbito global: sigue siendo la tarea diferida de C40, con su motivo
  (exigiría migración de EF Core y la spec prohíbe el marcador de posición).
- **No es C41.** C41 es la frescura de `ai.pos_projection` y no comparte ni un fichero con esto.

---

## 5 · Preguntas

**Dos quedaron cerradas por la exploración del §1**, y se registran cerradas para que el `design.md` no
las reabra:

| # | Pregunta | **Resuelta** |
|---|---|---|
| 1 | ¿El control se ofrece a operarios **y** administradores, o sólo a administradores? | **A los dos.** La spec lo autoriza así con su razón, y endurecerlo a administrador sería contradecir la spec en silencio. La frontera es no poder **nombrar** una tienda ajena, no el ensanchado |
| 2 | ¿Qué dice la insignia de disponibilidad sin tienda? | **Lo que responda la sonda**, una vez acepte la ausencia: el ámbito por defecto, vía `options.EnabledByDefault`. Deja de ser una pregunta de interfaz y pasa a ser la segunda pieza del fix (§3.3) |

Siguen abiertas:

| # | Pregunta | Por dónde tirar |
|---|---|---|
| 3 | ¿Es el ámbito global el valor **por defecto** del selector, o hay que elegirlo? | Hoy el efecto de carga fija la primera tienda activa. Cambiarlo movería el coste y el comportamiento de todo el panel. Casi seguro que no |
| 4 | ¿Cómo se llama la opción en castellano? | «Todas las tiendas» es lo que se usó al reportarlo; conviene que la copia y el reporte coincidan |
| 5 | ¿Debe la spec del panel ganar una regla **transversal** sobre alcanzabilidad? | Es la lección del §2: un estado especificado sin camino hasta él es un estado que nadie puede usar. Podría ser una regla y no un requisito suelto |
| 6 | ¿La sonda sin tienda responde `200` con qué forma exacta? | Hoy el DTO lleva `pointOfSaleId`. Sin tienda hay que decidir si viaja nulo o se omite — y que **no viaje `Guid.Empty`**, por lo mismo del §3.4 |
