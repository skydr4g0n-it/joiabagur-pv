> **Línea de corte.** Los grupos 1 a 3 forman una mitad completa y archivable por sí sola —esquema, migración y arnés—, que libera el slot de migración para C07. Los grupos 4 a 7 son la segunda mitad y no llevan migración, así que conviven con el C07 del compañero sin colisionar. Si la sesión se desborda (regla 5 del plan), el corte es aquí y es mecánico.

> **Guardarraíl del arnés.** En el grupo 3 se construyen **únicamente** las aserciones que este change necesita hoy. Ningún método «por si acaso»: C07, C08, C19, C27 y C29 extenderán la capa común cuando sepan qué necesitan. *«Construye una herramienta que heredarán cinco changes»* es literalmente el enunciado que produce un DSL que nadie pidió y que se come la sesión.

## 1. Dominio y modelo

- [x] 1.1 Anunciar al compañero la apertura de la migración (regla 3 del plan): mientras este change esté abierto, C07, C08, C19, C27 y C29 quedan bloqueados y su cola limpia es C05 o C06 — **acción humana, fuera del alcance del agente**
- [x] 1.2 Crear el enum `SearchOrigin` en `JoiabagurPV.Domain/Enums/` con valores explícitos (`Assisted = 1`, `LexicalFallback = 2`), no implícitos por orden de declaración
- [x] 1.3 Crear la entidad `ProductSearchEvent : BaseEntity` en `JoiabagurPV.Domain/Entities/` con las catorce propiedades propias, **sin propiedades de navegación** hacia usuario, punto de venta, producto ni venta
- [x] 1.4 Añadir la propiedad `SearchEventId` (`Guid?`) a `Sale`, sin navegación inversa desde el evento
- [x] 1.5 ~~Crear `IProductSearchEventRepository`~~ → **descartado durante la aplicación.** `IRepository<T>` ya expone `GetByIdAsync`, `AddAsync` y `UpdateAsync`, que es todo lo que necesitan los dos caminos de escritura, y está registrado genéricamente en el contenedor. Una interfaz dedicada sería un marcador vacío más una línea de DI sin comportamiento propio; se usa `IRepository<ProductSearchEvent>` directamente

## 2. Persistencia y migración

- [x] 2.1 Escribir `ProductSearchEventConfiguration`: `FiltersJson` y `ResultsJson` con tipo de columna `jsonb` declarado a mano, `SearchText` con la longitud tomada de `query.maxLength` en `ai-service/openapi.json`, `TraceId` acotado, y la nulabilidad exacta de las tres columnas de selección y de las dos duraciones
- [x] 2.2 Declarar en esa configuración los dos índices analíticos: el compuesto con `PointOfSaleId` **antes** de `CreatedAt`, y el simple sobre `CreatedAt`. *Nota al aplicar: EF añade por convención un índice por clave foránea (usuario y producto seleccionado); se conservan porque las reglas de borrado restrictivas los necesitan para no degradar a recorrido secuencial. Ver la precisión en la decisión 12 del design*
- [x] 2.3 Declarar a mano las tres reglas de borrado salientes del evento —usuario, punto de venta y producto seleccionado— como restrictivas, sin depender del comportamiento por defecto, que para relaciones obligatorias es en cascada
- [x] 2.4 Ampliar `SaleConfiguration` con la relación hacia el evento y su regla de borrado **poner a nulo**; comprobar que el índice que EF genera sobre la columna nueva queda en la migración y no se elimina
- [x] 2.5 Registrar el `DbSet<ProductSearchEvent>` en `ApplicationDbContext`. *Sin repositorio dedicado, por 1.5: se usa `IRepository<ProductSearchEvent>`, ya registrado genéricamente*
- [x] 2.6 Generar **la única migración** del change y revisar el `.cs` generado línea a línea: tipos de columna, orden de las columnas del índice compuesto y las cuatro reglas de borrado. **Verificado**: `jsonb` en las dos columnas de documento, `character varying(500)`, índice compuesto en el orden correcto, tres `Restrict` salientes y `SetNull` en `FK_Sales_ProductSearchEvents_SearchEventId`

## 3. Arnés de verificación de esquema

- [x] 3.1 Escribir en `JoiabagurPV.Tests/TestHelpers/` el ayudante de aserciones sobre `information_schema` y `pg_indexes`, apoyado en la cadena de conexión que ya expone `TestDatabaseFixture`: existencia y tipo de columna, nulabilidad, índice con columnas en orden, y regla de borrado de una clave foránea
- [x] 3.2 Escribir el test de desfase entre el modelo y el snapshot de migraciones. **No debe necesitar base de datos**: compara dos modelos en memoria, así que es un test unitario de milisegundos que corre en cada build. *Nota: el espacio de nombres no puede llamarse `...UnitTests.Infrastructure`, porque dentro de él la directiva `using Microsoft.EntityFrameworkCore.Infrastructure` no resuelve; se usa `...UnitTests.Persistence`*
- [x] 3.3 Escribir las aserciones de esquema propias de este change: los dos tipos `jsonb`, la longitud del texto de consulta, el orden del índice compuesto, la nulabilidad de las columnas de selección y las cuatro reglas de borrado — **21 tests en verde**
- [x] 3.4 Verificar que el arnés **falla** si se altera a propósito el tipo de una columna JSON o el orden del índice compuesto, y revertir. **Verificado** con un test desechable que afirmaba lo contrario en tres puntos: el ayudante devolvió `jsonb`, `SET NULL` y el orden `PointOfSaleId, CreatedAt` reales, los tres fallaron como debían, y se borró

