## 1. Baselines before touching anything

- [ ] 1.1 Record the Python baseline: `uv run pytest` from `ai-service/`, keeping the failing **test names**, not the count
- [ ] 1.2 Record the .NET baseline with `git stash push -u`, `dotnet test`, `git stash pop`, keeping the failing **test names**
- [ ] 1.3 Confirm the local index is the one the report measured: 1.168 documents with embeddings, `ai.pos_projection` empty, `ai.sync_checkpoint` holding only the `catalog` row

## 2. Injected sales clock (.NET, D7)

- [ ] 2.1 Add `SalesAsOf` (`DateTime?`, null = wall clock) to `IndexFeedOptions` and validate it at application start when present
- [ ] 2.2 Feed it in `IndexFeedService.LoadSalesAsync` as `SalesAsOf ?? _timeProvider.GetUtcNow().UtcDateTime` into the `now` parameter `GetSalesAggregatesAsync` already takes — `IndexFeedRepository` keeps its shape
- [ ] 2.3 Add `computedAsOf` to the POS availability page DTO and populate it with the instant actually used
- [ ] 2.4 Configure `IndexFeed:SalesAsOf` as `2026-08-23T23:59:59Z` in `appsettings` and document it in the backend README environment table
- [ ] 2.5 Tests: `SalesAggregates_WithConfiguredAsOf_CountWindowsAgainstIt`, `SalesAggregates_WithoutAsOf_FallBackToWallClock`, `PosAvailabilityPage_DeclaresComputedAsOf`
- [ ] 2.6 Confirm no EF Core migration was created and the catalog feed is untouched

## 3. POS feed client and projection repository (Python)

- [ ] 3.1 Type the POS feed items in `indexing/feed.py`: `PosUpsertItem`, `PosTombstoneItem` and `parse_pos_item`, over the existing `fetch_pos_page`
- [ ] 3.2 Carry `computed_as_of` through the parsed page
- [ ] 3.3 Add the `ai.pos_projection` repository: idempotent upsert on `(pos_id, product_id)` setting `refreshed_at`
- [ ] 3.4 Implement the `unassigned` tombstone as a **soft delete** (`is_assigned_hint = false`, `qty_bucket = '0'`), inserting the row when the pair is unknown — never `DELETE`
- [ ] 3.5 Tests: idempotency, bucket vocabulary rejected outside `0` / `1-2` / `3+`, soft delete keeps the row, tombstone for an unknown pair inserts it

## 4. POS drain, checkpoint and CLI (Python)

- [ ] 4.1 Orchestrate the drain with its own keyset cursor in `ai.sync_checkpoint` under `feed = 'pos-availability'`, recording `last_incremental_sync_at`, `last_full_sync_at`, `last_aggregate_hash` and `indexed_count`
- [ ] 4.2 Record per-batch failures in `ai.sync_failure` without aborting the remaining pages
- [ ] 4.3 Add `python -m jbg_ai.indexing sync-pos [--full]` with the same `backend/.env` load as `sync`, and counters on stdout
- [ ] 4.4 Document the cron recipe in `ai-service/README.md`
- [ ] 4.5 Tests: resume from cursor, `--full` ignores it, the `catalog` checkpoint row is never touched, no `/v1` route and no scheduler were added

## 5. Point-of-sale scope in retrieval (Python, D1 + D2)

- [ ] 5.1 Fix `TOKEN_POS_ID` in `ai-service/tests/support/settings.py` to a UUID and repair the dependent battery **before** the scope lands
- [ ] 5.2 Parse `principal.pos_id` to `UUID` in the orchestrator; a value that does not parse produces 422 and never an unscoped search
- [ ] 5.3 Add the scope CTE over `ai.pos_projection` (`pos_id = :pos AND is_assigned_hint`) to the three statements in `retrieval/search.py`, computing distance over the scoped subset — no forced index, no post-filtered approximate scan
- [ ] 5.4 Extend `ports.py` so hits carry what the demotion and the diagnostics need
- [ ] 5.5 Tests: candidates only from the assortment, soft-deleted rows out of scope, malformed `pos_id` rejected, and the scoped vector branch returns its full depth

## 6. Availability demotion (Python, D3)

- [ ] 6.1 Extend `demotion_rank` to `(price_ceiling, size, materials, out_of_stock)` as a **single** key, with stock last and binary on `qty_bucket == '0'`
- [ ] 6.2 Verify the existing stable block sort still preserves fusion order inside each block
- [ ] 6.3 Tests: `test_out_of_stock_product_is_penalised_not_removed`, out-of-stock still present in candidates, a typed constraint outranks stock, and `1-2` versus `3+` keeps the fused order

## 7. Freshness, guards and contract (Python, D5 + D6)

- [ ] 7.1 Read `last_incremental_sync_at` for `feed = 'pos-availability'` through a 10-second cache — never `max(refreshed_at)`
- [ ] 7.2 Add optional `projection_age_seconds` to `RetrievalResponse`
- [ ] 7.3 Guard: empty projection for the token's point of sale → 503 naming the cause, never a 200 with an empty list; `GET /health` stays 200
- [ ] 7.4 Guard: age above the ceiling → hard filter not applied for that request, warning logged, age still reported
- [ ] 7.5 Regenerate `ai-service/openapi.json` with the README one-liner and update the snapshot test
- [ ] 7.6 Tests: freshness from the checkpoint and not from the rows, 503 on empty, degradation on stale, and the committed contract contains the new field

## 8. Configuration and observability (Python, D10)

- [ ] 8.1 Add `JPV_POS_PREFILTER_ENABLED` (default true) and `JPV_POS_PROJECTION_MAX_AGE_SECONDS` (default 3600) to `Settings`, pinned in `canonical_openapi_settings`
- [ ] 8.2 Pass both as parameters of `retrieve_products`, in the C20/C21 pattern, without moving the frozen request schema
- [ ] 8.3 Log `stage=projection` with `trace_id`, projection age, scope size and whether the filter was applied; extend `stage=search` with the scoped cardinality
- [ ] 8.4 Add the two settings to the `ai-service/README.md` environment table
- [ ] 8.5 Tests: disabled flag restores pre-change behaviour, a sweep overrides the default without restarting, and no vector reaches the logs

## 9. Measurement and report

- [ ] 9.1 Run `sync-pos --full` against the real feed and record rows written, pages drained and duration
- [ ] 9.2 Compare `ai.pos_projection` against the POS feed `aggregateHash` and record the drift
- [ ] 9.3 Measure the fill rate per point of sale, before and after, and record the non-zero rate of `sales_30d` once the reference instant is applied
- [ ] 9.4 Write the versioned report under `Documentos/Proyecto Final AIEng/informes/` for C24 to reuse

## 10. Closing

- [ ] 10.1 `uv run pytest` and `dotnet test` compared against the task 1 baselines **by test name**
- [ ] 10.2 Confirm no diff in `indexing/embeddings.py`, `enrichment/vocabularies.yaml` and the `frontend/` tree; no Alembic revision; no EF Core migration; `AiGateway:RetrievalTimeoutMs` still 2500 ms
- [ ] 10.3 `openspec validate --all --strict` reporting `0 failed`
- [ ] 10.4 Update `Documentos/epicas.md` EP14 from "en curso" to done, and add the fixed-horizon limitation to the README declarations list
