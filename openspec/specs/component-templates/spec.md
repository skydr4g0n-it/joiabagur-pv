# component-templates Specification

## Purpose

Define reusable component quantity templates so administrators can apply standard recipes to products faster and consistently.

## Requirements
### Requirement: Component Template Management
The system SHALL provide CRUD operations for component templates that define reusable lists of components with quantities (without prices). Only administrators can manage templates.

#### Scenario: Create template
- **WHEN** an authenticated administrator creates a template with Name "Anillo oro" and components: Oro (qty 3), Hora trabajo (qty 1), Soldadura (qty 0.5)
- **THEN** the template is saved with all component-quantity pairs
- **AND** each component appears only once in the template

#### Scenario: Edit template
- **WHEN** an authenticated administrator modifies a template's name, description, or component list
- **THEN** the template is updated
- **AND** existing product assignments created from this template are not affected

#### Scenario: Delete template
- **WHEN** an authenticated administrator deletes a template
- **THEN** the template and its items are removed
- **AND** existing product assignments created from this template are not affected

#### Scenario: Prevent duplicate component in template
- **WHEN** an administrator attempts to add the same component twice to a template
- **THEN** the system prevents the duplicate or updates the existing quantity

#### Scenario: Unauthorized access
- **WHEN** an operator or unauthenticated user attempts to access template management
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: Apply Template to Product
The system SHALL allow administrators to apply a component template to a product (in edit or create mode), merging template components with existing assignments using a non-overwrite strategy.

#### Scenario: Apply template to product without conflicts
- **WHEN** an administrator applies template "Anillo oro" (Oro qty 3, Trabajo qty 1) to a product with no existing components
- **THEN** all template components are added as assignments
- **AND** CostPrice and SalePrice are pre-filled from the master table for each component
- **AND** totals are recalculated

#### Scenario: Apply template with merge (no overwrite)
- **WHEN** a product already has component "Oro" assigned (qty 2, prices 140/190)
- **AND** template "Anillo oro" includes Oro (qty 3) and Plata (qty 1)
- **THEN** the existing Oro assignment is preserved (qty 2, prices 140/190)
- **AND** Plata is added with qty 1 and master prices pre-filled
- **AND** totals are recalculated

#### Scenario: Template component without master prices
- **WHEN** a template includes component "Diamante" and master has no prices for it
- **THEN** the assignment is added with the template quantity
- **AND** CostPrice and SalePrice fields are empty
- **AND** the administrator MUST fill prices before saving the product

#### Scenario: Apply template during product creation
- **WHEN** an administrator applies a template while creating a new product
- **THEN** template components are added to the assignment list before the product is saved
- **AND** all validation rules apply (prices required, etc.)

### Requirement: Component Template API
The system SHALL provide REST API endpoints for template CRUD and application, restricted to administrators.

#### Scenario: List templates
- **WHEN** an authenticated administrator requests GET /api/component-templates
- **THEN** the system returns a list of all templates with their names and descriptions

#### Scenario: Get template details
- **WHEN** an authenticated administrator requests GET /api/component-templates/{id}
- **THEN** the system returns the template with its component items (componentId, description, quantity)

#### Scenario: Create template via API
- **WHEN** an authenticated administrator POSTs to /api/component-templates with name and component items
- **THEN** the template is created and returned with its generated Id

#### Scenario: Update template via API
- **WHEN** an authenticated administrator PUTs to /api/component-templates/{id}
- **THEN** the template is updated (name, description, items)

#### Scenario: Delete template via API
- **WHEN** an authenticated administrator DELETEs /api/component-templates/{id}
- **THEN** the template and its items are removed

#### Scenario: Apply template via API
- **WHEN** an authenticated administrator POSTs to /api/products/{id}/components/apply-template with templateId
- **THEN** the system applies the merge logic and returns the updated assignment list with pre-filled master prices

### Requirement: Component Template Frontend
The system SHALL provide a UI for managing component templates, integrated as a subsection within the Products section, visible only to administrators.

#### Scenario: Display template list
- **WHEN** an authenticated administrator navigates to the template management page
- **THEN** a list of templates is displayed with Name and Description columns
- **AND** actions to edit and delete each template

#### Scenario: Create or edit template page
- **WHEN** an authenticated administrator creates or edits a template
- **THEN** a form is displayed with Name (required), Description (optional), and a component list
- **AND** components can be added via autocomplete and removed
- **AND** quantity can be set per component (4-decimal precision)

#### Scenario: Template selector in product pages
- **WHEN** an authenticated administrator is on a product edit or create page with the component section visible
- **THEN** an "Apply Template" dropdown or button is available in the component section
- **AND** selecting a template and confirming applies it with merge logic
- **AND** the UI indicates which components were added and which were skipped

