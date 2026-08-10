> **Línea de corte.** Los grupos 1 a 3 forman una mitad completa y archivable por sí sola —esquema, migración y arnés—, que libera el slot de migración para C07. Los grupos 4 a 7 son la segunda mitad y no llevan migración, así que conviven con el C07 del compañero sin colisionar. Si la sesión se desborda (regla 5 del plan), el corte es aquí y es mecánico.

> **Guardarraíl del arnés.** En el grupo 3 se construyen **únicamente** las aserciones que este change necesita hoy. Ningún método «por si acaso»: C07, C08, C19, C27 y C29 extenderán la capa común cuando sepan qué necesitan. *«Construye una herramienta que heredarán cinco changes»* es literalmente el enunciado que produce un DSL que nadie pidió y que se come la sesión.

## 1. Dominio y modelo

- [ ] 1.1 Anunciar al compañero la apertura de la migración (regla 3 del plan): mientras este change esté abierto, C07, C08, C19, C27 y C29 quedan bloqueados y su cola limpia es C05 o C06
- [ ] 1.2 Crear el enum `SearchOrigin` en `JoiabagurPV.Domain/Enums/` con valores explícitos (`Assisted = 1`, `LexicalFallback = 2`), no implícitos por orden de declaración
- [ ] 1.3 Crear la entidad `ProductSearchEvent : BaseEntity` en `JoiabagurPV.Domain/Entities/` con las catorce propiedades propias, **sin propiedades de navegación** hacia usuario, punto de venta, producto ni venta
- [ ] 1.4 Añadir la propiedad `SearchEventId` (`Guid?`) a `Sale`, sin navegación inversa desde el evento
- [ ] 1.5 Crear `IProductSearchEventRepository` en `JoiabagurPV.Domain/Interfaces/Repositories/`, siguiendo el patrón de los repositorios existentes

## 2. Persistencia y migración

- [ ] 2.1 Escribir `ProductSearchEventConfiguration`: `FiltersJson` y `ResultsJson` con tipo de columna `jsonb` declarado a mano, `SearchText` con la longitud tomada de `query.maxLength` en `ai-service/openapi.json`, `TraceId` acotado, y la nulabilidad exacta de las tres columnas de selección y de las dos duraciones
- [ ] 2.2 Declarar en esa configuración los dos índices: el compuesto con `PointOfSaleId` **antes** de `CreatedAt`, y el simple sobre `CreatedAt`. Ninguno más
- [ ] 2.3 Declarar a mano las tres reglas de borrado salientes del evento —usuario, punto de venta y producto seleccionado— como restrictivas, sin depender del comportamiento por defecto, que para relaciones obligatorias es en cascada
- [ ] 2.4 Ampliar `SaleConfiguration` con la relación hacia el evento y su regla de borrado **poner a nulo**; comprobar que el índice que EF genera sobre la columna nueva queda en la migración y no se elimina
- [ ] 2.5 Registrar el `DbSet<ProductSearchEvent>` en `ApplicationDbContext` e implementar el repositorio en `JoiabagurPV.Infrastructure`
- [ ] 2.6 Generar **la única migración** del change y revisar el `.cs` generado línea a línea: tipos de columna, orden de las columnas del índice compuesto y las cuatro reglas de borrado. Es el fichero que nadie lee en la revisión y donde los errores no dan error

## 3. Arnés de verificación de esquema

- [ ] 3.1 Escribir en `JoiabagurPV.Tests/TestHelpers/` el ayudante de aserciones sobre `information_schema` y `pg_indexes`, apoyado en la cadena de conexión que ya expone `TestDatabaseFixture`: existencia y tipo de columna, nulabilidad, índice con columnas en orden, y regla de borrado de una clave foránea
- [ ] 3.2 Escribir el test de desfase entre el modelo y el snapshot de migraciones. **No debe necesitar base de datos**: compara dos modelos en memoria, así que es un test unitario de milisegundos que corre en cada build
- [ ] 3.3 Escribir las aserciones de esquema propias de este change: los dos tipos `jsonb`, la longitud del texto de consulta, el orden del índice compuesto, la nulabilidad de las columnas de selección y las cuatro reglas de borrado
- [ ] 3.4 Verificar que el arnés **falla** si se altera a propósito el tipo de una columna JSON o el orden del índice compuesto, y revertir. Un arnés que nunca ha fallado no está probado

