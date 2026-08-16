## ADDED Requirements

### Requirement: Product families are an editable business entity

The system SHALL persist product families as first-class entities carrying a name and an optional description, independent of any AI-generated value. A family MUST remain editable after creation without re-running any inference, because the grouping is business data a person answers for. Families are distinct from collections: a collection groups products by editorial criteria and a product may belong to none or to one of many unrelated collections, whereas a family groups the same piece in several variants and a product belongs to at most one.

#### Scenario: A family is created with a name and a description

- **WHEN** an administrator creates a family with a name and a description
- **THEN** the family is persisted with a generated identifier and audit timestamps
- **AND** it is retrievable by that identifier

#### Scenario: A family's name and description can be corrected afterwards

- **WHEN** an administrator updates the name or description of an existing family
- **THEN** the new values are persisted
- **AND** the family's members are left untouched

#### Scenario: Two families may carry the same name

- **WHEN** a second family is created with a name that another family already uses
- **THEN** the creation succeeds
- **AND** both families remain distinguishable by their identifiers

### Requirement: A product belongs to at most one family, enforced by the database

The system SHALL enforce single family membership with a unique database index on the member's product, not with an application-level check. An application check leaves a race open between concurrent writers and, more importantly, a second membership row produces no error anywhere: it would surface downstream as two family identifiers emitted for one product and as duplicated documents in the vector index.

#### Scenario: A second membership for the same product is rejected

- **WHEN** a product that already belongs to a family is declared as a member of a different family
- **THEN** the write fails on the database's uniqueness constraint
- **AND** both families are left unchanged

#### Scenario: The conflict names the product and the family that already holds it

- **WHEN** an administrator declares members that include a product belonging to another family
- **THEN** the request is rejected with 409 Conflict
- **AND** the response identifies which products conflict and which family currently holds each of them
- **AND** no member of the target family is created, modified or removed

#### Scenario: A concurrent write does not surface as a server error

- **WHEN** two administrators simultaneously assign the same product to two different families and one write loses the race
- **THEN** the losing request is reported as a conflict rather than as an unhandled failure
- **AND** the winning assignment is persisted intact

### Requirement: Family membership is declared as a complete list

The system SHALL replace a family's entire membership from a single declaration. Products present in the declaration and absent from the family are added, products absent from the declaration and present in the family are removed, and each member's position within the family is derived from its position in the declared list, which makes gaps and duplicated positions impossible to express. Declaring the same list again MUST NOT rewrite any row, so that repeating the operation creates no downstream reindexing work.

#### Scenario: Members are persisted in the order declared

- **WHEN** an administrator declares three products as members of a family in a given order
- **THEN** the three memberships are persisted
- **AND** each member's position reflects its place in the declared list
- **AND** reading the family returns the members in that same order

#### Scenario: Omitting a member removes it without dissolving the family

- **WHEN** an administrator declares a list that omits one of a family's three current members
- **THEN** that product no longer belongs to the family
- **AND** the family still exists with its two remaining members
- **AND** the remaining members hold consecutive positions with no gap
- **AND** the removed product belongs to no family

#### Scenario: An empty declaration leaves the family without members

- **WHEN** an administrator declares an empty list of members for a family
- **THEN** the family still exists and has no members
- **AND** every former member belongs to no family and is free to be assigned elsewhere

#### Scenario: Members can be reordered

- **WHEN** an administrator declares the family's current members in a different order
- **THEN** the operation succeeds
- **AND** reading the family afterwards returns exactly the declared order
- **AND** the uniqueness of position within the family still holds

#### Scenario: Declaring an identical list writes nothing

- **WHEN** an administrator declares a list identical to the family's current members, labels and order
- **THEN** the operation succeeds and returns the same family
- **AND** no membership row is rewritten

#### Scenario: A product declared twice in one request is rejected

- **WHEN** a declaration names the same product more than once
- **THEN** the request is rejected with 400 Bad Request before any database write is attempted

### Requirement: Variant labels distinguish members within their family

The system SHALL store an optional variant label per member — the size, colour or finish that tells one variant from another — and SHALL reject two members of the same family carrying the same label. The label is optional because a member whose variant has not been determined yet is a legitimate state that downstream rule-based warnings are meant to report, not a defect to block on. Two labelled members that cannot be told apart, by contrast, defeat the purpose of the family.

#### Scenario: Members without a label coexist in one family

- **WHEN** two members of the same family are persisted with no variant label
- **THEN** both are stored without error

