# HU-AIENG-004: Telemetría de búsqueda asistida — evento consulta→selección

## Formato estándar

Como **desarrollador del proyecto**, quiero **una entidad `ProductSearchEvent` que registre cada búsqueda asistida con sus resultados, sus tiempos y la selección del operador, escrita por quien conoce cada dato** **para** **que los KPIs de adopción y de calidad de recuperación estén instrumentados desde el primer día y puedan medirse con SQL en la entrega, en lugar de inferirse cuando ya sea tarde**.

---

## Descripción

Última pieza de la Ola 0 del Proyecto Final de IA (change OpenSpec `add-product-search-event-tracking` / C04, épica **EP17 — Evaluación y Observabilidad de IA**). Es el **primer change con migración de EF Core** de los seis previstos en el plan, y el único de la Ola 0 que toca el modelo de datos.

El valor no es de usuario final —esta historia no entrega pantalla— sino de **medición**. El diseño v3 §15 declara que *«los KPIs de negocio están instrumentados, no medidos»*: instrumentado significa que el dato se captura aunque nadie lo mire todavía. Sin esta tabla, seis de los KPIs de las especificaciones funcionales v2 §5.11 no son medibles ni al final del proyecto, y la comparación online entre la ruta asistida y la ruta léxica degradada —el equivalente en producción de la ablación v0 vs v3 de §11.2— no existe.

La decisión estructural de la historia es **quién escribe cada dato**. El principio del diseño §6.2 (*«.NET calcula números y decide»*) y §7.6 (el hidratador es autoridad final) se aplican también a la telemetría: la mitad de búsqueda del evento la escribe el backend, que es el único que conoce lo que realmente devolvió, si el circuito estaba abierto, cuánto tardó la recuperación y con qué `trace_id`; la mitad de selección la reporta el navegador, que es el único que sabe qué eligió la persona. Pedirle al cliente que reporte lo que el propio servidor acaba de calcular es el mismo error de categoría que fiarse de `jbg-ai` para el precio y el stock.

Esa decisión tiene un efecto de calendario buscado: **el contrato que hereda C16 se reduce a un `POST` con un solo campo en el cuerpo**. C16 es 🔴 y cae en la ola más congestionada; todo lo que se pueda sacar de ahí, se saca.

**Alcance de esta historia (sí):**

- Entidad `ProductSearchEvent` en `JoiabagurPV.Domain` con 17 columnas, enum `SearchOrigin` y su repositorio.
- Columna `Sale.SearchEventId` (uuid nullable, `ON DELETE SET NULL`) — la atribución venta↔búsqueda vive del lado de la venta.
- **Una única migración de EF Core** que crea la tabla, sus dos índices y la columna nueva de `Sales`, con las cuatro reglas de borrado declaradas a mano.
- `IProductSearchEventService` con **dos caminos de escritura**: `RecordSearchAsync` (API interna que invocará C15) y el registro de la selección.
- Proyección y truncado de la lista de resultados a JSON, y derivación del rank en el servidor.
- **Un único endpoint HTTP**: `POST /api/ai/search-events/{id}/selection`, cuerpo `{ "productId": "..." }`, respuesta `204`.
- Autorización por propiedad del evento, **sin bypass de administrador**.
- Arnés reutilizable de test de migración en `TestHelpers/`, que heredarán C07, C08, C19, C27 y C29.
- Tests unitarios del servicio, de integración con Testcontainers y de esquema.

**Fuera de alcance (no):**

