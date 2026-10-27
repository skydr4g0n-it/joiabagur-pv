> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

## 1. Backend Data Layer

- [x] 1.1 Create `ProductPhotoEmbedding` entity in `backend/src/JoiabagurPV.Domain/Entities/ProductPhotoEmbedding.cs` inheriting `BaseEntity` with fields: `ProductPhotoId` (Guid, FK), `ProductId` (Guid, FK), `ProductSku` (string), `EmbeddingVector` (string). Add navigation properties to `ProductPhoto` and `Product`.
- [x] 1.2 Create `IProductPhotoEmbeddingRepository` interface in `backend/src/JoiabagurPV.Domain/Interfaces/Repositories/` with methods: `GetAllAsync()`, `GetByPhotoIdAsync(Guid)`, `GetByProductIdAsync(Guid)`, `DeleteByPhotoIdAsync(Guid)`, `DeleteAllAsync()`, `GetCountAsync()`, `GetLastUpdatedAsync()`.
- [x] 1.3 Create `ProductPhotoEmbeddingRepository` implementation in `backend/src/JoiabagurPV.Infrastructure/Data/Repositories/` extending `Repository<ProductPhotoEmbedding>`.
- [x] 1.4 Create `ProductPhotoEmbeddingConfiguration` EF configuration in `backend/src/JoiabagurPV.Infrastructure/Data/Configurations/` following the `ProductPhotoConfiguration` pattern. Map `EmbeddingVector` to a `text` column, add index on `ProductPhotoId` (unique) and `ProductId`.
- [x] 1.5 Add `DbSet<ProductPhotoEmbedding>` to `ApplicationDbContext`.
- [x] 1.6 Register `IProductPhotoEmbeddingRepository` in `ServiceCollectionExtensions.cs`.
- [x] 1.7 Run `dotnet ef migrations add AddProductPhotoEmbeddings` to generate the migration. Verify migration creates the table with correct columns and indexes. Run `dotnet build` to confirm no compilation errors.

## 2. Backend DTOs

- [x] 2.1 Create DTOs in `backend/src/JoiabagurPV.Application/DTOs/ImageRecognition/`: `SaveEmbeddingRequest` (photoId, productId, sku, vector as float[]), `EmbeddingDto` (photoId, productId, sku, vector as float[]), `EmbeddingsIndexResponse` (embeddings as List<EmbeddingDto>, lastUpdated as DateTime?, count as int), `EmbeddingsStatusResponse` (count as int, lastUpdated as DateTime?).

## 3. Backend Service Layer

- [x] 3.1 Add embedding methods to `IImageRecognitionService`: `SaveEmbeddingAsync(SaveEmbeddingRequest)`, `DeleteEmbeddingAsync(Guid photoId)`, `DeleteAllEmbeddingsAsync()`, `GetAllEmbeddingsAsync()` returning `EmbeddingsIndexResponse`, `GetEmbeddingsStatusAsync()` returning `EmbeddingsStatusResponse`.
- [x] 3.2 Implement embedding methods in `ImageRecognitionService`. `SaveEmbeddingAsync` must validate vector length = 1280 and upsert (delete existing by photoId, then add). `GetAllEmbeddingsAsync` must deserialize EmbeddingVector JSON to float arrays. `GetEmbeddingsStatusAsync` must return count and max UpdatedAt.
- [x] 3.3 Verify backend builds successfully with `dotnet build`. Run existing tests to confirm no regressions.

## 4. Backend API Endpoints

- [x] 4.1 Add embedding endpoints to `ImageRecognitionController`: `POST /api/image-recognition/embeddings` (save single), `DELETE /api/image-recognition/embeddings/{photoId}` (delete single), `DELETE /api/image-recognition/embeddings` (delete all), `GET /api/image-recognition/embeddings` (bulk download), `GET /api/image-recognition/embeddings/status` (count + lastUpdated). All endpoints require JWT authentication.
- [x] 4.2 Add request validation: POST must validate vector is not null and has exactly 1280 elements, return 400 with descriptive error otherwise. DELETE endpoints return 204 No Content.
- [x] 4.3 Run `dotnet build` and verify all new endpoints are accessible. Manually test with a tool like curl or Scalar to confirm endpoint routing.

