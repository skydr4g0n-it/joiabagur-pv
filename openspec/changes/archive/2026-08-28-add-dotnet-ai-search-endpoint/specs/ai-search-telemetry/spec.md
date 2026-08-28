## MODIFIED Requirements

### Requirement: Degraded searches are recorded and distinguishable

The system SHALL record searches that were not served by the AI service with the same completeness as assisted searches, and MUST mark their origin so every path can be separated in analysis.

Two such paths exist and MUST NOT share an origin value. The first is the degraded path, used when the AI service was consulted and could not answer. The second is the disabled path, used when assisted search is switched off for the point of sale and the AI service was therefore never consulted at all. Recording the second as the first would corrupt the very population the origin exists to isolate: a period with assisted search switched off would read as a period of repeated AI failures.

The retrieval duration MUST measure obtaining the candidate list regardless of its source, so all origins remain comparable to each other.

The origin MUST be persisted as an enumeration with explicit stable values, and its mapping MUST be documented, because the table is queried by hand. Adding a value MUST NOT change the meaning of the values already stored.

#### Scenario: A degraded search is recorded with its own origin
- **WHEN** a search is served by the lexical searcher because the AI service was unavailable
- **THEN** the persisted event carries the lexical-fallback origin
- **AND** the retrieval duration measures the lexical query

#### Scenario: A search with assisted retrieval switched off is recorded as disabled
- **WHEN** a search is served without consulting the AI service because assisted search is switched off for that point of sale
- **THEN** the persisted event carries the disabled origin
- **AND** it does not carry the lexical-fallback origin
- **AND** the retrieval duration measures the query that produced the results

#### Scenario: The origins are separable in analysis
- **WHEN** events of the assisted, degraded and disabled origins exist
- **THEN** grouping by origin yields the three populations separately
- **AND** the retrieval duration of all of them is expressed in the same unit and measures the same phase
- **AND** the values previously stored for the assisted and degraded origins still mean what they meant before

#### Scenario: Adding the third origin needs no schema change
- **WHEN** the persisted origin column is inspected after the third value is introduced
- **THEN** the column type is unchanged
- **AND** no migration was required to store the new value