- **Cualquier ruta de lectura.** No hay `GET`, ni endpoint de agregación, ni panel de KPIs, ni «módulo de analítica». El análisis del entregable se hace con SQL a mano en C39.
- `POST /api/ai/search` y la llamada a `RecordSearchAsync` desde él → **C15**.
- Panel «Buscar con ayuda», generación del identificador de episodio y envío de la selección → **C16**.
- Campo `SearchEventId` en `CreateSaleRequest` / `BulkSaleLineRequest` y su asignación en el servicio de ventas → C16 o el change que conecte el flujo.
- Política de retención o anonimización de `SearchText`. Se declara como limitación; el `SET NULL` la deja operable en el futuro.
- Frontend: la SPA no ve nada de este change.
- `ai-service/`: no se toca, y el snapshot `ai-service/openapi.json` no cambia.

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Principio rector | **Generoso en esquema, mínimo en API.** El esquema consume 1 de los 6 slots de migración del plan y es caro de cambiar; el DTO no tiene ni un cliente y es gratis. Si dudo si una columna hará falta, entra; si dudo si un campo del DTO hará falta, se queda fuera |
| Quién escribe la búsqueda | **El servidor**, desde C15, vía servicio interno. Es el único que conoce la lista realmente devuelta, el origen, el `trace_id` y la latencia real de recuperación |
| Quién escribe la selección | **El cliente**, con un solo campo. Es lo único que el navegador sabe de verdad |
| Granularidad | **Una fila por consulta ejecutada**, agrupadas por `SearchSessionId` que genera el cliente por episodio. Reformulación y abandono se derivan sin columnas extra: una fila sin selección con hermanas posteriores es una reformulación; sin hermanas, un abandono |
| Ruta | `POST /api/ai/search-events/{id}/selection`. **Divergencia respecto a specs v2 §5.9** (`/api/products/search-events`): un evento sin selección y sin resultados no pertenece a ningún producto, así que anidarlo bajo `/products` miente sobre la propiedad del recurso. `api/ai/*` es el namespace que ya usan C15, C19 y C34 |
| Controller | Uno por recurso (`AiSearchEventsController`), no un `AiController` compartido: cuatro changes van a añadir rutas bajo `api/ai/*` con dos desarrolladores en paralelo |
| Versionado de la ruta | **Sin versión**, como los 18 controllers existentes. El criterio del máster (*versionar desde el día uno*) ya se aplica donde compra algo: la frontera .NET↔Python, con `/v1` y snapshot congelado. Entre React y .NET no hay despliegues independientes ni contrato negociado. `BaseController` declara un `api/v1/[controller]` que **nadie hereda**: es andamiaje muerto y no se toca en este change |
| Enlace venta↔búsqueda | **`Sale.SearchEventId`**, no `ProductSearchEvent.CreatedSaleId`. **Divergencia respecto a specs v2 §5.8**: la atribución la declara el hecho derivado en el instante en que nace, en el mismo `INSERT`, sin llamadas de seguimiento. Con el checkout masivo la diferencia es de N llamadas extra contra N campos opcionales en una petición que ya se envía |
| Regla de borrado hacia la venta | **`SET NULL`**, declarado a mano. Nunca `Cascade` (borrar telemetría no puede borrar ventas) ni `Restrict` (bloquearía cualquier retención futura). Las otras tres claves foráneas van a `Restrict` explícito, porque el default de EF para relaciones obligatorias es **`Cascade`** y aquí significaría *«borrar un empleado borra la evidencia de cómo se usó el sistema»* |
| Un `SearchEventId` desconocido | Degrada la atribución a nula. **Nunca hace fallar la venta.** Regla especificada aquí aunque la implemente el change que conecte la escritura |
| Relojes | `SearchDurationMs` de specs v2 era ambiguo y se desdobla en **`RetrievalMs`** (obtener candidatos, agnóstico del origen) y **`TotalMs`**; su diferencia mide el coste de la hidratación, que es una cifra que el proyecto quiere poder defender |
| Tiempo hasta la selección | **No lo calcula el cliente.** El servidor sella `SelectedAt` al recibir la selección; el KPI de episodio sale de `SelectedAt − min(CreatedAt)` de la sesión. Un delta calculado en cliente mediría solo el último tramo tras varias reformulaciones |
| `UpdatedAt` como `SelectedAt` | **No.** `UpdatedAt` lo pisa cualquier escritura futura (un backfill, una anonimización) y el KPI empezaría a mentir en silencio. Reutilizar una columna de auditoría como hecho de negocio corrompe la tabla sin ruido |
| Qué se guarda de cada resultado | Solo **lo irrecuperable**: `productId`, `sku`, `rank`, `score` y `matchReasons`. Materiales, familia y variante se reconstruyen con un `JOIN`. El `score` es el caso de libro —dependía del índice, del modelo de embeddings y de los pesos de ese día—, misma lógica por la que `Sale.Price` congela el precio |
| Qué lista se guarda | **La mostrada**, no los candidatos crudos. Bajo este modelo es imposible equivocarse: escribe C15 en el mismo método donde acaba de truncar |
| Tipo de las columnas JSON | **`jsonb`**, no `text`. El precedente de `ProductPhotoEmbedding.EmbeddingVector` no aplica: aquel es un blob que nunca se consulta por dentro, esta columna existe para agregarse. Además Postgres valida en la escritura, lo que hace **imposible por construcción** el bug de truncar la cadena JSON |
| Mapeo EF del JSON | Propiedad `string` + `HasColumnType("jsonb")`, sin `ToJson()`. Nunca se lee desde C#, así que el tipado no compra nada y complica el truncado |
| Convención de nombres del JSON | **`camelCase`**, fijado en el spec. Es una decisión de una vía: cambiarla después rompe en silencio todas las consultas del script de C39 |
| Truncado | **Por número de entradas, con tope holgado (50). Nunca por bytes.** Es un guardarraíl contra un bug propio, no una funcionalidad: con `top_k` en torno a 10-20 no salta jamás en operación normal |
| `ResultsCount` | Columna entera con los resultados **realmente mostrados**. El KPI más consultado (`% consultas sin resultado`) se calcula sin parsear JSON, y el truncado queda detectable comparándola con `jsonb_array_length` |
| `SelectedFromRank` | **Lo deriva el servidor** buscando el producto en la lista guardada. El cliente no lo envía. El invariante deja de necesitar validación porque deja de poder romperse, y el rank pasa a medir la calidad del retriever y no el orden de la UI |
| Producto fuera de la lista | Se guarda la selección con **rank nulo** y aviso en el log; no se rechaza. Un nulo no miente y cualquier agregación lo ignora; un evento que parece abandonado sin serlo corrompe el KPI de conversión |
| Autorización de la selección | Por **propiedad del evento**, y **sin bypass de administrador** — desviación deliberada del patrón de la casa. Ningún flujo legítimo hace que un admin complete el evento de otra persona, y permitirlo deja corromper telemetría sin rastro |
| Garantía de punto de venta | La aporta la **firma del servicio**: recibe un `AiCallScope`, cuyo único constructor exige un POS ya validado (patrón de C03). La fila no puede existir para un POS al que el usuario no tiene acceso, porque la búsqueda tampoco pudo |
| El servicio nunca lanza | `RecordSearchAsync` devuelve `Guid?` y **traga cualquier fallo de persistencia**, registrándolo. Convierte en garantía verificable lo que si no sería una obligación que C15 podría incumplir: *el sistema nunca se cae por culpa de medir la IA* |
| Idempotencia de la selección | **Última escritura gana**, sin 409. Un operador que elige el 3.º, vuelve y elige el 1.º ha elegido el 1.º |
| Longitud de `SearchText` | **`varchar(500)`**, derivado del contrato congelado `ai-service/openapi.json` (`query.maxLength = 500`), no elegido a ojo |
| Privacidad del texto de consulta | Se hereda la regla y el test de C03: **no aparece en ningún log por encima de `Debug`**. No procede el pipeline de anonimización del máster: este texto nunca entra al espacio vectorial ni se recupera semánticamente, así que el control de acceso sí basta |
| Índices | **Dos, no más**: `(PointOfSaleId, CreatedAt)` en ese orden —es la consulta dominante y el orden inverso no serviría— y `(CreatedAt)`. A ~3.000 filas en la entrega ningún índice mejora nada; se ponen porque añadirlos después cuesta un slot de migración y tenerlos no cuesta nada |
| Test de migración | Dos capas. **Capa 1 reutilizable**: test de desfase modelo↔migración (sin base de datos) y ayudante de aserciones sobre `information_schema`/`pg_indexes`. **Capa 2**: las seis aserciones propias de C04. Lo heredan los cinco 🗄️ restantes |
| Reversibilidad de la migración | **No se prueba**, con el motivo escrito: a diferencia del lado Alembic (C05), esta migración es generada y su `Down` no es código nuestro. Probarlo exigiría un contenedor propio y rompería el aislamiento del fixture compartido |

