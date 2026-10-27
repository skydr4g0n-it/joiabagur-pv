> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

## ADDED Requirements

### Requirement: Cosine Similarity Inference

The system SHALL recognize products by computing cosine similarity between a query image's MobileNetV2 feature vector and all stored embedding vectors, ranking results by maximum similarity per product.

#### Scenario: Successful product recognition via similarity

- **WHEN** operator captures or uploads a product photo
- **AND** embeddings index contains at least one embedding
- **THEN** frontend extracts 1280-dimensional feature vector using MobileNetV2 feature extractor
- **AND** computes cosine similarity between query vector and every stored embedding vector
- **AND** groups results by product (SKU)
- **AND** takes the maximum similarity score per product
- **AND** sorts products by similarity score descending
- **AND** returns products with similarity >= 0.70 (SIMILARITY_THRESHOLD)
- **AND** returns at most 5 product suggestions

#### Scenario: No match above threshold

- **WHEN** inference completes
- **AND** the highest similarity score across all products is < 0.50 (MIN_TOP_SIMILARITY)
- **THEN** system returns zero suggestions
- **AND** displays message: "No se encontró una correspondencia fiable"
- **AND** offers options: "Tomar otra foto" or "Registrar venta manual"

#### Scenario: Top match above minimum but few above threshold

- **WHEN** inference completes
- **AND** the highest similarity score is >= 0.50 (MIN_TOP_SIMILARITY)
- **AND** fewer than 5 products have similarity >= 0.70
- **THEN** system returns only the products that exceed 0.70
- **AND** displays available suggestions (1 to 4 products)

#### Scenario: Inference performance

- **WHEN** operator triggers similarity inference
- **AND** embeddings index is loaded in memory
- **THEN** cosine similarity computation across all stored embeddings completes in < 10ms
- **AND** total inference time (feature extraction + similarity) completes in < 500ms on mobile device

### Requirement: Embeddings Index Loading and Caching

The system SHALL load all stored embedding vectors into browser memory and cache them, using a lightweight status check to detect staleness.

#### Scenario: First load of embeddings index

- **WHEN** similarity inference is requested for the first time in a session
- **AND** no embeddings index is cached in memory
- **THEN** frontend fetches all embeddings from GET /api/image-recognition/embeddings
- **AND** parses embedding vectors into Float32Arrays for efficient computation
- **AND** caches the parsed index in memory with the lastUpdated timestamp

#### Scenario: Cache validation on subsequent inference

- **WHEN** similarity inference is requested
- **AND** embeddings index is already cached in memory
- **THEN** frontend calls GET /api/image-recognition/embeddings/status
- **AND** compares server's lastUpdated with cached lastUpdated
- **AND** uses cached index if timestamps match
- **AND** re-fetches full index if server timestamp is newer

#### Scenario: Cache invalidation after photo upload

- **WHEN** a new photo embedding is saved via POST /api/image-recognition/embeddings
- **THEN** the cached embeddings index is invalidated
- **AND** next inference re-fetches the full index from the server

### Requirement: Fallback to Classifier

The system SHALL use embedding similarity as the default inference path and fall back to the existing softmax classifier when no embeddings exist.

#### Scenario: Use similarity when embeddings exist

- **WHEN** operator triggers product recognition
- **AND** GET /api/image-recognition/embeddings/status returns count > 0
- **THEN** system uses cosine similarity inference path

#### Scenario: Fall back to classifier when no embeddings

- **WHEN** operator triggers product recognition
- **AND** GET /api/image-recognition/embeddings/status returns count = 0
- **THEN** system uses existing classifier-based inference path
- **AND** inference behavior is identical to pre-change system

#### Scenario: Similarity inference failure falls back to classifier

- **WHEN** operator triggers product recognition
- **AND** embeddings exist but similarity inference fails (network error loading index, computation error)
- **THEN** system attempts classifier-based inference as fallback
- **AND** logs warning with error details

### Requirement: Suggestion Display with Similarity Scores

The system SHALL display product suggestions with similarity percentage scores, maintaining the existing suggestion card UI pattern.

#### Scenario: Display similarity-based suggestions

- **WHEN** similarity inference returns one or more suggestions
- **THEN** system displays suggestions ordered by similarity score (highest first)
- **AND** each suggestion shows:
  - Product reference photo (primary ProductPhoto)
  - SKU
  - Product name
  - Similarity score as percentage (e.g., "87%")
- **AND** first suggestion is visually highlighted (pre-selected)

#### Scenario: Operator selects from similarity suggestions

- **WHEN** operator taps/clicks a similarity-based suggestion
- **THEN** system marks selected product
- **AND** continues to quantity and payment method selection (sales-management workflow)
- **AND** captured photo is attached to sale
