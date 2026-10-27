# Spec Delta

## MODIFIED Requirements

### Requirement: Sales Report API with Extended Filters and Global Aggregates

The system SHALL provide a REST API endpoint at `GET /api/reports/sales` that returns paginated sales data with extended filtering and global aggregate totals computed over the entire filtered result set (not just the current page). Aggregates SHALL include `totalAmount` (filtered gross sale amounts minus return amounts in the filter window and scope, minus gift-card coverage dated in that same window and scope; amounts stay VAT-inclusive), `totalCommission` (sum of per-sale commissions from `pos-commission-tiers`, including VAT applied to the net commission), and `totalAmountNet` (`totalAmount` minus that commission). Tier selection uses calendar-year UTC return-adjusted economic YTD from `pos-commission-tiers`. When the filtered set includes more than one point of sale, the response SHALL include per-POS aggregate breakdown with the same three amounts per POS. Only authenticated users can access this endpoint; administrators see all POS, operators see only assigned POS.

#### Scenario: Administrator retrieves sales report with default filters

- **WHEN** an authenticated administrator requests `GET /api/reports/sales` without filters
- **THEN** the system returns paginated sales for the last 30 days across all points of sale
- **AND** the response includes `items`, `totalCount`, `page`, `pageSize`, `totalPages`
- **AND** the response includes global aggregates: `totalSalesCount`, `totalQuantity`, `totalAmount`, `totalCommission`, `totalAmountNet` over the filtered dataset

#### Scenario: Filter sales report by text search

- **WHEN** an authenticated user requests `GET /api/reports/sales?search=anillo`
- **THEN** the system returns sales where `Product.SKU` or `Product.Name` contains "anillo" (case-insensitive)
- **AND** global aggregates reflect only the matching sales (and returns in scope per filter rules)

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
- **AND** `totalSalesCount = 0`, `totalQuantity = 0`, `totalAmount = 0`, `totalCommission = 0`, `totalAmountNet = 0`

#### Scenario: Net amount subtracts commissions on filtered sales

- **GIVEN** filtered sales with return-adjusted `totalAmount` T and calculated commission C on those sales
- **WHEN** an authenticated user requests the sales report with those filters
- **THEN** `totalCommission` equals C
- **AND** `totalAmountNet` equals T − C

#### Scenario: Returns in filter window reduce totalAmount

- **GIVEN** filtered sales totaling 10000 EUR in the date range
- **AND** returns totaling 2000 EUR with `ReturnDate` in the same filter window and POS scope
- **WHEN** an authenticated user requests the sales report
- **THEN** `totalAmount` equals 8000 EUR before commission

#### Scenario: Per-POS breakdown when multiple POS match

- **GIVEN** a filter that includes sales from POS A and POS B
- **WHEN** an authenticated administrator requests the sales report
- **THEN** the response includes per-POS entries with `totalAmount`, `totalCommission`, and `totalAmountNet` for each POS in the filtered set

#### Scenario: Unauthenticated access denied

- **WHEN** an unauthenticated user requests `GET /api/reports/sales`
- **THEN** the system returns 401 Unauthorized

#### Scenario: Gift card coverage reduces the window total

- **GIVEN** a 100.00 EUR gift-card sale on 1 March at POS A
- **AND** a 150.00 EUR product sale on 15 March at POS A with 100.00 EUR coverage dated 15 March
- **WHEN** an administrator requests the sales report for 15 March through 15 March at POS A
- **THEN** `totalAmount` equals 50.00 EUR