**Referencias:**
[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C04),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.2 frontera, §6.4 degradación, §7.6 hidratación, §11.2 ablations, §15 limitaciones),
[joiabagur-ia-especificaciones-funcionales-v2.md](../../Proyecto%20Final%20AIEng/joiabagur-ia-especificaciones-funcionales-v2.md) (§5.8 modelo de datos, §5.9 endpoints, §5.11 KPIs),
[epicas.md](../../epicas.md) (EP17),
[modelo-de-datos.md](../../modelo-de-datos.md),
[HU-AIENG-003.md](HU-AIENG-003.md),
specs vivas `openspec/specs/access-control/spec.md` y `openspec/specs/ai-gateway-client/spec.md`,
contrato congelado `ai-service/openapi.json`,
change OpenSpec `openspec/changes/add-product-search-event-tracking/` y su ticket técnico.

---

## Criterios de Aceptación

### Escenario 1: Una búsqueda asistida queda registrada con todo lo que solo el servidor conoce
**Dado que** existe un ámbito de llamada con usuario y punto de venta ya validados
**Cuando** se invoca el registro de búsqueda con la consulta, los filtros efectivos, la lista mostrada, el origen, el identificador de traza y los dos tiempos
**Entonces** se persiste una fila con la consulta, los filtros y los resultados en columnas `jsonb`
**Y** el instante de la consulta, el origen, el identificador de traza y las dos duraciones quedan guardados
**Y** se devuelve el identificador del evento para que quien llame lo entregue al cliente

