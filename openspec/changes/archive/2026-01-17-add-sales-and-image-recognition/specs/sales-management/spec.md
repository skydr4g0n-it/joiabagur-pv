> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

## ADDED Requirements

### Requirement: Sales Registration with Dual Entry Methods

The system SHALL allow operators to register sales using two methods: AI-assisted image recognition (with photo attached) or manual product selection (with optional photo). Both methods validate stock availability, payment method assignment, and operator authorization before creating sale records.

#### Scenario: Create sale with image recognition successfully

- **WHEN** authenticated operator captures product photo
- **AND** selects product from AI suggestions
- **AND** enters quantity (>= 1)
- **AND** selects payment method assigned to point of sale
- **AND** product has sufficient stock at point of sale
- **THEN** system creates Sale record with price snapshot from current Product.Price
- **AND** creates SalePhoto record with compressed photo (JPEG 80%, <= 2MB)
- **AND** creates InventoryMovement record with type "Sale" (via inventory-management integration)
- **AND** updates Inventory.Quantity atomically in same transaction
- **AND** returns success with sale ID and low stock warning if applicable

#### Scenario: Create manual sale without photo

- **WHEN** authenticated operator searches and selects product by SKU or name
- **AND** enters quantity (>= 1)
- **AND** selects payment method assigned to point of sale
- **AND** product has sufficient stock at point of sale
- **THEN** system creates Sale record with price snapshot
- **AND** SalePhoto is null (no photo attached)
- **AND** creates InventoryMovement and updates stock atomically
- **AND** returns success with sale ID

#### Scenario: Create manual sale with optional photo

- **WHEN** authenticated operator manually selects product
- **AND** optionally attaches photo (e.g., for documentation purposes)
- **AND** enters quantity and selects payment method
- **AND** product has sufficient stock
- **THEN** system creates Sale with price snapshot
- **AND** creates SalePhoto with compressed photo
- **AND** creates InventoryMovement and updates stock atomically

#### Scenario: Reject sale with insufficient stock

- **WHEN** operator attempts to create sale
- **AND** requested quantity > available stock at point of sale
- **THEN** system validates stock before creating sale record
- **AND** returns 400 Bad Request with error: "Stock insuficiente. Disponible: X, Solicitado: Y"
- **AND** does not create sale, photo, or inventory movement
- **AND** operator can cancel or reduce quantity

#### Scenario: Double stock validation for concurrency safety

- **WHEN** operator selects product and enters quantity
- **THEN** system performs first validation to show available stock in form
- **AND** displays "Stock disponible: X unidades"
- **WHEN** operator confirms sale
- **THEN** system performs second validation immediately before transaction commit
- **AND** validates stock has not changed since first check
- **AND** if stock changed (another sale occurred), returns error: "Stock cambió durante la venta. Disponible ahora: X, Solicitado: Y"
- **AND** operator can retry with updated stock information

#### Scenario: Concurrent sales of last unit

- **WHEN** two operators attempt to sell last unit of product simultaneously
- **AND** both see "Stock disponible: 1" (first validation passed for both)
- **AND** Operator A confirms sale first (stock becomes 0)
- **AND** Operator B confirms sale second
- **THEN** Operator B's second validation fails
- **AND** returns error: "Stock cambió. Disponible: 0, Solicitado: 1"
- **AND** Operator A's sale succeeds, Operator B's sale is rejected

#### Scenario: Reject sale for unassigned product

- **WHEN** operator attempts to create sale
- **AND** product has no Inventory record at point of sale (IsActive = false or missing)
- **THEN** system returns 400 Bad Request with error: "El producto no está asignado a este punto de venta"
- **AND** does not create sale record
- **NOTE**: Uses IStockValidationService from inventory-management

#### Scenario: Reject sale with unavailable payment method

- **WHEN** operator attempts to create sale
- **AND** payment method is not assigned to point of sale OR IsActive = false
- **THEN** system returns 400 Bad Request with error: "El método de pago no está disponible en este punto de venta"
- **AND** does not create sale record
- **NOTE**: Uses payment-method-management validation integration

#### Scenario: Reject sale from unauthorized operator

- **WHEN** operator attempts to create sale at point of sale not assigned to them
- **THEN** system returns 403 Forbidden
- **AND** provides error message indicating unauthorized access
- **NOTE**: Uses access-control integration

#### Scenario: Low stock warning after sale

