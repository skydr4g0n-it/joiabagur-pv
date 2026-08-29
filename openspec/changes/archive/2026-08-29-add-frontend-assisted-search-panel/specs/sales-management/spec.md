## ADDED Requirements

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

## MODIFIED Requirements

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
