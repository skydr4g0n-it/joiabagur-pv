# image-recognition Specification

## Purpose

Identify products from POS photos using in-browser transfer learning, confidence thresholds, and operator confirmation before sale.

## Requirements
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

### Requirement: Image Preprocessing

The system SHALL preprocess captured photos to optimize ML inference quality and speed, ensuring consistent input to the model.

#### Scenario: Preprocess image for inference

- **WHEN** operator captures product photo
- **THEN** frontend resizes image to model input size (224x224 pixels)
- **AND** normalizes pixel values to [0, 1] range
- **AND** converts to RGB if image is grayscale or RGBA
- **AND** applies center cropping if aspect ratio doesn't match (preserve main subject)
- **AND** preprocessing completes in <100ms

#### Scenario: Validate image format

- **WHEN** operator provides image file
- **THEN** system validates format is JPEG, PNG, or HEIC
- **AND** rejects unsupported formats (GIF, BMP) with error message
- **AND** converts HEIC to JPEG if needed (browser support)

#### Scenario: Handle image quality issues

- **WHEN** captured photo is very blurry, dark, or overexposed
- **THEN** inference may produce low confidence scores
- **AND** system redirects to manual entry if all confidences < 40%
- **AND** operator can retake photo with better lighting/focus

### Requirement: Browser-Based Model Training Capability

The system SHALL support model training executed in administrator's browser using TensorFlow.js, with automatic upload of trained models to storage. No Python installation required.

Class labels SHALL use `ProductSku` (immutable, unique) instead of `ProductName` to ensure stable model-to-product mapping after product name edits.

#### Scenario: Check device capabilities before training

- **WHEN** administrator clicks "Train Model" button
- **THEN** browser checks WebGL 2.0 support (GPU acceleration)
- **AND** browser checks available memory (recommend 8GB+, minimum 2GB)
- **AND** browser checks battery status (warn if on battery)
- **AND** displays estimated training duration (GPU: 15-20min, CPU: 45-60min)
- **AND** shows device capability summary (GPU detected: Yes/No, Memory: XGB)

#### Scenario: Download photos for browser training

- **WHEN** administrator confirms training start
- **THEN** browser fetches product photos from GET /api/products/photos/training-dataset
- **AND** downloads photos in parallel batches (10 photos per batch)
- **AND** displays download progress (X/Y photos - Z MB downloaded)
- **AND** photos are held in memory (not saved to disk)

#### Scenario: Execute browser training

- **WHEN** photos are downloaded successfully
- **THEN** browser loads pre-trained MobileNetV2 from TensorFlow Hub
- **AND** applies data augmentation (rotation ±15°, brightness ±20%, flip, zoom ±10%)
- **AND** adds custom classification head for product classes
- **AND** trains for 15 epochs with validation split 0.2
- **AND** displays training progress (Epoch X/15, Accuracy: Y%, Loss: Z)
- **AND** training uses WebGL GPU acceleration if available (WASM fallback)

#### Scenario: Upload trained model automatically

- **WHEN** browser training completes successfully
- **THEN** browser saves checkpoint to IndexedDB (backup)
- **AND** browser uploads trained model to POST /api/image-recognition/upload-trained-model
- **AND** displays upload progress (X MB / Y MB uploaded)
- **AND** server validates model format and stores in /ml-models/v{version}/
- **AND** server updates ModelMetadata table (version, uploaded_at, accuracy_metrics)
- **AND** displays success message with model version and accuracy

#### Scenario: Validate uploaded model

- **WHEN** model files are uploaded to server
- **THEN** system validates model.json exists and is valid TensorFlow.js format
- **AND** validates weight data is complete and correct size
- **AND** validates total model size is within limits (<20MB)
- **AND** rejects upload if validation fails with descriptive error

#### Scenario: Keep browser tab open during training

- **WHEN** training is in progress
- **THEN** browser displays prominent warning: "⚠️ Keep this tab open during training"
- **AND** browser shows beforeunload warning if user tries to close tab
- **AND** training progress updates in real-time (no polling)
- **AND** admin cannot navigate away without warning

#### Scenario: Initial deployment without model