- **WHEN** sale is created successfully
- **AND** remaining stock after sale <= Inventory.MinimumThreshold (if configured)
- **THEN** system returns success response with lowStockWarning flag = true
- **AND** includes remaining stock quantity in response
- **AND** frontend displays non-blocking toast: "?? Quedan solo X unidades de este producto"
- **NOTE**: Warning does not block sale, only informs operator

#### Scenario: Validate quantity is positive

- **WHEN** operator attempts to create sale with quantity <= 0
- **THEN** system returns 400 Bad Request with validation error
- **AND** does not create sale record

#### Scenario: Price snapshot on sale creation

- **WHEN** sale is created
- **THEN** system captures current Product.Price at time of sale
- **AND** stores price in Sale.Price field (immutable snapshot)
- **AND** subsequent product price changes do not affect historical Sale.Price

### Requirement: Transaction-Based Stock Updates

The system SHALL ensure atomic consistency between sale creation and inventory updates using database transactions, preventing orphaned sales or stock mismatches.

#### Scenario: Atomic sale and inventory update

- **WHEN** sale is created
- **THEN** system begins database transaction
- **AND** creates Sale record
- **AND** creates SalePhoto record if photo provided
- **AND** calls IInventoryService.CreateSaleMovement (creates InventoryMovement + updates stock)
- **AND** commits transaction only if all operations succeed
- **AND** ensures InventoryMovement always exists for every Sale

#### Scenario: Rollback on inventory update failure

- **WHEN** sale creation succeeds but inventory update fails
- **THEN** system rolls back entire transaction
- **AND** Sale record is not persisted
- **AND** SalePhoto is not saved to storage
- **AND** Inventory.Quantity remains unchanged
- **AND** returns error to operator

#### Scenario: Rollback on photo upload failure

- **WHEN** sale and inventory update succeed but photo upload fails
- **THEN** system rolls back entire transaction
- **AND** removes uploaded photo from storage if partially saved
- **AND** returns error to operator

### Requirement: Photo Compression and Storage

The system SHALL compress sale photos to reduce storage costs and improve mobile upload performance, saving photos only on successful sale completion.

#### Scenario: Compress photo before storage

- **WHEN** operator provides photo with sale (image recognition or manual)
- **THEN** system compresses photo to JPEG quality 80%
- **AND** converts all formats (PNG, HEIC, etc.) to JPEG
- **AND** resizes to max 1920x1920 pixels if larger (preserves aspect ratio)
- **AND** validates output size <= 2MB
- **AND** returns error if compressed size still exceeds 2MB

#### Scenario: Save photo only on successful sale

- **WHEN** sale transaction commits successfully
- **THEN** system uploads compressed photo to storage (IFileStorageService)
- **AND** creates SalePhoto record with FilePath, FileName, FileSize, MimeType
- **AND** photo becomes permanently associated with sale

#### Scenario: Discard photo on canceled sale

- **WHEN** operator cancels sale before confirmation
- **OR** sale creation fails validation or transaction rollback
- **THEN** system discards captured/uploaded photo immediately
- **AND** does not save photo to storage
- **AND** does not create SalePhoto record

### Requirement: Sales History and Queries

The system SHALL provide sales history with filtering capabilities, applying role-based access control (administrators see all sales, operators see only sales from assigned points of sale).

#### Scenario: Administrator views full sales history

- **WHEN** authenticated administrator requests GET /api/sales
- **AND** applies optional filters (date range, product, POS, user, payment method)
- **THEN** system returns paginated sales (max 50 per page)
- **AND** includes sale details (date, product, quantity, price, total, payment method, operator, photo indicator)
- **AND** includes pagination metadata (totalCount, totalPages, currentPage)
- **AND** sales from all points of sale are visible

#### Scenario: Operator views sales history for assigned POS

- **WHEN** authenticated operator requests GET /api/sales
- **AND** applies optional filters
- **THEN** system returns sales ONLY from points of sale assigned to operator
- **AND** filters by UserPointOfSale assignments (via access-control integration)
- **AND** applies same pagination and filtering as admin
- **AND** sales from unassigned POS are invisible

#### Scenario: Filter sales by date range

- **WHEN** user requests sales history with date range filter (startDate, endDate)
- **THEN** system returns sales where SaleDate >= startDate AND SaleDate <= endDate
- **AND** defaults to last 30 days if no date range specified

#### Scenario: Filter sales by product

- **WHEN** user requests sales history with product filter (productId or SKU)
- **THEN** system returns sales matching specified product
- **AND** includes product name and SKU in response

#### Scenario: Filter sales by payment method

