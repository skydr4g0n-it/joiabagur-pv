## 1. Backend Contracts

- [x] 1.1 Add output model and product search fields to inventory movement report request DTOs, validate accepted output model values in the controller, and verify missing/invalid query values return expected HTTP responses.
- [x] 1.2 Add typed summary/detail report row DTOs and response typing that preserves the existing paginated shape, and verify existing summary consumers remain compatible when `outputModel` is omitted.
- [x] 1.3 Extend detail row DTOs to include movement `saleId` and `returnId`, and verify mapping exposes nulls for movement types without those references.

## 2. Backend Queries and Service Logic

- [x] 2.1 Update summary repository query to apply optional product name/SKU search before grouping, and verify summary totals only include matching products.
- [x] 2.2 Add a detail report repository projection with date, POS, product search, product/POS/user joins, sale/return IDs, and newest-first ordering, and verify pagination counts reflect transaction rows.
- [x] 2.3 Update `InventoryMovementReportService` to branch by output model, preserve summary sorting, ignore sorting for detail mode, and verify default summary behavior is unchanged.
- [x] 2.4 Update Excel generation to produce summary or detail sheets based on output model, keep the 50,000-row limit for both modes, and verify sheet names, headers, row order, and limit errors.

## 3. Frontend Report UI

- [x] 3.1 Extend frontend inventory movement report types and service parameter building for `outputModel` and `productSearch`, and verify requests include the selected filters.
- [x] 3.2 Add the `Modelo de salida` selector with `Resumen` default and `Detalle` alternate option to the report filter panel, and verify changing modes resets pagination appropriately.
- [x] 3.3 Add one product search input for product name or SKU, and verify searches apply to both summary and detail report requests.
- [x] 3.4 Render summary columns and sortable controls only in summary mode, and verify the existing summary table behavior still works.
- [x] 3.5 Render detail columns Fecha, Tipo, Producto, SKU, Punto de Venta, Cambio, Antes, Después, Usuario, Motivo, Venta, Devolución without sortable column controls, and verify detail rows display movement data correctly.
- [x] 3.6 Update Excel export calls and toast handling to include the selected output model and product search, and verify downloaded exports match the visible mode.

## 4. Tests and Documentation

- [x] 4.1 Add or update backend unit/integration tests using `Method_Scenario_ExpectedResult` naming for summary compatibility, product search, detail mode, invalid output model, and both export formats.
- [x] 4.2 Add or update frontend tests using `should [behavior] when [condition]` naming for output model selection, product search requests, summary table rendering, detail table rendering, and export parameters.
- [x] 4.3 Update affected documentation under `Documentos/` for the inventory movement report behavior, and verify docs mention summary/detail output models and product name/SKU search.
- [x] 4.4 Run backend and frontend validation commands for the touched areas, and verify all relevant tests/build checks pass before marking the change ready to apply.
