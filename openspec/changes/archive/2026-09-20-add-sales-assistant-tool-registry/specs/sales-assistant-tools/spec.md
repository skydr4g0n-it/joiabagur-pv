## ADDED Requirements

### Requirement: The sale assistant's tools are a registry of six read-only tools whose names are frozen
The service SHALL expose a registry holding exactly six tools — `buscar_catalogo`, `buscar_sustitutos`, `listar_familia`, `consultar_conocimiento`, `consultar_disponibilidad` and `pedir_aclaracion` — and the set of names SHALL be a declared constant rather than whatever the construction happened to assemble.

The count is not what the project evaluates of the agent; what it evaluates is the loop, the hard budget, the read-only invariant and the partial flag. The frozen set exists so that a tool added later is a deliberate act with a test behind it, and so that the two tools withdrawn before this capability existed — a point-of-sale profile whose service was cancelled, and complementary products whose signals measured empty — cannot return by accident.

#### Scenario: The registry holds exactly the six expected tools
- **WHEN** the registry is built with its ports injected and its contents are enumerated
- **THEN** it holds exactly six entries
- **AND** their names are exactly the declared constant set
- **AND** neither a point-of-sale profile tool nor a complementary-products tool appears

#### Scenario: A tool outside the frozen set is rejected
- **WHEN** a tool whose name is not in the declared set is registered
- **THEN** construction fails rather than silently accepting a seventh tool

### Requirement: Every tool publishes a function-calling schema and validates its arguments before executing anything
Each tool SHALL publish a name, a Spanish description written for a reader who sees no code, and a typed parameter schema, and it MUST validate the arguments it receives against that schema before any port is touched.

A schema is a type guard and not a substitute for judgement, so bounded parameters carry their bounds explicitly and enumerated ones carry their closed set. The description is the interface the model reads to choose: it is a prompt, and it is versioned with the code that serves it.

#### Scenario: Arguments are validated before execution
- **WHEN** a tool is invoked with an argument that violates its schema
- **THEN** no port is called
- **AND** a failed observation is returned carrying the invalid-argument cause

#### Scenario: The catalogue search bounds its result size
- **WHEN** the schema of the catalogue search tool is read
- **THEN** its result-size parameter declares an explicit minimum and maximum

### Requirement: No registered tool can write, and the invariant is verified structurally rather than declared
The registry SHALL contain no tool capable of writing, and that property MUST be verified by introspection of the constructed registry rather than by a self-declared flag on the tool descriptor.

The verification inspects the object graph on three axes: the set of registered names, the methods exposed by every port a tool captures, and the HTTP verbs any registered client can issue. A boolean field saying a tool does not write is set by whoever registers it, which is precisely who could be wrong; the published limitation that no agent writes has to be demonstrated or it must not be published.

#### Scenario: No captured port exposes a write method
- **WHEN** the constructed registry is inspected
- **THEN** no port captured by any tool exposes a method of the write vocabulary
- **AND** no registered HTTP client can issue a verb other than a read

#### Scenario: A writing tool fails the check rather than passing it
- **WHEN** a tool capturing a port that exposes a write method is registered
- **THEN** the verification fails, regardless of what the tool descriptor declares about itself

### Requirement: A failure is returned as an observation carrying a closed-vocabulary cause, never as an exception
A tool SHALL NOT let an exception escape to its caller, and a failure MUST be returned as an observation marked failed and carrying a cause drawn from a closed vocabulary of codes.

An exception would kill the consuming loop instead of costing it one turn, and a generic error leaves the model blind where an informative one lets it reformulate. The cause travels as a code and never as prose, by the same rule the rule-derived warnings already follow: the Spanish belongs to whoever presents it.

#### Scenario: A dependency failure comes back as data
- **WHEN** the dependency a tool consults is unavailable and the tool is invoked
- **THEN** no exception reaches the caller
- **AND** a failed observation is returned carrying the cause of the failure

#### Scenario: An unknown piece reference is an observation and not an error
- **WHEN** a piece-anchored tool is invoked with a SKU that the index does not hold
- **THEN** a failed observation is returned carrying the unknown-reference cause

### Requirement: Availability is reported as a qualitative label and never as a stock figure
The availability tool SHALL report a label drawn from a closed vocabulary, and no value it emits MAY contain a digit or otherwise express a quantity of stock.

The projection stores availability as buckets whose members are numerals, so emitting the bucket verbatim would put a stock figure into the model's context — which is the thing the service boundary forbids and which the search port already declares when it says a bucket on the wire would be the beginning of one. The authority on stock remains the .NET side; this label is a band, of the same kind the ranking already consumes.

#### Scenario: The label carries no figure
- **WHEN** availability is consulted for a piece within an assigned reading scope
- **THEN** the observation carries a label from the closed availability vocabulary
- **AND** that label contains no digit
- **AND** no quantity of stock appears anywhere in the observation

#### Scenario: Every bucket the feed defines maps to a label
- **WHEN** the mapping from stored buckets to labels is read
- **THEN** every bucket the index feed can store has a label
- **AND** no label is a bucket value

### Requirement: An absent reading scope is its own value and is never reported as out of stock
The availability tool SHALL report a distinct value when there is no reading scope or no projection row for the piece, and it MUST NOT report that case as an absence of stock.

Absence of a row is not a count of zero: the search port already fixes that meaning by carrying an unset bucket to say the query ran unscoped. Collapsing the two would trigger a pivot to substitutes over a piece the shop can actually sell, which is the failure the degrade-never-remove rule exists to prevent.

