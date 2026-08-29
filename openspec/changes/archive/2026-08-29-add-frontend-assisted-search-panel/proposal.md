## Why

C15 dejó `POST /api/ai/search` con hidratación autoritativa, degradación acotada y telemetría completa, y **nadie le llama**: el operador sigue teniendo que recordar el SKU exacto, porque el buscador clásico casa la cadena completa contra el nombre y devuelve lista vacía ante cualquier frase en lenguaje natural. Este change entrega la primera pantalla del sistema RAG y, con ella, cierra una laguna que sólo se ve al llegar aquí: la spec viva `ai-search-telemetry` declara —archivada como cumplida— que una venta puede llevar la búsqueda que la originó, la columna `Sale.SearchEventId` existe con índice y clave foránea desde C04, y **ningún objeto de transferencia de venta acepta el campo**, de modo que el requisito no se puede satisfacer a través de la API.

## What Changes

- **Panel «Buscar con ayuda»** en ruta propia `/sales/new/assisted`, con **tercera tarjeta** en el hub de ventas, siguiendo el patrón de entrega de la página de escaneo: `productId` por estado de navegación.
- **Envío explícito de la consulta** —Enter o botón—, con consultas de ejemplo pulsables. **Nunca `debounce`**: la clave de la caché de candidatos de C15 incluye la cadena completa, así que ningún prefijo acierta y cada pulsación intermedia factura un embedding contra un límite de 30 peticiones por minuto y usuario.
- **Filtros rápidos**: materiales en multi-selección sobre el vocabulario cerrado replicado en el cliente, y categoría de pieza. **No disparan búsqueda por sí solos**, y se pueden quitar todos de una vez.
- **Resultados en el orden recibido**, sin ordenación en cliente, con foto, SKU, nombre, precio en EUR, stock del punto de venta —conservando y marcando el agotado—, **insignia de origen** y **chips de materiales**.
- **Cinco estados distinguibles**: carga, abstención del retriever, ausencia de surtido en ese punto de venta, camino degradado o desactivado, y **cuota de peticiones agotada**; más el aviso de **página corta** cuando sobreviven menos resultados que la página pedida.
- **Bloque de embudo colapsado, sólo para administradores**, con el identificador de correlación y los tres contadores que C15 ya devuelve.
- **Reporte de la selección en el instante del clic**, sin bloquear la navegación y sin mostrar error si falla; omitido en silencio cuando la telemetría no persistió.
- **Arrastre de `searchEventId` hasta la caja, por línea**: estado de navegación → página de venta manual → línea del carrito → los dos caminos de creación de venta.
- **Aceptación de la atribución en la API de ventas**: campo opcional en la creación individual y en cada línea de la masiva, con comprobación de existencia y de propiedad. Un identificador desconocido o de otro usuario **degrada la atribución a nula y nunca hace fallar la venta**.
- **Materiales en la respuesta de búsqueda asistida**: hoy llegan del retriever al backend y se descartan al construir el resultado, dejando al panel sin nada honesto que enseñar como motivo —`match_reasons` es la cadena literal `["vector"]` hasta que llegue la rama léxica.

Sin cambios de ruptura: los dos campos nuevos son opcionales y anulables, la respuesta crece de forma aditiva, el contrato con `jbg-ai` queda intacto, el buscador clásico y el buscador por SKU de la venta manual no se tocan, y **no hay migración de base de datos**.

## Capabilities

### New Capabilities
- `assisted-search-panel`: el panel del operador — punto de entrada en el flujo de venta, episodio de búsqueda, envío explícito con control de coste, filtros rápidos sobre vocabulario cerrado, ámbito de punto de venta por rol, resultados en orden de recuperación con la verdad del backend, los cinco estados distinguibles incluida la cuota agotada, el aviso de página corta, el embudo reservado a administradores, y el reporte de la selección que no bloquea ni falla.

### Modified Capabilities
- `sales-management`: los métodos de entrada de una venta pasan de dos a tres, y la API de creación —individual y masiva— acepta la referencia opcional a la búsqueda que originó la venta, degradándola a nula cuando el evento no existe o no pertenece a quien vende.
- `ai-assisted-search`: el resultado devuelto al cliente pasa a llevar los materiales que el recuperador reconoció, que no son hidratados ni autoritativos y existen para poder explicar la coincidencia al operador.

**No se modifica `ai-search-telemetry`.** Su requisito de atribución ya está escrito y es correcto; lo que falta es que exista un camino por el que cumplirlo, y ese camino es la API de ventas.

## Impact

- **`frontend/`** — página nueva del panel y componente aislado de fila de resultado *(para que el change del argumentario lo amplíe en vez de reescribirlo)*; servicio de búsqueda asistida; tipos espejo de los objetos de transferencia; constante del vocabulario cerrado de materiales con test que la fija; ruta perezosa y tarjeta en el hub; propagación del identificador de búsqueda por la página de venta manual, la línea del carrito y la página del carrito.
- **`backend/`** — campo opcional en los objetos de transferencia de creación de venta individual y masiva; asignación en el servicio de ventas tras comprobar existencia y propiedad; campo de materiales en el resultado de búsqueda asistida y su propagación desde el candidato; pruebas unitarias y de integración.
- **Sin cambios** en `ai-service/`, en el contrato congelado, en el cliente de pasarela, en el buscador clásico del catálogo, ni en el esquema de la base de datos: este change **no abre migración**, porque la columna, su índice y su clave foránea existen desde la telemetría de búsqueda.
- **Cierra** el hito de la ola vertical junto con el despliegue del servicio: un operador buscando en lenguaje natural desde producción, con precio y stock reales de su tienda.
- **Deudas anotadas, no pagadas aquí**: un endpoint que agregue los materiales realmente presentes en el surtido de un punto de venta —mejor producto que replicar el vocabulario, porque nunca ofrecería un filtro que devuelve cero— queda para el change de revisión de perfiles; y el motivo real de la coincidencia depende de la rama léxica, que llega después.
- **Limitaciones declaradas**: la talla sólo aparecerá cuando el change de familias puebla la etiqueta de variante; y el cliente no puede distinguir «asistencia desactivada en este punto de venta» de «el servicio de IA no responde», porque la respuesta expone el mismo indicador en ambos casos aunque la telemetría sí los separe.
