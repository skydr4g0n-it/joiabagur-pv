> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

## ADDED Requirements

### Requirement: Backend Unit Tests for Embedding Service

The system SHALL include unit tests for `ImageRecognitionService` embedding methods using Moq for repository mocking, FluentAssertions for assertions, and TestDataGenerator for test data.

#### Scenario: SaveEmbeddingAsync saves new embedding

- **WHEN** `SaveEmbeddingAsync` is called with a valid `SaveEmbeddingRequest` (photoId, productId, sku, 1280-element float array)
- **AND** no embedding exists for that photoId
- **THEN** service calls `IProductPhotoEmbeddingRepository.AddAsync` with a `ProductPhotoEmbedding` entity
- **AND** entity has `ProductPhotoId`, `ProductId`, `ProductSku` matching the request
- **AND** entity has `EmbeddingVector` containing the serialized JSON float array

#### Scenario: SaveEmbeddingAsync upserts existing embedding

- **WHEN** `SaveEmbeddingAsync` is called with a photoId that already has an embedding
- **THEN** service calls `DeleteByPhotoIdAsync` for the existing embedding
- **AND** then calls `AddAsync` with the new embedding data
- **AND** only one embedding per photoId exists after the operation

#### Scenario: SaveEmbeddingAsync rejects invalid vector length

- **WHEN** `SaveEmbeddingAsync` is called with a vector that has fewer or more than 1280 elements
- **THEN** service throws a `DomainException` with message containing "1280"
- **AND** no repository write operations are invoked

#### Scenario: DeleteEmbeddingAsync deletes by photo ID

- **WHEN** `DeleteEmbeddingAsync` is called with a valid photoId
- **THEN** service calls `IProductPhotoEmbeddingRepository.DeleteByPhotoIdAsync(photoId)`

#### Scenario: DeleteAllEmbeddingsAsync clears all embeddings

- **WHEN** `DeleteAllEmbeddingsAsync` is called
- **THEN** service calls `IProductPhotoEmbeddingRepository.DeleteAllAsync()`

#### Scenario: GetAllEmbeddingsAsync returns deserialized embeddings

- **WHEN** `GetAllEmbeddingsAsync` is called
- **AND** repository returns 3 `ProductPhotoEmbedding` records with JSON-serialized vectors
- **THEN** service returns an `EmbeddingsIndexResponse` with 3 `EmbeddingDto` entries
- **AND** each dto has `vector` as a deserialized float array of 1280 elements
- **AND** `count` equals 3
- **AND** `lastUpdated` equals the maximum `UpdatedAt` across all records

#### Scenario: GetAllEmbeddingsAsync returns empty when no embeddings

- **WHEN** `GetAllEmbeddingsAsync` is called
- **AND** repository returns zero records
- **THEN** service returns `EmbeddingsIndexResponse` with empty embeddings list, count = 0, and lastUpdated = null

#### Scenario: GetEmbeddingsStatusAsync returns count and timestamp

- **WHEN** `GetEmbeddingsStatusAsync` is called
- **THEN** service returns `EmbeddingsStatusResponse` with count from `GetCountAsync()` and lastUpdated from `GetLastUpdatedAsync()`

### Requirement: Backend Unit Tests for Embedding Test Data

The system SHALL extend `TestDataGenerator` with methods for creating `ProductPhotoEmbedding` test entities using Bogus.

#### Scenario: TestDataGenerator creates ProductPhotoEmbedding

- **WHEN** `TestDataGenerator.CreateProductPhotoEmbedding()` is called
- **THEN** a `ProductPhotoEmbedding` is returned with:
  - Random Guid for Id, ProductPhotoId, ProductId
  - Random ProductSku
  - EmbeddingVector containing a JSON-serialized array of 1280 random floats in [-1, 1] range
  - CreatedAt and UpdatedAt set to realistic timestamps

#### Scenario: TestDataGenerator creates batch of embeddings

- **WHEN** `TestDataGenerator.CreateProductPhotoEmbeddings(count, productId?, sku?)` is called
- **THEN** a list of `count` ProductPhotoEmbedding entities is returned
- **AND** optional productId and sku override the generated values for all entries

### Requirement: Backend Integration Tests for Embedding Endpoints

The system SHALL include integration tests for all embedding API endpoints using `ApiWebApplicationFactory`, `TestDataMother`, and Respawn for database cleanup.

