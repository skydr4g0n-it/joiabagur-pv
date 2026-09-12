## Context

The design document promises a hybrid human review (§7.8), two metrics that come out of it (§11.5)
and a delivery checkbox that names them (§16). Measured against the local Postgres on 2026-09-12, the
reviewed path holds nothing at all:

| `ReviewStatus` | `ReviewOrigin` | profiles | with reviewer | with timing |
|---|---|---:|---:|---:|
| `Approved` | `AutoBulk` | 1.168 | 0 | 0 |
| `Rejected` | `AutoBulk` | 32 | 0 | 0 |

Three facts from the tree shape every decision below.

**The hybrid routing narrows nothing.** `size_label` is the only field the extractor ever marks
`rule` (539 of 1.200). `piece_type` (1.173), `materials` (1.200) and `stone_type` (629) are always
`inferred`. The §7.8 policy filters correctly and discards nobody, so **the whole catalog is the
queue** and the sampling criterion has to be invented here.

**Confidence is an evidence staircase, not a probability.** `confidence.py` opens with *«The model's
own score is never copied»* and emits four values: `1,00` rule, `0,85` the vocabulary phrase is
literally in the text, `0,45` asserted with no such phrase, `0,20` absent. It follows that the
heuristic can only catch false positives and is structurally blind to omissions — and the blindness
is measured: **94 products name a material the extractor did not extract (`hilo` 60, `perla` 35,
`plata` 3), and 81 of them sit at `0,85`**.

**The storage is already there.** C08 reserved `ProposedProfileJson` and `ReviewDurationMs` in
writing, so no migration is needed, and `product-ai-profile` explicitly excludes read routes, queues,
metrics and approval from its own scope — this change is the capability it was delegating to.

## Goals / Non-Goals

**Goals:**

- Produce the two numbers §16 asks for, from a sample whose composition can be defended.
- Make the **direction** of each correction visible, so omission and hallucination are separable.
- Keep the vector index whole throughout a review session.
- Avoid a seventh migration.
- Repair, rather than repeat, the timing failure C18b recorded.
- Close the two inherited gaps from C18b: keyboard navigation and family creation.

**Non-Goals:**

- Re-enriching any product, changing the closed vocabulary, or moving a prompt version. A vocabulary
  gap the review uncovers is recorded as a finding, the way C18a's became `FIX1`.
- Touching `ai-service/`, the frozen contract, `confidence.py` or the confidence constants.
- Reviewing the whole catalog. The batch is 180 and §15 limitation 2 is declared from what is
  actually reviewed.
- Extracting the whole shell of `family-review.tsx`.

## Decisions

### D1 — The queue is defined by origin, not by status

`ReviewOrigin = AutoBulk` over `ReviewStatus = Approved`. Reviewing moves the profile to `Human` and
leaves the status to the reviewer's verdict.

| Alternative | Why not |
|---|---|
| Open a batch into `ReviewStatus = Pending` | The index feed selects `Approved`, so 180 documents would leave the index mid-session and be re-embedded on re-approval. The queue would degrade the very corpus the demo runs on |
| A `ReviewBatch` entity | A seventh migration, which is exactly what C08 paid to avoid |

`product-ai-profile` already carries the requirement *«Review status and review origin are
independent»*, with the profile docstring adding that human-review metrics select on origin alone.
This decision spends that independence rather than inventing anything.

```
        ReviewStatus →   Approved          Rejected
 ReviewOrigin ↓        ┌──────────────┬──────────────┐
   AutoBulk            │    1168      │      32      │  ← the queue / the inverted pass
                       ├──────────────┼──────────────┤
   Human               │  reviewed    │  reviewed    │  ← what this change fills
                       └──────────────┴──────────────┘
                         indexed         out of index

   status governs the index  ·  origin governs the metric
```

### D2 — The sample is stratified by evidence, not ordered by confidence

Strata are computed from the **worst** of the three sensitive fields, with an absent `stone_type`
treated as unremarkable because most jewellery carries no stone:

```
peor = MIN( conf(piece_type) ?? 0,20 , conf(materials) ?? 0,20 , conf(stone_type) ?? 1,00 )

  A · absence        peor ≤ 0,20    122 approved    quota 60   →  is the emptiness real?
  B · no span        peor ≤ 0,45    285 approved    quota 60   →  removals expected (270 are stone_type)
  C · with span      peor = 0,85    761 approved    quota 60   →  additions expected (the 94 measured)
```

