## Why

Seis de los KPIs de las especificaciones funcionales v2 §5.11 —tiempo búsqueda→selección, ventas iniciadas desde búsqueda asistida, consultas sin resultado, selección en rank 1/3, ticket medio asistido frente a no asistido y ventas con sustituto sugerido— **no tienen hoy ningún soporte de datos**. El diseño v3 §15.3 declara que los KPIs de negocio están *«instrumentados, no medidos»*: instrumentado significa que el dato se captura aunque nadie lo mire, no que se pueda inferir después con un cruce difuso por usuario, punto de venta, producto y ventana temporal — que es lo único que quedaría, y que falla precisamente en el caso más frecuente del negocio: vender dos veces el mismo artículo.

Se hace ahora, y no cuando llegue el frontend que lo usará, por dos motivos. La telemetría es 🟢 y no bloquea a nadie, mientras que C16 es 🔴 y cae en la ola más congestionada: adelantarla **descarga la ruta crítica** en lugar de competir con ella. Y este es el primer change con migración de EF Core de los seis previstos, de modo que paga un coste fijo de utillaje —no existe ni un test de migración en todo el repositorio— que conviene pagar en el change del que no depende nadie.

## What Changes

- **Entidad `ProductSearchEvent`** con la consulta, los filtros efectivos, la lista realmente mostrada, el origen de los resultados, la traza, dos duraciones de servidor y las tres columnas de selección. Diecisiete columnas, cada una respondiendo a una pregunta que el modelo de specs v2 §5.8 no podía responder.
- **Columna `Sale.SearchEventId`** con `ON DELETE SET NULL`: la atribución venta↔búsqueda la declara la venta al nacer, no el evento a posteriori.
- **Una única migración de EF Core**, con las cuatro reglas de borrado declaradas a mano en lugar de heredadas del comportamiento por defecto.
- **Servicio con dos caminos de escritura**, repartidos según quién conoce cada dato: una API interna que invocará C15 para la mitad de búsqueda, y el registro de la selección que llega por HTTP. La API interna **nunca lanza**: devuelve un identificador opcional y absorbe cualquier fallo de persistencia.
- **Un solo endpoint HTTP**: registro de la selección sobre un evento existente, con un único campo en el cuerpo y sin contenido en la respuesta.
- **Arnés reutilizable de test de esquema**, que heredarán las cinco migraciones restantes del plan (C07, C08, C19, C27, C29).
- **Cero rutas de lectura.** Ni consultas, ni agregaciones, ni panel: el análisis del entregable se hace con SQL a mano en C39.

Sin cambios que rompan nada: ningún contrato REST existente se modifica, el snapshot `ai-service/openapi.json` no se toca, y `Sales` gana una columna nullable que todavía nadie escribe.

**Tres divergencias respecto a las especificaciones funcionales v2**, todas con el mismo motivo de fondo —ese documento se escribió antes de que existieran la arquitectura de dos servicios y el flujo de carrito— y todas ya corregidas en el propio documento con fecha y motivo:

| Specs v2 | Este change | Por qué |
|---|---|---|
| `POST /api/products/search-events` (§5.9) | `POST /api/ai/search-events/{id}/selection` | Un evento sin resultados y sin selección no pertenece a ningún producto; anidarlo bajo `/products` miente sobre la propiedad del recurso |
| `ProductSearchEvent.CreatedSaleId` (§5.8) | `Sale.SearchEventId` | La atribución se escribe en el mismo `INSERT` de la venta; la alternativa exigía N llamadas de seguimiento tras un checkout masivo |
| `SearchDurationMs` (§5.8) | `RetrievalMs` + `TotalMs` + `SelectedAt` | Un solo campo era ambiguo entre latencia de recuperación y tiempo hasta la selección. La diferencia de los dos primeros mide además el coste de la hidratación |

## Capabilities

### New Capabilities

- `ai-search-telemetry`: registro del ciclo consulta→selección de la búsqueda asistida. Cubre el modelo del evento y su ciclo de vida en dos escrituras, el reparto de responsabilidad entre servidor y cliente, la proyección y el truncado de la lista de resultados, la derivación del rank en el servidor, la distinción entre la ruta asistida y la degradada, la agrupación de las consultas de un episodio, la atribución de la venta a la búsqueda que la originó, la autorización por propiedad del evento, la garantía de que un fallo de telemetría nunca propaga error, y la confidencialidad del texto de consulta en los registros.

### Modified Capabilities

