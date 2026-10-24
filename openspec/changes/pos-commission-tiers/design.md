## Context

Points of sale persist sales (`Sale.Price * Quantity`). The sales report today sums sale lines in the filter and **does not** subtract returns in `totalAmount`. The dashboard already treats monthly revenue as net of returns for some KPIs. Administrators need per-POS annual brackets and **beneficio real** after commission in report, Excel, and dashboard.

Stack: layered .NET API + EF/PostgreSQL; React admin at `/points-of-sale`, report at `/reports/sales`, dashboards for admin/operator.

## Goals / Non-Goals

**Goals:**

- Persist ordered commission tiers per POS (`decimal` min/max/% in DB/API).
- Calculate commission with UTC calendar-year, return-adjusted YTD per POS.
- Apply **one rate per sale** from the tier active at YTD-before-sale (full sale amount × that %).
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

**Tier lookup:** Given YTD before a sale event, find the tier where `MinAmountInclusive ≤ YTD ≤ MaxAmountInclusive` (null max = unbounded). Commission for that sale = `saleAmount × CommissionPercent / 100` for the **entire** sale. No split across tiers when a sale would cross a boundary.

**Example:** tiers 0–20000 @ 20%, 20001–100000 @ 30%. YTD before sale = 15000, sale 10000 → commission 2000 (10k @ 20%), not a 5k/5k split.

**Returns:** reduce YTD for subsequent sales in the same year. Partial returns use returned quantity × snapshotted unit price.

**Recalculation:** Always uses **current** tier rows from DB (editing tiers changes historical report nets).

### 3. Report aggregates

- **`totalAmount` (gross for display):** sum of filtered sale line amounts minus return amounts whose `ReturnDate` falls in the report filter (same POS scope as sales). Aligns commission base with “real” revenue in the window.
- **`totalCommission`:** sum of per-sale commission for sale lines matching the report filters (commission still uses full-year YTD timeline up to each sale).
- **`totalAmountNet`:** `totalAmount − totalCommission`.
- **`aggregatesByPointOfSale` (optional array):** when the filtered set spans multiple POS, include `{ pointOfSaleId, totalAmount, totalCommission, totalAmountNet }` per POS.

Paginated `items` remain sale rows (unchanged columns); aggregates carry the new semantics.

### 4. Admin API

- `GET /api/point-of-sales/{id}/commission-tiers`
- `PUT /api/point-of-sales/{id}/commission-tiers` — **Administrator** only; replace-all.

### 5. Frontend

- **POS:** “Comisiones” dialog; integer euro fields; es-ES validation messages.
- **Report totals:** primary amount = return-adjusted gross; net after commission in parentheses — `Z € (W €)` where Z = gross, W = net (`totalAmountNet`). Reuse the same formatter for dashboard KPIs.
- **Excel:** footer/summary row with `totalAmount`, `totalCommission`, `totalAmountNet` (and per-POS sheet section if breakdown enabled).
- **Dashboard:** API exposes `monthlyRevenue` (return-adjusted gross) and `monthlyRevenueNet` (after commission). Admin «Ingresos del mes» and operator monthly revenue KPI render **`formatCurrency(monthlyRevenue) (formatCurrency(monthlyRevenueNet))`** — identical pattern to the sales report totals bar, not a separate label-only net figure.

### 6. Flow (report)

```
Report filters → SaleRepository (sales + returns in window)
              → CommissionCalculator (YTD events per POS/year)
              → totalAmount, totalCommission, totalAmountNet (+ breakdown)
```

## Risks / Trade-offs

- **Report `totalAmount` behavior change** (now net of returns in filter) vs legacy sum-of-sales-only — documented; matches user expectation for “importe real”.
- **Performance** — load events per POS/year in filtered set; acceptable at current scale.
- **Tier edits** — historical months recalculate; accepted for v1.
- **Dashboard vs report** — share one calculator to avoid divergent numbers.

## Migration Plan

1. EF migration for `PointOfSaleCommissionTiers`.
2. Deploy API + UI; existing POS have zero tiers (commission 0).
3. Admin configures tiers.
4. Rollback: revert migration and DTO fields; deploy atomically.

## Open Questions

- None (stakeholder clarification completed 2026-10-24).