- **WHEN** application is deployed for first time
- **AND** no model has been trained yet
- **THEN** GET /api/image-recognition/model returns 404 Not Found
- **AND** GET /api/image-recognition/model/metadata returns empty or null
- **AND** frontend detects no model available
- **AND** image recognition option shows "No disponible (entrenar modelo primero)"
- **AND** admin dashboard shows "Train First Model" button
- **AND** only manual sales entry is available

#### Scenario: First model training after deployment

- **WHEN** administrator uploads product photos (via EP1)
- **AND** trains first model via browser dashboard
- **THEN** browser trains model using TensorFlow.js
- **AND** browser uploads trained model to server
- **AND** server stores model and updates ModelMetadata
- **AND** image recognition becomes available for operators

#### Scenario: Preserve previous model on new training

- **WHEN** administrator trains new model version
- **THEN** system does not delete previous model files
- **AND** previous model remains accessible via versioned path
- **AND** ModelMetadata history preserves all versions
- **AND** admin can rollback by updating metadata to point to previous version (Phase 2)

#### Scenario: Server-side training disabled

- **WHEN** POST /api/image-recognition/retrain is called
- **THEN** system returns 501 Not Implemented
- **AND** response message: "Server-side training is disabled. Use browser-based training."
- **AND** no BackgroundService or Python scripts are executed

### Requirement: Model Metadata and Versioning

The system SHALL track model versions, training dates, and accuracy metrics to enable model management and rollback if needed.

#### Scenario: Store model metadata

- **WHEN** model retraining completes successfully
- **THEN** system creates or updates ModelMetadata record
- **AND** stores version (timestamp or semantic version)
- **AND** stores last_trained_at (UTC timestamp)
- **AND** stores model_path (storage path to .json and .bin files)
- **AND** stores accuracy_metrics (JSON: top-1 accuracy, top-3 accuracy, loss)
- **AND** stores training_duration (seconds)

#### Scenario: Retrieve model metadata

- **WHEN** frontend requests GET /api/image-recognition/model/metadata
- **THEN** system returns latest model metadata in JSON format
- **AND** includes version (e.g., "v2_20260111" - semantic version with date)
- **AND** includes last_trained_at (ISO 8601 UTC timestamp)
- **AND** includes accuracy metrics (top-1, top-3 accuracy percentages)
- **AND** includes model_url (download path: "/api/image-recognition/model?version=v2_20260111")
- **AND** includes model_size_bytes (for download progress estimation)
- **AND** frontend displays in UI ("Modelo v2, entrenado hace 5 días, precisión 82%")

#### Scenario: Model metadata response format

- **WHEN** frontend receives model metadata response
- **THEN** response follows format:
  ```json
  {
    "version": "v2_20260111",
    "last_trained_at": "2026-01-11T14:30:00Z",
    "accuracy_metrics": {
      "top_1_accuracy": 0.75,
      "top_3_accuracy": 0.89
    },
    "model_url": "/api/image-recognition/model?version=v2_20260111",
    "model_size_bytes": 14680064,
    "created_at": "2026-01-11T14:30:00Z"
  }
  ```
- **AND** frontend uses version string for cache comparison
- **AND** frontend uses model_size_bytes for download progress indicator

#### Scenario: Admin views model history

- **WHEN** administrator accesses model management page
- **THEN** system displays list of previous model versions
- **AND** shows version, trained date, accuracy for each
- **AND** indicates currently active version
- **NOTE**: Phase 2 feature - version rollback

### Requirement: Photo Capture from Mobile Camera

The system SHALL provide intuitive photo capture functionality optimized for mobile devices, allowing operators to take photos of products using device camera.

#### Scenario: Access device camera

- **WHEN** operator taps "Capturar foto" button
- **THEN** frontend requests camera permission (if not granted)
- **AND** displays camera viewfinder fullscreen
- **AND** shows capture button and cancel button
- **AND** uses rear camera by default (jewelry product photos)

#### Scenario: Handle camera permission denial

- **WHEN** operator denies camera permission
- **THEN** system displays error: "Se requiere acceso a la cámara para reconocimiento de imagen"
- **AND** offers alternative: "Registrar venta manual"
- **AND** redirects to manual entry workflow

#### Scenario: Capture photo

- **WHEN** operator taps capture button
- **THEN** camera takes photo
- **AND** displays photo preview with options: "Usar esta foto" or "Tomar otra"
- **AND** photo is temporarily held in memory (not saved to storage yet)

