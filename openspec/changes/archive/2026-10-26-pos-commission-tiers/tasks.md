## 1. Domain and Persistence

- [x] 1.1 Add `PointOfSaleCommissionTier` entity (decimal min/max/percent, PointOfSaleId) and navigation on `PointOfSale`; EF configuration and DbSet
- [x] 1.2 Create and apply EF migration for `PointOfSaleCommissionTiers` with cascade delete; verify migration builds

## 2. Commission Calculation Service

- [x] 2.1 Implement calendar-year UTC calculator: return-adjusted YTD timeline (sales on SaleDate, returns on ReturnDate); one rate per sale from YTD-before-sale; empty tiers → 0%. Unit tests `Method_Scenario_ExpectedResult` for single-tier sale, boundary-cross sale (prior tier on full amount), partial return adjusting YTD, year reset, no tiers
- [x] 2.2 Repository/queries to load sales and returns per POS/year ordered for YTD walks; focused test or integration coverage

## 3. Commission Tiers API (POS Admin)

- [x] 3.1 DTOs, FluentValidation (start at 0, contiguous ranges, single open max, percent 0–100), GET/PUT replace-all service
- [x] 3.2 `GET`/`PUT /api/point-of-sales/{id}/commission-tiers` — GET/PUT Administrator only (operator 403 on both); integration tests for success, validation 400, operator 403

## 4. Sales Report and Export

- [x] 4.1 Extend `SalesReportResponse` with `totalAmount` (sales minus returns in filter), `totalCommission`, `totalAmountNet`, and `aggregatesByPointOfSale` when multiple POS; wire `GetSalesReportAsync` and export path
- [x] 4.2 Excel export summary row/section with `totalAmount`, `totalCommission`, `totalAmountNet`; integration tests for aggregates and return-adjusted gross
- [x] 4.3 Empty result and no-tier POS: commission 0, net equals gross; adjust `SalesReportController` tests

## 5. Dashboard Net Revenue

- [x] 5.1 Extend dashboard stats DTO and `DashboardService` for `monthlyRevenueNet` (global admin + operator POS) using shared calculator; API tests or service unit tests

## 6. Frontend — POS Commission UI

- [x] 6.1 Types and service methods for commission tiers GET/PUT
- [x] 6.2 Admin-only dialog on `/points-of-sale` (integer euro min/max inputs, validation, save); operators do not see the action
- [x] 6.3 Playwright: admin saves valid tier ranges (`should save commission tiers when admin submits valid ranges`)

## 7. Frontend — Report and Dashboard

- [x] 7.1 Sales report types and UI: parentheses net, show commission; per-POS breakdown when API returns it
- [x] 7.2 Shared `formatGrossWithNetInParentheses` (or reuse from sales report totals); admin «Ingresos del mes» and operator monthly KPI show `bruto € (neto €)` like `/reports/sales`; manual or Playwright check
- [x] 7.3 Playwright: `should show net amount in parentheses when report loads` with seeded tiers

## 8. Commission on Net Amount, Then VAT

- [x] 8.1 Add a shared domain VAT constant at 21% (`0.21`). Point the commission calculator at it. If any other business-code VAT literal exists, replace it with the same constant
- [x] 8.2 Change `PosCommissionCalculator` so YTD and tier lookup stay on gross, and commission is `Round(Round(Round(gross / 1.21, 2) × percent / 100, 2) × 1.21, 2)` with midpoint away from zero. Unit test: 100.00 EUR at 10% → 9.99; 10000 EUR at 20% → 2000.00; empty tiers → 0. Update existing calculator tests that assumed gross × %
- [x] 8.3 Confirm sales report and dashboard still subtract that commission from gross (`totalAmountNet`, `monthlyRevenueNet`) and that sale-row prices stay VAT-inclusive. Adjust assertions that encoded the old formula
