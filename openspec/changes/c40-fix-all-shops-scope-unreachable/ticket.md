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

**El ámbito «todas las tiendas» que C40 construyó no se puede alcanzar desde la pantalla.** El
backend lo acepta, la autorización lo permite a operarios y administradores, los DTO se volvieron
anulables para ello y la fila tiene sus tres estados — y **el selector del panel no ofrece la
opción**, así que nadie puede usarlo.

---

## 1 · La evidencia, capa por capa

Tres cosas del frontend lo bloquean, y basta una para que el ámbito sea inalcanzable:

| Dónde | Qué impide |
|---|---|
| [`assisted.tsx:365-369`](../../../frontend/src/pages/sales/assisted.tsx) | El `<SelectContent>` mapea **sólo** `pointsOfSale`. **No existe** una opción «Todas las tiendas» |
| [`assisted.tsx:196`](../../../frontend/src/pages/sales/assisted.tsx) | `if (!trimmed \|\| !pointOfSaleId) return;` — la búsqueda **no se dispara** sin tienda |
| [`assisted.tsx:403`](../../../frontend/src/pages/sales/assisted.tsx) | El botón *Buscar* está `disabled` sin tienda |
| [`ai-search.types.ts:284`](../../../frontend/src/types/ai-search.types.ts) | `pointOfSaleId: string` — **obligatorio**, con el comentario *«Required: searching every shop is a scope of its own»* |

Y al otro lado, todo lo que C40 construyó para ese ámbito **está y funciona**, comprobado contra el
servicio en marcha:

- `POST /api/ai/search/assisted` **sin** `pointOfSaleId` responde 200 y sirve resultados de todo el
  catálogo, con la cantidad y el indicador de stock **nulos**.
- `AiCallScope.ForAllPointsOfSale` existe con su frontera, y el test por reflexión fija que hay
  exactamente tres caminos de construcción y ninguno acepta centinela.
- `AssistedSearchResultDto.QuantityAtPointOfSale` y `HasStock` son anulables **precisamente** para
  este caso, y la fila resuelve **tres** estados con «Selecciona una tienda para ver existencias».
- El botón de ficha se deshabilita, el embudo declara «Sin registrar: búsqueda en todas las tiendas»,
  y la carencia de telemetría está declarada en `DEFERRED_TASKS.md`.

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

### 3.3 · Dos avisos para quien lo implemente

**El centinela no puede llegar al cuerpo HTTP.** Radix no admite `value=""` en un `SelectItem`, así
que hará falta un valor centinela **de interfaz** — y tiene que traducirse a **ausencia** del campo al
construir la petición. Si el centinela viaja en el cuerpo, se acaba de crear el comodín que todo el
grupo 12 existe para impedir: la propiedad que hace seguro este ámbito es que **la ausencia de
`pos_id` hace que el prefiltro no se aplique**, no que case con todo. Y ese agujero ya se abrió y se
cerró una vez en C40 — un `pos_id` presente y en blanco, con su test
(`test_a_blank_pos_claim_is_never_read_as_its_absence`).

**La disponibilidad se lee por tienda.** `GET /api/ai/search/availability` toma un `pointOfSaleId`.
Sin tienda no hay a quién preguntar, así que hay que decidir qué dice la insignia y qué habilita el
toggle en ese estado — y no dejarlo en que el interruptor «parece apagado» porque no se pudo leer.

---

## 4 · Lo que este ticket NO pide

- **No toca el backend.** El endpoint, la autorización y los DTO están hechos y comprobados.
- **No reabre** la decisión de que la cantidad viaje **nula** y no cero. Es correcta y es la razón de
  que el ámbito exista como clase aparte.
- **No añade telemetría** para el ámbito global: sigue siendo la tarea diferida de C40, con su motivo
  (exigiría migración de EF Core y la spec prohíbe el marcador de posición).
- **No es C41.** C41 es la frescura de `ai.pos_projection` y no comparte ni un fichero con esto.

---

## 5 · Preguntas abiertas para el `design.md`

| # | Pregunta | Por dónde tirar |
|---|---|---|
| 1 | ¿El control se ofrece a operarios **y** administradores, o sólo a administradores? | La spec autoriza a los dos y da la razón. Limitarlo exige enmendar la spec, no contradecirla en silencio |
| 2 | ¿Qué dice la insignia de disponibilidad sin tienda? | No se puede leer por tienda; decidir entre no pintarla, pintarla neutra, o leerla de la tienda por defecto y decir que es de ella |
| 3 | ¿Es el ámbito global el valor **por defecto** del selector, o hay que elegirlo? | Por defecto cambiaría el coste y el comportamiento de todo el panel. Casi seguro que no |
| 4 | ¿Cómo se llama la opción en castellano? | «Todas las tiendas» es lo que el usuario usó al reportarlo; conviene que la copia y el reporte coincidan |
| 5 | ¿Debe la spec del panel ganar una regla **transversal** sobre alcanzabilidad? | Es la lección del §2: un estado especificado sin camino hasta él es un estado que nadie puede usar. Podría ser una regla y no un requisito suelto |