## 5. Frontend API Client

- [x] 5.1 Add embedding methods to `imageRecognitionService` in `frontend/src/services/sales.service.ts`: `saveEmbedding(photoId, productId, sku, vector)` (POST), `deleteEmbedding(photoId)` (DELETE), `getAllEmbeddings()` (GET, returns EmbeddingsIndexResponse), `getEmbeddingsStatus()` (GET, returns EmbeddingsStatusResponse), `deleteAllEmbeddings()` (DELETE).
- [x] 5.2 Add TypeScript types for `EmbeddingDto`, `EmbeddingsIndexResponse`, `EmbeddingsStatusResponse` alongside the existing types in the sales service file or a shared types file.

## 6. Frontend Similarity Inference Engine

- [x] 6.1 Add `cosineSimilarity(a: Float32Array, b: Float32Array): number` function to `frontend/src/services/image-recognition.service.ts`. Compute dot product divided by product of norms.
- [x] 6.2 Add `loadEmbeddingsIndex()` function that fetches all embeddings from the API, parses vectors into Float32Arrays, caches in a module-level variable with the lastUpdated timestamp. On subsequent calls, check staleness via `getEmbeddingsStatus()` and re-fetch only if server timestamp is newer.
- [x] 6.3 Add `recognizeProductBySimilarity(imageFile: File)` function implementing the full similarity inference flow: validate image, load MobileNetV2, preprocess, extract features, load embeddings index, compute cosine similarity against all stored vectors, group by SKU (max similarity per product), sort descending, filter by SIMILARITY_THRESHOLD (0.70), enforce MIN_TOP_SIMILARITY (0.50) for top match, return top 5 suggestions enriched with product details.
- [x] 6.4 Rename existing `recognizeProduct` to `recognizeProductByClassifier` (internal). Create new `recognizeProduct` that checks embedding status: if count > 0 use `recognizeProductBySimilarity`, otherwise fall back to `recognizeProductByClassifier`. Add try-catch around similarity path to fall back to classifier on error.
- [x] 6.5 Add constants `SIMILARITY_THRESHOLD = 0.70` and `MIN_TOP_SIMILARITY = 0.50`. Add `clearEmbeddingsCache()` function to invalidate the in-memory cache.
- [x] 6.6 Verify frontend builds with `npm run build`. Check no TypeScript errors.

## 7. Frontend Photo Upload Integration

- [x] 7.1 In `product-photo-upload.tsx`, after `productService.uploadPhoto` succeeds in the upload flow: load MobileNetV2 feature extractor (lazy, cached), preprocess the uploaded image, extract 1280-dim features, call `imageRecognitionService.saveEmbedding(photo.id, productId, productSku, vector)`. Show brief indicator "Generando embedding de IA..." during extraction. Handle errors non-blockingly (photo upload still succeeds, log warning, show brief toast).
- [x] 7.2 In `product-photo-upload.tsx`, after `productService.deletePhoto` succeeds in the delete flow: call `imageRecognitionService.deleteEmbedding(photoId)`. Handle errors non-blockingly (photo delete still succeeds).
- [x] 7.3 Verify the photo upload and delete flows work end-to-end by building and testing manually.

## 8. Frontend Full Rebuild

- [x] 8.1 Add `executeEmbeddingGeneration(onProgress: (phase, current, total) => void)` function to `frontend/src/services/model-training.service.ts`. Steps: call `deleteAllEmbeddings()`, fetch training dataset via `getTrainingDataset()`, load MobileNetV2, process photos in batches of 8 (download, preprocess, extract features, save embedding via API), report progress via callback.
- [x] 8.2 On `frontend/src/pages/admin/ai-model.tsx`, add an embeddings status card showing: embedding count, last updated timestamp. Add "Generar Embeddings" button that calls `executeEmbeddingGeneration`. Show progress card during generation (reuse existing progress UI pattern). Disable button during generation. Keep the existing "Entrenar Modelo" button for classifier training.
- [x] 8.3 Fetch embedding status on page load via `getEmbeddingsStatus()` and display in the new card. Show "No hay embeddings generados" when count is 0.
- [x] 8.4 Verify the full rebuild flow works by building and testing manually.

