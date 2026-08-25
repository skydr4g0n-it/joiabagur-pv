## ADDED Requirements

### Requirement: Membership changes stamp the catalog watermark of entering and leaving products
When family membership is replaced with a list that is not identical to the current members, labels and order, the system SHALL stamp `Product.UpdatedAt` of every product that **enters** the family and every product that **leaves** it, so that an indexing feed whose cursor is `Product.UpdatedAt` can see both. Stamping MUST happen by loading those products and marking them modified (or equivalent) so the existing `SaveChangesAsync` interceptor writes `UpdatedAt`; deleting a membership row MUST NOT be relied on to touch `Product`. A reorder or variant-label change that keeps the same product identifiers MUST stamp those products, because the denormalised variant in the index changed. Declaring an identical list MUST still write nothing, including no `Product` row. Updating only the family's name or description MUST NOT stamp member products: the family's own `UpdatedAt` is the watermark the feed joins on, and membership rows stay untouched.

#### Scenario: A product that leaves a family has its UpdatedAt stamped
- **GIVEN** a family of three members
- **WHEN** an administrator declares a list that omits one of them
- **THEN** the omitted product no longer belongs to the family
- **AND** that product's `UpdatedAt` is later than it was before the replace

#### Scenario: A product that enters a family has its UpdatedAt stamped
- **GIVEN** a family and a product that belongs to no family
- **WHEN** an administrator declares a list that includes that product
- **THEN** the product belongs to the family
- **AND** that product's `UpdatedAt` is later than it was before the replace

#### Scenario: A reorder or label change stamps the products that stayed
- **GIVEN** a family whose two members are products A then B with labels S and M
- **WHEN** an administrator declares the same two products in a different order or with swapped labels
- **THEN** the operation succeeds
- **AND** both products' `UpdatedAt` values are later than they were before the replace

#### Scenario: An identical list still writes nothing, including Product
- **GIVEN** a family whose current members, labels and order are I
- **WHEN** an administrator declares exactly I
- **THEN** the operation succeeds and returns the same family
- **AND** no membership row is rewritten
- **AND** no member product's `UpdatedAt` changes

#### Scenario: A metadata rename does not stamp member products
- **GIVEN** a family with members
- **WHEN** an administrator updates only the family's name or description
- **THEN** the new metadata is persisted
- **AND** membership rows are left untouched
- **AND** member products' `UpdatedAt` values are left untouched
- **AND** the family's own `UpdatedAt` is later than it was before the update
