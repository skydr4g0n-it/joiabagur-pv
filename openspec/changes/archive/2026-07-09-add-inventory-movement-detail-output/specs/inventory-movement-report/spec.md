## MODIFIED Requirements

### Requirement: Inventory Movement Summary API with Date and POS Filters

The system SHALL provide a REST API endpoint at `GET /api/reports/inventory-movements` that returns a paginated inventory movement report for the selected output model. The `outputModel` query parameter SHALL accept `summary` and `detail`, defaulting to `summary` when omitted. Summary mode SHALL return inventory movements aggregated by product. Each summary row SHALL contain the total additions (sum of positive `QuantityChange`), total subtractions (sum of absolute value of negative `QuantityChange`), and the difference (additions minus subtractions) for a product within the filtered date range. Detail mode SHALL return each matching inventory movement transaction separately. Only administrators SHALL access this endpoint.

#### Scenario: Administrator retrieves inventory movement summary with required date filters

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements?startDate=2025-01-01&endDate=2025-03-31`
- **THEN** the system returns a paginated response with `items`, `totalCount`, `page`, `pageSize`, `totalPages`
- **AND** the response uses summary mode
- **AND** each item contains `productId`, `productName`, `productSku`, `additions`, `subtractions`, `difference`
- **AND** `additions` equals the sum of all positive `QuantityChange` values for that product within the date range
- **AND** `subtractions` equals the sum of the absolute values of all negative `QuantityChange` values for that product within the date range
- **AND** `difference` equals `additions` minus `subtractions`

#### Scenario: Administrator retrieves inventory movement detail with required date filters

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements?startDate=2025-01-01&endDate=2025-03-31&outputModel=detail`
- **THEN** the system returns a paginated response with `items`, `totalCount`, `page`, `pageSize`, `totalPages`
- **AND** each item represents one inventory movement transaction
- **AND** each item contains `id`, `inventoryId`, `productId`, `productName`, `productSku`, `pointOfSaleId`, `pointOfSaleName`, `movementType`, `movementTypeName`, `quantityChange`, `quantityBefore`, `quantityAfter`, `userId`, `userName`, `reason`, `movementDate`, `saleId`, and `returnId`
- **AND** the items are ordered by `movementDate` descending by default

#### Scenario: Filter by point of sale

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements?startDate=2025-01-01&endDate=2025-03-31&pointOfSaleId=5`
- **THEN** the system returns only movements associated with inventories belonging to the specified point of sale
- **AND** summary mode aggregation is grouped by product across that POS only
- **AND** detail mode rows are individual transactions from that POS only

#### Scenario: No POS filter returns all POS combined

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements` without `pointOfSaleId`
- **THEN** the system includes movements across all points of sale
- **AND** summary mode aggregates matching movements across all points of sale per product

#### Scenario: Filter by product name or SKU

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements?startDate=2025-01-01&endDate=2025-03-31&productSearch=ring`
- **THEN** the system returns only movements whose product name or SKU matches the search text
- **AND** the filter applies before summary aggregation
- **AND** the same filter applies to detail rows

#### Scenario: Missing date filters returns 400

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements` without `startDate` or `endDate`
- **THEN** the system returns HTTP 400 Bad Request

#### Scenario: Invalid output model returns 400

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements?startDate=2025-01-01&endDate=2025-03-31&outputModel=unknown`
- **THEN** the system returns HTTP 400 Bad Request

#### Scenario: Empty result set

- **WHEN** the applied filters match zero inventory movements
- **THEN** the system returns an empty `items` list with `totalCount = 0`

#### Scenario: Non-administrator access denied

- **WHEN** an authenticated operator requests `GET /api/reports/inventory-movements`
- **THEN** the system returns HTTP 403 Forbidden

#### Scenario: Unauthenticated access denied

- **WHEN** an unauthenticated user requests `GET /api/reports/inventory-movements`
- **THEN** the system returns HTTP 401 Unauthorized

### Requirement: Inventory Movement Summary Excel Export with Row Limit

The system SHALL provide a REST API endpoint at `GET /api/reports/inventory-movements/export` that generates an Excel file (.xlsx) with the full result set for the selected output model using the same filters as the report API. The `outputModel` query parameter SHALL accept `summary` and `detail`, defaulting to `summary` when omitted. The export is limited to 50,000 rows.

#### Scenario: Successful summary export within row limit

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements/export` with filters matching <= 50,000 aggregated product rows
- **THEN** the system returns an Excel file with content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **AND** the filename follows the pattern `reporte-movimientos-inventario-{yyyy-MM-dd-HH-mm}.xlsx`

#### Scenario: Summary Excel sheet format

- **WHEN** the summary Excel file is generated
- **THEN** it SHALL contain a single sheet named "Resumen movimientos"
- **AND** columns in order: Producto, SKU, Adiciones, Sustracciones, Diferencia
- **AND** headers are formatted in bold
- **AND** numeric columns use appropriate number formatting
- **AND** columns are auto-fitted to content width

