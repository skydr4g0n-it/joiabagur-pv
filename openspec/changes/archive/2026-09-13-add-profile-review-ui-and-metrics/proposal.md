# Change: add-profile-review-ui-and-metrics

## Why

The design promises a hybrid human review of AI-proposed catalog attributes (§7.8), two metrics that
come out of it (§11.5) and a delivery checkbox that asks for them by name (§16). All three are
assertions with nothing behind them: **all 1.200 profiles sit at `ReviewOrigin = AutoBulk`, with zero
reviewers and zero measured times**. The reviewed path does not exist, and §11.5 already warned that
those numbers *«no existen sin la vía revisada»*.

Exploration also refuted the premise the plan's card rested on. **The hybrid routing narrows nothing:**
`size_label` is the only field the extractor ever marks `rule` (539 of 1.200); `piece_type`,
`materials` and `stone_type` come back `inferred` every single time, so the whole catalog enters the
queue with two or three sensitive fields each. Which products get reviewed therefore has to be an
explicit sampling criterion, and none was written anywhere.

## What Changes

- **A review queue defined by origin rather than by status.** `ReviewOrigin = AutoBulk` over
  `ReviewStatus = Approved`; reviewing moves a profile to `Human`. Nothing leaves the vector index
  while a review session is in progress.
- **A stratified, deterministic sample.** Three strata by evidence — absence (`0,20`), asserted
  without a textual span (`0,45`), asserted with one (`0,85`) — with quotas of 60 each over the 1.168
  approved profiles. Ordered by a seeded hash so the batch is reproducible **without being persisted**,
  which is what avoids a seventh migration.
- **Corrections recorded with a direction** — addition, removal, substitution, confirmation — because
  that is what separates an omission from a hallucination. The span heuristic can only catch the
  second: measured, **94 products name a material in their text that the extractor did not extract,
  and 81 of them (86 %) sit in the highest-confidence stratum**, invisible to any confidence-ordered
  queue.
- **A batch review screen** showing, per field, the proposed value, its confidence and its provenance
  (`rule` / `inferred`), with sensitive inferred fields highlighted and **the product's source text
  beside them** — the reviewer's criterion is fidelity to that text, never the truth of the piece,
  because the system holds no photographs.
- **Per-item timing persisted on every save**, never accumulated in screen state, and **bulk approval
  confined to one field within one stratum**, marked as such and left without a fabricated duration.
- **A metrics route** reporting correction rate per field, per stratum and per direction, a total
  weighted by real stratum sizes, and the two timing populations — timed and bulk — counted apart.
- **A separate pass over the 32 rejected profiles**, asking the inverted question: is any rejection
  wrong? They are gift-shop articles (candles, postcards, magnets) and their rejection is correct, but
  one of them — `Presión Oro`, `piece_type: anillo`, `materials: ["oro"]` — looks like a sellable ring
  that fell out of the index.
- **Creating a family from the family-review screen**, with the nine SKUs C18b left open as the test
  case: seven of `piece_type` `cadena`, for which no family exists at all, and two plain wedding bands.
- **Keyboard navigation on both review screens**, which C18b's task 6.4 claimed as delivered while the
  screen holds no key handler at all.
- **A narrow shell extraction** of exactly what has two consumers: the per-item stopwatch, the
  three-state list and the keyboard hook.

No breaking changes. No database migration — C08 reserved `ProposedProfileJson` and `ReviewDurationMs`
in writing and delivered them. The frozen `jbg-ai` contract is untouched.

## Capabilities

### New Capabilities

- **`profile-review`** — standing human review of AI-proposed product profiles: the origin-based
  queue, the stratified deterministic sample, the correction recorded with its direction, bulk
  approval bounded to one field and one stratum, review time persisted per item, the inverted pass
  over rejected profiles, and the metrics that fall out of all of it.

  This is a new capability rather than an extension of `product-ai-profile` because **that spec
  already reserved the ground in writing**: *«This capability MUST expose no read route: no profile
  retrieval, no review queue, no metrics and no aggregation. Approving or rejecting a profile is
  likewise outside this capability»*, and *«Populating these fields when a person reviews a profile is
  outside this capability»*. It is the same split C18b made between `product-family` and
  `family-review`.

### Modified Capabilities

- **`family-review`** — two added requirements: a family can be **created** from the review screen
  (it lists and dissolves families today but cannot create one, which is why the two degenerate roots
  C18a delegated to a person are still open), and a reviewer can work a queue **without the mouse**.

### Unchanged

- **`product-ai-profile`** — deliberately untouched. Its requirements already anticipate this change
  and delegate to it; nothing in its behaviour moves.
- **`index-feed`** — untouched. A correction already re-emits the product because the watermark
  includes `profile.UpdatedAt`, and a rejection already propagates as a removal.

## Impact

- **`backend/src/JoiabagurPV.Application`** — new review service, DTOs, FluentValidation rules, the
  shared stratum function and the metric computation.
- **`backend/src/JoiabagurPV.API`** — four new routes on `AiCatalogController`, under the existing
  `api/ai/catalog` prefix and the existing administrator-only policy.
- **`backend/src/JoiabagurPV.Tests`** — unit tests for stratification, determinism, correction
  direction and the null-not-zero rule; integration tests for the routes and their permissions.
- **`frontend/src`** — a new admin page and its service and types, one new route entry, the three
  extracted pieces, and edits to `family-review.tsx` for family creation and keyboard support.
- **No impact** on `Domain/`, `Infrastructure/`, `ai-service/`, `terraform/` or the CI workflows.
- **No migration**, no schema change, and no change to `Documentos/modelo-de-datos.md`.
- **Operational impact that is part of the change, not after it:** a real review session of 180 items
  plus the short pass over the 32 rejected ones. The deliverable is two numbers; the screen is what
  has to be built in order to obtain them. C18b is the precedent for delivering the mechanism and
  leaving the average unmeasured.
