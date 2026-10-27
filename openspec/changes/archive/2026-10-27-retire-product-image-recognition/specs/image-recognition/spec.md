## ADDED Requirements

### Requirement: Withdrawn product-photo recognition
The system SHALL NOT offer product-photo image recognition in the user interface. The system SHALL NOT show model-health warnings, an AI-model admin page, or a sales flow that captures a photo to suggest products. Every HTTP route under `/api/image-recognition` SHALL respond that the capability is withdrawn and SHALL NOT execute the previous model, health, training, or embedding behavior.

#### Scenario: Administrator session shows no model warning
- **GIVEN** an authenticated administrator
- **WHEN** the administrator opens the application
- **THEN** the interface does not request model health
- **AND** the interface does not show a toast about the AI model

#### Scenario: Retired routes are absent
- **GIVEN** an authenticated user
- **WHEN** the user opens `/admin/ai-model` or `/sales/new/image`
- **THEN** the application does not render a recognition page
- **AND** the existing unmatched-route rule navigates to `/dashboard`
- **AND** the sidebar does not contain an entry named "Modelo de IA"

#### Scenario: Authenticated API call is withdrawn
- **GIVEN** an authenticated caller
- **WHEN** the caller requests any route under `/api/image-recognition`, including model metadata, model health, model versions, model files, retrain, training dataset, class labels, and embeddings
- **THEN** the response status is 410 Gone
- **AND** the response body states that product-photo image recognition is withdrawn
- **AND** the handler does not read or write model files, embeddings, or training jobs

#### Scenario: Unauthenticated API call stays unauthorized
- **GIVEN** a caller without a valid access token
- **WHEN** the caller requests any route under `/api/image-recognition`
- **THEN** the response status is 401 Unauthorized

#### Scenario: Integration coverage of the withdrawn API
- **GIVEN** the image-recognition integration tests
- **WHEN** those tests call representative routes, including `GET /api/image-recognition/model/health` and `GET /api/image-recognition/embeddings`
- **THEN** authenticated calls assert status 410
- **AND** unauthenticated calls assert status 401

## REMOVED Requirements

### Requirement: Client-Side ML Inference
**Reason**: Product-photo recognition is no longer used.
**Migration**: Use manual product selection in sales. The API returns 410 Gone.

### Requirement: Product Suggestions with Confidence Scores
**Reason**: Suggestion UI is removed with recognition.
**Migration**: Operators select the product manually.

### Requirement: Confidence Threshold and Fallback
**Reason**: There is no inference result to threshold.
**Migration**: No client action. Manual sales remain.

### Requirement: Image Preprocessing
**Reason**: The browser no longer prepares images for a recognition model.
**Migration**: Product photo upload keeps its existing catalog validation only.

### Requirement: Browser-Based Model Training Capability
**Reason**: In-browser training is unused.
**Migration**: Do not train or upload a model. The upload route returns 410.

### Requirement: Model Metadata and Versioning
**Reason**: The client no longer selects or downloads a model.
**Migration**: Stored model metadata remains in the database. Metadata routes return 410.

### Requirement: Photo Capture from Mobile Camera
**Reason**: The recognition sales page is removed.
**Migration**: Register the sale from the manual sales page.

### Requirement: Model Performance and Optimization
**Reason**: No client inference remains to optimize.
**Migration**: None.

### Requirement: Device Compatibility Requirements
**Reason**: No recognition runtime remains in the client.
**Migration**: None.

### Requirement: Image Recognition Validation and Error Handling
**Reason**: The recognition flow is removed.
**Migration**: Sales validation for stock, payment method, and price stays on the manual flow.

### Requirement: Admin Dashboard for Model Health Monitoring
**Reason**: Administrators must no longer see model warnings or a model dashboard.
**Migration**: Remove the page, menu entry, and health toast. Health routes return 410.

### Requirement: Photo Content Validation
**Reason**: These checks existed to prepare recognition training data.
**Migration**: Catalog photo rules remain under product-management. This recognition-specific validation is not required.

### Requirement: Training Data Validation
**Reason**: Retraining is withdrawn.
**Migration**: The retrain route returns 410.

### Requirement: Model Retraining Required After SKU Migration
**Reason**: No active model is required after this change.
**Migration**: Do not retrain. Existing stored models stay unused.
