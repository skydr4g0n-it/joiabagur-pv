## ADDED Requirements

### Requirement: Calendar-Year Commission Per Sale From Pre-Sale YTD

The system SHALL calculate POS commission using the commission tier that applies to return-adjusted year-to-date (YTD) sales **immediately before** each sale. The calendar year is UTC (1 January–31 December). YTD resets at the start of each UTC calendar year. Each sale’s commission SHALL be the full sale amount (`Price × Quantity`) multiplied by that tier’s `CommissionPercent` (no marginal/progressive split within a single sale). Tiers are the currently configured tiers for the POS.

#### Scenario: Entire sale at tier from YTD before sale

- **GIVEN** a POS with tiers: 0–20000 at 20%, 20001–100000 at 30%, 100001+ at 40%
- **AND** return-adjusted YTD before the sale is 15000 EUR in that UTC calendar year
- **WHEN** a sale of 10000 EUR occurs
- **THEN** commission for that sale is 2000 EUR (10000 × 20%)
- **AND** the sale is not split across 20% and 30%

#### Scenario: Sale that would cross threshold still uses prior tier

- **GIVEN** the same tiers as above
- **AND** return-adjusted YTD before the sale is 19500 EUR
- **WHEN** a sale of 10000 EUR occurs in the same year
- **THEN** commission is 2000 EUR (10000 × 20%)

#### Scenario: Return reduces YTD for later sales

- **GIVEN** a POS with tiers starting at 0–20000 at 20%
- **AND** a sale of 18000 EUR on 2026-03-01
- **AND** a return of 5000 EUR on 2026-03-15 for that POS (same year)
- **WHEN** a sale of 10000 EUR occurs on 2026-03-20
- **THEN** return-adjusted YTD before the March 20 sale is 13000 EUR
- **AND** commission for the March 20 sale is 2000 EUR (10000 × 20%)

#### Scenario: Return event ordering uses ReturnDate

- **GIVEN** sales and returns for a POS in the same UTC year
- **WHEN** commission YTD is computed
- **THEN** return amounts use `ReturnDate` (UTC) and subtract `ReturnSale.Quantity × ReturnSale.UnitPrice`
- **AND** sale amounts use `SaleDate` (UTC) and add `Price × Quantity`

#### Scenario: Calendar year reset

- **GIVEN** a POS with 50000 EUR return-adjusted YTD in year Y
- **WHEN** the first sale of year Y+1 is 10000 EUR
- **THEN** YTD before that sale is 0
- **AND** commission uses the first tier rate on the full 10000 EUR

#### Scenario: Open-ended top tier

- **GIVEN** a POS whose last tier is MinAmountInclusive = 100001 with MaxAmountInclusive null at 40%
- **AND** return-adjusted YTD before the sale is 150000 EUR
- **WHEN** a sale of 5000 EUR occurs
- **THEN** commission is 2000 EUR (5000 × 40%)

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
