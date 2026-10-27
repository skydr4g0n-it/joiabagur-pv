> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

## ADDED Requirements

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

### Requirement: Embedding API Endpoints

The system SHALL expose REST endpoints for creating, reading, and deleting embedding records.

#### Scenario: Save single embedding

- **WHEN** POST /api/image-recognition/embeddings is called
- **AND** request body contains { photoId, productId, sku, vector: float[1280] }
- **THEN** system creates or updates ProductPhotoEmbedding record
- **AND** returns 200 OK on success

#### Scenario: Save embedding with invalid vector length

- **WHEN** POST /api/image-recognition/embeddings is called
- **AND** vector length is not exactly 1280
- **THEN** system returns 400 Bad Request
- **AND** response includes error: "Embedding vector must have exactly 1280 dimensions"

#### Scenario: Delete single embedding by photo ID

- **WHEN** DELETE /api/image-recognition/embeddings/{photoId} is called
- **THEN** system deletes the ProductPhotoEmbedding with matching ProductPhotoId
- **AND** returns 204 No Content on success
- **AND** returns 204 No Content if no embedding exists for that photoId (idempotent)

#### Scenario: Delete all embeddings

- **WHEN** DELETE /api/image-recognition/embeddings is called
- **THEN** system deletes all ProductPhotoEmbedding records
- **AND** returns 204 No Content

#### Scenario: Get all embeddings (bulk download)

- **WHEN** GET /api/image-recognition/embeddings is called
- **THEN** system returns all ProductPhotoEmbedding records
- **AND** response format is:
  ```json
  {
    "embeddings": [
      { "photoId": "...", "productId": "...", "sku": "SKU01", "vector": [0.023, -0.114, ...] }
    ],
    "lastUpdated": "2026-03-22T10:00:00Z",
    "count": 366
  }
  ```
- **AND** response includes all embeddings in a single payload (no pagination)

#### Scenario: Get embeddings status

- **WHEN** GET /api/image-recognition/embeddings/status is called
- **THEN** system returns { count, lastUpdated } without embedding vectors
- **AND** response is lightweight (no vector data transferred)

#### Scenario: Authentication required

- **WHEN** any embedding endpoint is called without valid JWT token
- **THEN** system returns 401 Unauthorized

### Requirement: Auto-Generate Embedding on Photo Upload

The system SHALL automatically extract and save an embedding when a product photo is uploaded.

#### Scenario: Embedding generated after photo upload

- **WHEN** a product photo is successfully uploaded via the product photo upload flow
- **AND** backend returns the saved photo with its ID
- **THEN** frontend loads MobileNetV2 feature extractor (lazy, cached after first load)
- **AND** preprocesses the uploaded image (resize to 224x224, normalize)
- **AND** extracts 1280-dimensional feature vector
- **AND** calls POST /api/image-recognition/embeddings with { photoId, productId, sku, vector }
- **AND** displays brief indicator "Generando embedding de IA..." during extraction

#### Scenario: Embedding generation failure is non-blocking

- **WHEN** embedding extraction or save fails (model load error, network error)
- **THEN** photo upload is still considered successful
- **AND** system logs warning
- **AND** displays brief toast: "No se pudo generar el embedding. Se generará en la próxima reconstrucción."
- **AND** missing embedding can be regenerated via full rebuild

### Requirement: Auto-Delete Embedding on Photo Deletion

The system SHALL automatically delete the associated embedding when a product photo is deleted.

#### Scenario: Embedding deleted after photo deletion

- **WHEN** a product photo is successfully deleted
- **THEN** frontend calls DELETE /api/image-recognition/embeddings/{photoId}
- **AND** associated ProductPhotoEmbedding record is removed

#### Scenario: Embedding deletion failure is non-blocking

- **WHEN** embedding deletion fails (network error, embedding doesn't exist)
- **THEN** photo deletion is still considered successful
- **AND** orphaned embeddings are cleaned up on next full rebuild

### Requirement: Full Embedding Rebuild

The system SHALL provide an admin function to regenerate all embeddings from scratch.

#### Scenario: Admin triggers full rebuild

- **WHEN** administrator clicks "Generar Embeddings" button on /admin/ai-model page
- **THEN** system calls DELETE /api/image-recognition/embeddings to clear existing
- **AND** fetches training dataset via GET /api/image-recognition/training-dataset
- **AND** loads MobileNetV2 feature extractor
- **AND** processes photos in batches of 8: download, preprocess, extract features, upload embedding
- **AND** reports progress via callback (X/Y photos processed)
- **AND** completes in approximately 30-60 seconds for ~366 photos

#### Scenario: Full rebuild progress display

- **WHEN** full rebuild is in progress
- **THEN** admin page displays progress card with:
  - Current phase ("Descargando fotos...", "Extrayendo embeddings...")
  - Progress bar (X/Y photos)
  - Elapsed time
- **AND** "Generar Embeddings" button is disabled during rebuild

#### Scenario: Full rebuild error handling

- **WHEN** full rebuild encounters errors on individual photos (download failure, processing error)
- **THEN** system skips failed photos and continues with remaining
- **AND** logs warnings for each skipped photo
- **AND** reports summary at completion: "Completado: X de Y embeddings generados"

### Requirement: Embedding Status Display on Admin Dashboard

The system SHALL display embedding status information on the AI model admin page.

#### Scenario: Display embedding status when embeddings exist

- **WHEN** administrator navigates to /admin/ai-model
- **AND** embeddings have been generated
- **THEN** page displays embedding status card with:
  - Total embedding count
  - Last updated timestamp
  - "Generar Embeddings" button

#### Scenario: Display embedding status when no embeddings exist

- **WHEN** administrator navigates to /admin/ai-model
- **AND** no embeddings exist (count = 0)
- **THEN** page displays embedding status card with:
  - Message: "No hay embeddings generados"
  - "Generar Embeddings" button (prominent, primary style)