#### Scenario: A principal with no point of sale gets the unscoped value
- **WHEN** availability is consulted with a principal carrying no point of sale
- **THEN** the observation declares that there is no reading scope
- **AND** it does not carry the out-of-stock label

#### Scenario: A piece the point of sale does not carry is not reported as sold out
- **WHEN** availability is consulted for a piece with no projection row in the assigned scope
- **THEN** the observation is distinguishable by its consumer from a piece that is genuinely out of stock

### Requirement: The availability observation declares the age of the projection that served it
The availability observation SHALL declare how old the projection reading is, and a stale projection MUST degrade the observation rather than fail it.

The projection can lag by minutes, which is why it weights ranking and never excludes; a tool reading it inherits the same rule. The age is taken from the checkpoint the drain already records, the same source the retrieval path publishes, rather than recomputed here.

#### Scenario: Freshness travels with the label
- **WHEN** availability is consulted and answered
- **THEN** the observation carries the age of the projection reading that produced it

#### Scenario: A stale projection still answers
- **WHEN** the projection reading is older than the interval the drain targets
- **THEN** the observation is still returned, carrying its age
- **AND** the tool does not fail

### Requirement: The clarification tool selects an axis and the question text is resolved in code
The clarification tool SHALL accept a missing axis drawn from the closed set the assistance layer already publishes, and the Spanish question MUST be resolved in code from the existing closed catalogue of templates rather than written by any model.

The response field carrying this question is typed as prose, so a presentation layer cannot resolve it the way it resolves a code, and no numeric gate inspects it. Letting a model write it would put unchecked prose into the one field with no net under it, and would withdraw a requirement the assistance layer already holds.

#### Scenario: The same axis always produces the same question
- **WHEN** the clarification tool is invoked twice with the same axis
- **THEN** both observations carry exactly the template text that the closed catalogue associates with that axis

#### Scenario: An axis outside the closed set is rejected before execution
- **WHEN** the clarification tool is invoked with an axis that is not in the published set
- **THEN** the argument validation rejects it
- **AND** no question text is produced

### Requirement: Tools address pieces by SKU and never by internal product identifier
A tool SHALL accept a piece as a SKU, and no tool MAY accept an internal product identifier as an argument.

A SKU is stable, real and semantic, which is what a tool result has to carry for a model to chain calls; an internal identifier is an arbitrary string of digits that is never spoken at a counter, and the generation layer already excludes it from what a model is shown for exactly that reason.

#### Scenario: A tool resolves a piece from its SKU
- **WHEN** a piece-anchored tool is invoked with a SKU the index holds
- **THEN** the piece is resolved and the observation is produced

#### Scenario: No tool schema admits an internal identifier
- **WHEN** the parameter schemas of every registered tool are read
- **THEN** none of them declares a parameter carrying an internal product identifier

### Requirement: Observations are bounded and carry no raw retrieval score
An observation SHALL carry only what a consumer needs to decide the next step, and it MUST NOT carry raw retrieval scores.

Everything a tool returns is re-sent on every subsequent turn of the consuming loop, and accumulated context — not the number of steps — is what dominates the cost of an agent. Scores are additionally not comparable across tools: a product distance and a substitute similarity do not measure the same thing, and placing them side by side invites a comparison that means nothing. Where an ordering signal is needed it travels as a position.

#### Scenario: No observation carries a raw score
- **WHEN** any tool is invoked and its observation is inspected
- **THEN** no raw retrieval or similarity score appears in it

#### Scenario: Ordering travels as a position
- **WHEN** a tool returns several candidates whose order matters
- **THEN** the order is expressed as a position within the observation

### Requirement: No tool calls a chat provider, and the embedding calls they do make are counted separately
No tool in the registry SHALL call a chat completion provider, and the embedding calls that some tools legitimately make MUST be counted in a counter of their own rather than in the provider-call figure the assistance layer already publishes.

This is what makes this layer measurable at no cost and the ablation against it clean. The published provider-call figure means chat calls of one request and has tests asserting its ceiling; widening its meaning here would make a number that is already reported mean two different things in two places.

#### Scenario: The registry runs with no provider credential configured
- **WHEN** every tool is exercised with no chat provider credential present
- **THEN** all of them produce their observation
- **AND** none of them calls a chat provider

#### Scenario: Embedding calls are visible and kept apart
- **WHEN** tools that embed their input are invoked
- **THEN** those calls are reported in a counter of their own
- **AND** the provider-call figure of the assistance layer is unchanged

### Requirement: The registry is not wired to any route and the frozen contract does not move
This capability SHALL NOT add, remove or modify any route of the service, and the frozen OpenAPI snapshot MUST remain unchanged.

The only consumer of this registry is the agent loop, which is a later change. Exposing a surface before there is a decision behind it would publish a contract nobody consumes, and the cheapest moment to move that contract is not now.

#### Scenario: The snapshot is untouched
- **WHEN** the committed OpenAPI snapshot is compared against the one the service generates
- **THEN** they are identical

#### Scenario: Sale assistance is unaffected
- **WHEN** a sale-assistance request is served in any of its three modes
- **THEN** the response is the one the assistance layer already produced, with no field added and none changed

### Requirement: Tool tests run offline
The tests of this capability SHALL reach no provider, no network and no real database, driving injected fakes instead.

It is the rule the whole assistance area already follows, and here it is nearly free: this layer calls no chat provider by construction, and its ports are injected rather than built.

#### Scenario: The suite opens no socket
- **WHEN** the tool suite runs with no credential and no database configured
- **THEN** every test passes
- **AND** no network connection is attempted
