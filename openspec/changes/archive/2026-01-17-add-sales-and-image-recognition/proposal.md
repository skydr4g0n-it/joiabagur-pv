> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

# Change: Add Sales Registration and AI Image Recognition

## Why

The system requires comprehensive sales registration capabilities with AI-powered image recognition to enable efficient point-of-sale operations in jewelry retail environments. This change implements the core business functionality (EP3: Sales Registration and EP4: AI Image Recognition), allowing operators to register sales through two methods: AI-assisted image recognition for fast identification, and manual product selection for cases where image recognition is unavailable or unreliable.

**Business Need:**
- Operators need to quickly register sales using mobile devices at points of sale
- Product identification in jewelry retail is challenging due to visual similarity of items
- AI image recognition reduces identification errors and speeds up sales processing
- Manual fallback ensures system remains functional when AI confidence is low
- Complete audit trail required for inventory reconciliation and business analytics

**Why combine EP3 + EP4:**
- Image recognition (EP4) is not standalone - it only serves sales registration (EP3)
- Both capabilities share the same user journey and frontend workflows
- Combining reduces proposal overhead and ensures tight integration
- Sales with and without image recognition use the same backend API and validations

## What Changes

- **NEW Capability**: `sales-management` - Complete sales registration system with dual entry methods (AI-assisted and manual)
- **NEW Capability**: `image-recognition` - Client-side AI product identification with confidence-based suggestions
- **INTEGRATION**: Extends `inventory-management` with automatic inventory movement creation on sale
- **INTEGRATION**: Uses `payment-method-management` validation for payment method availability
- **INTEGRATION**: Uses `product-management` for product catalog and reference photos
- **INTEGRATION**: Uses `access-control` for operator point-of-sale restrictions

**Sales Management (EP3):**
- Sales registration endpoint with transaction-based stock updates
- Dual registration methods: with image recognition (photo attached) or manual selection
- Multi-unit sales support (editable quantity field)
- Stock validation before sale (assignment + sufficient quantity)
- Payment method validation (active and assigned to POS)
- Automatic inventory movement creation (type "Sale") in same transaction
- Low stock warnings after sale (non-blocking, informational)
- Price snapshot capture (current product price frozen in Sale record)
- Optional notes field for sale annotations
- Sales history with filters and pagination

**Image Recognition (EP4):**
- Client-side ML inference using TensorFlow.js or ONNX.js
- Model download and caching (one-time download, executed locally)
- Product photo capture from mobile camera
- Image preprocessing (resize, normalize) before inference
- Generate 3-5 product suggestions ordered by confidence score
- Display suggestions with reference photos, SKU, name, and confidence percentage
- Configurable confidence threshold (default 40%) for fallback to manual entry
- Model training executed locally on admin's machine (not on server)
- Trained model uploaded to S3/storage for distribution
- Photo compression before storage (JPEG quality 80%, max 2MB)
- Photos saved only on successful sale completion
- Intelligent fallback: redirect to manual entry on low confidence with photo preserved

## Scope Clarifications

**MVP Scope (This Phase):**
- ? Sales registration (manual and with image recognition)
- ? Image recognition with online model version check
- ? **Browser-based model training** (admin trains model in browser using TensorFlow.js - no Python required)
- ? Model upload to S3 via admin dashboard (automatic after browser training)
- ? Model metadata management (version, date, accuracy)
- ? Transaction-based inventory updates
- ? Photo compression and storage

**Deferred to Phase 2 (Documented but NOT Implemented):**
- ?? Offline model usage (cached model when no network)
- ?? Progressive Web App offline capabilities
- ?? Push notifications for new model versions
- ?? Automatic model retraining triggers

**Explicitly NOT Supported (Disabled):**
- ? Server-side training (disabled to keep AWS infrastructure within free-tier limits)
- ? Python-based local training scripts (removed - browser training is the only option)

**Rationale:** Browser-based TensorFlow.js training is the most user-friendly approach for MVP. It requires **zero Python installation** on the admin's machine - just a modern browser with WebGL 2.0 support. Training leverages the admin's GPU (if available) for faster performance. Server-side training is disabled to keep AWS infrastructure costs minimal.

