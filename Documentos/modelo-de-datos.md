# Modelo de Datos - Sistema de Gestión de Puntos de Venta para Joyería

## Visión General

Modelo de datos diseñado para soportar el MVP del sistema de gestión de puntos de venta, con consideraciones para facilitar la escalabilidad hacia la Fase 2. El modelo está optimizado para PostgreSQL 15+ y utiliza Entity Framework Core como ORM.

---

## Diagrama del Modelo de Datos

```mermaid
erDiagram
    User ||--o{ UserPointOfSale : "asignado a"
    User ||--o{ Sale : "realiza"
    User ||--o{ InventoryMovement : "registra"
    User ||--o{ Return : "registra"
    
    PointOfSale ||--o{ UserPointOfSale : "tiene asignados"
    PointOfSale ||--o{ Sale : "registra ventas"
    PointOfSale ||--o{ Inventory : "tiene stock"
    PointOfSale ||--o{ PointOfSalePaymentMethod : "tiene métodos"
    PointOfSale ||--o{ Return : "recibe devoluciones"
    
    Product ||--o{ ProductPhoto : "tiene fotos"
    Product ||--o{ ProductPhotoEmbedding : "tiene embeddings"
    ProductPhoto ||--o| ProductPhotoEmbedding : "tiene embedding"
    Product ||--o{ Sale : "se vende"
    Product ||--o{ Inventory : "en stock"
    Product ||--o{ InventoryMovement : "movimiento"
    Product ||--o{ Return : "devuelto"
    Product }o--|| Collection : "pertenece a"
    
    Collection ||--o{ Product : "contiene"
    
    PaymentMethod ||--o{ PointOfSalePaymentMethod : "disponible en"
    PaymentMethod ||--o{ Sale : "usado en"
    
    Sale ||--o{ SalePhoto : "tiene foto"
    Sale ||--o{ ReturnSale : "asociada a devoluciones"
    Sale ||--o{ InventoryMovement : "genera movimiento"
    
    Return ||--o{ ReturnSale : "asociada a ventas"
    Return ||--o{ ReturnPhoto : "tiene foto"
    Return ||--o{ InventoryMovement : "genera movimiento"
    
    Inventory ||--o{ InventoryMovement : "tiene movimientos"

    Product ||--o{ ProductComponentAssignment : "tiene componentes"
    ProductComponent ||--o{ ProductComponentAssignment : "asignado a"
    ProductComponent ||--o{ ComponentTemplateItem : "en plantilla"
    ComponentTemplate ||--o{ ComponentTemplateItem : "tiene items"
    User ||--o{ RefreshToken : "tiene tokens"
    User ||--o{ ModelTrainingJob : "inicia entrenamiento"
    
    User {
        uuid Id PK
        string Username UK "unique"
        string Email UK "unique, nullable"
        string PasswordHash
        string FirstName
        string LastName
        enum Role "Admin, Operator"
        bool IsActive
        datetime CreatedAt
        datetime UpdatedAt
        datetime? LastLoginAt
    }
    
    PointOfSale {
        uuid Id PK
        string Name
        string Code UK "unique"
        string? Address
        string? Phone
        string? Email
        bool IsActive
        bool AllowManualPriceEdit "default false"
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    UserPointOfSale {
        uuid Id PK
        uuid UserId FK,UK
        uuid PointOfSaleId FK,UK
        datetime AssignedAt
        datetime? UnassignedAt
        bool IsActive UK
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    Collection {
        uuid Id PK
        string Name
        string? Description
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    Product {
        uuid Id PK
        string SKU UK "unique, indexed"
        string Name
        string? Description
        decimal Price
        uuid? CollectionId FK "nullable"
        bool IsActive
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    ProductPhoto {
        uuid Id PK
        uuid ProductId FK
        string FileName "nombre del archivo almacenado"
        int DisplayOrder "para ordenar múltiples fotos"
        bool IsPrimary "foto principal"
        datetime CreatedAt
        datetime UpdatedAt
    }

    ProductPhotoEmbedding {
        uuid Id PK
        uuid ProductPhotoId FK,UK "unique - un embedding por foto"
        uuid ProductId FK
        string ProductSku "desnormalizado para búsquedas sin JOIN"
        text EmbeddingVector "1280 floats como JSON"
        datetime CreatedAt
        datetime UpdatedAt
    }

    PaymentMethod {
        uuid Id PK
        string Code UK "unique"
        string Name
        string? Description
        bool IsActive
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    PointOfSalePaymentMethod {
        uuid Id PK
        uuid PointOfSaleId FK,UK
        uuid PaymentMethodId FK,UK
        bool IsActive
        datetime CreatedAt
        datetime? DeactivatedAt
    }
    
    Sale {
        uuid Id PK
        uuid ProductId FK
        uuid PointOfSaleId FK
        uuid UserId FK "operador que realizó la venta"
        uuid PaymentMethodId FK
        decimal Price "precio efectivo de la venta"
        int Quantity "default 1"
        string? Notes "notas adicionales"
        bool PriceWasOverridden "default false"
        decimal? OriginalProductPrice "precio oficial cuando hubo override"
        uuid? BulkOperationId "agrupa ventas de un checkout masivo"
        datetime SaleDate
        datetime CreatedAt
    }
    
    SalePhoto {
        uuid Id PK
        uuid SaleId FK
        string FilePath "S3/blob path"
        string FileName
        long FileSize "bytes"
        string MimeType
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    Return {
        uuid Id PK
        uuid ProductId FK
        uuid PointOfSaleId FK
        uuid UserId FK "usuario que registra la devolución"
        int Quantity "cantidad total devuelta"
        enum ReturnCategory "Defectuoso, TamañoIncorrecto, NoSatisfecho, Otro"
        string? Reason "motivo libre opcional, max 500 chars"
        datetime ReturnDate
        datetime CreatedAt
    }
    
    ReturnSale {
        uuid Id PK
        uuid ReturnId FK,UK
        uuid SaleId FK,UK
        int Quantity "cantidad de esta venta incluida en la devolución"
        decimal UnitPrice "precio unitario snapshot de Sale.Price"
        datetime CreatedAt
    }
    
    ReturnPhoto {
        uuid Id PK
        uuid ReturnId FK
        string FilePath "S3/blob path"
        string FileName
        long FileSize "bytes"
        string MimeType
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    Inventory {
        uuid Id PK
        uuid ProductId FK,UK
        uuid PointOfSaleId FK,UK
        int Quantity "stock actual"
        bool IsActive "true=asignado, false=desasignado"
        datetime LastUpdatedAt
        datetime CreatedAt
        datetime UpdatedAt
    }
    
    InventoryMovement {
        uuid Id PK
        uuid InventoryId FK
        uuid? SaleId FK "nullable, si es movimiento por venta"
        uuid? ReturnId FK "nullable, si es movimiento por devolución"
        uuid UserId FK "usuario que registra el movimiento"
        enum MovementType "Sale, Return, Adjustment, Import"
        int QuantityChange "positivo o negativo"
        int QuantityBefore "stock antes del movimiento"
        int QuantityAfter "stock después del movimiento"
        string? Reason "motivo del ajuste"
        datetime MovementDate
        datetime CreatedAt
        datetime UpdatedAt
    }

    RefreshToken {
        uuid Id PK
        string Token UK "unique"
        uuid UserId FK
        datetime ExpiresAt
        bool IsRevoked "default false"
        datetime? RevokedAt
        string? CreatedByIp
        string? RevokedByIp
        string? ReplacedByToken
        datetime CreatedAt
        datetime UpdatedAt
    }

    ProductComponent {
        uuid Id PK
        string Description UK "unique, max 35 chars"
        decimal? CostPrice "precision 18,4"
        decimal? SalePrice "precision 18,4"
        bool IsActive "default true"
        datetime CreatedAt
        datetime UpdatedAt
    }

    ProductComponentAssignment {
        uuid Id PK
        uuid ProductId FK,UK
        uuid ComponentId FK,UK
        decimal Quantity "precision 18,4"
        decimal CostPrice "precision 18,4"
        decimal SalePrice "precision 18,4"
        int DisplayOrder "default 0"
        datetime CreatedAt
        datetime UpdatedAt
    }

    ComponentTemplate {
        uuid Id PK
        string Name "max 100 chars"
        string? Description "max 500 chars"
        datetime CreatedAt
        datetime UpdatedAt
    }

    ComponentTemplateItem {
        uuid Id PK
        uuid TemplateId FK,UK
        uuid ComponentId FK,UK
        decimal Quantity "precision 18,4"
        datetime CreatedAt
        datetime UpdatedAt
    }

    ModelMetadata {
        uuid Id PK
        string Version UK "unique"
        datetime TrainedAt
        string ModelPath
        string? AccuracyMetrics "JSON"
        int TotalPhotosUsed
        int TotalProductsUsed
        bool IsActive "default false"
        string? Notes
        datetime CreatedAt
        datetime UpdatedAt
    }

    ModelTrainingJob {
        uuid Id PK
        uuid InitiatedBy FK "User"
        string Status "Queued, InProgress, Completed, Failed"
        int ProgressPercentage "default 0"
        string? CurrentStage
        datetime? StartedAt
        datetime? CompletedAt
        string? ErrorMessage
        string? ResultModelVersion
        int? DurationSeconds
        datetime CreatedAt
        datetime UpdatedAt
    }
```

