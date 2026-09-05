## MODIFIED Requirements

### Requirement: Dictionary entries and exclusions are justified against the corpus
Every overlay entry MUST be accompanied in the file by the reason it exists. Terms measured to be false friends, terms that are vocabulary gaps rather than synonyms, and terms that already reach their documents without expansion MUST be recorded as explicit exclusions with their reason, so a later editor sees the rule where the temptation is.

A term recorded as a vocabulary gap MUST name the change that will close it, and MUST be removed from the exclusions once the base vocabulary defines it as a canonical: a term the base now knows is no longer a gap, and leaving it listed as one would make the file contradict the vocabulary it overlays. An overlay entry MUST NOT be added for a surface form that reaches no document, unless the entry is a regional variant declared as such.

#### Scenario: A measured false friend is absent from the dictionary
- **WHEN** the dictionary is loaded
- **THEN** no class for the leather material contains the term `piel`
- **AND** the overlay records that exclusion together with its reason

#### Scenario: Vocabulary gaps are not smuggled in as synonyms
- **WHEN** the dictionary is loaded
- **THEN** it contains no class introducing a piece type absent from the enrichment vocabulary
- **AND** any term still recorded as a vocabulary gap names the change that will close it

#### Scenario: A closed gap stops being recorded as an exclusion
- **GIVEN** the enrichment vocabulary now defines `diadema`, `gemelos`, `cinturon` and `llavero` as canonical piece types
- **WHEN** the overlay is loaded
- **THEN** none of those four terms is recorded as an exclusion
- **AND** the exclusions that remain are the ones still measured to be false friends, still open vocabulary gaps, or still able to reach their documents unexpanded

#### Scenario: A plural canonical is reachable from its singular
- **GIVEN** a canonical piece type recorded in the plural, such as `gemelos`
- **AND** that plural reduction maps a plural query term to its singular and never the reverse
- **WHEN** an operator types the singular form
- **THEN** the overlay supplies it as a surface form of that class
- **AND** the query resolves to the plural canonical
