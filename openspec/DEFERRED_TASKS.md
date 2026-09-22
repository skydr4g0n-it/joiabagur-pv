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

**Step 1 is paid. C21 (`add-hybrid-search-rrf`) made the client a process singleton**, and it
was not the "three lines in `main.py`" this note assumed. `InMemoryEmbeddingCache` is a `dict`
with no ceiling and no TTL: harmless per request, since it was born empty and died with the
response — which is also *why* retrieval never got a hit — and a lifetime leak as a singleton
keyed by every distinct operator query (~13 KB per vector) inside a container capped at
512 MiB that already uses 232. `indexing/embeddings.py` stays frozen by C11, so the bound was
injected through its existing `cache` constructor field: `retrieval/cache.py` holds a bounded
LRU, `api/main.py` builds the client once, `api/routers/retrieval.py` resolves it from
`app.state`, and `test_embeddings_module_is_unchanged` pins the freeze by content hash.

**Steps 2 to 4 stay open, and they are a change of their own** — they need a demo deploy, a
cold and warm re-measurement and a funnel confirmation, which is a different kind of work and
a different risk from anything C21 touches.

1. ~~Make the embedding client a singleton in the AI service.~~ **Done in C21.**
2. ~~**Measure again**, both cold and warm.~~ **Done on 2026-09-02**, against the local index
   of 1.168 documents and the real provider, through the full C21 pipeline (expansion, both
   lexical lists, embedding, vector branch, fusion, demoting filters), six operator queries:

   | | min | media | max |
   |---|---:|---:|---:|
   | **Cold** (first time each text is seen) | 273 ms | 475 ms | **1328 ms** |
   | **Warm** (the singleton's cache hits) | **74 ms** | **76 ms** | 78 ms |

   **The singleton works, and the figure that matters is 76 ms** — an order of magnitude inside
   the 800 ms budget, against 170-383 ms warm on the demo host before it existed. The cache
   removes the provider round trip entirely on a repeated query text.

   **What it does not remove is the first call for each distinct text**: 1328 ms on
   `criollas de oro`, still well over 800 ms and consistent with the 1707 ms measured on the
   demo host. So the budget is now comfortable for a shop that searches for similar things all
   day and still blown by a genuinely new query.

   These figures are a **laptop against a local database**, not the demo environment. They say
   the singleton was worth paying for; they do not settle the revert, which needs step 3
   measured where the operator actually is.
3. Put `RetrievalTimeoutMs` back to **800 ms** in `appsettings.json` **and** in the
   `AiGatewayOptions` default — the two must not drift apart. **Decide with the cold tail in
   hand**: at 800 ms a first-ever query text still degrades to the lexical searcher. That may
   now be the right trade — C21's own lexical branch is what answers, and it scores 219/240
   against the vector branch's 157/240 — but it is a decision to take deliberately and to
   confirm with the funnel, not a consequence of the cache working.
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

### The retrieval budget, measured on the demo environment

**Status: measured on 2026-08-30. The conclusion is "do not revert yet", and the reason is
sharper than before.**

Four `ai_gateway_call_completed` latencies over four distinct queries, from the demo host in
`eu-west-1` against the real provider, with `aiAvailable: true` on all four:

| Query | Gateway latency | End to end |
|---|---|---|
| anillo de plata para regalar | 383 ms | 0,99 s |
| pendientes de oro para una boda | **1707 ms** | 1,98 s |
| collar con perlas elegante | 170 ms | 0,41 s |
| pulsera de plata sencilla | 184 ms | 0,40 s |

**What this changes.** The 2500 ms budget is not being consumed in the normal case: warm calls
land at **170–383 ms**, four to fourteen times inside it. Measured from a laptop during C16 the
same path degraded on *every* search at 800 ms; from an instance in the same region as nothing in
particular but with a better route to the provider, the ordinary case is comfortable.

**What this does NOT change.** One call in four cost **1707 ms** — still more than double the
800 ms of §6.4. So reverting the budget today would degrade roughly a quarter of searches to the
lexical path. The debt is the same one recorded above: the AI service builds a
`LiteLlmEmbeddingClient` per request, so the in-memory cache never hits and any request may pay a
full cold round trip. Distance to the provider changed how *often* that hurts, not whether it
happens.

**Therefore:** leave `RetrievalTimeoutMs` at 2500 ms. Make the embedding client a singleton in
the change that owns `retrieval/`, measure again, and only then consider 800 ms. These figures
are the new baseline to beat.

**References:** C17 `qa.md` · C16 `qa.md` §6 · measured with the demo corpus of 1200 documents

### Instance sizing, measured (C17 §10.3) — no action needed

`docker stats` on the four containers with the corpus loaded and searches served, 2026-08-30:

| Container | Memory | Of its limit |
|---|---|---|
| `jbg-demo-ai` | 232,5 MiB | **45 % of its 512 MiB cap** |
| `jbg-demo-api` | 108 MiB | — |
| `jbg-demo-postgres` | 93 MiB | — |
| `jbg-demo-proxy` | 11,7 MiB | — |

Host: 689 MB used of 1909, **917 MB available**, and **no swap configured**.

**`t3.small` is right-sized and the 512 MiB cap on the AI service is well chosen**: high enough
that ordinary operation never approaches it, low enough that the container dies before the host
does — which is the whole point of D18. No resizing, and the swap file the design offered as a
mitigation is not needed at these numbers. Re-measure if the corpus grows by an order of
magnitude or if a generative route lands.

> **A generative route landed with C34** (2026-09-21): the demo configuration now passes
> `JPV_ASSIST_LLM_API_KEY` to `jbg-demo-ai` and switches the sale card on. **The re-measurement is
> pending** because it needs the parameter created by hand and a deployment (C34 tasks 11.3 and
> 11.4). What to record here when it is done: `docker stats --no-stream jbg-demo-ai` after a
> handful of sale assistance requests, against the 512 MiB cap and the 232,5 MiB above; and
> whether several requests in a row hit the organisation's tokens-per-minute quota before the
> money does — the constraint C32b measured on the agent route.

---

## **Este repositorio no tiene CI** — causa ya documentada, confirmada el 2026-08-30

**Estado: hallazgo, no tarea de C17.** Merece un change propio; se anota aquí para que no
se pierda.

> **La causa no es nueva.** [`Documentos/testing-backend.md`](../Documentos/testing-backend.md)
> ya la registraba en su sección *Estado de la suite*: `test-backend.yml` sólo dispara en
> `main` y `develop`, «y **todo el Proyecto Final de IA se está construyendo en `ai-eng`** y
> sus ramas de change». Lo que C17 aporta no es el descubrimiento sino la **confirmación
> empírica** de su consecuencia extrema, que hasta ahora se intuía: no es que se ejecute poco,
> es que **no se ha ejecutado nunca**.

`test-backend.yml` y `test-frontend.yml` **no se han ejecutado nunca**, ni una vez:

```
gh run list --workflow=test-backend.yml   -> NUNCA SE HA EJECUTADO
gh run list --workflow=test-frontend.yml  -> NUNCA SE HA EJECUTADO
```

Ambos disparan sobre `branches: [main, develop]`, y **ninguna de esas dos ramas existe**. Las
del repositorio son `master`, `ai-eng` —donde se integra de verdad: el PR #21 mergeó ahí— y
`demo`. Los workflows están bien escritos, sus filtros de ruta son razonables, y son inertes.

Es la misma firma que C17 encontró siete veces en un día: algo que aparenta funcionar y no se
ejecuta. Aquí el coste acumulado es mayor que el de cualquiera de aquéllos, porque significa
que **ningún cambio de este proyecto ha pasado por una comprobación automática antes de
integrarse**.

### Lo que hay que hacer, y en qué orden

1. **Corregir las ramas**: `pull_request: branches: [ai-eng, master]` más `push` sobre las
   mismas. Es el arreglo de una línea que enciende la CI.
2. **Sólo entonces**, decidir si la CI puede ser una puerta. Hoy **no puede**, y el motivo
   está en `CLAUDE.md`: la suite de backend arrastra **53 fallos preexistentes** y la de
   frontend **116**. Una puerta sobre una suite roja no es una puerta; es un bloqueo
   permanente que alguien terminará saltándose. Poner la CI en verde es el trabajo de verdad,
   y es un change en sí mismo.
3. Mantener la **lista blanca** (`paths:`) en los tests, al contrario que en los despliegues.
   Un test que sobra cuesta minutos; un despliegue que falta deja el entorno corriendo código
   viejo en silencio. Los dos filtros fallan hacia lados distintos a propósito.
4. Al hacer la CI obligatoria, cuidado con la trampa conocida: un workflow **omitido** por
   filtro de rutas nunca reporta su estado, y una comprobación requerida que no reporta deja
   el PR bloqueado para siempre. Se resuelve con un trabajo acompañante que siempre se ejecuta
   y publica el mismo nombre de comprobación.

### Y el despliegue de producción, que sigue sin filtro

`deploy-aws-ec2.yml` redespliega la tienda ante **cualquier** cambio, incluido uno que sólo
toque documentación. Se le aplica el mismo razonamiento que a `deploy-demo.yml`, pero **C17 no
lo toca**: su propia especificación exige que el flujo de despliegue de producción quede
inalterado, y hay un escenario que lo verifica. Corresponde a otro change.

---

## FIX1 — lo que la corrida dejó anotado y sin ficha

Archivado el 2026-09-05 como `2026-09-05-fix-enrichment-vocabulary-gaps`. Las tres cosas que su
informe deja abiertas, y por qué ninguna entró en el change:

### `filigrana` sigue siendo una laguna, y de otro eje

Es la única exclusión del overlay de C20 que queda abierta, y **ahora es el ejemplo al que apunta
el test guardián** `test_overlay_anchor_absent_from_the_base_is_a_vocabulary_gap`. Alcanza 66
documentos por sí sola, repartidos por todos los tipos de pieza —es una técnica, no una pieza—, y
una de las 12 búsquedas registradas de operador es literalmente «anillo de filigrana tradicional
menorquina».

**Por qué se aplazó:** cerrarla significa añadir un canónico a **`style_tags`**, que es otro eje con
sus propias puertas de cobertura en el auditor, y no cuesta lo que cuesta una laguna de
`piece_type`. No tiene change asignado: FIX1 cerró las cuatro de `piece_type` y dejó ésta declarada
como abierta en su propio motivo, dentro de las `exclusions` del overlay.

**Referencia:** `ai-service/src/jbg_ai/retrieval/query_synonyms.yaml`, sección `exclusions`.

---

### El endpoint que agregue los tipos realmente presentes en el surtido

FIX1 midió lo que cuesta mover el vocabulario cerrado: **cinco ficheros, cuatro tests fijados, dos
lenguajes y dos specs vivas, para cuatro términos**. Nadie puede hoy responder «qué tipos de pieza
hay de verdad en el surtido» sin consultar la base a mano.

**Por qué se aplazó:** es una capacidad nueva, no la corrección de una laguna. **Sigue sin ficha
propia** en el plan de changes.

**Referencia:** `Documentos/Proyecto Final AIEng/informes/fix1-vocabulary-gaps-measurements.md` §8.

---

### `Llavero Cape Nao` Grande y pequeño podrían formar familia

Al ganar `llavero` como tipo, **comparten `piece_type` por primera vez** (SKU416 y SKU417), que es
la condición que el agrupador de C18a necesita para proponerlos como familia.

**Por qué se aplazó:** correr la sugerencia de C18a estaba explícitamente fuera del alcance de FIX1,
que no toca `families/`. Es una pasada del agrupador, no un cambio de código.

**Referencia:** `Documentos/Proyecto Final AIEng/informes/fix1-vocabulary-gaps-measurements.md` §8.

---

## C28 — lo que la revisión de perfiles destapó y no puede arreglar

Anotado el 2026-09-13, durante el apply de `add-profile-review-ui-and-metrics`. Los dos hallazgos
salieron de medir antes de revisar, no de la sesión, y ninguno cabe en ese change.

### `StoneType` guarda una piedra y hay piezas que llevan dos

Medido sobre los 1.168 perfiles `Approved`: de los **434 productos cuyo texto nombra al menos una
piedra del vocabulario, 14 nombran dos**, y en los catorce el extractor eligió una y descartó la
otra. Es el **3,2 %**, y no es un fallo del extractor: en una columna escalar no cabe la segunda
piedra por bien que la lea.

```
  SKU1140  esmeralda     <- el texto dice esmeralda y zafiro
  SKU1144  topacio       <- diamante y topacio
  SKU579-581  cuarzo     <- cuarzo y esmeralda   (tres productos)
  SKU582-584  onix       <- citrino y onix       (tres productos)
  SKU1148  onix          <- onix y turquesa
  SKU1149  amatista      <- amatista y nacar
  SKU593   topacio       <- diamante y topacio
  SKU795   amatista      <- amatista y topacio
```

La asimetría con `materials` es lo que lo hace visible: aquel es `jsonb` y admite lista —una pieza
es rutinariamente plata *y* baño de oro— mientras que `StoneType` es `character varying`. La
pantalla de revisión ofrece un solo valor porque refleja el esquema, no porque lo restrinja.

**Por qué se aplazó:** cerrarlo es **una migración** —`StoneType` → `StoneTypesJson`— y C08 reservó
el almacenamiento de esta capacidad precisamente para que C28 no necesitara ninguna. Y arrastra el
**contrato congelado**: `AiProposedProfile.StoneType` pasaría de `AiProposedText?` a
`AiProposedList`, lo que mueve `openapi.json` y obliga a acordar el cambio con el lado .NET. Son
dos invariantes del change a la vez. **Sin ficha asignada**, y probablemente fuera del alcance del
Proyecto Final.

**Referencia:** `backend/src/JoiabagurPV.Domain/Entities/ProductAiProfile.cs:50` ·
`backend/src/JoiabagurPV.Application/DTOs/Ai/AiEnrichResponse.cs:40`

---

### `vidrio` falta en `materials`, y alcanza 67 productos

**Lo encontró la sesión de revisión, no una consulta.** La exploración de C28 midió omisiones
buscando los términos que **ya estaban** en el vocabulario —`hilo`, `perla`, `plata`, `acero`,
`latón`— y por construcción no podía ver un hueco de cobertura. Una persona leyendo 204 productos sí.

| término | campo | anotados en la sesión | **en el corpus** |
|---|---|---:|---:|
| `vidrio` | `materials` | 13 | **67 (5,6 %)** |
| `naturaleza` | `style_tags` | 8 | **38** |
| `platino` | `materials` | 11 | 20 |
| `cobre` | `materials` | 9 | 15 |
| `cuarzo rosa` | `stone_type` | 1 | 7 |
| `turmalina` | `stone_type` | 1 | 5 |
| `titanio` · `bronce` · `marfil` · `hierro` · `madera` | `materials` | 7 | 1-5 cada uno |

`naturaleza` es el **segundo hueco conocido de `style_tags`**, junto al `filigrana` que FIX1 dejó
abierto más arriba en este documento y que alcanza 66 documentos. Ese eje empieza a tener un caso
propio.

Dos anotaciones **no son huecos de cobertura** y conviene no mezclarlas: `cuarzo rosa` es un
problema de **granularidad** —`cuarzo` sí está en `stone_type`, y la ficha de conocimiento ya
describe el rosa como una de sus variedades—, y `nácar` anotado bajo `materials` es una **frontera
de campo**, porque `nacar` está en el vocabulario de `stone_type`: la pregunta es si el nácar es el
material de la pieza o la piedra que lleva.

**Por qué se aplazó:** el mismo motivo que el término siguiente, y cuantificado en el informe —
añadir estos términos sacaría 21 de los 122 productos del estrato A y unos 30 de los 284 del B,
cambiando el lote que produjo la cifra publicada.

**Referencia:** [c28-implementation-measurements.md](../Documentos/Proyecto%20Final%20AIEng/informes/c28-implementation-measurements.md) §5

---

### El extractor emite `plata` cuando el texto dice `platino`

`platino` y `cobre` no están en el vocabulario cerrado de `materials`, que tiene nueve términos.
Medido sobre los productos cuyo texto dice `platino` y **nunca** dice `plata`:

| qué extrajo | productos | confianza | estrato |
|---|---:|---|---|
| `["plata"]` o `["oro","plata"]` | **11** | 0,45 | B |
| `[]` | 9 | 0,20 | A |

Los once son una alucinación: el modelo lee «platino», no lo encuentra entre los nueve canónicos y
emite el metal más parecido que conoce. **El sistema de confianza los cazó a los once** —0,45 es
literalmente *«lo afirmó sin que la frase esté en el texto»*— lo que confirma de paso la predicción
falsable del diseño de C28: las retiradas se concentran en el estrato B. `cobre` aparece en 15
productos, los 15 en el estrato A.

**Por qué se aplazó:** ampliar el vocabulario **cambiaría el lote a mitad de medición**.
`confidence.py` calcula el span contra el vocabulario, así que añadir los dos términos movería
hasta 24 productos fuera del estrato A —que solo tiene 122— y los 180 dejarían de ser los 180 que
produjeron la cifra publicada. Además obliga a re-enriquecer, y re-enriquecer reescribe
`ProposedProfileJson`, que es la columna contra la que se mide la tasa de corrección.

**Lo que costaría, completo:** los dos términos en `vocabularies.yaml`; sus fichas
`material-platino.md` y `material-cobre.md`, que **no son opcionales** —la spec viva de
`knowledge-corpus` exige exactamente una ficha por material canónico y
`test_every_canonical_material_has_exactly_one_sheet` lo hace fallar nombrando el término que
falta—; reindexar el corpus de conocimiento; y re-enriquecer con versión de prompt nueva, como
FIX1 hizo con sus 22 productos en `enrichment/v2`.

**Orden obligatorio:** la tasa de C28 tiene que estar **publicada antes**. Re-enriquecer primero
mezcla dos poblaciones y ninguna de las dos cifras significa lo que dice.

**Cautela heredada de la exploración:** igual que con `hilo`, «baño de platino» o «filigranas de
cobre» no son necesariamente una pieza *de* platino o *de* cobre. Por eso el registro de huecos de
la pantalla guarda el SKU y no solo el término: el change que amplíe la lista mira los textos
reales antes de decidir.

**Referencia:** `openspec/specs/knowledge-corpus/spec.md` §*Every canonical material has exactly
one sheet* · `ai-service/tests/knowledge/test_corpus_rules.py:257`

---

## C30b — la demo no genera argumentario, y lo que hace falta para que genere

**Estado:** **cerrada en el repositorio por C34** (2026-09-21): los pasos 2, 3 y 4 están hechos, más
la configuración .NET que el card necesita. **Queda sólo el paso 1 —crear el parámetro— y la
verificación en el entorno**, que son manuales y del desarrollador (tareas 11.3 y 11.4 de C34).
· **Abierto el:** 2026-09-14 · **Zona:** `deploy/demo/`, `compose.demo.yaml`
**No es un fallo:** es el comportamiento declarado, verificado y con test.

> **Lo que C34 hizo con esta entrada** *(2026-09-21)*:
>
> | Paso | Estado |
> |---|---|
> | 1 · `/jbg-demo/ASSIST_LLM_API_KEY` como `SecureString` | **pendiente, manual** — el comando está abajo y en `deploy/demo/README.md` §3 |
> | 2 · `deploy.sh` lee el parámetro **sin `:?`** y con `\|\| true` | **hecho**, y además registra `Generation credential: present/absent` —si está, nunca qué es— |
> | 3 · `JPV_ASSIST_LLM_MODEL` y `JPV_ASSIST_LLM_API_KEY` en `jbg-demo-ai` | **hecho**. La clave se interpola como `${ASSIST_LLM_API_KEY:-}`, con valor por defecto vacío, para que `docker compose config` resuelva también sin el script de despliegue; vacía equivale a no configurada (`blank_assist_llm_key_is_unset`) |
> | 4 · El parámetro en la lista de secretos manuales del runbook, marcado como el único opcional | **hecho**, con una §5.6b de comprobación del card |
> | + `AiSalesAssist__EnabledByDefault: "true"` y `AiGateway__AssistTimeoutMs: "10000"` en la API | **hecho** — sin el interruptor el card saldría siempre degradado y sin llamar a la IA |
>
> **Dos precisiones a lo que dice la entrada de abajo.** La primera: `prompt_version` ya no pasa a
> `assist/v1` sino a la versión vigente para M2/M3, **`assist/v3`**. La segunda: con la clave
> puesta, el log mostrará **también** `stage=router_client … credential=assist_fallback`, porque el
> enrutador de C31 repliega a esta clave cuando no tiene la suya. Es esperado y no gasta nada: el
> enrutador sólo corre en M1 —consulta libre sin pieza—, que C34 no expone.

### Qué pasa hoy

`compose.demo.yaml` **no pasa ninguna credencial de proveedor generativo** al servicio
`jbg-demo-ai` — comprobado, no hay `JPV_RAG_LLM_*` ni `JPV_ASSIST_LLM_*` en el fichero. Así que
la demo sirve `POST /v1/assist/sale` con `pitch: ""`, `prompt_version: null` y `usage` a cero:
exactamente la respuesta de C30a, con **200** y no 503.

Eso es correcto por diseño y no hay que "arreglarlo" con prisa: un despliegue sin credencial
sirve la mitad estructurada, que es la que tiene grupos, avisos y citas resolubles. Es también
el *rollback* de C30b. Lo que falta es **decidir** que la demo enseñe la capa de generación, que
es media hora de trabajo y una clave.

### Lo que hay que cambiar, y lo que NO

**Corrección de una nota anterior de este mismo change:** el informe de implementación llegó a
decir que esto vivía en `terraform/`. **No es así**, y la diferencia importa:

| | ¿hace falta? | por qué |
|---|---|---|
| `terraform/demo/iam.tf` | **NO** | el rol de instancia ya lee **todo el prefijo** `/jbg-demo/`, no parámetro a parámetro |
| `terraform/demo/ssm.tf` | **NO** | los secretos **no se declaran en Terraform a propósito**: un valor pasado a Terraform se escribe **en claro en el fichero de estado**. Se crean a mano, como los otros seis |
| `/jbg-demo/ASSIST_LLM_API_KEY` | **sí**, a mano | `aws ssm put-parameter --type SecureString` |
| `deploy/demo/deploy.sh` | **sí**, una línea | leer el parámetro **sin `:?`** |
| `compose.demo.yaml` | **sí**, dos líneas | pasar la clave y fijar el modelo |
| `deploy/demo/README.md` | **sí** | el runbook enumera los secretos que se crean a mano |

**Terraform no se toca.** Ésa era la parte de la nota anterior que estaba mal.

### Los cuatro pasos

**1 · Crear el parámetro, a mano y una vez** (como los otros seis secretos de esta demo):

```bash
aws ssm put-parameter --region eu-west-1 \
  --name /jbg-demo/ASSIST_LLM_API_KEY \
  --type SecureString \
  --value "sk-..." \
  --description "C30b credential for the sale argument. Separate from EMBEDDING_API_KEY"
```

**2 · `deploy/demo/deploy.sh`**, junto a las otras lecturas de Clase A:

```bash
# C30b. A DIFERENCIA de los demás, este parámetro puede NO existir: sin él la capa
# de generación no corre y la ruta sirve la respuesta estructurada con 200. Por eso
# `|| true` — `set -e` más el error del store abortarían el despliegue entero por una
# credencial cuya ausencia es un estado válido y declarado.
export ASSIST_LLM_API_KEY="$(read_parameter ASSIST_LLM_API_KEY || true)"
```

Y **no** añadir una línea `: "${ASSIST_LLM_API_KEY:?...}"` en el bloque de validación: ese bloque
existe para que un valor **vacío** falle ruidosamente, y aquí vacío significa «no generamos»,
que es legítimo.

**3 · `compose.demo.yaml`**, en `jbg-demo-ai`:

```yaml
      # Clase C — ajuste versionado, no parámetro. Misma regla que
      # JPV_EMBEDDING_MODEL y JPV_RETRIEVAL_DISTANCE_THRESHOLD (C17 D8): el store
      # es un sitio donde un valor cambia sin revisión de código, y el modelo
      # cambia lo que cuesta y lo que se midió.
      JPV_ASSIST_LLM_MODEL: openai/gpt-4o-mini
      # Clase A — secreto. Fuente: /jbg-demo/ASSIST_LLM_API_KEY. Ausente = la capa
      # de generación no corre y la ruta sirve la respuesta de C30a con 200.
      JPV_ASSIST_LLM_API_KEY: ${ASSIST_LLM_API_KEY}
```

`JPV_ASSIST_PITCH_TIMEOUT_SECONDS` se deja **fuera** hasta tener una medición del propio
despliegue: el defecto de 4 s está medido desde una máquina de desarrollo en España a través de
un interceptor TLS, que es una **cota superior** de la latencia del proveedor. Si la demo mide
una distribución distinta, entonces se añade — con la cifra delante, como se hizo con el 3 s.

**4 · `deploy/demo/README.md`**: añadir el parámetro a la lista de secretos que se crean a mano,
marcándolo como **el único opcional** de esa lista.

### Cómo comprobar que funcionó

Sin abrir la consola de AWS y sin leer ninguna clave, en el log del contenedor:

```
stage=assist_client model=openai/gpt-4o-mini timeout_s=4.0 credential=assist
```

`credential=rag_fallback` diría que está replegando a la clave de C09, y `stage=assist_client`
ausente, que no se construyó cliente: la capa no corre y la ruta sirve C30a. Y en la respuesta,
`prompt_version` pasa de `null` a `assist/v1` — que es exactamente la distinción que C30b metió
en el contrato para poder ver esto desde fuera.

### Por qué no se hizo aquí

C30b declara `terraform/`, `.github/workflows/` y `backend/` fuera de alcance, y el despliegue
de la demo es trabajo de despliegue, no de la capa. La mitad de Python está entregada, probada
con **13 tests** y **no es andamio**: en local se separa hoy poniendo `JPV_ASSIST_LLM_API_KEY`
en `backend/.env`, que es de donde el barrido de C30b lee sus credenciales.

---

## Active Change: `add-guardrails-and-intent-router` (C31)

### Desplegar el clasificador de intención en la demo

**Estado: pendiente, y la configuración que se despliega está decidida por medición.**

Mismo patrón que la entrada de C30b de arriba, con **tres** variables en lugar de una y con un
requisito que manda sobre todo lo demás: **sólo se despliega la configuración que pasó el veto.**

Medido sobre los 119 casos de `evals/routing/cases.yaml`, mismo prompt `router/v3`, temperatura
cero, cobertura completa en los dos arms:

| modelo | acierto `catalog` | falso positivo | silenciadas | veto |
|---|---|---|---|---|
| `openai/gpt-4o-mini` | 81,3 % | 6,25 % | **3** | **NO PASA** |
| `openai/gpt-4o` | 100 % | 0,00 % | **0** | **PASA** |

`DEFAULT_ROUTER_MODEL` quedó fijado en **`openai/gpt-4o`** por esa medición, y ése es el valor
que el despliegue tiene que poner. **Un despliegue que apunte `JPV_ROUTER_LLM_MODEL` a
`gpt-4o-mini` estaría sirviendo una configuración vetada**, que silencia tres consultas que la
tienda sí puede contestar.

Mientras la credencial no esté puesta, el clasificador no se construye, `intent` vuelve a
`unclassified` y la ruta se comporta exactamente como la dejó C30b. Eso es a la vez el
*fail-open*, la ablación y el rollback, y está entregado con test.

### Los cuatro pasos

**1 · Crear el parámetro, a mano y una vez** (como los otros siete secretos de esta demo):

```
aws ssm put-parameter --name /jbg-demo/ROUTER_LLM_API_KEY --type SecureString --value '…'
```

**Terraform no se toca**, por la misma razón que en C30b: el rol de instancia ya lee todo el
prefijo `/jbg-demo/`, y un valor pasado a Terraform se escribe en claro en el fichero de estado.

**2 · `deploy/demo/deploy.sh`**: leer el parámetro **sin `:?`**, para que un despliegue sin él
siga funcionando — que es precisamente el estado en el que hay que dejarlo hasta que el veto
pase.

**3 · `compose.demo.yaml`**: pasar `JPV_ROUTER_LLM_API_KEY` y fijar `JPV_ROUTER_LLM_MODEL`.

`JPV_ROUTER_TIMEOUT_SECONDS` se deja **fuera**, igual que C30b dejó fuera el suyo y por la misma
razón, sólo que más fuerte: el defecto de 2 s está **declarado no calibrado** en el docstring de
la constante, se tomó desde una máquina de desarrollo en España a través de un interceptor TLS, y
este corte va **delante de todo**, así que su efecto es más duro que el del argumentario. Se
añade cuando el despliegue mida su propia distribución, con la cifra delante.

**4 · `deploy/demo/README.md`**: añadir el parámetro a la lista de secretos que se crean a mano,
marcándolo como **opcional**, y anotando junto a él que `JPV_ROUTER_LLM_MODEL` **no puede
apuntar a `gpt-4o-mini`**, que es la configuración que el veto rechazó.

### Cómo comprobar que funcionó

Sin abrir la consola de AWS y sin leer ninguna clave, en el log del contenedor:

```
stage=router_client model=openai/gpt-4o timeout_s=2.0 credential=router
```

**Si ese `model=` dice `gpt-4o-mini`, el despliegue está sirviendo la configuración vetada** y
hay que corregirlo antes de mirar nada más.

`credential=assist_fallback` o `rag_fallback` dirían que repliega por la cadena, y
`stage=router_client` ausente, que no se construyó cliente y la ruta se comporta como C30b. Y en
la respuesta, `intent` pasa de `unclassified` a un veredicto de enrutado.

### Dos cosas más que este change dejó medidas y que el despliegue hereda

1. **El límite de tasa del proveedor decide cuánto se puede medir de golpe.** El barrido de 119
   casos a concurrencia 6 produjo **22 degradaciones por `RateLimitError`**, y sobre `gpt-4o`,
   **89 de 119**. El arnés reintenta sólo eso —nunca un fallo de parseo, que es la degradación
   que se está midiendo— y aun así hace falta concurrencia 1 y pausa. No afecta al camino de
   servicio, que hace una llamada por petición.
2. **La primera llamada de un proceso paga el `import litellm` dentro de su propio *timeout*.**
   Medido: los dos primeros casos de una pasada agotaron **20 s** por eso y por nada más. En el
   camino de servicio, con un corte de 2 s, eso significa que **la primera consulta libre tras un
   arranque en frío degrada** — cae en el *fail-open*, que es el comportamiento correcto, pero es
   una degradación evitable calentando el import en el arranque de la aplicación. No se hizo aquí
   porque tocar el arranque está fuera del alcance de este change; queda anotado.

---

## C32a · La consulta puntual de disponibilidad en .NET

**Estado:** identificada, acotada y **no hecha**. Aplazada **con motivo**, no por falta de tiempo.

El §6.1 del diseño RAG dibuja la arista `R2 -->|tool: consultar_disponibilidad| API` y deja el
esquema de la llamada de vuelta Python → .NET como *«decisión abierta del change del agente de
venta»*. C32a es ese change, y la resuelve **difiriéndola**: la tool se sirve desde
`ai.pos_projection`, que es un dato que Python ya tiene proyectado.

### Por qué no se hizo aquí

La única arista Python → .NET que existe hoy es
[`AiIndexFeedController`](../backend/src/JoiabagurPV.API/Controllers/AiIndexFeedController.cs), y
no sirve para esto por tres razones independientes:

1. Está autenticada con `X-Index-Feed-Key` y **sin `[Authorize]` a propósito** — *«a user JWT
   must not open these routes»* — así que no transporta identidad de usuario.
2. **No transporta `pos_id`**, que es justo el ámbito que una consulta puntual necesita.
3. Su ruta `pos-availability` es un **feed paginado de 200 filas con keyset**, pensado para un
   drenaje batch y no para preguntar por una pieza.

Construirlo habría significado ruta .NET nueva, filtro de autenticación con ámbito de punto de
venta y tests de integración: **zona .NET dentro de un change de zona Python**.

### Qué hace falta cuando se haga

- Ruta .NET puntual por `(pos_id, product_id)` o por `(pos_id, sku)`.
- Un esquema de autenticación de vuelta que **sí** transporte el ámbito del punto de venta, y
  que no sea la clave de feed: la clave de feed abre rutas sin usuario por diseño.
- Decidir si la respuesta sigue siendo una **banda cualitativa** o pasa a ser la cifra. La
  frontera del §6.2 dice que .NET es la autoridad sobre el stock, así que la cifra es suya; lo
  que C32a fija es que **al modelo no le llega un número**, venga de donde venga.

### Por qué el reemplazo es directo

La tool no tiene lógica de disponibilidad dentro: llama a
`ProductSearchPort.availability_bucket(product_id, pos_id=...)` y traduce con
`AVAILABILITY_LABEL_BY_BUCKET`. Sustituir el puerto por un cliente del endpoint .NET no cambia
la forma de la observación, ni el vocabulario cerrado, ni ninguno de sus tests — salvo el del
invariante de solo-lectura, que **volverá a ser el que decide**: un cliente HTTP de propósito
general expone `post`, `put`, `patch` y `delete`, y el tercer eje de la comprobación lo rechaza.
Quien construya ese cliente tendrá que envolverlo en una superficie que exponga sólo la lectura,
que es exactamente la restricción que se quería dejar puesta.


---

## Implementation Guidance

When implementing deferred tasks:

1. **Check this document** - Ensure task is still relevant and not superseded
2. **Review original spec** - Check `openspec/changes/[change-id]/specs/` for full requirements
3. **Review design decisions** - Check `openspec/changes/[change-id]/design.md` for context
4. **Create new change proposal** - If adding new capability, create new change proposal
5. **Update this document** - Mark tasks as completed or update status

---

**Last Updated:** 2026-09-20
**Maintained By:** Development Team

---

## C32b · La política de *timeout* y de circuito de `POST /v1/assist/agent` en la capa .NET

**Estado:** identificada, acotada y **no hecha**. Aplazada **con motivo**: hoy la ruta no tiene
ningún consumidor. *(Sigue abierta tras C34, que dejó fuera la ruta del agente por decisión cerrada
—sus marcadores hablan de varias piezas—.)*

> **Lo que C34 cambia en esta entrada** *(2026-09-21)*. La ruta determinista ya no declara 5 s: C34
> registró el cliente `ai-assist` para `/v1/assist/sale` con **10 s y un suelo de 8 s validado al
> arranque**, sin reintento en timeout y con circuito propio. El agente **no debe reutilizarlo**:
> su techo es otro (15 s más las herramientas de la vuelta en curso) y su circuito tiene que contar
> `stop_reason=fallo_proveedor`, que la ruta determinista no emite. El patrón a copiar sí está ya:
> un cliente con nombre por ruta, `HttpClient.Timeout` infinito y el presupuesto en el *pipeline*.

C32b publica `POST /v1/assist/agent` y **nadie la llama**. `IAiGatewayClient` no tiene método para
ella, no hay pantalla detrás y el change de hidratación no la consume. Escribir su política de
tiempo de espera y de cortocircuito ahora sería escribirla contra un consumidor imaginario, que es
la misma razón por la que C32a difirió el endpoint de disponibilidad.

### Por qué la política no puede ser la de `/v1/assist/sale`

Medido en la pasada `293fe5c6e470`, sobre 102 peticiones con `gpt-4o`:

| | `/v1/assist/sale` | `/v1/assist/agent` |
|---|---|---|
| Latencia declarada | **5 s** (§6.4 del diseño) | **15 s**, fijados por medición |
| p50 medido | — | **5,3 s** |
| p95 medido | — | **9,0 s** |
| Máximo medido | — | **11,9 s** |

**Un cliente .NET con el *timeout* de la ruta determinista cortaría más de la mitad de las
peticiones del agente.** El p50 del agente es del orden de la latencia total que la otra ruta
declara como techo.

### Qué hace falta cuando se haga

- **Un *timeout* propio por ruta**, no uno compartido: 15 s más el margen de red, contra los 5 s
  de la determinista.
- **Un cortocircuito que distinga degradación de fallo.** Esta ruta **no devuelve 5xx** cuando el
  proveedor cae: responde 200 con `partial: true` y un `stop_reason` del vocabulario cerrado. Un
  circuito que contase esas respuestas como fallos se abriría sobre una ruta que está funcionando
  como está diseñada; el que las ignorase perdería la única señal de que el proveedor está caído.
  Lo que hay que contar es `stop_reason=fallo_proveedor`, que existe precisamente porque la
  primera pasada de C32b demostró que sin él esas respuestas son indistinguibles de una completa.
- **Decidir qué hace el mostrador con `partial: true`.** Es una respuesta útil e incompleta, y la
  pantalla tiene que poder decirlo sin alarmar: no es un error.

### Y una restricción operativa que el consumidor heredará

La pasada midió que **la cuota de tokens por minuto de la organización**, y no el dinero, es lo que
limita el ritmo: con peticiones de ~13.000 tokens, un techo de 25.000 TPM admite **una petición por
minuto**. Un mostrador con varios operarios simultáneos choca con eso mucho antes que con el coste,
y el síntoma es un `RateLimitError` que la capa convierte en `fallo_proveedor` y sirve degradado.
Dimensionar la cuota es parte de poner esta ruta en producción, no un detalle de la medición.

> **Nota de la verificación independiente de C32b.** Los 15 s de la tabla de arriba **no acotaban
> la petición** cuando se escribió: el reloj sólo se miraba antes de cada vuelta, y el peor caso por
> construcción eran 15 + 8 + 2 × 4 = 31 s más las herramientas. Ahora el bucle corre contra 15 s
> menos la reserva del argumentario y la vuelta en curso se corta; el límite es **15 s más, como
> mucho, las herramientas de esa vuelta**, que no se cancelan a medias. Es el número que un
> *timeout* .NET debe cubrir, con su margen de red.

---

## C32b · Once tests preexistentes de `ai-service` salen a la red con una clave falsa

**Estado:** medido, **no corregido** y fuera del alcance de C32b: los tests son de C30b y C31, y
ninguno lo introdujo este change. Encontrado por su verificación independiente.

`tests/api/test_assist_generation.py` construye la app con una clave de mentira
(`jpv_rag_llm_api_key="sk-test"` y análogas) e inyecta dobles para el *embedding*, la búsqueda y el
corpus, **pero no para el clasificador ni para el argumentario**. La ruta construye entonces los
clientes reales de LiteLLM y los usa: la llamada sale hacia `api.openai.com`, muere (TLS o 401) y
el test pasa porque la capa degrada. Medido con un guardia de sockets y de `psycopg` sobre la suite
entera: **12 resoluciones de `api.openai.com` y 1 de `raw.githubusercontent.com`** (la tabla de
costes que descarga `litellm`), en estos once tests:

- `test_the_configured_timeout_reaches_the_generation_client`
- `test_the_dedicated_credential_is_preferred_over_the_enrichment_one`
- `test_the_enrichment_credential_is_the_fallback_and_not_a_requirement`
- `test_the_fallback_is_recorded_so_a_deployment_can_check_it_instead_of_assuming`
- `test_the_configured_model_reaches_the_generation_client`
- `test_the_enrichment_model_cannot_move_the_assistance_model`
- `test_the_classifier_credential_falls_back_through_the_three_links` (tres veces)
- `test_which_classifier_credential_is_in_force_is_recorded_without_the_key`
- `test_the_configured_classifier_model_and_timeout_reach_the_client`
- `test_the_argument_model_cannot_move_the_classifier_model`

Y uno más de otro fichero, `tests/api/test_retrieval_real.py::test_missing_embedding_key_is_503`,
intenta abrir una conexión de `psycopg`.

**Es el mismo defecto que el §10.4 del QA de C32b encontró en su propio test y corrigió**: *«la suite
no abre sockets» no es una propiedad que la suite compruebe sola*. Aparte, **72 tests `db`** corren
contra un PostgreSQL real a través de testcontainers cuando Docker está disponible (y se saltan si
no): eso es diseño, pero significa que «la suite corre sin base de datos» sólo es cierto en una
máquina sin Docker.

### Qué hace falta cuando se haga

- **Pilotar el resolutor directamente**, como hace `test_the_credential_chain_is_agent_then_assist_then_enrichment`
  desde C32b, o **inyectar los dobles** del clasificador y del argumentario en `app.state` antes de
  servir la petición. Lo que se prueba es la resolución y lo que se registra, que ocurre antes de
  cualquier llamada.
- **Después, un guardia de sockets automático en `tests/conftest.py`** que rechace toda conexión que
  no sea de bucle local y deje pasar la de testcontainers. Sin los once arreglados antes, ese
  guardia los pondría en rojo el primer día; con ellos arreglados, convierte la propiedad en algo
  que la suite comprueba en vez de algo que su README afirma.

---

## C32b · El desglose del uso por etapa en la respuesta de `POST /v1/assist/agent`

**Estado:** identificado y **no hecho**, a decidir cuando la ruta tenga consumidor (C34/C36).

`AgentUsage` suma los tokens de hasta tres etapas —clasificador, bucle y argumentario— que corren
modelos distintos, y publica **un solo `model`**, el de la última. Quien tarife `usage` × `model`
reproduce el error de coste que la verificación independiente encontró en el arnés. Dentro del
proceso ya está resuelto (`AgentRun.router_usage`, `loop_usage` y `pitch_usage`, que el arnés
tarifa una a una), y la descripción de `AgentUsage.model` en el contrato avisa de que no es una
clave de precio.

**Lo que falta, si un consumidor .NET necesita el coste**: añadir a `AgentUsage` un desglose por
etapa, cada una con su modelo y sus tokens. Es **adición pura** sobre un esquema que sólo publica
esta ruta —`/v1/assist/sale` no se mueve— y no se hace ahora porque, sin consumidor, agrandaría la
superficie congelada para nadie.
