# HU-AIENG-016: Panel «Buscar con ayuda» del operador, con atribución de la venta a la búsqueda

## Formato estándar

Como **operador de punto de venta**, quiero **un panel «Buscar con ayuda» donde describir con mis palabras la pieza que me está pidiendo un cliente y ver resultados con la foto, el precio y el stock reales de mi tienda, y llevarme el elegido al flujo de venta** **para** **encontrar en segundos lo que hoy sólo encuentro si recuerdo el SKU o el nombre exacto, y para que quede medido si la búsqueda asistida sirve de verdad**.

---

## Descripción

Change OpenSpec `add-frontend-assisted-search-panel` / **C16**, épica **EP14 — Búsqueda Semántica Híbrida**. Marcado 🔴 en la ruta crítica y en la lista de *nunca se recorta*. Prerrequisito: **C15** (`POST /api/ai/search`), archivado el 2026-08-28.

Es la primera pantalla del sistema RAG. Todo lo anterior —el corpus, el enriquecimiento, el índice vectorial, el retriever, la hidratación autoritativa— existe para que un operador de Ciutadella, del aeropuerto o de Fornells pueda escribir *«algo azul de plata para regalar a mi suegra»* y obtener piezas que su tienda tiene, al precio que hoy cuestan.

Hoy el operador tiene dos formas de encontrar un producto: escanear su código o teclear el SKU exacto en `/sales/new`. `ProductService.SearchProductsAsync` casa la **cadena completa** contra el nombre, así que cualquier frase en lenguaje natural devuelve lista vacía. El servidor ya sabe hacer lo que falta desde C15; **nadie le llama**.

Y hay una segunda cosa que sólo se ve al llegar aquí. La spec viva `ai-search-telemetry` declara, con escenario y archivada como cumplida, la requirement *«Sale attribution is carried by the sale, not by the event»*. La columna `Sale.SearchEventId`, su índice y su clave foránea existen desde C04. Pero **ni `CreateSaleRequest` ni `BulkSaleLineRequest` tienen el campo**, y ningún servicio lo asigna: el único sitio del repositorio que lo escribe es un test de integración que toca la entidad a mano. Es la misma clase de defecto que la obligación A1 —compila, los tests pasan, `openspec validate --all --strict` da verde y la columna llega vacía a la entrega—, agravada porque aquí ya hay una spec afirmando lo contrario. C16 es donde se descubre y donde se cierra.

**Alcance de esta historia (sí):**

- **Panel en ruta propia** `/sales/new/assisted`, con **tercera tarjeta** en el hub `/sales`, siguiendo el patrón de [`scan.tsx`](../../../frontend/src/pages/sales/scan.tsx): entrega al flujo de venta por estado de navegación.
- `ai-search.service.ts` con las dos llamadas del panel: `POST /ai/search` y `POST /ai/search-events/{id}/selection`, sobre `apiClient` (que ya trae `/api` en `VITE_API_BASE_URL`).
- **Entrada en lenguaje natural con envío explícito** —Enter o botón—, nunca `debounce`, más 3-5 **consultas de ejemplo** pulsables.
- **Filtros rápidos**: materiales en **multi-selección** sobre el vocabulario cerrado, y categoría de pieza. **No disparan por sí solos.**
- **Selector de punto de venta**: oculto si el operador tiene uno solo, visible si tiene varios o es administrador; sólo puntos de venta activos.
- **Resultados en el orden recibido**, con foto, SKU, nombre, precio en EUR, stock del punto de venta con marca de agotado, **insignia de origen** y **chips de materiales**; la talla se pinta sólo cuando `variantLabel` exista.
- **Cinco estados** que dicen cosas distintas: carga, **abstención**, **sin surtido en este punto de venta**, **degradado o desactivado**, y **cuota de peticiones agotada**; más el aviso de **página corta**.
- **Bloque de embudo colapsado, sólo para administradores**: identificador de correlación y `candidatos → supervivientes → mostrados`.
- **«Seleccionar para venta»**: reporta la selección en el instante del clic sin bloquear, y navega a `/sales/new` con `productId` y `searchEventId`.
- **Arrastre de `searchEventId` hasta la caja, por línea**: estado de navegación → `new.tsx` → `CartLine` → `CreateSaleRequest` y `BulkSaleLineRequest`.
- **Tramo .NET mínimo**: `Guid? SearchEventId` en los dos objetos de transferencia de venta, asignación a `Sale.SearchEventId`, y degradación a nula cuando el evento no existe **o es de otro usuario**. Y `materials` en `AssistedSearchResultDto`, que hoy llega del retriever a .NET y se descarta.
- Tests de Vitest + React Testing Library + MSW, y de xUnit para el tramo .NET.

