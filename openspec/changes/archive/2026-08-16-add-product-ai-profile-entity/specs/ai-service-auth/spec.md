## MODIFIED Requirements

### Requirement: Validated tokens produce a service principal for handlers
The service MUST validate the token in a FastAPI dependency and expose the result to handlers as a service principal built from the claims `user_id`, `role`, `pos_id` and `trace_id`. These claim names are frozen in `snake_case` on the wire; the calling .NET service is responsible for emitting them with exactly those keys.

`user_id`, `role` and `trace_id` MUST be required on every `/v1` route. `pos_id` MUST be required on routes that have point-of-sale scope — retrieval, sale assistance and inventory — and MUST NOT be required on catalog-wide routes such as enrichment and index synchronization, which operate over the whole catalog and belong to no point of sale. The service MUST expose these as two distinct dependencies, so that a route's scope is declared where the route is declared and cannot be relaxed by accident for a route that needs it. A token carrying no `pos_id` MUST be rejected with HTTP 401 on any point-of-sale scoped route.

#### Scenario: Principal carries the token claims
- **WHEN** an authenticated request reaches a point-of-sale scoped `/v1` handler
- **THEN** the handler receives a service principal exposing `user_id`, `role`, `pos_id` and `trace_id` taken from the token

#### Scenario: Claim names are frozen in snake_case
- **WHEN** a token presents point-of-sale scope under a key other than `pos_id`
- **THEN** the required claim is considered absent and the response status is 401

#### Scenario: A catalog route accepts a token without point-of-sale scope
- **WHEN** an authenticated client calls a catalog-wide `/v1` route with a token carrying `user_id`, `role` and `trace_id` but no `pos_id`
- **THEN** the request reaches the route handler
- **AND** the response is not 401

#### Scenario: A retrieval route rejects a token without point-of-sale scope
- **WHEN** the same token is presented to `POST /v1/retrieval/products`
- **THEN** the response status is 401
- **AND** the route handler is not executed

#### Scenario: A catalog route still rejects a token missing the other claims
- **WHEN** a catalog-wide `/v1` route is called with a token that omits `user_id`, `role` or `trace_id`
- **THEN** the response status is 401
