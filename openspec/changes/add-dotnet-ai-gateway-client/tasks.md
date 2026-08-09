## 1. Dependencies and configuration

- [ ] 1.1 Add `Microsoft.Extensions.Http`, `Microsoft.Extensions.Http.Resilience` and `Microsoft.Extensions.Options.ConfigurationExtensions` to `JoiabagurPV.Application.csproj`, pinning versions compatible with the target framework
- [ ] 1.2 Add `Serilog.Formatting.Compact` to `JoiabagurPV.API.csproj`
- [ ] 1.3 Create `Application/Configuration/AiGatewayOptions.cs` with `BaseUrl`, `JwtSecret`, `TokenTtlSeconds` (300), `RetrievalTimeoutMs` (800), `AssistTimeoutMs` (5000) and `Enabled`
- [ ] 1.4 Add the `AiGateway` section to `API/appsettings.json` with `BaseUrl` = `http://localhost:8001` and `JwtSecret` matching the value in `backend/docker-compose.yml` **literally**, with a comment explaining that the .NET API runs on the host and only sees the published port
- [ ] 1.5 Verify `dotnet build` succeeds with the new package references before writing any consuming code

## 2. Transport models for the frozen contract

- [ ] 2.1 Create `Application/DTOs/Ai/` with `AiSearchRequest` (`query`, `top_k`, `filters`, `mode`) and `AiSearchFilters` (`materials`, `category`, `family_id`, `exclude_product_ids`), deliberately omitting `pos_id` from the request
- [ ] 2.2 Create `AiSearchResult` (`product_id`, `sku`, `score`, `match_reasons`, `materials`, nullable `family_id`, nullable `variant_label`, optional `debug`) and `AiDebugInfo`
- [ ] 2.3 Create `AiSearchResponse` (`results`, `candidates_returned`, `low_confidence`, `trace_id`, `effective_pos_id`)
- [ ] 2.4 Centralise a single `JsonSerializerOptions` with a `snake_case` naming policy, without per-property attributes
- [ ] 2.5 Cross-check every property name and nullability against `ai-service/src/jbg_ai/api/schemas/retrieval.py` and `common.py`, and confirm the models compile

## 3. Call scope

- [ ] 3.1 Create `Application/DTOs/Ai/AiCallScope.cs` carrying user identifier, role and point-of-sale identifier
- [ ] 3.2 Expose `ForPointOfSale(userId, role, pointOfSaleId)` as the only construction path, rejecting an empty point-of-sale identifier and a blank role
- [ ] 3.3 Document in code that the scope authorises nothing: the caller has already validated the assignment against `UserPointOfSale`
- [ ] 3.4 Add `ForPointOfSale_WhenPointOfSaleIsEmpty_ThrowsArgumentException` and its blank-role counterpart, and confirm both pass

## 4. Internal service token

- [ ] 4.1 Create `Application/Interfaces/IAiServiceTokenFactory.cs` and `Application/Services/AiServiceTokenFactory.cs` signing HS256 with `AiGateway:JwtSecret`
- [ ] 4.2 Emit exactly `user_id`, `role`, `pos_id`, `trace_id` and `exp`, with the claim names written literally in `snake_case`
- [ ] 4.3 Ensure no audience, issuer or not-before claim is emitted, and inject `TimeProvider` so the expiry is testable without waiting
- [ ] 4.4 Add `BuildToken_IncludesPosAndRoleClaims`, `BuildToken_UsesSnakeCaseClaimNames`, `BuildToken_OmitsAudienceAndIssuer` and `BuildToken_ExpiresAfterConfiguredTtl`, decoding the payload to assert the exact claim set

## 5. Trace correlation

- [ ] 5.1 Create `Application/Interfaces/ITraceContextAccessor.cs` exposing the current correlation identifier
- [ ] 5.2 Implement it in `API/Services/TraceContextAccessor.cs` from `Activity.Current` with the HTTP context identifier as fallback, following the `CurrentUserService` precedent
- [ ] 5.3 Register the accessor in `API/Extensions/ServiceCollectionExtensions.cs` and confirm the API still starts

## 6. Gateway client

- [ ] 6.1 Create `Application/Exceptions/` with `AiGatewayException` and the three derived types for unavailability, not-implemented and configuration fault
- [ ] 6.2 Create `Application/Interfaces/IAiGatewayClient.cs` exposing `SearchAsync(request, scope, cancellationToken)`
- [ ] 6.3 Implement `Application/Services/AiGatewayClient.cs`: sign the token, set the bearer header and the trace header, post to `/v1/retrieval/products`, deserialize the response without truncating the candidate list
- [ ] 6.4 Implement the failure translation: 401 to configuration fault, 501 to not-implemented, 408 and 5xx other than 501 plus timeouts, transport failures and open circuit to unavailability; never let a raw transport exception escape
- [ ] 6.5 Confirm the project builds and that no call path returns an undeclared exception type

