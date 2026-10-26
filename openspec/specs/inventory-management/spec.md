# inventory-management Specification

## Purpose

Manage per-POS product assignment, stock quantities, movements, imports, and adjustments while preserving audit history.

## Requirements
### Requirement: Product Assignment to Points of Sale

The system SHALL allow administrators to assign products from the global catalog to specific points of sale, creating Inventory records with initial quantity 0. The presence of an active Inventory record (IsActive = true) determines product visibility for operators assigned to that point of sale, regardless of quantity.

#### Scenario: Assign single product to point of sale

- **WHEN** administrator assigns a product to a point of sale
- **AND** product exists in global catalog
- **AND** product is not already assigned to that point of sale
- **THEN** system creates Inventory record with Quantity = 0 and IsActive = true
- **AND** product becomes visible to operators assigned to that point of sale
- **AND** system returns success message

#### Scenario: Bulk assignment of multiple products

- **WHEN** administrator selects multiple products
- **AND** assigns them to a point of sale
- **THEN** system creates Inventory records for all selected products
- **AND** all products become visible to operators
- **AND** system returns count of assigned products

#### Scenario: Prevent duplicate assignment

- **WHEN** administrator attempts to assign product already assigned to point of sale
- **THEN** system returns error message indicating product is already assigned
- **AND** no duplicate record is created

#### Scenario: Prevent assignment of inactive product

- **WHEN** administrator attempts to assign product with IsActive = false
- **THEN** system returns error message
- **AND** no Inventory record is created

#### Scenario: Reassign previously unassigned product

- **WHEN** product has Inventory record with IsActive = false
- **AND** administrator assigns it to the same point of sale
- **THEN** system reactivates existing record (IsActive = true)
- **AND** preserves previous quantity (maintains historical accuracy)
- **AND** product becomes visible to operators

### Requirement: Product Unassignment from Points of Sale

The system SHALL allow administrators to unassign products from points of sale using soft delete (IsActive = false), preserving historical data for audit purposes. Products can only be unassigned when quantity is 0.

#### Scenario: Unassign product with zero quantity

- **WHEN** administrator unassigns product with Quantity = 0
- **THEN** system sets IsActive = false on Inventory record
- **AND** product becomes invisible to operators
- **AND** historical record is preserved for audit
- **AND** system returns success message

#### Scenario: Prevent unassignment with stock

- **WHEN** administrator attempts to unassign product with Quantity > 0
- **THEN** system returns error: "No se puede desasignar un producto con stock. Ajuste la cantidad a 0 primero."
- **AND** product remains assigned (IsActive = true)

#### Scenario: View assigned products by point of sale

- **WHEN** administrator selects a point of sale
- **THEN** system returns list of products assigned to that point of sale
- **AND** displays current quantity for each product
- **AND** indicates products with Quantity = 0 visually

### Requirement: Stock Import from Excel

The system SHALL allow administrators to import stock adjustments from Excel for a UI-selected point of sale, with implicit assignment, signed quantities, and all-or-nothing validation that rejects the file when any row would make stock negative.

#### Scenario: Import stock for existing inventory (positive quantity)

- **GIVEN** a product already has an Inventory record for the selected point of sale
- **WHEN** administrator imports Excel with a row containing a positive Quantity for that product's SKU
- **THEN** system adds imported quantity to existing quantity
- **AND** creates InventoryMovement record with type "Import" and positive QuantityChange
- **AND** updates Inventory.Quantity and LastUpdatedAt

#### Scenario: Import stock with negative quantity (stock decrease)

- **GIVEN** a product has an Inventory record with Quantity = 10 at the selected point of sale
- **WHEN** administrator imports Excel with a row containing Quantity = -3 for that product's SKU
- **THEN** system subtracts 3 from existing quantity (resulting in 7)
- **AND** creates InventoryMovement record with type "Import" and QuantityChange = -3
- **AND** sets QuantityBefore = 10 and QuantityAfter = 7
- **AND** updates Inventory.LastUpdatedAt