### Escenario 2: Una búsqueda degradada también se registra, y se distingue
**Dado que** el circuito hacia el servicio de IA está abierto y los resultados vienen del buscador léxico existente
**Cuando** se registra la búsqueda
**Entonces** la fila queda con origen `LexicalFallback`
**Y** la duración de recuperación mide la consulta léxica, no una llamada al servicio de IA
**Y** las dos rutas quedan comparables entre sí agrupando por origen

### Escenario 3: Una búsqueda sin resultados se registra igual
**Dado que** la recuperación no devuelve ningún candidato
**Cuando** se registra la búsqueda
**Entonces** la fila se persiste con el contador de resultados a cero
**Y** la columna de resultados contiene una lista vacía, no un nulo
**Y** el KPI de consultas sin resultado puede calcularse sin abrir el JSON

### Escenario 4: Un fallo al persistir la telemetría no propaga error a quien llama
**Dado que** la escritura del evento falla por cualquier motivo de base de datos
**Cuando** se invoca el registro de búsqueda
**Entonces** el método no lanza ninguna excepción
**Y** devuelve un identificador nulo
**Y** el fallo queda registrado en el log con nivel de error

### Escenario 5: El rank de la selección lo deriva el servidor
**Dado que** un evento tiene guardada una lista de resultados en orden
**Cuando** llega la selección indicando únicamente el identificador de producto
**Entonces** el rank se calcula como la posición de ese producto en la lista guardada, empezando en 1
**Y** el cliente no ha enviado ningún rank ni ninguna duración

### Escenario 6: Una selección sobre un producto ausente de la lista se registra con rank nulo
**Dado que** el identificador de producto recibido no aparece en los resultados guardados
**Cuando** se procesa la selección
**Entonces** el producto seleccionado y el instante de selección sí se guardan
**Y** el rank queda nulo
**Y** se emite un aviso en el log, porque esa situación siempre indica un defecto
**Y** el evento **no** queda como abandonado

### Escenario 7: Una selección repetida conserva la última
**Dado que** un evento ya tiene una selección registrada
**Cuando** llega una segunda selección sobre otro producto de la misma lista
**Entonces** el evento queda con el segundo producto y su rank correspondiente
**Y** la respuesta es correcta, sin conflicto

