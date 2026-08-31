## MODIFIED Requirements

### Requirement: Frozen `/v1` endpoint surface
The `jbg-ai` service SHALL expose the following internal endpoints under `/v1`, each backed by explicit Pydantic request and response models: `POST /v1/retrieval/products`, `POST /v1/retrieval/substitutes`, `POST /v1/assist/sale`, `POST /v1/inventory/propose`, `POST /v1/enrich/products`, `POST /v1/families/suggest`, `POST /v1/index/sync`, `GET /v1/index/status`, and `GET /v1/evals/runs` (development profile only). Every `/v1` endpoint MUST require a valid internal service token. `GET /health` MUST remain public and its contract MUST NOT change with respect to C01. Response bodies MUST validate against the declared response model; the service MUST NOT return undeclared shapes.

`POST /v1/families/suggest` is the ninth route and the first addition to this surface since it was frozen. Adding it moves the boundary with the .NET client deliberately: the committed `ai-service/openapi.json` MUST be regenerated in the same change that adds the route, and `test_openapi_snapshot_is_stable` MUST pass against that regenerated snapshot. A route added without regenerating the snapshot MUST fail the build.

#### Scenario: Every frozen route answers with its declared model
- **WHEN** an authenticated client calls any of the nine `/v1` endpoints with a valid request body in stub mode
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

#### Scenario: The regenerated snapshot matches the live schema
- **WHEN** `test_openapi_snapshot_is_stable` runs against the working tree of this change
- **THEN** the live OpenAPI schema equals the committed `ai-service/openapi.json`
- **AND** that snapshot contains the nine `/v1` paths

## ADDED Requirements

### Requirement: Family suggestion contract carries members, labels and review flags

`POST /v1/families/suggest` SHALL accept an optional scoping body — a piece type and a maximum number of proposals — and MUST return, for each proposal, the normalized root, the piece type, and the ordered members. Each member MUST carry the product identifier, its SKU, its name, its variant label as a nullable value, and its position. A member the relative embedding veto flagged MUST be marked as such together with its distance, and MUST still be present in the proposal.

The response MUST carry **three** lists, not one: the proposals, the groups a guard rejected together with the reason, and the products the piece-type gate excluded with theirs. A caller must be able to surface both kinds of omission as catalogue quality incidences without inferring them from an absence. Products skipped for already belonging to a family MUST be reported as a count rather than enumerated.

Under stub mode the route MUST return a deterministic fixture that validates against the declared response model, without touching the database.

#### Scenario: A proposal carries its members in order with their labels
- **WHEN** an authenticated client requests suggestions and a family is proposed
- **THEN** the proposal reports the root, the piece type and the ordered members
- **AND** each member carries its product identifier, SKU, name, position and nullable variant label

#### Scenario: A flagged member is reported and retained
- **WHEN** a proposal contains a member the relative veto flagged
- **THEN** that member is present in the members list
- **AND** it is marked for review with its distance

#### Scenario: Rejected groups are reported explicitly
- **WHEN** a candidate group is rejected by the degenerate-root guard
- **THEN** the response lists it with the reason for the rejection
- **AND** it does not appear among the proposals

#### Scenario: Stub mode answers without a database
- **WHEN** the route is called with stub mode enabled
- **THEN** the response is a deterministic fixture that validates against the declared model
- **AND** no database connection is opened
