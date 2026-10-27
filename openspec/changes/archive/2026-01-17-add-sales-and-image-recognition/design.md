> **Withdrawn (2026-10-27):** Product-photo image recognition was retired. This document is historical. Current behavior is manual sales only, and /api/image-recognition returns 410 Gone.

# Design: Sales Registration and AI Image Recognition

## Context

Jewelry retail requires fast, accurate product identification at point of sale. Products are visually similar, making manual SKU lookup error-prone and slow. AI-powered image recognition addresses this by providing instant suggestions based on reference photos, while maintaining a manual fallback for reliability.

**Stakeholders:**
- Operators: Need fast, intuitive sales registration on mobile devices
- Administrators: Need accurate inventory tracking and sales data
- Business: Needs audit trail for reconciliation and analytics

**Constraints:**
- Mobile-first design (operators use tablets/phones at POS)
- Free-tier cloud deployment (minimize server-side ML costs)
- ~500 products in catalog (manageable for client-side inference)
- 2-3 concurrent users (low traffic, prioritize simplicity)

## Goals / Non-Goals

**Goals:**
- Enable fast sales registration with image recognition (~5 seconds from photo to suggestion)
- Maintain data consistency between Sales and Inventory (atomic transactions)
- Provide reliable fallback when AI confidence is low (<40%)
- Support model retraining when product catalog changes
- Minimize server costs by processing images client-side

**Non-Goals (Deferred to Phase 2):**
- Automatic model retraining on photo upload (manual trigger in MVP)
- Advanced analytics dashboard for sales trends
- Multi-product recognition from single photo
- Real-time model accuracy tracking

## Decisions

### Decision 1: Client-Side ML Inference (TensorFlow.js vs ONNX.js)

**What:** Execute ML inference in browser/mobile app using JavaScript ML runtime

**Why:**
- **Cost**: Eliminates server ML infrastructure costs (critical for free-tier deployment)
- **Latency**: No network round-trip for inference (faster than server-side)
- **Privacy**: Photos never leave device for inference (better data privacy)
- **Scale**: Inference cost scales with users, not with requests (better for low-traffic MVP)

**Technology Choice: TensorFlow.js (Preferred) with ONNX.js as Alternative**

| Criteria | TensorFlow.js | ONNX.js | Winner |
|----------|--------------|---------|--------|
| Mobile Support | Excellent (WebGL + WASM) | Good (WASM) | TensorFlow.js |
| Model Ecosystem | Large (TensorFlow/Keras native) | Large (cross-framework) | Tie |
| Bundle Size | ~500KB (modular) | ~1.5MB | TensorFlow.js |
| Documentation | Excellent | Good | TensorFlow.js |
| Jewelry Use Case | Pre-trained MobileNet fine-tuning | Pre-trained models available | TensorFlow.js |

**Recommendation:** Start with TensorFlow.js using MobileNetV2 fine-tuned on jewelry photos. Keep ONNX.js as fallback if bundle size becomes issue.

**Alternatives Considered:**
- **Server-side inference:** Rejected due to cost (requires GPU instances or ML API usage)
- **Hybrid approach (edge caching):** Rejected as over-engineered for MVP

### Decision 2: Image Classification Model Architecture

**What:** Use transfer learning with MobileNetV2 pre-trained on ImageNet, fine-tuned on jewelry product photos

**Why:**
- **Fast inference**: MobileNetV2 optimized for mobile devices (~150ms on mobile)
- **Small model size**: ~14MB (acceptable for initial download)
- **Proven accuracy**: Transfer learning effective for product classification
- **Few training samples**: Works well with ~3-5 photos per product (our scenario)

**Model Training Pipeline (Backend):**
1. Collect product photos from `ProductPhoto` table
2. Augment data (rotation, brightness, crop) to increase training set
3. Fine-tune MobileNetV2 final layers on jewelry dataset
4. Export to TensorFlow.js format (.json + .bin files)
5. Deploy model files to S3/Blob Storage or serve from backend
6. Frontend downloads model once and caches in IndexedDB

