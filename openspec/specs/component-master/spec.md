# component-master Specification

## Purpose

Maintain the administrator-managed master list of components (materials, labor, fees) with 4-decimal cost and sale prices.

## Requirements
### Requirement: Component Master Table Management
The system SHALL provide CRUD operations for a component master table that defines materials, labor, and other elements assignable to products. Only administrators can access this functionality.

#### Scenario: Create component with full data
- **WHEN** an authenticated administrator creates a component with Description "Oro 18k", CostPrice 150.0000, SalePrice 200.0000
- **THEN** the component is created with IsActive = true
- **AND** audit timestamps (CreatedAt, UpdatedAt) are set

#### Scenario: Create component without prices
- **WHEN** an authenticated administrator creates a component with only Description "Diamante"
- **AND** CostPrice and SalePrice are not provided
- **THEN** the component is created with null CostPrice and null SalePrice
- **AND** prices can be added later via edit

#### Scenario: Description validation
- **WHEN** an administrator attempts to create or edit a component
- **AND** the description is empty or exceeds 35 characters
- **THEN** the system rejects the request with a validation error

#### Scenario: Description uniqueness
- **WHEN** an administrator attempts to create a component with a description that already exists (case-insensitive)
- **THEN** the system rejects the request with error "La descripción ya existe"

#### Scenario: Price validation
- **WHEN** an administrator provides CostPrice or SalePrice < 0
- **THEN** the system rejects the request with a validation error

#### Scenario: Edit component
- **WHEN** an authenticated administrator updates a component's description, CostPrice, or SalePrice
- **THEN** the component is updated
- **AND** UpdatedAt timestamp is refreshed
- **AND** existing product assignments are NOT affected (override prices are independent)

#### Scenario: Deactivate component
- **WHEN** an authenticated administrator deactivates a component
- **THEN** IsActive is set to false
- **AND** the component no longer appears in autocomplete for new assignments
- **AND** existing product assignments are preserved

#### Scenario: Reactivate component
- **WHEN** an authenticated administrator reactivates a previously deactivated component
- **THEN** IsActive is set to true
- **AND** the component becomes available for new assignments

#### Scenario: Unauthorized access
- **WHEN** an operator or unauthenticated user attempts to access component management
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: Component Master Table API
The system SHALL provide REST API endpoints for component CRUD operations restricted to administrators.

#### Scenario: List components with filters
- **WHEN** an authenticated administrator requests GET /api/product-components
- **AND** optionally provides filters: isActive (boolean), search (string, min 2 chars)
- **THEN** the system returns a paginated list of components matching the filters
- **AND** includes pagination metadata (totalCount, totalPages, currentPage)
- **AND** maximum 50 items per page

#### Scenario: Create component via API
- **WHEN** an authenticated administrator POSTs to /api/product-components with valid data
- **THEN** the component is created and returned with its generated Id

#### Scenario: Update component via API
- **WHEN** an authenticated administrator PUTs to /api/product-components/{id} with valid data
- **THEN** the component is updated and the updated data is returned

#### Scenario: Get component by ID
- **WHEN** an authenticated administrator requests GET /api/product-components/{id}
- **THEN** the system returns the component details

#### Scenario: Component not found
- **WHEN** an authenticated administrator requests a non-existent component
- **THEN** the system returns 404 Not Found

### Requirement: Component Master Table Frontend
The system SHALL provide a UI for managing the component master table, integrated as a subsection within the Products section, visible only to administrators.

#### Scenario: Display component list
- **WHEN** an authenticated administrator navigates to the component management page
- **THEN** a paginated table of components is displayed
- **AND** columns include Description, CostPrice (EUR), SalePrice (EUR), Status (Active/Inactive)
- **AND** filter controls for active/inactive and search by description are available

#### Scenario: Create component via dialog
- **WHEN** an authenticated administrator clicks "Create Component"
- **THEN** a dialog opens with fields: Description (required, max 35 chars), CostPrice (optional, >= 0, 4 decimals), SalePrice (optional, >= 0, 4 decimals)
- **AND** validation errors are shown inline
- **AND** on success, the list is refreshed

#### Scenario: Edit component via dialog
- **WHEN** an authenticated administrator clicks "Edit" on a component
- **THEN** a dialog opens pre-populated with current values
- **AND** the administrator can modify description and prices
- **AND** on save, the list is refreshed

#### Scenario: Toggle component active status
- **WHEN** an authenticated administrator toggles the active/inactive status of a component
- **THEN** the component's IsActive state is updated
- **AND** a confirmation message is shown

#### Scenario: Operator cannot see component management
- **WHEN** an operator is authenticated
- **THEN** the component management subsection is not visible in the Products navigation
- **AND** direct URL access returns 403 or redirects

