# HU-AIENG-015: Endpoint de búsqueda asistida en .NET con hidratación autoritativa

## Formato estándar

Como **desarrollador del proyecto**, quiero **un endpoint `POST /api/ai/search` que pida candidatos a `jbg-ai`, los hidrate desde PostgreSQL con la verdad de negocio del punto de venta, degrade a un buscador léxico propio cuando la IA no responde y registre la telemetría de C04** **para** **que el panel de C16 pueda enseñar al operador resultados con precio, stock y permisos reales, y para que el sistema no se caiga nunca por culpa de la IA**.

---

## Descripción

Change OpenSpec `add-dotnet-ai-search-endpoint` / **C15**, épica **EP14 — Búsqueda Semántica Híbrida**. Marcado 🔴 en la ruta crítica y en la lista de *nunca se recorta*. Prerrequisitos: **C03** (cliente gateway) y **C14** (retriever vectorial), ambos archivados.

Es el change que implementa la **decisión 11** de la revisión: *la verdad la pone .NET*. Python calcula parecidos; .NET calcula números y decide. El endpoint es la primera pieza del sistema RAG que un operador va a tocar, aunque la pantalla llegue en C16.

Hoy el hueco está completo por los dos lados y vacío en el medio: `IAiGatewayClient.SearchAsync` mapea el contrato congelado con presupuesto de 800 ms, circuit breaker y `AiCallScope`; `IProductSearchEventService.RecordSearchAsync` persiste el evento y nunca lanza; `ProductService.SearchProductsAsync` existe como buscador clásico. **No existe ningún endpoint que los una.**

El valor no es sólo de fontanería. C15 desbloquea **C16** (panel del operador) y **C17** (despliegue del servicio en producción), que son el hito de la Ola 2, y arrastra la obligación **A1** de C04: sin invocar `RecordSearchAsync`, C04 es código muerto sin síntoma — compila, los tests pasan y la tabla llega vacía a la entrega.

**Alcance de esta historia (sí):**

- `AiSearchController` nuevo en `api/ai/search`, sin versión en la ruta, siguiendo el patrón de `AiCatalogController` y `AiSearchEventsController`. Autenticado; **el body exige `pointOfSaleId` siempre**.
- Servicio de aplicación que orquesta: resolver y validar el POS → comprobar el flag → llamar al gateway con la **ventana máxima del contrato en una sola llamada** (`top_k = 20` → 60 candidatos) → hidratar → truncar → registrar telemetría → responder.
- **Hidratación autoritativa** con una consulta conjunta sobre `public`: `Product` activo, `Inventory` activo **en ese POS**, cantidad de ese POS, precio, foto principal, nombre de colección. Precio y stock **nunca** vienen de la respuesta de la IA.
- **Buscador degradado propio**, acotado al POS de la búsqueda: `to_tsvector('spanish', …)` calculado en consulta —sin índice y sin migración—, **semántica OR** y orden por `ts_rank`.
- **Feature flag por POS** en configuración (`IOptionsMonitor`), y `SearchOrigin.Disabled` como tercer origen de telemetría.
- **Caché de candidatos** de TTL corto (sólo identificadores y scores de la IA; la hidratación se rehace siempre) y **política de limitación de peticiones** particionada por usuario.
- Telemetría completa de C04: `RecordSearchAsync` **después** de hidratar y truncar, `searchEventId` en la respuesta, `SearchOrigin`, `traceId`, `RetrievalMs`, `TotalMs`, `searchSessionId`.
- Respuesta que distingue los **tres «cero resultados»**: abstención, sin surtido en este POS, y degradado.
- Log estructurado del embudo (`candidatesReturned → survivedHydration → displayed`) con `trace_id` y `posId`.
- Tests unitarios con `IAiGatewayClient` falso y de integración con Testcontainers.

**Fuera de alcance (no):**