## 4. Servicio de registro

- [x] 4.1 Definir `IProductSearchEventService` en `JoiabagurPV.Application/Interfaces/`, con el registro de búsqueda recibiendo `AiCallScope` y devolviendo `Guid?`, y el registro de selección
- [x] 4.2 Implementar la proyección de la lista mostrada a JSON: `{ productId, sku, rank, score, matchReasons }` en `camelCase`, en orden de rank 1-based
- [x] 4.3 Implementar el truncado **por número de entradas**, con tope holgado sobre cualquier página plausible, y `ResultsCount` guardando siempre los mostrados reales
- [x] 4.4 Implementar el registro de búsqueda de modo que **absorba cualquier fallo de persistencia**, lo registre a nivel de error y devuelva un identificador ausente. Nunca lanza
- [x] 4.5 Generar el identificador de episodio en el servidor cuando el llamante no lo aporte, para que la columna nunca quede vacía
- [x] 4.6 Implementar el registro de selección: derivación del rank desde la lista guardada, sellado del instante con el reloj del servidor, última escritura gana, y rank nulo con aviso cuando el producto no aparece en la lista
- [x] 4.7 Confinar el texto de consulta a nivel de depuración en todos los eventos de log del servicio, siguiendo la regla que C03 ya dejó establecida y probada
- [x] 4.8 Registrar el servicio en el contenedor de dependencias

## 5. Endpoint

- [x] 5.1 Crear el DTO de selección con su único campo y el validador de FluentValidation correspondiente
- [x] 5.2 Crear `AiSearchEventsController` con ruta explícita `api/ai/search-events` y `[Authorize]` a nivel de clase; **sin versión** en la ruta y **sin heredar de `BaseController`**, cuyo helper de creación apunta a una ruta de lectura que este change no tiene
- [x] 5.3 Implementar el endpoint de selección: comprobación de propiedad del evento **sin bypass de administrador**, 403 si no es suyo, 404 si el evento no existe, 204 en éxito
- [x] 5.4 Añadir `backend/api-tests/ai-search-events.http` y su entrada en el README de esa carpeta

## 6. Tests

- [x] 6.1 Unitarios del servicio: persistencia con los campos del servidor, origen degradado distinguible, búsqueda sin resultados con contador a cero y lista vacía, truncado que conserva el contador real
- [x] 6.2 Unitarios del servicio: derivación del rank desde la lista guardada, producto ausente que persiste con rank nulo, selección repetida que conserva la última
- [x] 6.3 Unitario: el registro de búsqueda **no lanza** cuando la persistencia falla y devuelve identificador ausente
- [x] 6.4 Unitario: el texto de consulta no aparece en ningún evento de log de nivel información o superior
- [x] 6.5 Integración con Testcontainers: 403 por evento ajeno y 403 cuando quien llama es administrador y no propietario
- [x] 6.6 Integración con Testcontainers: borrar eventos deja las ventas en pie con la atribución a nula y sin bloqueo. *Se borra con SQL directo a propósito: así se comprueba la restricción de la base de datos y no el arreglo en memoria de EF, que anularía la referencia aunque el esquema no estuviera de acuerdo*
- [x] 6.7 Integración que hace de C16: construir el payload a partir de un `AiSearchResponse` real usando los helpers de C03 y comprobar la fila completa. **Proyección resuelta en 9 líneas**, por debajo del umbral. *Hallazgo: `jsonb` normaliza el documento —reordena claves y reescribe separadores—, así que la aserción se hace sobre el JSON parseado y no sobre el texto crudo, que estaría comprobando el formateo de PostgreSQL*
- [x] 6.8 Verificar `dotnet build` y `dotnet test` sin regresión. **Build: 0 errores.** Tras cerrar los huecos del verify: 633 tests, 51 fallos, frente a **585 con 52 en HEAD sin estos cambios** (medido con la rama limpia). Los 48 tests nuevos pasan y **ninguna clase de C04 aparece entre los fallos**. El recuento oscila entre 46 y 52 en ejecuciones del mismo código por la familia de datos generados; el diagnóstico completo, en [qa.md](qa.md) §4 y en `Documentos/testing-backend.md`

## 7. Cierre

- [x] 7.1 Anotar la obligación A1 en la ficha de C15 de `Documentos/Proyecto Final AIEng/proyecto-final-plan-changes-openspec.md` si no está ya: **es la única obligación cuyo incumplimiento deja este change sin efecto y sin síntoma**
- [x] 7.2 Actualizar `Documentos/modelo-de-datos.md` con la entidad, la columna nueva de `Sale`, los dos índices y las cuatro reglas de borrado
- [x] 7.3 Marcar HU-AIENG-004 como hecha en `Documentos/epicas.md`
- [x] 7.4 Ejecutar `openspec validate --all --strict` y comprobar `0 failed` — la forma de un solo change no basta, porque un change puede estar verde con las specs vivas rotas. **31 passed, 0 failed**
