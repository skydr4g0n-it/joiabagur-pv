## ADDED Requirements

### Requirement: A family approved from an assisted suggestion records its approver

The system SHALL provide a write path that creates a family from an approved suggestion, recording its origin as approved from an assisted suggestion together with the approving administrator and the instant of approval. This exercises the storage the family schema reserved and left unwritten: until this change, origin was always recorded as manual and the approval fields had no write path at all.

The assisted write path MUST reuse the existing family creation and membership replacement, and MUST NOT bypass them with direct SQL. Bypassing them would skip the stamping of `Product.UpdatedAt` on entering and leaving products, and an indexing feed whose cursor is that watermark would never emit them — a failure that produces no error anywhere.

Manual creation MUST continue to record manual origin with empty approval fields, so that the two paths remain distinguishable after the fact.

#### Scenario: An approved suggestion records assisted origin, approver and instant

- **WHEN** an administrator approves a suggested family
- **THEN** the family is persisted with its members in the declared order and with their variant labels
- **AND** its origin is recorded as approved from an assisted suggestion
- **AND** the approving user and the approval instant are both recorded

#### Scenario: Manual creation is still distinguishable afterwards

- **WHEN** a family is created through the manual family endpoints after assisted families exist
- **THEN** its origin is recorded as manual
- **AND** its approving user and approval instant remain empty

#### Scenario: The assisted path stamps the catalog watermark like the manual one

- **WHEN** a family is created from an approved suggestion
- **THEN** every product that entered the family has its `UpdatedAt` stamped
- **AND** an indexing feed whose cursor predates the approval emits exactly those products

#### Scenario: A conflicting product is reported without leaving a partial family

- **WHEN** an approved suggestion names a product that already belongs to another family
- **THEN** the request is rejected with 409 Conflict
- **AND** the response identifies which products conflict and which family currently holds each of them
- **AND** no member of the target family is created, modified or removed

#### Scenario: Approving the same suggestion twice writes nothing the second time

- **WHEN** an administrator approves a suggestion whose products already belong to the family a previous approval created
- **THEN** the second approval creates no family and no membership
- **AND** it is reported as a conflict rather than absorbed in silence, because approving the same batch twice is a mistake worth seeing
- **AND** no member product's `UpdatedAt` changes