#### Scenario: Reject import when negative quantity would cause negative stock

- **GIVEN** a product has an Inventory record with Quantity = 2 at the selected point of sale
- **WHEN** administrator imports Excel with a row containing Quantity = -5 for that product's SKU
- **THEN** system validates all rows before committing any changes
- **AND** returns error for that row: "Fila {row}: El stock resultante para '{SKU}' sería negativo (actual: 2, cambio: -5, resultado: -3)."
- **AND** no Inventory or InventoryMovement records are modified
- **AND** the entire import is rejected (no partial application)

#### Scenario: Reject import when multiple rows for different products cause negative stock

- **GIVEN** product A has Quantity = 5 and product B has Quantity = 1
- **WHEN** administrator imports Excel with Quantity = -3 for product A (valid) and Quantity = -4 for product B (invalid)
- **THEN** system returns an error for the product B row
- **AND** does not apply the product A change either (all-or-nothing)

#### Scenario: Implicit assignment via import (positive quantity only)

- **GIVEN** a product exists in the global catalog but is not assigned to the selected point of sale
- **WHEN** administrator imports Excel with a positive Quantity for that product's SKU
- **THEN** system creates Inventory record with the imported quantity
- **AND** sets IsActive = true (implicit assignment)
- **AND** creates InventoryMovement record with type "Import"
- **AND** product becomes visible to operators
- **AND** system indicates implicit assignment occurred

#### Scenario: Reject negative quantity for unassigned product

- **GIVEN** a product exists in the global catalog but has no Inventory record at the selected point of sale
- **WHEN** administrator imports Excel with a negative Quantity for that product's SKU
- **THEN** system returns error for that row indicating stock would be negative (current stock is 0)
- **AND** does not create an Inventory record

#### Scenario: Zero quantity row produces no stock change

- **GIVEN** a product has an Inventory record at the selected point of sale
- **WHEN** administrator imports Excel with Quantity = 0 for that product's SKU
- **THEN** system does not modify the Inventory quantity
- **AND** does not create an InventoryMovement record
- **AND** the row is silently skipped (no error, no warning)

#### Scenario: Handle invalid SKU in import

- **WHEN** Excel contains SKU not found in global catalog
- **THEN** system validates file before import
- **AND** returns error listing invalid SKUs with format: "Row X: SKU 'ABC-123' not found in catalog"
- **AND** groups all SKU errors together
- **AND** does not import invalid records
- **AND** suggests verifying product was imported in EP1

#### Scenario: Excel format validation

- **WHEN** administrator uploads Excel file
- **THEN** system validates required columns (SKU, Quantity) with exact column name matching
- **AND** validates Quantity is a valid integer (positive, negative, or zero)
- **AND** validates SKU exists in Product catalog
- **AND** validates all rows before processing any
- **AND** shows all validation errors with detailed format (row number, field name, error message)
- **AND** groups errors by type (missing columns, invalid data, business rule violations)
- **AND** shows preview of file contents before import confirmation
- **AND** processes valid rows only after user confirmation

#### Scenario: Download Excel template

- **WHEN** administrator requests stock import template
- **THEN** system provides downloadable Excel template file via GET /api/inventory/import-template endpoint
- **AND** template contains exact column headers: "SKU" and "Quantity" (header row protected/locked)
- **AND** template includes example rows with both positive and negative quantity samples
- **AND** template includes data validation rules (Quantity must be a whole number, SKU text format)
- **AND** template includes instructions explaining: positive values add stock, negative values subtract stock, final stock cannot be negative
- **AND** template has proper formatting (bold headers, number format for Quantity column)

#### Scenario: Template accessible from help documentation

- **WHEN** administrator accesses help or documentation pages
- **THEN** template download link is available
- **AND** link provides same template as import page

#### Scenario: Import confirmation with summary

