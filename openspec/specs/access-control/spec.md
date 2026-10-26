# access-control Specification

## Purpose

Enforce role-based access (Admin vs Operator) on APIs and UI, including operator scoping to assigned points of sale.

## Requirements
### Requirement: Role-Based Access Control

The system SHALL enforce access control based on user roles (Admin, Operator).

#### Scenario: Administrator full access

- **WHEN** authenticated user has Admin role
- **THEN** user can access all system functionality
- **AND** user can view all points of sale
- **AND** user can manage users
- **AND** user can manage configuration
- **AND** user does not require point of sale assignments

#### Scenario: Operator restricted access

- **WHEN** authenticated user has Operator role
- **THEN** user can only access operations for assigned points of sale
- **AND** user cannot access user management
- **AND** user cannot access system configuration
- **AND** user cannot access points of sale management

#### Scenario: Access denied for unauthorized role

- **WHEN** operator attempts to access admin-only functionality
- **THEN** system returns 403 Forbidden
- **AND** frontend hides unauthorized navigation items

### Requirement: Point of Sale Assignment

The system SHALL allow administrators to assign operators to specific points of sale.

#### Scenario: Assign operator to point of sale

- **WHEN** admin assigns operator to active point of sale
- **THEN** system creates UserPointOfSale record with IsActive=true
- **AND** sets AssignedAt timestamp
- **AND** operator gains access to that point of sale

#### Scenario: Assign operator to multiple points of sale

- **WHEN** admin assigns operator to multiple points of sale
- **THEN** system creates multiple UserPointOfSale records
- **AND** operator can access all assigned points of sale

#### Scenario: Attempt to assign admin to point of sale

- **WHEN** admin attempts to assign another admin to point of sale
- **THEN** system returns 400 Bad Request
- **AND** provides message "Los administradores tienen acceso a todos los puntos de venta y no requieren asignación"

#### Scenario: Assign to inactive point of sale

- **WHEN** admin attempts to assign operator to inactive point of sale
- **THEN** system returns 400 Bad Request
- **AND** provides message "No se puede asignar a un punto de venta inactivo"

#### Scenario: Duplicate assignment

- **WHEN** admin attempts to assign operator to already-assigned point of sale
- **THEN** if assignment is inactive, system reactivates it
- **AND** if assignment is active, system returns 409 Conflict

### Requirement: Point of Sale Unassignment

The system SHALL allow administrators to remove operator access to points of sale.

#### Scenario: Unassign operator from point of sale

- **WHEN** admin unassigns operator from point of sale
- **THEN** system sets UserPointOfSale.IsActive to false
- **AND** sets UnassignedAt timestamp
- **AND** preserves historical record
- **AND** operator loses access to that point of sale

#### Scenario: Unassign last active assignment

- **WHEN** admin attempts to unassign operator's only active assignment
- **THEN** system returns 400 Bad Request
- **AND** provides message "Un operador debe tener al menos un punto de venta asignado"

#### Scenario: Unassign already inactive assignment

- **WHEN** admin attempts to unassign already inactive assignment
- **THEN** system returns 400 Bad Request
- **AND** provides message "El operador ya está desasignado de este punto de venta"

### Requirement: Point of Sale Access Validation

The system SHALL validate operator access before allowing point-of-sale-specific operations.

#### Scenario: Operator accesses assigned point of sale

- **WHEN** operator performs operation on assigned point of sale
- **THEN** system validates user has active assignment
- **AND** allows operation to proceed

#### Scenario: Operator accesses unassigned point of sale

- **WHEN** operator attempts operation on unassigned point of sale
- **THEN** system returns 403 Forbidden
- **AND** provides message "No tiene acceso a este punto de venta"

#### Scenario: Operator bypasses frontend via API

- **WHEN** operator directly calls API with unassigned point of sale ID
- **THEN** backend validates assignment
- **AND** returns 403 Forbidden

#### Scenario: Admin accesses any point of sale

- **WHEN** admin performs operation on any point of sale
- **THEN** system allows operation without assignment check

### Requirement: Data Filtering by Assignment

The system SHALL automatically filter data for operators based on their assignments.

#### Scenario: Operator views inventory

