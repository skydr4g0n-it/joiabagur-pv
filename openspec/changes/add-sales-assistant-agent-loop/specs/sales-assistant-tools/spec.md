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
