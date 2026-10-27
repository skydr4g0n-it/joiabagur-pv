# Spec Delta

## ADDED Requirements

### Requirement: System products stay out of the jewelry catalog
The system SHALL store products with a system-product kind. Those products SHALL be excluded from the product catalog, product search, Excel import, and image recognition. They SHALL NOT have inventory rows. Deleting or editing them through the jewelry product screens SHALL be rejected. Sales of system products SHALL occur only through the gift card issuance API, not through bulk checkout.

#### Scenario: Catalog omits the gift-card product
- **GIVEN** the gift-card system product exists
- **WHEN** an administrator requests GET /api/products
- **THEN** the response does not include that product

#### Scenario: Search does not return the gift-card product
- **GIVEN** the gift-card system product has SKU `SYS-GIFT-CARD`
- **WHEN** an administrator searches products with query `SYS-GIFT-CARD`
- **THEN** the system returns an empty array

#### Scenario: Excel import does not create a system product
- **GIVEN** an import workbook contains a row whose SKU is `SYS-GIFT-CARD`
- **WHEN** an administrator imports the workbook
- **THEN** that row is reported as an error
- **AND** the system product row is unchanged

#### Scenario: Recognition ignores the system product
- **GIVEN** a recognition request for a POS
- **WHEN** the system builds the candidate product set
- **THEN** the set contains no system product