#### Scenario: Retake photo

- **WHEN** operator taps "Tomar otra" in preview
- **THEN** system discards captured photo
- **AND** reopens camera viewfinder
- **AND** operator can capture new photo

#### Scenario: Cancel photo capture

- **WHEN** operator taps cancel button during capture or preview
- **THEN** system discards captured photo
- **AND** returns to previous screen (sales menu or home)
- **AND** no photo is saved

### Requirement: Model Performance and Optimization

The system SHALL optimize model size and inference speed to ensure fast, responsive image recognition on mobile devices with limited resources.

#### Scenario: Optimize model size

- **WHEN** model is exported to TensorFlow.js format
- **THEN** system applies quantization (int8 or float16) to reduce file size
- **AND** target model size <= 15MB total (.json + .bin files)
- **AND** ensures accuracy loss from quantization is minimal (<2% accuracy drop)

#### Scenario: Fast inference on mobile

- **WHEN** operator triggers inference on mobile device
- **THEN** inference completes in <500ms (median)
- **AND** uses WebGL acceleration if available (GPU)
- **AND** falls back to WASM if WebGL not supported
- **AND** displays loading indicator during inference

#### Scenario: Progressive model loading

- **WHEN** model download is in progress
- **THEN** frontend shows manual entry option immediately
- **AND** loads model in background
- **AND** enables image recognition once model ready
- **AND** operator can proceed with manual entry without waiting

### Requirement: Device Compatibility Requirements

The system SHALL validate minimum device requirements for running TensorFlow.js inference, redirecting to manual entry with clear message if device is incompatible.

#### Scenario: Check device compatibility on feature access

- **WHEN** operator accesses image recognition functionality
- **THEN** frontend checks device compatibility:
  - Browser: Chrome/Edge 90+, Safari 14+, Firefox 88+
  - WebGL 2.0 support (GPU acceleration)
  - TensorFlow.js backend availability (WebGL or WASM)
- **AND** proceeds if compatible
- **AND** shows error if incompatible

#### Scenario: Incompatible device error

- **WHEN** device fails compatibility check (no WebGL 2.0, browser too old, insufficient RAM)
- **THEN** system displays error message:
  "Tu dispositivo no es compatible con reconocimiento de imágenes.
   Requisitos: iOS 12+, Android 8+, navegador moderno.
   
   [Registrar Venta Manual]"
- **AND** redirects to manual sales entry
- **AND** image recognition option remains hidden for that device

#### Scenario: Fallback to WASM if WebGL unavailable

- **WHEN** device supports TensorFlow.js but WebGL is unavailable
- **THEN** system attempts to use WASM backend (CPU inference)
- **AND** displays warning: "Reconocimiento puede ser más lento en este dispositivo"
- **AND** inference may take >1 second (still functional, just slower)

#### Scenario: Log device compatibility for analytics

- **WHEN** compatibility check is performed
- **THEN** system logs device info (browser, OS, WebGL support) for analytics
- **AND** helps identify common incompatible devices
- **NOTE**: Analytics logging optional, deferred to Phase 2

### Requirement: Image Recognition Validation and Error Handling

The system SHALL handle errors gracefully during image recognition workflow, ensuring operators can always complete sales even if AI fails.

#### Scenario: Handle no products with photos

- **WHEN** operator attempts image recognition
- **AND** no products in operator's assigned POS have reference photos (ProductPhoto)
- **THEN** system displays error: "No hay productos con fotos de referencia en este punto de venta"
- **AND** provides link: "Configurar productos con fotos" (admin) or "Registrar venta manual" (operator)
- **AND** prevents inference execution (no training data)

#### Scenario: Handle inference timeout

- **WHEN** inference takes >5 seconds (device too slow, model too large)
- **THEN** system displays error: "El reconocimiento está tardando demasiado"
- **AND** offers options: "Esperar" or "Registrar venta manual"
- **AND** if inference completes after timeout, shows suggestions

#### Scenario: Handle corrupted model

- **WHEN** downloaded model files are corrupted or incomplete
- **THEN** system detects error during model.loadLayersModel()
- **AND** clears IndexedDB cache
- **AND** displays error: "Error al cargar el modelo. Intentando recargar..."
- **AND** attempts fresh download once
- **AND** if second attempt fails, redirects to manual entry

