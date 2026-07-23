# Guía de Registro de Ventas

## Descripción General

El sistema ofrece tres métodos para registrar ventas:

1. **Registro Manual**: Selección directa de productos por SKU o nombre
2. **Escaneo de Código de Barras / QR**: Captura del código del producto mediante la cámara para identificación instantánea
3. **Carrito de Ventas**: Composición de múltiples productos con checkout masivo atómico

Los métodos individuales (1 y 2) comparten el mismo flujo de validación y confirmación. Desde el registro manual se puede añadir productos al carrito para luego confirmarlos todos juntos.

---

## Registro Manual de Ventas

### Acceso
- Navegue a **Ventas** → **Nueva Venta** o directamente a `/sales/new`

### Flujo de Trabajo

1. **Seleccionar Producto**
   - Use el buscador para encontrar el producto por SKU o nombre
   - El sistema muestra el stock disponible en tiempo real

2. **Ingresar Cantidad**
   - Por defecto: 1 unidad
   - El sistema valida que la cantidad no exceda el stock disponible

3. **Modificar Precio (si está habilitado)**
   - Si el punto de venta tiene activada la opción "Permitir Edición Manual de Precio", aparece un campo de precio editable
   - El precio oficial del producto se muestra como referencia
   - Si no se modifica, se usa el precio oficial
   - Si el POS no permite edición, este campo no aparece y se usa siempre el precio oficial

4. **Seleccionar Método de Pago**
   - Solo se muestran métodos activos y asignados al punto de venta actual

4. **Agregar Notas (opcional)**
   - Campo de texto libre, máximo 500 caracteres

6. **Adjuntar Foto (opcional)**
   - Puede adjuntar una foto del producto incluso en registro manual
   - La foto se comprime automáticamente a JPEG (máx 2MB)

7. **Confirmar Venta**
   - Revise el resumen: producto, cantidad, precio unitario, total
   - Si el precio fue modificado, se muestra el precio oficial como referencia con indicación "(modificado)"
   - Confirme la operación

### Validaciones

| Validación | Mensaje de Error |
|------------|------------------|
| Stock insuficiente | "Stock insuficiente. Disponible: X unidades" |
| Método de pago no disponible | "Método de pago no asignado a este punto de venta" |
| Operador no asignado al POS | "No tiene permisos para operar en este punto de venta" |
| Precio manual en POS no autorizado | "Manual price editing is not allowed for this point of sale" |
| Precio manual <= 0 | "Price must be greater than zero" |

### Advertencia de Stock Bajo

Después de una venta exitosa, si el stock restante es bajo (≤5 unidades), se muestra una advertencia:
> "⚠️ Quedan solo X unidades de este producto"

Esta advertencia es informativa y no bloquea la operación.

---

## Registro con Escaneo de Código de Barras / QR

### Requisitos del Dispositivo

- **Navegador**: Chrome 90+, Edge 90+, Safari 14+, Firefox 88+
- **Cámara**: Acceso a cámara del dispositivo trasera
- **Iluminación**: Iluminación suficiente para que la cámara enfoque el código

### Acceso
- Navegue a **Ventas** → **Escanear Código** o directamente a `/sales/new/scan`

### Flujo de Trabajo

1. **Apertura de Cámara**
   - Otorgue permisos de cámara cuando se solicite
   - La cámara trasera se activa automáticamente
   - Se muestra un recuadro de escaneo en el centro de la pantalla

2. **Escaneo Continuo**
   - Apunte la cámara al código de barras (Code128) o código QR del producto
   - El sistema decodifica automáticamente el código
   - El código QR simplemente contiene el SKU del producto
   - Los códigos repetidos dentro de 2 segundos se ignoran

3. **Búsqueda Automática**
   - El SKU decodificado se busca automáticamente en el sistema
   - Si se encuentra una coincidencia exacta, el producto se selecciona automáticamente
   - El operador es redirigido al formulario de venta

