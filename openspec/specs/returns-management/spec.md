# returns-management Specification

## Purpose

Process customer returns against prior sales within policy rules, restore inventory, and record categorized refund transactions.
## Requirements
### Requirement: Return Registration with Sale Association

The system SHALL allow administrators and operators to register product returns by associating them with one or more original sales from the same point of sale within a 30-day window. Returns automatically increment stock and create inventory movement records. A jewelry sale with gift-card coverage SHALL NOT be accepted by this classic return flow. The gift card issuance sale SHALL NOT be accepted by this classic return flow.

#### Scenario: Create return associated with single sale

- **WHEN** authenticated user (admin or operator) selects product to return
- **AND** selects point of sale (operator: from assigned POS only)
- **AND** system displays eligible sales (same product, same POS, within 30 days, with available quantity)
- **AND** user selects one sale and enters quantity to return (<= available quantity)
- **AND** user selects return category (required)
- **AND** optionally enters reason text
- **AND** optionally attaches photo
- **THEN** system creates Return record with total quantity
- **AND** creates ReturnSale record linking return to sale with quantity and price snapshot
- **AND** creates InventoryMovement record with type "Return" (positive quantity change)
- **AND** updates Inventory.Quantity atomically (increment by returned quantity)
- **AND** returns success with return ID

#### Scenario: Create return associated with multiple sales

- **WHEN** user selects product to return with quantity > available in single sale
- **AND** system shows multiple eligible sales with available quantities
- **AND** user selects multiple sales and distributes return quantity across them
- **AND** total distributed quantity equals requested return quantity
- **AND** each sale's distributed quantity <= that sale's available quantity
- **THEN** system creates Return record with total quantity
- **AND** creates multiple ReturnSale records (one per selected sale)
- **AND** each ReturnSale stores quantity and price snapshot from respective Sale.Price
- **AND** creates single InventoryMovement with total quantity change
- **AND** returns success

#### Scenario: Partial return from multi-unit sale

- **WHEN** original sale has Quantity = 5
- **AND** user creates return with Quantity = 2
- **THEN** system creates Return with Quantity = 2
- **AND** ReturnSale records quantity = 2 from that sale
- **AND** sale still has 3 units available for future returns
- **AND** stock increments by 2

#### Scenario: Reject return exceeding available quantity

- **WHEN** user attempts to return quantity > total available across eligible sales
- **THEN** system returns 400 Bad Request
- **AND** displays error: "Cantidad a devolver excede las unidades disponibles. Disponible: X"
- **AND** does not create return record

#### Scenario: Reject return outside 30-day window

- **WHEN** user attempts to associate return with sale older than 30 days
- **THEN** sale does not appear in eligible sales list
- **AND** if all sales are outside window, system displays: "No hay ventas elegibles para devolución en los últimos 30 días"

#### Scenario: Reject return at different point of sale

- **WHEN** user attempts to create return at POS different from sale's POS
- **THEN** system returns 400 Bad Request
- **AND** displays error: "La devolución debe realizarse en el mismo punto de venta de la venta original"

#### Scenario: Reject return with already-returned quantity

- **WHEN** sale has Quantity = 3
- **AND** previous return already used 2 units from this sale
- **THEN** eligible sales shows available = 1 for this sale
- **AND** user cannot return more than 1 unit from this sale

#### Scenario: Reject classic return of a gift-card-linked sale

- **GIVEN** a product sale with gift-card coverage
- **WHEN** the user submits that sale to the classic return endpoint
- **THEN** the system returns 400 Bad Request
- **AND** does not create a return or change stock

#### Scenario: Reject classic return of a gift card issuance sale

- **GIVEN** a sale that is the issuance sale of a gift card
- **WHEN** the user submits that sale to the classic return endpoint
- **THEN** the system returns 400 Bad Request
- **AND** does not create a return or change stock

### Requirement: Return Category Classification

The system SHALL require a return category for every return, enabling analytics and pattern detection. Categories are predefined and mandatory, while free-text reason remains optional.

#### Scenario: Select mandatory return category

