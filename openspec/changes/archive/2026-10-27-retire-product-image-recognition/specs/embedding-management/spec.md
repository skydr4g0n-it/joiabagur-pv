## ADDED Requirements

### Requirement: Product photos do not generate embeddings
Uploading or deleting a product photo SHALL complete as catalog management only. The client SHALL NOT load a feature extractor and SHALL NOT call embedding routes.

#### Scenario: Upload does not generate an embedding
- **GIVEN** an administrator on the product edit page
- **WHEN** the administrator uploads a valid JPG or PNG product photo
- **THEN** the photo is stored and shown in the gallery
- **AND** the client does not call `/api/image-recognition/embeddings`
- **AND** the interface does not show an embedding-generation message

#### Scenario: Delete does not call the embedding API
- **GIVEN** a product photo exists
- **WHEN** an administrator deletes that photo
- **THEN** the photo is removed from the product
- **AND** the client does not call `/api/image-recognition/embeddings/{photoId}`

### Requirement: Embedding HTTP API is withdrawn
Embedding routes under `/api/image-recognition/embeddings` SHALL use the same withdrawal behavior as the rest of `/api/image-recognition`. Existing `ProductPhotoEmbedding` rows SHALL remain stored.

#### Scenario: Authenticated embedding call returns 410
- **GIVEN** an authenticated caller
- **WHEN** the caller sends GET, POST, or DELETE to `/api/image-recognition/embeddings` or GET `/api/image-recognition/embeddings/status`
- **THEN** the response status is 410 Gone
- **AND** no embedding row is created, updated, or deleted by that call

#### Scenario: Stored embeddings are kept
- **GIVEN** `ProductPhotoEmbedding` rows already exist
- **WHEN** this change is deployed
- **THEN** those rows are not deleted by a migration

## REMOVED Requirements

### Requirement: Embedding API Endpoints
**Reason**: Embedding routes are part of the withdrawn recognition API.
**Migration**: Clients stop calling them. Stored rows remain. Routes return 410.

### Requirement: Auto-Generate Embedding on Photo Upload
**Reason**: Photos are catalog images, not recognition features.
**Migration**: Upload the photo only. Do not extract or save a vector.

### Requirement: Auto-Delete Embedding on Photo Deletion
**Reason**: The client no longer maintains embeddings.
**Migration**: Delete the product photo only. Orphaned embedding rows may remain.

### Requirement: Full Embedding Rebuild
**Reason**: The admin AI-model page and its rebuild action are removed.
**Migration**: Do not rebuild embeddings.

### Requirement: Embedding Status Display on Admin Dashboard
**Reason**: `/admin/ai-model` is removed.
**Migration**: No status card is shown.
