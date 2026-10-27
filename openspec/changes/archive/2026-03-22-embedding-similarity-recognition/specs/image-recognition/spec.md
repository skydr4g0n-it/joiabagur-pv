> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

## MODIFIED Requirements

### Requirement: Client-Side ML Inference

The system SHALL execute machine learning inference in the browser/mobile device using TensorFlow.js, eliminating server-side ML costs and reducing latency for product identification.

#### Scenario: Download model on first use

- **WHEN** operator accesses image recognition for first time
- **AND** no embeddings are available (embedding count = 0)
- **THEN** frontend fetches ML model from GET /api/image-recognition/model
- **AND** backend serves TensorFlow.js model files (.json + .bin shard files)
- **AND** frontend displays loading indicator: "Descargando modelo de IA... X%"
- **AND** model is cached in browser IndexedDB after download
- **AND** subsequent uses load model from cache (no re-download)

#### Scenario: Load embeddings index on first use

- **WHEN** operator accesses image recognition for first time
- **AND** embeddings are available (embedding count > 0)
- **THEN** frontend fetches all embeddings from GET /api/image-recognition/embeddings
- **AND** parses embedding vectors into Float32Arrays
- **AND** caches parsed index in memory with lastUpdated timestamp
- **AND** loads MobileNetV2 feature extractor for query image processing

#### Scenario: Check model version and update

- **WHEN** frontend loads from cache
- **AND** system is using classifier-based inference (no embeddings)
- **THEN** system checks GET /api/image-recognition/model/metadata for current version
- **AND** compares cached version with server version
- **AND** downloads new model if version changed
- **AND** updates IndexedDB cache with new version

#### Scenario: Check embeddings staleness

- **WHEN** frontend has embeddings index cached in memory
- **AND** operator accesses image recognition
- **THEN** frontend calls GET /api/image-recognition/embeddings/status
- **AND** compares server lastUpdated with cached lastUpdated
- **AND** re-fetches full embeddings index if server timestamp is newer
- **AND** uses cached index if timestamps match

#### Scenario: Version check with network connectivity

- **WHEN** operator accesses image recognition functionality
- **AND** device has internet connection
- **THEN** frontend ALWAYS fetches model metadata from server (no time restriction)
- **AND** check is performed in background (non-blocking)
- **AND** cached model is used immediately while check executes
- **AND** compares cached version with server version
- **AND** if server version is newer, frontend downloads new model in background
- **AND** displays notification: "Nueva versión del modelo disponible. Descargando..."
- **AND** switches to new model after download completes
- **NOTE**: Version check executes on every access when online to ensure latest model

#### Scenario: Version check without network connectivity

- **WHEN** operator accesses image recognition functionality
- **AND** device has no internet connection
- **THEN** system detects network error on metadata fetch
- **AND** uses cached model without version check
- **AND** logs warning: "No se pudo verificar versión del modelo (offline)"
- **AND** inference proceeds normally with cached model
- **AND** version check retries on next feature access when connectivity restored

#### Scenario: Outdated model notification

- **WHEN** frontend detects cached model is older than server version
- **AND** model age > 7 days behind latest
- **THEN** system displays notification to operator: "El modelo de reconocimiento tiene una actualización disponible"
- **AND** provides option to download immediately or continue with current version
- **AND** allows operator to defer update (e.g., not during active sale)

#### Scenario: Manual model update trigger

- **WHEN** operator or admin clicks "Actualizar modelo" button in settings
- **THEN** frontend forces fresh metadata check
- **AND** downloads latest model if newer version exists
- **AND** displays progress: "Descargando modelo... X%"
- **AND** updates IndexedDB cache with new model
- **AND** confirms: "Modelo actualizado a versión vX"

#### Scenario: Execute inference locally

- **WHEN** operator captures product photo
- **AND** model is loaded (from cache or fresh download)
- **THEN** frontend preprocesses image (resize to 224x224, normalize pixel values)
- **AND** if embeddings exist: extracts MobileNetV2 features and computes cosine similarity against stored embeddings
- **AND** if no embeddings: executes model.predict() on preprocessed image using classifier
- **AND** returns top 3-5 products ordered by score (descending)
- **AND** inference completes in <500ms on mobile device

#### Scenario: Fallback on model loading failure

- **WHEN** model fails to download (network error, storage full, corrupted file)
- **THEN** frontend displays error: "No se pudo cargar el modelo de IA"
- **AND** automatically redirects to manual entry workflow
- **AND** operator can retry model download or proceed with manual entry
- **AND** system remains functional (graceful degradation)

### Requirement: Product Suggestions with Confidence Scores

The system SHALL generate 3-5 product suggestions ordered by confidence score, displaying reference photos, product details, and confidence percentages to assist operator selection.

Inference matching SHALL use `ProductSku` to resolve class predictions to product details, ensuring stability when product names are edited.

#### Scenario: Display suggestions with confidence scores

- **WHEN** inference completes successfully
- **AND** at least one product has score >= threshold (0.70 cosine similarity for embeddings, 40% softmax for classifier)
- **THEN** system displays top 3-5 suggestions ordered by score (highest first)
- **AND** number of suggestions shown depends on how many exceed threshold (variable: 3-5 max)
- **AND** each suggestion shows:
  - Product reference photo (primary ProductPhoto)
  - SKU
  - Product name
  - Score as percentage (e.g., "85%")
- **AND** suggestions are visually distinct (cards or list with photos)
- **AND** operator can select any suggestion by tapping/clicking

#### Scenario: Show 3 suggestions when only 3 exceed threshold

- **WHEN** inference generates exactly 3 products with score >= threshold
- **THEN** system displays exactly 3 suggestions
- **AND** does not show 4th or 5th product if score < threshold