| Alternative | Why not |
|---|---|
| Lowest confidence first | Blind to 81 of the 94 measured omissions, and the published rate is biased upward relative to the catalog |
| Uniform random | Spends 63 % of the attention on stratum C without separating populations, and cannot answer *«is the span a usable triage signal?»* |
| Cross-stratify by `data_origin` too | **Infeasible**: stratum A holds only 8 real products. §15 does not require it either — enrichment metrics *«miden al extractor y no la verdad del dato»*. `data_origin` is reported descriptively |

The design yields three results instead of one: the §16 rate, a per-stratum rate that validates or
refutes the span heuristic as triage, and the omission class, which is reachable **only** if stratum C
is in the batch.

### D3 — The sample is deterministic and is not persisted

Ordering within each stratum is by `hash(ProductId + seed)`, with the seed in configuration.

The batch is reproducible on demand, the seed is declared in the implementation report, and nothing
has to be stored — which is what keeps D1's rejection of `ReviewBatch` consistent. It mirrors the
determinism `family-review` already requires of its audit.

### D4 — The reviewer's criterion is fidelity to the source text

There are **0 photographs and 0 visual embeddings** in the system; the 764 synthetic products and the
text of the 404 real ones were written by an LLM. *«Is this true of the piece?»* is therefore not
executable. *«Does the source text support this value?»* is, and it is precisely what §11.5 claims to
measure.

The consequence is a UI requirement, not a note: the product's **full name and description** sit
beside the proposed values, because they are the only material the judgement is made against.

A second consequence: at `0,85` the span check already asked *«is the phrase present?»*, so the human
adds value only by catching what is **missing**. The screen therefore asks *«¿falta algo?»* in that
stratum and *«¿es correcto?»* in the others. Asking the wrong one is how the 81 omissions get
confirmed away.

### D5 — Corrections carry a direction

| direction | scalar | list |
|---|---|---|
| `confirmation` | unchanged | equal sets |
| `addition` | null → value | elements grow |
| `removal` | value → null | elements shrink |
| `substitution` | value → other value | same size, different content |

Reporting only *«corrected: yes/no»* discards exactly what the stratified design was built to find.
The falsifiable prediction is that removals concentrate in B and additions in C; either outcome is a
result worth publishing.

`ProposedProfileJson` is **immutable**. The rate is the difference between that column and the values
in force, so rewriting it would destroy the metric silently and irrecoverably.

### D6 — Timing is persisted per save, and the two populations never merge

C18b recorded 64 judgements and **6 timings**, because *«el cronómetro vivía en el estado del
componente y moría con la pestaña»*. Its corrected pattern — duration travelling in the same request
that records the judgement — is copied rather than redesigned.

Bulk approval leaves the duration absent by design. Therefore:

- Bulk approval is confined to **one field within one stratum**, and rejected otherwise. Approving
  300 `color_tags` at once is cheap and legitimate; bulk-approving stratum B empties the change of
  content.
- Metrics report **timed** and **bulk** populations separately, with counts, and the average is
  `null` and never `0` when nothing was timed — the rule `FamilyReviewMetricsDto` already follows,
  because a zero asserts an instantaneous review while a null reports an absence.

### D7 — Narrow shell extraction

Only what has two real consumers moves: `useItemStopwatch()`, `<ThreeStateList>`,
`useReviewKeyboard()`. The table, the bulk bar and the metrics card are copied.

| Alternative | Why not |
|---|---|
| Extract the whole 920-line shell | Refactoring a screen a person already validated, with the frontend suite red at baseline (118 of 482 failing): the regression would not be reported by anything |
| Extract nothing | The keyboard handler would be born duplicated across two screens |

`family-review.tsx` gains the keyboard hook as well, which is what makes the extraction pay and what
retires C18b's task 6.4 claim instead of leaving it false in the archive.

### D8 — Family creation lands in `family-review`, as its own requirement

`POST /api/product-families` has existed since C07, so this is frontend-only. It is specified as a
separate requirement of the `family-review` capability rather than folded into profile review,
because mixing two capabilities inside one requirement is how a spec stops being checkable.

## Flow

