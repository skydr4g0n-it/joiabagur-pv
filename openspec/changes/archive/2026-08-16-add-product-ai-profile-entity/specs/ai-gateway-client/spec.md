## MODIFIED Requirements

### Requirement: Every gateway call carries a real point-of-sale scope

Every call to the gateway SHALL carry a call scope holding the user identifier, the role and, when the route has point-of-sale scope, the point-of-sale identifier. The scope type MUST expose exactly two construction paths and no more: one for point-of-sale scoped routes, which requires a concrete point of sale and MUST reject an empty point-of-sale identifier, and one for catalog-wide routes, which carries no point of sale at all. Both MUST reject a blank role. No sentinel value MUST be accepted in place of a point of sale on either path, because from the change that introduces the soft prefilter onward the `pos_id` claim is the retriever's only hard filter, and a wildcard reaching it would be a cross-point-of-sale leak.

A catalog-wide scope MUST be rejected by any point-of-sale scoped operation of the client, before any request is issued. The client MUST NOT perform authorization: the caller is responsible for having validated the user's assignment to that point of sale before constructing a point-of-sale scope.

#### Scenario: Scope requires a concrete point of sale
- **WHEN** code attempts to build a point-of-sale call scope with an empty point-of-sale identifier
- **THEN** construction fails with an argument error
- **AND** no construction path accepts a sentinel value in its place

#### Scenario: Blank role is rejected
- **WHEN** code attempts to build a call scope with a blank role
- **THEN** construction fails with an argument error

#### Scenario: Catalog scope carries no point of sale
- **WHEN** code builds a catalog-wide call scope
- **THEN** the resulting scope exposes no point-of-sale identifier
- **AND** construction succeeds without one

#### Scenario: Catalog scope cannot be used for retrieval
- **WHEN** a retrieval call is attempted with a catalog-wide scope
- **THEN** the call fails before any HTTP request is issued

### Requirement: Internal service token carries the frozen claims and nothing else

The client SHALL sign an internal service token with HS256 using a secret dedicated to this integration, separate from the user-facing signing key. The payload MUST contain the claims frozen by the AI service in `snake_case`: `user_id`, `role` and `trace_id`, each non-empty, plus `pos_id` when and only when the call scope carries a point of sale. A scope without a point of sale MUST produce a token with no `pos_id` claim at all, rather than one carrying an empty or placeholder value. It MUST contain an expiry derived from the configured time-to-live. It MUST NOT contain an audience claim, an issuer claim or a not-before claim, because the service validates tokens without expecting an audience and evaluates temporal claims with no clock tolerance. The token MUST be presented as a bearer credential on every request.

#### Scenario: Token carries the four frozen claims
- **WHEN** the client signs a token for a valid point-of-sale call scope
- **THEN** the payload contains `user_id`, `role`, `pos_id` and `trace_id` under exactly those names
- **AND** none of the four is empty

#### Scenario: Catalog token omits the point-of-sale claim
- **WHEN** the client signs a token for a catalog-wide call scope
- **THEN** the payload contains `user_id`, `role` and `trace_id`
- **AND** it contains no `pos_id` claim, empty or otherwise

#### Scenario: Token declares no audience and no issuer
- **WHEN** the client signs a token
- **THEN** the payload contains no audience claim and no issuer claim
- **AND** it contains no not-before claim

#### Scenario: Token expires after the configured lifetime
- **WHEN** the client signs a token with a configured time-to-live
- **THEN** the expiry equals the signing instant plus that lifetime

#### Scenario: Request presents the token as a bearer credential
- **WHEN** the client issues a retrieval request
- **THEN** the request carries an `Authorization` header with the signed token as a bearer credential

### Requirement: Client models cannot drift from the committed contract

An automated test SHALL compare the client's models against the committed `ai-service/openapi.json`, so that a renegotiated contract breaks the .NET build as well as the Python one. The test MUST cover the retrieval request, result and response models and the enrichment request, proposed-profile and response models, verifying that every property exists in the committed schema under the same name and with the same nullability. Without this guard, a contract change would leave the .NET build green and surface at runtime as a silently missing value — which is exactly what the per-field provenance of a proposed profile would become.

#### Scenario: Models match the committed schema
- **WHEN** the contract test runs against an unmodified working tree
- **THEN** every retrieval and enrichment model property is present in the committed schema with the same name and nullability

#### Scenario: Contract drift breaks the build
- **WHEN** the committed schema changes a retrieval or enrichment property name or nullability and the client models are not updated
- **THEN** the contract test fails

## ADDED Requirements

### Requirement: Typed gateway client exposes catalog enrichment

The client SHALL expose an operation for catalog enrichment against `POST /v1/enrich/products`, serializing and deserializing the frozen contract with `snake_case` property names on the wire. Every proposed value MUST map its confidence and its provenance — `rule` or `inferred` — as first-class values rather than being flattened away, because the review policy of the consuming capability is expressed entirely in terms of them. Proposed values the contract declares as nullable MUST map to nullable values. The operation MUST carry a catalog-wide call scope.

#### Scenario: Proposed profiles are mapped with confidence and provenance
- **WHEN** the AI service answers HTTP 200 to an enrichment request
- **THEN** the client returns one proposed profile per requested product
- **AND** each proposed field exposes its confidence and whether it is `rule` or `inferred`

#### Scenario: Absent proposed fields survive mapping
- **WHEN** a returned profile carries a null piece type, stone type or size label
- **THEN** those properties are null on the mapped object
- **AND** mapping neither throws nor substitutes a default value

### Requirement: Enrichment degrades on its own budget, isolated from retrieval

Catalog enrichment SHALL use its own named client with its own circuit-breaker state and its own configured time budget, sized for an extraction call rather than for retrieval. It MUST NOT be retried automatically, because a second attempt at an extraction duplicates model cost with no reason to expect a different result. A slow or failing enrichment call MUST NOT open the retrieval circuit, so it can never push an operator's search onto its degraded lexical path for a service that is answering retrieval correctly.

#### Scenario: Enrichment failures do not open the retrieval circuit
- **WHEN** enrichment calls fail repeatedly until the enrichment circuit opens
- **THEN** retrieval calls continue to be issued normally

#### Scenario: An enrichment failure is not retried
- **WHEN** the AI service answers an enrichment request with a server error
- **THEN** exactly one HTTP request was issued

#### Scenario: Enrichment resilience is configured explicitly
- **WHEN** the enrichment client is registered
- **THEN** its time budget and circuit breaker thresholds come from configuration rather than from framework defaults