**Fuera de alcance (no):**

- **Tarjeta de argumentario generado, citas y desambiguación por familia** → **C36**. C16 deja el hueco, no lo llena.
- **Rama léxica del híbrido, RRF y diccionario de sinónimos** → **C20 / C21**, en Python. Mientras tanto, `matchReasons` es la cadena literal `["vector"]` y no se pinta.
- **Talla real** → la puebla **C18** en `variantLabel`. No se sustituye hidratando `ProductAiProfile.SizeLabel`, que sería rehacer trabajo de C15.
- **Endpoint que exponga el vocabulario de materiales o los materiales presentes en el surtido de un punto de venta** → anotado para **C28**.
- **Migración de EF Core.** C16 no es 🗄️: la columna `Sale.SearchEventId` es de C04.
- Tocar `ai-service/`, regenerar `ai-service/openapi.json`, o modificar `IAiGatewayClient`, `AssistedSearchService` (más allá de propagar `materials`) o `/api/v1/products/search`.
- Sustituir el buscador por SKU de `/sales/new`, que sigue siendo el camino rápido de quien ya sabe qué quiere.
- Búsqueda asistida desde el catálogo de productos, devoluciones o inventario.
- Persistir preferencias del panel, historial de consultas del operador o `ai.query_log`.

**Decisiones de diseño ya acordadas** (exploración 2026-08-29, registradas en [§0 del plan](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md)):