```
  Browser (profile-review.tsx)          .NET (Application/API)            Postgres            jbg-ai
        │                                      │                             │                   │
        │ GET profile-review-queue             │                             │                   │
        │─────────────────────────────────────▶│ stratum(FieldConfidenceJson)│                   │
        │                                      │ hash(ProductId+seed) order  │                   │
        │                                      │────────────────────────────▶│                   │
        │◀─ 180 items, stratum + text + fields │◀────────────────────────────│                   │
        │                                      │                             │                   │
   [ stopwatch starts on item open ]           │                             │                   │
        │ POST profile-reviews                 │                             │                   │
        │   values + durationMs                │ diff vs ProposedProfileJson │                   │
        │─────────────────────────────────────▶│ → direction per field       │                   │
        │                                      │ Origin=Human, reviewer,     │                   │
        │                                      │ ReviewedAt, DurationMs      │                   │
        │                                      │────────────────────────────▶│                   │
   [ stopwatch resets — nothing held in state ]│                             │                   │
        │                                      │                             │                   │
        │                          (later, unchanged)  GET index-feed ?since │                   │
        │                                      │  watermark includes         │◀──────────────────│
        │                                      │  profile.UpdatedAt          │──────────────────▶│
        │                                      │                             │   re-embed if the │
        │                                      │                             │   source hash moved
```

The right-hand half is **existing behaviour**: `IndexFeedRepository` already folds `profile.UpdatedAt`
into the watermark and carries `IsActive` and `ReviewStatus` on the row, so a correction re-indexes
and a rejection propagates as a removal with no new code.

## Risks / Trade-offs

- **The stopwatch comes back empty again, as in C18b** → duration travels in the save request and a
  test asserts that an individual save always carries one; bulk approval is bounded so it cannot
  become the whole batch.
- **Bulk approval hollows out the batch** → confined to one field within one stratum, rejected
  otherwise, and marked in the metrics.
- **The shell extraction breaks `family-review.tsx` silently** → narrow extraction, plus a baseline of
  failing **test names** taken before any edit and compared by name, never by count; both suites are
  red at baseline.
- **The correction rate comes out near zero and the deliverable looks thin** → that is a result, not a
  failure, but only because the sample is stratified: with uniform random sampling it would be
  indistinguishable from not having measured.
- **The review session is postponed and the change is declared done without its numbers** → the
  session is a task in `tasks.md` and an item in the DoD. C18b is the precedent.
- **Reviewing without a written criterion** → D4 is a spec requirement with a UI consequence, not a
  convention.
- **Single reviewer, who also designed the sampling** → declared, exactly as §15 limitation 4 declares
  the single annotator of the golden set.
- **60 per stratum is a coarse instrument** → a 95 % interval of roughly ±0,12 on a rate of 0,35.
  Enough to separate B from C if the effect is large, which is the hypothesis; not enough for a fine
  interval. Declared rather than presented as precision.

## Migration Plan

**No database migration.** C08 reserved the columns and delivered them; this is verified, not assumed,
and the DoD carries it as a checked item.

Deployment is ordinary: new routes behind the existing administrator policy, one new frontend route.
Rollback is removing the routes and the page — no data written by this change is required by anything
else, and profiles left at `ReviewOrigin = Human` remain valid because status and origin are
independent by spec.

## Open Questions

| # | Question | Default if unanswered |
|---|---|---|
| 1 | Three new routes on `AiCatalogController`, or a dedicated controller? | **`AiCatalogController`**, for prefix and policy coherence with `family-review-metrics`. Split during apply if the file grows unmanageable, and record it |
| 2 | Which keys for approve / reject / next? | `A`, `R`, `J`/`K` or arrows, `Enter` to save — confirmed in the first real session, which is the proof the plan's card asks for |
| 3 | Seed in configuration or per request? | **Configuration**, overridable per request for tests, and declared in the report |
| 4 | How is the keyboard A/B obtained? | First ~40 items with the mouse, the rest with the keyboard, alternating strata. The learning effect favours the keyboard and is declared rather than controlled |
| 5 | Is `Presión Oro` a sellable ring wrongly rejected? | Settled by the inverted pass over the 32, which exists for this |
| 6 | If `hilo` and `perla` prove systematically missing, is the vocabulary widened? | **Not in this change.** Recorded as a finding, the way C18a's became `FIX1` |
