# sales-reports Specification

## Purpose
Paginated sales reporting with extended filters and global aggregates computed over the whole filtered set, scoped by role (administrators see every point of sale, operators only their assigned ones), plus a multi-sheet Excel export bounded by a row limit.
## Requirements
### Requirement: Sales Report API with Extended Filters and Global Aggregates

The system SHALL provide a REST API endpoint at `GET /api/reports/sales` that returns paginated sales data with extended filtering and global aggregate totals computed over the entire filtered result set (not just the current page). Only authenticated users can access this endpoint; administrators see all POS, operators see only assigned POS.

#### Scenario: Administrator retrieves sales report with default filters

- **WHEN** an authenticated administrator requests `GET /api/reports/sales` without filters
- **THEN** the system returns paginated sales for the last 30 days across all points of sale
- **AND** the response includes `items` (list of `SalesReportItem`), `totalCount`, `page`, `pageSize`, `totalPages`
- **AND** the response includes global aggregates: `totalSalesCount`, `totalQuantity`, `totalAmount` computed over the entire filtered dataset

#### Scenario: Filter sales report by text search

- **WHEN** an authenticated user requests `GET /api/reports/sales?search=anillo`
- **THEN** the system returns sales where `Product.SKU` or `Product.Name` contains "anillo" (case-insensitive)
- **AND** global aggregates reflect only the matching sales

#### Scenario: Filter sales report by amount range

- **WHEN** an authenticated user requests `GET /api/reports/sales?amountMin=100&amountMax=500`
- **THEN** the system returns sales where `Price * Quantity` is between 100 and 500 inclusive
- **AND** global aggregates reflect only the matching sales

#### Scenario: Filter sales report by has-photo flag

- **WHEN** an authenticated user requests `GET /api/reports/sales?hasPhoto=true`
- **THEN** the system returns only sales that have an associated `SalePhoto` record
- **AND** global aggregates reflect only sales with photos

#### Scenario: Filter sales report by price-was-overridden flag

- **WHEN** an authenticated user requests `GET /api/reports/sales?priceWasOverridden=true`
- **THEN** the system returns only sales where `PriceWasOverridden = true`
- **AND** global aggregates reflect only overridden-price sales

#### Scenario: Operator sees only assigned POS in report

- **WHEN** an authenticated operator requests `GET /api/reports/sales`
- **THEN** the system restricts results to sales from points of sale assigned to the operator via `UserPointOfSale`
- **AND** global aggregates are scoped to the operator's assigned POS only

#### Scenario: Combine multiple filters

- **WHEN** an authenticated user applies date range, POS, product, payment method, search, amount range, has-photo, and price-was-overridden filters simultaneously
- **THEN** the system returns sales matching ALL applied filters (AND logic)
- **AND** global aggregates reflect the combined filter result

#### Scenario: Empty result set

- **WHEN** the applied filters match zero sales
- **THEN** the system returns an empty items list
- **AND** `totalSalesCount = 0`, `totalQuantity = 0`, `totalAmount = 0`

#### Scenario: Unauthenticated access denied

- **WHEN** an unauthenticated user requests `GET /api/reports/sales`
- **THEN** the system returns 401 Unauthorized

### Requirement: Sales Report Item Data Shape

The system SHALL return each sale in the report with product details, collection, price override audit fields, and photo indicator so the frontend can display a comprehensive preview table.

#### Scenario: Report item includes all required fields

- **WHEN** a sales report is retrieved
- **THEN** each item SHALL include: `id`, `saleDate`, `productName`, `productSku`, `collectionName` (nullable), `pointOfSaleName`, `quantity`, `price`, `total` (price * quantity), `originalProductPrice` (nullable, present when `priceWasOverridden`), `priceWasOverridden`, `paymentMethodName`, `operatorName`, `notes` (nullable), `hasPhoto` (boolean)

### Requirement: Sales Report Excel Export with Row Limit

The system SHALL provide a REST API endpoint at `GET /api/reports/sales/export` that generates an Excel file (.xlsx) with the same filters as the report API. The export is limited to 10,000 rows; when exceeded, the system returns a 409 Conflict with the real total count.

#### Scenario: Successful export within row limit

- **WHEN** an authenticated user requests `GET /api/reports/sales/export` with filters matching <= 10,000 sales
- **THEN** the system returns an Excel file with content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **AND** the filename follows the pattern `reporte-ventas-{yyyy-MM-dd-HH-mm}.xlsx`

#### Scenario: Export exceeds 10,000-row limit

- **WHEN** an authenticated user requests `GET /api/reports/sales/export` with filters matching more than 10,000 sales
- **THEN** the system returns HTTP 409 Conflict
- **AND** the response body includes `{ "message": "Hay más de 10.000 ventas. Ajuste los filtros para exportar.", "totalCount": <real count> }`
- **AND** `totalCount` is the actual number of matching sales (e.g., 25000), not 10001

