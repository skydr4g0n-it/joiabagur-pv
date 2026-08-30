# OpenSpec Deferred Tasks

This document tracks all tasks that have been deferred to future phases or epics, along with explanations for why they were deferred.

## Active Change: `add-sales-and-image-recognition`

### Phase 2 - Offline Capabilities (Image Recognition)

**Status:** Documented in specs but NOT implemented in MVP

**Deferred Tasks:**
1. **Offline model usage** - Cached model when no network connection
2. **Progressive Web App offline capabilities** - Full offline support for PWA
3. **Push notifications for new model versions** - Notify users when new model is available
4. **IndexedDB model caching** - Store model locally for offline inference
5. **Offline inference execution** - Run ML inference without network connectivity
6. **Background model updates** - Download new models in background during idle time
7. **Cache invalidation logic** - Manage cached model version lifecycle

**Why Deferred:**
- MVP focuses on core online functionality
- Offline scenarios add significant complexity (state management, cache invalidation, conflict resolution)
- Network connectivity is expected in retail POS environments
- Simplifies MVP UX and reduces development time
- Can be added incrementally without breaking existing functionality

**Reference:** `openspec/changes/add-sales-and-image-recognition/proposal.md` lines 63-69

---

### Phase 2 - Model Configuration & Analytics

**Deferred Tasks:**
1. **Configurable confidence threshold** - Admin UI to adjust threshold (20%-80% range)
   - Currently fixed at 40% in MVP
   - **Why:** Need real-world usage data to determine optimal threshold before making it configurable

2. **Precision metrics calculation** - Track model accuracy over time
   - Currently returns `null` in MVP
   - **Why:** Requires inference logging infrastructure and historical data collection

3. **Analytics logging** - Log inference metrics (inference time, confidence scores)
   - Optional in MVP
   - **Why:** Not critical for MVP functionality, adds storage/complexity

4. **AIInferenceLog table** - Store inference history for analytics
   - **Why:** Requires database schema changes and logging infrastructure

**Reference:** 
- `openspec/changes/add-sales-and-image-recognition/specs/image-recognition/spec.md` lines 165, 437
- `openspec/changes/add-sales-and-image-recognition/tasks.md` lines 140, 235, 260

---

### Phase 2 - Model Retraining Automation

**Deferred Tasks:**
1. **Automatic model retraining triggers** - Retrain when products added/removed or photos updated
   - Currently manual trigger via admin endpoint
   - **Why:** Adds complexity (monitoring, failure handling, cost control). Manual retraining sufficient for MVP with ~500 products

2. **Scheduled retraining** - Nightly retraining if photos changed in last 24h
   - **Why:** Unnecessary for MVP scale, adds infrastructure complexity

3. **Incremental learning** - Add new products without full retrain
   - **Why:** Advanced ML technique, not needed for MVP scale

4. **A/B testing with version pinning** - Deploy new model to subset of users
   - **Why:** Over-engineering for MVP, adds significant complexity

**Reference:** 
- `openspec/changes/add-sales-and-image-recognition/design.md` lines 81, 265-268, 658

---

### Phase 2 - Frontend Enhancements

**Deferred Tasks:**
1. **CSV export for sales history** - Download sales data as CSV
   - **Why:** Nice-to-have feature, not critical for MVP

2. **Progressive model download** - Download model in chunks/streaming
   - **Why:** Simplifies MVP UX, adds state complexity. Current approach (full download) acceptable for ~14MB model

**Reference:** 
- `openspec/changes/add-sales-and-image-recognition/tasks.md` lines 248, 623

---

## Archived Changes - EP3 Integration Tasks

### Payment Method Management - Sales Integration

**Status:** Deferred until EP3 (Sales Registration) is implemented

**Deferred Tasks:**
1. **Integrate validation into sale creation workflow** - Use payment method validation when creating sales
2. **Return appropriate error messages for invalid payment methods** - Sales-specific error handling
3. **Prevent deactivation of payment methods assigned to active sales** - Business rule enforcement
4. **Test sales validation with payment methods** - Integration tests
5. **Test sales creation with valid/invalid payment methods** - End-to-end tests
6. **Sales validation documentation** - API documentation updates

**Why Deferred:**
- These tasks require the sales system (EP3) to be implemented first
- Payment method management was built as standalone capability
- Integration will be completed when sales registration is implemented
- **Note:** Sales registration is now being implemented in `add-sales-and-image-recognition` change