### Escenario 8: Nadie completa el evento de otra persona, tampoco un administrador
**Dado que** un evento pertenece a un operador
**Cuando** otro usuario intenta registrar su selección
**Entonces** el sistema responde 403 y no modifica la fila
**Y** el resultado es el mismo si quien lo intenta tiene rol de administrador

### Escenario 9: La lista guardada se limita en número de entradas, no en bytes
**Dado que** se registra una búsqueda con más resultados mostrados que el tope de almacenamiento
**Cuando** se persiste el evento
**Entonces** la columna de resultados contiene exactamente el tope de entradas, en orden de rank
**Y** el contador de resultados refleja los realmente mostrados, no los guardados
**Y** el JSON almacenado sigue siendo válido y consultable

### Escenario 10: Las consultas de un mismo episodio quedan agrupadas
**Dado que** un operador reformula su consulta tres veces antes de elegir
**Cuando** las tres búsquedas se registran con el mismo identificador de episodio
**Entonces** existen tres filas agrupables por ese identificador
**Y** solo la última lleva selección
**Y** las dos primeras son distinguibles de un abandono real por tener filas hermanas posteriores

### Escenario 11: Una venta puede declarar de qué búsqueda procede
**Dado que** la tabla de ventas tiene la columna de atribución
**Cuando** se crea una venta indicando el evento de búsqueda de origen
**Entonces** la venta queda enlazada a ese evento
**Y** el porcentaje de ventas iniciadas desde búsqueda asistida se obtiene de la tabla de ventas sin ningún `JOIN`

### Escenario 12: Borrar telemetría no destruye ni bloquea ventas
**Dado que** existen ventas enlazadas a eventos de búsqueda
**Cuando** se eliminan esos eventos
**Entonces** las ventas siguen existiendo con la atribución a nulo
**Y** el borrado no queda bloqueado por la restricción

### Escenario 13: El texto de la consulta no sube por encima de `Debug`
**Dado que** se registra una búsqueda cuya consulta es texto libre escrito por un operador
**Cuando** se emiten los eventos de log del registro
**Entonces** el texto aparece únicamente en nivel `Debug`
**Y** ningún evento de nivel `Information` o superior lo contiene

### Escenario 14: La migración crea el esquema que se pretendía, no uno que solo se le parece
**Dado que** la migración se ha aplicado sobre una base de datos limpia
**Cuando** se inspecciona el catálogo de PostgreSQL
**Entonces** las dos columnas de documentos son de tipo `jsonb` y no `text`
**Y** el índice compuesto lleva punto de venta y fecha **en ese orden**
**Y** la columna de texto de consulta admite 500 caracteres
**Y** la regla de borrado hacia la venta es «poner a nulo» y las otras tres son «restringir»
**Y** si alguien modifica la configuración de EF sin generar migración, el test de desfase falla

### Escenario 15: Fuera de alcance explícito
**Dado que** esta historia está implementada
**Cuando** se revisa el entregable
**Entonces** no existe ninguna ruta de lectura sobre los eventos: ni `GET`, ni agregación, ni panel
**Y** no existe `POST /api/ai/search` ni ninguna llamada real al servicio de registro desde un endpoint de búsqueda
**Y** el frontend no ha cambiado
**Y** `ai-service/` y su snapshot OpenAPI no se han tocado
**Y** el flujo de creación de venta no acepta todavía el identificador de búsqueda: la columna existe, el camino de escritura no

---

## Notas adicionales

- **Actor:** historia de plataforma para el equipo del Proyecto Final. No hay pantalla; los beneficiarios directos son C15 (que escribirá a través del servicio), C16 (que enviará la selección) y C39 (que consultará la tabla para el README).

