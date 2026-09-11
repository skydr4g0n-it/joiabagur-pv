## MODIFIED Requirements

### Requirement: Evaluation endpoint exists only in the development profile

`GET /v1/evals/runs` MUST be mounted only when development endpoints are enabled. Under a production profile the route MUST NOT be registered at all.

Under a development profile it MUST answer HTTP 200 for an authenticated caller with the evaluation runs the harness has persisted, ordered most recent first, each carrying its identifier, its suite, its outcome, its start and end instants and its metrics. It MUST NOT answer 501 when stub mode is disabled: the route has a real implementation, and the placeholder that named a future change no longer applies.

When no run has been persisted, the route MUST answer 200 with an empty list, because "no evaluation has been run here" is a valid answer and is not an error.

The route's declared request and response models MUST NOT change, so the committed OpenAPI snapshot stays byte-for-byte identical.

#### Scenario: Evals route serves persisted runs in the development profile

- **WHEN** the application is built with development endpoints enabled and at least one evaluation run has been persisted
- **AND** an authenticated client calls `GET /v1/evals/runs`
- **THEN** the response status is 200
- **AND** the body contains the persisted runs with their metrics, most recent first

#### Scenario: An empty history is an empty list, not an error

- **WHEN** the application is built with development endpoints enabled and no evaluation run has been persisted
- **AND** an authenticated client calls `GET /v1/evals/runs`
- **THEN** the response status is 200
- **AND** the body contains an empty list of runs

#### Scenario: The route no longer answers 501 with stubs disabled

- **WHEN** `STUB_MODE` is disabled and an authenticated client calls `GET /v1/evals/runs` under a development profile
- **THEN** the response status is 200
- **AND** the response is not a placeholder naming a future change

#### Scenario: Evals route is absent in the production profile

- **WHEN** the application is built with a production profile
- **AND** an authenticated client calls `GET /v1/evals/runs`
- **THEN** the route is not mounted and the request is not served by an evals handler

#### Scenario: The contract snapshot is unchanged

- **WHEN** the OpenAPI snapshot test runs after the route gains its real implementation
- **THEN** the live schema equals the committed snapshot
