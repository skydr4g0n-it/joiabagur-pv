## Context

Points of sale persist sales (`Sale.Price * Quantity`). The sales report today sums sale lines in the filter and **does not** subtract returns in `totalAmount`. The dashboard already treats monthly revenue as net of returns for some KPIs. Administrators need per-POS annual brackets and **beneficio real** after commission in report, Excel, and dashboard.

Stack: layered .NET API + EF/PostgreSQL; React admin at `/points-of-sale`, report at `/reports/sales`, dashboards for admin/operator.

## Goals / Non-Goals

**Goals:**

- Persist ordered commission tiers per POS (`decimal` min/max/% in DB/API).
- Calculate commission with UTC calendar-year, return-adjusted YTD per POS.
- Apply **one rate per sale** from the tier active at gross YTD-before-sale. Commission uses the net base, then VAT on that commission (three roundings).
- Sales report: return-adjusted `totalAmount`, `totalCommission`, `totalAmountNet`, optional per-POS breakdown; Excel includes totals.
- Dashboard: show net-after-commission on monthly revenue (admin global + operator POS).
- Admin-only tier CRUD; UI inputs in whole euros.

**Non-Goals:**

- Storing commission on each `Sale` at checkout.
- Payout workflows or operator tier editing/view.
- Historical tier versioning (reports always use current tiers).
- Per-line commission column in the sales preview table.

## Decisions

### 1. Data model: `PointOfSaleCommissionTier`

| Field | Type | Notes |
|-------|------|--------|
| `Id` | Guid | PK |
| `PointOfSaleId` | Guid | FK → `PointOfSales` |
| `MinAmountInclusive` | decimal(18,2) | Lower bound of annual YTD |
| `MaxAmountInclusive` | decimal(18,2)? | Null = no upper limit |
| `CommissionPercent` | decimal(5,2) | e.g. 20.00 = 20% |
| timestamps | `BaseEntity` | |

**Validation (replace-all PUT):** first tier min = 0; contiguous inclusive ranges; one open-ended max (last); `0 ≤ CommissionPercent ≤ 100`. Empty list = 0% commission.

**UI:** min/max entered as whole euros; API persists decimals (e.g. 20000.00). Future cent precision does not require schema change.

### 2. Return-adjusted YTD timeline (UTC calendar year)

For each POS and year `Y`, build ordered events:

1. Sale events: `SaleDate` (UTC), amount `+ Price × Quantity`.
2. Return events: `ReturnDate` (UTC), amount `− Σ(ReturnSale.Quantity × UnitPrice)` for that return at that POS.

Walk events in chronological order (`SaleDate`/`ReturnDate`, then stable tie-breaker). Maintain running YTD.

**Tier lookup:** Given gross YTD before a sale event (`Price × Quantity`, VAT included), find the tier where `MinAmountInclusive ≤ YTD ≤ MaxAmountInclusive` (null max = unbounded). No split across tiers when a sale would cross a boundary. Returns still subtract gross `ReturnSale.Quantity × UnitPrice` from YTD. Tier bounds configured by the admin are not rescaled.

**Commission amount** (entire sale, one rate). `VatRate` is the shared domain constant `0.21` (`divisor = 1 + VatRate`). Each step rounds to 2 decimal places, midpoint away from zero:

1. `netBase = Round(saleAmount / (1 + VatRate), 2)`
2. `commissionNet = Round(netBase × CommissionPercent / 100, 2)`
3. `commission = Round(commissionNet × (1 + VatRate), 2)`

`saleAmount` is gross `Price × Quantity`, including manual price overrides. Empty tiers → commission 0 (skip the formula).

**Example (tier):** tiers 0–20000 @ 20%, 20001–100000 @ 30%. YTD before sale = 15000, sale 10000 → rate 20% on the full sale, not a 5k/5k split. After the three steps the commission is 2000.00.

**Example (rounding differs from gross × %):** sale 100.00 at 10% → net 82.64, commission net 8.26, commission with VAT 9.99 (gross × 10% would be 10.00).

**Returns:** reduce YTD for subsequent sales in the same year. Partial returns use returned quantity × snapshotted unit price.

**Recalculation:** Always uses **current** tier rows from DB (editing tiers changes historical report nets).

### 3. VAT constant

No business code currently hardcodes 21% or 1.21. Add one shared constant on the domain layer, next to other shared constants (for example `VatConstants.StandardRate = 0.21m`). The commission calculator reads that constant. If implementation finds another VAT literal in application code, switch it to the same constant. Do not introduce per-line or per-product rates.

### 4. Report aggregates

- **`totalAmount` (gross for display):** sum of filtered sale line amounts minus return amounts whose `ReturnDate` falls in the report filter (same POS scope as sales). Amounts stay VAT-inclusive.
- **`totalCommission`:** sum of per-sale VAT-inclusive commission (three-step formula) for sale lines matching the report filters. Tier selection still uses the full-year gross YTD timeline up to each sale.
- **`totalAmountNet`:** `totalAmount − totalCommission`.
- **`aggregatesByPointOfSale` (optional array):** when the filtered set spans multiple POS, include `{ pointOfSaleId, totalAmount, totalCommission, totalAmountNet }` per POS.

Paginated `items` remain sale rows (unchanged columns); aggregates carry the new semantics.

### 5. Admin API

- `GET /api/point-of-sales/{id}/commission-tiers`
- `PUT /api/point-of-sales/{id}/commission-tiers` — **Administrator** only; replace-all.

### 6. Frontend

- **POS:** “Comisiones” dialog; integer euro fields; es-ES validation messages.
- **Report totals:** primary amount = return-adjusted gross; net after commission in parentheses — `Z € (W €)` where Z = gross, W = net (`totalAmountNet`). Reuse the same formatter for dashboard KPIs.
- **Excel:** footer/summary row with `totalAmount`, `totalCommission`, `totalAmountNet` (and per-POS sheet section if breakdown enabled).
- **Dashboard:** API exposes `monthlyRevenue` (return-adjusted gross) and `monthlyRevenueNet` (after commission). Admin «Ingresos del mes» and operator monthly revenue KPI render **`formatCurrency(monthlyRevenue) (formatCurrency(monthlyRevenueNet))`** — identical pattern to the sales report totals bar, not a separate label-only net figure.

### 7. Flow (report)

```
Report filters → SaleRepository (sales + returns in window)
              → CommissionCalculator (YTD events per POS/year)
              → totalAmount, totalCommission, totalAmountNet (+ breakdown)
```

## Risks / Trade-offs

- **Report `totalAmount` behavior change** (now net of returns in filter) vs legacy sum-of-sales-only — documented; matches user expectation for “importe real”.
- **Performance** — load events per POS/year in filtered set; acceptable at current scale.
- **Tier edits and formula change** — historical months recalculate on read (commission is not stored); accepted. Switching to the three-step formula changes some commission cents versus gross × %.
- **VAT is always 21%** — reduced or exempt lines are out of scope; every sale uses the global rate.
- **Dashboard vs report** — share one calculator to avoid divergent numbers.

## Migration Plan

1. EF migration for `PointOfSaleCommissionTiers`.
2. Deploy API + UI; existing POS have zero tiers (commission 0).
3. Admin configures tiers.
4. Rollback: revert migration and DTO fields; deploy atomically.

## Open Questions

- None (stakeholder clarification completed 2026-10-24; VAT base clarified 2026-10-26: gross YTD, three-step net-then-VAT commission, parentheses stay gross minus that commission).
