# Spec Delta

## ADDED Requirements

### Requirement: Bulk checkout applies gift cards
`POST /api/sales/bulk` SHALL accept zero or more gift card codes together with product lines. All lines SHALL still share one point of sale and one payment method. Jewelry lines SHALL create inventory movements. Coverage and card balances SHALL commit in the same transaction as the sales. A failed line SHALL roll back sales, movements, and card changes.

#### Scenario: Gift card checkout rolls back together
- **GIVEN** a bulk request that applies a valid gift card and includes one line with no stock
- **WHEN** the user submits the checkout
- **THEN** the system persists no sale, no inventory movement, and no coverage
- **AND** the card spendable balance is unchanged

#### Scenario: Sale history exposes gift-card coverage

- **GIVEN** a product sale with 100.00 EUR of gift-card coverage
- **WHEN** a user loads sales history including that sale
- **THEN** the sale shows its catalog total
- **AND** shows gift-card coverage of 100.00 EUR

#### Scenario: Mixed payment methods stay rejected
- **GIVEN** a bulk request that applies a gift card
- **AND** two product lines with different payment method ids
- **WHEN** the user submits the checkout
- **THEN** the system returns 400 Bad Request
- **AND** persists nothing

### Requirement: System product sales only through gift card issuance
`POST /api/sales/bulk` SHALL NOT create a sale for a system product. The system gift-card product SHALL be sold only through `POST /api/gift-cards`.

#### Scenario: Reject bulk checkout of the system gift-card product
- **GIVEN** a bulk request whose lines include the system gift-card product
- **WHEN** the user submits the checkout
- **THEN** the system returns 400 Bad Request
- **AND** persists no sale or inventory movement