## 7. Resilience and dependency injection

- [ ] 7.1 Create `Application/Extensions/AiGatewayServiceCollectionExtensions.cs` with `AddAiGateway(IConfiguration)`, binding options and applying `Validate(...).ValidateOnStart()` for absolute base address, non-empty secret of sufficient length, and positive lifetime and budgets
- [ ] 7.2 Register the `ai-retrieval` named client with base address and a 0.8 s time budget
- [ ] 7.3 Configure the resilience pipeline explicitly: single retry with a whitelist predicate that excludes 501 and 401, and a circuit breaker with explicit thresholds — do not use the unconfigured standard handler
- [ ] 7.4 Leave a documented slot for the future generative named client with its own breaker, to be filled by C34
- [ ] 7.5 Call `AddAiGateway(builder.Configuration)` from `Program.cs` as its own line, leaving the `AddApplication()` signature untouched
- [ ] 7.6 Add `AddAiGateway_WhenSecretMissing_FailsOnStart`, and run the existing integration suite to confirm `WebApplicationFactory` still boots with startup validation active

## 8. Structured logging

- [ ] 8.1 Emit `ai_gateway_call_started`, `ai_gateway_call_completed` and `ai_gateway_call_failed` with the fields defined in the spec, using `BeginScope` to bind endpoint and correlation identifier once per call
- [ ] 8.2 Include `base_url` on the failure event only, and keep the operator's query text at debug level
- [ ] 8.3 Create `API/appsettings.Production.json` with the Serilog section rendering through `CompactJsonFormatter`, using the keyed sink form so the override replaces the console entry cleanly instead of merging by array index
- [ ] 8.4 Verify manually: start with the production environment profile and confirm the output is one JSON object per event with named properties as fields

## 9. Test infrastructure and unit tests

- [ ] 9.1 Create `Tests/TestHelpers/FakeHttpMessageHandler.cs` with a queue of programmed responses and a counter of issued requests, reusable by C12, C15 and C34
- [ ] 9.2 Create `Tests/UnitTests/Application/AiGatewayClientTests.cs` with `SearchAsync_WhenServiceReturns200_MapsResponse` and `SearchAsync_WhenFamilyIdIsNull_MapsToNullWithoutThrowing`
- [ ] 9.3 Add `SearchAsync_SendsBearerTokenAndTraceHeader`, asserting both the header and the claim carry the same identifier
- [ ] 9.4 Add `SearchAsync_WhenTimeout_ThrowsAiUnavailable` and `SearchAsync_WhenCircuitOpen_FailsFastWithoutCall`, configuring low breaker thresholds in the test pipeline or forcing the state — a naive two-failure test passes without the circuit ever opening
- [ ] 9.5 Add `SearchAsync_WhenServiceReturns501_DoesNotRetryAndThrowsNotImplemented`, `SearchAsync_WhenServiceReturns401_DoesNotRetry` and `SearchAsync_WhenServiceReturns503_RetriesOnceThenSucceeds`, asserting the issued-request count in each
- [ ] 9.6 Confirm the whole suite passes with `jbg-ai` stopped and no network access

## 10. Contract drift guard

- [ ] 10.1 Create `Tests/TestHelpers/RepositoryRoot.cs` walking up from the test assembly location to a repository marker, mirroring the Python side's path helper
- [ ] 10.2 Create `Tests/UnitTests/Application/AiContractSnapshotTests.cs` with `Dtos_MatchCommittedOpenApiSchema`, asserting name and nullability of every retrieval model property against the committed `ai-service/openapi.json`
- [ ] 10.3 Verify the guard bites: temporarily rename a property, confirm the test fails, then revert

## 11. Verification and documentation

- [ ] 11.1 Run `dotnet build` and `dotnet test` from `backend/src/`, confirming no regression in the existing suite
- [ ] 11.2 Optional end-to-end smoke: `docker compose up jbg-ai`, confirm `/health` answers, then exercise `SearchAsync` and check that `top_k = 5` yields 15 candidates per the stub's over-retrieval rule
- [ ] 11.3 Confirm `ai-service/` is untouched and `ai-service/openapi.json` is unmodified in the diff
- [ ] 11.4 Run `openspec validate --all --strict` and require `0 failed` — the `--all` form, because this change carries a delta over a live spec
- [ ] 11.5 Update the affected documentation in `Documentos/` per the post-implementation table in `openspec/project.md`, and mark HU-AIENG-003 as done in `Documentos/epicas.md`
