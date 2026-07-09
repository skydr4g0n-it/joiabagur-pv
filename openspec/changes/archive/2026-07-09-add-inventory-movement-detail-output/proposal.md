## Why

Administrators currently can only see inventory movement totals aggregated by product, which is useful for high-level reporting but not enough to audit the individual stock operations behind those totals. The report should let users switch between the current summary and a detailed transaction-level view without leaving the existing reporting page.

## What Changes

- Add an output model selector to `/reports/inventory-movement-summary` with `Resumen` as the default and `Detalle` as the alternate mode.
- Keep the current aggregated result model unchanged for summary mode.
- Add detail mode that returns and displays each matching inventory movement transaction separately.
- Include detailed movement columns: date, movement type, product, SKU, point of sale, quantity change, quantity before, quantity after, user, reason, `saleId`, and `returnId`.
- Add a product search filter that matches by product name or SKU and applies to both summary and detail modes.
- Update Excel export so it exports the currently selected output model: aggregated rows for summary mode and transaction rows for detail mode.
- Keep the report restricted to administrators.
- Do not add interactive column sorting for detail mode; detail mode is initially ordered using the report's default ordering.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `inventory-movement-report`: Add selectable summary/detail output models, product name/SKU filtering, transaction-level report rows, and matching Excel export behavior.

## Impact

- Backend report request/response DTOs for inventory movement reports.
- `GET /api/reports/inventory-movements` and `GET /api/reports/inventory-movements/export` query handling and response/export generation.
- Inventory movement repository queries for product name/SKU filtering and transaction-level report projection.
- Frontend report types, service query parameters, and `/reports/inventory-movement-summary` UI/table rendering.
- Backend and frontend tests covering summary mode compatibility, detail mode, product search, and Excel export variants.