- **WHEN** user requests sales history with payment method filter
- **THEN** system returns sales matching specified payment method
- **AND** includes payment method name in response

#### Scenario: View sale details with photo

- **WHEN** user requests GET /api/sales/{id}
- **THEN** system returns full sale details
- **AND** includes SalePhoto with pre-signed URL if photo exists
- **AND** includes product details, payment method, operator name, inventory movement reference
- **AND** admin can view any sale, operator can view only sales from assigned POS

#### Scenario: Require authentication for sales access

- **WHEN** unauthenticated user requests sales endpoints
- **THEN** system returns 401 Unauthorized

### Requirement: Multi-Unit Sales Support

The system SHALL allow selling multiple units of the same product in a single transaction, validating total stock availability.

#### Scenario: Create sale with multiple units

- **WHEN** operator creates sale with quantity = 5
- **AND** product has stock >= 5 at point of sale
- **THEN** system validates total stock availability
- **AND** creates single Sale record with Quantity = 5
- **AND** creates single InventoryMovement with QuantityChange = -5
- **AND** updates Inventory.Quantity -= 5 atomically

#### Scenario: Reject multi-unit sale with insufficient stock

- **WHEN** operator creates sale with quantity = 10
- **AND** product has stock = 7 at point of sale
- **THEN** system returns error: "Stock insuficiente. Disponible: 7, Solicitado: 10"
- **AND** does not create sale record

### Requirement: Optional Sale Notes

The system SHALL allow operators to add optional notes to sales for annotations (discounts, promotions, customer remarks).

#### Scenario: Add notes to sale

- **WHEN** operator creates sale
- **AND** provides notes text (e.g., "10% descuento cliente VIP")
- **THEN** system stores notes in Sale.Notes field (max 500 characters)
- **AND** notes are visible in sale details

#### Scenario: Create sale without notes

- **WHEN** operator creates sale without providing notes
- **THEN** system stores Sale.Notes as null
- **AND** sale is created successfully

#### Scenario: Validate notes length

- **WHEN** operator provides notes > 500 characters
- **THEN** system returns 400 Bad Request with validation error
- **AND** does not create sale

### Requirement: Price Display Format

The system SHALL display all monetary values using Euro (EUR) currency format with Spanish locale conventions throughout the sales interface.

#### Scenario: Display prices in Euro format

- **WHEN** displaying product prices, subtotals, or sale totals
- **THEN** the € symbol is shown before the numeric value
- **AND** prices are formatted with 2 decimal places
- **AND** Spanish locale (es-ES) formatting is used for Intl.NumberFormat

#### Scenario: Sales history currency display

- **WHEN** displaying sale amounts in history or reports
- **THEN** formatCurrency uses Intl.NumberFormat with locale 'es-ES' and currency 'EUR'
- **AND** amounts are displayed consistently across all views

### Requirement: Payment Method Selector Filtering

The system SHALL display only active and assigned payment methods in the sales form, preventing selection of unavailable methods.

#### Scenario: Display available payment methods

- **WHEN** operator opens sales form for specific point of sale
- **THEN** frontend fetches GET /api/payment-methods?pointOfSaleId={id}
- **AND** backend returns ONLY payment methods with active assignment (PointOfSalePaymentMethod.IsActive = true)
- **AND** frontend displays payment methods in dropdown/selector
- **AND** unavailable methods are not displayed

#### Scenario: Prevent selection of deactivated payment method

- **WHEN** payment method is deactivated after form loads but before submission
- **THEN** backend validation rejects sale with error: "El método de pago no está disponible en este punto de venta"
- **AND** frontend handles error gracefully and refreshes payment method list

### Requirement: Sales Authorization and Access Control

The system SHALL enforce role-based access and point-of-sale assignment restrictions for all sales operations.

#### Scenario: Operator creates sale at assigned POS only

- **WHEN** operator attempts to create sale
- **THEN** system validates operator is assigned to point of sale via UserPointOfSale
- **AND** allows sale if assignment exists
- **AND** returns 403 Forbidden if operator not assigned to POS

#### Scenario: Administrator creates sale at any POS

- **WHEN** authenticated administrator creates sale at any point of sale
- **THEN** system allows sale without UserPointOfSale validation
- **AND** admin can create sales at all points of sale

#### Scenario: Operator views only assigned POS sales

- **WHEN** operator requests sales history
- **THEN** system filters results to UserPointOfSale assignments
- **AND** operator cannot view sales from unassigned points of sale