- **WHEN** user creates return
- **THEN** system requires selection of one category from: Defectuoso, TamañoIncorrecto, NoSatisfecho, Otro
- **AND** return cannot be submitted without category selection
- **AND** category is stored in Return.ReturnCategory

#### Scenario: Add optional reason text

- **WHEN** user creates return
- **AND** optionally enters reason text (max 500 characters)
- **THEN** reason is stored in Return.Reason
- **AND** reason appears in return history and details

#### Scenario: Create return without reason text

- **WHEN** user creates return without entering reason
- **THEN** Return.Reason is stored as null
- **AND** return is created successfully with category only

### Requirement: Eligible Sales Query

The system SHALL provide an endpoint to query sales eligible for return association, filtering by product, point of sale, and 30-day window, calculating remaining available quantities. Jewelry sales with gift-card coverage and gift card issuance sales SHALL be excluded.

#### Scenario: Query eligible sales for product

- **WHEN** user requests eligible sales for product at specific POS
- **THEN** system returns sales matching criteria:
  - Same ProductId
  - Same PointOfSaleId
  - SaleDate within last 30 days
  - Available quantity > 0 (Sale.Quantity - already returned quantity)
  - No gift-card coverage
  - Not a gift card issuance sale
- **AND** results include: saleId, saleDate, originalQuantity, availableForReturn, unitPrice, paymentMethod
- **AND** results ordered by SaleDate descending (most recent first)

#### Scenario: Calculate available quantity per sale

- **WHEN** sale has Quantity = 5
- **AND** previous returns have used 2 units from this sale (SUM of ReturnSale.Quantity)
- **THEN** availableForReturn = 3
- **AND** sale appears in eligible list with available = 3

#### Scenario: Exclude fully returned sales

- **WHEN** sale has Quantity = 2
- **AND** previous returns have used all 2 units
- **THEN** availableForReturn = 0
- **AND** sale does NOT appear in eligible sales list

#### Scenario: No eligible sales found

- **WHEN** product has no sales at POS within 30 days
- **OR** all sales are fully returned
- **THEN** system returns empty list
- **AND** frontend displays: "No hay ventas elegibles para devolución"

#### Scenario: Exclude a sale linked to a gift card

- **GIVEN** a sale within 30 days at the requested POS with available quantity
- **AND** that sale has gift-card coverage
- **WHEN** the user requests eligible sales for that product and POS
- **THEN** the sale is absent from the list

#### Scenario: Exclude a gift card issuance sale

- **GIVEN** a gift card issuance sale within 30 days at the requested POS
- **WHEN** the user requests eligible sales for the system gift-card product at that POS
- **THEN** that issuance sale is absent from the list

### Requirement: Transaction-Based Return Processing

The system SHALL ensure atomic consistency between return creation, sale association, and inventory updates using database transactions, preventing orphaned returns or stock mismatches.

#### Scenario: Atomic return and inventory update

- **WHEN** return is created
- **THEN** system begins database transaction
- **AND** creates Return record
- **AND** creates ReturnSale record(s) with price snapshots
- **AND** creates ReturnPhoto record if photo provided
- **AND** creates InventoryMovement with type "Return" and positive QuantityChange
- **AND** updates Inventory.Quantity += returned quantity
- **AND** commits transaction only if all operations succeed

#### Scenario: Rollback on failure

- **WHEN** any step in return creation fails
- **THEN** system rolls back entire transaction
- **AND** Return record is not persisted
- **AND** Inventory.Quantity remains unchanged
- **AND** returns error to user

#### Scenario: Concurrent return conflict

- **WHEN** two users attempt to return last available unit from same sale simultaneously
- **AND** User A's return commits first
- **THEN** User B's validation fails at transaction commit
- **AND** User B receives error: "La cantidad disponible cambió. Por favor, recargue las ventas elegibles."

### Requirement: Return Photo Support

The system SHALL allow optional photo attachment to returns for documentation purposes (e.g., photo of defective product), following the same compression and storage patterns as sale photos.

#### Scenario: Attach photo to return

