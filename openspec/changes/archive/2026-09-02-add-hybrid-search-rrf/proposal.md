# add-hybrid-search-rrf (C21)

## Why

Two cables have been stripped and left unconnected. `ai.product_document.tsv` — a generated `to_tsvector('spanish', doc_text)` column with its GIN index — has been populated on all 1.168 live rows since C05 and **nothing queries it**. C20 built the query expansion dictionary, and its result is computed, logged as `stage=expand` and **read by nobody**. C21 connects both.

The problem it solves is measured, not supposed. Serving from the vector branch alone, the retriever scores **67 of 120** correct hits in the top ten over twelve operator queries: `sortija de plata` returns *Pulsera Río de Plata* first and scores 4/10, `criollas de oro` scores 1/10, `dije de plata` scores **0/10**. And it fails without abstaining — the 0.65 distance threshold sits above the median distance and passes **1.168 of 1.168** documents on ordinary queries, so the failure reaches the operator's screen looking healthy. It is the signature this project has been chasing since C17.

C21 is the first change in the C14→C20 chain the operator notices, and it is the graph's neck: it unblocks C24, C25 and C30 at once.

## What Changes

- **A lexical branch over `tsv`**, consuming C20's equivalence groups. Two ranked lists: the operator's typed query and the expanded one. The typed list must exist because the expanded one, on its own, does not place any of the nine products literally named «Sortija» in its top six.
- **RRF fusion of three ranked lists with per-list weights**, `k` and a **symmetric depth** coupled to `k`, all configurable. Measured: branch parity (`w_vector = 1.0`) is the **worst** fusion at 96/120 against 105/120, because the vector branch fills its quota whether or not it understands the query and therefore always votes at full strength.
- **Coordination ordering inside the lexical branch**: candidates by OR across groups, ordered by how many groups a document matches, then by `ts_rank`. **BREAKING relative to the ficha**, which specified strict conjunction: measured, `&&` between groups leaves **7 of the 10 real recorded queries at zero documents**, and OR-plus-coordination contains the conjunction's result and places it at the head, so it dominates it.
- **Coordination counts only the groups whose absence is evidence.** Fields covered at 11-19 % (`occasion_tags` 13 %, `style_tags` 11 %, `color_tags` 19 %) and `size_label` (45 %) contribute to `ts_rank` but cannot leapfrog the queue: `boda` matches 5 documents of 1.168, and without this rule those five would outrank 1.163 equally suitable ones. A useful consequence falls out for free — a mostly subjective query has almost no structural signal left to order by, so the vector branch decides by default, which is adaptive weighting without a second number to calibrate.
- **Rule-based structural filters that demote and never exclude.** Price ceiling, size and materials extracted from the query text reorder by stable blocks and never push a candidate out of the over-retrieval window. **BREAKING relative to the ficha and design §7.3**, which specified `materials && ARRAY[...]` by default and `@>` for multi-material queries: measured, `@>` reaches **60 documents against 913**, and 126 documents (10.8 %) carry no extracted materials at all, so a hard `&&` would delete 36 rings from every silver-ring query.
- **No exact-match anchor for SKU or product name.** **BREAKING relative to the ficha**, which specified a boost: measured, an exact name already heads both lexical lists on its own, and for an exact SKU the vector branch returns **zero** candidates, so a one-element list has nothing to lose against.
- **`match_reasons` reports real provenance** per result instead of the literal `["vector"]`, `debug.lexical_score` is populated, and `score` becomes the RRF score normalised to the first result. `mode` stops lying: `vector`, `lexical` and `hybrid` do what they say and the `vector_only_until_c21` note disappears.
- **Honest degradation.** If the embedding provider fails in `mode=hybrid`, the lexical branch is served with 200 and `match_reasons: ["lexical"]`, and the panel's origin badge says so per result. If the lexical branch produces nothing either, **503** — a 200 with an empty list would be indistinguishable from a legitimate abstention.
- **`low_confidence` becomes the absence of cross-branch consensus**, as a signal only: it does not change when results are returned.
- **The embedding client becomes a process singleton with a bounded injected cache**, paying half the debt recorded in `openspec/DEFERRED_TASKS.md`. It is not the "three lines in `main.py`" the note describes: `InMemoryEmbeddingCache` is a `dict` with no ceiling and no TTL, harmless per request and a lifetime leak as a singleton inside a container capped at 512 MiB that already uses 232.
- **No contract movement.** `ai-service/openapi.json` is not regenerated, `backend/` is untouched, there is no Alembic revision and no EF Core migration. Everything new fits in fields that have existed since C02.