Ninguna. `Sales` gana una columna sin comportamiento asociado, y una columna sin escenario no es un requisito: la regla que gobierna su escritura queda recogida abajo como prerrequisito hacia adelante hasta que un change la implemente. `access-control` tampoco cambia: la ausencia de bypass de administrador en el endpoint de selección no contradice su escenario de acceso del administrador a cualquier punto de venta, porque aquí no se comprueba el punto de venta sino la propiedad del evento.

## Impact

**Código afectado**

- `backend/src/JoiabagurPV.Domain/`: entidad, enum de origen, interfaz de repositorio y la propiedad nueva en `Sale`.
- `backend/src/JoiabagurPV.Infrastructure/`: dos configuraciones de EF Core, el `DbSet`, el repositorio y **la única migración** del change.
- `backend/src/JoiabagurPV.Application/`: interfaz y servicio con los dos caminos de escritura, DTO de selección con su validador, y la proyección con truncado.
- `backend/src/JoiabagurPV.API/`: un controlador con un endpoint.
- `backend/src/JoiabagurPV.Tests/`: ayudante de aserciones de esquema en `TestHelpers/`, test de desfase modelo↔migración, unitarios del servicio e integración con Testcontainers.
- `backend/api-tests/`: fichero `.http` del endpoint nuevo.

La ficha del plan citaba dos capas (`Domain/`, `API/Controllers/`); son cinco. La superficie de colisión más probable con otros changes es `Sale` y su configuración, territorio que C15 y C16 también pisarán.

**Dependencias**

Ninguna nueva. Se reutiliza `AiCallScope` de C03 como garantía de ámbito ya validado, y `TestDatabaseFixture` como base del arnés de esquema: no hace falta infraestructura de test nueva.

**Sistemas y contratos**

- No se toca `ai-service/`, ni el frontend, ni la infraestructura.
- `ai-service/openapi.json` se **lee** para derivar la longitud del texto de consulta, y no se modifica.
- Es el primer change 🗄️ del Proyecto Final: mientras esté abierto, la regla 4 del plan impide abrir C07, C08, C19, C27 y C29. La cola limpia para el otro desarrollador es C05 o C06.

**Prerrequisito hacia adelante**

Este change no tiene prerrequisitos hacia atrás, pero **sí obligaciones hacia adelante**, que es una propiedad distinta y conviene nombrarla. Van aquí y no en `specs/`: un requisito especificado y no implementado haría fallar la verificación del change. Están replicadas en las fichas de C15 y C16 del plan de changes.

*Sobre C15 · `add-dotnet-ai-search-endpoint`*

| | |
|---|---|
| **A1 · crítica** | Invocar el registro de búsqueda **después** de hidratar y truncar, y devolver el identificador del evento en su respuesta. Es la única obligación cuyo incumplimiento deja este change **sin efecto y sin síntoma**: todo compilaría, todos los tests pasarían y la tabla llegaría vacía a la entrega |
| **A2** | Aportar filtros efectivos, origen de los resultados, traza, las dos duraciones y el identificador de episodio que envía el cliente |
| **A3** | Tolerar un identificador nulo cuando la telemetría falle, y responder igual. El servicio de este change no lanza nunca, así que basta con no asumir que siempre hay identificador |
| **A4** | Aplicar limitación de peticiones al endpoint de búsqueda. Es cuestión de coste antes que de seguridad: un `debounce` mal ajustado genera llamadas de embedding facturables |

*Sobre C16 · `add-frontend-assisted-search-panel`*

| | |
|---|---|
| **B1** | Usar la ruta relativa correcta; la URL base del frontend ya incluye el prefijo de la API |
| **B2** | Generar un identificador de episodio al abrir el panel y enviarlo en todas las búsquedas de ese episodio |
| **B3** | Renderizar los resultados en el orden recibido, sin reordenar en cliente: si se reordena, el rank pasa a medir la interfaz en lugar de la calidad de la recuperación |
| **B4** | Enviar la selección en el instante del clic, sin diferirla ni bloquear la navegación |
| **B5** | Arrastrar el identificador del evento hasta el checkout, por línea, y enviarlo al crear la venta |

*Sobre quien conecte la escritura del lado venta*

| | |
|---|---|
| **C1** | Un identificador de búsqueda desconocido degrada la atribución a nula. **Nunca hace fallar la venta** |

**Fuera de alcance**

Endpoint de búsqueda asistida y la llamada real al servicio de registro (C15); panel de búsqueda, generación del identificador de episodio y envío de la selección (C16); el campo de atribución en las peticiones de creación de venta y su asignación (C16 o el change que conecte el flujo); política de retención o anonimización del texto de consulta, declarada como limitación en el diseño §15; y cualquier lectura, agregación o panel sobre estos eventos.
