## Context

C02 (`add-ai-service-contracts-and-auth`, archived) froze eight `/v1` routes on `jbg-ai` with complete Pydantic models, deterministic stubs, a versioned `ai-service/openapi.json` and an HS256 service token requiring four `snake_case` claims. Nothing calls it yet.

On the .NET side there is nothing to build on. Verified in the repository: the backend has **no outbound HTTP client at all**, no Polly, no `Microsoft.Extensions.Http`, and no trace correlation (`Activity` and `TraceIdentifier` appear nowhere in `backend/src/`). `ICurrentUserService` exposes user, username, role and admin flag but **no point of sale**. `JwtTokenService` signs user tokens with issuer and audience against a different secret.

This change is Ola 0 / C03 / HU-AIENG-003 / T-AIENG-003. It is the last piece of the wave and sits on the critical path: C15 cannot start without it, and C16, C17 and C34 follow C15. Because it is the first of its kind, every pattern chosen here is inherited by C12, C15 and C34 — the cost of a sloppy decision is paid three times over.

**The diagnostic constraint that shapes the design.** The `ai-service-auth` capability requires `jbg-ai` to reject any doubtful token with an HTTP 401 that discloses neither the secret nor which validation step failed. That is correct security and hostile debugging: a mistyped secret, an extra claim and a clock skew all produce the same silent symptom. Several decisions below exist specifically to remove causes of that 401 before they can happen.

**Stakeholders:** the two Proyecto Final developers. No end-user surface: the operator sees nothing from this change.

## Goals / Non-Goals

**Goals:**

- A typed client with one operation, `SearchAsync` against `POST /v1/retrieval/products`, mapping the frozen contract faithfully including its explicit nulls
- A call scope that cannot be constructed without a real point of sale
- Correct emission of the internal service token, including the claims the AI service requires and — just as important — the claims it must not receive
- Bounded degradation: time budget, single retry, circuit breaker, isolated per route family
- Failure modes the caller can branch on: unavailable, not implemented, misconfigured
- End-to-end correlation across the .NET → Python hop, in the token claim and in a header
- Structured, environment-appropriate observability with no operator query text in production logs
- Configuration validated at startup, not on first use
- A .NET-side guard against contract drift, reciprocal to the Python snapshot test
- `dotnet build` and `dotnet test` green with `jbg-ai` stopped and no network access

**Non-Goals:**

- `AiController`, `POST /api/ai/search`, price and stock hydration, dropping candidates after hydration, refetching with a larger `top_k`, lexical fallback and per-POS feature flag — all C15
- The other seven contracted endpoints; the client grows in the change that consumes each one (C34, C13, C08)
- Signing a token **without** a point of sale, needed by catalog-wide routes — the first of C08 or C13 to need it
- `ProductAiProfile` (C08), index feeds (C12), schema `ai` (C05)
- Any change to `ai-service/` or to `ai-service/openapi.json` — this change is a consumer of the frozen contract
- EF Core migration, data model changes, frontend work
- Deployment, production base address, SSM parameters and container networking — C17

## Decisions

### 1. One operation now; the client's surface grows with its consumers

- **Choice:** expose only `SearchAsync`. Every other contracted endpoint is added by the change that first calls it.
- **Why:** C02 froze its contract wide with a sound argument — reopening a *wire* contract costs a negotiation between two developers. That argument does not transfer to a C# method, which is added in a small diff with nobody to negotiate with. Mapping all eight endpoints now would produce roughly twenty-five transport models, half without a consumer until Ola 4, inside a critical-path change that must fit one session.
- **Alternatives discarded:** mirror all eight endpoints for symmetry with `openapi.json` (dead code with real review cost, and the session overruns); ship retrieval plus substitutes as one "domain" (substitutes has no consumer until C26/C34).

### 2. The client lives in `Application`, and the layering forces it

- **Choice:** interfaces, transport models and implementation in `JoiabagurPV.Application`.
- **Why:** instinct says `Infrastructure` — it is outbound I/O, and the closest precedent is `S3FileStorageService`. But `JoiabagurPV.Infrastructure.csproj` references **only** `Domain`, so an implementation there would force `IAiGatewayClient` and its models up into `Domain`. A retrieval result carrying `match_reasons` and `variant_label` is not jewellery domain. Precedents already in `Application`: `ImageRecognitionService`, `JwtTokenService`.
- **Trade-off accepted:** `Application` gains HTTP client and resilience packages, which reads as infrastructure leaking into the application layer. Recorded explicitly because the next reader will try to "fix" it toward `Infrastructure` and hit a circular reference.

### 3. `AiCallScope` with a single factory — the sentinel problem solved by construction

