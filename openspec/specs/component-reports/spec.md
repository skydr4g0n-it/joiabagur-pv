# component-reports Specification

## Purpose

Provide administrator margin reports and Excel export derived from product component assignments and aggregated totals.

## Requirements
### Requirement: Product Margin Report
The system SHALL provide a paginated report showing profit margins for products that have component assignments, with filtering, aggregated totals, and Excel export. Only administrators can access this report.

#### Scenario: Display margin report
- **WHEN** an authenticated administrator accesses the margin report
- **THEN** a paginated table is displayed with columns: Product (SKU, Name), TotalCostPrice (EUR), TotalSalePrice (EUR), Margin (EUR), Margin (%)
- **AND** totals are aggregated at the bottom of the table
- **AND** only products with at least one component assignment are included
- **AND** maximum 50 items per page

#### Scenario: Margin calculation
- **WHEN** a product has TotalCostPrice = 400 and TotalSalePrice = 600
- **THEN** Margin (EUR) = 200
- **AND** Margin (%) = (600 - 400) / 600 * 100 = 33.33%

#### Scenario: Filter by collection
- **WHEN** an administrator filters the margin report by collection "Verano 2024"
- **THEN** only products in that collection are shown
- **AND** aggregated totals reflect the filtered results

#### Scenario: Filter by margin threshold
- **WHEN** an administrator filters by "Margin < 20%"
- **THEN** only products with margin percentage below 20 are shown

#### Scenario: Search by product
- **WHEN** an administrator searches by product name or SKU
- **THEN** results are filtered to matching products

#### Scenario: Export to Excel
- **WHEN** an administrator clicks "Export to Excel"
- **THEN** an Excel file is downloaded containing the report data with current filters applied
- **AND** includes all columns from the report

#### Scenario: Unauthorized access
- **WHEN** an operator or unauthenticated user attempts to access the margin report
- **THEN** access is denied with 403 Forbidden

### Requirement: Product Margin Report API
The system SHALL provide REST API endpoints for retrieving margin report data with filters and pagination, restricted to administrators.

#### Scenario: Get margin report
- **WHEN** an authenticated administrator requests GET /api/reports/product-margins
- **AND** optionally provides filters: collectionId, maxMarginPercent, search, page, pageSize
- **THEN** the system returns paginated results with product margin data
- **AND** includes aggregated totals (sumCostPrice, sumSalePrice, sumMargin)

#### Scenario: Export margin report
- **WHEN** an authenticated administrator requests GET /api/reports/product-margins/export with same filters
- **THEN** the system returns an Excel file with the report data

### Requirement: Products Without Components Report
The system SHALL provide a paginated report listing products that have no component assignments, with navigation to the product edit page. Only administrators can access this report.

#### Scenario: Display products without components
- **WHEN** an authenticated administrator accesses the products-without-components report
- **THEN** a paginated table is displayed with columns: SKU, Name, Price (EUR), Collection
- **AND** only products with zero component assignments are included
- **AND** each row has an "Edit" button linking to the product edit page

#### Scenario: Navigate to product edit
- **WHEN** an administrator clicks "Edit" on a product row
- **THEN** the system navigates to the product edit page for that product

#### Scenario: Empty report
- **WHEN** all products have at least one component assignment
- **THEN** the report shows a message "No hay productos sin componentes"

#### Scenario: Pagination
- **WHEN** more than 50 products have no components
- **THEN** results are paginated with maximum 50 items per page

#### Scenario: Filter by collection or search
- **WHEN** an administrator applies collection or search filters
- **THEN** results are filtered accordingly

#### Scenario: Unauthorized access
- **WHEN** an operator or unauthenticated user attempts to access this report
- **THEN** access is denied with 403 Forbidden

### Requirement: Products Without Components Report API
The system SHALL provide a REST API endpoint for retrieving products without component assignments, restricted to administrators.

#### Scenario: Get products without components
- **WHEN** an authenticated administrator requests GET /api/reports/products-without-components
- **AND** optionally provides filters: collectionId, search, page, pageSize
- **THEN** the system returns paginated results of products with no component assignments