**Retraining Trigger:**
- **MVP**: Manual trigger via admin endpoint `POST /api/image-recognition/retrain-model`
- **Phase 2**: Automatic trigger when products added/removed or photos updated

**Alternatives Considered:**
- **Custom CNN from scratch:** Rejected (requires more training data, slower development)
- **Vision API (Google/AWS):** Rejected (recurring costs, network latency, privacy concerns)

### Decision 3: Confidence Threshold and Fallback Strategy

**What:** Use 40% confidence threshold; show top 3-5 suggestions if above threshold, redirect to manual entry if all below threshold

**Why:**
- **User research:** 40% threshold balances precision (accurate suggestions) and recall (avoid too many fallbacks)
- **Business logic:** Jewelry items are visually similar; even 40% confidence provides useful suggestions
- **Fallback UX:** If all suggestions <40%, automatically redirect to manual entry with photo preserved

**Threshold Tuning Strategy:**
1. Start with 40% in MVP
2. Log confidence scores + operator selections (analytics)
3. Adjust threshold in Phase 2 based on real-world accuracy data

**Fallback Flow:**
```
Capture Photo ? Inference ? Check Confidence
                                  |
                    =40% ----------------- <40%
                     |                      |
               Show 3-5 suggestions    Redirect to manual entry
                     |                 (photo preserved as attachment)
                Operator selects       Operator searches SKU/name
                     |                      |
                     +----------------------+
                           Continue to stock validation
```

**Alternatives Considered:**
- **Fixed 60% threshold:** Rejected (too strict, causes too many fallbacks)
- **Show all suggestions regardless:** Rejected (confusing UX when confidence very low)

### Decision 4: Transaction Management for Sales + Inventory

**What:** Use database transactions to ensure atomic sale creation + inventory movement + stock update

**Why:**
- **Data consistency:** Prevents orphaned sales or stock mismatches
- **Audit integrity:** Ensures InventoryMovement always exists for every Sale
- **Error recovery:** Rollback on any failure prevents partial state