- **Frontend** → **C16**. Esta historia no toca `frontend/src/`.
- **Despliegue del servicio de IA** → **C17**.
- **Rama léxica del híbrido, RRF y sinónimos** → **C20 / C21**, en Python, sobre `ai.product_document.tsv` (que ya existe con índice GIN desde C05). El buscador degradado de C15 **no es** esa rama y no la anticipa.
- **Filtro duro por POS dentro del retriever y `ai.pos_projection`** → **C22**.
- `POST /api/ai/assist`, sustitutos y complementarios → **C26 / C27 / C34**.
- **Migración EF Core.** C15 no es 🗄️: ni columna nueva, ni índice nuevo, ni cambio de esquema.
- Tocar `ai-service/` (incluido el singleton del cliente de embeddings, que se anota como deuda para C21/C22), regenerar `ai-service/openapi.json`, o modificar `IAiGatewayClient`.
- Modificar `/api/v1/products/search`, que usan otras pantallas.
- `ai.query_log` (sigue sin dueño desde C05).
- Agrupación por familia y `pitch` generado → **C34 / C36**.

**Decisiones de diseño ya acordadas** (exploración 2026-08-28, registradas en [§0 del plan](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md)):

| # | Tema | Decisión |
|---|---|---|
| 1 | Sobre-recuperación | `top_k = 20` → **60 candidatos, techo absoluto del contrato, una sola llamada**. **Se elimina** la repetición con `top_k` mayor: el umbral de C14 filtra *antes* del `LIMIT`, así que repedir devuelve las mismas filas cobrando un segundo embedding |
| 2 | Hidratación | Se descarta si no hay `Inventory` activo **en ese POS** o `Product.IsActive = false`. **`Quantity = 0` se conserva** y se marca. Cantidad **de ese POS**, no la suma. Consulta conjunta: **nunca** `ProductService` |
| 3 | Fallback degradado | **Full-text español calculado en consulta** sobre `public."Products"`, acotado al POS, **semántica OR**, orden por `ts_rank`. Sin índice, sin migración. Spike de verificación como primera tarea |
| 4 | Feature flag | **Configuración** con `IOptionsMonitor` + `SearchOrigin.Disabled = 3` vía `## MODIFIED` sobre la spec viva `ai-search-telemetry`. Columna entera: sin migración |
| 5 | Coste | **Caché de candidatos** (TTL corto, clave con `posId` desde el día uno) **+ rate limit por `userId`** |
| 6 | Admin y POS | El body **exige `pointOfSaleId` siempre**. Operador validado contra sus asignaciones; **admin puede elegir cualquier POS activo** |
| 7 | Embudo | Se instrumenta en **log estructurado**, no en columnas. La línea base para C22 sale de `ResultsCount` + `PointOfSaleId`, ya persistidos; abstención vs sin surtido se separa uniendo por `TraceId` con el log `stage=search` de C14 |

**El hallazgo que gobierna el change.** El §7.6 paso 1 del diseño sitúa el `pos_id` como filtro duro **en Python**, pero C13 no indexó disponibilidad y C14 declara que *«the search SQL does not filter by `pos_id`»*. C15 vive en la ventana anterior a C22 y sólo puede aplicarlo al hidratar. Con las coberturas de C10 (`FORNELLS` 0,22; `MAO-AIR` 0,38) y el 8 % de inventario inactivo, **una página de 10 se llena en el ~4 % de las búsquedas de FORNELLS con 30 candidatos**, y el sesgo de `collection_weights` hace que el descarte correlacione con el ranking en lugar de adelgazar uniformemente. Se acepta el corte, se dobla la ventana y **se mide**, porque esa medición es la línea base «antes» de la ablation de C22 en §11.2.

**Cortes que no se reabren:** el contrato C02 no se renegocia (`top_k` máximo 50, overfetch `min(top_k × 3, 60)`); `IAiGatewayClient` no cambia; Python no se toca; C15 no abre migración; `/api/v1/products/search` se queda como está.

**Referencias:**