- **WHEN** user creates return with photo
- **THEN** system compresses photo (JPEG 80%, max 1920x1920, <= 2MB)
- **AND** uploads to storage via IFileStorageService
- **AND** creates ReturnPhoto record with FilePath, FileName, FileSize, MimeType
- **AND** photo is accessible via pre-signed URL in return details

#### Scenario: Create return without photo

- **WHEN** user creates return without attaching photo
- **THEN** ReturnPhoto record is not created
- **AND** return is created successfully

#### Scenario: Photo upload failure rollback

- **WHEN** return creation succeeds but photo upload fails
- **THEN** system rolls back entire transaction
- **AND** return is not created
- **AND** returns error to user

### Requirement: Returns Authorization and Access Control

The system SHALL enforce role-based access control for return operations, with operators restricted to their assigned points of sale.

#### Scenario: Operator creates return at assigned POS

- **WHEN** authenticated operator attempts to create return
- **AND** point of sale is assigned to operator via UserPointOfSale
- **THEN** system allows return creation
- **AND** operator can only select from eligible sales at assigned POS

#### Scenario: Operator rejected at unassigned POS

- **WHEN** operator attempts to create return at POS not assigned to them
- **THEN** system returns 403 Forbidden
- **AND** POS does not appear in operator's POS selection

#### Scenario: Administrator creates return at any POS

- **WHEN** authenticated administrator creates return
- **THEN** system allows return at any point of sale
- **AND** admin can view and select from all points of sale

#### Scenario: Operator views only assigned POS returns

- **WHEN** operator requests return history
- **THEN** system filters results to returns from assigned points of sale only
- **AND** returns from unassigned POS are not visible

### Requirement: Return History and Queries

The system SHALL provide return history with filtering capabilities, applying role-based access control for visibility. All list responses MUST eager-load the associated `Sale` entity for each `ReturnSale` so that sale date and payment method are always available without requiring a separate detail request.

#### Scenario: View return history with filters

- **WHEN** authenticated user requests GET /api/returns
- **AND** applies optional filters (date range, product, point of sale, category)
- **THEN** system returns paginated list (max 50 per page)
- **AND** includes: returnId, returnDate, product (SKU, name), quantity, category, reason, user, pointOfSale, totalValue
- **AND** each entry's `associatedSales` array includes `saleDate` populated from the actual Sale entity (never a default/fallback date)
- **AND** applies role-based POS filtering

#### Scenario: Associated sale date is always present in list response

- **WHEN** authenticated user requests GET /api/returns (list endpoint)
- **THEN** every `associatedSales[].saleDate` is a valid ISO 8601 timestamp matching the original sale's `SaleDate`
- **AND** the date is NEVER `0001-01-01T00:00:00` (DateTime.MinValue) regardless of query scope

#### Scenario: Default date range

- **WHEN** user requests return history without date range
- **THEN** system defaults to last 30 days
- **AND** displays returns within that period

#### Scenario: View return details

- **WHEN** user requests GET /api/returns/{id}
- **THEN** system returns full return details
- **AND** includes associated sales with quantities and prices
- **AND** includes photo URL if exists
- **AND** includes inventory movement reference
- **AND** admin can view any return, operator can view only assigned POS returns

#### Scenario: Calculate total return value

- **WHEN** displaying return details or history
- **THEN** totalValue = SUM(ReturnSale.Quantity * ReturnSale.UnitPrice)
- **AND** value is displayed in Euro format (es-ES locale)

### Requirement: Inventory Movement Integration

The system SHALL create InventoryMovement records with type "Return" when returns are registered, maintaining complete audit trail and updating stock quantities.

#### Scenario: Create inventory movement on return

- **WHEN** return is successfully created
- **THEN** system creates InventoryMovement record:
  - MovementType = "Return"
  - QuantityChange = +returned quantity (positive, stock increases)
  - QuantityBefore = stock before return
  - QuantityAfter = stock after return
  - ReturnId = reference to created return
  - UserId = user who registered return
  - MovementDate = return date
- **AND** updates Inventory.Quantity atomically

#### Scenario: Movement appears in inventory history

- **WHEN** administrator views inventory movement history
- **THEN** return movements appear with type "Return"
- **AND** show positive quantity change
- **AND** link to return details is available

