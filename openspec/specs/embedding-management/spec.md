# embedding-management Specification

## Purpose
Defines how the system stores, exposes, auto-generates, and manages MobileNetV2 feature embeddings for product photos, including the REST API, lifecycle hooks (upload/delete), full rebuild, and admin status display.
## Requirements
### Requirement: Embedding Data Storage

The system SHALL persist per-photo MobileNetV2 feature embeddings in a PostgreSQL table, linked to the source photo and product.

#### Scenario: ProductPhotoEmbedding entity structure

- **WHEN** an embedding is stored
- **THEN** the ProductPhotoEmbedding record contains:
  - Id (Guid, primary key, inherited from BaseEntity)
  - ProductPhotoId (Guid, foreign key to ProductPhoto)
  - ProductId (Guid, foreign key to Product)
  - ProductSku (string, denormalized for efficient bulk reads)
  - EmbeddingVector (text, JSON-serialized float array of 1280 dimensions)
  - CreatedAt, UpdatedAt (inherited from BaseEntity)

#### Scenario: Unique constraint on photo

- **WHEN** an embedding for a ProductPhotoId that already exists is saved
- **THEN** system replaces the existing embedding (upsert behavior)
- **AND** only one embedding per ProductPhoto exists at any time

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