#### Scenario: POST embedding saves and is retrievable

- **WHEN** authenticated client sends POST /api/image-recognition/embeddings with valid payload
- **THEN** response status is 200 OK
- **AND** subsequent GET /api/image-recognition/embeddings returns the saved embedding
- **AND** the returned embedding has matching photoId, productId, sku, and vector

#### Scenario: POST embedding with invalid vector returns 400

- **WHEN** authenticated client sends POST /api/image-recognition/embeddings with vector of length 500
- **THEN** response status is 400 Bad Request
- **AND** response body contains error message about 1280 dimensions

#### Scenario: POST embedding upserts on duplicate photoId

- **WHEN** authenticated client sends POST with embedding for photoId X
- **AND** then sends another POST with a different vector for the same photoId X
- **THEN** GET /api/image-recognition/embeddings returns only one embedding for photoId X
- **AND** the vector matches the second POST (most recent)

#### Scenario: DELETE single embedding removes only that embedding

- **WHEN** authenticated client saves two embeddings (photoId A, photoId B)
- **AND** sends DELETE /api/image-recognition/embeddings/{photoIdA}
- **THEN** response status is 204 No Content
- **AND** GET /api/image-recognition/embeddings returns only embedding for photoId B

#### Scenario: DELETE single embedding is idempotent

- **WHEN** authenticated client sends DELETE /api/image-recognition/embeddings/{nonExistentPhotoId}
- **THEN** response status is 204 No Content

#### Scenario: DELETE all embeddings clears the table

- **WHEN** authenticated client saves 3 embeddings
- **AND** sends DELETE /api/image-recognition/embeddings
- **THEN** response status is 204 No Content
- **AND** GET /api/image-recognition/embeddings/status returns count = 0

#### Scenario: GET embeddings returns correct format

- **WHEN** authenticated client saves 2 embeddings with known SKUs
- **AND** sends GET /api/image-recognition/embeddings
- **THEN** response status is 200 OK
- **AND** response body has `embeddings` array with 2 entries
- **AND** response body has `count` = 2
- **AND** response body has `lastUpdated` as a valid ISO 8601 timestamp

#### Scenario: GET embeddings status returns lightweight response

- **WHEN** authenticated client saves 5 embeddings
- **AND** sends GET /api/image-recognition/embeddings/status
- **THEN** response status is 200 OK
- **AND** response body has `count` = 5
- **AND** response body has `lastUpdated` as a valid ISO 8601 timestamp
- **AND** response body does NOT contain `embeddings` or `vector` fields

#### Scenario: Unauthenticated request returns 401

- **WHEN** unauthenticated client sends GET /api/image-recognition/embeddings
- **THEN** response status is 401 Unauthorized

### Requirement: Frontend Unit Tests for Cosine Similarity Function

The system SHALL include unit tests for the `cosineSimilarity` function verifying mathematical correctness and edge cases.

#### Scenario: Identical vectors return similarity of 1.0

- **WHEN** `cosineSimilarity` is called with two identical Float32Arrays
- **THEN** the result is 1.0 (within floating-point tolerance of 1e-6)

#### Scenario: Orthogonal vectors return similarity of 0.0

- **WHEN** `cosineSimilarity` is called with two orthogonal Float32Arrays (e.g., [1,0,...] and [0,1,...])
- **THEN** the result is 0.0 (within floating-point tolerance of 1e-6)

#### Scenario: Opposite vectors return similarity of -1.0

- **WHEN** `cosineSimilarity` is called with a vector and its negation
- **THEN** the result is -1.0 (within floating-point tolerance of 1e-6)

#### Scenario: Known similarity value

- **WHEN** `cosineSimilarity` is called with two known vectors with pre-computed expected similarity
- **THEN** the result matches the expected value within tolerance of 1e-4

#### Scenario: Handles 1280-dimensional vectors

- **WHEN** `cosineSimilarity` is called with two random Float32Arrays of length 1280
- **THEN** the result is a number between -1.0 and 1.0

### Requirement: Frontend Unit Tests for Similarity Inference

The system SHALL include unit tests for `recognizeProductBySimilarity` verifying the full inference flow with mocked MobileNetV2 and API responses.

#### Scenario: Returns top products sorted by similarity