- **WHEN** operator requests inventory list
- **THEN** system returns only inventory from assigned points of sale

#### Scenario: Operator views sales history

- **WHEN** operator requests sales history
- **THEN** system returns only sales from assigned points of sale

#### Scenario: Operator selects point of sale

- **WHEN** operator views point of sale dropdown
- **THEN** only assigned points of sale are shown

#### Scenario: Admin views all data

- **WHEN** admin requests any data list
- **THEN** system returns data from all points of sale
- **AND** admin can filter by any point of sale

### Requirement: Product Catalog Filtering by Inventory Assignment

The system SHALL filter product catalog and search results based on user role and inventory assignments.

#### Scenario: Admin views all products

- **WHEN** authenticated admin requests product catalog or searches products
- **THEN** system returns all products from the global Product table
- **AND** includes products with or without Inventory records

#### Scenario: Operator views only assigned products

- **WHEN** authenticated operator requests product catalog or searches products
- **THEN** system returns ONLY products that have Inventory records at operator's assigned points of sale
- **AND** includes products with Quantity = 0 if Inventory record exists
- **AND** excludes products with no Inventory records at assigned points of sale

#### Scenario: Operator has multiple POS assignments

- **WHEN** operator is assigned to multiple points of sale
- **AND** requests product catalog
- **THEN** system returns products that have Inventory records at ANY of the assigned points of sale
- **AND** aggregates results without duplicates

#### Scenario: Product exists globally but not in operator's inventory

- **WHEN** operator searches for or accesses a product that exists in Product table
- **BUT** has no Inventory record at operator's assigned points of sale
- **THEN** system returns 404 Not Found or excludes from search results
- **AND** operator cannot view product details

#### Scenario: Operator attempts direct access to unassigned product

- **WHEN** operator directly accesses product detail URL for unassigned product
- **THEN** backend validates inventory assignment
- **AND** returns 403 Forbidden with message "No tiene acceso a este producto"

#### Scenario: Product with zero quantity visible to operator

- **WHEN** operator views catalog or searches products
- **AND** product has Inventory.Quantity = 0 at assigned POS
- **THEN** product is included in results with quantity indicator
- **AND** displays warning message about zero inventory when selected

### Requirement: Assignment History

The system SHALL maintain history of operator assignments.

#### Scenario: View assignment history

- **WHEN** admin views operator's assignments
- **THEN** system shows both active and historical assignments
- **AND** includes AssignedAt timestamps
- **AND** includes UnassignedAt timestamps for inactive assignments

#### Scenario: Re-assign after unassignment

- **WHEN** admin re-assigns operator to previously unassigned point of sale
- **THEN** system reactivates existing record or creates new record
- **AND** sets new AssignedAt timestamp
- **AND** clears UnassignedAt

### Requirement: Authentication State Handling

The system SHALL properly handle authentication state transitions.

#### Scenario: Unauthenticated access to protected resource

- **WHEN** unauthenticated user accesses protected endpoint
- **THEN** system returns 401 Unauthorized
- **AND** frontend redirects to login page

#### Scenario: Token expiration during session

- **WHEN** access token expires during active session
- **THEN** frontend automatically attempts token refresh
- **AND** if refresh succeeds, request is retried
- **AND** if refresh fails, user is redirected to login

#### Scenario: Session expiration message

- **WHEN** both access and refresh tokens expire
- **THEN** system returns 401 Unauthorized
- **AND** frontend shows message "Su sesión ha expirado. Por favor, inicie sesión nuevamente"

### Requirement: Frontend Access Control

The system SHALL implement access control in the frontend for user experience.

#### Scenario: Hide admin menu for operators

- **WHEN** operator is logged in
- **THEN** frontend hides user management navigation
- **AND** hides points of sale management navigation
- **AND** hides payment methods management navigation

#### Scenario: Show all menus for admin

- **WHEN** admin is logged in
- **THEN** frontend shows all navigation items
- **AND** all functionality is accessible

#### Scenario: Redirect on direct URL access

- **WHEN** operator directly navigates to admin-only URL
- **THEN** frontend redirects to authorized page
- **AND** shows access denied notification

