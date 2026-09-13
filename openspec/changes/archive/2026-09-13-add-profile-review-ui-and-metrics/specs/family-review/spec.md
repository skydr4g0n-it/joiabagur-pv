## ADDED Requirements

### Requirement: A family can be created from the review screen

The system SHALL allow an administrator to create a variant family from the review screen, naming it
and assigning its members with their variant labels in the same operation. The created family MUST
record that its origin is a person rather than a proposal.

Listing and dissolving families is not enough, and the gap has a measured population behind it. The
audit nominates an unassigned product by its margin relative to a target family, so a product whose
piece type has **no family at all** cannot be nominated: there is nothing to compute a margin
against. Seven products of one such piece type and two plain wedding bands are in exactly that
position — the two degenerate roots the suggestion pass delegated to a person — and no amount of
tuning the audit reaches them, because the obstacle is the absence of a target and not the value of a
threshold.

#### Scenario: A family is created with its members

- **WHEN** an administrator creates a family from the review screen, giving it a name and selecting products with their variant labels
- **THEN** the family is persisted with those members and their labels
- **AND** its origin records that a person created it

#### Scenario: The created family absorbs its members from the orphan list

- **GIVEN** products that belonged to no family
- **WHEN** they are made members of a newly created family
- **THEN** they no longer appear as unassigned products

#### Scenario: A piece type with no family can receive its first one

- **GIVEN** products of a piece type for which no family exists, so the audit can nominate none of them
- **WHEN** an administrator creates a family for that piece type from the review screen
- **THEN** the family is persisted and those products become its members

#### Scenario: Creating a family is restricted to administrators

- **WHEN** a user with the operator role attempts to create a family
- **THEN** the response is HTTP 403 and no family is created

### Requirement: A reviewer can work the family queue without the mouse

The system SHALL provide keyboard operation for confirming, rejecting and advancing through the
family review queue, sufficient to traverse a queue end to end without a pointing device. The
shortcuts MUST NOT fire while focus is inside a text-editing field.

This was recorded as delivered once and was not: the screen carries no key handler at all. The proof
that matters is a queue worked end to end with them, not that a handler is attached, and the same
operation is required of the profile review queue — so a reviewer moving between the two screens
meets one set of keys rather than two.

#### Scenario: A family queue is traversed by keyboard

- **WHEN** a reviewer uses the keyboard to confirm, reject and advance
- **THEN** the queue can be traversed from first to last item without using the mouse

#### Scenario: Editing a variant label does not trigger a shortcut

- **GIVEN** focus is inside the field that edits a member's variant label
- **WHEN** the reviewer types a character bound to a shortcut
- **THEN** the character is entered into the field and no review action is triggered