- **Choice:** a small scope type carrying user, role and point of sale, constructible only through `ForPointOfSale(...)`, which rejects an empty identifier and a blank role.
- **Why:** the contract requires `pos_id` on all eight routes, but catalog enrichment and index sync have no point of sale. Whoever needs those routes first will be tempted to pass `"*"` or `"system"` — and from C22 onward `pos_id` from the token becomes the **only hard filter** of the retriever. A sentinel reaching that filter is a cross-POS leak wearing a convenience-parameter costume. Making the illegal state unconstructible is cheaper and more durable than a comment asking people not to do it.
- **Alternatives discarded:** accept a sentinel now and document it (defers a security-shaped bug to the change least equipped to notice it); make `pos_id` optional in Python now (correct long-term, but it is Python-zone work with its own spec and tests inside a change labelled ".NET" on the critical path).
- **Consequence:** the open question moves, with a named owner, to the first of C08 or C13 — which must add the new factory **and**, in the same change, the Python-side rule preventing that scope from reaching POS-scoped routes.

### 4. A dedicated token factory that emits fewer claims, not more

- **Choice:** a separate factory signing HS256 with `AiGateway:JwtSecret`, emitting exactly `user_id`, `role`, `pos_id`, `trace_id` and `exp`, with an injected `TimeProvider`. No audience, no issuer, no not-before.
- **Why:** three verified traps converge here. `jbg-ai` calls `jwt.decode(...)` without an `audience` argument, and PyJWT rejects a token that *does* declare `aud` when the validator expects none — producing the opaque 401 the spec forbids explaining. PyJWT also validates `iat` and `nbf` with zero leeway, so a few seconds of clock skew between containers can make a freshly issued token look like it comes from the future. And reusing `JwtTokenService` would drag issuer and audience in by default, since that is how it signs user tokens.
- **Alternatives discarded:** reuse `JwtTokenService` with a parameter (different secret, different claims, different lifetime, different recipient — the sharing buys nothing and imports the audience bug); accept both `pos_id` and `pointOfSaleId` spellings (doubles the surface while there is exactly one issuer).
- **Verification:** `BuildToken_OmitsAudienceAndIssuer` is not a stylistic test; it is the guard against a failure mode that produces no usable diagnostic anywhere in the stack.

### 5. `Microsoft.Extensions.Http.Resilience` with an explicit pipeline, never the standard preset

- **Choice:** Polly v8 through the Microsoft resilience package, with time budget, retry count and breaker thresholds all set explicitly.
- **Why:** it is the idiomatic option on this framework version, and `AddPolicyHandler` is the previous generation. But `AddStandardResilienceHandler()` unconfigured brings a 30-second total budget and three retries, which contradicts the agreed 0.8 s and single retry. Accepting the preset would silently replace the design.
- **Alternatives discarded:** `Polly.Extensions.Http` with `AddPolicyHandler` (older pattern, kept as documented fallback only if the modern package cannot be pinned to this framework version); hand-rolled retry and timeout (re-implements a solved problem, badly).

### 6. Two named clients so a slow generative route cannot kill search

- **Choice:** a named client for retrieval with its own breaker state, and a prepared slot for a generative client in C34.
- **Why:** the two route families have different time budgets — 0.8 s versus 5 s — and one `HttpClient` cannot hold two. That is the mechanical reason. The design reason is stronger: a shared breaker means a slow language model opens the retrieval circuit, and C15's lexical fallback fires for a service that is answering correctly. The operator loses semantic search because of a problem that was not theirs.
- **Alternatives discarded:** one client with a per-request cancellation budget (shares the breaker — wrong for the reason above); two full typed clients with two interfaces (the caller should not choose a transport; one interface, two named clients behind it).

### 7. The retry predicate is a whitelist, not "any server error"

- **Choice:** retry transport failures, timeouts, HTTP 408 and HTTP 5xx **except 501**. Never 401, never 501.
- **Why:** C02 chose 501 over 503 for unimplemented routes precisely so that a resilient client would not insist: *"503 implies transient, invites retries — Polly would retry a permanent condition"*. A generic `IsServerError` predicate breaks that decision in the client's first line of code. HTTP 401 is configuration: retrying it with the same wrong secret repeats the failure and burns the request budget. This mirrors the error-typed fallback strategy from the course material — credentials are not retried, timeouts are.
- **Alternatives discarded:** the framework's default transient-error predicate (includes 501, contradicting C02); no retry at all (loses cheap recovery from a genuine blip on a hop-to-hop call).

### 8. Typed exceptions rather than a result type

