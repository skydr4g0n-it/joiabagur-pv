## Why

C18a created 156 families and 486 memberships in a single batch, and **nobody has looked at any of them**: all 156 record assisted approval by the administrator who fired the batch, none records a judgement about that particular family, and there are zero manually created families to compare against. The delivery checklist asks for human-review metrics — correction rate and average review time — and today there is no evidence behind that line at all, for families or for profiles.

Meanwhile the catalogue holds **682 active products belonging to no family**, 671 of them with a piece type, and the suggestion engine cannot see them: it converges by excluding products that already belong somewhere, so a product it failed to group the first time is invisible to it forever. The one signal that would surface those — a product that sits closer to an existing family than that family's own worst member — needs families to exist, which is why it was deferred to this change.

The review queue this change was originally meant to paint no longer exists. The fifteen flagged members lived only in a suggestion response that was never persisted, and the products they name now belong to families and are excluded from every subsequent run. Painting that queue is not possible; recomputing it over the families that exist is, and it is the same computation.

## What Changes

- **Audit of persisted families.** A new operation reports, over the families that actually exist, which members the vectors do not support — a product of another family sits closer than the member's own worst sibling — and which unassigned products look like they belong to one. Both are the same comparison read from opposite sides of the membership line, so they are computed together and returned together.
- **Orphan nomination by relative margin, never by an absolute threshold.** Measured over the corpus, nominating by neighbourhood purity fires overwhelmingly on the synthetic near-duplicates that were built to be distinct families; nominating by margin relative to the target family's own cohesion fires almost entirely on real catalogue gaps. Purity is kept as a ranking signal only.
- **Human verdicts become persistent.** A judgement about a `(product, family)` pair is recorded with its author, its instant and the margin at the time, so a dismissed orphan never returns and a confirmed member is a fact rather than a side effect of a batch. The same record is the per-item approval stamp that batch approval could not give.
- **Families become listable and dissolvable.** There is no way to enumerate families today, and no way to delete one — dissolving a bad family currently leaves an empty shell behind.
- **BREAKING** — the frozen AI service contract moves from nine routes to ten, and its snapshot test is regenerated in this change, as C18a did for the ninth.
- **The grouping vocabulary gains one material synonym.** Three of the strongest orphan candidates were missed for the same reason: a finish the vocabulary does not name. Because grouping reads the product name and not the stored attributes, the synonym recovers those families without re-enriching anything.
- **A review surface in the administration UI**, built as the first tenant of a shell that the profile-review change will reuse: only what that change already specifies in writing is generalised, nothing anticipated.
- **An unavailable audit is never painted as a clean catalogue.** Each list reports whether it was computed and came back empty or could not be computed at all, and the review of existing families — which needs no vectors — stays usable while the audit does not. On a catalogue-quality screen, "nothing to review" reads as "nothing is wrong", which is the conclusion this change exists to support with evidence rather than to assert by accident.
- **A judgement can be enacted, a label can be corrected, and the review is timed.** Recording a verdict does not move a membership, so the screen reports which decisions the catalogue has not acted on and lets the reviewer apply them; a member already in a family can have its variant label corrected; and the time spent per judgement is persisted rather than held in the page, because an average that dies with the tab is not evidence. Which population a judgement came from is captured when it is made, since a rejected member that was removed is indistinguishable from a rejected candidate afterwards.
- Not included: widening the closed piece-type vocabulary and its prompt version, re-enriching any product, and persisting suggestions.

## Capabilities

### New Capabilities

- `family-review`: human review of families that already exist — the audit that recomputes unsupported memberships over persisted families and nominates unassigned products as candidates, the persisted verdict on a `(product, family)` pair that is at once the dismissal record and the per-item approval stamp, the restriction of all of it to administrators, the requirement that auditing reads without writing, the requirement that a list which could not be computed is never presented as a list that came back empty, the gap between a judgement and the membership change it implies, correcting a member's label after the fact, and the per-judgement review time the delivery figures are computed from.

### Modified Capabilities

- `product-family`: families become enumerable through a paginated, filterable listing, and a family can be dissolved outright rather than only emptied — with its members freed, its review verdicts removed with it, and the catalogue watermark of the departing products stamped so an incremental index pull sees them.
- `ai-service-api-contracts`: the contracted surface gains the audit route, taking it to ten.
- `ai-gateway-client`: the .NET client gains the method that calls it, following the established rule that an endpoint is added by the change that first calls it.

## Impact

- **`ai-service/`** — `jbg_ai/families/` extends to persisted memberships, reusing the relative veto with a different universe and computing similarities in the database rather than loading vectors; a new router and its schemas; one new setting for the orphan margin; one synonym in the enrichment vocabulary; `openapi.json` and its drift test regenerated.
- **`backend/`** — a new entity and the **seventh migration of the project plan**, viable now that the branch competing for that turn was cancelled; two new routes on the families controller and two on the AI catalogue controller; writes continue to go through the existing family service so the index watermark stays coherent in both directions.
- **`frontend/`** — a new administrator route and review surface, its service and types, reusing the existing table and layout components.
- **Corpus** — only families the reviewer actually changes move it; confirming without editing writes a verdict and moves nothing. Even so the change lands before the evaluation baseline, because the preprocessing identifier would not reveal the difference.
- **Documentation** — the plan's card for this change, the epic, the data model, and a versioned report carrying the grouper's correction rate and average review time.
- **Not touched** — infrastructure and deployment workflows, the embedding client, the source-text template, the closed piece-type vocabulary, and the transactional schema by SQL from Python.