#### Scenario: Show 5 suggestions when many exceed threshold

- **WHEN** inference generates 5 or more products with score >= threshold
- **THEN** system displays top 5 suggestions (capped at 5)
- **AND** does not show 6th product even if score >= threshold

#### Scenario: Show 4 suggestions when 4 exceed threshold

- **WHEN** inference generates exactly 4 products with score >= threshold
- **THEN** system displays exactly 4 suggestions

#### Scenario: Highlight top suggestion

- **WHEN** suggestions are displayed
- **THEN** system visually highlights first suggestion (highest score)
- **AND** first suggestion is pre-selected or emphasized (e.g., larger card, different color)
- **AND** operator can confirm top suggestion or select alternative

#### Scenario: Select product from suggestions

- **WHEN** operator taps/clicks a suggestion
- **THEN** system marks selected product
- **AND** continues to quantity and payment method selection (sales-management workflow)
- **AND** captured photo is attached to sale

### Requirement: Confidence Threshold and Fallback

The system SHALL use configurable thresholds to determine when to show suggestions vs redirect to manual entry, ensuring operator only sees reliable suggestions.

For embedding similarity: SIMILARITY_THRESHOLD = 0.70 (minimum to include), MIN_TOP_SIMILARITY = 0.50 (minimum for top match to return any result).
For classifier fallback: confidence threshold = 40%.

#### Scenario: Show suggestions when score above threshold

- **WHEN** inference generates at least one product with score >= threshold
- **THEN** system displays suggestions (top 3-5 products >= threshold)
- **AND** operator can select from suggestions or choose "None of these" option

#### Scenario: Redirect to manual entry when all scores below threshold

- **WHEN** inference completes
- **AND** for similarity: top match < 0.50 (MIN_TOP_SIMILARITY)
- **AND** for classifier: ALL products have confidence < 40%
- **THEN** system displays message: "No se encontró una correspondencia fiable"
- **AND** offers options:
  - "Tomar otra foto" (retry image recognition)
  - "Registrar venta manual" (redirect to manual entry with photo preserved)
- **AND** if operator chooses manual entry, captured photo is preserved as optional attachment

#### Scenario: Manual override option

- **WHEN** suggestions are displayed (score >= threshold)
- **THEN** system provides "Ninguno coincide" button
- **AND** clicking button redirects to manual entry with photo preserved
- **AND** operator can search product manually while retaining captured photo

#### Scenario: Configure confidence threshold (Phase 2)

- **WHEN** administrator accesses model configuration settings
- **THEN** system allows adjusting confidence threshold (range: 20%-80%)
- **AND** new threshold applies to future inferences
- **NOTE**: MVP uses fixed thresholds, configuration deferred to Phase 2

### Requirement: Admin Dashboard for Model Health Monitoring

The system SHALL provide administrators with a dashboard showing model health metrics, catalog changes, embedding status, and automated alerts to determine when retraining or embedding regeneration is necessary.

#### Scenario: Display model health dashboard

- **WHEN** authenticated administrator navigates to /admin/ai-model
- **THEN** system displays model status card with current version, last trained date, and current accuracy
- **AND** shows embedding status card with embedding count, last updated timestamp, and "Generar Embeddings" button
- **AND** shows alert level (CRITICAL, HIGH, RECOMMENDED, OK) with icon and recommendation
- **AND** displays catalog metrics (total products, with/without photos, new products not in model)
- **AND** displays photo metrics (total, added since training, deleted since training, net change %)
- **AND** shows "Re-train Model Now" button for classifier
- **AND** shows "Generar Embeddings" button for similarity system

#### Scenario: Calculate retraining alert level

- **WHEN** system calculates model health status
- **THEN** evaluates multiple criteria:
  - Precision <70% ? CRITICAL
  - >=20% new products ? CRITICAL
  - >=10% new products ? HIGH
  - >=20% photo changes ? HIGH
  - >=10% photos deleted ? HIGH
  - Model >30 days + (>=5% products or >=10% photos changed) ? HIGH
  - Model >60 days ? RECOMMENDED
- **AND** returns highest severity alert level

#### Scenario: Show toast notification on admin login

- **WHEN** administrator logs in
- **AND** model health status is CRITICAL or HIGH
- **THEN** system displays toast notification with alert message
- **AND** toast includes "View Dashboard" button linking to /admin/ai-model
- **AND** toast auto-dismisses after 10 seconds (or until user clicks)

#### Scenario: Critical alert for low precision

- **WHEN** top-3 accuracy is <70% based on last 100 sales with image recognition
- **THEN** dashboard shows CRITICAL alert: "Precisión muy baja, re-entrenar inmediatamente"
- **AND** toast notification appears on admin login

#### Scenario: High priority alert for catalog changes

- **WHEN** 45 new products added (9% of 500 total) and 127 new photos uploaded
- **THEN** dashboard shows HIGH alert: "Cambios significativos en catálogo"
- **AND** toast notification appears on admin login

#### Scenario: OK status when model is current

- **WHEN** model trained 5 days ago
- **AND** only 2 new products (0.4%)
- **AND** only 10 new photos (0.4%)
- **THEN** dashboard shows OK: "Modelo actualizado"
- **AND** no toast notification appears

#### Scenario: Precision metrics unavailable in MVP

- **WHEN** precision tracking not implemented (Phase 2 feature)
- **THEN** dashboard shows precision section as "No disponible (Fase 2)"
- **AND** alert level calculated without precision criterion

#### Scenario: Hide dashboard from operators

- **WHEN** operator user attempts to access /admin/ai-model
- **THEN** system returns 403 Forbidden
- **AND** dashboard link not visible in operator menu
