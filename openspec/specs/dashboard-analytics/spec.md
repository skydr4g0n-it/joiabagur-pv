# dashboard-analytics Specification

## Purpose
Role-aware landing dashboards: KPIs, trend and distribution charts, critical stock alerts and recent sales, served from pre-aggregated endpoints. Administrators see the whole business; operators see only their assigned point of sale.
## Requirements
### Requirement: Administrator Dashboard KPIs

The system SHALL provide an Administrator dashboard displaying today's sales count and total, monthly net revenue (gross sales minus returns for the same month) with year-over-year comparison, and monthly return count and total, sourced from a single pre-aggregated API endpoint.

#### Scenario: Display today's sales KPI

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays "Ventas hoy" card showing total sales count and total revenue across all POS for the current day
- **AND** data is fetched from GET /api/dashboard/stats (no posId parameter)

#### Scenario: Display monthly net revenue with year-over-year comparison

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays "Ingresos del mes" card showing NET revenue for the current month
- **AND** net revenue = gross sales revenue for the month MINUS total return value for returns registered in the same month
- **AND** displays percentage change vs. the same month of the previous year (using gross sales revenue for the previous year, unchanged)
- **AND** if no data exists for the previous year, comparison is omitted

#### Scenario: Display monthly returns KPI

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays "Devoluciones del mes" card showing return count and total refunded amount for the current month

### Requirement: Administrator Sales Trend Chart

The system SHALL display a multi-line chart showing daily sales revenue per active POS over the last 30 days, **excluding sales with associated returns**, with interactive legend for toggling POS visibility.

#### Scenario: Display 30-day sales trend excluding returned sales

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a line chart with one line per active POS for the last 30 days
- **AND** revenue aggregation excludes sales where hasReturn = true
- **AND** each line is color-coded with a unique color and labeled in the legend
- **AND** by default only the top 5 POS by monthly revenue are visible

#### Scenario: Fetch trend data from existing sales endpoint

- **WHEN** dashboard loads the trend chart
- **THEN** frontend fetches GET /api/sales with date range filter (last 30 days)
- **AND** filters client-side to exclude sales where hasReturn = true before aggregating by day and POS

### Requirement: Administrator Revenue by POS Chart

The system SHALL display a horizontal bar chart showing net revenue (excluding returned sales) per active POS for the current month, enabling quick comparison of POS performance.

#### Scenario: Display monthly revenue by POS excluding returned sales

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a horizontal bar chart with one bar per active POS
- **AND** bar values are computed client-side from sales where hasReturn = false
- **AND** bars are sorted by revenue descending
- **AND** chart height scales with the number of POS

### Requirement: Administrator Critical Stock Alerts

The system SHALL display a table of products with critically low stock (quantity <= 2) across all POS, with direct navigation to inventory adjustment.

#### Scenario: Display critical stock table

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a table of products with stock <= 2 at any POS
- **AND** columns include: product name, SKU, POS name, current stock
- **AND** table provides a navigation link to /inventory/adjust

#### Scenario: Fetch stock data from centralized inventory endpoint

- **WHEN** dashboard loads the critical stock table
- **THEN** frontend fetches GET /api/inventory/centralized
- **AND** filters results client-side for items with stock <= 2

### Requirement: Administrator Recent Sales Table

The system SHALL display a table of the 8 most recent sales **that have no associated return** across all POS on the administrator dashboard, with navigation to sales history.

#### Scenario: Display recent sales table excluding returned sales

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays up to 8 of the most recent sales where hasReturn = false
- **AND** sales where hasReturn = true are NOT shown in this table
- **AND** columns include: date, product name, POS name, operator name, amount (EUR format), payment method
- **AND** table provides a navigation link to /sales/history

### Requirement: Administrator Donut Charts with Server Cache

The system SHALL display two donut charts on the administrator dashboard — payment method distribution (excluding returned sales) and return category distribution for the current month — with data cached server-side for 24 hours.

#### Scenario: Display payment method distribution donut excluding returned sales

- **WHEN** authenticated administrator views the dashboard
- **THEN** system displays a donut chart showing sales distribution by payment method for the current month
- **AND** only sales with NO associated return are counted (ReturnSales collection is empty)
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

### Requirement: Operator Dashboard KPIs

The system SHALL provide an Operator dashboard displaying KPIs scoped to the operator's assigned POS: today's sales, weekly sales, today's returns, and stock summary.

#### Scenario: Display operator today's sales KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Mis ventas hoy" card showing sales count and total revenue for today at the assigned POS
- **AND** data is fetched from GET /api/dashboard/stats?posId={assignedPosId}