## Model Retraining Strategy

**Admin Dashboard with Model Health Metrics:**
- Dashboard at `/admin/ai-model` shows model health metrics and alert level
- Automated scoring system calculates when retraining is needed based on:
  - Catalog changes (new products, photo additions/deletions)
  - Model staleness (days since last training)
  - Precision metrics (Phase 2 - optional in MVP)
- Alert levels: ?? CRITICAL, ?? HIGH, ?? RECOMMENDED, ? OK
- Toast notifications on admin login for CRITICAL and HIGH priority alerts

**Browser-Based Training Infrastructure (MVP):**
- **Training location:** Admin's browser (TensorFlow.js with WebGL acceleration)
- **Requirements:** Modern browser (Chrome/Edge 90+, Safari 14+, Firefox 88+), WebGL 2.0, 8GB+ RAM recommended
- **No Python required!** ?
- **Process:**
  1. Admin clicks "Train Model" button in dashboard
  2. Browser downloads product photos from server (~5-10MB, 30-60 seconds)
  3. Browser trains model using TensorFlow.js (GPU accelerated via WebGL)
  4. Browser uploads trained model to server automatically
  5. Backend stores model and updates metadata
- **Duration:** 10-20 minutes with GPU (WebGL), 30-60 minutes CPU-only (WASM fallback)
- **Cost:** $0 additional AWS infrastructure

**Training UX:**
- Admin must keep browser tab open during training
- Real-time progress updates (download ? train ? upload stages)
- Prominent warning: "?? Keep this tab open during training"
- Device capability check before training (GPU detected, memory check, battery status)
- Estimated duration shown before starting

**Server-Side Training: DISABLED**
- Server-side training is explicitly disabled to keep AWS within free-tier limits
- No Python runtime on server, no BackgroundService for training
- All training happens in the browser

**Notification Strategy:**
- Toast on admin login when alert level is CRITICAL or HIGH
- No persistent badges or email notifications (simplified UX)
- Dashboard always accessible to check current status

## Impact

- **Affected specs**: 
  - New capability: `sales-management`
  - New capability: `image-recognition`
  - Extended capability: `inventory-management` (adds automatic movement creation)
  - Referenced capability: `payment-method-management` (validation integration)
  - Referenced capability: `product-management` (product data and photos)
  - Referenced capability: `access-control` (operator POS restrictions)
  
- **Affected code**: 
  - New domain entities: `Sale`, `SalePhoto` (already in data model)
  - New services: `ISalesService`, `IImageRecognitionService`, `IPaymentMethodValidationService`
  - Extended services: `IStockValidationService` (added to inventory-management), `IInventoryService.CreateSaleMovement`
  - New API controllers: `SalesController`, `ImageRecognitionController`
  - New frontend modules: Sales registration (with/without image), Image capture and suggestion display
  - ML integration: TensorFlow.js/ONNX.js library, model loading and inference
  - File storage: Photo upload and compression (IFileStorageService integration)
  
- **Dependencies**: 
  - Requires `product-management` (EP1) - products and reference photos
  - Requires `inventory-management` (EP2) - stock validation and automatic movements
  - Requires `payment-method-management` (EP6) - payment validation
  - Requires `point-of-sale-management` (EP8) - POS context
  - Requires `access-control` (EP7) - operator restrictions
  - Requires trained ML model for image recognition (deployment artifact)
  
- **Breaking changes**: None (new capabilities)

- **Infrastructure**: 
  - Model hosting: ML model file served via backend endpoint or CDN
  - Storage: Photo compression before save (JPEG 80%, max 2MB)
  - File access: IFileStorageService provides provider-agnostic abstraction (local filesystem for dev, S3/Blob for production)
  - Photo URLs: Backend serves photos through API endpoint (no direct storage URLs, maintains provider independence)
  - Model retraining: Backend endpoint to trigger rebuild (manual trigger in MVP, automated in Phase 2)
  - Initial deployment: Application deploys without pre-trained model (manual entry works, admin trains first model after deployment)