- **Por qué se antepone a C07 pese a la regla 2 del plan.** C04 es 🟢 y no desbloquea nada; C07 desbloquea C12, que es 🔴. Por la letra del plan, C07 debería ir antes. El motivo para invertirlo es que **la primera migración del proyecto paga un coste fijo de utillaje** —el arnés de test de esquema— que las otras cinco no pagan, y ese coste debe caer en el change sin dependientes y no en el que abre la ruta crítica. Si finalmente se coge C07 primero, el arnés viaja con C07 y C04 lo hereda: la decisión es de orden, no de propiedad.

- **Bloqueo de la migración única.** Mientras C04 esté abierto, la regla 4 del plan impide abrir C07, C08, C19, C27 y C29. La cola limpia para el otro desarrollador es C05 o C06, ambos Python y ambos de la ola en curso, así que el bloqueo no fuerza trabajo de relleno. Hay que anunciarlo antes de empezar.

- **Tres divergencias respecto a las especificaciones funcionales v2 §5.8-5.9**, todas con el mismo motivo de fondo: el documento funcional se escribió antes de que existieran la arquitectura de dos servicios y el flujo de carrito. Son la ruta (§5.9), el lado del enlace venta↔búsqueda y el desdoble del campo de duración (§5.8). Las tres están recogidas en el proposal del change.

- **El modelo elegido mató tres obligaciones que el modelo alternativo habría creado.** Bajo un modelo donde el cliente escribe el evento entero, C16 habría tenido que acordarse de emitir en abandono, de enviar el rank 1-based de la lista mostrada y de reportar el origen de los resultados. Las tres desaparecieron al mover la escritura al servidor: dejaron de depender de que alguien se acordara.

- **La obligación crítica es que C15 llame al servicio.** Es la única cuyo incumplimiento deja el change entero sin efecto **y sin síntoma**: todo compilaría, todos los tests pasarían y la tabla estaría vacía en septiembre. Por eso se recoge en el proposal y además se anota en la ficha de C15 del plan de changes.

- **Volumen esperado:** unas 200 filas al día (~5 operadores × ~40 búsquedas), en torno a 3.000 filas en la fecha de entrega y ~70.000 en un año de operación real. A esa escala ningún índice mejora nada medible y ninguna consulta analítica sufre. Los dos índices se ponen por opción de futuro, no por rendimiento, y conviene que quede escrito para que nadie añada cuatro más.

- **Limitaciones declaradas:** no hay política de retención ni anonimización de `SearchText`, y el texto puede recoger incidentalmente datos de terceros —los puntos de venta son hoteles y un operador puede teclear una referencia a un huésped—. Las medidas proporcionadas son el tope de longitud, la regla de nivel de log heredada de C03 y la ausencia de ruta de lectura. La supresión por usuario es operable gracias al `SET NULL` hacia la venta.

- **OpenSpec:** se implementa vía el change `add-product-search-event-tracking` (proposal → design → specs → tasks → apply → verify → archive). Las diez obligaciones hacia C15 y C16 van en el **proposal**, nunca en `specs/`: un requisito especificado y no implementado haría fallar la verificación del change.

- **Línea de corte prevista.** Si la sesión se desborda (regla 5 del plan), el corte es: primero **esquema + migración + arnés**, que libera el slot de migración y es archivable por sí solo; después **servicio + endpoint + tests**, que no lleva migración y convive sin colisionar con el C07 del compañero. Las tareas van ordenadas para que ese corte sea mecánico y no improvisado.

---

## Tareas

> Ordenadas para que las tareas 1-5 formen una mitad completa y archivable por sí sola (esquema + migración + arnés), y las 6-11 la segunda mitad (escritura + endpoint), por si hay que aplicar la línea de corte.