#### Scenario: Successful detail export within row limit

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements/export?outputModel=detail` with filters matching <= 50,000 transaction rows
- **THEN** the system returns an Excel file with content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **AND** the filename follows the pattern `reporte-movimientos-inventario-{yyyy-MM-dd-HH-mm}.xlsx`

#### Scenario: Detail Excel sheet format

- **WHEN** the detail Excel file is generated
- **THEN** it SHALL contain a single sheet named "Detalle movimientos"
- **AND** columns in order: Fecha, Tipo, Producto, SKU, Punto de Venta, Cambio, Antes, Después, Usuario, Motivo, Venta, Devolución
- **AND** headers are formatted in bold
- **AND** numeric columns use appropriate number formatting
- **AND** columns are auto-fitted to content width

#### Scenario: Export respects current summary sort order

- **WHEN** the summary export request includes `sortBy` and `sortDirection` parameters
- **THEN** the Excel rows SHALL follow the specified sort order

#### Scenario: Detail export uses default detail order

- **WHEN** the detail export request includes `outputModel=detail`
- **THEN** the Excel rows SHALL be ordered by movement date descending

#### Scenario: Export respects product search

- **WHEN** the export request includes `productSearch`
- **THEN** the Excel rows SHALL include only movements whose product name or SKU matches the search text

#### Scenario: Export exceeds 50,000-row limit

- **WHEN** an authenticated administrator requests `GET /api/reports/inventory-movements/export` with filters matching more than 50,000 rows for the selected output model
- **THEN** the system returns HTTP 409 Conflict
- **AND** the response body includes `{ "message": "Más de 50.000 filas en el resultado. Ajuste los filtros para exportar.", "totalCount": <real count> }`

#### Scenario: Non-administrator export access denied

- **WHEN** an authenticated operator requests `GET /api/reports/inventory-movements/export`
- **THEN** the system returns HTTP 403 Forbidden

#### Scenario: Unauthenticated export access denied

- **WHEN** an unauthenticated user requests `GET /api/reports/inventory-movements/export`
- **THEN** the system returns HTTP 401 Unauthorized

### Requirement: Inventory Movement Summary Frontend Page

The system SHALL provide a frontend page at `/reports/inventory-movement-summary` accessible from the Reports hub. The page SHALL display a filter panel with mandatory date range, optional POS selector, output model selector, product name/SKU search field, a paginated results table, and an Excel export button. Summary mode SHALL show aggregated product totals. Detail mode SHALL show one row per inventory movement transaction.

#### Scenario: Reports hub includes inventory movement summary card

- **WHEN** an administrator navigates to the Reports hub (`/reports`)
- **THEN** a card for "Resumen de movimientos de inventario" is displayed with a brief description and link to `/reports/inventory-movement-summary`

#### Scenario: Date filters are required before search

- **WHEN** an administrator navigates to `/reports/inventory-movement-summary`
- **THEN** the page displays date range inputs (start date and end date) that MUST be filled before querying
- **AND** the search button is disabled until both dates are provided

#### Scenario: Optional POS filter

- **WHEN** the filter panel is displayed
- **THEN** a POS selector is available with "Todos los puntos de venta" as default
- **AND** the list of POS is populated from the existing POS API

#### Scenario: Output model selector

- **WHEN** the filter panel is displayed
- **THEN** an output model selector is available with "Resumen" selected by default
- **AND** the selector includes "Detalle" as an alternate option

#### Scenario: Product search filter

- **WHEN** the filter panel is displayed
- **THEN** a single product search input is available for product name or SKU
- **AND** searching applies the text to both product name and SKU matches

#### Scenario: Summary results table with sortable columns

- **WHEN** summary report results are displayed
- **THEN** a table shows columns: Producto, SKU, Adiciones, Sustracciones, Diferencia
- **AND** the Adiciones, Sustracciones, and Diferencia columns are sortable (clicking toggles asc/desc)
- **AND** pagination controls allow navigating between pages

#### Scenario: Detail results table

- **WHEN** detail report results are displayed
- **THEN** a table shows columns: Fecha, Tipo, Producto, SKU, Punto de Venta, Cambio, Antes, Después, Usuario, Motivo, Venta, Devolución
- **AND** detail columns are not interactive sort controls
- **AND** pagination controls allow navigating between pages

#### Scenario: Help legend explains terminology

- **WHEN** the inventory movement summary page is displayed
- **THEN** a visible text or tooltip explains: "Adiciones = entradas al inventario (devoluciones, ajustes positivos, importaciones). Sustracciones = salidas del inventario (ventas, ajustes negativos). Diferencia = Adiciones − Sustracciones."

#### Scenario: Export button triggers selected model download

- **WHEN** the administrator clicks "Exportar a Excel"
- **AND** the current filters and output model produce <= 50,000 rows
- **THEN** the browser downloads the generated Excel file with name `reporte-movimientos-inventario-{yyyy-MM-dd-HH-mm}.xlsx`
- **AND** the file columns match the selected output model

#### Scenario: Export button shows warning on 409

- **WHEN** the administrator clicks "Exportar a Excel"
- **AND** the API returns 409 with `totalCount`
- **THEN** a warning toast is displayed with the message from the API response

#### Scenario: Export limit notice displayed

- **WHEN** the inventory movement summary page is displayed
- **THEN** a notice near the export button reads: "Máximo 50.000 filas. Si hay más resultados, ajuste los filtros."

#### Scenario: Operator cannot access the report

- **WHEN** an operator is logged in
- **THEN** the "Resumen de movimientos de inventario" card is NOT visible in the Reports hub
- **AND** navigating directly to `/reports/inventory-movement-summary` is denied
