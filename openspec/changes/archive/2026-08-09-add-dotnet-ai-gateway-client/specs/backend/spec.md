## MODIFIED Requirements

### Requirement: Structured Logging

The backend SHALL implement structured logging using Serilog, capturing relevant context and supporting multiple output targets. The rendering of those events SHALL depend on the deployment environment: a human-readable console rendering under a development profile, and one JSON object per event under a production profile, so that emitted events are ingestible by an observability platform without parsing free text. Named properties of a log event MUST be emitted as fields rather than embedded in a rendered sentence. Correlation SHALL cover outbound calls to other services, not only inbound requests: a call the backend makes to another service MUST be attributable to the same correlation identifier as the request that caused it.

#### Scenario: Request Logging
- **WHEN** API request is processed
- **THEN** request details are logged with correlation ID
- **AND** response status and duration are captured

#### Scenario: Error Logging
- **WHEN** exception occurs
- **THEN** full exception details and context are logged
- **AND** sensitive information is redacted

#### Scenario: Environment-dependent rendering
- **WHEN** the application emits a log event under a development profile
- **THEN** the output is the human-readable console rendering
- **AND** under a production profile the same event is emitted as a single-line JSON object
- **AND** the event's named properties appear as fields, not embedded in a rendered sentence

#### Scenario: Outbound Call Logging
- **WHEN** the backend calls another service on behalf of an inbound request
- **THEN** the outbound call is logged with the same correlation ID as that request
- **AND** its outcome and duration are captured
