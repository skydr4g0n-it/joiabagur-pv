# Spec Delta

## MODIFIED Requirements

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
