## ADDED Requirements

### Requirement: Typed gateway client exposes family suggestion

The backend SHALL extend the typed `jbg-ai` client with one operation for assisted family grouping against `POST /v1/families/suggest`, added by this change because this is the change that first calls it. The client MUST serialize and deserialize the frozen contract using `snake_case` property names on the wire. `variant_label` MUST map to a nullable value, because the contract guarantees an explicit null rather than an absent field for a member with no distinguishing token. The client MUST report the proposals and the rejected groups as received and MUST NOT filter, reorder or truncate either list: deciding what to accept belongs to the administrator, not to the transport.

The client MUST NOT invoke this operation on behalf of an operator: the calling scope is the administrator that the .NET controller has already authorised.

#### Scenario: Proposals are surfaced without truncation

- **WHEN** the service returns a set of proposals and a set of rejected groups
- **THEN** the client returns both lists in full and in the order received
- **AND** it does not drop members flagged for review

#### Scenario: A member with no variant maps to an explicit null

- **WHEN** the service returns a member whose `variant_label` is null
- **THEN** the client maps it to a nullable value rather than to an empty string
- **AND** the distinction between "no variant" and "empty variant" is preserved

#### Scenario: Wire names follow the frozen contract

- **WHEN** the client serializes a family suggestion request
- **THEN** the property names on the wire are `snake_case`
- **AND** the payload validates against the committed contract

### Requirement: Family suggestion failures are distinguishable by the caller

The gateway client SHALL translate the failure modes of the family suggestion route onto the same typed errors the rest of the surface already uses, so that the controller can branch without inspecting transport details: a contracted-but-unimplemented route MUST surface as the not-implemented error, a timeout, transport failure, open circuit or server error MUST surface as the unavailable error, and rejected credentials MUST surface as the configuration error.

Family suggestion MUST NOT have a lexical or degraded fallback. Unlike search, which can drop to the lexical index, there is no safe degraded answer here: proposing groupings without the index would mean inventing catalogue structure.

#### Scenario: An unimplemented route is distinguishable from an unavailable one

- **WHEN** the service answers the family suggestion route with 501
- **THEN** the client raises the not-implemented error
- **AND** a timeout or a server error raises the unavailable error instead

#### Scenario: No degraded proposal is produced

- **WHEN** the family suggestion call fails for any reason
- **THEN** the client returns no proposals at all
- **AND** it does not synthesise a fallback grouping