1. Definir `ProductSearchEvent` y el enum `SearchOrigin` con valores explícitos en `JoiabagurPV.Domain`, y añadir `SearchEventId` a `Sale`.
2. Escribir las dos configuraciones de EF Core: tipos `jsonb`, longitud del texto de consulta derivada del contrato, nulabilidades, los dos índices con el orden correcto y **las cuatro reglas de borrado declaradas a mano**, sin propiedades de navegación.
3. Registrar el `DbSet` y el repositorio, y generar **la única migración** del change.
4. Construir la capa 1 del arnés en `TestHelpers/`: test de desfase modelo↔migración (sin base de datos) y ayudante de aserciones sobre `information_schema` y `pg_indexes`. **Solo lo que C04 necesita hoy; ningún método «por si acaso».**
5. Escribir la capa 2: las aserciones de esquema propias de este change, sobre el `TestDatabaseFixture` existente.
6. Implementar `IProductSearchEventService.RecordSearchAsync`, recibiendo `AiCallScope`, devolviendo `Guid?` y sin propagar nunca una excepción de persistencia.
7. Implementar la proyección de resultados a JSON con el truncado por número de entradas y el contador de resultados mostrados.
8. Implementar el registro de la selección: derivación del rank desde la lista guardada, sellado del instante, última escritura gana y rank nulo cuando el producto no aparece.
9. Implementar `AiSearchEventsController` con el único endpoint, la comprobación de propiedad **sin bypass de administrador** y respuesta `204`.
10. Escribir los tests unitarios del servicio (truncado, contador, derivación de rank, producto ausente, no propagación de fallos) y los de integración con Testcontainers (persistencia completa, 403 de propiedad, `SET NULL` al borrar eventos).
11. Añadir el fichero `.http` en `backend/api-tests/` y verificar `dotnet build` y `dotnet test` en verde sin regresión.

---

## Estimaciones y atributos de priorización

> Valores propuestos a partir de la guía de estimación de [Procedimiento-TicketsTrabajo.md](../../Procedimientos/Procedimiento-TicketsTrabajo.md) (§4.6). **Pendientes de validar** en la sesión de refinamiento del equipo.

- **Puntos de historia:** **5** — la lógica es sencilla y no hay algoritmo, pero la superficie es ancha (cuatro capas más tests), incluye la primera migración del Proyecto Final y arrastra el coste fijo del arnés de esquema, que se paga una sola vez para seis changes.
- **Impacto en usuario / Valor de negocio:** **2** — nulo de forma directa. El valor aparece en la entrega, cuando los KPIs se pueden calcular en lugar de estimarse.
- **Urgencia (mercado / feedback):** **2** — 🟢, no bloquea a nadie. Su urgencia real es indirecta: hacerlo ahora saca trabajo de C16, que sí es 🔴 y cae en la ola congestionada.
- **Complejidad / Esfuerzo:** **3** — la dificultad no está en el código sino en las decisiones de esquema, que son de una sola vía: el tipo `jsonb`, el orden del índice compuesto y las reglas de borrado fallan **sin dar ningún error** y se descubren semanas después.
- **Riesgos y dependencias:**
  - **Sin prerrequisitos hacia atrás.** Pero **sí un prerrequisito hacia adelante sobre C15**, que es una propiedad distinta y hay que nombrarla: si C15 no invoca `RecordSearchAsync`, C04 es código muerto sin síntoma → mitigado con la obligación escrita en el proposal y anotada en la ficha de C15 del plan.
  - **Riesgo:** el arnés de migración se sobredimensiona y consume la sesión — es literalmente el enunciado que produce un DSL de aserciones que nadie pidió → mitigado con el guardarraíl en `tasks.md` y con la línea de corte predefinida.
  - **Riesgo:** colisión con C07 por la regla de migración única → mitigado anunciando antes de empezar y cerrando primero la mitad de esquema.
  - **Riesgo:** el tipo `jsonb` se pierde por olvidar la configuración explícita y la columna nace `text`; nada falla hasta que C39 intente consultarla, con seis semanas de datos dentro → mitigado con la aserción de esquema del escenario 14.
  - **Riesgo:** el default de EF para las claves foráneas obligatorias es `Cascade`, lo que significaría que borrar un usuario o un punto de venta evapora su histórico → mitigado declarando las cuatro reglas a mano y verificándolas en el arnés.
  - **Riesgo:** las tres divergencias respecto a specs v2 se descubren en la revisión → mitigado con una sección propia en el proposal.
  - No depende del export del catálogo real, ni del esquema `ai`, ni del proveedor de modelos, ni de C15: compila y se prueba de forma aislada.
