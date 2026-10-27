# sales-management Specification

## Purpose

Register sales at the POS via manual product selection with stock, payment method, and price-policy validation in one atomic flow.
## Requirements
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

### Requirement: Sales History and Queries

The system SHALL provide sales history with filtering capabilities, applying role-based access control (administrators see all sales, operators see only sales from assigned points of sale). Each sale in the response MUST include a `hasReturn` boolean indicating whether the sale has at least one associated return record.

#### Scenario: Administrator views full sales history

- **WHEN** authenticated administrator requests GET /api/sales
- **AND** applies optional filters (date range, product, POS, user, payment method)
- **THEN** system returns paginated sales (max 50 per page)
- **AND** includes sale details (date, product, quantity, price, total, payment method, operator, photo indicator)
- **AND** includes `hasReturn: true` for sales that have at least one associated ReturnSale record
- **AND** includes `hasReturn: false` for sales with no associated returns
- **AND** includes pagination metadata (totalCount, totalPages, currentPage)
- **AND** sales from all points of sale are visible

#### Scenario: Operator views sales history for assigned POS

- **WHEN** authenticated operator requests GET /api/sales
- **AND** applies optional filters
- **THEN** system returns sales ONLY from points of sale assigned to operator
- **AND** each sale includes `hasReturn` boolean
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

### Requirement: Sales Override Indicator in History and Details

The system SHALL expose and display a clear indicator when a sale used a manually overridden price.

#### Scenario: Override badge in sales history list

- **WHEN** user requests sales history
- **AND** a returned sale has PriceWasOverridden = true
- **THEN** API response includes the override flag
- **AND** frontend shows a visible indicator such as "Precio modificado" for that sale row

#### Scenario: Override details in sale detail view

- **WHEN** user requests a specific sale detail
- **AND** the sale has PriceWasOverridden = true
- **THEN** API response includes PriceWasOverridden and OriginalProductPrice
- **AND** frontend shows the overridden sale price and original product price reference

### Requirement: Atomic Bulk Sales Registration
The system SHALL provide `POST /api/sales/bulk` to register multiple sale lines in a single atomic operation, where all lines succeed or none are persisted.

#### Scenario: Bulk sale checkout succeeds
- **WHEN** an authenticated user submits a bulk request with valid lines
- **AND** every line passes authorization, payment method, quantity, and stock validation
- **THEN** the system creates one Sale record per line
- **AND** creates corresponding inventory movements for all lines
- **AND** commits the transaction only after all operations succeed
- **AND** returns a successful bulk result with created sale identifiers

#### Scenario: Bulk sale checkout fails on one invalid line
- **WHEN** a bulk request contains at least one line that fails validation
- **THEN** the system aborts the bulk operation
- **AND** rolls back all pending Sale and InventoryMovement writes
- **AND** returns a single error response describing the failing condition

### Requirement: Bulk Checkout Invariants
The system SHALL enforce cross-line invariants for bulk sales: all lines MUST use the same point of sale and the same payment method.

#### Scenario: Reject mixed point-of-sale lines
- **WHEN** a bulk request includes lines with different `PointOfSaleId` values
- **THEN** the system returns `400 Bad Request`
- **AND** does not persist any sale line

#### Scenario: Reject mixed payment method lines
- **WHEN** a bulk request includes lines with different `PaymentMethodId` values
- **THEN** the system returns `400 Bad Request`
- **AND** does not persist any sale line

### Requirement: Global Bulk Confirmation Note
The system SHALL support one optional checkout note in bulk sales and propagate it consistently to each created sale record.

#### Scenario: Apply global note to all created sales
- **WHEN** a bulk checkout is confirmed with a global note
- **THEN** every sale created by that bulk operation stores the same note content
- **AND** note validation rules remain consistent with existing sale note constraints

### Requirement: Idempotent Bulk Submission
The system SHALL support idempotent retries for bulk sale checkout requests using an `Idempotency-Key` to prevent duplicate sale creation.

#### Scenario: Retry with same idempotency key
- **WHEN** a client sends a valid bulk request with an `Idempotency-Key`
- **AND** the same client retries with the same key and equivalent payload
- **THEN** the system returns the original successful result
- **AND** does not create additional duplicate sale records

#### Scenario: Reuse key with different payload
- **WHEN** a client reuses an existing `Idempotency-Key` with a different payload
- **THEN** the system rejects the request with a validation/conflict response
- **AND** preserves previously created records unchanged

### Requirement: Bulk Operation Traceability
The system SHALL assign a `BulkOperationId` to each successful bulk checkout and associate all resulting sales with that operation identifier.

#### Scenario: Group sales created by one bulk checkout
- **WHEN** a bulk checkout succeeds
- **THEN** all created sales include the same `BulkOperationId`
- **AND** the bulk response returns that identifier for auditing and support workflows

### Requirement: Bulk checkout applies gift cards
`POST /api/sales/bulk` SHALL accept zero or more gift card codes together with product lines. All lines SHALL still share one point of sale and one payment method. Jewelry lines SHALL create inventory movements. Coverage and card balances SHALL commit in the same transaction as the sales. A failed line SHALL roll back sales, movements, and card changes. The cart checkout and the manual sale page SHALL both send gift card codes on this endpoint when the operator attaches cards.

#### Scenario: Manual sale page applies a gift card
- **GIVEN** an operator on the manual sale page with one jewelry line and a valid gift card attached
- **WHEN** the operator confirms the sale
- **THEN** the client submits `POST /api/sales/bulk` with that line and the gift card codes
- **AND** does not look up the gift card code as a product SKU

#### Scenario: Gift card checkout rolls back together
- **GIVEN** a bulk request that applies a valid gift card and includes one line with no stock
- **WHEN** the user submits the checkout
- **THEN** the system persists no sale, no inventory movement, and no coverage
- **AND** the card spendable balance is unchanged

#### Scenario: Sale history exposes gift-card coverage

- **GIVEN** a product sale with 100.00 EUR of gift-card coverage
- **WHEN** a user loads sales history including that sale
- **THEN** the sale shows its catalog total
- **AND** shows gift-card coverage of 100.00 EUR

#### Scenario: Mixed payment methods stay rejected
- **GIVEN** a bulk request that applies a gift card
- **AND** two product lines with different payment method ids
- **WHEN** the user submits the checkout
- **THEN** the system returns 400 Bad Request
- **AND** persists nothing

### Requirement: System product sales only through gift card issuance
`POST /api/sales/bulk` SHALL NOT create a sale for a system product. The system gift-card product SHALL be sold only through `POST /api/gift-cards`.

#### Scenario: Reject bulk checkout of the system gift-card product
- **GIVEN** a bulk request whose lines include the system gift-card product
- **WHEN** the user submits the checkout
- **THEN** the system returns 400 Bad Request
- **AND** persists no sale or inventory movement

