## MODIFIED Requirements

### Requirement: Dashboard Stats API Endpoint

The system SHALL provide a GET /api/dashboard/stats endpoint returning pre-aggregated metrics for dashboard display, supporting optional POS filtering for operator-scoped data. Monthly figures SHALL include return-adjusted gross revenue and net-after-POS-commission revenue for the current UTC month, using the same calendar-year return-adjusted gross YTD tier rules and three-step VAT commission formula as sales reports and the current tier configuration per POS. `monthlyRevenue` stays VAT-inclusive gross; `monthlyRevenueNet` is that gross minus VAT-inclusive commission.

#### Scenario: Administrator requests global stats with net revenue

- **WHEN** an authenticated administrator calls GET /api/dashboard/stats without posId
- **THEN** system returns aggregated metrics across all POS:
  - salesTodayCount, salesTodayTotal
  - monthlyRevenue (return-adjusted gross sales for the current UTC month)
  - monthlyRevenueNet (`monthlyRevenue` minus POS commission on sales in that month per tier rules and the three-step VAT commission formula)
  - previousYearMonthlyRevenue (nullable, gross sales only for comparison period)
  - monthlyReturnsCount, monthlyReturnsTotal
  - paymentMethodDistribution (array of method + amount + count, cached 24h, excludes returned sales)
  - returnCategoryDistribution (array of category + count, cached 24h)

#### Scenario: Operator requests POS-scoped stats

- **WHEN** an authenticated operator calls GET /api/dashboard/stats?posId={id}
- **THEN** system validates operator is assigned to the requested POS
- **AND** returns metrics scoped to that POS:
  - salesTodayCount, salesTodayTotal
  - monthlyRevenue (return-adjusted gross for the current UTC month)
  - monthlyRevenueNet (monthlyRevenue minus commission for that POS using the same calculator as admin global stats)
  - weeklyRevenue (current Mon-Sun natural week, gross)
  - returnsTodayCount
- **AND** does not include donut chart distributions (admin-only)

#### Scenario: POS without commission tiers shows net equal to return-adjusted gross

- **GIVEN** a POS with no commission tiers
- **WHEN** dashboard stats are requested for that POS for the current month
- **THEN** net-after-commission monthly revenue equals return-adjusted gross monthly sales

#### Scenario: Operator requests stats for unassigned POS

- **WHEN** operator calls GET /api/dashboard/stats?posId={unassignedId}
- **THEN** system returns 403 Forbidden

#### Scenario: Unauthenticated request

- **WHEN** unauthenticated user calls GET /api/dashboard/stats
- **THEN** system returns 401 Unauthorized

## ADDED Requirements

### Requirement: Dashboard Monthly Revenue Display Matches Sales Report

The system SHALL display monthly revenue KPIs on the administrator and operator dashboards using the same gross-with-net-in-parentheses pattern as the sales report «Importe total» totals bar: return-adjusted gross amount formatted as currency, immediately followed by net-after-commission in parentheses (e.g. `12.345,67 € (9.876,54 €)`), using the same locale and currency formatting helper as `/reports/sales`.

#### Scenario: Administrator monthly revenue card shows gross and net like the report

- **GIVEN** an administrator on the dashboard with `monthlyRevenue` and `monthlyRevenueNet` from the stats API
- **WHEN** the «Ingresos del mes» KPI card is rendered
- **THEN** the primary figure shows `monthlyRevenue` as currency
- **AND** `monthlyRevenueNet` appears in parentheses after the gross amount
- **AND** the visual pattern matches the sales report global totals bar (not a second line or subtitle-only net)

#### Scenario: Operator monthly revenue KPI shows gross and net like the report

- **GIVEN** an operator on the POS dashboard with `monthlyRevenue` and `monthlyRevenueNet` for the assigned POS
- **WHEN** the monthly revenue KPI is displayed
- **THEN** the amount uses the same `gross € (net €)` formatting as the administrator dashboard and sales report

#### Scenario: Zero commission shows equal gross and net in parentheses

- **GIVEN** a POS with no commission tiers or zero commission for the month
- **WHEN** the monthly revenue KPI is displayed
- **THEN** the parenthetical net equals the gross amount (both formatted as currency)