**Reference:** 
- `openspec/changes/archive/2026-01-07-add-payment-method-management/tasks.md` lines 46-47, 56, 74, 78, 108, 114

---

## Archived Changes - Documentation Tasks

### Point of Sale Management - System Documentation

**Status:** Deferred to post-MVP documentation phase

**Deferred Tasks:**
1. **Update data model documentation** - Full ERD and schema documentation
2. **Update architectural diagrams** - C4 model updates, sequence diagrams

**Why Deferred:**
- Documentation tasks are non-functional requirements
- Can be completed after MVP is stable
- Focus on implementation over documentation for MVP phase

**Reference:** 
- `openspec/changes/archive/2026-01-07-add-point-of-sale-management/tasks.md` lines 76-77
- `openspec/changes/archive/2025-12-14-add-point-of-sale-management/tasks.md` lines 76-77

---

### Payment Method Management - Documentation

**Deferred Tasks:**
1. **Update data model documentation** - Full ERD updates
2. **Sales validation documentation** - Integration documentation (requires EP3)

**Why Deferred:**
- Same rationale as POS management documentation
- Sales validation docs require EP3 implementation

**Reference:** 
- `openspec/changes/archive/2026-01-07-add-payment-method-management/tasks.md` lines 106, 108

---

## Archived Changes - Testing Tasks

### Product Catalog Search - Integration Tests

**Status:** Deferred (lower priority)

**Deferred Tasks:**
1. **Integration tests for GET /api/products** - Pagination, sorting, filtering
2. **Integration tests for GET /api/products/search** - Role-based filtering
3. **Integration tests for DELETE /api/products/{id}/photos/{photoId}** - Admin-only endpoint
4. **Integration tests for PUT photo management endpoints** - Admin-only endpoints

**Why Deferred:**
- Lower priority compared to unit tests and critical path integration tests
- Functionality is covered by unit tests and manual testing
- Can be added incrementally

**Reference:** 
- `openspec/changes/archive/2026-01-08-extend-product-catalog-search/tasks.md` lines 97-100

---

## Summary by Category

### By Reason for Deferral:

1. **Requires Future Epic/Feature** (EP3 Sales System)
   - Payment method sales integration
   - Sales validation tests

2. **MVP Simplification** (Phase 2 Enhancements)
   - Offline capabilities
   - Model retraining automation
   - Advanced analytics

3. **Non-Critical Features** (Nice-to-Have)
   - CSV export
   - Progressive model download
   - Additional integration tests

4. **Post-MVP Documentation**
   - System documentation updates
   - Architectural diagrams

### By Priority:

**High Priority (Implement Next):**
- Payment method sales integration (when sales system is complete)
- Offline capabilities (if network reliability becomes issue)

**Medium Priority:**
- Model retraining automation (when catalog grows significantly)
- Configurable confidence threshold (after collecting usage data)

**Low Priority:**
- Analytics logging
- CSV export
- Additional integration tests
- Documentation updates

---

---

## Active Change: `add-frontend-assisted-search-panel` (C16)

### Restore the retrieval time budget to 800 ms

**Status:** Budget temporarily raised from **800 ms to 2500 ms** in
`backend/src/JoiabagurPV.API/appsettings.json` and in the default of
`AiGatewayOptions.RetrievalTimeoutMs`.

**Why it was raised.** Measured on 2026-08-29 against the seeded world with real retrieval
(`STUB_MODE=false`, 1.200 documents with embeddings):

| Budget | Outcome |
|---|---|
| 800 ms (design §6.4) | `ai_gateway_call_failed timeout 1956 2` → `LexicalFallback` on **every** search |
| 2500 ms | Served assisted in **0,86 s** and **0,31 s** end to end |

At 800 ms the assisted path never serves: the feature would ship looking healthy —
HTTP 200, results on screen — while silently answering from the degraded lexical searcher
every single time. That is the failure mode C15 designed the origin column to make visible,
and it would have reached production undetected.

**The actual cause, which this does not fix.**
[`ai-service/src/jbg_ai/api/routers/retrieval.py`](../ai-service/src/jbg_ai/api/routers/retrieval.py)
constructs a `LiteLlmEmbeddingClient` **per request**, so the in-memory embedding cache frozen
in C11 is born empty and dies with the response. Retrieval never gets a cache hit, and every
search pays a full cold round trip to the embedding provider. The debt was recorded when C15
was designed and assigned to **C21 or C22**, which already work inside `retrieval/`; the fix is
roughly three lines in `main.py` making that client a singleton.

