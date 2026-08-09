## ADDED Requirements

### Requirement: Typed gateway client exposes catalog retrieval

The backend SHALL provide a typed client for the `jbg-ai` service exposing exactly one operation in this change: catalog retrieval against `POST /v1/retrieval/products`. The client MUST serialize and deserialize the frozen contract using `snake_case` property names on the wire. `family_id` and `variant_label` MUST map to nullable values, because the contract guarantees an explicit null rather than an absent field. The client MUST NOT send `pos_id` in the request body, since the service ignores it and the scope comes from the token. The client MUST report `candidates_returned` as received and MUST NOT truncate the result list: `top_k` is the page size the caller wants after hydrating, and truncation belongs to the hydrating caller.

#### Scenario: Successful response is mapped in full
- **WHEN** the AI service answers HTTP 200 to a retrieval request
- **THEN** the client returns an object exposing `results`, `candidates_returned`, `low_confidence`, `trace_id` and `effective_pos_id`
- **AND** each result exposes `product_id`, `sku`, `score`, `match_reasons` and `materials` as a list

#### Scenario: Contract nulls survive mapping
- **WHEN** a returned result carries `family_id` and `variant_label` set to null
- **THEN** both properties are null on the mapped object
- **AND** mapping neither throws nor substitutes a default value

#### Scenario: Over-retrieval is reported, not truncated
- **WHEN** the service returns more candidates than the requested `top_k`
- **THEN** the client returns every candidate it received
- **AND** `candidates_returned` reports the same count the service reported

### Requirement: Every gateway call carries a real point-of-sale scope

Every call to the gateway SHALL carry a call scope holding the user identifier, the role and the point-of-sale identifier. The scope type MUST expose a single construction path that requires a concrete point of sale, and MUST reject an empty point-of-sale identifier and a blank role. There MUST be no construction path producing a scope without a point of sale, and no sentinel value MUST be accepted in its place. The client MUST NOT perform authorization: the caller is responsible for having validated the user's assignment to that point of sale before constructing the scope.

#### Scenario: Scope requires a concrete point of sale
- **WHEN** code attempts to build a call scope with an empty point-of-sale identifier
- **THEN** construction fails with an argument error
- **AND** no alternative construction path exists that omits the point of sale

#### Scenario: Blank role is rejected
- **WHEN** code attempts to build a call scope with a blank role
- **THEN** construction fails with an argument error

### Requirement: Internal service token carries the frozen claims and nothing else

The client SHALL sign an internal service token with HS256 using a secret dedicated to this integration, separate from the user-facing signing key. The payload MUST contain exactly the four claims frozen by the AI service in `snake_case`: `user_id`, `role`, `pos_id` and `trace_id`, each non-empty. It MUST contain an expiry derived from the configured time-to-live. It MUST NOT contain an audience claim, an issuer claim or a not-before claim, because the service validates tokens without expecting an audience and evaluates temporal claims with no clock tolerance. The token MUST be presented as a bearer credential on every request.

#### Scenario: Token carries the four frozen claims
- **WHEN** the client signs a token for a valid call scope
- **THEN** the payload contains `user_id`, `role`, `pos_id` and `trace_id` under exactly those names
- **AND** none of the four is empty

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

### Requirement: Contract failure modes are distinguishable by the caller

The client SHALL translate every documented outcome of the frozen contract into a distinguishable result, so a caller can decide whether to degrade, to surface a configuration fault or to stop. HTTP 401 MUST surface as a configuration fault, because the AI service is required to reject invalid tokens without disclosing the cause and the only actionable interpretation on this side is misconfiguration. HTTP 501 MUST surface as a not-implemented outcome, distinct from unavailability, because the contract uses it for routes whose real logic arrives in a later change. Timeouts, transport failures, HTTP 408, HTTP 5xx other than 501, and an open circuit MUST all surface as service unavailability. The client MUST NOT surface a raw transport exception to its caller.

#### Scenario: Authentication failure is reported as configuration fault
- **WHEN** the AI service answers HTTP 401
- **THEN** the client raises a configuration fault distinct from unavailability
- **AND** the failure is logged at error level

#### Scenario: Unimplemented route is reported as such
- **WHEN** the AI service answers HTTP 501
- **THEN** the client raises a not-implemented outcome distinct from unavailability

#### Scenario: Timeout is reported as unavailability
- **WHEN** the AI service does not answer within the configured time budget
- **THEN** the client raises service unavailability

#### Scenario: Transport failure is reported as unavailability
- **WHEN** the request fails at the transport level
- **THEN** the client raises service unavailability
- **AND** no raw transport exception reaches the caller

### Requirement: Retry policy never retries a permanent condition

The client SHALL retry at most once, and only for conditions that can plausibly succeed on a second attempt: transport failures, timeouts, HTTP 408 and HTTP 5xx other than 501. It MUST NOT retry HTTP 401, which reflects configuration rather than a transient fault. It MUST NOT retry HTTP 501, which reflects a route that has no implementation yet. Retrying either would consume the request time budget with no possibility of success.

