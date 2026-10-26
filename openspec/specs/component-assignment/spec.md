# component-assignment Specification

## Purpose

Assign jewelry components to products with quantities and optional price overrides to drive cost, sale price, and margin calculations.

## Requirements
### Requirement: Component Assignment to Products
The system SHALL allow administrators to assign components to products with quantities and price overrides. Each assignment requires a quantity (> 0), CostPrice (>= 0), and SalePrice (>= 0), all with 4-decimal precision. Assignments are managed in the product edit and create pages.

#### Scenario: Add component with master prices pre-filled
- **WHEN** an administrator adds component "Oro 18k" (master CostPrice 150, SalePrice 200) to a product with quantity 3
- **THEN** the assignment is created with CostPrice 150.0000 and SalePrice 200.0000 pre-filled from master
- **AND** the administrator can modify the pre-filled prices

#### Scenario: Add component without master prices
- **WHEN** an administrator adds component "Diamante" (no master prices) to a product with quantity 2
- **THEN** the assignment is created with empty CostPrice and SalePrice fields
- **AND** the administrator MUST fill in both prices before saving

#### Scenario: Prevent duplicate component assignment
- **WHEN** an administrator attempts to add a component already assigned to the product
- **THEN** the system prevents the duplicate
- **AND** displays a message indicating the component is already assigned

#### Scenario: Override price independence
- **WHEN** an administrator changes prices in a product assignment
- **THEN** the master component prices are NOT affected
- **AND** when master prices change, existing product assignments are NOT automatically updated

#### Scenario: Remove component assignment
- **WHEN** an administrator removes a component assignment from a product
- **THEN** the assignment is deleted
- **AND** totals are recalculated

#### Scenario: Block save with incomplete prices
- **WHEN** an administrator attempts to save a product with component assignments that have empty or invalid prices
- **THEN** the save is blocked
- **AND** validation errors indicate which assignments need prices

#### Scenario: Deactivated component not available for new assignment
- **WHEN** an administrator searches for components to assign
- **THEN** only active components (IsActive = true) appear in autocomplete results
- **AND** already-deactivated components that are assigned to the product remain visible in the assignment list

### Requirement: Component Assignment Real-Time Totals
The system SHALL calculate and display TotalCostPrice and TotalSalePrice in real-time based on component assignments: TotalCostPrice = SUM(CostPrice * Quantity), TotalSalePrice = SUM(SalePrice * Quantity).

#### Scenario: Calculate totals with multiple components
- **WHEN** a product has components: Oro (qty 3, cost 150, sale 200) and Trabajo (qty 1, cost 50, sale 50)
- **THEN** TotalCostPrice = (3 * 150) + (1 * 50) = 500
- **AND** TotalSalePrice = (3 * 200) + (1 * 50) = 650
- **AND** totals update immediately when any value changes

#### Scenario: Totals with no components
- **WHEN** a product has no component assignments
- **THEN** totals are not displayed or shown as 0

### Requirement: Component Assignment Ordering
The system SHALL support drag-and-drop reordering of component assignments within a product. The order is persisted via a DisplayOrder field.

#### Scenario: Reorder components via drag-and-drop
- **WHEN** an administrator drags component B from position 2 to position 3
- **THEN** the display order is updated to reflect the new arrangement
- **AND** the new order is persisted when the product is saved

#### Scenario: DisplayOrder persistence
- **WHEN** an administrator saves a product with reordered components
- **THEN** the DisplayOrder values are stored in the database
- **AND** subsequent loads of the product display components in the saved order

### Requirement: Component Assignment API
The system SHALL provide REST API endpoints for managing component assignments on products, restricted to administrators.

#### Scenario: Get product components
- **WHEN** an authenticated administrator requests GET /api/products/{id}/components
- **THEN** the system returns the list of component assignments for the product
- **AND** each assignment includes ComponentId, Description, Quantity, CostPrice, SalePrice, DisplayOrder
- **AND** assignments are ordered by DisplayOrder

#### Scenario: Save product components
- **WHEN** an authenticated administrator PUTs to /api/products/{id}/components with an array of assignments
- **THEN** the system replaces all component assignments for the product with the provided list
- **AND** validates all assignments (no duplicates, prices required, quantity > 0)
- **AND** returns the updated list

#### Scenario: Component autocomplete search
- **WHEN** an authenticated administrator requests GET /api/product-components/search?query=Oro
- **AND** the query has at least 2 characters
- **THEN** the system returns active components matching the query by description (case-insensitive)
- **AND** results are limited to 20 items

