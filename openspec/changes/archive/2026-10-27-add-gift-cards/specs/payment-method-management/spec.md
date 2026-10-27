# Spec Delta

## MODIFIED Requirements

### Requirement: Seed Data Management

The system SHALL provide predefined payment methods on initialization, including the system method `GIFT_CARD`. `GIFT_CARD` SHALL be assigned and active on every point of sale, SHALL be hidden from ordinary sale payment choices, and SHALL NOT be deactivated.

#### Scenario: Automatic seed data

- **WHEN** database is initialized or migrated
- **THEN** system creates predefined payment methods if they don't exist
- **AND** sets appropriate names and descriptions in Spanish
- **AND** marks them as active by default
- **AND** creates `GIFT_CARD` when it is missing
- **AND** ensures `GIFT_CARD` is actively assigned to every point of sale

#### Scenario: Seed data idempotency

- **WHEN** seed data runs multiple times
- **THEN** system doesn't create duplicates
- **AND** doesn't modify existing payment method data
- **AND** only adds missing predefined methods
- **AND** does not rename or reprice an existing `GIFT_CARD` method

#### Scenario: Ordinary sale choices hide the gift-card method
- **GIVEN** POS A has cash and `GIFT_CARD` assigned
- **WHEN** the sales form loads payment methods for POS A
- **THEN** cash is selectable
- **AND** `GIFT_CARD` is not selectable

#### Scenario: Reject deactivation of the gift-card method
- **GIVEN** `GIFT_CARD` is assigned to a POS
- **WHEN** an admin deactivates that assignment or the method
- **THEN** the system rejects the request with 400 Bad Request
- **AND** the assignment stays active
