# Spec Delta

## MODIFIED Requirements

### Requirement: Administrator Dashboard KPIs

The system SHALL provide an Administrator dashboard displaying today's sales count and total, monthly net revenue (gross sales minus returns for the same month, minus gift-card coverage dated in that month) with year-over-year comparison, and monthly return count and total, sourced from a single pre-aggregated API endpoint.

#### Scenario: Display today's sales KPI

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays "Ventas hoy" card showing total sales count and total revenue across all POS for the current day
- **AND** today's revenue subtracts gift-card coverage dated today
- **AND** data is fetched from GET /api/dashboard/stats (no posId parameter)

#### Scenario: Display monthly net revenue with year-over-year comparison

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays "Ingresos del mes" card showing NET revenue for the current month
- **AND** net revenue = gross sales revenue for the month MINUS total return value for returns registered in the same month MINUS gift-card coverage dated in that month
- **AND** displays percentage change vs. the same month of the previous year using that same formula
- **AND** if no data exists for the previous year, comparison is omitted

#### Scenario: Display monthly returns KPI

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays "Devoluciones del mes" card showing return count and total refunded amount for the current month

#### Scenario: Redemption day shows only the cash top-up

- **GIVEN** a 100.00 EUR gift card issued on an earlier day
- **AND** today a 150.00 EUR product is sold with 100.00 EUR coverage dated today
- **WHEN** the administrator views today's sales total
- **THEN** this checkout contributes 50.00 EUR to today's revenue

### Requirement: Administrator Donut Charts with Server Cache

The system SHALL display two donut charts on the administrator dashboard — payment method distribution (excluding returned sales, and excluding gift-card coverage on the sales that remain) and return category distribution for the current month — with data cached server-side for 24 hours.

#### Scenario: Display payment method distribution donut excluding returned sales

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a donut chart showing sales distribution by payment method for the current month
- **AND** only sales with NO associated return are counted (ReturnSales collection is empty)
- **AND** each method amount is `Price × Quantity` minus gift-card coverage on that sale
- **AND** data is fetched from GET /api/dashboard/stats (paymentMethodDistribution field)
- **AND** server caches this aggregation for 24 hours using IMemoryCache

#### Scenario: Display return category distribution donut

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a donut chart showing return distribution by ReturnCategory for the current month
- **AND** data is fetched from GET /api/dashboard/stats (returnCategoryDistribution field)
- **AND** server caches this aggregation for 24 hours using IMemoryCache

#### Scenario: Cache expiration refreshes data

- **WHEN** 24 hours have elapsed since the last cache write
- **THEN** next request to GET /api/dashboard/stats triggers fresh aggregation
- **AND** new results are cached for another 24 hours

#### Scenario: A returned sale stays out of the payment mix

- **GIVEN** a product sale that has a gift-card exchange return
- **WHEN** the administrator views the payment-method donut
- **THEN** that sale contributes nothing to any method amount

### Requirement: Operator Dashboard KPIs

The system SHALL provide an Operator dashboard displaying KPIs scoped to the operator's assigned POS: today's sales, weekly sales, today's returns, and stock summary. Today and week revenue SHALL subtract gift-card coverage dated in that period.

#### Scenario: Display operator today's sales KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Mis ventas hoy" card showing sales count and total revenue for today at the assigned POS
- **AND** today's revenue subtracts gift-card coverage dated today at that POS
- **AND** data is fetched from GET /api/dashboard/stats?posId={assignedPosId}

#### Scenario: Display operator weekly sales KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Mis ventas esta semana" card showing accumulated revenue for the current natural week (Mon-Sun) at the assigned POS
- **AND** that revenue subtracts gift-card coverage dated in that week at that POS

#### Scenario: Display operator today's returns KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Devoluciones hoy" card showing return count for today at the assigned POS

#### Scenario: Display operator stock summary KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Artículos en stock" card showing count of SKUs with stock > 0 and total units at the assigned POS
- **AND** data is fetched from GET /api/inventory?posId={assignedPosId}

### Requirement: Dashboard Stats API Endpoint

The system SHALL provide a GET /api/dashboard/stats endpoint returning pre-aggregated metrics for dashboard display, supporting optional POS filtering for operator-scoped data. Monthly figures SHALL include return-adjusted economic revenue and net-after-POS-commission revenue for the current UTC month, using the same calendar-year economic YTD tier rules and three-step VAT commission formula as sales reports and the current tier configuration per POS. `monthlyRevenue` stays VAT-inclusive after subtracting returns and gift-card coverage; `monthlyRevenueNet` is that amount minus VAT-inclusive commission.

