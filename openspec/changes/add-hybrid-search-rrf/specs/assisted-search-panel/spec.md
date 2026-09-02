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

## ADDED Requirements

### Requirement: The panel says which retriever answered the search

The panel MUST state, for the response as a whole, which retriever produced the results it is showing, derived from the provenance the results carry rather than asserted by a field of the response. Three outcomes MUST be distinguishable:

- the assisted path served and at least one result came from the semantic branch;
- the assisted path served but **no** result came from the semantic branch, which is the retrieval service having degraded to its text branch after the embedding provider failed;
- the assisted path did not serve at all and the caller's own text search answered.

The second case MUST be stated on screen. It is the failure that looks healthiest of all — the request succeeds, results are rendered and the response reports the assisted path as available — so leaving it unsaid shows the operator a screen named after a capability that did not run. It MUST NOT be presented as the assisted search being unavailable, because it answered.

When no result is returned there is no provenance to read, so the panel MUST NOT claim a mode; that case is already covered by the empty-state messages, which stay unchanged.

The low-confidence marking MUST be read only alongside an empty result list, because the retriever computes it as branch disagreement only when more than one branch ran and as "nothing was returned" otherwise.

#### Scenario: A degraded semantic branch is stated rather than hidden
- **GIVEN** a response reporting the assisted path as available
- **AND** no result carries the semantic branch among its match reasons
- **WHEN** the panel renders it
- **THEN** it says the semantic match was not available
- **AND** it does not say the assisted search is unavailable
- **AND** the results are still rendered

#### Scenario: A fused response is not warned about
- **GIVEN** a response in which at least one result came from the semantic branch
- **WHEN** the panel renders it
- **THEN** no warning about the semantic branch is displayed

#### Scenario: The caller's own text search keeps its own message
- **GIVEN** a response reporting the assisted path as unavailable
- **WHEN** the panel renders it
- **THEN** it says the assisted search is unavailable
- **AND** the results are labelled as coming from the text search

#### Scenario: No results means no claim about the mode
- **GIVEN** a response with no results
- **WHEN** the panel renders it
- **THEN** no retriever is named
- **AND** the empty-state message is shown instead