#### Scenario: A duplicate label within a family is rejected

- **WHEN** a declaration gives two members of the same family the same variant label
- **THEN** the request is rejected with 400 Bad Request
- **AND** the family's members are left unchanged

#### Scenario: The same label may be reused in a different family

- **WHEN** two members of two different families carry the same variant label
- **THEN** both are stored without error

### Requirement: A product's family is retrievable, and an orphan is distinguishable from a missing product

The system SHALL expose the family a product belongs to, together with all its sibling members in their declared order and with each sibling's variant label. A product that exists and belongs to no family MUST produce a response distinct from a product that does not exist, so that a caller can tell a quality incidence from a bad identifier without inspecting the body.

#### Scenario: Retrieving the family of a member product

- **WHEN** a caller requests the family of a product that belongs to one
- **THEN** the response returns 200 with the family, its name and its description
- **AND** the response includes every member of the family, the queried product among them
- **AND** the members appear in their declared order, each with its variant label

#### Scenario: Retrieving the family of an orphan product

- **WHEN** a caller requests the family of a product that exists and belongs to no family
- **THEN** the response is 204 No Content

#### Scenario: Retrieving the family of a product that does not exist

- **WHEN** a caller requests the family of an identifier that matches no product
- **THEN** the response is 404 Not Found

### Requirement: Writing families is restricted to administrators, reading is not

The system SHALL restrict family creation, metadata editing and membership declaration to authenticated administrators, in line with the rest of catalogue administration. Reading a family, whether directly or through one of its products, SHALL be available to any authenticated user and MUST NOT be filtered by the caller's assigned points of sale: family membership is a fact about the catalogue and not about stock, and applying inventory visibility here would make the sibling list depend on where a piece happens to be held.

#### Scenario: An operator cannot create or modify a family

- **WHEN** a user with the operator role attempts to create a family, edit its metadata or declare its members
- **THEN** the request is rejected with 403 Forbidden
- **AND** no family or membership is created, modified or removed

#### Scenario: An unauthenticated caller is rejected

- **WHEN** an unauthenticated caller invokes any family endpoint
- **THEN** the request is rejected with 401 Unauthorized

#### Scenario: An operator can read the family of a product

- **WHEN** an authenticated operator requests the family of a product
- **THEN** the response returns the family with all of its members
- **AND** the member list is the same one an administrator would receive, regardless of which points of sale the operator is assigned to

### Requirement: Family storage records how the family came to exist

The system SHALL record, on every family, whether it was created manually or approved from an assisted suggestion, together with the user who approved it and the moment of approval. The approval fields MUST be nullable and MUST be left empty by manual creation, so that a family created by hand does not have to invent a reviewer. This storage exists from the first migration because the change that will populate it has no migration turn of its own.

#### Scenario: A manually created family records manual origin

- **WHEN** an administrator creates a family through the family endpoints
- **THEN** the family's origin is recorded as manual
- **AND** the approving user and the approval instant are left empty

#### Scenario: Approval fields accept no value

- **WHEN** a family is persisted without an approving user or an approval instant
- **THEN** the write succeeds and both remain empty

### Requirement: The family schema preserves what would otherwise fail silently

The system SHALL declare explicitly, in the migration, every constraint whose absence produces wrong behaviour without producing an error: the uniqueness of a product across all families, the uniqueness of position and of variant label within a family, and the deletion rules on both foreign keys. Deleting a family MUST cascade into its members, which have no life of their own, while deleting a product or a user MUST be restricted, because the framework default for a required relationship is a cascade that would destroy curation work — and products are deactivated rather than deleted in this system.

#### Scenario: Product uniqueness is enforced by a unique index

- **WHEN** the migration is applied to a clean database and the catalogue is inspected
- **THEN** a unique index exists over the membership's product column

#### Scenario: Position and variant label are unique within a family

- **WHEN** the migration is applied to a clean database and the catalogue is inspected
- **THEN** a unique index exists over family and position
- **AND** a unique index exists over family and variant label

#### Scenario: Deleting a family removes its members

- **WHEN** the deletion rule of the foreign key from membership to family is inspected
- **THEN** it is a cascade

#### Scenario: Deleting a product is restricted

- **WHEN** the deletion rule of the foreign key from membership to product is inspected
- **THEN** it is restricted
- **AND** the same holds for the foreign key from family to the approving user

#### Scenario: Model and migrations agree

- **WHEN** the entity model is compared against the migrations snapshot
- **THEN** there are no pending differences