- **WHEN** file validation passes and administrator clicks import
- **THEN** system shows confirmation dialog with summary
- **AND** displays total rows to process
- **AND** displays breakdown (e.g., "X products will have stock added, Y products will have stock subtracted, Z products will be assigned")
- **AND** requires explicit confirmation before processing

### Requirement: Stock Visualization by Point of Sale

The system SHALL allow administrators and operators to view stock for a specific point of sale, with operators restricted to their assigned points of sale only.

#### Scenario: Administrator views stock by point of sale

- **WHEN** administrator selects a point of sale
- **THEN** system returns list of products with current stock quantities
- **AND** displays SKU, product name, and quantity
- **AND** includes products with Quantity = 0

#### Scenario: Operator views stock for assigned point of sale

- **WHEN** operator requests stock view
- **THEN** system allows selection only from assigned points of sale
- **AND** returns products with Inventory records (IsActive = true) for selected point of sale
- **AND** displays SKU, product name, and quantity

#### Scenario: Operator cannot access unassigned point of sale

- **WHEN** operator attempts to view stock for point of sale not assigned to them
- **THEN** system returns 403 Forbidden
- **AND** point of sale does not appear in selection list

### Requirement: Centralized Stock View

The system SHALL allow administrators to view consolidated stock across all points of sale, showing total quantity per product and breakdown by location.

#### Scenario: View total stock per product

- **WHEN** administrator requests centralized stock view
- **THEN** system aggregates quantities across all points of sale per product
- **AND** displays total quantity for each product
- **AND** provides expandable breakdown by point of sale

#### Scenario: View stock breakdown by location

- **WHEN** administrator expands product in centralized view
- **THEN** system shows quantity per point of sale
- **AND** displays point of sale name and quantity

### Requirement: Manual Inventory Adjustment

The system SHALL allow administrators to manually adjust inventory quantities with reason tracking, generating audit trail entries. Adjustments can only be performed on products already assigned to the point of sale.

#### Scenario: Successful manual adjustment

- **WHEN** administrator adjusts inventory quantity
- **AND** product is assigned to point of sale (IsActive = true)
- **AND** provides adjustment amount and reason (max 500 characters)
- **THEN** system updates Inventory.Quantity
- **AND** creates InventoryMovement record with type "Adjustment"
- **AND** records reason, QuantityBefore, QuantityAfter, and QuantityChange
- **AND** updates Inventory.LastUpdatedAt

#### Scenario: Prevent negative stock

- **WHEN** administrator attempts adjustment that would result in negative quantity
- **THEN** system validates before applying adjustment
- **AND** returns error: "El stock no puede ser negativo"
- **AND** does not update Inventory or create movement record

#### Scenario: Adjustment requires assigned product

- **WHEN** administrator attempts adjustment for product not assigned to point of sale
- **THEN** system returns error: "El producto no está asignado a este punto de venta"
- **AND** suggests using assignment functionality first

#### Scenario: Reason is required for adjustment

- **WHEN** administrator attempts adjustment without reason
- **THEN** system validates reason field is provided
- **AND** returns validation error if reason is empty

### Requirement: Inventory Movement History

The system SHALL provide complete audit trail of all inventory movements with filtering capabilities, allowing administrators to track all changes to stock quantities. Movement history defaults to last 30 days if no date range is specified.

#### Scenario: View movement history with filters

- **WHEN** administrator requests movement history
- **AND** applies filters (product, point of sale, date range)
- **THEN** system returns paginated list of movements matching filters
- **AND** displays movement type, quantity change, quantity before/after, user, date, and reason
- **AND** orders results by MovementDate descending

#### Scenario: Default date range for movement history

- **WHEN** administrator requests movement history without specifying date range
- **THEN** system defaults to last 30 days from current date
- **AND** displays movements within that date range

#### Scenario: Filter by product

