## ADDED Requirements

### Requirement: The vector branch truncates under a total order, so ties do not decide silently

The vector branch orders its candidates by cosine distance and truncates at the configured branch depth, and that ordering MUST be a total order. Distance alone is not one: when two documents share a distance and the truncation boundary falls between them, which one survives is undefined, and PostgreSQL is free to return either.

The ordering MUST therefore carry a final deterministic key after the distance, so that the set surviving truncation is a function of the query and the index alone. The key MUST NOT alter the relative order of candidates whose distances differ.

This is a property the evaluation harness depends on: without it, two runs of the same configuration against the same index can return different candidate sets, and a moved metric cannot be attributed to a change rather than to chance.

#### Scenario: Equal distances resolve the same way on every run

- **GIVEN** two indexed documents whose distance to a query vector is identical
- **AND** the branch depth truncates the candidate list between them
- **WHEN** the same retrieval runs twice against an unchanged index
- **THEN** the same document survives truncation in both runs

#### Scenario: The tiebreak does not reorder candidates that are not tied

- **GIVEN** two candidates with different distances
- **WHEN** the vector branch orders them
- **THEN** the closer one precedes the other, regardless of the deterministic key

#### Scenario: Repeating a retrieval yields the same candidate set

- **GIVEN** `STUB_MODE` is disabled and an unchanged index
- **WHEN** the same query is retrieved twice with the same configuration
- **THEN** the two candidate lists are identical in content and order