**What to do when C21/C22 land.**

1. Make the embedding client a singleton in the AI service.
2. **Measure again** against the seeded world, both cold and warm.
3. Put `RetrievalTimeoutMs` back to **800 ms** in `appsettings.json` **and** in the
   `AiGatewayOptions` default — the two must not drift apart.
4. Confirm with the funnel log that `Origin=Assisted` and not `LexicalFallback`.

**Why not leave it at 2500 ms.** A budget that no longer bites stops being a budget. With the
single retry of C03 the worst case before degrading becomes roughly **five seconds** of an
operator standing at the till waiting for an answer that will arrive degraded anyway — worse
for the shop than failing fast into the lexical searcher. The 800 ms of §6.4 exists to bound
that wait, not to be comfortable.

**References:** `openspec/changes/add-frontend-assisted-search-panel/qa.md` §6 ·
[design §6.4](../Documentos/Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) ·
C15 `design.md`, *Risks / Trade-offs*

---

## Active Change: `add-ai-service-deployment` (C17)

### Splitting `/health` into liveness and readiness probes

**Status:** Deliberately NOT done in C17. The enriched report lives on the existing `GET /health`
with its return annotation unchanged (an open mapping), so `ai-service/openapi.json` — the
contract frozen with the .NET side — does not move and `test_openapi_snapshot_is_stable` stays
green.

**Why it is deferred rather than forgotten.** The current endpoint answers three different
questions for three different consumers: the container health check ("is this process alive?"),
post-deployment verification ("is this environment fit to show?"), and the administrator card
("what is wrong right now?"). That is one endpoint doing the job of two, and it is affordable
only while nothing acts on the answer automatically.

**The three triggers. Split when ANY ONE of them becomes true, and not before:**

1. **Something can restart the container based on the answer.** Today nothing does: Compose's
   `restart: unless-stopped` reacts to the process exiting, not to a health status. The moment an
   orchestrator is allowed to recycle the container on an unhealthy report, a degraded database
   turns into a restart loop — the probe causing the outage it reports.
2. **The expensive part stops being cheaply cacheable.** The report is reused for ten seconds,
   which is what keeps repeated probing off a connection pool capped at five for the whole
   system. If a future field cannot be cached that way, liveness must stop paying for readiness.
3. **The service is deployed to the shop's real account.** A different blast radius and a
   different operator justify a different contract.

**What splitting costs, and why that cost is correct.** A new route regenerates `openapi.json`
and breaks its drift test. That is the right outcome, not an obstacle: the boundary with the .NET
side will genuinely have moved, and the test exists to make that visible rather than silent.
Agree the change with whoever owns the .NET client, then regenerate with the README one-liner.

**References:** C17 `design.md` D12 · `openspec/specs/ai-service-runtime/spec.md` ·
S16 *Observabilidad* ("no confundáis el latido con la vigilancia")

### Measuring the real retrieval budget on the demo environment

**Status:** Pending the demo environment being deployed. **Not** a revision of the 2500 ms budget
— that belongs to the changes working in `retrieval/`, as recorded above.

**What to measure and why it is a different measurement.** The 2500 ms figure was measured
against a provider reached from a laptop. The demo environment sits in a different network, a
different region and a different instance size, and the same cold round trip may cost more there.
Once the environment is up, run several assisted searches and read the funnel log:

- `ai_gateway_call_completed` latency, cold and warm.
- Whether the badge reports `Origin=Assisted` or `LexicalFallback`.

Record the numbers here. If the assisted path degrades on the demo at 2500 ms, that is evidence
the singleton fix is more urgent, not a reason to raise the budget further.

**References:** C17 `tasks.md` §10.1 · C16 `qa.md` §6

---

## Implementation Guidance

When implementing deferred tasks:

1. **Check this document** - Ensure task is still relevant and not superseded
2. **Review original spec** - Check `openspec/changes/[change-id]/specs/` for full requirements
3. **Review design decisions** - Check `openspec/changes/[change-id]/design.md` for context
4. **Create new change proposal** - If adding new capability, create new change proposal
5. **Update this document** - Mark tasks as completed or update status

---

**Last Updated:** 2026-08-29
**Maintained By:** Development Team
