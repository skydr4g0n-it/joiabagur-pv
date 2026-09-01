## ADDED Requirements

### Requirement: Families are enumerable through a paginated listing

The system SHALL expose a paginated listing of families to administrators, returning at most 50 per page, and MUST accept narrowing by how the family came to exist, by the piece type its members share, and by whether it holds members flagged by a review audit.

Retrieval by identifier is not enough for review: a reviewer working through the catalogue's families has no identifier to start from, and no other operation produces the set.

#### Scenario: Families are returned a page at a time

- **WHEN** an administrator requests the family listing
- **THEN** the response contains at most 50 families
- **AND** it reports the total number of families matching the request
- **AND** requesting the next page returns the following families with no family repeated or skipped

#### Scenario: The listing narrows by how the family came to exist

- **WHEN** an administrator requests only the families approved from an assisted suggestion
- **THEN** every family returned records assisted-approval origin
- **AND** manually created families are absent

#### Scenario: The listing narrows to families holding flagged members

- **WHEN** an administrator requests only the families that hold a member flagged by a review audit
- **THEN** every family returned holds at least one such member
- **AND** families whose members are all unflagged are absent

#### Scenario: An operator cannot list families

- **WHEN** a user with the operator role requests the family listing
- **THEN** the request is rejected with 403 Forbidden

### Requirement: A family can be dissolved, not only emptied

The system SHALL allow an administrator to delete a family outright. Its members MUST cease to belong to it and become free to be assigned elsewhere, and the catalog watermark of every departing product MUST be stamped so that an incremental indexing pull emits them.

Emptying a family through a membership declaration is not equivalent and MUST NOT be the only route: it leaves a family with no members, which is a legitimate state for a family being built and a meaningless one for a family that was wrong.

Deleting a family that does not exist MUST be distinguishable from deleting one that does.

#### Scenario: Dissolving a family frees its members

- **WHEN** an administrator deletes a family that holds three members
- **THEN** the family no longer exists
- **AND** none of the three products belongs to any family
- **AND** each of them may afterwards be declared a member of another family

#### Scenario: Departing products are visible to an incremental catalog pull

- **WHEN** a family is deleted and the catalog feed is pulled incrementally from a cursor earlier than the deletion
- **THEN** the feed emits exactly the products that belonged to it
- **AND** no additional product is emitted

#### Scenario: Deleting an absent family is reported as absent

- **WHEN** an administrator deletes a family that does not exist
- **THEN** the request is rejected with 404 Not Found
- **AND** no other family is affected

#### Scenario: An operator cannot dissolve a family

- **WHEN** a user with the operator role deletes a family
- **THEN** the request is rejected with 403 Forbidden
- **AND** the family and its members are left unchanged
