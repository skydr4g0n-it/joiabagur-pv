# add-pos-projection-soft-prefilter (C22)

## Why

A third cable was stripped and left unconnected. C05 created `ai.pos_projection` with its `qty_bucket` `CHECK` and its reverse index; C12 built and specified `GET /api/ai/index-feed/pos-availability`, page 200, keyset cursor, tombstones and bucketed quantities; C13 built the client that reads it — `fetch_pos_page`, `parse_pos_page` — and was **forbidden to consume it**. Three pieces that fit together, **zero rows written**.

The consequence is arithmetic and it is measured. The retriever spends its 60-candidate window on the whole catalogue, and `AssistedSearchRepository.Carried()` discards, at hydration time, everything the point of sale does not carry. Over 20 probe queries against the live index: **eight of the eleven points of sale have at least 6 of every 20 searches below a page of 10**. FORNELLS reaches **12 of 20**, with a worst case of **one single product**, and one MAO-AIR query leaves **zero** survivors — a blank page the C16 panel paints with its "we found nothing" screen, indistinguishable from a legitimate abstention. It is the same signature as C21's: a failure that reaches the operator looking healthy.

And a second clock is running out. The synthetic world of C10 ends on **2026-08-23** while the feed aggregates count against the wall clock, so `sales_30d` falls from **16,28 %** of non-zero pairs today to **1,32 %** on 22 September and to **zero** on the 26th. C25 would sweep weights over a dead signal, find the optimal rotation weight is 0, and write into the ablation table that business signals do not improve ranking — an artefact of the clock recorded as a finding.

## What Changes

- **`ai.pos_projection` is synchronised from the POS availability feed**: typed items over the existing `fetch_pos_page`, idempotent upsert on `(pos_id, product_id)`, its own keyset cursor in `ai.sync_checkpoint` under `feed = 'pos-availability'`, and a CLI `python -m jbg_ai.indexing sync-pos` with a documented cron. **No new HTTP route** — `ai-service-api-contracts` enumerates the endpoints in a MUST — and **no in-process scheduler**.
- **The `unassigned` tombstone is applied as a soft delete** (`is_assigned_hint = false`, `qty_bucket = '0'`), never a `DELETE`. **BREAKING relative to the ficha's implicit reading**: `IndexFeedService.MapPosItem` hardcodes `IsAssignedHint = true` on every upsert and routes inactive rows to tombstones, so the field is today a constant and the ficha's `test_unassigned_product_is_penalised_not_removed` cannot be satisfied at all. The soft delete is what makes the field reachable, and it is what will later let C26 tell "never carried here" from "no longer carried".
- **The point-of-sale scope becomes the retriever's only hard filter**, taken from the token's `pos_id` claim and applied in SQL to all three branches. **BREAKING relative to the ficha**, which asks for row existence: the authority's own exclusion predicate is `Inventory.IsActive`, so filtering on `is_assigned_hint` excludes exactly what `Carried()` excludes anyway, while row existence would spend **7-9 %** of the window — 65 rows at CIU-CENTRE, 40 at MAO-AIR, 23 at FORNELLS — on candidates .NET is certain to drop.
- **What degrades without excluding is stock**, which is where the ficha is exactly right: `Carried()` does not filter by quantity, so a zero-stock product reaches the operator today marked `HasStock: false`. `qty_bucket = '0'` becomes one more block of `demotion_rank` — single sort key, binary, lowest priority. The signal is coarse and real: **MAO-AIR holds 143 of its 416 assigned products at zero**, 34,4 %.
- **The scoped vector branch uses a scope CTE plus exact distance over the subset.** Measured, this is not an engine change: since C14 the planner has chosen a sequential exact scan — 8,2 ms unscoped, 10,8 ms in the live shape, **7,3 ms scoped** — and **the HNSW index has never been used on the live path**. Forcing it costs **113,7 ms** and returns **40 of the 60 requested rows**, which is `ef_search = 40` truncating: S10's post-filter trap, real and reproducible here, simply not on the live path.
- **`projection_age_seconds` is added to `RetrievalResponse`** and governs behaviour rather than decorating: an empty projection for that `pos_id` is **503** (*refusing to abstain over an empty projection*), a projection older than a configured ceiling **disables the hard filter for that request and declares it**, and a fresh one applies it. Its source is `ai.sync_checkpoint.last_incremental_sync_at`, **never** `max(refreshed_at)`: the feed is incremental, so `refreshed_at` measures when an assignment last changed, not when it was last looked at, and would report months on a projection synchronised seconds ago.
- **A `pos_id` that does not parse as a UUID is rejected**, never silently unscoped. The auth module already wrote the rule: *«a wildcard `pos_id` is exactly what must never exist, because from the soft-prefilter change onward that claim is the retriever's only hard filter»*.
- **The sales windows are counted against a declared reference instant** — `IndexFeed:SalesAsOf = 2026-08-23T23:59:59Z`, absent meaning today's wall-clock behaviour — with `computedAsOf` travelling on the feed page and persisted alongside the projection. This is not a workaround for a dataset with an end: C24 requires `test_run_is_reproducible_for_same_config_and_seed` and the delivery checklist requires an ablation table reproducible with one command, so a ranking that reads `now()` **was already irreproducible by design**. The fixed horizon only makes it urgent.
- **An ablation flag**, default in `Settings` and effective value as a parameter of the orchestration call, in the pattern C20 and C21 established, so C24 can sweep configurations without restarting and without moving the frozen request schema.
- **BREAKING: `ai-service/openapi.json` is regenerated**, for the first time since C13, by one optional response field. Backward compatible for the .NET deserialiser; the snapshot test exists precisely to force the act to be deliberate.
- **No migration of any kind**, Alembic or EF Core. `ai.pos_projection` exists since C05 and `ai.sync_checkpoint` already has `feed` as its primary key.