- Change: `openspec/changes/add-dotnet-ai-search-endpoint/` · ticket [T-AIENG-015](../../../openspec/changes/add-dotnet-ai-search-endpoint/ticket.md)
- Plan: [proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) — ficha C15 y entrada §0 de 2026-08-28
- Diseño: [proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — §6.2 (frontera), §6.4 (degradación), §7.6 (prefiltro blando y sobre-recuperación)
- Specs vivas: `ai-gateway-client` · `ai-search-telemetry` · `vector-retrieval` · `product-management` · `inventory-management` · `access-control`
- Historias vecinas: [HU-AIENG-004](HU-AIENG-004.md) (telemetría) · [HU-AIENG-014](HU-AIENG-014.md) (retriever)
- Épica: [EP14](../../epicas.md)

---

## Criterios de Aceptación

### Escenario 1: Una búsqueda asistida devuelve resultados con la verdad de negocio del POS

**Dado que** el operador está autenticado y asignado al punto de venta `P`
**Y** el flag de búsqueda asistida está activo para `P`
**Y** `jbg-ai` responde correctamente
**Cuando** llama a `POST /api/ai/search` con una consulta en lenguaje natural, `pointOfSaleId = P` y una página de 10
**Entonces** se llama al gateway **una sola vez**, con `top_k = 20`
**Y** los candidatos recibidos se hidratan desde `public` con una consulta conjunta
**Y** el precio, la cantidad, la foto y el nombre de cada resultado salen de la base de datos, **no** de la respuesta de la IA
**Y** la cantidad devuelta es la de `P`, no la suma de los puntos de venta del usuario
**Y** la lista se trunca a 10 conservando el orden de relevancia recibido
**Y** la respuesta incluye `searchEventId`, `aiAvailable: true` y `lowConfidence: false`

### Escenario 2: La ventana máxima se pide una vez y no se repide

**Dado que** tras hidratar quedan menos resultados de los pedidos
**Cuando** termina la hidratación
**Entonces** **no** se emite una segunda llamada al gateway
**Y** se responde con los resultados que hayan sobrevivido, aunque sean menos que la página
**Y** el log estructurado registra `candidatesReturned`, `survivedHydration` y `displayed` con el `trace_id` y el `posId`

### Escenario 3: El stock cero no elimina, pero la falta de asignación sí

**Dado que** entre los candidatos hay un producto asignado a `P` con `Quantity = 0`, otro con `Inventory.IsActive = false` en `P`, otro sin fila de inventario en `P` y otro con `Product.IsActive = false`
**Cuando** se hidrata
**Entonces** el de cantidad cero **se conserva** y se marca como sin stock
**Y** los otros tres se descartan
**Y** el descarte se refleja en `survivedHydration`

### Escenario 4: Con la IA caída se responde con el buscador degradado, no con una lista vacía

**Dado que** el circuito de recuperación está abierto, o el gateway agota el presupuesto, o devuelve un error de configuración
**Cuando** el operador busca *«un anillo de plata para regalar»*
**Entonces** la petición **no** falla: se responde HTTP 200 con `aiAvailable: false`
**Y** el buscador degradado casa **cualquier término** de la consulta, no la cadena completa
**Y** sólo devuelve productos del punto de venta `P`
**Y** el evento se persiste con origen `LexicalFallback` y con `RetrievalMs` midiendo la consulta léxica

### Escenario 5: Con el flag apagado se usa la búsqueda clásica y se distingue en la telemetría

**Dado que** el punto de venta `P` no está en la lista de puntos de venta habilitados
**Cuando** el operador llama al endpoint
**Entonces** **no** se llama al gateway ni se consume ningún embedding
**Y** se responde con los resultados del buscador clásico y `aiAvailable: false`
**Y** el evento se persiste con origen `Disabled`, distinguible de `LexicalFallback` en SQL

### Escenario 6: Los tres «cero resultados» se distinguen

**Dado que** la IA responde con `low_confidence: true` y cero candidatos
**Cuando** se construye la respuesta
**Entonces** `lowConfidence` es `true` y `aiAvailable` es `true`
**Y** cuando el caso es que había candidatos y ninguno sobrevivió a la hidratación, `lowConfidence` es `false` y `aiAvailable` es `true`
**Y** cuando el caso es el camino degradado, `aiAvailable` es `false`
**Y** los tres se persisten con `ResultsCount = 0` y son separables uniendo por `TraceId` con los logs de C14

### Escenario 7: La telemetría se escribe después de truncar y nunca rompe la búsqueda

**Dado que** la lista final ya está hidratada y truncada
**Cuando** se registra el evento
**Entonces** se persiste la lista **mostrada** en orden de pantalla, no el conjunto de 60 candidatos
**Y** se persisten `SearchOrigin`, `TraceId`, `RetrievalMs`, `TotalMs` y el `searchSessionId` del cliente —o uno generado por el servidor si no viene—
**Y** `TotalMs` se captura **antes** de la escritura, para que no se mida a sí misma
**Y** si la persistencia falla, la búsqueda responde igual, con `searchEventId` nulo

### Escenario 8: El punto de venta es obligatorio y se valida por rol

**Dado que** la petición llega sin `pointOfSaleId`
**Cuando** se procesa
**Entonces** se responde **400**, porque ni `AiCallScope` ni la telemetría admiten una búsqueda sin punto de venta
**Y** si un operador pide un punto de venta al que no está asignado, se responde **403**
**Y** si un administrador pide cualquier punto de venta **activo**, la búsqueda se ejecuta
**Y** el `pos_id` que viaja al gateway sale siempre del ámbito validado, nunca del cuerpo de la petición

### Escenario 9: El coste está acotado

**Dado que** la misma consulta se repite desde el mismo punto de venta dentro de la ventana de caché
**Cuando** llega la segunda petición
**Entonces** se reutilizan los candidatos cacheados y **no** se emite una segunda llamada de embedding
**Y** la hidratación se rehace, de modo que el precio y el stock devueltos son los actuales
**Y** la clave de caché incluye el punto de venta, aunque hoy la recuperación no dependa de él
**Y** superar el límite de peticiones por usuario devuelve **429**, distinguible de una caída de la IA

### Escenario 10: Fuera de alcance explícito

**Dado que** C15 entrega el endpoint de búsqueda
**Cuando** se revisa el entregable
**Entonces** **no** hay cambios en `frontend/`, en `ai-service/` ni en `ai-service/openapi.json`
**Y** **no** hay migración de EF Core ni índice nuevo en la base de datos
**Y** `/api/v1/products/search` mantiene su comportamiento actual
**Y** **no** se ha creado `ai.query_log` ni se ha leído el esquema `ai` desde .NET
**Y** `IAiGatewayClient` no tiene diff

---

## Notas adicionales

- **Actor.** Operador de punto de venta como beneficiario final, pero sin pantalla hasta C16. El administrador puede ejercitarlo sobre cualquier punto de venta activo, que es lo que hará falta para el vídeo de entrega.

- **Por qué la ventana máxima y no la repetición.** El SQL de C14 aplica el umbral de distancia **antes** del `LIMIT`. Si vuelven menos candidatos que el `overfetch`, ató el umbral: repedir con `top_k` mayor devuelve exactamente las mismas filas y cobra un segundo embedding. Sólo aportaría algo con `top_k < 20`, y nunca por encima de 60, que es el tope de `over_retrieval_count`. Pedir 20 obtiene el máximo teórico en una llamada, y es *más barato* que repetir en el caso malo.

- **Por qué el buscador degradado no es la rama léxica del híbrido.** Son dos cosas distintas y no compiten. La rama léxica de C21 corre en Python, sobre `ai.product_document.tsv` —columna generada `to_tsvector('spanish', doc_text)` con índice GIN, construida en C05—, y su corpus incluye tipo, materiales, piedra, talla, familia, colores, estilo y ocasiones que C09 extrajo. El buscador degradado de C15 corre en .NET sobre `public."Products"`, que sólo tiene SKU, nombre y descripción, y existe para cuando `jbg-ai` **no responde**. Indexar `public` sería un segundo índice, más pobre, del mismo texto; y leer `ai` desde .NET haría que el camino degradado compartiese cuatro eslabones con la cadena que acaba de romperse.

- **Por qué sin índice GIN.** Con 1.200 productos, un GIN compraría lematización, no velocidad: el escaneo secuencial calculando `to_tsvector` está en el orden de decenas de milisegundos. La lematización se obtiene igual sin índice. Cuando el catálogo crezca un orden de magnitud, el índice es una migración futura.

- **Trampa del `tsquery`.** `plainto_tsquery` conjunta los términos. Sobre este corpus eso devuelve cero y habríamos reproducido el fallo de `Contains` con mejor tecnología. La consulta degradada debe usar **semántica OR** y ordenar por `ts_rank`, no filtrar por él.

- **Hidratar con `ProductService` es un anti-patrón aquí.** `GetInventoryQuantitiesAsync` consulta el inventario producto a producto y `MapToListDtoAsync` resuelve la URL de la foto una a una: con 60 candidatos son del orden de 120 idas y vueltas dentro de un endpoint que compite con un presupuesto de 800 ms. Además, su `AvailableQuantity` suma todos los puntos de venta asignados, que es otro dato.

- **Deuda anotada, no pagada.** `api/routers/retrieval.py` construye un `LiteLlmEmbeddingClient` por petición, así que la caché en memoria que C11 congeló nace vacía y muere con la respuesta: en recuperación no hay ni un acierto en producción. Se arregla con tres líneas en `main.py`, y le toca a **C21 o C22**, que ya trabajan en `retrieval/`. C15 mitiga por su lado con la caché de candidatos.

- **`IMemoryCache` ya está registrado** en `ServiceCollectionExtensions` (lo usa el dashboard): la caché de candidatos no añade dependencia nueva.

- **Par de zona.** No solapar con **C34**, que añadirá las rutas de asistencia y recomendación. Ya no comparten fichero de controlador —`AiController.cs` nunca existió— pero sí compartirán el servicio de búsqueda.

- **`design.md` obligatorio** en el change: siete decisiones con alternativas defendibles y coste asimétrico no caben sólo en `tasks.md`.

---

## Tareas

1. Completar los artefactos OpenSpec del change: `proposal`, **`design.md`**, specs delta (capability nueva de búsqueda asistida + `## MODIFIED` sobre `ai-search-telemetry` por `SearchOrigin.Disabled`) y `tasks`.
2. **Spike de 15 minutos**: verificar la traducción de `EF.Functions.ToTsVector` / `WebSearchToTsQuery` / `ts_rank` con Npgsql 10. Si no traduce limpiamente, caer al OR de términos sobre SKU, nombre y descripción.
3. Opciones de configuración: puntos de venta habilitados, tamaño de la ventana de candidatos, TTL de caché y límites de peticiones, validadas al arranque.
4. `SearchOrigin.Disabled` en el dominio y su reflejo en la spec viva.
5. Servicio de hidratación: consulta conjunta sobre `Product` + `Inventory` + foto principal + colección, acotada al POS.
6. Buscador degradado POS-scoped con semántica OR y orden por `ts_rank`.
7. Servicio de aplicación que orquesta el flujo completo, con caché de candidatos y el embudo en log estructurado.
8. `AiSearchController` con validación FluentValidation, política de limitación de peticiones y mapeo de errores del gateway.
9. Tests unitarios con gateway falso y `TimeProvider` inyectado; integración con Testcontainers.
10. Enlazar la HU en `Documentos/epicas.md` (EP14) durante el apply.
11. `openspec validate --all --strict` en verde antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 5 — es el primer punto del sistema RAG que toca un operador, y el que hace que C04 deje de ser código muerto
- **Urgencia (mercado / feedback):** **5** — 🔴; nunca se recorta; desbloquea C16 y C17, que cierran el hito de la Ola 2
- **Complejidad / esfuerzo:** 4 — orquestación, hidratación conjunta, degradación, caché y telemetría; sin migración y sin tocar Python
- **Riesgos y dependencias:**
  - **Corte de recall en puntos de venta de baja cobertura.** Aceptado y medido; se corrige en C22. Si la demo se hace desde `FORNELLS`, la página saldrá corta, y eso es lo esperado.
  - **Spike del full-text**: si Npgsql no traduce las funciones, hay caída controlada al OR de términos, pero conviene resolverlo el primer día.
  - **Obligación A1 de C04**: su incumplimiento no tiene síntoma. Debe haber un test que verifique que la telemetría se invoca.
  - **No paralelizar con C34** (servicio de búsqueda compartido).
  - Un `MODIFIED` sobre una spec archivada exige `openspec validate --all --strict`, no sólo la forma de un solo change.
