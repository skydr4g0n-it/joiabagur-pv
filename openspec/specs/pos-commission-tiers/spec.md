# pos-commission-tiers Specification

## Purpose
Define how annual POS sales commission tiers are applied to sales and returns for reporting, including VAT-aware commission amounts on gross sale prices.

## Requirements

### Requirement: Calendar-Year Commission Per Sale From Pre-Sale YTD

The system SHALL calculate POS commission using the commission tier that applies to return-adjusted year-to-date (YTD) sales **immediately before** each sale. The calendar year is UTC (1 January–31 December). YTD resets at the start of each UTC calendar year. YTD and tier bounds SHALL use gross amounts (`Price × Quantity`, VAT included, including manual price overrides). Returns SHALL subtract gross `ReturnSale.Quantity × ReturnSale.UnitPrice`. Each sale SHALL use a single tier rate on the full sale (no marginal/progressive split).

The commission amount SHALL NOT be `gross × CommissionPercent`. Using the shared domain VAT rate constant of 21% (`VatRate = 0.21`), the system SHALL compute, rounding each step to 2 decimal places with midpoint away from zero:

1. `netBase = Round(grossSaleAmount / (1 + VatRate), 2)`
2. `commissionNet = Round(netBase × CommissionPercent / 100, 2)`
3. `commission = Round(commissionNet × (1 + VatRate), 2)`

There is no per-line VAT rate. Tiers are the currently configured tiers for the POS. When no tier applies, commission is 0 and the formula is not applied.

#### Scenario: Entire sale at tier from YTD before sale

- **GIVEN** a POS with tiers: 0–20000 at 20%, 20001–100000 at 30%, 100001+ at 40%
- **AND** return-adjusted YTD before the sale is 15000 EUR in that UTC calendar year
- **WHEN** a sale of 10000 EUR occurs
- **THEN** the tier rate is 20% on the full 10000 EUR gross
- **AND** commission is 2000.00 EUR after the three rounding steps (net base 8264.46, commission net 1652.89, then × 1.21)
- **AND** the sale is not split across 20% and 30%

#### Scenario: Sale that would cross threshold still uses prior tier

- **GIVEN** the same tiers as above
- **AND** return-adjusted YTD before the sale is 19500 EUR
- **WHEN** a sale of 10000 EUR occurs in the same year
- **THEN** commission is 2000.00 EUR (prior tier 20% on the full gross sale, after the three rounding steps)

#### Scenario: Return reduces YTD for later sales

- **GIVEN** a POS with tiers starting at 0–20000 at 20%
- **AND** a sale of 18000 EUR on 2026-03-01
- **AND** a return of 5000 EUR on 2026-03-15 for that POS (same year)
- **WHEN** a sale of 10000 EUR occurs on 2026-03-20
- **THEN** return-adjusted YTD before the March 20 sale is 13000 EUR
- **AND** commission for the March 20 sale is 2000.00 EUR (20% on the full gross sale, after the three rounding steps)

#### Scenario: Return event ordering uses ReturnDate

- **GIVEN** sales and returns for a POS in the same UTC year
- **WHEN** commission YTD is computed
- **THEN** return amounts use `ReturnDate` (UTC) and subtract `ReturnSale.Quantity × ReturnSale.UnitPrice`
- **AND** sale amounts added to YTD use `SaleDate` (UTC) and gross `Price × Quantity` (VAT included)

#### Scenario: Calendar year reset

- **GIVEN** a POS with 50000 EUR return-adjusted YTD in year Y
- **WHEN** the first sale of year Y+1 is 10000 EUR
- **THEN** YTD before that sale is 0
- **AND** commission uses the first tier rate on the full gross 10000 EUR (2000.00 EUR after the three rounding steps)

#### Scenario: Open-ended top tier

- **GIVEN** a POS whose last tier is MinAmountInclusive = 100001 with MaxAmountInclusive null at 40%
- **AND** return-adjusted YTD before the sale is 150000 EUR
- **WHEN** a sale of 5000 EUR occurs
- **THEN** commission is 2000.00 EUR (40% on the full gross 5000 EUR, after the three rounding steps: net base 4132.23, commission net 1652.89, then × 1.21)

#### Scenario: Rounding differs from gross times percent

- **GIVEN** a POS whose applicable tier rate is 10%
- **AND** return-adjusted gross YTD before the sale selects that tier
- **WHEN** a sale of 100.00 EUR gross occurs
- **THEN** net base is 82.64 EUR
- **AND** commission net is 8.26 EUR
- **AND** commission is 9.99 EUR (not 10.00 EUR)

#### Scenario: No tiers configured

- **GIVEN** a POS with an empty commission tier list
- **WHEN** commission is calculated for any sale
- **THEN** commission is 0
- **AND** net amount equals gross amount

#### Scenario: Current tier configuration applies on recalculation

- **GIVEN** sales in January and tiers updated in July
- **WHEN** a sales report is requested after the July change
- **THEN** commission uses the tier rows stored at request time
- **AND** January sales are recomputed with the July tier percentages