#### Scenario: Display operator weekly sales KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Mis ventas esta semana" card showing accumulated revenue for the current natural week (Mon-Sun) at the assigned POS

#### Scenario: Display operator today's returns KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Devoluciones hoy" card showing return count for today at the assigned POS

#### Scenario: Display operator stock summary KPI

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays "Artículos en stock" card showing count of SKUs with stock > 0 and total units at the assigned POS
- **AND** data is fetched from GET /api/inventory?posId={assignedPosId}

### Requirement: Operator Weekly Sales Trend Chart

The system SHALL display a simple line chart showing daily sales revenue for the current natural week (Mon-Sun) at the operator's assigned POS, **excluding sales with associated returns**.

#### Scenario: Display weekly sales trend excluding returned sales

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays a line chart with 7 data points (Mon through Sun)
- **AND** revenue aggregation excludes sales where hasReturn = true
- **AND** future days within the week show no data point

### Requirement: Operator Recent Sales Table

The system SHALL display a table of the 8 most recent sales **that have no associated return** at the operator's assigned POS with basic transaction details.

#### Scenario: Display operator recent sales excluding returned

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays up to 8 of the most recent sales at the assigned POS where hasReturn = false
- **AND** sales where hasReturn = true are NOT shown in this table
- **AND** columns include: time, product name, quantity, amount (EUR format), payment method
- **AND** table provides a navigation link to /sales/history

### Requirement: Operator Low Stock Table

The system SHALL display a table of products with stock <= 2 at the operator's assigned POS for informational awareness.

#### Scenario: Display operator low stock items

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays products with stock <= 2 at the assigned POS
- **AND** columns include: product name, SKU, current stock
- **AND** table provides a navigation link to /inventory
- **AND** operator cannot adjust stock from this view

### Requirement: Operator Quick Action Bar

The system SHALL display a sticky bottom bar with 3 quick-action buttons on the operator dashboard, always visible regardless of scroll position, providing instant access to core sales operations.

#### Scenario: Display sticky action bar

- **WHEN** authenticated operator views the dashboard
- **THEN** system displays a fixed bottom bar with 3 buttons
- **AND** buttons are: "Nueva venta manual" (links to /sales/new), "Venta por imagen" (links to /sales/new/image), "Registrar devolución" (links to /returns/new)
- **AND** bar remains visible at all scroll positions

#### Scenario: Action bar hidden for administrators

- **WHEN** authenticated administrator views the dashboard
- **THEN** the sticky bottom action bar is NOT displayed

### Requirement: Dashboard Role Routing

The system SHALL render the appropriate dashboard based on the authenticated user's role when navigating to /dashboard.

#### Scenario: Administrator sees admin dashboard

- **WHEN** authenticated administrator navigates to /dashboard
- **THEN** system renders AdminDashboard component with global KPIs, charts, alerts, and donut charts

#### Scenario: Operator sees operator dashboard

- **WHEN** authenticated operator navigates to /dashboard
- **THEN** system renders OperatorDashboard component with POS-scoped KPIs, weekly trend, tables, and action bar

### Requirement: Dashboard Stats API Endpoint

The system SHALL provide a GET /api/dashboard/stats endpoint returning pre-aggregated metrics for dashboard display, supporting optional POS filtering for operator-scoped data.

#### Scenario: Administrator requests global stats with net revenue

- **WHEN** authenticated administrator calls GET /api/dashboard/stats without posId
- **THEN** system returns aggregated metrics across all POS:
  - salesTodayCount, salesTodayTotal
  - monthlyRevenue (NET: gross sales minus return totals for the current month)
  - previousYearMonthlyRevenue (nullable, gross sales only for comparison period)
  - monthlyReturnsCount, monthlyReturnsTotal
  - paymentMethodDistribution (array of method + amount + count, cached 24h, excludes returned sales)
  - returnCategoryDistribution (array of category + count, cached 24h)

#### Scenario: Operator requests POS-scoped stats

- **WHEN** authenticated operator calls GET /api/dashboard/stats?posId={id}
- **THEN** system validates operator is assigned to the requested POS
- **AND** returns metrics scoped to that POS:
  - salesTodayCount, salesTodayTotal
  - weeklyRevenue (current Mon-Sun natural week, gross)
  - returnsTodayCount
- **AND** does not include donut chart distributions (admin-only)

#### Scenario: Operator requests stats for unassigned POS

- **WHEN** operator calls GET /api/dashboard/stats?posId={unassignedId}
- **THEN** system returns 403 Forbidden

#### Scenario: Unauthenticated request

- **WHEN** unauthenticated user calls GET /api/dashboard/stats
- **THEN** system returns 401 Unauthorized