> **Notación del diagrama.** El `erDiagram` usa solo marcas Mermaid válidas: `PK`,
> `FK` y `UK` (esta última sobre cada columna que participa en una restricción
> única, incluidas las compuestas — p. ej. `Inventory.ProductId FK,UK` +
> `Inventory.PointOfSaleId FK,UK` es la única `(ProductId, PointOfSaleId)`).
> Los índices no únicos, los índices compuestos y los filtros de las restricciones
> únicas **no caben en esa notación** y se documentan en
> [Índices y Optimizaciones](#índices-y-optimizaciones), que es la referencia
> completa: campos, orden, propósito y casos de uso.

---

## Descripción de Entidades Principales

### User (Usuarios)

Representa a los usuarios del sistema con dos roles principales: **Administrador** y **Operador**.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `Username`: Nombre de usuario único para login
- `Email`: Email único (opcional, para notificaciones futuras)
- `PasswordHash`: Hash de la contraseña (BCrypt)
- `Role`: Enum (Admin, Operator) - define permisos del usuario
- `IsActive`: Flag para habilitar/deshabilitar usuarios sin eliminarlos

**Consideraciones Fase 2:**
- Campo `Email` preparado para notificaciones de alertas de stock bajo
- `LastLoginAt` para auditoría y seguridad

---

### PointOfSale (Puntos de Venta)

Representa los diferentes puntos de venta donde se realizan las transacciones (tiendas propias, hoteles, terceros).

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `Name`: Nombre del punto de venta
- `Code`: Código único para identificación rápida
- `IsActive`: Flag para habilitar/deshabilitar puntos de venta
- `AllowManualPriceEdit`: Indica si los operadores pueden modificar el precio de venta al registrar transacciones en este punto de venta (default `false`, solo configurable por administradores)

**Consideraciones Fase 2:**
- Campos `Address`, `Phone`, `Email` preparados para reportes y contactos

---

### UserPointOfSale (Asignación Usuario-Punto de Venta)

Tabla de relación muchos a muchos entre usuarios y puntos de venta. Permite que los operadores estén asignados a múltiples puntos de venta.

**Campos Clave:**
- `UserId`: Referencia al usuario (operador)
- `PointOfSaleId`: Referencia al punto de venta
- `IsActive`: Controla si la asignación está activa
- `AssignedAt` / `UnassignedAt`: Historial de asignaciones

**Nota:** Los administradores no necesitan estar en esta tabla ya que tienen acceso a todos los puntos de venta por defecto.

---

### Collection (Colecciones)

Agrupa productos por colección. Aunque está en el MVP, es opcional inicialmente.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `Name`: Nombre de la colección
- `Description`: Descripción opcional

**Consideraciones Fase 2:**
- Preparado para reportes por colección y filtros avanzados

---

### Product (Productos)

Catálogo centralizado de productos de la joyería.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `SKU`: Código único del producto (índice único, usado para matching en importaciones)
- `Name`: Nombre del producto
- `Description`: Descripción detallada (opcional)
- `Price`: Precio actual del producto
- `CollectionId`: Referencia opcional a la colección
- `IsActive`: Flag para productos activos/inactivos

**Consideraciones Fase 2:**
- Campo `Price` puede evolucionar a tabla `ProductPriceHistory` para historial de precios
- Preparado para precios diferentes por punto de venta (nueva tabla `ProductPointOfSalePrice`)

---

### ProductPhoto (Fotos de Productos)

Fotos de referencia de productos para el reconocimiento de imágenes. Múltiples fotos por producto para mejorar la precisión del modelo de IA.

**Campos Clave:**
- `ProductId`: Referencia al producto
- `FileName`: Nombre del archivo almacenado (la ruta se construye en runtime desde la configuración del storage service)
- `DisplayOrder`: Orden de visualización
- `IsPrimary`: Indica si es la foto principal

**Nota:** A diferencia de `SalePhoto` y `ReturnPhoto`, esta entidad no almacena `FilePath`, `FileSize` ni `MimeType` directamente. El path completo se resuelve en tiempo de ejecución a través de `IFileStorageService`.

**Optimizaciones:**
- Índice compuesto en `(ProductId, DisplayOrder)` para ordenamiento eficiente
- Las fotos se almacenan en object storage (S3/Blob), no en la base de datos

---

### ProductPhotoEmbedding (Embeddings de Fotos de Productos)

Almacena el vector de características MobileNetV2 (1280 dimensiones) de cada foto de producto. Se usa para inferencia por similitud coseno en lugar del clasificador entrenado.

**Campos Clave:**
- `ProductPhotoId`: FK a la foto de producto (único — un embedding por foto)
- `ProductId`: FK al producto (desnormalizado para evitar JOINs en lecturas masivas)
- `ProductSku`: SKU del producto (desnormalizado para búsquedas sin JOIN)
- `EmbeddingVector`: Vector de 1280 floats serializado como JSON text

**Ciclo de Vida:**
- Se crea automáticamente cuando se sube una foto de producto (extracción en el navegador con MobileNetV2)
- Se elimina automáticamente cuando se elimina la foto asociada
- Se puede regenerar en bloque desde la página de administración de IA ("Generar Embeddings")

**Decisiones de Diseño:**
- Almacenado como `text` (JSON) en lugar de `pgvector` porque la similitud se calcula íntegramente en el navegador, sin consultas de similitud en servidor
- Una fila por foto (no por producto) para capturar múltiples ángulos visuales
- Tamaño estimado: ~366 filas × 1280 floats × ~8 bytes (JSON) ≈ 3 MB

**Optimizaciones:**
- Índice único en `ProductPhotoId` (un embedding por foto)
- Índice en `ProductId` para borrados en cascada eficientes

---

### ProductSearchEvent (Telemetría de Búsqueda Asistida)

Registra cada búsqueda asistida ejecutada y, si la hubo, la selección que el operador hizo sobre ella. Añadida por el change C04 (`add-product-search-event-tracking`, EP17) para que los KPIs de adopción y de calidad de recuperación de las especificaciones funcionales v2 §5.11 estén instrumentados desde antes de que exista el panel que los produce.

**Campos Clave:**
- `UserId`, `PointOfSaleId`: operador y punto de venta, tomados del ámbito ya validado, nunca del cuerpo de la petición
- `SearchSessionId`: agrupa las consultas de un mismo episodio de búsqueda
- `SearchText`: consulta en lenguaje natural, `varchar(500)` — la longitud viene del contrato congelado `ai-service/openapi.json`
- `FiltersJson`: `jsonb` con los filtros **efectivos** enviados a recuperación, `{}` si no hubo
- `ResultsJson`: `jsonb` con la lista **mostrada**, proyectada a `{ productId, sku, rank, score, matchReasons }`, `[]` si vacía
- `ResultsCount`: resultados realmente mostrados, con independencia de cuántos se almacenaron
- `SearchOrigin`: `Assisted = 1` | `LexicalFallback = 2` — distingue la ruta asistida de la degradada al buscador léxico
- `TraceId`: correlación con los logs del salto .NET↔Python
- `RetrievalMs`, `TotalMs`: obtener candidatos y servir la petición completa; su diferencia mide la hidratación
- `SelectedProductId`, `SelectedFromRank`, `SelectedAt`: la selección, todos nullable

**Ciclo de Vida:**
- La mitad de búsqueda la escribe el backend al servir `POST /api/ai/search` (C15), porque es el único que conoce el origen, la traza, la latencia real y la lista devuelta
- La mitad de selección llega por `POST /api/ai/search-events/{id}/selection` con un único campo; el rank lo **deriva el servidor** desde la lista guardada
- Una fila por consulta ejecutada; las reformulaciones de un episodio comparten `SearchSessionId`

**Decisiones de Diseño:**
- `jsonb` y no `text`: la columna existe para agregarse en SQL, y además hace imposible almacenar un JSON truncado a medias
- Solo se guarda lo **irrecuperable**: `score` y `matchReasons` dependían del índice y los pesos de ese día — misma lógica que el snapshot de `Sale.Price`. Materiales, familia y variante se reconstruyen con un `JOIN`
- Truncado por número de entradas (tope 50) y nunca por bytes: es un guardarraíl contra un defecto propio, no una funcionalidad
- Sin propiedades de navegación y **sin ninguna ruta de lectura**: el análisis se hace con SQL directo
- El enlace con la venta vive en `Sale.SearchEventId`, no aquí: la atribución la declara la venta en su propio `INSERT`

**Optimizaciones:**
- Índice compuesto `(PointOfSaleId, CreatedAt)` en ese orden — punto de venta primero porque es el predicado de igualdad de la consulta dominante
- Índice sobre `CreatedAt` para la serie temporal global
- Reglas de borrado declaradas a mano: `RESTRICT` hacia usuario, punto de venta y producto seleccionado; `SET NULL` desde `Sale`. La telemetría es prescindible, así que nada que dependa de ella se rompe al desaparecer, y nada de lo que ella depende desaparece arrastrándola

---

### PaymentMethod (Métodos de Pago)

Lista general de métodos de pago disponibles en el sistema.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `Code`: Código único (ej: "CASH", "BIZUM", "CARD_OWN", "CARD_POS", "PAYPAL", "TRANSFER")
- `Name`: Nombre descriptivo
- `Description`: Descripción opcional
- `IsActive`: Flag para habilitar/deshabilitar métodos

**Valores Predefinidos (MVP):**
- Efectivo (CASH)
- Bizum (BIZUM)
- Transferencia bancaria (TRANSFER)
- Tarjeta TPV propio (CARD_OWN)
- Tarjeta TPV punto de venta (CARD_POS)
- PayPal (PAYPAL)

---

### PointOfSalePaymentMethod (Métodos de Pago por Punto de Venta)

Tabla de relación muchos a muchos que define qué métodos de pago están disponibles en cada punto de venta.

**Campos Clave:**
- `PointOfSaleId`: Referencia al punto de venta
- `PaymentMethodId`: Referencia al método de pago
- `IsActive`: Controla si el método está activo para ese punto de venta
- `DeactivatedAt`: Timestamp de desactivación (auditoría)

**Restricción:** Constraint único en `(PointOfSaleId, PaymentMethodId)` para evitar duplicados.

---

### Sale (Ventas)

Registro de todas las ventas realizadas en el sistema.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `ProductId`: Producto vendido
- `PointOfSaleId`: Punto de venta donde se realizó la venta
- `UserId`: Operador que realizó la venta
- `PaymentMethodId`: Método de pago utilizado
- `Price`: Precio efectivo de la venta (precio oficial del producto o precio manual si fue modificado)
- `Quantity`: Cantidad vendida (default 1)
- `SaleDate`: Fecha y hora de la venta
- `Notes`: Notas adicionales opcionales
- `PriceWasOverridden`: Indica si el precio fue modificado manualmente por el operador (default `false`)
- `OriginalProductPrice`: Precio oficial del producto al momento de la venta, solo se almacena cuando `PriceWasOverridden = true` (nullable)
- `BulkOperationId`: UUID que agrupa ventas creadas juntas en un checkout masivo (nullable). Las ventas individuales tienen este campo en `null`
- `SearchEventId`: FK al `ProductSearchEvent` del que procede la venta (nullable). Regla de borrado **`SET NULL`**. La columna existe desde C04; el camino de escritura lo aporta el change que conecte el flujo de venta

**Consideraciones:**
- `Price` es un snapshot para mantener integridad histórica; puede ser el precio oficial del producto o un precio manual si el POS lo permite
- Cuando `PriceWasOverridden = true`, `OriginalProductPrice` contiene el precio oficial del catálogo como referencia de auditoría
- `BulkOperationId` comparte un mismo UUID entre todas las ventas creadas en una misma operación de checkout masivo, permitiendo trazabilidad y agrupación
- Múltiples índices compuestos para consultas frecuentes por punto de venta, producto, usuario, método de pago y operación masiva

**Reglas de resolución de precio:**
1. Si el POS no permite edición manual (`AllowManualPriceEdit = false`): se rechaza cualquier precio manual enviado
2. Si el POS permite edición y no se envía precio: se usa el precio oficial del producto
3. Si el POS permite edición y se envía un precio igual al oficial: `PriceWasOverridden = false`
4. Si el POS permite edición y se envía un precio diferente: `PriceWasOverridden = true`, `OriginalProductPrice` = precio oficial

**Consideraciones Fase 2:**
- Campo `Notes` puede evolucionar para incluir información de promociones/descuentos
- Preparado para tabla `SaleDiscount` si se implementan descuentos

---

### SalePhoto (Fotos de Ventas)

Fotos asociadas a ventas cuando se registran mediante reconocimiento de imágenes.

**Campos Clave:**
- `SaleId`: Referencia a la venta
- `FilePath`: Ruta en S3/Blob Storage
- `FileName`: Nombre original del archivo
- `FileSize`: Tamaño en bytes
- `MimeType`: Tipo MIME de la imagen

**Nota:** Una venta puede tener 0 o 1 foto (cuando se registra con reconocimiento de imagen). Si se registra manualmente, no tendrá foto.

---

### Return (Devoluciones)

Registro de devoluciones de productos vendidos. Una devolución puede estar asociada a una o más ventas originales mediante la tabla de relación `ReturnSale`.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `ProductId`: Producto devuelto
- `PointOfSaleId`: Punto de venta donde se recibe la devolución (debe coincidir con la venta original)
- `UserId`: Usuario que registra la devolución
- `Quantity`: Cantidad total de unidades devueltas
- `ReturnCategory`: Categoría obligatoria de la devolución (Defectuoso, TamañoIncorrecto, NoSatisfecho, Otro)
- `Reason`: Motivo de texto libre de la devolución (opcional, máximo 500 caracteres)
- `ReturnDate`: Fecha y hora de la devolución

**Reglas de Negocio:**
- La devolución debe realizarse en el mismo punto de venta donde se realizó la venta original
- Solo se pueden devolver unidades de ventas realizadas en los últimos 30 días
- La cantidad total devuelta no puede exceder la cantidad disponible (vendida - ya devuelta previamente)
- El stock se incrementa automáticamente mediante `InventoryMovement` (tipo "Return")
- Operadores solo pueden registrar devoluciones en sus puntos de venta asignados

**Consideraciones:**
- Una devolución puede asociarse a múltiples ventas (ej: cliente compró 2 unidades el lunes, 3 el martes, devuelve 4)
- Una venta puede tener múltiples devoluciones parciales
- El valor total de la devolución se calcula como: SUM(ReturnSale.Quantity * ReturnSale.UnitPrice)

---

### ReturnSale (Relación Devolución-Venta)

Tabla de relación muchos a muchos entre devoluciones y ventas. Permite asociar una devolución a múltiples ventas originales, registrando la cantidad devuelta y el precio snapshot de cada venta.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `ReturnId`: Referencia a la devolución
- `SaleId`: Referencia a la venta original
- `Quantity`: Cantidad de unidades de esta venta incluidas en la devolución
- `UnitPrice`: Precio unitario snapshot copiado de Sale.Price al momento de la devolución

**Consideraciones:**
- Permite calcular el valor exacto devuelto por venta
- Preserva el precio histórico para reportes financieros precisos
- La suma de ReturnSale.Quantity para un SaleId no puede exceder Sale.Quantity

**Cálculo de cantidad disponible para devolución:**
```
Para cada Sale en últimos 30 días en mismo POS con mismo Producto:
  disponible = Sale.Quantity - SUM(ReturnSale.Quantity WHERE SaleId = Sale.Id)
```

---

### ReturnPhoto (Fotos de Devoluciones)

Fotos opcionales asociadas a devoluciones para documentación (ej: foto del producto defectuoso).

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `ReturnId`: Referencia a la devolución
- `FilePath`: Ruta en S3/Blob Storage
- `FileName`: Nombre original del archivo
- `FileSize`: Tamaño en bytes
- `MimeType`: Tipo MIME de la imagen

**Consideraciones:**
- Una devolución puede tener 0 o 1 foto
- Las fotos se comprimen (JPEG 80%, máximo 2MB) antes de almacenar
- Mismo patrón de almacenamiento que SalePhoto

---

### Inventory (Inventario)

Stock actual de cada producto en cada punto de venta. **La presencia de un registro activo (`IsActive = true`) en esta tabla indica que el producto está asignado a ese punto de venta**, independientemente de la cantidad.

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `ProductId`: Referencia al producto
- `PointOfSaleId`: Referencia al punto de venta
- `Quantity`: Cantidad actual en stock (**puede ser 0, el producto sigue asignado al POS si IsActive = true**)
- `IsActive`: Indica si el producto está asignado (true) o desasignado (false) - permite soft delete
- `LastUpdatedAt`: Última actualización del stock
- `CreatedAt`: Fecha de creación del registro

**Campos Fase 2 (no implementados aún):**
- `MinimumThreshold`: Umbral mínimo para alertas de stock bajo (se añadirá cuando se implementen alertas)

**Restricción:** Constraint único en `(ProductId, PointOfSaleId)` para garantizar un solo registro por combinación producto-punto de venta.

**Regla de Visibilidad:**
- Los operadores solo pueden ver/acceder a productos que tienen registro **activo** (`IsActive = true`) en `Inventory` para sus puntos de venta asignados
- Un producto puede existir en la tabla `Product` sin ningún registro en `Inventory` (no asignado a ningún POS)
- Registros con `IsActive = false` se preservan para auditoría pero el producto no es visible para operadores

**Campo IsActive (Soft Delete):**
- `true`: Producto asignado y visible para operadores del POS
- `false`: Producto desasignado (soft delete), no visible pero historial preservado
- Permite reasignación sin perder datos históricos
- Solo se puede desasignar (`IsActive = false`) si `Quantity = 0`

**Optimizaciones:**
- Índice compuesto en `(PointOfSaleId, Quantity)` para consultas de stock bajo
- Índice en `ProductId` para consultas de stock total por producto
- **Índice compuesto en `(PointOfSaleId, ProductId, IsActive)` para filtrado eficiente de catálogo por operador**
- Índice parcial en `(PointOfSaleId, ProductId) WHERE IsActive = true` para consultas frecuentes de productos activos

---

### InventoryMovement (Movimientos de Inventario)

Historial completo y trazable de todos los movimientos de inventario (ventas, devoluciones, ajustes manuales, importaciones).

**Campos Clave:**
- `Id`: Identificador único (UUID)
- `InventoryId`: Referencia al inventario afectado
- `SaleId`: Referencia opcional a la venta (si el movimiento es por venta)
- `ReturnId`: Referencia opcional a la devolución (si el movimiento es por devolución)
- `UserId`: Usuario que registra el movimiento
- `MovementType`: Tipo de movimiento (Sale, Return, Adjustment, Import)
- `QuantityChange`: Cambio en la cantidad (positivo o negativo)
- `QuantityBefore`: Stock antes del movimiento
- `QuantityAfter`: Stock después del movimiento
- `Reason`: Motivo del movimiento (especialmente para ajustes manuales)
- `MovementDate`: Fecha y hora del movimiento

**Consideraciones:**
- Tabla de auditoría completa para trazabilidad total
- Permite reconstruir el estado del inventario en cualquier momento
- Los campos `QuantityBefore` y `QuantityAfter` permiten validar integridad

**Optimizaciones:**
- Índices en `InventoryId`, `MovementDate` y compuesto `(InventoryId, MovementDate)` para historial ordenado

---

### RefreshToken (Tokens de Refresco)

Tokens de sesión almacenados en base de datos para permitir revocación y rotación de tokens JWT.

**Campos Clave:**
- `Token`: Valor único del token (string base64)
- `UserId`: Referencia al usuario propietario
- `ExpiresAt`: Fecha de expiración
- `IsRevoked`: Si el token fue revocado
- `RevokedAt`: Timestamp de revocación
- `CreatedByIp` / `RevokedByIp`: IPs de auditoría
- `ReplacedByToken`: Token sustituto (en rotación)

---

### ProductComponent (Componentes de Joyas - Tabla Maestra)

Tabla maestra de componentes (materiales, mano de obra, etc.) que pueden asignarse a productos. Solo visible para administradores.

**Campos Clave:**
- `Description`: Descripción única del componente (máx 35 caracteres)
- `CostPrice`: Precio de coste por defecto (opcional, precisión 18,4)
- `SalePrice`: Precio de venta por defecto (opcional, precisión 18,4)
- `IsActive`: Componentes inactivos no pueden asignarse a nuevos productos pero los ya asignados mantienen su asignación

---

### ProductComponentAssignment (Asignación Componente-Producto)

Asigna un componente de la tabla maestra a un producto concreto, con cantidad y precios override.

**Campos Clave:**
- `ProductId`: Referencia al producto
- `ComponentId`: Referencia al componente maestro
- `Quantity`: Cantidad del componente (precisión 18,4)
- `CostPrice`: Precio de coste override para esta asignación (precisión 18,4)
- `SalePrice`: Precio de venta override para esta asignación (precisión 18,4)
- `DisplayOrder`: Orden de visualización (drag-and-drop)

**Restricción:** Constraint único en `(ProductId, ComponentId)` para evitar duplicados.

---

### ComponentTemplate (Plantillas de Componentes)

Plantillas reutilizables que definen conjuntos de componentes con cantidades para configuración rápida de productos.

**Campos Clave:**
- `Name`: Nombre de la plantilla (máx 100 caracteres)
- `Description`: Descripción opcional (máx 500 caracteres)

---

### ComponentTemplateItem (Items de Plantilla)

Componente individual dentro de una plantilla, define componente y cantidad (los precios se cargan desde la tabla maestra al aplicar).

**Campos Clave:**
- `TemplateId`: Referencia a la plantilla
- `ComponentId`: Referencia al componente maestro
- `Quantity`: Cantidad del componente (precisión 18,4)

**Restricción:** Constraint único en `(TemplateId, ComponentId)` para evitar duplicados.

---

### ModelMetadata (Metadatos de Modelos IA)

Metadatos de las versiones del modelo de reconocimiento de imágenes. Solo un modelo puede estar activo a la vez.

**Campos Clave:**
- `Version`: Identificador de versión único (ej: "v2_20260111")
- `ModelPath`: Ruta a los archivos del modelo en storage
- `AccuracyMetrics`: Métricas de precisión en formato JSON
- `TotalPhotosUsed` / `TotalProductsUsed`: Datos de entrenamiento
- `IsActive`: Solo un modelo activo simultáneamente

---

### ModelTrainingJob (Trabajos de Entrenamiento)

Registra el estado y progreso de operaciones de entrenamiento del modelo de IA.

**Campos Clave:**
- `InitiatedBy`: Usuario que inició el entrenamiento
- `Status`: Estado actual (Queued, InProgress, Completed, Failed)
- `ProgressPercentage`: Progreso 0-100
- `CurrentStage`: Etapa actual descriptiva
- `StartedAt` / `CompletedAt`: Timestamps de ejecución
- `ResultModelVersion`: Versión del modelo generado (si exitoso)

---

## Relaciones y Cardinalidades

### Relaciones Principales

| Entidad Origen | Relación | Entidad Destino | Cardinalidad | Descripción |
|----------------|----------|-----------------|--------------|-------------|
| **User** | asignado a | **PointOfSale** | N:M | Operadores asignados a puntos de venta (tabla intermedia: `UserPointOfSale`) |
| **User** | realiza | **Sale** | 1:N | Un usuario puede realizar múltiples ventas |
| **User** | registra | **InventoryMovement** | 1:N | Un usuario registra múltiples movimientos |
| **User** | registra | **Return** | 1:N | Un usuario registra múltiples devoluciones |
| **PointOfSale** | tiene métodos | **PaymentMethod** | N:M | Puntos de venta tienen múltiples métodos de pago (tabla intermedia: `PointOfSalePaymentMethod`) |
| **PointOfSale** | registra ventas | **Sale** | 1:N | Un punto de venta registra múltiples ventas |
| **PointOfSale** | tiene stock | **Inventory** | 1:N | Un punto de venta tiene múltiples productos en stock |
| **Product** | tiene fotos | **ProductPhoto** | 1:N | Un producto tiene múltiples fotos de referencia |
| **Product** | pertenece a | **Collection** | N:1 | Un producto pertenece a una colección (opcional, nullable) |
| **Product** | se vende | **Sale** | 1:N | Un producto puede venderse múltiples veces |
| **Product** | en stock | **Inventory** | 1:N | Un producto puede estar en stock en múltiples puntos de venta |
| **Sale** | tiene foto | **SalePhoto** | 1:0..1 | Una venta puede tener una foto (opcional) |
| **Sale** | puede tener devolución | **Return** | 1:0..N | Una venta puede tener múltiples devoluciones |
| **Sale** | genera movimiento | **InventoryMovement** | 1:1 | Cada venta genera un movimiento de inventario |
| **Return** | genera movimiento | **InventoryMovement** | 1:1 | Cada devolución genera un movimiento de inventario |
| **Inventory** | tiene movimientos | **InventoryMovement** | 1:N | Un inventario tiene múltiples movimientos históricos |
| **Product** | tiene componentes | **ProductComponentAssignment** | 1:N | Un producto puede tener múltiples componentes asignados |
| **ProductComponent** | asignado a | **ProductComponentAssignment** | 1:N | Un componente puede asignarse a múltiples productos |
| **ProductComponent** | en plantilla | **ComponentTemplateItem** | 1:N | Un componente puede estar en múltiples plantillas |
| **ComponentTemplate** | tiene items | **ComponentTemplateItem** | 1:N | Una plantilla tiene múltiples items de componentes |
| **User** | tiene tokens | **RefreshToken** | 1:N | Un usuario tiene múltiples refresh tokens |
| **User** | inicia entrenamiento | **ModelTrainingJob** | 1:N | Un usuario puede iniciar múltiples entrenamientos |

### Reglas de Negocio Implícitas

1. **Usuarios Administradores:**
   - No requieren asignación en `UserPointOfSale`
   - Tienen acceso a todos los puntos de venta por lógica de aplicación
   - Pueden ver y gestionar todos los productos del catálogo global

2. **Usuarios Operadores:**
   - Deben estar asignados al menos a un punto de venta en `UserPointOfSale`
   - Solo pueden registrar ventas en puntos de venta asignados
   - **Solo pueden ver productos que tienen registros en `Inventory` para sus puntos de venta asignados** (independientemente de la cantidad)
   - Pueden seleccionar productos con `Quantity = 0` pero el sistema impedirá completar la venta

3. **Métodos de Pago:**
   - Un punto de venta debe tener al menos un método de pago asignado
   - Solo se pueden usar métodos de pago activos y asignados al punto de venta

4. **Fotos de Productos:**
   - Un producto debe tener al menos una foto para usar reconocimiento de imágenes
   - Solo una foto puede ser marcada como `IsPrimary = true` por producto

5. **Stock:**
   - El stock no puede ser negativo (validación a nivel de aplicación)
   - Cada movimiento actualiza `Inventory.Quantity` y crea registro en `InventoryMovement`

6. **Ventas:**
   - El precio en `Sale` es un snapshot (no referencia al precio actual del producto)
   - Una venta debe tener un método de pago válido para el punto de venta
   - Si el POS tiene `AllowManualPriceEdit = true`, el operador puede enviar un precio manual; en caso contrario, el sistema rechaza cualquier precio manual
   - Cuando el precio es modificado, se almacena `PriceWasOverridden = true` y `OriginalProductPrice` con el precio oficial del catálogo
   - El historial y detalle de ventas muestra un indicador visual cuando el precio fue modificado

7. **Devoluciones:**
   - Una devolución debe asociarse a una o más ventas existentes (vía ReturnSale)
   - El producto devuelto debe coincidir con el producto de las ventas originales
   - La devolución debe realizarse en el mismo punto de venta de las ventas originales
   - Solo se pueden asociar ventas de los últimos 30 días
   - La cantidad total devuelta no puede exceder la cantidad disponible (vendida - ya devuelta)
   - La categoría de devolución es obligatoria (Defectuoso, TamañoIncorrecto, NoSatisfecho, Otro)
   - El motivo de texto libre es opcional (máximo 500 caracteres)
   - Operadores solo pueden registrar devoluciones en sus puntos de venta asignados

---

## Índices y Optimizaciones

### Índices Primarios

Todas las entidades utilizan `Id` (UUID) como clave primaria con índice automático.

### Índices Únicos

| Tabla | Campo(s) | Propósito |
|-------|----------|-----------|
| `User` | `Username` | Login único |
| `User` | `Email` | Email único (si se proporciona) |
| `PointOfSale` | `Code` | Código único de identificación |
| `Product` | `SKU` | Código único para matching en importaciones |
| `PaymentMethod` | `Code` | Código único del método de pago |
| `Inventory` | `(ProductId, PointOfSaleId)` | Un solo registro por combinación |
| `UserPointOfSale` | `(UserId, PointOfSaleId, IsActive)` filtro `IsActive=true` | Una sola asignación activa por par usuario-POS |
| `PointOfSalePaymentMethod` | `(PointOfSaleId, PaymentMethodId)` | Evitar métodos duplicados |
| `ProductComponent` | `Description` | Descripción única de componente |
| `ProductComponentAssignment` | `(ProductId, ComponentId)` | Un componente por producto |
| `ComponentTemplateItem` | `(TemplateId, ComponentId)` | Un componente por plantilla |
| `RefreshToken` | `Token` | Token único |
| `ModelMetadata` | `Version` | Versión de modelo única |
| `ReturnSale` | `(ReturnId, SaleId)` | Evitar duplicados de asociación |

### Índices Compuestos para Consultas Frecuentes

#### Tabla: Sale

| Índice | Campos | Propósito | Casos de Uso |
|--------|--------|-----------|--------------|
| `IX_Sale_PointOfSale_SaleDate` | `(PointOfSaleId, SaleDate DESC)` | Consultas de ventas por punto de venta y fecha | Historial de ventas por punto de venta |
| `IX_Sale_Product_SaleDate` | `(ProductId, SaleDate DESC)` | Consultas de ventas por producto | Productos más vendidos, historial por producto |
| `IX_Sale_User_SaleDate` | `(UserId, SaleDate DESC)` | Consultas de ventas por operador | Rendimiento por operador |
| `IX_Sale_PaymentMethod_SaleDate` | `(PaymentMethodId, SaleDate DESC)` | Consultas de ventas por método de pago | Reportes por método de pago |
| `IX_Sale_BulkOperation` | `(BulkOperationId)` | Recuperar todas las ventas de un checkout masivo | Detalle y devolución de una operación masiva |

**Justificación:** Las consultas de historial de ventas (caso de uso #10) requieren filtrado por múltiples criterios y ordenamiento por fecha. Estos índices optimizan las consultas más comunes. `IX_Sale_BulkOperation` agrupa las ventas creadas en un mismo checkout masivo, que se consultan y anulan como una unidad.

#### Tabla: InventoryMovement

| Índice | Campos | Propósito | Casos de Uso |
|--------|--------|-----------|--------------|
| `IX_InventoryMovement_Inventory` | `(InventoryId)` | Búsqueda de movimientos por inventario | Trazabilidad de stock |
| `IX_InventoryMovement_MovementDate` | `(MovementDate)` | Consultas por fecha | Reportes temporales |
| `IX_InventoryMovement_Inventory_MovementDate` | `(InventoryId, MovementDate)` | Historial de movimientos por inventario ordenado | Trazabilidad de stock |

**Justificación:** La tabla `InventoryMovement` crecerá rápidamente y necesita índices para consultas de historial y auditoría. Los índices por `SaleId`, `ReturnId` y `(UserId, MovementDate)` se resuelven a través de las relaciones FK configuradas en EF Core.

#### Tabla: Inventory

| Índice | Campos | Propósito | Casos de Uso |
|--------|--------|-----------|--------------|
| `IX_Inventory_PointOfSale_Quantity` | `(PointOfSaleId, Quantity)` | Consultas de stock bajo por punto de venta | Alertas de stock bajo (Fase 2) |
| `IX_Inventory_Product` | `(ProductId)` | Consultas de stock total por producto | Vista centralizada de stock |
| `IX_Inventory_PointOfSale_Product_IsActive` | `(PointOfSaleId, ProductId, IsActive)` | Resolver el registro de stock vigente de un producto en un punto de venta sin leer los desasignados | Venta, devolución y ajuste de inventario |

**Justificación:** Optimiza las consultas de inventario por punto de venta y producto, esenciales para el caso de uso #11. El índice con `IsActive` cubre el camino más caliente: localizar la asignación activa de un producto en un punto de venta durante la venta.

#### Tabla: ProductPhoto

| Índice | Campos | Propósito | Casos de Uso |
|--------|--------|-----------|--------------|
| `IX_ProductPhoto_Product_DisplayOrder` | `(ProductId, DisplayOrder)` | Ordenamiento de fotos por producto | Visualización de catálogo |

**Justificación:** Permite cargar fotos ordenadas eficientemente para el reconocimiento de imágenes.

#### Tabla: Return

| Índice | Campos | Propósito | Casos de Uso |
|--------|--------|-----------|--------------|
| `IX_Return_PointOfSale_ReturnDate` | `(PointOfSaleId, ReturnDate DESC)` | Historial de devoluciones por punto de venta | Reportes de devoluciones |
| `IX_Return_Product_ReturnDate` | `(ProductId, ReturnDate DESC)` | Historial de devoluciones por producto | Análisis de productos |

**Justificación:** Optimiza las consultas de devoluciones por punto de venta y producto.

#### Tabla: ReturnSale

| Índice | Campos | Propósito | Casos de Uso |
|--------|--------|-----------|--------------|
| `IX_ReturnSale_Sale` | `(SaleId)` | Búsqueda de devoluciones asociadas a una venta | Cálculo de cantidad disponible para devolución |
| `IX_ReturnSale_Return` | `(ReturnId)` | Obtener ventas asociadas a una devolución | Detalle de devolución |
| `UQ_ReturnSale_Return_Sale` | `(ReturnId, SaleId)` | Evitar duplicados de asociación | Integridad de datos |

**Justificación:** Optimiza el cálculo de cantidades disponibles para devolución y la consulta de ventas asociadas a una devolución.

### Índices Adicionales para Búsquedas

| Tabla | Campo | Tipo | Propósito |
|-------|-------|------|-----------|
| `Product` | `Name` | B-tree | Búsqueda por nombre de producto |
| `Product` | `SKU` | B-tree (único) | Búsqueda rápida por SKU (caso de uso #6) |
| `PointOfSale` | `Name` | B-tree | Búsqueda por nombre de punto de venta |
| `User` | `Username` | B-tree (único) | Login rápido |

### Optimizaciones Específicas para PostgreSQL

#### 1. Particionamiento (Fase 2 - Preparado)

Las tablas `Sale` e `InventoryMovement` pueden particionarse por rango de fechas cuando crezcan significativamente:

```sql
-- Ejemplo para Fase 2
CREATE TABLE Sale_2024 PARTITION OF Sale
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

**Beneficio:** Mejora el rendimiento de consultas históricas y facilita el archivado.

#### 2. Índices Parciales

Para consultas frecuentes de datos activos:

```sql
-- Solo indexar productos activos
CREATE INDEX IX_Product_Active_SKU ON Product(SKU) 
WHERE IsActive = true;

-- Solo indexar ventas recientes (últimos 6 meses)
CREATE INDEX IX_Sale_Recent ON Sale(SaleDate DESC) 
WHERE SaleDate >= CURRENT_DATE - INTERVAL '6 months';
```

**Beneficio:** Reduce el tamaño de los índices y mejora el rendimiento de consultas comunes.

#### 3. Full-Text Search (Fase 2 - Preparado)

Para búsquedas avanzadas en descripciones de productos:

```sql
-- Preparado para Fase 2
ALTER TABLE Product ADD COLUMN SearchVector tsvector;
CREATE INDEX IX_Product_SearchVector ON Product USING GIN(SearchVector);
```

**Beneficio:** Búsquedas de texto completo más eficientes que `LIKE`.

#### 4. Connection Pooling

Configurar pool de conexiones en Entity Framework Core:

```csharp
// En Program.cs
services.AddDbContext<ApplicationDbContext>(options =>
    options.UseNpgsql(connectionString, npgsqlOptions =>
    {
        npgsqlOptions.MaxBatchSize(50);
        npgsqlOptions.CommandTimeout(30);
    }));
```

**Recomendación:** Máximo 5-10 conexiones simultáneas para free-tier.

#### 5. VACUUM y Mantenimiento

Configurar VACUUM automático para mantener el rendimiento:

```sql
-- Configuración recomendada para free-tier
ALTER TABLE Sale SET (autovacuum_vacuum_scale_factor = 0.1);
ALTER TABLE InventoryMovement SET (autovacuum_vacuum_scale_factor = 0.1);
```

**Beneficio:** Mantiene las tablas optimizadas sin intervención manual.

### Estrategias de Optimización por Caso de Uso

#### Caso de Uso #1: Importar productos desde Excel
- **Índice crítico:** `Product.SKU` (único) para matching rápido
- **Optimización:** Usar `UPSERT` (INSERT ... ON CONFLICT) para actualizaciones eficientes

#### Caso de Uso #5 y #6: Registrar ventas
- **Índices críticos:** 
  - `Sale(PointOfSaleId, SaleDate)` para validación rápida
  - `Inventory(ProductId, PointOfSaleId)` para verificar stock
- **Optimización:** Transacciones atómicas para venta + movimiento de inventario

#### Caso de Uso #7: Gestionar devoluciones
- **Índice crítico:** `Return(SaleId)` para validar venta original
- **Optimización:** Transacciones atómicas para devolución + movimiento de inventario

#### Caso de Uso #10: Consultar historial de ventas
- **Índices críticos:** Todos los índices compuestos de `Sale`
- **Optimización:** Paginación obligatoria (máx 50 items/página)

#### Caso de Uso #11: Consultar inventario
- **Índices críticos:** `Inventory(PointOfSaleId, Quantity)` y `Inventory(ProductId)`
- **Optimización:** Cache en memoria para productos frecuentes (backend)

### Consideraciones de Escalabilidad (Fase 2)

1. **Read Replicas:** Para reportes pesados, usar réplicas de lectura
2. **Caching:** Redis para cache de productos y stock frecuente
3. **Archivado:** Mover datos antiguos (>2 años) a tablas de archivado
4. **Materialized Views:** Para agregaciones complejas de reportes
5. **Índices Adicionales:** Basados en patrones de consulta reales (monitoreo)

---

## Consideraciones de Implementación

### Campos de Auditoría

Todas las entidades principales incluyen:
- `CreatedAt`: Timestamp de creación (automático)
- `UpdatedAt`: Timestamp de última actualización (automático, trigger)

### Soft Delete

Las entidades críticas (`User`, `Product`, `PointOfSale`) utilizan `IsActive` en lugar de eliminación física para mantener integridad referencial histórica.

### UUID vs Integer

Se utiliza UUID como clave primaria para:
- **Ventajas:**
  - Evitar problemas de colisión en sistemas distribuidos
  - Mayor seguridad (no expone información sobre cantidad de registros)
  - Facilita sincronización offline (Fase 2)
- **Desventajas:**
  - Mayor tamaño (16 bytes vs 4-8 bytes)
  - Rendimiento ligeramente inferior en joins
- **Mitigación:** Los índices compensan el impacto en rendimiento

### Normalización

El modelo sigue 3NF (Tercera Forma Normal) con las siguientes excepciones intencionales:
- `Sale.Price`: Snapshot del precio efectivo de venta (redundante pero necesario para integridad histórica)
- `Sale.OriginalProductPrice`: Precio oficial del catálogo al momento de la venta cuando hubo override (redundante pero necesario para auditoría)
- `Return.ProductId`: Redundante pero útil para consultas sin join

### Constraints y Validaciones

#### A Nivel de Base de Datos

```sql
-- Stock no negativo (validación en aplicación, constraint opcional)
ALTER TABLE Inventory ADD CONSTRAINT CHK_Quantity_NonNegative 
CHECK (Quantity >= 0);

-- Precio positivo
ALTER TABLE Product ADD CONSTRAINT CHK_Price_Positive 
CHECK (Price > 0);

-- Cantidad de venta positiva
ALTER TABLE Sale ADD CONSTRAINT CHK_Sale_Quantity_Positive 
CHECK (Quantity > 0);
```

#### A Nivel de Aplicación

- Validación de métodos de pago asignados al punto de venta
- Validación de stock disponible antes de venta
- Validación de usuario asignado al punto de venta (para operadores)
- Validación de SKU único en importaciones

---

## Migración y Evolución del Modelo

### Fase 1 (MVP) - Implementación Inicial

1. Crear todas las tablas base
2. Implementar índices principales
3. Seed de datos iniciales (métodos de pago predefinidos)
4. Migraciones de Entity Framework Core

### Fase 2 - Extensiones Preparadas

El modelo está preparado para agregar sin cambios estructurales mayores:

1. **Historial de Precios:**
   ```sql
   CREATE TABLE ProductPriceHistory (
       Id UUID PRIMARY KEY,
       ProductId UUID REFERENCES Product(Id),
       Price DECIMAL NOT NULL,
       EffectiveDate TIMESTAMP NOT NULL,
       CreatedAt TIMESTAMP DEFAULT NOW()
   );
   ```

2. **Alertas de Stock Bajo:**
   - Campo `MinimumThreshold` ya existe en `Inventory`
   - Nueva tabla `StockAlert` para registro de alertas

3. **Promociones y Descuentos:**
   ```sql
   CREATE TABLE SaleDiscount (
       Id UUID PRIMARY KEY,
       SaleId UUID REFERENCES Sale(Id),
       DiscountType VARCHAR(50), -- Percentage, Fixed
       DiscountValue DECIMAL NOT NULL,
       CreatedAt TIMESTAMP DEFAULT NOW()
   );
   ```

4. **Feedback de Reconocimiento de Imágenes:**
   ```sql
   CREATE TABLE ImageRecognitionFeedback (
       Id UUID PRIMARY KEY,
       SaleId UUID REFERENCES Sale(Id),
       ProductId UUID REFERENCES Product(Id),
       ConfidenceScore DECIMAL,
       WasCorrect BOOLEAN,
       CreatedAt TIMESTAMP DEFAULT NOW()
   );
   ```

---

## Resumen de Optimizaciones para Free-tier

### Reducción de Carga en Base de Datos

1. **Índices Selectivos:** Solo índices necesarios para consultas frecuentes
2. **Paginación Obligatoria:** Todas las listas paginadas (máx 50 items)
3. **Cache en Backend:** Productos y métodos de pago en memoria
4. **Lazy Loading:** Carga diferida de relaciones no críticas
5. **Connection Pooling:** Máximo 5-10 conexiones simultáneas

### Optimización de Almacenamiento

1. **Fotos en Object Storage:** No en base de datos (reduce tamaño de DB)
2. **UUID Eficiente:** Aunque más grande, evita problemas de escalabilidad
3. **Soft Delete:** Mantiene historial sin crecimiento excesivo de tablas

### Monitoreo Recomendado

1. **Tamaño de Tablas:** Monitorear crecimiento de `Sale` e `InventoryMovement`
2. **Uso de Índices:** Analizar índices no utilizados con `pg_stat_user_indexes`
3. **Tiempo de Consulta:** Monitorear queries lentas con `pg_stat_statements`
4. **Conexiones:** Alertar cuando se acerque al límite del pool

---

## Conclusión

Este modelo de datos está diseñado para:

✅ **Soportar todos los casos de uso del MVP** de manera eficiente  
✅ **Escalar hacia la Fase 2** sin cambios estructurales mayores  
✅ **Optimizar para free-tier** con índices selectivos y paginación  
✅ **Mantener integridad** mediante constraints y validaciones  
✅ **Facilitar auditoría** con campos de trazabilidad completos  
✅ **Preparar para crecimiento** con campos y estructuras extensibles  

El modelo balancea normalización con rendimiento, priorizando las consultas más frecuentes mientras mantiene la flexibilidad para evolucionar según las necesidades del negocio.