#### Scenario: Create product with components
- **WHEN** an authenticated administrator creates a product and then saves component assignments
- **THEN** the product and its component assignments are persisted
- **AND** all assignment validations apply

#### Scenario: Unauthorized access to assignments
- **WHEN** an operator or unauthenticated user attempts to access component assignment endpoints
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: Component Assignment Frontend in Product Edit
The system SHALL display a component assignment section in the product edit page, visible only to administrators, with autocomplete search, price fields, real-time totals, and drag-and-drop reordering.

#### Scenario: Display component section for admin
- **WHEN** an authenticated administrator navigates to the product edit page
- **THEN** a "Components" section is displayed below the main product form
- **AND** shows the list of assigned components with Quantity, CostPrice (EUR), SalePrice (EUR) per row
- **AND** shows TotalCostPrice and TotalSalePrice

#### Scenario: Search and add component via autocomplete
- **WHEN** an administrator types at least 2 characters in the component search field
- **THEN** matching active components appear in a dropdown after 300ms debounce
- **AND** selecting a component adds it to the assignment list with master prices pre-filled

#### Scenario: Operator does not see component section
- **WHEN** an operator navigates to the product edit page
- **THEN** the component section is not rendered
- **AND** the product form functions as before without component features

#### Scenario: Price display format
- **WHEN** component prices and totals are displayed
- **THEN** all monetary values use Euro format (EUR) with appropriate decimal places

### Requirement: Component Assignment Frontend in Product Create
The system SHALL display the same component assignment section in the product creation page, visible only to administrators, allowing components to be assigned during product creation.

#### Scenario: Add components during product creation
- **WHEN** an authenticated administrator is on the product creation page
- **AND** adds components with quantities and prices
- **AND** saves the product
- **THEN** the product is created and component assignments are saved
- **AND** totals are calculated correctly

#### Scenario: Create product without components
- **WHEN** an authenticated administrator creates a product without adding any components
- **THEN** the product is created successfully
- **AND** components can be added later via the edit page

### Requirement: Price Sync from Master
The system SHALL allow administrators to apply current master table prices to all component assignments of a product, with a confirmation dialog showing before/after changes.

#### Scenario: Sync prices successfully
- **WHEN** an administrator clicks "Apply master prices" on a product with assigned components
- **AND** confirms in the dialog after reviewing before/after prices
- **THEN** all assignments where the master component has defined prices are updated with current master prices
- **AND** totals are recalculated in real-time

#### Scenario: Confirmation dialog with preview
- **WHEN** an administrator clicks "Apply master prices"
- **THEN** a dialog shows a table with: Component Description, Current CostPrice/SalePrice, New CostPrice/SalePrice (from master)
- **AND** the administrator can cancel or confirm

#### Scenario: Skip components without master prices
- **WHEN** a component in master has no CostPrice or SalePrice defined
- **THEN** that component's assignment prices are NOT modified during sync
- **AND** the dialog indicates these components will be skipped

#### Scenario: Button visibility
- **WHEN** a product has at least one component assignment and the user is an administrator
- **THEN** the "Apply master prices" button is visible
- **WHEN** a product has no component assignments
- **THEN** the button is not visible

### Requirement: Price Deviation Warning
The system SHALL display a warning when the product's official price (Product.Price) deviates more than 10% from the total suggested sale price calculated from components (TotalSalePrice). Includes a quick action to adjust the product price.

#### Scenario: Show warning when deviation exceeds 10%
- **WHEN** a product has TotalSalePrice = 100 and Product.Price = 120
- **THEN** the system displays a warning: "El precio oficial (EUR 120) difiere mas del 10% del precio sugerido por componentes (EUR 100)"
- **AND** a button "Ajustar a precio sugerido" is shown

#### Scenario: No warning when deviation is within 10%
- **WHEN** a product has TotalSalePrice = 100 and Product.Price = 108
- **THEN** no deviation warning is displayed

#### Scenario: Quick adjust action
- **WHEN** an administrator clicks "Ajustar a precio sugerido"
- **THEN** Product.Price field is updated to TotalSalePrice value in the form
- **AND** the warning disappears
- **AND** the change must be saved to persist

#### Scenario: No warning without components
- **WHEN** a product has no component assignments
- **THEN** no deviation warning is shown

#### Scenario: No warning when TotalSalePrice is zero
- **WHEN** TotalSalePrice = 0 (e.g., all components have SalePrice 0)
- **THEN** no deviation warning is shown (avoids division by zero)

