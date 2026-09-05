# vector-retrieval

## MODIFIED Requirements

### Requirement: Over-retrieval applies after the distance filter
`top_k` MUST remain the page size the .NET caller wants after hydrating. The retriever MUST return at most `min(top_k × 3, 60)` hits, using the same `over_retrieval_count` helper as the stub, applied to the fused and reordered candidate list. `candidates_returned` MUST equal the length of `results`. `effective_pos_id` MUST be the token claim, not the body `pos_id`. `low_confidence` MUST be false when at least one result is returned and at least one of them was produced by more than one branch. When only one branch ran, `low_confidence` MUST NOT be derived from cross-branch consensus at all — it MUST be true only when no result is returned, which is the meaning it had before the branches existed.

Each branch MUST be truncated at the configured branch depth **before** fusing, and that depth MUST be a separate parameter from the over-retrieval window even when their defaults coincide. The vector branch's depth MUST be applied as a `LIMIT` on the set already filtered by the distance threshold.

The candidate set of every branch MUST additionally be restricted to the point of sale of the token when the soft-prefilter capability applies its scope, as defined by `pos-projection`. That restriction is the only predicate that removes a candidate on availability grounds: stock never removes one. Filtering by the point of sale MUST NOT be implemented by post-filtering an approximate index scan, because an approximate scan that returns fewer rows than requested does so without any visible error; the scoped subset MUST be established before the distance is ranked so the branch depth is honoured.

#### Scenario: Overfetch is capped after fusion
- **GIVEN** `STUB_MODE` is disabled and more than 15 candidates survive fusion
- **WHEN** an authenticated client calls `POST /v1/retrieval/products` with `top_k = 5`
- **THEN** `results` has length 15
- **AND** `candidates_returned` is 15

#### Scenario: Overfetch does not refill from rows above the threshold
- **GIVEN** `STUB_MODE` is disabled, `mode=vector`, and only 2 compatible rows pass the threshold while many more exist above it
- **WHEN** an authenticated client calls `POST /v1/retrieval/products` with `top_k = 5`
- **THEN** `results` has length 2
- **AND** `candidates_returned` is 2
- **AND** no row with distance greater than the threshold is present

#### Scenario: Branch depth does not follow the requested page size
- **GIVEN** `STUB_MODE` is disabled
- **WHEN** the same query is served with `top_k = 5` and with `top_k = 20`
- **THEN** the number of candidates each branch contributes to the fusion is the same in both calls
- **AND** only the number of returned candidates differs

#### Scenario: Token pos_id is echoed and body pos_id is ignored
- **GIVEN** `STUB_MODE` is disabled and at least one hit is returned
- **WHEN** an authenticated client calls with token `pos_id = B` and body `pos_id = A`
- **THEN** `effective_pos_id` is B
- **AND** the search SQL scopes candidates to point of sale B and never to the body value

#### Scenario: The scoped branch still returns its full depth
- **GIVEN** `STUB_MODE` is disabled and a point of sale whose assortment is a small fraction of the indexed catalogue
- **WHEN** a retrieval is served with the point-of-sale scope applied
- **THEN** the vector branch returns as many candidates as its depth allows within the scoped subset
- **AND** the count is not silently capped below that depth by an approximate index scan
