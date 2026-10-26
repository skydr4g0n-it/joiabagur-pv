## ADDED Requirements

### Requirement: Commission Tier Configuration Per Point Of Sale

The system SHALL allow administrators to define and replace the ordered list of annual sales commission tiers for a point of sale via nested APIs under that POS. Operators SHALL NOT read or modify tiers through these APIs.

#### Scenario: Administrator replaces commission tiers

- **GIVEN** an authenticated administrator and an existing point of sale
- **WHEN** the administrator sends `PUT /api/point-of-sales/{id}/commission-tiers` with a valid ordered list of tiers (min inclusive, max inclusive or null, commission percent)
- **THEN** the system replaces all existing tiers for that POS with the submitted list
- **AND** returns the persisted tiers

#### Scenario: Administrator retrieves commission tiers

- **GIVEN** an authenticated administrator and a POS with configured tiers
- **WHEN** the administrator requests `GET /api/point-of-sales/{id}/commission-tiers`
- **THEN** the system returns the ordered list of tiers for that POS

#### Scenario: Clear all tiers

- **GIVEN** an authenticated administrator and a POS with existing tiers
- **WHEN** the administrator sends `PUT` with an empty list
- **THEN** the system stores no tiers for that POS
- **AND** commission for that POS is treated as 0%

#### Scenario: Invalid overlapping or gapped ranges rejected

- **GIVEN** an authenticated administrator
- **WHEN** the submitted tiers overlap, leave a gap, do not start at 0, or have more than one open-ended max
- **THEN** the system returns 400 Bad Request
- **AND** does not modify existing tiers

#### Scenario: Operator cannot modify commission tiers

- **GIVEN** an authenticated operator
- **WHEN** the operator attempts `PUT /api/point-of-sales/{id}/commission-tiers`
- **THEN** the system returns 403 Forbidden
- **AND** existing tiers are unchanged

#### Scenario: Operator cannot read commission tiers

- **GIVEN** an authenticated operator
- **WHEN** the operator attempts `GET /api/point-of-sales/{id}/commission-tiers`
- **THEN** the system returns 403 Forbidden

### Requirement: Commission Tier Admin UI

The system SHALL provide an administrator-only UI on the points-of-sale management page to view and edit commission tiers for a selected POS. Min and max amount inputs SHALL accept whole euros in the UI while persisting decimal values via the API.

#### Scenario: Administrator opens commission configuration

- **GIVEN** an administrator on `/points-of-sale`
- **WHEN** the administrator chooses the action to manage commissions for a POS
- **THEN** the UI displays the current tiers (min, max, percent) and allows add, edit, remove, and save
- **AND** on successful save the tiers are persisted via the commission-tiers API

#### Scenario: Operator does not see commission configuration

- **GIVEN** an operator on `/points-of-sale`
- **WHEN** the page is displayed
- **THEN** no action to manage commission tiers is available