4. **Ingreso Manual como Alternativa**
   - Si la cámara no puede leer el código, use el campo de texto debajo de la vista de cámara
   - Ingrese el SKU manualmente y presione "Buscar"

5. **Finalización**
   - Complete la cantidad, método de pago y confirme la venta

### Controles Disponibles

| Control | Descripción |
|---------|-------------|
| 🔦 Flash | Botón para encender/apagar el flash en dispositivos compatibles |
| ❌ Cerrar | Botón para volver a la página principal de ventas |
| Campo SKU | Ingreso manual del SKU como alternativa al escaneo |

### Escenarios de Error

| Escenario | Comportamiento |
|-----------|----------------|
| Cámara no disponible | Mensaje "No se pudo acceder a la cámara" → Opción de reintentar o ir a registro manual |
| Permiso de cámara denegado | "Permiso de cámara denegado" → Botón para ir a registro manual |
| SKU escaneado no encontrado | Toast "Producto no encontrado: [SKU]" → El escáner continúa |
| Producto no asignado al POS | Toast "Producto no asignado a este punto de venta" → El escáner continúa |
| Flash no disponible | El botón de flash no tiene efecto (el dispositivo no soporta torch) |

---

## Carrito de Ventas y Checkout Masivo

### Descripción

El carrito permite componer una lista de productos para registrar múltiples ventas en una sola operación atómica. Todas las líneas comparten el mismo punto de venta y método de pago, y se envían al backend como una única transacción: si alguna línea falla, ninguna se registra.

### Acceso
- Desde **Ventas** → **Carrito** (visible cuando hay líneas en el carrito) o directamente en `/sales/cart`
- El botón de carrito con badge de cantidad aparece en `/sales`, `/sales/new` y `/sales/new/scan`

### Añadir Productos al Carrito

1. Navegue a **Ventas** → **Nueva Venta** (`/sales/new`)
2. Seleccione el producto, cantidad, punto de venta y método de pago como de costumbre
3. Pulse **"Añadir al carrito"** en lugar de confirmar la venta directamente
4. El producto se añade al carrito y puede seguir añadiendo más productos
5. El carrito muestra un badge con el número de líneas en la cabecera

> **Nota:** Si añade una línea con un punto de venta o método de pago diferente al de las líneas existentes, el carrito se vacía y comienza con la nueva configuración. Se muestra un aviso al operador.

### Gestión del Carrito

En la página del carrito (`/sales/cart`) puede:

- **Ver** todas las líneas añadidas con producto, cantidad y precio
- **Eliminar** líneas individuales que no procedan
- **Ver el resumen** con total, punto de venta y método de pago
- **Vaciar** el carrito completo

### Checkout Masivo

1. Revise las líneas en el carrito
2. Opcionalmente, introduzca una **nota global** que se aplicará a todas las ventas
3. El sistema **revalida el stock** de cada producto antes de habilitar el botón de checkout
4. Pulse **"Confirmar checkout"**
5. Se muestra un diálogo de confirmación con el resumen completo
6. Al confirmar, todas las ventas se crean atómicamente

### Persistencia y Caducidad

| Característica | Valor |
|----------------|-------|
| Almacenamiento | `localStorage` del navegador |
| Caducidad (TTL) | 10 horas de inactividad |
| Renovación | Se renueva con cada interacción (añadir, eliminar) |
| Supervivencia | Persiste al recargar la página y cerrar/abrir el navegador |

### Comportamiento Transaccional

- **Todo o nada:** Si cualquier línea falla la validación de stock dentro de la transacción, todas las ventas se revierten
- **Idempotencia:** El frontend envía un header `Idempotency-Key` para prevenir duplicados en caso de reintentos por fallos de red
- **Agrupación:** Todas las ventas creadas comparten un `BulkOperationId` para trazabilidad en el historial

### Validaciones

