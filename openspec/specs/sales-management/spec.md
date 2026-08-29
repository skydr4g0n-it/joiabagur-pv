# sales-management Specification

## Purpose
TBD - created by archiving change add-sales-and-image-recognition. Update Purpose after archive.
## Requirements
### Requirement: Sales Registration with Entry Methods

The system SHALL allow operators to register sales using three methods: barcode/QR code scanning (replacing image recognition), manual product selection (with optional photo), or assisted natural-language search. The image recognition entry point is removed from the UI, but its backend controllers and frontend components remain intact in the codebase. All methods validate stock availability, payment method assignment, operator authorization, and point-of-sale price policy before creating sale records.

Assisted search is an entry method rather than a sale flow of its own: it selects a product and hands it to the manual sale flow, which continues to own quantity, payment method, price policy and stock validation. The behaviour of the panel itself is specified by the assisted-search-panel capability.

#### Scenario: Create sale with barcode/QR scanning successfully

- **WHEN** authenticated operator scans a QR code or barcode
- **AND** the decoded value matches an existing product SKU
- **AND** the product has active Inventory at the operator's POS
- **AND** operator enters quantity (>= 1)
- **AND** selects payment method assigned to point of sale
- **AND** product has sufficient stock at point of sale
- **THEN** system creates Sale record using effective sale price rules (official Product.Price by default, optional override only if POS allows manual price edit)
- **AND** SalePhoto is null (no photo attached unless operator explicitly adds one via manual flow)
- **AND** creates InventoryMovement record with type "Sale" (via inventory-management integration)
- **AND** updates Inventory.Quantity atomically in same transaction
- **AND** returns success with sale ID and low stock warning if applicable

#### Scenario: Create sale with image recognition (deprecated — code retained)

- **WHEN** authenticated operator navigates to the sales landing page
- **THEN** the "Reconocimiento de imagen" tile is NOT displayed
- **AND** the `GET /api/image-recognition/*` endpoints remain functional
- **AND** the `new-image.tsx` React component remains in the codebase
- **AND** the image recognition route (`/sales/new/image`) still resolves if accessed directly

#### Scenario: Create sale from an assisted search selection

- **WHEN** authenticated operator selects a product from the assisted search panel
- **THEN** the manual sale flow opens with that product pre-selected
- **AND** quantity, payment method, price policy and stock validation behave exactly as in manual entry
- **AND** the created sale carries the search event it originated from

#### Scenario: Create manual sale without photo

- **WHEN** authenticated operator searches and selects product by SKU or name
- **AND** enters quantity (>= 1)
- **AND** selects payment method assigned to point of sale
- **AND** product has sufficient stock at point of sale
- **THEN** system creates Sale record using effective sale price rules
- **AND** SalePhoto is null (no photo attached)
- **AND** creates InventoryMovement and updates stock atomically
- **AND** returns success with sale ID

#### Scenario: Create manual sale with optional photo

- **WHEN** authenticated operator manually selects product
- **AND** optionally attaches photo (e.g., for documentation purposes)
- **AND** enters quantity and selects payment method
- **AND** product has sufficient stock
- **THEN** system creates Sale using effective sale price rules
- **AND** creates SalePhoto with compressed photo
- **AND** creates InventoryMovement and updates stock atomically

#### Scenario: Sales landing page with three entry methods

- **WHEN** authenticated operator navigates to the sales landing page
- **THEN** three entry options are displayed: "Escanear código" (barcode/QR), "Registro manual" and assisted search
- **AND** "Escanear código" is displayed as the first/primary option
- **AND** "Reconocimiento de imagen" is no longer shown

#### Scenario: Switch from scanning to manual entry

- **WHEN** operator is in the barcode scanning view
- **AND** the camera is unable to decode a readable code after multiple attempts
- **THEN** a "Entrada manual" button is visible
- **AND** clicking it navigates to the manual product search

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

#### Scenario: Reject manual price when POS disallows overrides

