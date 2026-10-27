## MODIFIED Requirements

### Requirement: ML Model Storage and Distribution

The backend SHALL keep existing ML model files and ModelMetadata rows. It SHALL NOT serve, accept, or mutate them through `/api/image-recognition`. Authenticated requests to that API SHALL receive 410 Gone. The implementation types remain in the codebase and SHALL be marked deprecated. This change SHALL NOT add a migration that deletes model storage.

#### Scenario: Authenticated model route is withdrawn
- **GIVEN** an authenticated caller
- **WHEN** the caller requests model metadata, model files, model versions, upload, or retrain under `/api/image-recognition`
- **THEN** the response status is 410 Gone
- **AND** model files are not written or deleted by that request

#### Scenario: Stored model history remains
- **GIVEN** ModelMetadata rows and stored model files from earlier uploads
- **WHEN** this change is deployed
- **THEN** those rows and files are left in place
- **AND** no admin screen lists them

#### Scenario: Deprecated marker is present
- **GIVEN** the image-recognition controller and its application service interfaces
- **WHEN** a developer inspects those types
- **THEN** each is marked obsolete with a message that product-photo image recognition is withdrawn
- **AND** the method bodies remain in source