| Validación | Mensaje de Error |
|------------|------------------|
| Carrito vacío | "Debe añadir al menos una línea" |
| Stock insuficiente (pre-checkout) | Botón de checkout deshabilitado, stock en rojo |
| Stock insuficiente (en transacción) | "Línea X: Stock cambió. Disponible: N, Solicitado: M" |
| Operador no asignado al POS | "Operator is not assigned to this point of sale" |
| POS o método de pago diferente | El carrito se vacía y se inicia con la nueva configuración |

---

## Historial de Ventas

### Acceso
- Navegue a **Ventas** → **Historial** o `/sales/history`

### Filtros Disponibles

| Filtro | Descripción |
|--------|-------------|
| Rango de fechas | Por defecto: últimos 30 días |
| Producto | Filtrar por producto específico |
| Método de pago | Filtrar por método de pago |
| Operador | Solo visible para administradores |

### Información Mostrada

- Fecha y hora de la venta
- Producto (SKU y nombre)
- Cantidad
- Precio unitario y total
- Indicador de precio modificado ("Precio modificado") cuando se usó un precio manual
- Método de pago
- Operador que realizó la venta
- Indicador de foto adjunta (📷)

### Detalle de Venta

Haga clic en una venta para ver:
- Información completa
- Si el precio fue modificado: precio de venta efectivo y precio oficial original como referencia
- Foto adjunta (si existe) con opción de ampliar
- Movimiento de inventario asociado

### Restricciones por Rol

| Rol | Acceso |
|-----|--------|
| Administrador | Ve todas las ventas de todos los puntos de venta |
| Operador | Solo ve ventas de puntos de venta asignados |

---

## Integración con Inventario

Cada venta crea automáticamente:
- Un movimiento de inventario tipo "Sale"
- Actualización inmediata del stock
- Registro de auditoría completo

La transacción es atómica: si algún paso falla, toda la operación se revierte.

---

## Preguntas Frecuentes

### ¿Puedo registrar ventas sin conexión a internet?
El registro manual funciona sin conexión si ya tiene la sesión iniciada. El escaneo de códigos requiere conexión para buscar el producto por SKU.

### ¿Qué pasa si dos operadores intentan vender el último producto?
El sistema usa doble validación de stock:
1. Validación al cargar el formulario
2. Validación dentro de la transacción antes de confirmar

Si el stock cambia entre ambas validaciones, se muestra el error:
> "Stock cambió. Disponible: X, Solicitado: Y"

### ¿Qué pasa si cierro el navegador con productos en el carrito?
El carrito se almacena en `localStorage` y persiste al cerrar y reabrir el navegador. Caduca automáticamente tras 10 horas sin actividad.

### ¿Qué pasa si el stock cambia mientras tengo productos en el carrito?
Al abrir la página del carrito, el sistema revalida el stock de todos los productos. Si alguno no tiene stock suficiente, el botón de checkout se deshabilita y se muestra el stock en rojo. Además, el backend realiza una segunda validación dentro de la transacción para prevenir carreras de concurrencia.

### ¿Puedo mezclar diferentes puntos de venta en el carrito?
No. Todas las líneas deben pertenecer al mismo punto de venta y método de pago. Si añade una línea con un POS o método diferente, el carrito se vacía y comienza con la nueva configuración.

### ¿Qué códigos de barras puedo escanear?
El sistema soporta códigos Code128, EAN, UPC y Code39 para códigos de barras, así como códigos QR. El valor decodificado se busca como SKU en el sistema.

### ¿Qué hago si la cámara no lee el código?
Use el campo de ingreso manual de SKU debajo de la vista de cámara. También puede ir a "Registro Manual" para buscar por nombre del producto.

### ¿El código QR es el mismo que el SKU?
Sí. El código QR codifica el SKU del producto. No se requiere ningún campo adicional en la base de datos. También puede generar códigos QR y códigos de barras Code128 desde la página de edición del producto.