- **WHEN** operator submits a sale request with explicit price
- **AND** selected point of sale has AllowManualPriceEdit = false
- **THEN** system returns 400 Bad Request with validation error
- **AND** does not create sale record

#### Scenario: Validate manual price is positive when provided

- **WHEN** operator submits a sale request with manual price <= 0
- **THEN** system returns 400 Bad Request with validation error
- **AND** does not create sale record

#### Scenario: Low stock warning after sale

- **WHEN** sale is created successfully
- **AND** remaining stock after sale <= Inventory.MinimumThreshold (if configured)
- **THEN** system returns success response with lowStockWarning flag = true
- **AND** includes remaining stock quantity in response
- **AND** frontend displays non-blocking toast: "⚠️ Quedan solo X unidades de este producto"
- **NOTE**: Warning does not block sale, only informs operator

#### Scenario: Validate quantity is positive

- **WHEN** operator attempts to create sale with quantity <= 0
- **THEN** system returns 400 Bad Request with validation error
- **AND** does not create sale record

#### Scenario: Price snapshot on sale creation

- **WHEN** sale is created
- **THEN** system captures current Product.Price at time of sale as official price reference
- **AND** stores effective price in Sale.Price
- **AND** stores PriceWasOverridden = true and OriginalProductPrice = official Product.Price when override is applied
- **AND** stores PriceWasOverridden = false and OriginalProductPrice = null when override is not applied
- **AND** subsequent product price changes do not affect historical sale pricing fields

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

### Requirement: A sale may declare the assisted search it originated from

The sale creation API SHALL accept an optional reference to the search event a sale originated from, on the single-sale request and on each line of the bulk request, and MUST persist it on the created sale.

The reference MUST be per line rather than per operation, because each line of a bulk checkout may come from a different search — or from no search at all.

The reference MUST be optional. A sale started by scanning, by SKU search or by any other entry method MUST be created with no attribution and MUST remain valid.

Before persisting the reference the system MUST verify that the referenced search event exists **and belongs to the user creating the sale**. Ownership is checked for the same reason the selection endpoint checks it, with no administrator exception: a search event records what one specific person did, and letting a caller attribute their sale to somebody else's search would corrupt the adoption metrics without leaving a trace.

A reference that is unknown, or that belongs to another user, MUST degrade the attribution to none. It MUST NOT produce a validation error, MUST NOT fail the sale, and MUST NOT alter the price, the stock movement or any other part of the sale. Attribution is analytics; refusing a sale over it would turn a measurement into a till outage.

The verification MUST be performed explicitly rather than delegated to the database relationship: the declared delete behaviour governs deletion of the event, whereas an insert carrying an unknown identifier would abort the transaction of the sale instead of degrading.

This requirement introduces no schema change: the column, its index and its foreign key already exist.

#### Scenario: A sale is attributed to its originating search
- **WHEN** a sale is created with a reference to a search event that exists and belongs to the caller
- **THEN** the created sale carries that reference

#### Scenario: Each bulk line carries its own attribution
- **WHEN** a bulk checkout is submitted with a different search event reference on two of its lines and none on a third
- **THEN** each created sale carries the reference of its own line
- **AND** the third is created with no attribution

#### Scenario: An unknown reference degrades to no attribution
- **WHEN** a sale is created with a reference to a search event that does not exist
- **THEN** the sale is created successfully
- **AND** it carries no attribution
- **AND** no validation error is returned

#### Scenario: A reference to another user's search degrades to no attribution
- **WHEN** a sale is created with a reference to a search event belonging to a different user
- **THEN** the sale is created successfully
- **AND** it carries no attribution

#### Scenario: Attribution never changes the rest of the sale
- **WHEN** a sale is created with an unusable search event reference
- **THEN** the price, the inventory movement and the stock update are exactly what they would have been with no reference at all

#### Scenario: A sale with no originating search stays valid
- **WHEN** a sale is created with no search event reference
- **THEN** the sale is created with no attribution
