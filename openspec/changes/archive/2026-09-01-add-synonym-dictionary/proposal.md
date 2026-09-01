# add-synonym-dictionary (C20)

## Why

`ai.product_document.tsv` — a generated `to_tsvector('spanish', doc_text)` column with its GIN index — has been populated on all 1.168 live rows since C05, and nothing queries it. C21 will switch on the lexical branch that consumes it, and measured against that index it would answer **zero documents** to ordinary operator phrasings: `gargantilla dorada` 0, `collares de plata` 0, `criollas de oro` 1 of a possible 102. The vector branch does not cover the gap and, worse, does not abstain — it scores 1 correct hit out of 10 on `criollas de oro` while still returning ten candidates under the threshold, so the failure would reach the screen looking healthy.

Decision 4 of the review removed `SearchAliases` from the product profile because it was AI-generated text persisted per product. Its agreed replacement (design §7.4) is a curated domain dictionary applied **at query time, never at indexing time**. C20 builds that dictionary. It is painted 🟢 but it is the graph's plug: the only prerequisite C21 still lacks, and C21 blocks both C24 and C30.

## What Changes

- **A query-side synonym dictionary in two layers.** `enrichment/vocabularies.yaml` is read as the base equivalence classes and **is not modified** — it already carries `sortija→anillo`, `gargantilla→collar`, `plata de ley→plata` with the right direction and the right accents. A new query-only overlay, `retrieval/query_synonyms.yaml`, adds what must never enter the extraction contract.
- **Spanish stemmer artefacts become first-class dictionary content**, not an afterthought. Measured: `collar`→`'coll'` versus `collares`→`'collar'` reaches **140 documents against 1**; `baño`→`'bañ'` versus `bano`→`'ban'` leaves `bano de oro` at **0 against 38**. The stemmer folds acute accents but not `ñ`, so an operator typing without `ñ` on a till gets nothing.
- **`expand_query` is a pure function returning equivalence groups plus resolved terms** — never a rewritten string. Measured: a single widened `tsquery` pushes the three products literally named «Sortija» out of the top 10, because `ts_rank` stops rewarding the word the operator typed; RRF over the original and widened lists puts them back at 1, 2 and 3. C21 does the fusing, so C20 must not throw away what it fuses with.
- **A flag whose default lives in `Settings` and whose value travels through the orchestrator signature**, so C24 can sweep configurations in one process without restarting and without touching the frozen request schema.
- **Observe-only delivery**: a `stage=expand` structured log beside `stage=embed` and `stage=search`. Until C21 lands, the expansion is computed, logged and **not consumed**. This is declared, not disguised.
- **A measurement CLI and a versioned report** reproducing the dictionary's reach over the live index, which C24 reuses as the golden set's synonym category.
- **No breaking changes.** The observable behaviour of `POST /v1/retrieval/products` is identical before and after; only one log line is added.

## Capabilities

### New Capabilities

- `query-expansion`: query-time synonym expansion for the retrieval pipeline — two-layer dictionary (enrichment base plus query-only overlay), equivalence-group output with resolved vocabulary terms, surface-form emission, unknown-token pass-through, the enable flag, and the `stage=expand` observability contract. C21 inherits this capability; the endpoint's own behaviour stays in `vector-retrieval`.

### Modified Capabilities

- `ai-service-runtime`: adds `JPV_QUERY_EXPANSION_ENABLED` to the family of optional settings that MUST NOT block boot or `GET /health`, alongside `JPV_RETRIEVAL_DISTANCE_THRESHOLD`, and pins it in the canonical OpenAPI settings profile.

## Impact

**Affected code** — `ai-service/` only:

- New: `src/jbg_ai/retrieval/synonyms.py`, `src/jbg_ai/retrieval/query_synonyms.yaml`, the measurement CLI under `jbg_ai.retrieval`, `evals/results/` for its report, tests under `tests/retrieval/`.
- Modified: `src/jbg_ai/retrieval/orchestrator.py` (call, log stage, flag parameter), `src/jbg_ai/api/routers/retrieval.py` (passes the settings default), `src/jbg_ai/config/settings.py` (flag plus canonical pin), `ai-service/README.md` (environment table row).
- Read but **not modified**: `src/jbg_ai/enrichment/vocab.py` and `vocabularies.yaml`.

**Explicitly untouched**: `ai-service/openapi.json` (frozen contract — no new endpoint), `indexing/embeddings.py` and `indexing/source_text.py` (frozen since C11; no document is reindexed and `source_hash` cannot move), Alembic, EF Core, `backend/`, `frontend/`.

**No new dependency and no new PostgreSQL extension.** `unaccent` is available but not installed, and installing it would mean a migration that rewrites the generated `tsv` column and its GIN index; the `ñ` problem is solved in the overlay with three entries instead.

**Debt this change does not pay**: the per-request embedding client singleton and reverting `AiGateway:RetrievalTimeoutMs` from 2500 ms to 800 ms remain assigned to C21/C22 in `openspec/DEFERRED_TASKS.md`. C20 adds no provider call and no SQL query, so it neither worsens nor fixes that budget.

**Downstream**: unblocks C21 (hybrid search and RRF), and through it C24, C25 and C30. Zone conflict with C21 — both work in `src/jbg_ai/retrieval/` — so the two must not be open at the same time.

**Declared limitation**: the dictionary is curated against the corpus, not against observed demand. `public."ProductSearchEvents"` holds 31 rows and 12 distinct texts, all written by the developer and all in canonical vocabulary. This belongs in the README beside the golden set's absence of inter-annotator agreement.
