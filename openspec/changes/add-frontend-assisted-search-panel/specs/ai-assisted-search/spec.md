## ADDED Requirements

### Requirement: Results carry the material signals the retriever recognised

Each result returned to the caller SHALL carry the materials the AI service reported for that candidate, so that the interface can explain why a result is being shown.

These materials are **not** hydrated and are **not** authoritative: they come from the enriched index, not from the transactional catalog, and they are the same values the caller may filter on. They exist to explain a match, never to describe stock, price or availability, which remain the exclusive product of hydration.

The field MUST be present and empty rather than absent when the retriever reported none, and MUST be empty on the degraded and disabled paths, where no retriever ran.

This is the only explanatory signal available today: the retriever's match reasons are a single constant value for every result until the lexical branch exists, so a caller has nothing else with which to tell an operator why a piece was proposed.

#### Scenario: A retrieved result carries its materials
- **WHEN** a result is built from a candidate the AI service returned
- **THEN** it carries the materials that candidate reported

#### Scenario: Materials never come from hydration
- **WHEN** a result carries materials
- **THEN** they are the values the AI service reported
- **AND** they are not read from the transactional catalog

#### Scenario: A degraded result carries no materials
- **WHEN** a result is produced by the degraded or the disabled path
- **THEN** its material list is empty
- **AND** it is not absent
