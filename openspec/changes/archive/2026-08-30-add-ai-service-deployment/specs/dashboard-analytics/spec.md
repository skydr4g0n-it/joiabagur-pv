# dashboard-analytics Specification

## ADDED Requirements

### Requirement: Administrator AI Service Status Card

The system SHALL display, on the Administrator dashboard only, a status card for the AI service reporting database reachability, the number of indexed documents, whether the embedding provider credential is configured, and whether the configured embedding model agrees with the indexed one.

The browser cannot query the AI service directly — it is private by design and publishes no port — so the card MUST be served by a backend endpoint that proxies the AI service health probe. That endpoint MUST be restricted to administrators and MUST NOT expose connection strings, database hostnames or any fragment of a credential.

The probe MUST NOT share the circuit breaker used by the assisted search gateway: its purpose is to diagnose the system precisely when the main path is failing, so an open circuit MUST NOT prevent the card from reporting.

#### Scenario: Administrator sees the AI service status card

- **WHEN** an authenticated administrator views the dashboard
- **THEN** the system displays an AI service status card
- **AND** the card shows whether the database is reachable
- **AND** the card shows the number of indexed documents
- **AND** the card shows whether the provider credential is configured

#### Scenario: Operator does not see the AI service status card

- **WHEN** an authenticated operator views the dashboard
- **THEN** no AI service status card is displayed

#### Scenario: The status endpoint rejects non-administrators

- **WHEN** an authenticated operator requests the AI service status endpoint directly
- **THEN** the request is rejected as forbidden

#### Scenario: The status endpoint rejects anonymous callers

- **WHEN** an unauthenticated client requests the AI service status endpoint
- **THEN** the request is rejected as unauthorised

#### Scenario: A model mismatch is presented as an error state

- **GIVEN** the AI service reports that the configured embedding model disagrees with the indexed one
- **WHEN** an authenticated administrator views the dashboard
- **THEN** the card presents the condition as an error rather than a healthy state
- **AND** the card names the discrepancy in text, not by colour alone

#### Scenario: The card reports while the assisted search circuit is open

- **GIVEN** the assisted search gateway circuit breaker is open
- **WHEN** an authenticated administrator views the dashboard
- **THEN** the AI service status card still reports the state of the service
- **AND** the card is not blocked by the open circuit

#### Scenario: The status response leaks no credential or connection detail

- **WHEN** the AI service status endpoint returns a response
- **THEN** the body contains no database connection string
- **AND** the body contains no database hostname
- **AND** the body contains no fragment of any API key or signing secret

#### Scenario: An unreachable AI service is reported rather than hidden

- **GIVEN** the AI service does not respond within the probe timeout
- **WHEN** an authenticated administrator views the dashboard
- **THEN** the card reports the AI service as unreachable
- **AND** the remainder of the dashboard continues to render