- **WHEN** administrator filters by specific product
- **THEN** system returns movements for that product across all points of sale
- **OR** filters by product and specific point of sale if both provided

#### Scenario: Filter by date range

- **WHEN** administrator provides date range filter
- **THEN** system returns movements within specified date range
- **AND** uses MovementDate for filtering

#### Scenario: Pagination for large result sets

- **WHEN** movement history query returns many results
- **THEN** system applies pagination (max 50 items per page)
- **AND** returns total count for pagination controls

### Requirement: Stock Validation

The system SHALL enforce non-negative stock validation at application level, preventing any operation that would result in negative inventory quantities.

#### Scenario: Validate stock before sale

- **WHEN** system processes sale that would reduce stock below zero
- **THEN** system validates available stock before completing sale
- **AND** returns error if insufficient stock
- **NOTE**: This requirement will be referenced by sales-management capability (EP3)

#### Scenario: Validate stock before adjustment

- **WHEN** administrator attempts adjustment
- **THEN** system calculates resulting quantity
- **AND** validates result >= 0 before applying change
- **AND** returns error if validation fails

### Requirement: Automatic Inventory Movement Creation on Sale

The system SHALL automatically create InventoryMovement records when sales are registered, updating stock quantities and maintaining full audit trail. This operation must occur within the same database transaction as the sale creation to ensure data consistency.

#### Scenario: Create movement on successful sale

- **WHEN** a sale is successfully registered via sales-management capability
- **AND** the sale reduces product stock by specified quantity
- **THEN** system creates InventoryMovement record with type "Sale"
- **AND** sets QuantityBefore to current stock
- **AND** sets QuantityChange to negative quantity sold (e.g., -2 for selling 2 units)
- **AND** sets QuantityAfter to new stock quantity
- **AND** links movement to Sale via SaleId
- **AND** records User who performed the sale
- **AND** sets MovementDate to sale timestamp
- **AND** updates Inventory.Quantity atomically in same transaction

#### Scenario: Rollback on transaction failure

- **WHEN** sale creation or inventory movement creation fails
- **THEN** system rolls back entire transaction
- **AND** ensures sale record is not created if inventory update fails
- **AND** ensures inventory is not updated if sale creation fails
- **AND** returns error to calling service

### Requirement: Stock Availability Validation Service

The system SHALL provide a shared service (IStockValidationService) for validating product stock availability before sales, ensuring products are assigned to the point of sale and have sufficient quantity.

#### Scenario: Validate sufficient stock and assignment

- **WHEN** sales-management capability validates stock before creating sale
- **AND** product has Inventory record at point of sale with IsActive = true
- **AND** current Quantity >= requested quantity
- **THEN** validation service returns success
- **AND** includes current available quantity in response

#### Scenario: Reject sale for unassigned product

- **WHEN** sales-management attempts to validate stock for product
- **AND** product has no Inventory record at point of sale
- **OR** Inventory record has IsActive = false
- **THEN** validation service returns error: "El producto no está asignado a este punto de venta"
- **AND** prevents sale from proceeding

#### Scenario: Reject sale for insufficient stock

- **WHEN** sales-management validates stock for product
- **AND** product is assigned (IsActive = true)
- **AND** current Quantity < requested quantity
- **THEN** validation service returns error: "Stock insuficiente. Disponible: X, Solicitado: Y"
- **AND** includes available quantity in error message
- **AND** prevents sale from proceeding

#### Scenario: Low stock warning after sale

- **WHEN** validation service is called with checkThreshold = true
- **AND** stock after sale would be <= MinimumThreshold (if configured)
- **THEN** validation returns success with lowStockWarning flag
- **AND** includes remaining stock quantity
- **NOTE**: Warning does not block sale, only informs

#### Scenario: Validate stock for multiple units

- **WHEN** sale includes quantity > 1
- **THEN** validation service checks current stock >= total quantity requested
- **AND** applies same validation rules as single unit sales