#### Scenario: Transient server error is retried once
- **WHEN** the AI service answers HTTP 503 on the first attempt and HTTP 200 on the second
- **THEN** the client returns the mapped response
- **AND** exactly two HTTP requests were issued

#### Scenario: Unimplemented route is not retried
- **WHEN** the AI service answers HTTP 501
- **THEN** exactly one HTTP request was issued

#### Scenario: Authentication failure is not retried
- **WHEN** the AI service answers HTTP 401
- **THEN** exactly one HTTP request was issued

### Requirement: Degradation is bounded per call and isolated per route family

Each gateway call SHALL be bounded by a configured time budget, at most one retry and a circuit breaker with explicitly configured thresholds. Default resilience presets MUST NOT be accepted unconfigured, because their default time budget and retry count contradict the agreed limits. Retrieval MUST use its own named client and its own circuit breaker state, isolated from any future generative route, so that a slow generative call cannot open the retrieval circuit and cannot trigger the caller's degraded path for a service that is answering correctly. While the circuit is open, the client MUST fail immediately without issuing an HTTP request.

#### Scenario: Open circuit fails fast without a request
- **WHEN** the retrieval circuit breaker is open and a retrieval call is made
- **THEN** the client raises service unavailability
- **AND** no HTTP request is issued

#### Scenario: Retrieval resilience is configured explicitly
- **WHEN** the retrieval client is registered
- **THEN** its time budget, retry count and circuit breaker thresholds come from configuration rather than from framework defaults

### Requirement: Gateway calls are traceable end to end

Every gateway call SHALL carry a correlation identifier obtained from the ambient request context, propagated both as the `trace_id` claim of the service token and as a request header, so the same call can be followed through the logs of both services including responses the service rejects before reaching a handler. Each call MUST emit a start event, and either a completion event or a failure event. The completion event MUST carry the endpoint, correlation identifier, status code, elapsed milliseconds, attempt count, `candidates_returned`, result count and `low_confidence`. The failure event MUST carry the endpoint, correlation identifier, elapsed milliseconds, attempt count, a classified outcome and the configured base address. The query text MUST NOT be emitted above debug level.

#### Scenario: Correlation identifier travels in claim and header
- **WHEN** the client issues a retrieval request with a known correlation identifier
- **THEN** the service token carries it as the `trace_id` claim
- **AND** the request carries it as a header

#### Scenario: Completed call is observable
- **WHEN** a retrieval call completes successfully
- **THEN** a completion event is emitted carrying the correlation identifier, elapsed milliseconds, attempt count and the returned candidate count

#### Scenario: Failed call records where it was pointing
- **WHEN** a retrieval call fails
- **THEN** a failure event is emitted carrying the classified outcome and the configured base address

#### Scenario: Query text stays out of production logs
- **WHEN** a retrieval call is logged at information level or above
- **THEN** the operator's query text does not appear in the emitted event

### Requirement: Gateway configuration is validated at application start

The gateway configuration SHALL be bound to a strongly-typed options object and validated during application startup, before the first request is served. Validation MUST require an absolute base address, a non-empty signing secret long enough for HS256, and positive time-to-live and time budgets. A failure MUST prevent the application from starting and MUST name the offending configuration key. Lazy validation is insufficient, because it would surface the fault inside a request instead of at startup, which is the failure mode this requirement exists to remove.

#### Scenario: Missing secret prevents startup
- **WHEN** the application starts without the gateway signing secret configured
- **THEN** startup fails
- **AND** the error names the missing configuration key

#### Scenario: Non-absolute base address prevents startup
- **WHEN** the configured base address is not an absolute URI
- **THEN** startup fails
- **AND** the error names the offending configuration key

### Requirement: Client models cannot drift from the committed contract

An automated test SHALL compare the client's retrieval models against the committed `ai-service/openapi.json`, so that a renegotiated contract breaks the .NET build as well as the Python one. The test MUST verify that every property of the retrieval request, result and response models exists in the committed schema under the same name and with the same nullability. Without this guard, a contract change would leave the .NET build green and surface at runtime as a silently missing value.

#### Scenario: Models match the committed schema
- **WHEN** the contract test runs against an unmodified working tree
- **THEN** every retrieval model property is present in the committed schema with the same name and nullability

#### Scenario: Contract drift breaks the build
- **WHEN** the committed schema changes a retrieval property name or nullability and the client models are not updated
- **THEN** the contract test fails

### Requirement: Gateway tests run in process without the AI service

The test suite for this integration SHALL exercise mapping, token emission, resilience and failure translation with a fake HTTP message handler, and MUST NOT require the `jbg-ai` container, network access or an AI provider. Time-dependent behavior MUST be driven by an injected time abstraction rather than by real waiting.

#### Scenario: Suite passes with the AI service stopped
- **WHEN** the backend test suite runs with `jbg-ai` not running and no network access
- **THEN** the gateway tests pass
- **AND** no real HTTP request leaves the test process
