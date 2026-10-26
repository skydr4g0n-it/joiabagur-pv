## Why

Los POS registran ventas, pero la aplicación no modela la comisión que se llevan por tramos de facturación anual. Sin esos porcentajes no se puede calcular el beneficio real (importe neto tras comisión) en reportes y dashboard. Hace falta configuración por POS (solo admin) y visualización del neto junto al importe total.

## What Changes

- Administrators define per-POS annual sales commission tiers (amount ranges + commission %).
- Commission uses **calendar year (UTC)** with YTD built chronologically: sales on `SaleDate` (+), returns on `ReturnDate` (−) using `ReturnSale.Quantity × UnitPrice`.
- **Per sale:** entire line uses the tier determined by return-adjusted YTD **immediately before** that sale (not progressive/marginal split). A sale that would cross a threshold still uses the prior tier’s % on the full amount.
- Tier selection (YTD) stays on gross `Price × Quantity` (VAT included, including manual overrides). Commission is not `gross × %`.
- Commission base is the net amount (gross ÷ 1.21), then VAT is applied to that commission, with a round to 2 decimals at each step (AwayFromZero). Shared domain constant for the 21% rate (no VAT literal exists in business code today).
- Displayed totals stay gross with net-after-commission in parentheses (`totalAmount − totalCommission`). Sale prices on screen and in sale rows stay VAT-inclusive. Reports recalculate with the new formula (commission is not stored on the sale).
- Sales report aggregates: `totalAmount` = filtered sales minus returns in the filter window; `totalCommission` and `totalAmountNet` (= `totalAmount` − commission on filtered sales). Optional per-POS breakdown when multiple POS match filters.
- UI `/reports/sales`: importe total shows net in parentheses; Excel export includes aggregate commission/net columns.
- Dashboard (admin global + operator POS): monthly revenue KPI shows return-adjusted gross with net after commission in parentheses, same format as `/reports/sales` importe total (e.g. `Z € (W €)`).
- Admin UI to manage tiers (integer euros in UI; `decimal` in API/DB). Empty tiers → 0% commission.
- Tier changes recalculate reports using **current** tier definitions (no historical versioning in v1).

## Capabilities

### New Capabilities
- `pos-commission-tiers`: Admin-configurable annual sales commission brackets per POS and calendar-year commission calculation for reporting.

### Modified Capabilities
- `point-of-sale-management`: Nested API + admin UI for commission tiers (Administrator only).
- `sales-reports`: Return-adjusted `totalAmount`, `totalCommission`, `totalAmountNet`, per-POS breakdown, Excel totals.
- `dashboard-analytics`: Net-after-commission on monthly revenue KPIs (global admin and operator POS scope).

## Impact

- **Backend**: `PointOfSaleCommissionTier` table; commission calculator service; sales report + export + dashboard stats integration; DTOs/validation.
- **Frontend**: POS commission dialog; sales report totals + Excel; admin/operator dashboard KPIs.
- **Database**: Migration for commission tiers (FK to POS, decimal bounds).
- **Checkout / Sale rows**: Unchanged (no stored commission per sale; prices remain VAT-inclusive).
- **Domain**: Shared VAT rate constant (21%). Commission calculator is the consumer; replace any other business-code VAT literal with that constant if one appears during implementation.
- **Tests**: Unit tests for calculator (returns, boundary tier, no tiers, three-step VAT rounding); integration/report/dashboard coverage.

## Out of Scope

- Commission payouts, invoicing, or operator visibility of tier config.
- Effective-dated / versioned tier history.
- Changing how individual sale rows appear in the paginated table beyond aggregate semantics.
- Mixed VAT rates (reduced or exempt). Every line uses the global 21% rate.
- Showing a net-of-VAT figure in the sales report or dashboard parentheses. The parenthesis remains gross minus VAT-inclusive commission.
