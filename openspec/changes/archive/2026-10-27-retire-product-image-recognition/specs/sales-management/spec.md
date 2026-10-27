## ADDED Requirements

### Requirement: Sales Registration by Manual Selection
The system SHALL allow operators to register sales by manual product selection. The system SHALL NOT offer an AI-assisted image-recognition entry method. Manual registration SHALL validate stock availability, payment method assignment, operator authorization, and point-of-sale price policy before creating sale records. An optional documentation photo on a manual sale remains allowed by the sales API. The recognition capture page is not an entry point.

#### Scenario: Create manual sale without photo
- **GIVEN** an authenticated operator assigned to the point of sale
- **WHEN** the operator searches and selects a product by SKU or name
- **AND** enters quantity (>= 1)
- **AND** selects a payment method assigned to the point of sale
- **AND** the product has sufficient stock at the point of sale
- **THEN** the system creates a Sale record using effective sale price rules
- **AND** SalePhoto is null
- **AND** the system creates an InventoryMovement and updates stock atomically
- **AND** the system returns success with the sale ID

#### Scenario: Create manual sale with optional photo
- **GIVEN** an authenticated operator
- **WHEN** the operator manually selects a product
- **AND** optionally attaches a documentation photo
- **AND** enters quantity and selects a payment method
- **AND** the product has sufficient stock
- **THEN** the system creates the Sale using effective sale price rules
- **AND** creates a SalePhoto with the compressed photo
- **AND** creates an InventoryMovement and updates stock atomically

#### Scenario: Reject sale with insufficient stock
- **GIVEN** an operator creating a sale
- **WHEN** the requested quantity is greater than available stock at the point of sale
- **THEN** the system validates stock before creating a sale record
- **AND** returns 400 Bad Request with error: "Stock insuficiente. Disponible: X, Solicitado: Y"
- **AND** does not create a sale, photo, or inventory movement

#### Scenario: Double stock validation for concurrency safety
- **GIVEN** an operator selecting a product and entering a quantity
- **WHEN** the form is shown
- **THEN** the system performs a first validation and displays "Stock disponible: X unidades"
- **WHEN** the operator confirms the sale
- **THEN** the system performs a second validation immediately before transaction commit
- **AND** if stock changed, returns error: "Stock cambió durante la venta. Disponible ahora: X, Solicitado: Y"

#### Scenario: Concurrent sales of last unit
- **GIVEN** two operators who both see "Stock disponible: 1"
- **WHEN** operator A confirms the sale first and stock becomes 0
- **AND** operator B confirms second
- **THEN** operator B's second validation fails with "Stock cambió. Disponible: 0, Solicitado: 1"
- **AND** operator A's sale succeeds

#### Scenario: Reject sale for unassigned product
- **GIVEN** a product with no Inventory record at the point of sale
- **WHEN** an operator attempts to create a sale for that product
- **THEN** the system returns 400 Bad Request with error: "El producto no está asignado a este punto de venta"
- **AND** does not create a sale record

#### Scenario: Reject sale with unavailable payment method
- **GIVEN** a payment method that is not assigned to the point of sale or is inactive
- **WHEN** an operator attempts to create a sale with that method
- **THEN** the system returns 400 Bad Request with error: "El método de pago no está disponible en este punto de venta"
- **AND** does not create a sale record

#### Scenario: Reject sale from unauthorized operator
- **GIVEN** an operator who is not assigned to the point of sale
- **WHEN** the operator attempts to create a sale at that point of sale
- **THEN** the system returns 403 Forbidden

#### Scenario: Reject manual price when POS disallows overrides
- **GIVEN** a point of sale with AllowManualPriceEdit = false
- **WHEN** an operator submits a sale request with an explicit price
- **THEN** the system returns 400 Bad Request
- **AND** does not create a sale record

#### Scenario: Validate manual price is positive when provided
- **GIVEN** a sale request with a manual price less than or equal to 0
- **WHEN** the operator submits the request
- **THEN** the system returns 400 Bad Request
- **AND** does not create a sale record

#### Scenario: Low stock warning after sale
- **GIVEN** a successful sale
- **WHEN** remaining stock is less than or equal to Inventory.MinimumThreshold, if configured
- **THEN** the response sets lowStockWarning to true and includes the remaining quantity
- **AND** the frontend displays a non-blocking toast: "⚠️ Quedan solo X unidades de este producto"

#### Scenario: Validate quantity is positive
- **GIVEN** a sale request with quantity less than or equal to 0
- **WHEN** the operator submits the request
- **THEN** the system returns 400 Bad Request
- **AND** does not create a sale record

#### Scenario: Price snapshot on sale creation
- **GIVEN** a sale that is created
- **WHEN** the sale is stored
- **THEN** the system stores the effective price in Sale.Price
- **AND** stores PriceWasOverridden = true and OriginalProductPrice = official Product.Price when an override is applied
- **AND** stores PriceWasOverridden = false and OriginalProductPrice = null when an override is not applied
- **AND** later product price changes do not change those historical fields

#### Scenario: No image-recognition sales entry
- **GIVEN** an authenticated operator
- **WHEN** the operator looks for a way to sell by product photo
- **THEN** the application has no `/sales/new/image` page and that path follows the existing catch-all to `/dashboard`
- **AND** the sales API is not required to accept an image-recognition suggestion payload

## MODIFIED Requirements

### Requirement: Photo Compression and Storage

The system SHALL compress sale photos to reduce storage costs and improve mobile upload performance, saving photos only on successful sale completion. This applies when a manual sale includes an optional documentation photo. Existing SalePhoto records remain readable.

#### Scenario: Compress photo before storage

- **GIVEN** an operator provides a photo with a manual sale
- **WHEN** the photo is accepted for storage
- **THEN** the system compresses the photo to JPEG quality 80%
- **AND** converts all formats (PNG, HEIC, etc.) to JPEG
- **AND** resizes to max 1920x1920 pixels if larger (preserves aspect ratio)
- **AND** validates output size <= 2MB
- **AND** returns an error if the compressed size still exceeds 2MB

#### Scenario: Save photo only on successful sale

- **GIVEN** a sale transaction that commits successfully and includes a photo
- **WHEN** the transaction commits
- **THEN** the system uploads the compressed photo to storage (IFileStorageService)
- **AND** creates a SalePhoto record with FilePath, FileName, FileSize, MimeType
- **AND** the photo becomes permanently associated with the sale

#### Scenario: Discard photo on canceled sale

- **GIVEN** an operator who cancels the sale before confirmation, or a sale that fails validation or rolls back
- **WHEN** the sale is not committed
- **THEN** the system discards the captured or uploaded photo immediately
- **AND** does not save the photo to storage
- **AND** does not create a SalePhoto record

## REMOVED Requirements

### Requirement: Sales Registration with Dual Entry Methods
**Reason**: AI-assisted image recognition is withdrawn. Sales are registered by manual selection only.
**Migration**: Use "Sales Registration by Manual Selection". Stock, payment, authorization, and price rules move there unchanged. The image-recognition success scenario is not carried forward.