#### Scenario: Unauthenticated export access denied

- **WHEN** an unauthenticated user requests `GET /api/reports/sales/export`
- **THEN** the system returns 401 Unauthorized

### Requirement: Excel Detail Sheet Format

The system SHALL generate the first Excel sheet named "Ventas" with one row per sale and specific column ordering, without a totals row.

#### Scenario: Detail sheet column order and content

- **WHEN** the Excel file is generated
- **THEN** sheet "Ventas" SHALL contain columns in order: Fecha, Hora, SKU, Producto, Colección, Punto de venta, Cantidad, Precio, Total, Precio original, Método de pago, Operador, Notas, Con foto
- **AND** "Con foto" displays "Sí" or "No"
- **AND** "Precio original" is populated only when the sale price was overridden
- **AND** headers are formatted in bold
- **AND** numeric columns use appropriate number formatting (currency for monetary values)
- **AND** columns are auto-fitted to content width

#### Scenario: Detail sheet has no totals row

- **WHEN** the Excel file is generated
- **THEN** sheet "Ventas" SHALL NOT include a summary or totals row at the bottom

### Requirement: Excel POS Summary Sheet

The system SHALL generate a second Excel sheet named "Resumen por punto de venta" with aggregated data per POS and a total-general row.

#### Scenario: POS summary sheet content

- **WHEN** the Excel file is generated
- **THEN** sheet "Resumen por punto de venta" SHALL contain columns: Punto de venta, Nº ventas, Cantidad total, Importe total
- **AND** one row per point of sale that has at least one sale in the exported data
- **AND** monetary values use currency number format

#### Scenario: Total general row

- **WHEN** the POS summary sheet is generated
- **THEN** the last row SHALL display "TOTAL GENERAL" in the POS column
- **AND** the remaining columns SHALL contain the sum of all POS rows (total sales count, total quantity, total amount)
- **AND** the total general row is visually distinct (bold)

### Requirement: Sales Report Frontend Page

The system SHALL provide a frontend page at `/reports/sales` accessible from the Reports hub with filters, global totals display, paginated preview table, and Excel export functionality.

#### Scenario: Reports hub includes sales report card

- **WHEN** an administrator navigates to the Reports hub (`/reports`)
- **THEN** a card for "Reporte de Ventas" is displayed with a brief description and link to `/reports/sales`

#### Scenario: Default date range on page load

- **WHEN** an administrator navigates to `/reports/sales`
- **THEN** the date range filters default to the last 30 days
- **AND** an initial report query is executed with these defaults

#### Scenario: Filter panel with all filter options

- **WHEN** the sales report page is displayed
- **THEN** the filter panel includes: date range (start/end), point of sale (select), product (select/search), user (select), payment method (select), text search (input), amount min/max (numeric inputs), "Solo con foto" (checkbox/toggle), "Solo con precio modificado" (checkbox/toggle)
- **AND** all filters are optional

#### Scenario: Global totals bar displays aggregate values

- **WHEN** a report query returns results
- **THEN** the page displays "Total (según filtros): X ventas, Y unidades, Z €" using `totalSalesCount`, `totalQuantity`, `totalAmount` from the API response
- **AND** these values do not change when navigating between pages

#### Scenario: Global totals bar with zero results

- **WHEN** a report query returns zero results
- **THEN** the page displays "Total (según filtros): 0 ventas, 0 unidades, 0 €"

#### Scenario: Preview table with pagination

- **WHEN** report results are displayed
- **THEN** a table shows columns: Fecha, Hora, SKU, Producto, Colección, POS, Cantidad, Precio, Total, Método de pago, Operador, Con foto
- **AND** pagination controls allow navigating between pages

#### Scenario: Export button triggers download

- **WHEN** the user clicks "Exportar Excel"
- **AND** the current filters match <= 10,000 sales
- **THEN** the browser downloads the generated Excel file

#### Scenario: Export button shows warning on 409

- **WHEN** the user clicks "Exportar Excel"
- **AND** the API returns 409 with `totalCount`
- **THEN** a warning toast is displayed: "Hay N ventas. Ajuste los filtros." (where N is the real `totalCount`)

#### Scenario: Export limit notice displayed

- **WHEN** the sales report page is displayed
- **THEN** a notice near the export button reads: "Máximo 10.000 filas. Si hay más resultados, ajuste los filtros."

#### Scenario: Operator cannot access reports section

- **WHEN** an operator is logged in
- **THEN** the "Reportes" menu entry is not visible in the sidebar
- **AND** the operator cannot navigate to `/reports/sales`
