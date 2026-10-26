## MODIFIED Requirements

### Requirement: Dashboard Stats API

The system SHALL expose dashboard statistics including monthly revenue net of returns and net of POS commission for the current UTC month, using the same calendar-year return-adjusted gross YTD tier rules and the same three-step VAT commission formula as sales reports, and the current tier configuration per POS. `monthlyRevenue` stays VAT-inclusive gross; `monthlyRevenueNet` is that gross minus VAT-inclusive commission.

#### Scenario: Administrator requests global stats with net monthly revenue

- **WHEN** an authenticated administrator calls `GET /api/dashboard/stats` without `posId`
- **THEN** the response includes `monthlyRevenue` as return-adjusted gross sales for the current UTC month
- **AND** the response includes `monthlyRevenueNet` (or equivalent documented field) equal to `monthlyRevenue` minus commission on sales in that month per POS tier rules
- **AND** existing fields such as `monthlyReturnsCount` and `monthlyReturnsTotal` remain available

#### Scenario: Operator requests POS stats with net monthly revenue

- **WHEN** an authenticated operator calls `GET /api/dashboard/stats?posId={id}` for an assigned POS
- **THEN** the response includes return-adjusted monthly sales for that POS
- **AND** includes net-after-commission monthly revenue for that POS using the same calculator as the admin global stats

#### Scenario: POS without commission tiers shows net equal to return-adjusted gross

- **GIVEN** a POS with no commission tiers
- **WHEN** dashboard stats are requested for that POS for the current month
- **THEN** net-after-commission monthly revenue equals return-adjusted gross monthly sales

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
