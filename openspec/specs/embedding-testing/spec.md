# embedding-testing Specification

## Purpose
Defines the automated test requirements for embedding-related backend services and API endpoints. Client-side embedding and similarity tests are withdrawn with product-photo recognition.

## Requirements

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
