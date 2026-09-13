## ADDED Requirements

### Requirement: The abstention decision reaches the sale-assistance path and is declared there

The abstention decision SHALL govern the sale-assistance path and not only the product retrieval response. When the rule decides that the catalogue has no answer for a query, the assistance response MUST return no group and MUST declare the abstention in a field dedicated to it.

The assistance response MUST NOT express this decision by reusing the cross-branch confidence signal. That signal carries a different, measured meaning — the absence of agreement between branches — and on the judged set it fires on answerable queries far more often than on out-of-domain ones, so reusing it would report the opposite of what a reader would conclude.

This requirement does not alter what the product retrieval response reports; it adds the obligation that the decision travels to the consumer that generates.

#### Scenario: An abstained query yields no group on the assistance path
- **GIVEN** a query for which the rule decides the catalogue has no answer
- **WHEN** the sale assistance is requested with it
- **THEN** no group is returned
- **AND** the dedicated abstention field is set

#### Scenario: The cross-branch signal is not repurposed
- **WHEN** the sale assistance declares an abstention
- **THEN** it does so in its own field
- **AND** it does not rely on the cross-branch confidence signal to convey it

#### Scenario: An answerable query is not silenced on the assistance path
- **GIVEN** a query the catalogue can answer
- **WHEN** the sale assistance is requested with it
- **THEN** the dedicated abstention field is clear
- **AND** at least one group is returned

### Requirement: The effective abstention configuration travels as a parameter on every consuming path

Every path that consumes the abstention rule SHALL receive the effective configuration as a parameter of the call. Configuration MUST supply the default only, and no consuming module may read the value from the environment internally, so an evaluation can compare configurations in a single process without restarting anything.

#### Scenario: A consuming path can be driven with a configuration of its own
- **GIVEN** two calls made in the same process with different abstention configurations
- **WHEN** both are served
- **THEN** each honours the configuration it was given
- **AND** neither reads the value from the environment

#### Scenario: Absent parameters fall back to the configured default
- **WHEN** a consuming path is called without an explicit abstention configuration
- **THEN** the configured default is applied

### Requirement: A piece that cannot be used is not reported as an abstention

When a request anchors a concrete product and the index cannot serve it — the product is unknown, inactive, or held without an embedding — the response MUST be an error that distinguishes those cases and MUST NOT be a success carrying the abstention field. An abstention is a statement about what the catalogue can answer, and using it for an unusable anchor would assert something the system has not established.

#### Scenario: An unusable anchor is an error and not an abstention
- **GIVEN** a request anchored to a product the index cannot serve
- **WHEN** it is served
- **THEN** the response is an error naming which of the unusable cases occurred
- **AND** it is not a success with the abstention field set