- **WHEN** `recognizeProductBySimilarity` is called
- **AND** embeddings index contains vectors for products SKU01 (2 photos), SKU02 (1 photo), SKU03 (1 photo)
- **AND** query vector has cosine similarity 0.95 with SKU01-photo1, 0.80 with SKU02, 0.60 with SKU03
- **THEN** result contains SKU01 first (0.95), SKU02 second (0.80)
- **AND** SKU03 is excluded (below 0.70 threshold)
- **AND** result has at most 5 entries

#### Scenario: Uses max similarity per product across multiple photos

- **WHEN** product SKU01 has two photos with similarities 0.60 and 0.85 to the query
- **THEN** SKU01 appears in results with similarity 0.85 (the max)

#### Scenario: Returns empty when top match below MIN_TOP_SIMILARITY

- **WHEN** all products have similarity < 0.50 to the query
- **THEN** result is an empty array

#### Scenario: Returns partial results when few exceed threshold

- **WHEN** 2 products exceed 0.70 and 3 products are between 0.50 and 0.70
- **THEN** result contains only the 2 products above 0.70

### Requirement: Frontend Unit Tests for Embeddings Index Caching

The system SHALL include unit tests for `loadEmbeddingsIndex` verifying caching behavior and staleness detection.

#### Scenario: First call fetches from API

- **WHEN** `loadEmbeddingsIndex` is called for the first time
- **THEN** it calls `getAllEmbeddings()` API method
- **AND** parses vectors into Float32Arrays
- **AND** caches the result in memory

#### Scenario: Subsequent call with fresh cache skips re-fetch

- **WHEN** `loadEmbeddingsIndex` is called a second time
- **AND** `getEmbeddingsStatus()` returns same `lastUpdated` as cached
- **THEN** it does NOT call `getAllEmbeddings()` again
- **AND** returns the cached index

#### Scenario: Subsequent call with stale cache re-fetches

- **WHEN** `loadEmbeddingsIndex` is called a second time
- **AND** `getEmbeddingsStatus()` returns a newer `lastUpdated` than cached
- **THEN** it calls `getAllEmbeddings()` to re-fetch
- **AND** updates the cache with the new data

#### Scenario: clearEmbeddingsCache invalidates the cache

- **WHEN** `clearEmbeddingsCache()` is called
- **AND** then `loadEmbeddingsIndex` is called
- **THEN** it calls `getAllEmbeddings()` regardless of previous cache state

### Requirement: Frontend Unit Tests for Fallback Logic

The system SHALL include unit tests for the `recognizeProduct` function verifying the similarity-first, classifier-fallback behavior.

#### Scenario: Uses similarity path when embeddings exist

- **WHEN** `recognizeProduct` is called
- **AND** `getEmbeddingsStatus()` returns count > 0
- **THEN** `recognizeProductBySimilarity` is called
- **AND** `recognizeProductByClassifier` is NOT called

#### Scenario: Uses classifier path when no embeddings exist

- **WHEN** `recognizeProduct` is called
- **AND** `getEmbeddingsStatus()` returns count = 0
- **THEN** `recognizeProductByClassifier` is called
- **AND** `recognizeProductBySimilarity` is NOT called

#### Scenario: Falls back to classifier on similarity error

- **WHEN** `recognizeProduct` is called
- **AND** `getEmbeddingsStatus()` returns count > 0
- **AND** `recognizeProductBySimilarity` throws an error
- **THEN** `recognizeProductByClassifier` is called as fallback
- **AND** error is logged as warning

### Requirement: Frontend Unit Tests for Embedding Generation

The system SHALL include unit tests for `executeEmbeddingGeneration` verifying the full rebuild flow with mocked dependencies.

#### Scenario: Full rebuild processes all photos and reports progress

- **WHEN** `executeEmbeddingGeneration` is called with a progress callback
- **AND** training dataset returns 3 photos
- **THEN** `deleteAllEmbeddings()` is called first
- **AND** MobileNetV2 feature extractor is loaded
- **AND** each photo is processed (download, preprocess, extract, save)
- **AND** progress callback is called with incrementing counts (1/3, 2/3, 3/3)
- **AND** `saveEmbedding` is called 3 times with correct photoId, productId, sku, and 1280-dim vectors

#### Scenario: Full rebuild skips failed photos and continues

- **WHEN** `executeEmbeddingGeneration` is called
- **AND** photo 2 of 3 fails to download
- **THEN** photos 1 and 3 are processed successfully
- **AND** `saveEmbedding` is called 2 times
- **AND** progress reports reflect the failure