**Implementation (C# Entity Framework Core):**
```csharp
using var transaction = await _dbContext.Database.BeginTransactionAsync();
try {
    // 1. Validate stock availability (throws if insufficient)
    await _stockValidationService.ValidateAsync(productId, posId, quantity);
    
    // 2. Create Sale record
    var sale = await _salesRepository.CreateAsync(saleDto);
    
    // 3. Create SalePhoto if provided
    if (photoDto != null) {
        await _salePhotoRepository.CreateAsync(sale.Id, photoDto);
    }
    
    // 4. Create inventory movement + update stock (atomic)
    await _inventoryService.CreateSaleMovementAsync(sale);
    
    await transaction.CommitAsync();
    return sale;
}
catch {
    await transaction.RollbackAsync();
    throw;
}
```

**Alternatives Considered:**
- **Eventual consistency (queues):** Rejected (over-engineered for MVP, adds complexity)
- **Compensating transactions:** Rejected (harder to reason about, more error-prone)

### Decision 5: Photo Compression and Storage

**What:** Compress photos to JPEG quality 80%, max 2MB before storage; save only on successful sale

**Why:**
- **Storage costs:** Reduce S3/Blob Storage usage (free tier limits)
- **Mobile UX:** Faster uploads on mobile networks
- **ML compatibility:** JPEG quality 80% preserves sufficient detail for inference

**Compression Strategy:**
- **Client-side:** Compress before upload using canvas API (browser) or Image library (React Native)
- **Server-side validation:** Reject files >2MB post-compression
- **Format enforcement:** Convert all uploads to JPEG (discard PNG/HEIC metadata)

**When to Save:**
- **Sale with image recognition:** Save photo only after successful sale transaction commit
- **Sale manual with optional photo:** Save photo only after successful sale transaction commit
- **Canceled sale:** Discard photo immediately (no storage)

**Alternatives Considered:**
- **Server-side compression:** Rejected (adds server processing overhead)
- **Save photos before sale:** Rejected (orphaned photos if sale fails)

### Decision 6: Model Versioning and Update Strategy (MVP: Online-Only)

**What:** Use timestamp-based versioning with always-on version check; require network connectivity for image recognition in MVP

**Why:**
- **Always up-to-date:** When online, always use latest model version available
- **Simplicity:** MVP requires network connection for image recognition (no offline caching)
- **Reduced complexity:** Defer offline/caching logic to Phase 2
- **User experience:** Non-blocking background checks don't interrupt sales workflow

**MVP Scope:**
- ? Version check on every feature access (online required)
- ? Model download from server (no local caching)
- ? Fallback to manual entry if network unavailable
- ?? **Phase 2:** Offline model caching, IndexedDB storage, offline inference

**Version Format:** `v{incrementalNumber}_{YYYYMMDD}` (e.g., "v2_20260111")
- Semantic version number (incremental)
- Date suffix for easy identification
- Stored in ModelMetadata table

**Check Strategy (MVP - Online Only):**
1. **On feature access:** ALWAYS fetch `/api/image-recognition/model/metadata`
2. **Compare:** Previous version (if any) vs server version
3. **If different:** Download new model from server
4. **If network error:** Show error message, redirect to manual entry (no offline fallback)

**Network Error Behavior (MVP):**
- Display error: "Se requiere conexión a internet para reconocimiento de imágenes"
- Provide "Registrar venta manual" button
- Manual entry always available as fallback

**Version Check Flow (MVP - Online Only):**
```
Operator opens image recognition
         ?
Check network connectivity
         ?
    Online -------------------- Offline
     ?                            ?
Fetch model metadata          Show error:
     ?                        "Se requiere conexión"
Compare with previous               ?
     ?                        Redirect to manual entry
Same? ------ Different?
  ?              ?
Use model   Download new model
            Display: "Descargando modelo..."
                     ?
            Use new model for inference
```

**Phase 2 Enhancements (Deferred):**
- Model caching in IndexedDB (offline usage)
- Background model updates with cache invalidation
- Push notifications when new model deployed
- Automatic background download during idle time
- A/B testing with version pinning per user

### Decision 7: Browser-Based Model Training (TensorFlow.js)

**What:** Model training executes in admin's browser using TensorFlow.js with WebGL GPU acceleration. Trained model is uploaded to server automatically after training completes.

**Why:**
- **Zero dependencies:** No Python, no CLI tools - just a modern browser
- **Free-tier compatibility:** Keeps AWS App Runner at 0.5GB RAM (no Python/TensorFlow in backend)
- **GPU acceleration:** Uses admin's GPU via WebGL (faster than server CPU)
- **Better UX:** One-click training from dashboard, real-time progress updates
- **Cost control:** $0 additional AWS infrastructure for training
- **Infrequent operation:** Training only needed when catalog changes significantly (1-2x/month)

**Browser Training Workflow (MVP):**
1. Admin sees retraining alert in dashboard (?? CRITICAL or ?? HIGH)
2. Admin clicks "Train Model" button in `/admin/ai-model` dashboard
3. Browser checks device capabilities (WebGL, memory, battery)
4. Browser downloads product photos from server (~5-10MB)
5. Browser loads pre-trained MobileNetV2 from TensorFlow Hub
6. Browser trains model with transfer learning (15 epochs)
7. Browser uploads trained model to server automatically
8. Backend stores model in S3 and updates ModelMetadata
9. Frontend downloads new model on next access

**Training UX:**
```
+------------------------------------------------------------+
¦  ?? Train AI Model                                          ¦
¦------------------------------------------------------------¦
¦                                                            ¦
¦  Device Check:                                             ¦
¦  ? GPU detected (WebGL 2.0)                               ¦
¦  ? Memory: 16GB available                                 ¦
¦  ?? On battery - connect to power recommended              ¦
¦                                                            ¦
¦  Estimated duration: 15-20 minutes                         ¦
¦                                                            ¦
¦  ?? Keep this browser tab open during training             ¦
¦                                                            ¦
¦  [Start Training]                                          ¦
+------------------------------------------------------------+
```

**Browser Requirements:**
- Modern browser: Chrome/Edge 90+, Safari 14+, Firefox 88+
- WebGL 2.0 support (GPU acceleration)
- 8GB+ RAM recommended (2GB minimum)
- Stable internet connection
- **No Python required!** ?

**Training Duration:**
- With GPU (WebGL): 10-20 minutes
- Without GPU (WASM fallback): 30-60 minutes

**Server-Side Training: DISABLED**
- Server-side training is explicitly disabled
- No Python runtime on server
- No BackgroundService for ML training
- All training happens client-side in browser

**Alternatives Considered:**
- **Python local scripts:** Rejected (requires Python installation, poor UX)
- **Server-side training (BackgroundService):** Rejected and DISABLED (requires 2-4GB RAM, exceeds free-tier)
- **AWS Lambda:** Rejected (15-min timeout insufficient)
- **ECS Fargate Spot:** Rejected (not in free-tier)

### Decision 8: Model Health Dashboard and Alerts

**What:** Provide admin dashboard with model health metrics and automated alerts to determine when local retraining is needed.

**Why:**
- **Clear criteria:** Admin needs objective metrics to decide when retraining is necessary
- **Visibility:** Dashboard shows model staleness, catalog changes, and precision metrics
- **Proactive alerts:** Toast notifications ensure admin doesn't miss critical retraining needs

**Retraining Decision Criteria (Scoring System):**

| Criterion | Condition | Alert Level | Example |
|-----------|-----------|-------------|---------|
| **Low Precision** | Top-3 accuracy <70% (last 100 sales) | ?? CRITICAL | Model suggesting wrong products frequently |
| **Many New Products** | =20% products added without photos in model | ?? CRITICAL | 100 new products of 500 = 20% |
| **Moderate New Products** | =10% products added | ?? HIGH | 50 new products of 500 = 10% |
| **Many Photo Changes** | =20% photos added since training | ?? HIGH | 500 photos added of 2,500 = 20% |
| **Photos Removed** | =10% photos deleted since training | ?? HIGH | 250 photos deleted of 2,500 = 10% |
| **Stale Model + Changes** | Model >30 days + (=5% products or =10% photos changed) | ?? HIGH | Model 45 days old + 30 new products |
| **Very Stale Model** | Model >60 days | ?? RECOMMENDED | Model trained 2 months ago |

**Alert Levels:**
- ?? **CRITICAL:** Retrain immediately (toast notification on admin login)
- ?? **HIGH PRIORITY:** Retrain this week (toast notification on admin login)
- ?? **RECOMMENDED:** Retrain when convenient (shown in dashboard only)
- ? **OK:** Model is up-to-date

**Admin Dashboard Components:**

```
/admin/ai-model page includes:

1. Model Status Card:
   - Current version (e.g., "v3_20260105")
   - Last trained date (e.g., "12 days ago")
   - Current accuracy (e.g., "78% top-3")
   - Alert level with icon and recommendation
   - "Download Training Guide" button

2. Catalog Metrics:
   - Total products: 500
   - With photos: 487 (97%)
   - Without photos: 13 (3%)
   - New products not in model: 45 (9%) ??

3. Photo Metrics:
   - Total photos: 2,435
   - Added since last training: 127
   - Deleted since last training: 8
   - Net change: +4.9%

4. Precision Metrics (Phase 2 - optional in MVP):
   - Top-1 accuracy: 65%
   - Top-3 accuracy: 78%
   - Fallback to manual: 22%
   - Average inference time: 320ms

5. Action Buttons:
   - "Download Photos for Training" (triggers photo export)
   - "Upload Trained Model" (file upload to S3)
   - "View Training History" (shows past versions and metrics)
```

**Notification Strategy:**
- ? **Toast on login:** Displayed when admin logs in if alert level is ?? CRITICAL or ?? HIGH
- ? **Badge removed:** No persistent badge in sidebar (simplified UX)
- ? **Email removed:** No email notifications (admin checks dashboard when needed)

**Training Performance (Local Machine):**

With project volumes (~500 products, ~2,500 photos):

| Phase | Duration (GPU Laptop) | Duration (CPU Only) |
|-------|----------------------|---------------------|
| Download photos from S3 | 2-3 min | 2-3 min |
| Data augmentation (×3) | 1-2 min | 3-5 min |
| Fine-tune MobileNetV2 (20 epochs) | 5-10 min | 20-40 min |
| Export to TensorFlow.js | 1-2 min | 1-2 min |
| Upload to S3 | 1-2 min | 1-2 min |
| **Total** | **10-20 min** | **30-50 min** |

**Precision Tracking (Optional - Phase 2):**
- Track when operator selects product from AI suggestions
- Log: suggested products (top-3) vs. selected product
- Calculate accuracy: % of times selected product was in top-3
- Store in `AIInferenceLog` table (deferred to Phase 2)

### Decision 9: Variable Number of Suggestions Based on Confidence

**What:** Show 3-5 product suggestions depending on how many products exceed 40% confidence threshold

**Why:**
- **Adaptive UX:** If only 3 products exceed threshold, show 3 (not padding with low-confidence items)
- **Quality over quantity:** Only show products operator might actually select
- **Clear signal:** Number of suggestions indicates model confidence level

**Logic:**
```
confidence >= 40% for top-3 ? Show 3 suggestions
confidence >= 40% for top-4 ? Show 4 suggestions  
confidence >= 40% for top-5+ ? Show 5 suggestions (cap at 5)
confidence >= 40% for 0 products ? Redirect to manual entry
```

**Alternatives Considered:**
- **Fixed top-3:** Rejected (might show low-confidence items unnecessarily)
- **Fixed top-5:** Rejected (too many options, decision fatigue)

### Decision 10: Double Stock Validation for Concurrency Safety

**What:** Validate stock twice: once when form loads, again immediately before transaction commit

**Why:**
- **Race condition prevention:** Two operators selling last unit simultaneously
- **Data integrity:** Ensure stock never goes negative even with concurrent sales
- **Better UX:** Show accurate error if stock changed between form load and submission

**Implementation:**
```csharp
// First validation: When operator selects product
var initialStock = await ValidateStockAsync(productId, posId, qty);
// Display: "Stock disponible: 5 unidades"

// Second validation: Before transaction commit
using var transaction = await BeginTransactionAsync();
var currentStock = await ValidateStockAsync(productId, posId, qty);
if (currentStock < qty) {
    throw new InsufficientStockException(
        $"Stock cambió. Disponible: {currentStock}, Solicitado: {qty}"
    );
}
// Proceed with sale creation...
```

**Alternatives Considered:**
- **Single validation + optimistic lock:** Rejected (might fail transaction without clear error message)
- **Pessimistic locking:** Rejected (overkill for low-concurrency scenario, reduces throughput)

### Decision 11: Initial Deployment Without ML Model

**What:** Deploy application without pre-trained model; admin trains first model after deployment using uploaded product photos

**Why:**
- **Flexibility:** App functional immediately (manual sales work without model)
- **Real data:** Model trained with actual product catalog, not test data
- **Simpler deployment:** No need to bundle model with initial deployment

**Deployment Flow:**
```
1. Deploy backend + frontend (no model)
2. Admin uploads product photos (EP1)
3. Admin triggers first training via dashboard
4. Model trains (30-45 min)
5. Image recognition becomes available
6. Manual sales work throughout entire process
```

**Fallback Strategy:**
- If image recognition accessed before model exists: Show error "Modelo de IA no disponible aún" + redirect to manual entry
- Manual entry ALWAYS available regardless of model status

**Alternatives Considered:**
- **Pre-trained model required:** Rejected (blocks deployment, requires test data)
- **Bundled dummy model:** Rejected (poor accuracy, confuses operators)

### Decision 12: Model Rollback on Training Failure

**What:** If training fails, preserve and continue serving previous model version; application never becomes model-less if a valid model already exists

**Why:**
- **Service continuity:** Image recognition remains functional even if retraining fails
- **Graceful degradation:** Operators can continue using (potentially outdated) model
- **Admin visibility:** Dashboard shows "Training failed" + previous model still active

**Implementation:**
```csharp
try {
    var newModel = await TrainModelAsync();
    await DeployModelAsync(newModel);
    UpdateMetadata(newModel);
} catch (Exception ex) {
    LogError("Training failed", ex);
    // Keep previous model active (don't delete or update metadata)
    NotifyAdmin("Training failed. Previous model (v3) still active.");
}
```

**Frontend Behavior:**
- If GET /api/image-recognition/model returns 200: Use model (even if old)
- If GET /api/image-recognition/model returns 404: Show error + redirect to manual

**Alternatives Considered:**
- **Disable image recognition on failure:** Rejected (poor UX, operators lose functionality)
- **Force retry:** Rejected (may fail repeatedly, blocks admin)

### Decision 13: Minimum Device Requirements for Image Recognition

**What:** Define minimum browser/device requirements for TensorFlow.js; redirect to manual entry with clear message if requirements not met

**Why:**
- **Compatibility:** Older devices may not support WebGL or have insufficient RAM
- **User expectation:** Clear error better than silent failure or infinite loading
- **Fallback:** Manual entry always works regardless of device

**Minimum Requirements:**
- **Browser:** Chrome/Edge 90+, Safari 14+, Firefox 88+ (WebGL 2.0 support)
- **OS:** iOS 12+, Android 8.0+, Windows 10+, macOS 10.14+
- **RAM:** 2GB+ (for model loading + inference)
- **WebGL:** 2.0 support required (GPU acceleration)

**Detection Strategy:**
```typescript
async function checkDeviceCompatibility(): Promise<boolean> {
  // Check WebGL 2.0 support
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl2');
  if (!gl) return false;
  
  // Check TensorFlow.js compatibility
  try {
    await tf.ready();
    return true;
  } catch {
    return false;
  }
}
```

**Error Message:**
```
"Tu dispositivo no es compatible con reconocimiento de imágenes.
 Requisitos: iOS 12+, Android 8+, navegador moderno.
 
 [Registrar Venta Manual]"
```

**Alternatives Considered:**
- **No requirements check:** Rejected (poor UX, cryptic errors)
- **Strict version enforcement:** Rejected (may block functional devices)

### Decision 14: Photo Content Validation

**What:** Validate photo dimensions, aspect ratio, and basic content before accepting upload

**Why:**
- **Training quality:** Ensure photos suitable for ML training (not too small, not distorted)
- **Storage efficiency:** Prevent upload of unusable images
- **User feedback:** Immediate validation better than discovering issues later

**Validation Rules:**
- Minimum dimensions: 200x200 pixels
- Maximum aspect ratio: 5:1 (reject extremely wide/tall images)
- Not completely black or white (detect using histogram)
- File size: 2MB max after compression

**Implementation:** Client-side validation using canvas API before upload

**Alternatives Considered:**
- **No content validation:** Rejected (poor training data quality)
- **Server-side only:** Rejected (wastes bandwidth uploading invalid images)

### Decision 15: Provider-Agnostic File Access (No Pre-signed URLs)

**What:** Serve photos through backend API endpoints instead of direct storage URLs or pre-signed URLs

**Why:**
- **Provider independence:** IFileStorageService works with local filesystem (dev), S3 (AWS), and Blob Storage (Azure) without code changes
- **No provider-specific logic:** Pre-signed URLs are AWS-specific, Blob Storage uses SAS tokens (different APIs)
- **Consistent interface:** Same photo URL format regardless of storage backend
- **Simpler implementation:** Backend streams file from storage, no URL generation logic

**Implementation:**
```csharp
// IFileStorageService interface (provider-agnostic)
public interface IFileStorageService {
    Task<string> SaveFileAsync(Stream file, string path);
    Task<Stream> GetFileAsync(string path);
    Task DeleteFileAsync(string path);
    // NO GetPresignedUrlAsync - rejected
}

// Photo access through API
GET /api/products/{id}/photos/{photoId}/file
? Backend calls IFileStorageService.GetFileAsync()
? Streams file to response
? Works with local, S3, or Blob Storage transparently
```

**Frontend:**
```typescript
// Photo URL is API endpoint, not storage URL
<img src="/api/products/ABC-123/photos/photo-456/file" />
```

**Trade-offs:**
- ? Provider-agnostic (works with any storage)
- ? No provider-specific code (same interface for local/S3/Blob)
- ?? Bandwidth through backend (vs direct S3/CDN access)
- **Acceptable for MVP:** Low traffic (2-3 concurrent users), small images (~500KB compressed)

**Alternatives Considered:**
- **Pre-signed URLs (AWS S3):** Rejected (AWS-specific, doesn't work with Azure Blob or local filesystem)
- **SAS tokens (Azure Blob):** Rejected (Azure-specific, doesn't work with S3 or local)
- **CDN with signed cookies:** Rejected (over-engineered for MVP, provider-specific)

**Alternatives Considered:**
- **GPU Spot Instances:** Rejected (requires external service, adds complexity, violates constraint)
- **Scheduled automatic retraining:** Rejected for MVP (manual trigger simpler, better cost control)
- **Email notifications:** Rejected (toast on login sufficient, reduces noise)
- **Persistent badge:** Rejected (toast is less intrusive, dashboard shows status)
- **CPU throttling:** Rejected (slower training, complexity; admin warning preferred)
- **Progressive model download:** Deferred to Phase 2 (simplifies MVP UX, adds state complexity)

### Decision 16: Browser-Based Training Only (TensorFlow.js) - MVP Feature

**What:** ML model training is executed in admin's browser using TensorFlow.js; server-side training is DISABLED; Python scripts are NOT provided.

**Why:**
- **Zero dependencies:** No Python installation required - just a modern browser
- **Free-tier compatibility:** Keeps AWS App Runner at 0.5GB RAM (no Python/TensorFlow on server)
- **GPU acceleration:** Uses admin's GPU via WebGL (often faster than server CPU)
- **Better UX:** One-click training from dashboard, real-time progress
- **Cost control:** $0 additional AWS infrastructure
- **Simpler deployment:** Docker image ~200MB (.NET only), no multi-runtime complexity
- **Infrequent operation:** Training only needed when catalog changes significantly (1-2x/month)

**Browser Training Workflow (MVP):**
1. Admin sees retraining alert in dashboard (?? CRITICAL or ?? HIGH)
2. Admin clicks "Train Model" button
3. Browser checks device capabilities (WebGL, memory, battery)
4. Browser downloads product photos from server
5. Browser trains model with TensorFlow.js (15 epochs, transfer learning)
6. Browser uploads trained model automatically
7. Backend stores model in S3, updates ModelMetadata
8. Frontend downloads new model on next access

**Admin Dashboard UI (MVP):**
```
Model Status Card:
- Current version: v3_20260105
- Last trained: 12 days ago
- Accuracy: 78% top-3
- Alert level: ?? HIGH (45 new products)

Device Capabilities:
- GPU: ? Detected (WebGL 2.0)
- Memory: ? 16GB available
- Estimated time: 15-20 minutes

[Train Model] - Train directly in browser

?? Keep this tab open during training
```

**Browser Requirements:**
- Modern browser: Chrome/Edge 90+, Safari 14+, Firefox 88+
- WebGL 2.0 support
- 8GB+ RAM recommended (2GB minimum)
- **No Python required!** ?

**Training Duration:**
- With GPU (WebGL): 10-20 minutes
- Without GPU (WASM): 30-60 minutes

**Server-Side Training: DISABLED**
- No server-side training option in UI
- No BackgroundService for ML training
- No Python runtime on server
- Retrain endpoint removed or returns 501 Not Implemented

**Python Scripts: NOT PROVIDED**
- No `scripts/ml/` directory
- No Python dependencies
- All training is browser-based

**Limitations:**
- Admin must keep browser tab open during training
- Training performance depends on admin's hardware
- Not suitable for automated/scheduled training

**Alternatives Considered and Rejected:**
- **Python local scripts:** Rejected (requires Python installation, poor UX)
- **Server-side training:** Rejected and DISABLED (exceeds free-tier)
- **Hybrid (both options):** Rejected (unnecessary complexity, browser is sufficient)
- **ML.NET training:** Rejected (no TensorFlow.js export)

**Trade-offs:**
- ? Zero dependencies (just browser)
- ? Better UX (one-click training)
- ? GPU acceleration (faster on modern hardware)
- ?? Must keep tab open (10-60 minutes)
- ?? No automated/scheduled training (acceptable for MVP, infrequent operation)

## Risks / Trade-offs

### Risk 1: Model Download Size on Mobile

**Risk:** 14MB model download on first use may be slow on poor mobile networks

**Mitigation:**
- Progressive loading: Show manual entry option immediately, load model in background
- Caching: Model cached in IndexedDB after first download (only download once)
- Fallback: If model fails to load, gracefully degrade to manual entry only

**Trade-off:** Slower first-time experience vs zero server ML costs

### Risk 2: AI Accuracy with Similar Products

**Risk:** Jewelry products visually similar; AI may suggest wrong items frequently

**Mitigation:**
- Show confidence scores to operator (transparency)
- Always require operator confirmation (no automatic selection)
- Track accuracy metrics (log selected product vs suggested product)
- Adjust threshold based on real-world data

**Trade-off:** Faster identification vs occasional incorrect suggestions

### Risk 3: Model Staleness When Products Change

**Risk:** Model becomes outdated when products added/removed, new photos uploaded

**Mitigation:**
- Admin notification when model is >30 days old and photos changed
- Manual retrain trigger accessible from admin panel
- Frontend displays model version and last trained date
- Phase 2: Automatic retraining triggers

**Trade-off:** Manual intervention required vs automated complexity

### Risk 4: Transaction Performance Under Concurrent Sales

**Risk:** Long transactions (sale + photo + inventory) may cause lock contention

**Mitigation:**
- Optimistic locking on Inventory table (prevent lost updates)
- Short transaction scope (validate before transaction, save photo async after)
- Database connection pooling (max 5-10 connections for free tier)

**Trade-off:** Absolute consistency vs potential for rare lock conflicts

## Migration Plan

**Phase 1: MVP Implementation**
1. Deploy backend + frontend without ML model (manual entry works immediately)
2. Test transaction integrity with Testcontainers
3. Admin uploads product photos via EP1 (Product Management)
4. Admin navigates to /admin/ai-model dashboard
5. Dashboard shows "No hay modelo entrenado aún" + "Re-train Model Now" button
6. Admin triggers first training (30-45 minutes, recommended off-hours)
7. Image recognition becomes available after first training completes
8. Operators automatically get model on next image recognition access
9. System continues functioning with manual entry during entire process

**Phase 2: Model Retraining (Post-MVP)**
1. Monitor model accuracy through admin dashboard
2. Implement automatic retrain trigger (weekly or on photo changes)
3. Add A/B testing for new model versions
4. Implement incremental learning (add products without full retrain)

**Rollback Plan:**
- Image recognition failure: Frontend falls back to manual entry (graceful degradation)
- API failure: Rollback backend deployment (sales data not affected if no transactions committed)
- Model corruption: Serve previous model version from versioned storage path

## Open Questions

1. **Model hosting location:** Serve model from backend API or dedicated CDN endpoint?
   - **Recommendation:** Start with backend API (`GET /api/image-recognition/model`), move to CDN in Phase 2 if bandwidth becomes issue

2. **Photo retention policy:** How long to keep SalePhoto records? (Storage costs)
   - **Recommendation:** Indefinite retention in MVP (audit trail), implement archival policy in Phase 2

3. **Confidence score display:** Show percentage or qualitative labels (High/Medium/Low)?
   - **Recommendation:** Show percentage (transparency), add qualitative labels in Phase 2 based on user feedback

4. **Model accuracy target:** What's acceptable accuracy for MVP launch?
   - **Recommendation:** =70% top-3 accuracy (operator sees correct product in top 3 suggestions), measure in beta

5. **Retraining frequency:** How often should model be retrained in Phase 2?
   - **Recommendation:** Weekly automated retrain if photos changed, manual override available