## Capabilities

### New Capabilities

- `hybrid-fusion`: fusion of several ranked lists by rank with configurable per-list weights and a shared depth coupled to the smoothing constant; provenance per candidate; absence of cross-branch consensus as a signal; safe composition of the lexical query from equivalence groups with terms always parameterised; coordination restricted to fields whose absence is evidence; and rule-extracted structural filters that demote and never exclude. It is a capability and not an endpoint detail because C23 (knowledge corpus), C25 (business signals) and C26 (substitutes) will fuse ranked lists **without going through `POST /v1/retrieval/products`**.

### Modified Capabilities

- `vector-retrieval`: hybrid and lexical modes stop running the vector branch and the `vector_only_until_c21` note is removed; over-retrieval gains a per-branch depth distinct from the returned window; `score` stops being `clamp(1 − cosine_distance)`; a provider failure in hybrid mode is no longer always 503; the prohibition on price becomes "must not **exclude** by price or stock" rather than "must not filter"; stage logs gain `stage=lexical`, `stage=filters` and `stage=fuse`.
- `query-expansion`: the requirements stating that the expansion result must not alter the retrieval response and is not consumed until the lexical branch exists are removed — the lexical branch now exists and consumes it.
- `ai-service-runtime`: the fusion settings (smoothing constant, per-list weights, branch depth) join `JPV_QUERY_EXPANSION_ENABLED` and `JPV_RETRIEVAL_DISTANCE_THRESHOLD` as optional-at-boot configuration pinned in the canonical OpenAPI profile.
- `assisted-search-panel`: the origin badge stops being a single decision for the whole response driven by `aiAvailable` and becomes a per-result decision driven by that result's match reasons, so a result served only by the lexical branch is never labelled a semantic match.

## Impact

**`ai-service/`** — new `retrieval/lexical.py`, `retrieval/fusion.py` and `retrieval/filters.py`; `retrieval/ports.py`, `retrieval/search.py`, `retrieval/orchestrator.py` and `retrieval/measure.py` modified; `api/main.py` gains the embedding singleton and `api/routers/retrieval.py` resolves it instead of building one per request; `config/settings.py` gains the fusion parameters; tests under `tests/retrieval/`; a versioned report under `evals/results/`; README environment table.

**`frontend/`** — `components/sales/assisted-search-result-row.tsx` derives the origin badge per result from `matchReasons`, plus its component test. No .NET work: `MatchReasons` already travels from `AssistedSearchService` to the DTO and to `ai-search.types.ts`.

**Not touched** — `backend/`, `ai-service/openapi.json`, `indexing/embeddings.py` (frozen since C11), `enrichment/vocabularies.yaml`, Alembic, EF Core, `terraform/`.

**Debt** — `openspec/DEFERRED_TASKS.md`: the embedding singleton is paid here; reverting `AiGateway:RetrievalTimeoutMs` from 2500 to 800 ms stays open, because it requires a demo deploy, a cold and warm re-measurement and a funnel confirmation, which is a different kind of work and a different risk.

**Declared and not fixed** — the distance threshold does not discriminate between plausible queries; cutting for real would need a per-query quantile rather than a constant, which is what C25's ficha already asks for.