- **Choice:** an exception hierarchy with a common base, distinguishing unavailability, not-implemented and configuration fault.
- **Why:** C15 has a single call site, so the `try/catch` is local and cheap, and the test names are already agreed with the other developer in the plan's C03 card.
- **Trade-off accepted, and stated plainly:** "circuit open" is an *expected* operating mode, not an exceptional one, and using exceptions for expected control flow has a bad smell. A result type would model it more honestly. The cost of switching later is one call site.

### 9. Configuration bound and validated at startup, with the values living where the environment expects them

- **Choice:** `IOptions<AiGatewayOptions>` with `Validate(...).ValidateOnStart()`. Development values in `appsettings.json`; production values as environment variables sourced from the parameter store.
- **Why:** `ValidateOnStart()` is the whole point — plain `IOptions` validation is lazy and would surface the fault inside a request, which is exactly the failure mode of today's `JwtTokenService`, whose constructor throws on first resolution. Failing at boot with the key name turns a long hunt into a log line. This also brings the code in line with the live `backend` spec, which already requires strongly-typed options with validation. The environment split follows the verified deploy path: production injects `__`-separated environment variables read from the parameter store and uses no configuration files.
- **Known limit, not papered over:** startup validation catches *absent* and *malformed*, not *present but wrong*. A missing production base address would fall back to the development value, pass validation as a legal absolute URI, and fail later with a refused connection. Mitigation here: the failure event carries the configured base address, so the log says where it was pointing. Definitive mitigation: the enriched health endpoint C17 delivers.

### 10. Observability split along the boundary it describes

- **Choice:** `ILogger<T>` with semantic templates and `BeginScope`; three events per call; JSON rendering under a production profile. Requirements split between two capabilities: the hop-specific ones (`trace_id` in claim and header, the three events, query text confined to debug) in `ai-gateway-client`; the global rendering and outbound correlation as a `MODIFIED` delta on the existing `Structured Logging` requirement of `backend`.
- **Why:** `ILogger` plus Serilog is already the house pattern across some twenty services, and `BeginScope` is the direct equivalent of the `bind()` idiom from the course material, with no new abstraction. On the capability question, the deciding fact is that `backend` **already** requires structured logging "supporting multiple output targets" and **already** specifies a correlation-ID scenario that is not implemented — so JSON output fulfils an existing requirement rather than adding one, and this change is the first to reduce that drift. A separate `backend-observability` capability would split one topic across two homes and worsen discoverability; treating it as pure implementation detail would leave the drift untouched and let a later change revert the format with no failing test.
- **Alternatives discarded:** Serilog's static API (`Log.ForContext<T>()`) — more expressive, but couples `Application` to Serilog and breaks the convention of every existing service; OpenTelemetry with an OTLP exporter — the right long-term answer for a single trace spanning both services, and what the observability tooling discussed in the course sits on, but it is packages, an exporter and probably a collector: its own change, naturally C17 or C39; an `AiUsageLog` entity — dropped by design v3, and inapplicable here since C03 calls no language model and has no tokens or cost to record.
- **Operational note:** because this carries a delta over a live spec, `openspec validate --all --strict` must be run before archiving, not just the single-change form.

### 11. A .NET-side contract test, reciprocal to the Python snapshot

