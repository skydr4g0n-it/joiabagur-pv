## MODIFIED Requirements

### Requirement: A result explains itself with what the system actually knows

The panel SHALL explain a result with an origin badge together with the materials the retriever recognised.

The origin badge MUST be derived **per result** from that result's own match reasons, and MUST NOT be a single decision taken once for the whole response from whether the assisted path served the search. A result the lexical branch alone produced MUST NOT be labelled a semantic match, so that a search served after the embedding provider failed tells the operator what actually answered it instead of claiming a capability that did not run.

The panel MUST NOT render the retriever's raw match reason values, which are engineering vocabulary, and MUST NOT synthesise an explanation the system has not asserted.

The variant label MUST be displayed only when present, so that it appears on its own once the change that populates it has run, without the panel being touched.

The mapping from origin to badge MUST tolerate values it does not know without failing, falling back to a neutral label rather than throwing or leaving the badge empty.

#### Scenario: The badge and the materials explain the match
- **WHEN** a result is rendered
- **THEN** an origin badge is displayed
- **AND** the materials the retriever recognised are displayed

#### Scenario: A result served only by the lexical branch says so
- **GIVEN** a response whose results carry different match reasons
- **WHEN** a result whose match reasons do not include the vector branch is rendered
- **THEN** its badge is the text-search origin
- **AND** a result whose match reasons include the vector branch shows the assisted origin in the same list

#### Scenario: An unknown origin does not break the row
- **WHEN** a result carries a match reason the panel does not know
- **THEN** a neutral origin label is displayed
- **AND** the row renders without error

#### Scenario: The raw match reasons are not shown
- **WHEN** a result is rendered
- **THEN** the retriever's raw match reason values do not appear on screen

#### Scenario: An absent variant label leaves no gap
- **WHEN** a result carries no variant label
- **THEN** no size is displayed for it
- **AND** no placeholder value is invented
