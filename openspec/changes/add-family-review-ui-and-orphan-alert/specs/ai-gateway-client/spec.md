## ADDED Requirements

### Requirement: Typed gateway client exposes the family audit

The backend SHALL extend the typed `jbg-ai` client with one operation for auditing persisted families against `POST /v1/families/audit`, added by the change that first calls it. The client MUST serialize and deserialize the frozen contract using `snake_case` property names on the wire.

The client MUST send the `(product, family)` pairs that already carry a human verdict, because the service holds none of its own and would otherwise report judgements the administrator has already made. Assembling that set from the backend's own store is the client's responsibility, not the service's.

The client MUST report the flagged members and the candidates as received and MUST NOT filter, reorder or truncate either list: deciding what deserves attention belongs to the administrator, not to the transport. The margin of a flagged member and the similarity, worst-sibling similarity, data origin and purity count of a candidate MUST all survive the mapping, because they are what the reviewer judges by.

The client MUST NOT invoke this operation on behalf of an operator: the calling scope is the administrator that the .NET controller has already authorised. This operation MUST NOT write to the catalogue; recording a verdict is a separate backend operation that does not pass through this client.

#### Scenario: Both lists are surfaced without truncation

- **WHEN** the service returns flagged members and candidates
- **THEN** the client returns both lists in full and in the order received
- **AND** it does not drop a candidate for its data origin or its purity count

#### Scenario: The evidence a reviewer judges by survives the mapping

- **WHEN** the service returns a candidate with its similarity, the target family's worst-sibling similarity, the margin between them, its data origin and its purity count
- **THEN** all of those values are present on the mapped result
- **AND** a flagged member keeps its margin and the identity of the product that beat its worst sibling

#### Scenario: Pairs already judged travel with the request

- **WHEN** the backend holds verdicts for a set of `(product, family)` pairs and the audit is requested
- **THEN** the client includes those pairs in the request
- **AND** the service is not expected to know them by any other means

#### Scenario: Wire names follow the frozen contract

- **WHEN** the client serializes a family audit request
- **THEN** the property names on the wire are `snake_case`
- **AND** the payload validates against the committed contract

### Requirement: Family audit failures are distinguishable by the caller

The backend SHALL let the caller of the audit tell apart a route that is not implemented, a dependency the service cannot reach, and a request the contract cannot accept. An audit that fails MUST NOT be reported as an audit that found nothing: a reviewer told "there is nothing to review" when the service never answered would conclude the catalogue is clean. An empty response body MUST be treated as a failure and never as a result, because on this route "empty" and "clean catalogue" are indistinguishable to the screen and only one of them is true.

A request the contract cannot accept MUST be refused **before it is sent**, which is a stronger guarantee than telling a refusal apart afterwards. A refusal the service itself issues surfaces as an unavailable service carrying the status code: the translation from HTTP status to exception is shared by every route on this client, and narrowing it is not this change's to make.

A failed audit MUST leave no verdict, no family and no membership modified.

#### Scenario: An unreachable dependency is not an empty audit

- **WHEN** the service cannot reach the index and the audit fails
- **THEN** the caller receives a failure distinguishable from a successful audit with no findings
- **AND** no empty list of flagged members or candidates is returned as though it were a result

#### Scenario: An invalid request is refused before it is sent

- **WHEN** the request carries a scope or a candidate cap the frozen contract cannot accept
- **THEN** the client refuses it without calling the service
- **AND** the caller can tell that refusal from an unavailable service and from a route that is not implemented

#### Scenario: An empty body is a failure, not an empty audit

- **WHEN** the service answers successfully with no body
- **THEN** the caller receives a failure
- **AND** no empty list of flagged members or candidates is returned as though it were a result

#### Scenario: A failed audit changes nothing

- **WHEN** an audit fails for any reason
- **THEN** no verdict is created or modified
- **AND** no family or membership is created, modified or removed