- **Choice:** a test reading the committed `ai-service/openapi.json` from the repository root and asserting that every retrieval model property exists in the schema with the same name and nullability.
- **Why:** today the guard is one-sided. A renegotiated contract breaks the Python build and leaves the .NET build green, surfacing at runtime as a silently null value. Making both builds fail is what turns "contract drift" into "explicit negotiation", which was C02's whole intent.
- **Alternatives discarded:** copying a stub response into a local fixture (catches today's mapping mistakes but ages silently — the local copy keeps passing after the real contract moves).

## Request flow

```mermaid
sequenceDiagram
    participant C15 as Caller (C15, later)
    participant CL as AiGatewayClient
    participant TF as AiServiceTokenFactory
    participant RP as Resilience pipeline
    participant AI as jbg-ai /v1

    C15->>CL: SearchAsync(request, scope)
    Note over C15: scope built via ForPointOfSale;<br/>assignment already validated by the caller
    CL->>TF: sign(scope, traceId)
    TF-->>CL: HS256 JWT — user_id, role, pos_id, trace_id, exp<br/>no aud, no iss, no nbf
    CL->>RP: POST /v1/retrieval/products<br/>Bearer token + X-Trace-Id
    alt circuit open
        RP-->>CL: fail fast, no HTTP request
        CL-->>C15: AiUnavailableException (outcome: circuit_open)
    else request issued
        RP->>AI: HTTP request (budget 0.8 s)
        alt 200
            AI-->>RP: retrieval response
            RP-->>CL: 200
            CL-->>C15: mapped response (no truncation)
        else 401
            AI-->>RP: 401, cause deliberately undisclosed
            RP-->>CL: no retry
            CL-->>C15: AiGatewayConfigurationException (logged at error)
        else 501
            AI-->>RP: 501, implementation arrives in a later change
            RP-->>CL: no retry
            CL-->>C15: AiNotImplementedException
        else 408 / 5xx / timeout / transport
            RP->>AI: one retry
            AI-->>RP: still failing
            RP-->>CL: exhausted
            CL-->>C15: AiUnavailableException (outcome classified)
        end
    end
```

Hydration, truncation to `top_k`, refetching and the lexical fallback all happen to the right of `C15` and are out of scope here.

## Risks / Trade-offs

- **[Risk] The opaque 401 consumes hours of diagnosis** — the same symptom covers a wrong secret, an extra `aud` claim and clock skew → Mitigation: emit no audience, issuer or not-before; pin it with `BuildToken_OmitsAudienceAndIssuer`; fail fast at startup on missing configuration; carry `base_url` on the failure event.
- **[Risk] A generic retry predicate silently reverts C02's decision on 501** → Mitigation: whitelist predicate plus `SearchAsync_WhenServiceReturns501_DoesNotRetryAndThrowsNotImplemented`, which counts issued requests rather than asserting on the exception alone.
- **[Risk] The circuit breaker test passes without the circuit ever opening** — Polly v8 uses a sampling window and a minimum throughput, so two failures open nothing → Mitigation: explicitly low thresholds in the test pipeline, or force the state; the risk is called out in the ticket so nobody reads the green tick as coverage.
- **[Risk] The production base address does not resolve** — the deploy path runs `docker run` on the default bridge network, where container names have no DNS → Mitigation: recorded as a named prerequisite on C17 (user-defined network, both containers attached, AI port unpublished) in the ticket and the user story. C03 changes no infrastructure, so this cannot be closed here.
- **[Risk] Startup validation gives false confidence** — it cannot catch a stale but syntactically valid address → Mitigation: `base_url` on the failure event now; enriched health endpoint in C17.
- **[Trade-off] `Application` takes on HTTP and resilience packages** → Accepted; the alternative pushes AI transport models into `Domain` (decision 2).
- **[Trade-off] Exceptions model an expected degradation path** → Accepted with the reasoning in decision 7; one call site to change if it proves wrong.
- **[Trade-off] A single-method client will be reopened by later changes** → Accepted deliberately; there is no zone conflict, since `AiController` does not exist yet and C03 touches no file C15 will own.
- **[Trade-off] Delta over a live spec carries archive risk** → Accepted; mitigated by the full-requirement copy in the delta and by running `--all --strict` before archiving.

## Migration Plan

1. Land configuration and options with startup validation first, then transport models, scope and token factory — these have no interdependencies and can be written in any order.
2. Add the trace accessor in `Application` with its implementation in `API`, following the `ICurrentUserService` / `CurrentUserService` precedent.
3. Implement the client and its failure translation, then register the named client with the explicit resilience pipeline.
4. Add structured logging and the production JSON rendering, using the keyed form of the Serilog sink configuration so the production file replaces the console entry cleanly instead of merging by array index.
5. Add the fake message handler and the test suites, including the contract test against the committed schema.
6. Local verification: `dotnet build` and `dotnet test` with `jbg-ai` stopped. Optional end-to-end smoke: `docker compose up jbg-ai`, confirm `/health`, then a temporary call asserting 15 candidates for `top_k = 5` per the stub's over-retrieval rule.
7. **Partition point if the session overruns:** the client plus its unit tests already unblock C15; dependency-injection registration and structured logging can follow in a second pass.
8. **Rollback:** revert the `Application`, `API` and test additions and the `AiGateway` configuration section. Nothing to undo in production — the change deploys no infrastructure and no consumer exists yet.

## Open Questions

- None blocking implementation. The four questions the ticket opened are closed there: the deferred admin-scoped token with a named owner, the resilience package version, the keyed form of the Serilog sink override, and the capability placement of the logging format.
- **Named prerequisite on C17, not a question for this change:** the user-defined Docker network, the unpublished AI port and the two parameter-store entries. Without them the production base address will not resolve.
- **Deferred to the first of C08 or C13:** how a token is signed for catalog-wide routes that have no point of sale, and the Python-side rule that must accompany it.
- **Revisit in C34:** whether the generative route needs streaming. This design buffers responses; streaming would change the client's shape and is an explicit change of its own, not a silent evolution.
