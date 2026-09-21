## MODIFIED Requirements

### Requirement: A failure is returned as an observation carrying a closed-vocabulary cause, never as an exception
A tool SHALL NOT let an exception escape to its caller, and a failure MUST be returned as an observation marked failed and carrying a cause drawn from a closed vocabulary of codes.

An exception would kill the consuming loop instead of costing it one turn, and a generic error leaves the model blind where an informative one lets it reformulate. The cause travels as a code and never as prose, by the same rule the rule-derived warnings already follow: the Spanish belongs to whoever presents it.

The closed vocabulary SHALL carry **five** causes: an argument that did not satisfy the tool's own schema, a reference the index does not hold, a reference that exists and cannot anchor the tool, a dependency that is unavailable, and a call the consumer refused because the request's tool budget is spent. The fifth is emitted by the consumer and never by the tool itself, and a tool whose call carries it MUST NOT have touched any port.

The budget cause exists because the alternative leaves the model blind in the one situation where it can still act usefully. A consumer that silently dropped the calls it could not afford would return a turn with fewer observations than calls requested, and the model would have no way to tell that from a tool that failed. Naming the cause lets it spend its remaining turn, if any, on what matters.

#### Scenario: A dependency failure comes back as data
- **WHEN** the dependency a tool consults is unavailable and the tool is invoked
- **THEN** no exception reaches the caller
- **AND** a failed observation is returned carrying the cause of the failure

#### Scenario: An unknown piece reference is an observation and not an error
- **WHEN** a piece-anchored tool is invoked with a SKU that the index does not hold
- **THEN** a failed observation is returned carrying the unknown-reference cause

#### Scenario: A call refused for want of budget is an observation that touched nothing
- **GIVEN** a consumer whose tool budget for the request is spent
- **WHEN** it declines to execute a requested call
- **THEN** a failed observation is returned carrying the budget-exhausted cause
- **AND** no port was touched for that call

#### Scenario: Every cause a consumer can observe belongs to the declared vocabulary
- **WHEN** the set of causes any failed observation can carry is enumerated
- **THEN** it is exactly the declared five
- **AND** no cause is prose

### Requirement: The registry is not wired to any route and the frozen contract does not move
This capability SHALL NOT add, remove or modify any route of the service, and the frozen OpenAPI snapshot MUST remain unchanged.

The consumer of this registry is the agent loop, which serves `POST /v1/assist/agent` from the `sales-assistant-agent` capability: that route, and the movement of the published contract it brought, belong to that capability and not to this one. The registry stays a library that declares no route and no budget of its own, so that exposing a surface remains a decision taken where there is a decision behind it — and the separation is what lets either layer change without the other noticing.

#### Scenario: The snapshot is untouched
- **WHEN** the committed OpenAPI snapshot is compared against the one the service generates
- **THEN** they are identical

#### Scenario: Sale assistance is unaffected
- **WHEN** a sale-assistance request is served in any of its three modes
- **THEN** the response is the one the assistance layer already produced, with no field added and none changed