#### Scenario: Fallback to manual entry always available

- **WHEN** any error occurs in image recognition workflow (camera failure, model loading, inference failure)
- **THEN** system ALWAYS provides "Registrar venta manual" option
- **AND** ensures sales workflow is never completely blocked by AI issues
- **AND** preserves captured photo if available (attach to manual sale)

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
  - Precision <70% → CRITICAL
  - >=20% new products → CRITICAL
  - >=10% new products → HIGH
  - >=20% photo changes → HIGH
  - >=10% photos deleted → HIGH
  - Model >30 days + (>=5% products or >=10% photos changed) → HIGH
  - Model >60 days → RECOMMENDED
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

### Requirement: Photo Content Validation

The system SHALL validate photo quality and dimensions before accepting uploads for product reference photos, ensuring suitable training data quality.

#### Scenario: Validate minimum photo dimensions

- **WHEN** administrator or operator uploads product photo
- **THEN** system validates dimensions are at least 200x200 pixels
- **AND** rejects photos smaller than minimum with error: "La foto debe tener al menos 200x200 píxeles"

#### Scenario: Validate aspect ratio

- **WHEN** photo is uploaded
- **THEN** system validates aspect ratio is not extreme (max 5:1 or 1:5)
- **AND** rejects photos with aspect ratio > 5:1 with error: "La foto tiene proporciones extremas. Usa una foto más cuadrada."

#### Scenario: Detect completely black or white images

- **WHEN** photo is uploaded
- **THEN** system analyzes image histogram (client-side using canvas API)
- **AND** rejects photos that are >95% single color (black or white)
- **AND** displays error: "La foto parece estar completamente oscura o sobreexpuesta. Toma otra foto."

#### Scenario: Validate file size after upload

- **WHEN** photo passes content validation
- **THEN** system validates file size <= 2MB after compression
- **AND** rejects if compressed size exceeds limit
- **AND** displays error: "La foto es demasiado grande incluso después de compresión. Intenta con una foto de menor resolución."

#### Scenario: Client-side validation before upload

- **WHEN** operator selects photo from camera or gallery
- **THEN** frontend performs all validations (dimensions, aspect ratio, histogram) before upload
- **AND** shows validation errors immediately (no network call)
- **AND** operator can retake photo or select different image

### Requirement: Training Data Validation

The system SHALL validate sufficient training data exists before allowing model retraining, ensuring model quality and preventing training failures.

#### Scenario: Validate minimum training data

- **WHEN** administrator triggers model retraining
- **THEN** system checks total ProductPhoto count in database
- **AND** requires at least 50 total photos (10 products × 5 photos minimum)
- **AND** returns 400 Bad Request if insufficient photos: "Se requieren al menos 50 fotos para entrenar el modelo"

#### Scenario: Validate photo distribution

- **WHEN** training job starts
- **THEN** system checks each product has at least 1 photo
- **AND** logs warning if any products have <3 photos (low accuracy expected)
- **AND** includes warning in training completion notification

#### Scenario: Validate photo accessibility

- **WHEN** training job fetches photos from storage
- **THEN** system validates all ProductPhoto.FilePath files exist in storage
- **AND** skips missing photos with warning logged
- **AND** fails training if >10% of photos are missing
- **AND** notifies administrator of missing photos

### Requirement: Model Retraining Required After SKU Migration

The system SHALL require model retraining when migrating from ProductName-based to ProductSku-based class labels, as existing trained models become incompatible with the new mapping scheme.

#### Scenario: Existing model incompatible after migration

- **WHEN** system is upgraded from ProductName to ProductSku class labels
- **AND** previously trained model exists
- **THEN** inference will fail to match class labels to class predictions
- **AND** system detects mismatch between model outputs and class labels
- **AND** displays warning: "El modelo fue entrenado con una versión anterior. Re-entrene el modelo."
- **AND** redirects to manual entry until model is retrained

#### Scenario: Administrator retrains model after migration

- **WHEN** administrator accesses model training after migration
- **THEN** system displays notice: "Se requiere re-entrenamiento para usar reconocimiento de imágenes"
- **AND** training proceeds normally using SKU-based class labels
- **AND** new model is compatible with inference system
