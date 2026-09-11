## ADDED Requirements

### Requirement: The lexical branch truncates under a total order, so ties do not decide silently

The lexical branch orders its candidates by coordination and then by textual rank, and truncates at the configured branch depth; that ordering MUST be a total order. Neither magnitude is one, and in this corpus ties are the norm rather than the exception: coordination takes a handful of values by construction, and the textual rank repeats across documents that match the same fields. When the truncation boundary falls inside a tie, which documents survive is undefined.

The ordering MUST therefore carry a final deterministic key after coordination and rank, so that the list entering the fusion is a function of the query and the index alone. The key MUST NOT alter the relative order of candidates that differ in coordination or in rank.

The fusion consumes rank positions, so an undefined order inside a tie propagates to the fused result and from there to any measurement taken over it.

#### Scenario: Equal coordination and rank resolve the same way on every run

- **GIVEN** two indexed documents with the same coordination and the same textual rank
- **AND** the branch depth truncates the lexical list between them
- **WHEN** the same retrieval runs twice against an unchanged index
- **THEN** the same document survives truncation in both runs

#### Scenario: The tiebreak does not disturb the coordination ordering

- **GIVEN** two candidates whose coordination differs
- **WHEN** the lexical branch orders them
- **THEN** the one matching more counting groups precedes the other, regardless of the deterministic key

#### Scenario: The fused result is stable across runs

- **GIVEN** `STUB_MODE` is disabled and an unchanged index
- **WHEN** the same query is served twice in hybrid mode with the same configuration
- **THEN** the fused candidate list is identical in content and order
