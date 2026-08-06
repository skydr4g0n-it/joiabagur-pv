# ai-service-auth Specification

## Purpose
Internal service authentication for `jbg-ai`: HS256 bearer tokens guarding every `/v1` endpoint, opaque rejection of invalid tokens, a service principal built from frozen `snake_case` claims, and token scope taking precedence over the request body.
## Requirements
### Requirement: Internal service token protects every `/v1` endpoint
Every `/v1` endpoint SHALL require an internal service token presented as `Authorization: Bearer <token>`. The token MUST be a JWT signed with HS256 using the secret configured in `JWT_SECRET`. A request without that header MUST be rejected with HTTP 401 and MUST NOT reach the route handler. `GET /health` MUST remain exempt from this requirement.

#### Scenario: Missing token is rejected
- **WHEN** a client calls any `/v1` endpoint without an `Authorization: Bearer` header
- **THEN** the response status is 401
- **AND** the route handler is not executed

#### Scenario: Valid token is accepted
- **WHEN** a client calls a `/v1` endpoint with a JWT signed with the configured secret and carrying all required claims
- **THEN** the request reaches the route handler
- **AND** the response is not 401

#### Scenario: Health stays exempt from authentication
- **WHEN** a client calls `GET /health` without any token
- **THEN** the request is accepted and answered with HTTP 200

### Requirement: Invalid tokens are rejected without revealing the cause
A token that is malformed, signed with the wrong secret, signed with an unexpected algorithm, expired, or missing any required claim MUST be rejected with HTTP 401. The response body MUST NOT disclose the signing secret, and MUST NOT disclose which specific validation step failed.

#### Scenario: Wrong signature is rejected
- **WHEN** a client presents a JWT signed with a secret other than the configured one
- **THEN** the response status is 401
- **AND** the body does not reveal the secret or the exact failure cause

#### Scenario: Expired token is rejected
- **WHEN** a client presents a JWT whose expiry is in the past
- **THEN** the response status is 401

#### Scenario: Missing required claim is rejected
- **WHEN** a client presents a correctly signed JWT that omits one of the required claims
- **THEN** the response status is 401

### Requirement: Validated tokens produce a service principal for handlers
The service MUST validate the token in a FastAPI dependency and expose the result to handlers as a service principal built from the claims `user_id`, `role`, `pos_id` and `trace_id`. These claim names are frozen in `snake_case` on the wire; the calling .NET service is responsible for emitting them with exactly those keys. All four claims MUST be required.

#### Scenario: Principal carries the token claims
- **WHEN** an authenticated request reaches a `/v1` handler
- **THEN** the handler receives a service principal exposing `user_id`, `role`, `pos_id` and `trace_id` taken from the token

#### Scenario: Claim names are frozen in snake_case
- **WHEN** a token presents point-of-sale scope under a key other than `pos_id`
- **THEN** the required claim is considered absent and the response status is 401

### Requirement: Token scope takes precedence over the request body
The effective `pos_id` and `role` applied by any `/v1` handler MUST come from the token, never from the request body. Request models MAY accept an optional `pos_id` for client compatibility, but that value MUST be ignored. A mismatch between the body value and the token value MUST NOT cause an error and MUST NOT change behavior.

#### Scenario: Token pos_id overrides a different body value
- **WHEN** a client calls `POST /v1/retrieval/products` with a token carrying `pos_id = B` and a body carrying `pos_id = A`, with A different from B
- **THEN** the effective scope applied by the handler is B
- **AND** the request does not fail because of the value sent in the body

#### Scenario: Role cannot be escalated from the body
- **WHEN** a request body carries a role value that differs from the token claim
- **THEN** the effective role remains the one from the token

### Requirement: Authentication tests run in process without external AI or database
The authentication test suite MUST cover missing token, invalid token variants, principal extraction and token-over-body precedence with an in-process client, and MUST NOT call real LLM providers, embedding APIs, or production RDS.

#### Scenario: Auth suite passes without external calls
- **WHEN** the `ai-service` test suite runs with the required environment provided in process
- **THEN** `test_request_without_token_is_rejected`, `test_invalid_token_is_rejected` and `test_pos_id_from_token_overrides_body_value` pass
- **AND** no call is made to an LLM provider, embedding API or production database
