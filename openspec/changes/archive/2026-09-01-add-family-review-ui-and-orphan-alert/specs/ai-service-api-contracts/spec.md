## MODIFIED Requirements

### Requirement: Frozen `/v1` endpoint surface
The `jbg-ai` service SHALL expose the following internal endpoints under `/v1`, each backed by explicit Pydantic request and response models: `POST /v1/retrieval/products`, `POST /v1/retrieval/substitutes`, `POST /v1/assist/sale`, `POST /v1/inventory/propose`, `POST /v1/enrich/products`, `POST /v1/families/suggest`, `POST /v1/families/audit`, `POST /v1/index/sync`, `GET /v1/index/status`, and `GET /v1/evals/runs` (development profile only). Every `/v1` endpoint MUST require a valid internal service token. `GET /health` MUST remain public and its contract MUST NOT change with respect to C01. Response bodies MUST validate against the declared response model; the service MUST NOT return undeclared shapes.

`POST /v1/families/suggest` is the ninth route and the first addition to this surface since it was frozen. `POST /v1/families/audit` is the tenth, and it is a separate route rather than an extension of the ninth: the two read disjoint populations — suggestion reads products that belong to no family, the audit reads the families that exist — and they converge differently, since suggestion empties itself as batches are approved while the audit is a standing signal. Folding the audit into the suggestion response would move the committed snapshot just the same, so nothing is saved by it.

Adding a route moves the boundary with the .NET client deliberately: the committed `ai-service/openapi.json` MUST be regenerated in the same change that adds the route, and `test_openapi_snapshot_is_stable` MUST pass against that regenerated snapshot. A route added without regenerating the snapshot MUST fail the build.

#### Scenario: Every frozen route answers with its declared model
- **WHEN** an authenticated client calls any of the ten `/v1` endpoints with a valid request body in stub mode
- **THEN** the response status is 200
- **AND** the body validates against that endpoint's declared response model

#### Scenario: Health contract is unchanged
- **WHEN** a client calls `GET /health` without a token
- **THEN** the response is HTTP 200 with an OK status indicator and the configured service version
- **AND** the shape is the same one C01 published

#### Scenario: The family suggestion route requires the service token
- **WHEN** an unauthenticated client calls `POST /v1/families/suggest`
- **THEN** the request is rejected before any work is done
- **AND** no proposal is computed

#### Scenario: The family audit route requires the service token
- **WHEN** an unauthenticated client calls `POST /v1/families/audit`
- **THEN** the request is rejected before any work is done
- **AND** no similarity is computed

#### Scenario: The regenerated snapshot matches the live schema
- **WHEN** `test_openapi_snapshot_is_stable` runs against the working tree of the change that added the route
- **THEN** the live OpenAPI schema equals the committed `ai-service/openapi.json`
- **AND** that snapshot contains the ten `/v1` paths

## ADDED Requirements

### Requirement: Family audit contract carries flags, candidates and the judgements already made

The contract for `POST /v1/families/audit` SHALL carry, in one response, the members of persisted families that the vectors do not support and the unassigned products nominated as candidates for a family, together with the groups a guard refused and the products a gate excluded, recomputed over the current catalogue state.

Each flagged member MUST carry its product, its family, the margin by which a product of another family beat its worst sibling, and the identity of that product. Each candidate MUST carry its product, the family it is nominated for, the similarity, the family's worst-sibling similarity, the margin between them, the data origin of the product, and the neighbourhood-purity count reported as a ranking signal only.

The request MUST accept the `(product, family)` pairs that already carry a human verdict, so that the service can omit them without holding any judgement of its own. The service MUST NOT persist those pairs, and MUST NOT read the transactional catalogue schema to discover them.

The request MUST accept the veto and nomination margins, falling back to configuration when they are absent, and a cap on the number of candidates returned. Flagged members, refused groups and excluded products MUST NOT be truncated by that cap.

#### Scenario: One call returns both sides of the membership line
- **WHEN** an authenticated client calls `POST /v1/families/audit` in stub mode
- **THEN** the response contains the flagged members and the candidates in the same body
- **AND** each flagged member carries its margin and the product that beat its worst sibling
- **AND** each candidate carries its similarity, the target family's worst-sibling similarity, its data origin and its purity count

#### Scenario: Judged pairs travel in the request and are not stored
- **WHEN** the caller sends a set of `(product, family)` pairs that already carry a verdict
- **THEN** none of those pairs appears among the flagged members or the candidates
- **AND** repeating the call without them reports those pairs again
- **AND** the service holds no record of them between calls

#### Scenario: The candidate cap never truncates a refusal
- **WHEN** the caller caps the number of candidates below the number the audit produced
- **THEN** the candidates are truncated to that cap
- **AND** the flagged members, the refused groups and the excluded products are returned in full