| # | Tema | Decisión |
|---|---|---|
| 1 | Atribución de venta (B5) | **C16 incluye el tramo .NET mínimo.** `Guid? SearchEventId` en `CreateSaleRequest` y `BulkSaleLineRequest`. Identificador desconocido **o de otro usuario** → atribución nula; **la venta nunca falla**. Sin migración |
| 2 | Ubicación del panel | **Ruta propia** `/sales/new/assisted` + tercera tarjeta en `/sales`, patrón `scan.tsx`. Aísla el fichero que C36 va a ampliar y no engorda `new.tsx`, que ya tiene 702 líneas |
| 3 | Disparo de la búsqueda | **Envío explícito** + consultas de ejemplo. Los filtros no disparan solos; cambiar de punto de venta limpia resultados y no relanza |
| 4 | El «motivo» | **Insignia de origen + chips de materiales**, con `materials` añadido a `AssistedSearchResultDto`. El mapa de insignias queda listo para que C21 añada `lexical` sin tocar el panel |
| 5 | Estados sin resultados | **Cuatro**, no tres: abstención, sin surtido, degradado o desactivado, y cuota agotada. Más **página corta**, que no está vacía y también se declara |
| 6 | Vocabulario de materiales | **Constante en el frontend**, espejo de [`vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml), fijada por un test |
| 7 | Embudo | Bloque colapsado **sólo para administradores**. Evidencia directa para §11 y para el checklist de §16 |
| 8 | Episodio de búsqueda | Un `searchSessionId` por **montaje del panel** |

**El hallazgo que gobierna la historia.** Copiar el `useDebouncedCallback` del catálogo de productos sería el camino natural y es el error. La clave de la caché de candidatos de C15 incluye la cadena de consulta completa, de modo que **ningún prefijo acierta**: una consulta de treinta caracteres genera entre tres y seis peticiones con 400 ms de `debounce`, cada una factura un embedding que nadie leyó, y el límite de C15 —30 peticiones por minuto y por usuario— se agota en cinco o seis consultas. El presupuesto de recuperación son 800 ms más hidratación, así que «resultados mientras escribo» nunca estuvo disponible: el envío explícito no renuncia a nada y además es lo que S4 llama hornear el prompting en la interfaz en lugar de delegarlo en el operador.

**El segundo hallazgo.** Los filtros duros se apilan y ninguno es del panel: el de materiales corre en el SQL de C14 **antes** del umbral y del límite, y la hidratación por punto de venta de C15 corta después. Con las coberturas de C10, un material poco frecuente —`perla`, `cuero`, `resina`— combinado con Fornells (0,22) vacía la página casi con seguridad. De ahí que el estado «sin surtido» ofrezca **quitar filtros** como primer remedio, y que la página corta se declare en lugar de disimularse.

**Cortes que no se reabren:** el contrato C02 no se toca; `ai-service/` no se toca; C16 no abre migración; `/api/v1/products/search` se queda como está; el orden de los resultados es el del servidor.

**Referencias:**

- Change: `openspec/changes/add-frontend-assisted-search-panel/` · ticket [T-AIENG-016](../../../openspec/changes/add-frontend-assisted-search-panel/ticket.md)
- Plan: [proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) — ficha C16 y entrada §0 de 2026-08-29
- Diseño: [proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — §6.4 (degradación), §7.6 (prefiltro y sobre-recuperación), §11 (evaluación)
- Specs vivas: `ai-assisted-search` · `ai-search-telemetry` · `sales-management` · `frontend` · `access-control` · `point-of-sale-management`
- Historias vecinas: [HU-AIENG-004](HU-AIENG-004.md) (telemetría) · [HU-AIENG-015](HU-AIENG-015.md) (endpoint)
- Épica: [EP14](../../epicas.md)

---

## Criterios de Aceptación

### Escenario 1: El operador encuentra una pieza describiéndola con sus palabras

**Dado que** el operador está autenticado, asignado al punto de venta `P`, y abre `/sales/new/assisted` desde la tarjeta «Buscar con ayuda» del hub de ventas
**Y** la búsqueda asistida está activa para `P` y `jbg-ai` responde
**Cuando** escribe *«un anillo de plata para regalar»* y pulsa Enter o el botón de buscar
**Entonces** se emite **una sola** petición a `POST /ai/search` con `query`, `pointOfSaleId = P`, `pageSize` y el `searchSessionId` del episodio
**Y** mientras llega la respuesta se muestra un estado de carga, no una lista vacía
**Y** los resultados se pintan **en el orden recibido**, sin ordenación en cliente
**Y** cada fila muestra foto, SKU, nombre, precio en EUR (€), el stock de `P`, la insignia de origen y los chips de materiales
**Y** una pieza con `hasStock: false` **aparece igualmente**, marcada como sin existencias

### Escenario 2: Teclear no cuesta dinero

**Dado que** el operador está escribiendo la consulta letra a letra
**Cuando** teclea, borra y vuelve a teclear sin enviar
**Entonces** **no** se emite ninguna petición a `POST /ai/search`
**Y** sólo al pulsar Enter o el botón se emite exactamente una
**Y** pulsar una de las consultas de ejemplo rellena la caja **y** lanza la búsqueda, en un solo gesto

### Escenario 3: Los filtros rápidos son multi-selección y no disparan solos

**Dado que** el panel muestra los materiales del vocabulario cerrado como opciones conmutables
**Cuando** el operador marca `plata` y después `perla`
**Entonces** ambos quedan marcados a la vez y se envían juntos en `materials`
**Y** marcarlos **no** lanza ninguna búsqueda por sí mismo
**Y** al enviar, la petición lleva los términos canónicos del vocabulario, no la etiqueta mostrada
**Y** existe una acción visible para **quitar todos los filtros**

### Escenario 4: Los cuatro «cero resultados» dicen cosas distintas

**Dado que** la búsqueda no devuelve ninguna fila
**Cuando** la respuesta trae `aiAvailable: true` y `lowConfidence: true`
**Entonces** el panel dice que no ha encontrado nada que encaje y sugiere **reformular**
**Y** cuando trae `aiAvailable: true`, `lowConfidence: false` y `candidatesReturned > 0`, dice que **hay piezas parecidas pero ninguna está en esta tienda** y ofrece **quitar filtros** como primer remedio
**Y** cuando trae `aiAvailable: false`, dice que la **búsqueda asistida no está disponible** y que lo mostrado viene de la búsqueda por texto
**Y** cuando el servidor responde **429**, dice que se han hecho **demasiadas búsquedas seguidas** y que espere unos segundos, sin insinuar que la IA esté caída
**Y** ninguno de los cuatro se presenta como un error de la aplicación

### Escenario 5: La página corta se declara en lugar de disimularse

**Dado que** el operador busca desde un punto de venta de baja cobertura y sobreviven menos resultados que la página pedida
**Cuando** se pintan los resultados
**Entonces** aparece una línea discreta que indica cuántos hay en esa tienda y cuántos candidatos se consideraron
**Y** los resultados se muestran igualmente, sin degradar la lista a un estado de error
**Y** el bloque de embudo con `candidatos → supervivientes → mostrados` y el identificador de correlación es visible **sólo** para un administrador, colapsado por defecto

### Escenario 6: La selección se reporta al instante y nunca bloquea

**Dado que** la respuesta trajo un `searchEventId`
**Cuando** el operador pulsa «Seleccionar para venta» en una fila
**Entonces** se emite `POST /ai/search-events/{searchEventId}/selection` con el `productId`, **en ese instante**, sin esperar su resultado
**Y** la navegación a `/sales/new` ocurre igualmente, aunque esa llamada falle o tarde
**Y** un fallo de esa llamada **no** muestra ningún error al operador
**Y** si `searchEventId` es nulo porque la telemetría no persistió, la llamada **se omite en silencio** y la selección funciona igual

### Escenario 7: La venta queda atribuida a la búsqueda que la originó

**Dado que** el operador llegó a `/sales/new` desde el panel con `productId` y `searchEventId`
**Cuando** completa la venta directamente
**Entonces** `CreateSaleRequest` lleva ese `searchEventId`
**Y** la `Sale` creada guarda `SearchEventId`
**Y** cuando en vez de vender añade la línea al carrito, el `searchEventId` viaja en la línea y llega a `BulkSaleLineRequest` **por línea**
**Y** una venta iniciada por escaneo, por SKU o por reconocimiento de imagen se guarda con `SearchEventId` nulo, y sigue siendo válida

### Escenario 8: Una atribución imposible degrada a nula, nunca rompe la venta

**Dado que** llega una venta con un `searchEventId` que no existe, o que pertenece a otro usuario
**Cuando** se procesa
**Entonces** la venta **se crea correctamente**
**Y** su `SearchEventId` queda **nulo**
**Y** no se devuelve ningún error de validación por ese campo
**Y** el stock, el movimiento de inventario y el importe se registran exactamente igual que sin atribución

### Escenario 9: El episodio agrupa las reformulaciones de una visita

**Dado que** el operador abre el panel y busca tres veces reformulando la consulta
**Cuando** se inspeccionan las tres peticiones
**Entonces** las tres llevan el **mismo** `searchSessionId`
**Y** ese identificador se genera al montar el panel, no por búsqueda
**Y** cambiar de punto de venta dentro de la misma visita **no** lo cambia
**Y** volver a abrir el panel más tarde genera uno nuevo

### Escenario 10: El punto de venta manda, y el rol decide cuál

**Dado que** el operador tiene un único punto de venta asignado
**Cuando** abre el panel
**Entonces** ese punto de venta queda preseleccionado y el selector no se muestra
**Y** si tiene varios, o es administrador, aparece un selector con los puntos de venta **activos** que puede usar
**Y** cambiar de punto de venta **limpia los resultados** y no relanza la búsqueda automáticamente
**Y** una respuesta **403** se presenta como que no tiene acceso a esa tienda, distinguible de un fallo del servicio

### Escenario 11: Fuera de alcance explícito

**Dado que** C16 entrega el panel del operador
**Cuando** se revisa el entregable
**Entonces** **no** hay cambios en `ai-service/` ni en `ai-service/openapi.json`
**Y** **no** hay migración de EF Core
**Y** `/api/v1/products/search` y el buscador por SKU de `/sales/new` mantienen su comportamiento
**Y** **no** se pinta `matchReasons` crudo, ni se inventa una talla mientras `variantLabel` sea nulo
**Y** **no** se entrega tarjeta de argumentario, citas ni agrupación por familia, que son de C36

---

## Notas adicionales

- **Actor.** El operador de punto de venta es el beneficiario. El administrador puede ejercitar el panel sobre cualquier punto de venta activo, que es lo que hará falta para el vídeo de entrega y para ver el bloque del embudo.

- **Por qué ruta propia y no un modo dentro de `new.tsx`.** `new.tsx` tiene 702 líneas y ya gestiona punto de venta, método de pago, cantidad, precio manual, stock y diálogo de confirmación. Meterle un segundo buscador lo convertiría en el peor fichero de la aplicación justo antes de que C36 vuelva a tocarlo. La ruta propia además reproduce el patrón que `scan.tsx` y `new-image.tsx` ya validaron, y hace la funcionalidad descubrible desde el hub, que es donde el operador elige cómo entrar a una venta.

- **Por qué no se puede distinguir «desactivado» de «caído».** La respuesta trae `aiAvailable: false` tanto si el circuito está abierto como si la asistencia está apagada para ese punto de venta. La telemetría **sí** los separa (`LexicalFallback` frente a `Disabled`), la API no. Para el operador el mensaje es el mismo —la búsqueda asistida no está sirviendo—, así que se acepta como decisión escrita en lugar de pedirle a C15 un discriminador que sólo cambiaría el texto de un aviso.

- **Por qué el vocabulario de materiales se replica en el frontend.** Son nueve términos de un vocabulario **cerrado** que sólo cambia cuando cambia `vocabularies.yaml`, en otro servicio y por acto deliberado. Un endpoint que lo devolviera duplicaría igual la lista, en configuración de .NET. Lo que sí sería mejor producto es un endpoint que agregue los materiales **realmente presentes en el surtido de ese punto de venta**, para no ofrecer nunca un filtro que devuelve cero: cuesta una consulta sobre `ProductAiProfile.MaterialsJson` cruzada con inventario, y se anota para **C28**. El riesgo de la réplica es la deriva silenciosa —un término desalineado no da error, devuelve cero—, y por eso lleva test que lo fija.

- **`matchReasons` no se pinta.** [`retrieval/orchestrator.py`](../../../ai-service/src/jbg_ai/retrieval/orchestrator.py) lo fija en `["vector"]` para todos los resultados hasta que C21 añada la rama léxica. Se sustituye por una insignia derivada de `aiAvailable`, con un mapa preparado para que C21 aporte valores reales sin tocar el panel.

- **La atribución exige comprobar propiedad, no sólo existencia.** El endpoint de selección de C04 exige que el evento sea del usuario, sin excepción de administrador, porque un evento de búsqueda registra lo que hizo una persona concreta. Si la atribución sólo comprobara existencia, un cliente podría colgar su venta de la búsqueda de un compañero y el KPI se ensuciaría sin dejar rastro. La comprobación es explícita —no vale confiar en la clave foránea, que abortaría la transacción de la venta en lugar de degradar.

- **El carrito persiste en `localStorage` con TTL de 10 horas.** Un `searchEventId` de hace nueve horas atribuirá la venta, y eso es correcto: es lo que pasó.

- **`sendBeacon` no sirve aquí** y tampoco hace falta: no hay descarga de página —la navegación es de SPA— y `sendBeacon` no puede poner la cabecera de autorización que usa `apiClient`.

- **Par de zona.** No solapar con **C36**, que reescribirá la fila de resultado con la tarjeta de argumentario y la desambiguación por familia. C16 debe dejar la fila como un componente propio para que C36 la amplíe en vez de sustituirla.

- **`design.md` obligatorio** en el change: ocho decisiones con alternativas defendibles y un cruce de tres zonas no caben sólo en `tasks.md`.

- **Trampa de la suite de frontend.** MSW corre con `onUnhandledRequest: 'warn'`, así que una petición sin manejador **no rompe el test**: los manejadores del panel se declaran explícitamente o los tests pasarán sin probar nada.

---

## Tareas

1. Completar los artefactos OpenSpec del change: `proposal`, **`design.md`**, specs delta (capacidad nueva del panel + `## MODIFIED` sobre `sales-management` por el tercer método de entrada y la atribución, + `## MODIFIED` sobre `ai-assisted-search` por `materials` en la respuesta) y `tasks`.
2. **Tramo .NET, primero**, porque desbloquea el arrastre completo: `Guid? SearchEventId` en `CreateSaleRequest` y `BulkSaleLineRequest`, asignación con comprobación de existencia y propiedad, degradación a nula, y `materials` en `AssistedSearchResultDto`.
3. Tipos TypeScript espejo de los objetos de transferencia de C15 en `frontend/src/types/`.
4. `frontend/src/services/ai-search.service.ts` con las dos llamadas y el mapeo de `429`, `403` y `400` a estados propios.
5. Constante del vocabulario de materiales con su test de fijación.
6. Componente de fila de resultado, aislado para que C36 lo amplíe.
7. Página `/sales/new/assisted`: episodio, envío explícito, consultas de ejemplo, filtros, selector de punto de venta, guardia de respuestas obsoletas, los cinco estados y el embudo de administrador.
8. Ruta en `routing/routes.tsx` y `app-routing-setup.tsx`, y tercera tarjeta en `pages/sales/index.tsx`.
9. Arrastre de `searchEventId`: estado de navegación en `new.tsx`, `CartLine`, `cart.tsx` y los dos envíos de venta.
10. Tests de Vitest + RTL + MSW del panel y del servicio; tests de xUnit del tramo .NET.
11. Enlazar la HU en `Documentos/epicas.md` (EP14) durante el apply.
12. `openspec validate --all --strict` en verde antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 5 — es la pantalla que convierte todo lo construido desde C01 en algo que un operador usa, y la que cierra el embudo búsqueda → selección → venta
- **Urgencia (mercado / feedback):** **5** — 🔴; nunca se recorta; cierra, con C17, el hito de la Ola 2
- **Complejidad / esfuerzo:** 4 — el panel es más ancho que profundo (cinco estados, cuatro errores, un arrastre que cruza cuatro ficheros y un tramo .NET), pero sin algoritmo nuevo y sin migración
- **Riesgos y dependencias:**
  - **Página corta y filtros apilados.** En Fornells (0,22) y el aeropuerto (0,38) la página saldrá corta a menudo, y un material poco frecuente puede vaciarla. Es lo esperado, se declara en pantalla y se corrige en C22. Si la demo se graba desde Fornells, hay que contarlo.
  - **El tramo .NET rompe la regla de una zona por change.** Se acepta a propósito: sin él, B5 envía un campo a un servidor que lo descarta, que es el patrón «código muerto sin síntoma» que el plan ya pagó con C04.
  - **Deriva del vocabulario de materiales** replicado en el frontend: un término desalineado no da error, devuelve cero. Mitigado con un test de fijación.
  - **`matchReasons` y `variantLabel` vacíos** hasta C21 y C18: el panel debe degradar sin huecos feos, no inventar contenido.
  - **No paralelizar con C36** (misma página y mismo servicio del frontend).
  - Los `## MODIFIED` sobre specs archivadas obligan a `openspec validate --all --strict`, no basta la forma de un solo change.
