## Why

C03 dejó el cliente tipado hacia `jbg-ai`, C04 dejó la telemetría de búsqueda y C14 dejó el retriever vectorial real, pero **no existe ningún endpoint que los una**: el frontend no tiene a quién llamar y `RecordSearchAsync` no tiene quién lo invoque, con lo que C04 es hoy código muerto sin síntoma —compila, sus tests pasan y su tabla llegaría vacía a la entrega—. Este change entrega el punto de entrada del operador y con él la decisión 11 del diseño: **la IA propone candidatos y .NET pone la verdad** sobre precio, stock y permisos, además de garantizar que la búsqueda no falla nunca por culpa del servicio de IA.

## What Changes

- **Nuevo `POST /api/ai/search`** en un controlador propio bajo `api/ai/*`, autenticado, con el punto de venta como parámetro obligatorio del cuerpo y una política de limitación de peticiones particionada por usuario.
- **Recuperación de ventana máxima en una sola llamada.** Se pide al gateway `top_k = 20`, que alcanza el tope de sobre-recuperación del contrato congelado (60 candidatos). **No se emite una segunda llamada** cuando la hidratación deja la página corta: el retriever aplica su umbral de distancia antes del `LIMIT`, de modo que repedir con un `top_k` mayor devolvería las mismas filas cobrando un segundo embedding.
- **Hidratación autoritativa** contra el esquema `public` con una única consulta conjunta: producto activo, inventario activo **en ese punto de venta**, cantidad de ese punto de venta, precio, foto principal y colección. Un candidato sin asignación o inactivo se descarta; **uno con cantidad cero se conserva y se marca**, porque la disponibilidad pondera y nunca excluye.
- **Buscador degradado propio**, acotado al punto de venta, con búsqueda de texto completo en español calculada en consulta —sin índice y sin cambio de esquema—, semántica de alternativa entre términos y ordenación por relevancia léxica. Sustituye al buscador existente para este camino, que casa la cadena completa y devuelve lista vacía ante cualquier consulta en lenguaje natural.
- **Bandera de activación por punto de venta** en configuración recargable, y **tercer origen de telemetría** para distinguir «la IA no se llegó a consultar» de «la IA no respondió».
- **Caché de candidatos** de vida corta que almacena únicamente identificadores y puntuaciones de la IA: la hidratación se rehace en cada petición, de modo que nunca se sirve precio ni stock desfasados.
- **Telemetría completa de C04** invocada después de hidratar y truncar, con el identificador del evento devuelto al cliente y el instante total capturado antes de la escritura.
- **Respuesta que distingue los tres «sin resultados»**: abstención del retriever, ausencia de surtido en ese punto de venta, y camino degradado.
- **Instrumentación del embudo** —candidatos recibidos, supervivientes de la hidratación, mostrados— en registro estructurado correlacionado, que queda como línea base para medir la aportación del prefiltro por punto de venta cuando llegue.

Sin cambios de ruptura: endpoint nuevo, contrato con `jbg-ai` intacto, cliente de pasarela sin modificar, buscador clásico existente sin tocar y sin migración de base de datos.

## Capabilities

### New Capabilities
- `ai-assisted-search`: el endpoint de búsqueda asistida del backend — resolución y validación del ámbito de punto de venta, ventana de sobre-recuperación pedida en una sola llamada, hidratación autoritativa que decide qué candidato sobrevive, truncado a la página solicitada, degradación acotada con buscador léxico propio, activación por punto de venta, acotación del coste por caché y limitación de peticiones, distinción de los tres estados sin resultados, e instrumentación del embudo.

### Modified Capabilities
- `ai-search-telemetry`: el origen de los resultados deja de tener dos valores y pasa a tener tres. Hoy la capacidad declara únicamente el camino asistido y el degradado; una búsqueda servida por el buscador clásico porque la asistencia está desactivada en ese punto de venta no es ninguno de los dos, y registrarla como degradada contaminaría la población que existe precisamente para medir la degradación.

## Impact

- **Backend `.NET`** — controlador nuevo bajo `api/ai/*`; servicios de aplicación de orquestación, hidratación y búsqueda degradada; objetos de transferencia de petición y respuesta; opciones de configuración validadas al arranque; ampliación del enumerado de origen de búsqueda; registro de la política de limitación de peticiones; pruebas unitarias con pasarela falsa y de integración con contenedores.
- **Sin cambios** en `ai-service/`, en el contrato congelado `ai-service/openapi.json`, en el cliente de pasarela, en el frontend, ni en el esquema de la base de datos: este change **no abre migración**.
- **Desbloquea** el panel del operador y el despliegue del servicio de IA, que cierran el hito de la ola vertical.
- **Deudas anotadas, no pagadas aquí**: el cliente de embeddings del retriever se reconstruye por petición, de modo que su caché en memoria no acierta nunca en producción —corresponde a un change posterior que ya trabaja en esa zona—; y un índice de texto completo sobre el catálogo transaccional sólo tendrá sentido si el catálogo crece un orden de magnitud.
- **Obligación heredada por el panel del operador**: los tres estados sin resultados deben decir cosas distintas en pantalla; el backend los expone, y renderizarlos como una única lista vacía haría que la interfaz mintiera en dos de los tres casos.
