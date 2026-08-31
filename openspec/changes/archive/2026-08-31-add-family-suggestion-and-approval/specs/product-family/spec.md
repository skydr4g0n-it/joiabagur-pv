## ADDED Requirements

### Requirement: A family approved from an assisted suggestion records its approver

The system SHALL provide a write path that creates a family from an approved suggestion, recording its origin as approved from an assisted suggestion together with the approving administrator and the instant of approval. This exercises the storage the family schema reserved and left unwritten: until this change, origin was always recorded as manual and the approval fields had no write path at all.

The assisted write path MUST reuse the existing family creation and membership replacement, and MUST NOT bypass them with direct SQL. Those operations are the only ones that keep the indexing feed's watermark coherent, and they keep it coherent in two directions: **creating** a family moves the cursor through the family's own `UpdatedAt`, which the feed joins on for current members, while **replacing** a membership stamps `Product.UpdatedAt` on the products entering and leaving, which stop joining that row and would otherwise drop out of the cursor. A direct `INSERT` does neither, and the feed then never emits those products — a failure that produces no error anywhere.

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

#### Scenario: An assisted family is visible to an incremental catalog pull

- **WHEN** a family is created from an approved suggestion and the catalog feed is pulled incrementally from a cursor earlier than the approval
- **THEN** the feed emits every product that entered the family
- **AND** it emits no product that entered nothing

#### Scenario: A conflicting product is reported without leaving a partial family

- **WHEN** an approved batch names a product that already belongs to another family
- **THEN** the response identifies which products conflict and which family currently holds each of them
- **AND** no member of the contested family is created, modified or removed
- **AND** the other families of the batch are still created, because one contested product must not cost an administrator the rest of the approvals

#### Scenario: Approving the same suggestion twice writes nothing the second time

- **WHEN** an administrator approves a suggestion whose products already belong to the family a previous approval created
- **THEN** the second approval creates no family and no membership
- **AND** it is reported as a conflict rather than absorbed in silence, because approving the same batch twice is a mistake worth seeing
- **AND** no member product's `UpdatedAt` changes
