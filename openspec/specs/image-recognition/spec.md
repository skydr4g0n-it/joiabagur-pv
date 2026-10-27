# image-recognition Specification

## Purpose

Product-photo image recognition has been withdrawn. The API reports withdrawal; the client no longer offers recognition, training, or model-health surfaces.

## Requirements

### Requirement: Withdrawn product-photo recognition
The system SHALL NOT offer product-photo image recognition in the user interface. The system SHALL NOT show model-health warnings, an AI-model admin page, or a sales flow that captures a photo to suggest products. Every HTTP route under `/api/image-recognition` SHALL respond that the capability is withdrawn and SHALL NOT execute the previous model, health, training, or embedding behavior.

#### Scenario: Administrator session shows no model warning
- **GIVEN** an authenticated administrator
- **WHEN** the administrator opens the application
- **THEN** the interface does not request model health
- **AND** the interface does not show a toast about the AI model

#### Scenario: Retired routes are absent
- **GIVEN** an authenticated user
- **WHEN** the user opens `/admin/ai-model` or `/sales/new/image`
- **THEN** the application does not render a recognition page
- **AND** the existing unmatched-route rule navigates to `/dashboard`
- **AND** the sidebar does not contain an entry named "Modelo de IA"

#### Scenario: Authenticated API call is withdrawn
- **GIVEN** an authenticated caller
- **WHEN** the caller requests any route under `/api/image-recognition`, including model metadata, model health, model versions, model files, retrain, training dataset, class labels, and embeddings
- **THEN** the response status is 410 Gone
- **AND** the response body states that product-photo image recognition is withdrawn
- **AND** the handler does not read or write model files, embeddings, or training jobs

#### Scenario: Unauthenticated API call stays unauthorized
- **GIVEN** a caller without a valid access token
- **WHEN** the caller requests any route under `/api/image-recognition`
- **THEN** the response status is 401 Unauthorized

#### Scenario: Integration coverage of the withdrawn API
- **GIVEN** the image-recognition integration tests
- **WHEN** those tests call representative routes, including `GET /api/image-recognition/model/health` and `GET /api/image-recognition/embeddings`
- **THEN** authenticated calls assert status 410
- **AND** unauthenticated calls assert status 401