## 9. Backend Tests

- [x] 9.1 Add `ProductPhotoEmbeddingFaker` and `CreateProductPhotoEmbedding` / `CreateProductPhotoEmbeddings` methods to `TestDataGenerator`. Generate realistic 1280-dim float vectors, random Guids, and SKUs. Verify with `dotnet build`.
- [x] 9.2 Create `ProductPhotoEmbeddingMother` in `TestHelpers/Mothers/` for integration tests. Register in `TestDataMother`. Support fluent builder: `WithPhotoId()`, `WithProductId()`, `WithSku()`, `WithVector()`, `CreateAsync()`.
- [x] 9.3 Create `ImageRecognitionEmbeddingServiceTests.cs` in `UnitTests/Application/` with unit tests for all embedding service methods: `SaveEmbeddingAsync` (new, upsert, invalid vector), `DeleteEmbeddingAsync`, `DeleteAllEmbeddingsAsync`, `GetAllEmbeddingsAsync` (with data, empty), `GetEmbeddingsStatusAsync`. Use Moq for `IProductPhotoEmbeddingRepository`, FluentAssertions for assertions, TestDataGenerator for test data. Verify all pass with `dotnet test`.
- [x] 9.4 Create `EmbeddingEndpointsTests.cs` in `IntegrationTests/` with integration tests for all embedding API endpoints: POST (valid, invalid vector, upsert), DELETE single (exists, idempotent), DELETE all, GET all (format, data), GET status (lightweight response), unauthenticated 401. Use `ApiWebApplicationFactory`, `TestDataMother`, Respawn. Verify all pass with `dotnet test`.

## 10. Frontend Tests

- [x] 10.1 Create `cosine-similarity.test.ts` in `frontend/src/services/__tests__/` testing the `cosineSimilarity` function: identical vectors (1.0), orthogonal vectors (0.0), opposite vectors (-1.0), known pre-computed value, 1280-dim vectors return value in [-1, 1]. Use Vitest.
- [x] 10.2 Add tests for `loadEmbeddingsIndex` to `frontend/src/services/__tests__/image-recognition.service.test.ts` (or a new dedicated file): first call fetches from API and caches, subsequent call with fresh cache skips re-fetch, stale cache triggers re-fetch, `clearEmbeddingsCache` invalidates cache. Mock `sales.service` API methods with `vi.mock`.
- [x] 10.3 Add tests for `recognizeProductBySimilarity` to `frontend/src/services/__tests__/image-recognition.service.test.ts`: returns top products sorted by similarity, uses max similarity per product across photos, returns empty when below MIN_TOP_SIMILARITY, returns partial results when few exceed SIMILARITY_THRESHOLD. Mock MobileNetV2 and embeddings index.
- [x] 10.4 Add tests for the updated `recognizeProduct` fallback logic: uses similarity path when embeddings exist, uses classifier when count = 0, falls back to classifier on similarity error. Mock `getEmbeddingsStatus` and both inference paths.
- [x] 10.5 Add tests for `executeEmbeddingGeneration` in `frontend/src/services/__tests__/model-training.service.test.ts`: full rebuild processes all photos with progress callback, skips failed photos and continues. Mock API methods and MobileNetV2.
- [x] 10.6 Verify all frontend tests pass with `npm run test`.

## 11. Documentation

- [x] 11.1 Update `Documentos/modelo-de-datos.md` to include the new `ProductPhotoEmbedding` entity with its fields and relationships.
- [x] 11.2 Update `Documentos/epicas.md` EP4 section to mention the embedding similarity approach as the new default inference method alongside the existing classifier.