## Capabilities

### New Capabilities
- `pos-projection`: synchronisation of `ai.pos_projection` from the POS availability feed and its use as the retriever's point-of-sale scope — soft-deleting tombstone, `is_assigned_hint` as the only hard filter, availability as a demotion that never excludes, freshness reported from the checkpoint and governing degradation, and the ablation flag.

### Modified Capabilities
- `vector-retrieval`: the scenario asserting «the search SQL does not filter by `pos_id`» becomes false, and the branch statements gain the scope. Over-retrieval, the distance threshold and the body filters are unchanged.
- `product-document-indexer`: the prohibition «MUST NOT invoke the POS availability feed and MUST NOT write `ai.pos_projection`» was C13's scope boundary and is now false. Narrowed to what stays true: the catalog indexer still does not, and `indexing/embeddings.py` stays frozen.
- `index-feed`: `sales30d` / `sales90d` stop being counted «over the last 30 and 90 days» of wall clock and are counted over the 30 and 90 days preceding a declared reference instant, reported as `computedAsOf`. Bucketing, sparseness, the 200-item cap, keyset cursor, tombstones and API-key authentication are unchanged.

## Impact

**Code.** `ai-service/src/jbg_ai/indexing/` (typed POS feed items, projection repository, sync orchestration, checkpoint, `sync-pos` CLI) · `ai-service/src/jbg_ai/retrieval/` (`search.py` scope CTE in three statements, `ports.py`, `filters.py` stock block, `orchestrator.py` freshness, guards and flag) · `ai-service/src/jbg_ai/api/` (`schemas/retrieval.py`, `routers/retrieval.py`) · `ai-service/src/jbg_ai/config/settings.py` · `ai-service/openapi.json` · `backend/src/JoiabagurPV.Application` (`IndexFeedOptions.SalesAsOf`, `IndexFeedService.LoadSalesAsync`, POS page DTO) · `backend/src/JoiabagurPV.Infrastructure` (`IndexFeedRepository` receives the reference instant through the `now` parameter it already takes).

**Contracts.** `ai-service/openapi.json` moves by one optional response field; the POS feed page gains an optional `computedAsOf`. No .NET REST contract changes shape.

**Data.** `ai.pos_projection` goes from empty to populated; `ai.sync_checkpoint` gains its `pos-availability` row. No schema change.

**Not touched.** `frontend/`, `terraform/`, `.github/workflows/`, `indexing/embeddings.py` (frozen since C11), `enrichment/vocabularies.yaml`, `AiGateway:RetrievalTimeoutMs` (still 2500 ms), the catalog feed and its checkpoint.

**Downstream.** Unblocks C25 (business-signals ranking, which reads the `sales_*` columns this change persists but does not use) and C26 (substitutes, which needs the soft-deleted rows). The golden set of C24 is labelled **unscoped**; the effect of this change is reported separately as fill rate per point of sale.

**Documentation.** `Documentos/epicas.md` EP14 (done at open), the fill-rate report under `Documentos/Proyecto Final AIEng/informes/`, and a new README limitation: the synthetic world has a fixed horizon and sales windows are counted against a declared reference instant, so rotation metrics describe the world **at its horizon**, not "today".