## 4. Servicio de registro

- [ ] 4.1 Definir `IProductSearchEventService` en `JoiabagurPV.Application/Interfaces/`, con el registro de búsqueda recibiendo `AiCallScope` y devolviendo `Guid?`, y el registro de selección
- [ ] 4.2 Implementar la proyección de la lista mostrada a JSON: `{ productId, sku, rank, score, matchReasons }` en `camelCase`, en orden de rank 1-based
- [ ] 4.3 Implementar el truncado **por número de entradas**, con tope holgado sobre cualquier página plausible, y `ResultsCount` guardando siempre los mostrados reales
- [ ] 4.4 Implementar el registro de búsqueda de modo que **absorba cualquier fallo de persistencia**, lo registre a nivel de error y devuelva un identificador ausente. Nunca lanza
- [ ] 4.5 Generar el identificador de episodio en el servidor cuando el llamante no lo aporte, para que la columna nunca quede vacía
- [ ] 4.6 Implementar el registro de selección: derivación del rank desde la lista guardada, sellado del instante con el reloj del servidor, última escritura gana, y rank nulo con aviso cuando el producto no aparece en la lista
- [ ] 4.7 Confinar el texto de consulta a nivel de depuración en todos los eventos de log del servicio, siguiendo la regla que C03 ya dejó establecida y probada
- [ ] 4.8 Registrar el servicio en el contenedor de dependencias

## 5. Endpoint

- [ ] 5.1 Crear el DTO de selección con su único campo y el validador de FluentValidation correspondiente
- [ ] 5.2 Crear `AiSearchEventsController` con ruta explícita `api/ai/search-events` y `[Authorize]` a nivel de clase; **sin versión** en la ruta y **sin heredar de `BaseController`**, cuyo helper de creación apunta a una ruta de lectura que este change no tiene
- [ ] 5.3 Implementar el endpoint de selección: comprobación de propiedad del evento **sin bypass de administrador**, 403 si no es suyo, 404 si el evento no existe, 204 en éxito
- [ ] 5.4 Añadir `backend/api-tests/ai-search-events.http` y su entrada en el README de esa carpeta

## 6. Tests

- [ ] 6.1 Unitarios del servicio: persistencia con los campos del servidor, origen degradado distinguible, búsqueda sin resultados con contador a cero y lista vacía, truncado que conserva el contador real
- [ ] 6.2 Unitarios del servicio: derivación del rank desde la lista guardada, producto ausente que persiste con rank nulo, selección repetida que conserva la última
- [ ] 6.3 Unitario: el registro de búsqueda **no lanza** cuando la persistencia falla y devuelve identificador ausente
- [ ] 6.4 Unitario: el texto de consulta no aparece en ningún evento de log de nivel información o superior
- [ ] 6.5 Integración con Testcontainers: 403 por evento ajeno y 403 cuando quien llama es administrador y no propietario
- [ ] 6.6 Integración con Testcontainers: borrar eventos deja las ventas en pie con la atribución a nula y sin bloqueo
- [ ] 6.7 Integración que hace de C16: construir el payload a partir de un `AiSearchResponse` real usando los helpers de C03 y comprobar la fila completa. **Umbral de ergonomía: si la proyección no cabe en unas diez líneas legibles, se arregla el payload, no el test**
- [ ] 6.8 Verificar `dotnet build` y `dotnet test` en verde, sin regresión en la suite existente

## 7. Cierre

- [ ] 7.1 Anotar la obligación A1 en la ficha de C15 de `Documentos/Proyecto Final AIEng/proyecto-final-plan-changes-openspec.md` si no está ya: **es la única obligación cuyo incumplimiento deja este change sin efecto y sin síntoma**
- [ ] 7.2 Actualizar `Documentos/modelo-de-datos.md` con la entidad, la columna nueva de `Sale`, los dos índices y las cuatro reglas de borrado
- [ ] 7.3 Marcar HU-AIENG-004 como hecha en `Documentos/epicas.md`
- [ ] 7.4 Ejecutar `openspec validate --all --strict` y comprobar `0 failed` — la forma de un solo change no basta, porque un change puede estar verde con las specs vivas rotas
