## MODIFIED Requirements

### Requirement: Backend Integration Tests for Embedding Endpoints

The system SHALL include integration tests for embedding API routes using `ApiWebApplicationFactory`, `TestDataMother`, and Respawn for database cleanup. Those tests SHALL assert that the routes are withdrawn.

#### Scenario: Authenticated embedding routes return 410
- **GIVEN** an authenticated client
- **WHEN** the client calls POST `/api/image-recognition/embeddings`, GET `/api/image-recognition/embeddings`, GET `/api/image-recognition/embeddings/status`, DELETE `/api/image-recognition/embeddings/{photoId}`, or DELETE `/api/image-recognition/embeddings`
- **THEN** each response status is 410 Gone
- **AND** the test does not expect a saved or deleted embedding from that call

#### Scenario: Unauthenticated embedding request returns 401
- **GIVEN** a client without a valid access token
- **WHEN** the client sends GET `/api/image-recognition/embeddings`
- **THEN** the response status is 401 Unauthorized

## REMOVED Requirements

### Requirement: Frontend Unit Tests for Cosine Similarity Function
**Reason**: The cosine-similarity client is removed.
**Migration**: Delete those frontend tests with the service.

### Requirement: Frontend Unit Tests for Similarity Inference
**Reason**: The inference client is removed.
**Migration**: Delete those frontend tests.

### Requirement: Frontend Unit Tests for Embeddings Index Caching
**Reason**: The client no longer caches an embeddings index.
**Migration**: Delete those frontend tests.

### Requirement: Frontend Unit Tests for Fallback Logic
**Reason**: Classifier fallback is removed from the client.
**Migration**: Delete those frontend tests.

### Requirement: Frontend Unit Tests for Embedding Generation
**Reason**: The client no longer generates embeddings on photo upload.
**Migration**: Delete those frontend tests. Keep catalog photo upload tests.