#### Scenario: Administrator requests global stats with net revenue

- **WHEN** an authenticated administrator calls GET /api/dashboard/stats without posId
- **THEN** system returns aggregated metrics across all POS:
  - salesTodayCount, salesTodayTotal
  - monthlyRevenue (return-adjusted economic sales for the current UTC month, minus gift-card coverage dated in that month)
  - monthlyRevenueNet (`monthlyRevenue` minus POS commission on the economic amounts in that month per tier rules and the three-step VAT commission formula)
  - previousYearMonthlyRevenue (nullable, same economic formula for the comparison period)
  - monthlyReturnsCount, monthlyReturnsTotal
  - paymentMethodDistribution (array of method + amount + count, cached 24h, excludes returned sales, amount minus gift-card coverage)
  - returnCategoryDistribution (array of category + count, cached 24h)

#### Scenario: Operator requests POS-scoped stats

- **WHEN** an authenticated operator calls GET /api/dashboard/stats?posId={id}
- **THEN** system validates operator is assigned to the requested POS
- **AND** returns metrics scoped to that POS:
  - salesTodayCount, salesTodayTotal
  - monthlyRevenue (return-adjusted economic amount for the current UTC month, minus gift-card coverage dated in that month)
  - monthlyRevenueNet (monthlyRevenue minus commission for that POS using the same calculator as admin global stats)
  - weeklyRevenue (current Mon-Sun natural week, economic amount minus gift-card coverage dated in that week)
  - returnsTodayCount
- **AND** does not include donut chart distributions (admin-only)

#### Scenario: POS without commission tiers shows net equal to return-adjusted gross

- **GIVEN** a POS with no commission tiers
- **WHEN** dashboard stats are requested for that POS for the current month
- **THEN** net-after-commission monthly revenue equals the return-adjusted economic monthly amount

#### Scenario: Operator requests stats for unassigned POS

- **WHEN** operator calls GET /api/dashboard/stats?posId={unassignedId}
- **THEN** system returns 403 Forbidden

#### Scenario: Unauthenticated request

- **WHEN** unauthenticated user calls GET /api/dashboard/stats
- **THEN** system returns 401 Unauthorized

### Requirement: Administrator Sales Trend Chart

The system SHALL display a multi-line chart showing daily sales revenue per active POS over the last 30 days, **excluding sales with associated returns**, with interactive legend for toggling POS visibility. Each day's revenue SHALL subtract gift-card coverage dated that day on the sales included in the chart.

#### Scenario: Display 30-day sales trend excluding returned sales

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a line chart with one line per active POS for the last 30 days
- **AND** revenue aggregation excludes sales where hasReturn = true
- **AND** each included sale contributes `Price × Quantity` minus its gift-card coverage
- **AND** each line is color-coded with a unique color and labeled in the legend
- **AND** by default only the top 5 POS by monthly revenue are visible

#### Scenario: Fetch trend data from existing sales endpoint

- **WHEN** dashboard loads the trend chart
- **THEN** frontend fetches GET /api/sales with date range filter (last 30 days)
- **AND** filters client-side to exclude sales where hasReturn = true before aggregating by day and POS
- **AND** subtracts the gift-card coverage returned on each sale

### Requirement: Administrator Revenue by POS Chart

The system SHALL display a horizontal bar chart showing net revenue (excluding returned sales) per active POS for the current month, enabling quick comparison of POS performance. Bar values SHALL subtract gift-card coverage on the included sales.

#### Scenario: Display monthly revenue by POS excluding returned sales

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a horizontal bar chart with one bar per active POS
- **AND** bar values are computed client-side from sales where hasReturn = false, minus gift-card coverage on those sales
- **AND** bars are sorted by revenue descending
- **AND** chart height scales with the number of POS

### Requirement: Operator Weekly Sales Trend Chart

The system SHALL display a simple line chart showing daily sales revenue for the current natural week (Mon-Sun) at the operator's assigned POS, **excluding sales with associated returns**. Each day SHALL subtract gift-card coverage on the included sales.

#### Scenario: Display weekly sales trend excluding returned sales

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays a line chart with 7 data points (Mon through Sun)
- **AND** revenue aggregation excludes sales where hasReturn = true
- **AND** each included sale contributes `Price × Quantity` minus its gift-card coverage
- **AND** future days within the week show no data point
