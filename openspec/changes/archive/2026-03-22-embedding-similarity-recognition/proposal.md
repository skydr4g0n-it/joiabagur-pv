> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

## Why

The current image recognition system trains a softmax classification head on top of MobileNetV2 features. With ~2 photos per class across 170 product classes, the classifier cannot learn meaningful decision boundaries -- training takes 15+ minutes and produces unreliable predictions. By switching to cosine similarity over raw MobileNetV2 feature embeddings, we eliminate the training step entirely, reduce "retraining" to a ~30-60 second embedding generation pass, and get naturally better results since the pre-trained feature extractor already produces excellent visual representations.

## What Changes

- **Replace classifier training with embedding indexing**: Instead of training a classification head, extract and store per-photo 1280-dimensional MobileNetV2 feature vectors in the database. No epochs, no loss functions -- just save the fingerprints.
- **Replace softmax inference with cosine similarity ranking**: At inference time, compare a query photo's feature vector against all stored embeddings using cosine similarity, rank by best match per product, and threshold at 0.70.
- **New backend data layer**: `ProductPhotoEmbedding` entity, repository, EF configuration, and migration to persist embedding vectors as JSON text in PostgreSQL.
- **New backend API endpoints**: CRUD operations for embeddings (save, delete, bulk download, status) on the `ImageRecognitionController`.
- **Auto-update embeddings on photo lifecycle**: When a product photo is uploaded, automatically extract and save its embedding. When a photo is deleted, delete its embedding. No manual model retraining needed for catalog changes.
- **Full rebuild option**: "Generar Embeddings" button on the admin AI model page to regenerate all embeddings from scratch (~30-60 seconds vs. 15+ minutes for classifier training).
- **Preserve existing classifier as fallback**: `recognizeProduct` checks for embeddings first and falls back to the existing classifier if no embeddings exist.

## Capabilities

### New Capabilities
- `embedding-similarity-inference`: Cosine similarity-based product recognition using stored MobileNetV2 feature embeddings, replacing the softmax classifier as the default inference path with automatic fallback.
- `embedding-management`: Backend storage, API endpoints, and frontend integration for creating, deleting, and bulk-managing per-photo embedding vectors, including auto-generation on photo upload and full rebuild capability.
- `embedding-testing`: Backend unit tests (service layer), backend integration tests (API endpoints), and frontend unit tests (cosine similarity, inference flow, caching, fallback logic, embedding generation) for the embedding similarity system.

### Modified Capabilities
- `image-recognition`: Inference behavior changes from softmax classifier probabilities to cosine similarity scores. Confidence thresholds shift from 40% softmax to 0.70 cosine similarity (with 0.50 minimum for top match). The model versioning/caching requirements evolve to include embeddings index caching alongside the existing model cache. The admin dashboard gains embedding status metrics and a "Generar Embeddings" action.

## Impact

- **Backend**: New `ProductPhotoEmbedding` entity, repository, EF configuration, and database migration. New service methods and controller endpoints on `ImageRecognitionController`. New DTOs for embedding payloads.
- **Frontend services**: `image-recognition.service.ts` gains similarity inference functions (`cosineSimilarity`, `recognizeProductBySimilarity`, `loadEmbeddingsIndex`). `model-training.service.ts` gains `executeEmbeddingGeneration`. `sales.service.ts` gains embedding API client methods.
- **Frontend pages**: `product-photo-upload.tsx` integrates embedding extraction into upload/delete flows. `ai-model.tsx` adds embedding generation button and status display.
- **Data storage**: ~1.8 MB additional database storage (366 photos x 1280 floats x 4 bytes as JSON text). Trivial compared to current model weight files.
- **No new dependencies**: Reuses existing MobileNetV2 feature extractor and TensorFlow.js runtime. No pgvector extension needed -- similarity is computed in the browser.
- **No breaking changes**: Existing classifier training and inference paths are preserved as fallback.
