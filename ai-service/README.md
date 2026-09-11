# jbg-ai

Python FastAPI microservice for the JoiaBagur Proyecto Final RAG.

- **C01** (HU-AIENG-001) shipped the runnable skeleton: settings, public health, structured `trace_id` logging, container and Compose wiring.
- **C02** (HU-AIENG-002) freezes the HTTP contract: eight `/v1` endpoints with complete Pydantic models, an internal HS256 service token, deterministic stubs, and a versioned `openapi.json`. **C18a made it nine** — the first and so far only addition since the freeze.
- **C05** (HU-AIENG-005) adds the persistence foundation: `vector` extension, schema `ai`, a dedicated database role, Alembic migrations and six empty index tables with their indexes. No data, no queries — see [Database and migrations](#database-and-migrations).
- **C08** (HU-AIENG-008) **renegotiates the enrichment contract** and opens catalog-wide auth. `POST /v1/enrich/products` now returns `source` (`rule` | `inferred`) on every proposed value, plus `piece_type`, `stone_type`, `size_label`, tags split into `color_tags` / `style_tags` / `occasion_tags`, and `prompt_version` on the response. Without per-field provenance the .NET side cannot tell a value a rule produced from one a model inferred, which is the whole of its hybrid review policy. Catalog-wide routes (`/v1/enrich/*`) authenticate through `get_catalog_principal`, which does **not** require `pos_id`; retrieval, assistance and inventory keep requiring it, and a token without it is still rejected there with 401.
- **C06a** (HU-AIENG-006a) ships the real-catalog corpus **outside this service**: offline scripts in `scripts/catalog/`, JSONL in `data/catalog/real/generated/`. No LLM client, no Alembic `text_provenance`, no writes to `public` from `jbg-ai`.
- **C06b** (HU-AIENG-006b) adds the **CLI** `python -m jbg_ai.data` (`generate` / `ingest`) under `jbg_ai.data`. `api.main` does not import it. Generate reads `JPV_CATALOG_LLM_API_KEY` from `backend/.env` (host only; not the RAG key). `GET /health` does not need it. See [`src/jbg_ai/data/README.md`](src/jbg_ai/data/README.md).
- **C09** (HU-AIENG-009) replaces the enrichment stub when `STUB_MODE=false`: closed vocabularies, size regex on `Name` then `Description` (never SKU), LiteLLM at temperature 0 (`JPV_RAG_LLM_*`), confidence by evidence span, `prompt_version = enrichment/v2` since FIX1 (`enrichment/v1` for the 1.178 profiles C09 produced). Batch quality gates live in an auditor, not as HTTP 422. Compose and the OpenAPI snapshot stay on `STUB_MODE=true` until a RAG key exists. See [`prompts/enrichment/v2.md`](prompts/enrichment/v2.md) and the superseded [`v1.md`](prompts/enrichment/v1.md), kept unmodified.
- **C10** (HU-AIENG-010) adds nested CLI `python -m jbg_ai.data world simulate|ingest` under `jbg_ai.data.world`. Simulate is offline (YAML of 12 POS, no Postgres, no LLM). Ingest uses `JPV_PG*` against local Docker and does not touch `"Products"` / `"Collections"` / schema `ai`. Recipe: [`../data/world/pos-profiles.yaml`](../data/world/pos-profiles.yaml). See [`src/jbg_ai/data/README.md`](src/jbg_ai/data/README.md).
- **C11** (HU-AIENG-011) adds the library `jbg_ai.indexing`: canonical `source-text/v1` (`build_source_text` / `hash_source_text`) and an injectable LiteLLM embedding client (`aembedding`, 1536-d, in-memory cache, batch 64). `api.main` does not import it. `JPV_EMBEDDING_*` are optional at boot; embedding requires its own key and does not fall back to `JPV_RAG_LLM_API_KEY`.
- **C13** (HU-AIENG-013) replaces the `/v1/index/*` stub when `STUB_MODE=false`: catalog feed pull (`X-Index-Feed-Key`, keyset `since`/`since_id`), committed `src/jbg_ai/indexing/sku_provenance.json`, skip-embed upsert, tombstones, checkpoint, CLI `python -m jbg_ai.indexing sync [--full]`. Auth is `get_catalog_principal` (no `pos_id`). The POS feed method exists on the client and is **not** called. `indexing/embeddings.py` is not edited. OpenAPI adds `since_id` / `cursor_id`.
- **C14** (HU-AIENG-014) replaces the `/v1/retrieval/products` stub when `STUB_MODE=false`: query embed with the C11 `LiteLlmEmbeddingClient` (`max_attempts=1`; `indexing/embeddings.py` unchanged), cosine `<=>` over HNSW, distance threshold `JPV_RETRIEVAL_DISTANCE_THRESHOLD` (default 0.65), overfetch after the threshold. `mode=hybrid`/`lexical` run the vector branch until C21. Missing key, `DATABASE_URL` or compatible index → 503, not 501. Substitutes stay 501 (C26). OpenAPI snapshot is not regenerated.

- **C18a** (HU-AIENG-018a) adds the library `jbg_ai.families` and the **ninth** `/v1` route, `POST /v1/families/suggest` — the first addition since C02 froze the surface, so `openapi.json` was regenerated in the same change. Grouping is deterministic and offline: no LLM, no embedding provider call, no SQL against schema `public`. The name root groups and the embedding **vetoes**, relative to the other proposed families rather than by any absolute cutoff (`JPV_FAMILY_VETO_MARGIN`), and a vetoed member is **marked for review, never removed**. Vocabularies are reused from `enrichment/vocabularies.yaml`, not redeclared. The route proposes and writes nothing; approving is .NET's, through `ProductFamilyService`.
- **C18b** (HU-AIENG-018b) adds `POST /v1/families/audit`, the **tenth** `/v1` route, and regenerates `openapi.json` in the same change as C18a did for the ninth. It audits the families that **already exist** rather than proposing new ones: it reports members the vectors do not support — a product of another family sits closer than the member's own worst sibling — and, in the same call, unassigned products that look like they belong to one. The two are the same comparison read from opposite sides of the membership line, which is why there is one route and not two. Orphans are nominated by **margin relative to the target family's own cohesion** (`JPV_FAMILY_ORPHAN_MARGIN`), never by an absolute cutoff: measured over the corpus, neighbourhood purity fires overwhelmingly on synthetic near-duplicates built to be distinct families, while relative margin fires almost entirely on real catalogue gaps — so purity is kept as a **ranking signal only**. The relative veto is reused from C18a with a different universe (persisted families instead of proposed ones), not reimplemented. Like every route here it reads **only `ai.product_document`** and never schema `public`, so the memberships it audits are the ones the index projection holds as of the last sync. It writes nothing: the verdict is .NET's, in `FamilyReviewVerdict`.
- **C20** (HU-AIENG-020) adds the library `jbg_ai.retrieval.synonyms`: query-side synonym expansion for the lexical branch C21 will build. Two layers — `enrichment/vocabularies.yaml` supplies the base equivalence classes and is **never modified from here**, because touching it forces a prompt bump and re-enrichment; `retrieval/query_synonyms.yaml` overlays what must not enter the extraction contract. That includes **Spanish stemmer artefacts**, which are first-class content and not a footnote: `collar` and `collares` stem to different lexemes and reach 140 documents against 1, and the stemmer folds acute accents but **not** `ñ`, so `bano de oro` reached 0 against 38. `expand_query` is a **pure function** returning **equivalence groups plus resolved terms** — never a rewritten string, because a single widened `tsquery` was measured to push the three products literally named «Sortija» out of the top ten, while RRF over the original and expanded lists puts them back at 1-2-3. Bridges between vocabularies are **directional**: the colour `dorado` reaches solid `oro`, but a query for `baño de oro` does not, because a symmetric union dragged 282 solid-gold pieces averaging 587 EUR into a query for plating averaging 420 EUR. The flag `JPV_QUERY_EXPANSION_ENABLED` supplies only the default; the value travels by parameter so C24 can sweep configurations in one process. **Observe-only**: a `stage=expand` log is emitted and the result is **not consumed** until C21, which is declared rather than disguised — the response of `POST /v1/retrieval/products` is unchanged. No migration, no new extension, no document re-indexed, `openapi.json` untouched.

- **C21** (HU-AIENG-021) connects the two cables C05 and C20 left stripped: `ai.product_document.tsv` had been populated on every live row since C05 and **nothing queried it**, and C20's expansion was computed, logged and read by nobody. `POST /v1/retrieval/products` now fuses **three ranked lists** — the operator's typed text (`websearch_to_tsquery`), C20's equivalence groups (`plainto_tsquery` per surface form, never `phraseto`: adjacency leaves `aro de dedo` at 0 documents against 6) and the vector branch — with **weighted RRF** (`retrieval/fusion.py`, pure and domain-free so C23, C25 and C26 can import it) at a **symmetric depth** coupled to `k`. Serving from the vector branch alone scored **67 of 120** over twelve operator queries; `dije de plata` scored **0/10**. Four measured decisions govern the shape. Groups are **OR-ed, not conjoined** — strict `&&` leaves 7 of the 10 real recorded queries at zero documents — and ordered by **coordination**, which contains the conjunction's result at the head of the list. Coordination counts **only fields whose absence is evidence**: `occasion_tags` (13 %), `style_tags` (11 %), `color_tags` (19 %) and `size_label` (45 %) score in `ts_rank` but may not jump the queue, which as a side effect leaves a mostly subjective query to the vector branch with no second number to calibrate. The vector list **weighs less** (0.33): branch parity is the worst fusion at 96/120 against 105/120, because the distance threshold passes essentially the whole corpus so that branch always votes at full strength. And structural constraints read from the text — a price ceiling, a size, materials — **demote and never exclude** (`retrieval/filters.py`), because `@>` reaches 60 documents where `&&` reaches 913 and 126 documents carry no extracted materials at all. `mode` stops lying (`lexical` makes no provider call, `vector` does not read `tsv`, the `vector_only_until_c21` note is gone), `match_reasons` reports **real provenance** per result, `low_confidence` becomes the absence of cross-branch consensus **but only when more than one branch ran** (with a single branch no candidate can appear twice, so the rule would mark every response and the field would inform of nothing; there it keeps C14's meaning of "nothing was returned"), a provider failure in `hybrid` degrades to the lexical branch with 200 instead of 503 — and to 503 only when there is nothing lexical to serve, since a 200 with an empty list is indistinguishable from a legitimate abstention. The retrieval embedding client becomes a **process singleton with a bounded LRU cache** injected through C11's existing constructor seam, paying half the debt in `openspec/DEFERRED_TASKS.md` without editing the frozen `indexing/embeddings.py`. `python -m jbg_ai.retrieval compare` writes the arm comparison to `evals/results/`. No migration, no `backend/` change, `openapi.json` untouched.

**Two behaviour changes C21 declares rather than hides.**

1. **`score` changes scale.** It is no longer `clamp(1 − cosine_distance)` but the fused RRF score normalised so the first result is 1.0 — still inside `[0, 1]` and still monotone with the order, which is what the frozen contract promises. The mapped cosine distance moves to `debug.vector_score`, and `debug.lexical_score` now carries `ts_rank`. C04's telemetry persists `score`, so **figures recorded before and after C21 are not comparable** and comparing them means nothing. Keeping the raw RRF score was rejected: values of 0,0001-0,03 persisted without meaning would look like a broken field.
2. **The distance threshold does not discriminate between plausible queries.** Measured on the live index, the cutoff passes **essentially the whole corpus** on an ordinary query and nothing at all on a nonsense control, so it is a floor and the branch depth is what actually bounds the vector list. C21 does not fix it: cutting for real needs a per-query quantile rather than a constant, which is what C25's ficha already claims. It is declared here so nobody reads the threshold as an abstention mechanism.

- **C23** (HU-AIENG-023) builds **the second index**. `ai.product_document` answers «enséñame anillos de plata» and cannot answer «¿este anillo se puede mojar?», because that answer lives in no product. C05 created `ai.knowledge_document` and `ai.knowledge_chunk` with their final shape and **nothing had ever written to them**; this change adds the content and the round trip to it. A corpus of **32 Markdown documents and 161 sections** in [`../data/knowledge/`](../data/knowledge/), one material sheet per canonical term of the enrichment vocabulary — a **derived, testable** invariant, so adding `titanio` to the vocabulary without its sheet fails a test. Every section declares its **`claim_scope`**, `general` (verifiable outside the jewellery) or `establecimiento` (a commitment of the house, **today illustrative**), and that mark travels with the retrieved fragment: a **minority** of the sections, the count sealed in `_corpus.meta.json` and reprinted by `python -m jbg_ai.knowledge stats`, are commitments, and the whole service block is one. **Zero `guion_venta` documents**, of the five the schema admits, and that is not a scope cut: an imperative fragment retrieved into a prompt is indistinguishable from an instruction, so the corpus would become an injection surface — the corpus keeps **facts to cite**, the prompt keeps **instructions to obey**. Chunking is one `##` section per chunk, no overlap, with both titles inside the indexed content, which is what tells nine structurally identical material sheets apart and comes free because `tsv` is a column generated over `content`. Identity is `uuid5` over the slugs and **never `(document_id, chunk_index)`**: inserting a section in the middle would shift every later index and silently repoint every later citation. The `citation_id` — `material-plata#cuidados-y-limpieza-en-casa` — resolves, **locates and opens the file and the heading in git**. Indexing is idempotent, skips embedding when the content hash and the version match, deletes what a run no longer produces, reuses the frozen `indexing/embeddings.py` untouched and writes a **version namespace of its own**, `knowledge/v1`: sharing `source-text/v1` would mean a change to the chunking rules invalidated nothing and left vectors declaring themselves current over text that no longer exists. Search is a **callable, not a route** — vector plus lexical fused by RRF through C21's module, with C20's expansion groups feeding the lexical branch — and the vector branch decides **whether there is an answer at all**: below `JPV_KNOWLEDGE_DISTANCE_THRESHOLD` it returns **nothing**, so C30 has nothing with which to invent an attribution. Both decisions were measured, not assumed — figures of the run of **2026-09-06**, reprintable with `python -m jbg_ai.knowledge measure --compare` and recorded in the C23 implementation report: over 32 fixture questions plus 5 out-of-domain ones the fused configuration beats vector-only by **+6,2 pp of Recall@3 and +0,042 of MRR**, and the threshold is calibrated at **0,51** against the production embedder on the live index — the questions with an answer reach at worst 0,5062 and the out-of-domain ones start at 0,5145, a clean gap, so the strictest value that loses none of the former is the one that abstains on all of the latter. `python -m jbg_ai.indexing sync-knowledge`. **No migration, no route, `openapi.json` byte-identical.**

Boundary rule: *Python computes similarity and writes prose; .NET computes numbers and decides.* The service never emits a price or stock figure and never touches schema `public`.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker / Docker Compose (optional, for the full local stack)

## Required environment

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `APP_ENV` | yes | — | e.g. `local`, `dev`, `prod` |
| `SERVICE_VERSION` | yes | — | echoed by `GET /health` |
| `JWT_SECRET` | yes | — | HS256 secret shared with the .NET API; ≥ 32 bytes |
| `LOG_LEVEL` | no | `INFO` | standard Python logging level |
| `JWT_TTL_SECONDS` | no | `300` | documented TTL; the .NET API is the issuer |
| `STUB_MODE` | no | `true` | serve deterministic fixtures instead of real logic |
| `ENABLE_DEV_ENDPOINTS` | no | `true` unless `APP_ENV` is `prod`/`production` | mounts `GET /v1/evals/runs` |
| `DATABASE_URL` | no | — | `postgresql+psycopg://…`; its absence does not stop the service booting |
| `DB_POOL_SIZE` | no | `5` | hard ceiling on simultaneous connections; no overflow |
| `JPV_CATALOG_LLM_API_KEY` | no | — | C06b `generate` only (host `backend/.env`). Distinct from `JPV_RAG_LLM_API_KEY`. Absence does not block `/health` |
| `JPV_CATALOG_LLM_MODEL` | no | — | optional; CLI default `gpt-4o` |
| `JPV_CATALOG_LLM_BASE_URL` | no | — | optional OpenAI-compatible proxy; empty = api.openai.com |
| `JPV_PG*` | no | — | Host CLI ingest only (C06b catalog, C10 world). `backend/.env`, port 5433. Absence does not block `/health` |
| `JPV_RAG_LLM_API_KEY` | no | — | C09 runtime enrichment (LiteLLM). Distinct from `JPV_CATALOG_LLM_API_KEY`. Absence does not block `/health`; real enrich requires it |
| `JPV_RAG_LLM_MODEL` | no | — | provider-prefixed id (e.g. `openai/gpt-4o`) |
| `JPV_RAG_LLM_BASE_URL` | no | — | optional LiteLLM `api_base`; empty = provider default |
| `JPV_RAG_LLM_CONCURRENCY` | no | `8` | in-flight enrichment calls inside a batch of ≤ 50 |
| `JPV_EMBEDDING_API_KEY` | no | — | C11 embeddings (LiteLLM). Distinct from `JPV_RAG_LLM_API_KEY`. Absence does not block `/health`; real `embed` requires it |
| `JPV_EMBEDDING_MODEL` | no | `openai/text-embedding-3-small` in code | provider-prefixed embedding model id |
| `JPV_EMBEDDING_BASE_URL` | no | — | optional LiteLLM `api_base`; empty = provider default |
| `JPV_EMBEDDING_BATCH_SIZE` | no | `64` | texts per provider embedding call |
| `JPV_INDEX_FEED_BASE_URL` | no | — | C13 catalog feed origin. Distinct from `JWT_SECRET`. Absence does not block `/health`; real sync requires it |
| `JPV_INDEX_FEED_API_KEY` | no | — | C13 `X-Index-Feed-Key`. Distinct from `JWT_SECRET` and `JPV_EMBEDDING_*`. Never falls back to `JWT_SECRET` |
| `JPV_INDEX_SYNC_TIME_BUDGET_SECONDS` | no | `180` | wall-clock budget for one catalog drain; blank → the default |
| `JPV_RETRIEVAL_DISTANCE_THRESHOLD` | no | `0.65` | C14 cosine-distance cutoff `(0, 2]`. Absence does not block `/health`; blank → the default. Distinct from `JPV_EMBEDDING_*` |
| `JPV_QUERY_EXPANSION_ENABLED` | no | `true` | C20 query-side synonym expansion. Supplies only the **default**: the effective value travels as a parameter of the retrieval orchestration call, so C24 can sweep configurations in one process without restarting and without moving the frozen `openapi.json`. Default on because, measured on the live index, the lexical branch answers **nothing at all** without it for ordinary surface-form variants of catalogue vocabulary. Turning it off is also the rollback for C20. Absence does not block `/health`, which never loads the dictionary |
| `JPV_RRF_K` | no | `60` | C21 smoothing constant of the reciprocal rank fusion; blank → the default. **Not independent of `JPV_BRANCH_DEPTH`**: `k` governs how slowly a document's vote decays as its rank grows, so a deeper branch keeps more of its tail voting and the two are swept together, never separately. Absence does not block `/health` |
| `JPV_RRF_WEIGHT_TYPED` | no | `0.5` | C21 weight of the lexical list built from the operator's own text. With `JPV_RRF_WEIGHT_EXPANDED` it sums to one, so disabling the expansion — which makes the two lexical lists identical — degrades to exactly one lexical list at full weight. Supplies only the **default**: the effective value travels as a parameter of the orchestration call, for C24 |
| `JPV_RRF_WEIGHT_EXPANDED` | no | `0.5` | C21 weight of the lexical list built from C20's equivalence groups. See `JPV_RRF_WEIGHT_TYPED` for why the two sum to one |
| `JPV_RRF_WEIGHT_VECTOR` | no | `0.33` | C21 weight of the vector list, deliberately **below** either lexical weight and the default easiest to undo by accident. Measured, giving the branches an equal say is the **worst** fused configuration of those tried: the threshold passes essentially the whole corpus, so the vector branch returns a full list whether or not it understood the query, and a branch that always fills its list always votes at full strength. Raising it back towards parity measurably sinks queries the lexical branch gets right. Swept figures in the C21 report |
| `JPV_BRANCH_DEPTH` | no | `60` | C21 depth at which **every** fused list is truncated before fusing; blank → the default. One value shared by all three: cutting the lexical branches deeper than the vector one was measured to cost accuracy rather than buy it. Conceptually distinct from the over-retrieval window the endpoint returns, which follows `top_k`, even where the two happen to share a default |
| `JPV_POS_PREFILTER_ENABLED` | no | `true` | C22 point-of-sale prefilter. Supplies only the **default**: the effective value travels as a parameter of the orchestration call, so C24 can sweep configurations in one process. Default on because, probed against the live index, **most** points of sale were left with a very short result page on a large share of ordinary searches once .NET had dropped what they do not carry — worst case **one** surviving product, and one query with **none**. Figures in the C22 report. Turning it off is the rollback for C22: retrieval returns to pre-change behaviour with no deploy, and `ai.pos_projection` can stay populated because nothing else reads it. Absence does not block `/health` |
| `JPV_POS_PROJECTION_MAX_AGE_SECONDS` | no | `3600` | C22 staleness ceiling of the projection. Above it the scope is **not** applied for that request, the degradation is logged and `projection_age_seconds` still reports the age: a stale projection may leave the page short, but it must never hide a valid product from the .NET authority that hydrates it. Deliberately generous — the sync cadence is a cron, so an hour degrades only under sustained failure and not under ordinary lateness; degrading eagerly would surrender the whole benefit of the change on any transient. Measured from `ai.sync_checkpoint.last_incremental_sync_at`, **never** from `ai.pos_projection.refreshed_at`, which records when an assignment last changed — the feed is incremental, so that column would report months on a projection synchronised seconds ago |
| `JPV_KNOWLEDGE_DISTANCE_THRESHOLD` | no | `0.51` | C23 cosine-distance cutoff of the knowledge corpus `(0, 2]`; blank → the default. **Separate from `JPV_RETRIEVAL_DISTANCE_THRESHOLD` on purpose**: that one was calibrated over much shorter product documents, and knowledge chunks are longer prose with another distance distribution. Below it the search returns **nothing** — for a question the corpus does not cover the correct answer is no citation, and C30 depends on that to have nothing with which to invent an attribution. **Calibrated, not chosen**, by a rule that outlives any one measurement: zero out-of-domain citations is a **constraint** and not a term to trade against recall; inside that band Recall@3 is maximised; and among the values that tie the **strictest** wins, which is the word the rule itself uses — being generous "to be safe" buys no recall at all and costs abstention. Re-run the sweep with `python -m jbg_ai.knowledge calibrate`; the figures of the last one are in the C23 implementation report. That sweep runs against the **offline stand-in embedder** the specification requires, so what it calibrates is the **rule**. The default here is what the same rule yields against the **production embedder on the live index**, and it is a different number rather than a rounding of it: the stand-in scores lexical overlap, its distances sit on another scale, and its own optimum lets through questions the corpus does not cover. Re-derive it against a populated index whenever the corpus, the chunking rules or the embedding model change. Supplies only the **default**: the effective value travels as a parameter of the call |
| `JPV_KNOWLEDGE_HYBRID_ENABLED` | no | `true` | C23 lexical branch of the knowledge search; blank → the default. Default on because it was **measured and not assumed**: over the fixture the fused configuration beats vector-only on **both** Recall@3 and MRR at no cost in abstention, and `python -m jbg_ai.knowledge measure --compare` reprints that comparison on demand. The branch exists for a reason specific to this corpus — nine material sheets are structurally identical, same skeleton, same register, same vocabulary, and the only thing telling them apart is the material's name, a short lexical token drowned in shared prose, so cosine collapses by homogeneity. The flag is what let that prediction be confirmed with a number instead of asserted, in the same pattern as `JPV_QUERY_EXPANSION_ENABLED`; turning it off degrades knowledge search to pure vector retrieval and is the rollback for the hybrid half of C23. Supplies only the **default**: the effective value travels as a parameter of the call |
| `JPV_FAMILY_VETO_MARGIN` | no | `0.05` | C18a relative-veto margin `[0, 1]`. **Never an absolute similarity cutoff**: a member is flagged for review, never removed, when a product of another proposed family beats its worst sibling by more than this. Absence does not block `/health` |
| `JPV_FAMILY_ORPHAN_MARGIN` | no | `0.0` | C18b orphan-nomination margin `[0, 1]`. An unassigned product is nominated when it beats the target family's **worst member** by more than this. Deliberately generous at `0.0`: it nominates, a person decides, and measured over the corpus it yields a queue one reviewer works through in a session. **Not a similarity cutoff** — the comparison is always against that family's own cohesion, so the same value behaves differently against a tight family and a broad one. Absence does not block `/health` |

Missing or blank `APP_ENV`, `SERVICE_VERSION` or `JWT_SECRET` aborts startup (fail-fast), so the process never serves `/v1` half-configured.

The **C20 synonym dictionary is curated against the corpus, not against observed demand**: `public."ProductSearchEvents"` holds 31 rows and 12 distinct texts, all written by the developer in canonical vocabulary, so there is no query distribution to draw on. Its reach is measured instead — `python -m jbg_ai.retrieval measure` writes `ai-service/evals/results/c20-query-expansion-reach.md` — and C24 re-measures it with graded relevance. This is a limitation of the same family as the golden set's absence of inter-annotator agreement, and is stated rather than mitigated.

`DATABASE_URL` is **optional on purpose**. The service must boot with no database — that is a requirement of `ai-service-dev-compose`, not an accident — so the engine is built on first use and never at import time. Under `STUB_MODE` nothing asks for a session, so the container starts fine against a database that has not even been provisioned. LLM keys are not required to boot `/health`; the catalog CLI reads `JPV_CATALOG_LLM_*` from `backend/.env`. **`python -m jbg_ai.indexing sync` reads that same file**, through `run_module` in `indexing/cli.py`: `backend/.env` is the single place the local credentials live and the one Compose interpolates, so no symlink and no `env_file:` are needed — the compose file rejects the latter on purpose, to keep host-only CLI keys out of the runtime process. The load happens in `run_module` and **not** in `main`, because tests call `main` directly and `support.settings.build_settings` pins the optional fields to `None` precisely so an exported credential cannot make an "absent configuration" case stop failing. That file carries credentials only: the three fail-fast settings of C02 — `APP_ENV`, `SERVICE_VERSION`, `JWT_SECRET` — still have to reach the process some other way, which is why the host invocation is a development aid and the container is the normal path. Real `POST /v1/enrich/products` (`STUB_MODE=false`) requires `JPV_RAG_LLM_API_KEY` and fails explicitly if it is missing — it does not invent profiles and does not return 501. Embedding (`jbg_ai.indexing`) requires `JPV_EMBEDDING_API_KEY` at call time and does not fall back to the RAG LLM key. Real `POST /v1/index/sync` requires `JPV_INDEX_FEED_BASE_URL`, `JPV_INDEX_FEED_API_KEY` and `JPV_EMBEDDING_API_KEY` (and the committed `sku_provenance.json`) and answers **503** naming the missing setting — never 501, and never `JWT_SECRET` as the feed key. Real `POST /v1/retrieval/products` requires `JPV_EMBEDDING_API_KEY` and `DATABASE_URL` (and a compatible index) and answers **503** naming the missing dependency — never 501, and never 200 with `low_confidence` for an empty compatible index. Real `POST /v1/families/suggest` requires `DATABASE_URL` and answers **503** naming it — it needs no provider key at all, because it reads vectors the index already holds and never embeds anything. `POST /v1/families/audit` behaves identically and for the same reason.

## Frozen endpoints (C02)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/health` | public | unchanged since C01 |
| `POST` | `/v1/retrieval/products` | Bearer | returns `min(top_k × 3, 60)` candidates, reported in `candidates_returned` |
| `POST` | `/v1/retrieval/substitutes` | Bearer | retrieval result shape plus `similarity_signals` |
| `POST` | `/v1/assist/sale` | Bearer | `groups[]` by `family_id`; `pitch` keeps `{{price}}` / `{{stock}}` unresolved |
| `POST` | `/v1/inventory/propose` | Bearer | prioritized proposals, never quantities |
| `POST` | `/v1/enrich/products` | Bearer | proposed profiles with per-field confidence |
| `POST` | `/v1/families/suggest` | Bearer (catalog) | family proposals plus the groups a guard refused and the products the gate excluded; writes nothing |
| `POST` | `/v1/families/audit` | Bearer (catalog) | unsupported memberships and orphan candidates over the families that already exist; writes nothing |
| `POST` | `/v1/index/sync` | Bearer (catalog) | keyset `since` / `since_id`; `batch_size` ignored |
| `GET` | `/v1/index/status` | Bearer (catalog) | set-hash drift vs one catalog GET |
| `GET` | `/v1/evals/runs` | Bearer | **development profile only** |

None of these is exposed through nginx: the SPA never talks to Python.

## Internal service token

The .NET API (C03) is the only issuer. Tokens are HS256, signed with `JWT_SECRET`, and must carry all four claims — names are frozen in `snake_case` on the wire:

| Claim | Meaning |
|---|---|
| `user_id` | acting user on the .NET side |
| `role` | `Admin` or `Operator` |
| `pos_id` | point-of-sale scope |
| `trace_id` | correlation id, preferred over the `X-Trace-Id` header |

Rules that C03 must rely on:

- **The token wins.** `pos_id` and `role` always come from the token. Requests may carry `pos_id` in the body for client compatibility; it is ignored, and a mismatch is neither an error nor a behavior change. Scoped responses echo the applied scope in `effective_pos_id`.
- Any missing, malformed, wrongly signed, expired or incomplete token gets a single opaque **401** that never says which check failed.
- `GET /health` is exempt.

## Stubs and 501

With `STUB_MODE=true` (the local and test default) every `/v1` route answers from deterministic fixtures: no LLM, no embeddings, no database, no clock. The same request always returns the same body, so the .NET client can assert its mapping against them.

With `STUB_MODE=false` a route whose real logic does not exist yet answers **501** naming the change that will deliver it (C24 evals, C26 substitutes, C30 assist, C35 inventory). `POST /v1/enrich/products` is C09: the real pipeline, or 503 if `JPV_RAG_LLM_API_KEY` is missing — never 501. `POST /v1/index/sync` and `GET /v1/index/status` are C13: the catalog drain, or 503 if feed/embed settings or `sku_provenance.json` are missing — never 501. `POST /v1/retrieval/products` is C14: the vector retriever, or 503 if `JPV_EMBEDDING_API_KEY`, `DATABASE_URL` or a compatible index is missing — never 501. Substitutes stay 501 until C26. Later changes replace remaining handlers one at a time; the contract frozen here is the one they must respect.

## Enrichment prompt versions

**The catalogue holds more than one.** `PROMPT_VERSION` in `enrichment/constants.py` names the
prompt in force, and `load_prompt()` derives its path from that constant — `prompts/<version>.md` —
so the two cannot drift and stamp a profile with a version that never produced it. Superseded
prompt files stay in the repository unmodified, because the profiles produced by them keep
declaring their version and that claim has to stay checkable.

Since FIX1 the corpus is mixed: **22 profiles on `enrichment/v2`** (the enumerated cohort of
`fix-enrichment-vocabulary-gaps`, whose `piece_type` the eight-term vocabulary could not name)
and **1.178 on `enrichment/v1`**.

**Consequence, and it is not optional: any aggregate metric over extracted attributes must be
reported per `PromptVersion`.** Coverage of `piece_type`, distribution of `materials`, share of
empty `style_tags` — an average across both populations is a number without a subject. This is the
same discipline C24 applies to `data_origin`, and the field exists precisely to make the difference
visible. Mixing `PromptVersion` is safe and traceable; mixing `embedding_version` is not, because
that compares two geometric spaces and returns a plausible number with no meaning.

## OpenAPI snapshot

`ai-service/openapi.json` is the published contract, and `test_openapi_snapshot_is_stable` fails whenever the live schema drifts from it. `docs_url` stays disabled: the artifact is the snapshot, not a browsable UI.

**Canonical profile.** The snapshot is generated with `canonical_openapi_settings()` — `APP_ENV=local`, `SERVICE_VERSION=0.1.0`, stubs on and development endpoints **enabled**, so `/v1/evals/runs` is part of the published contract. A production deployment would not serve that path; that asymmetry is deliberate. Pinning one profile in code is what keeps the snapshot deterministic and stops the test and the regeneration below from using different settings.

**Regenerating is a contract negotiation, not a chore.** A failing snapshot test means the frozen boundary moved — agree the change with whoever owns the .NET client before regenerating:

```bash
cd ai-service
uv run python -c "import json; from pathlib import Path; from jbg_ai.api.main import create_app; from jbg_ai.config import canonical_openapi_settings; Path('openapi.json').write_text(json.dumps(create_app(canonical_openapi_settings()).openapi(), indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')"
```

On PowerShell, wrap the same one-liner in single quotes:

```powershell
cd ai-service
uv run python -c 'import json; from pathlib import Path; from jbg_ai.api.main import create_app; from jbg_ai.config import canonical_openapi_settings; Path("openapi.json").write_text(json.dumps(create_app(canonical_openapi_settings()).openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")'
```

## Run locally with uv

```bash
cd ai-service
uv sync --system-certs   # use --system-certs only if TLS to PyPI fails
export APP_ENV=local
export SERVICE_VERSION=0.1.0
export JWT_SECRET=local-dev-jwt-secret-0123456789abcdef
uv run uvicorn jbg_ai.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

On PowerShell:

```powershell
cd ai-service
uv sync --system-certs
$env:APP_ENV = "local"
$env:SERVICE_VERSION = "0.1.0"
$env:JWT_SECRET = "local-dev-jwt-secret-0123456789abcdef"
uv run uvicorn jbg_ai.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Smoke checks:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/v1/retrieval/products \
  -H "Content-Type: application/json" -d '{"query":"anillo","top_k":5}'
```

Health returns HTTP 200 with `{"status":"OK","version":"0.1.0"}`. The `/v1` call returns **401** without a token — that is the expected answer. To exercise it, sign a token with the same secret and the four claims, then send `Authorization: Bearer <token>`.

### Running against a real database on Windows: two traps

Both are development-machine problems. In production the service runs in a Linux container and neither exists — which is exactly why they are worth writing down: nothing in CI will ever reproduce them for you.

**Uvicorn installs the `ProactorEventLoop`, and psycopg cannot use it.** Every query fails with `Psycopg cannot use the 'ProactorEventLoop' to run in async mode`, and `GET /health` reports `"database": "unavailable"` with no other hint. Setting the policy before calling `uvicorn.run` does not help — uvicorn installs its own. The service has to be started with uvicorn not managing the loop:

```python
import asyncio, sys, uvicorn
from jbg_ai.api.main import create_app

async def main() -> None:
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=8001, loop="none")
    await uvicorn.Server(config).serve()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
```

**LiteLLM verifies TLS against `certifi`, not the operating system store.** Behind a corporate proxy with its own root CA the embedding calls fail, and the symptom misleads: `curl` with the same key returns **200** while Python returns `CERTIFICATE_VERIFY_FAILED`. The indexer records it as `OpenAIException - Connection error` in `ai.sync_failure`, which names neither TLS nor certificates. This is the runtime sibling of the `--system-certs` flag above, and it needs its own fix — export the Windows root store, concatenate it with `certifi.where()`, and point `SSL_CERT_FILE` at the result.

## Run with Docker Compose

From `backend/`:

```bash
docker compose up --build jbg-ai
```

```bash
curl http://127.0.0.1:8001/health
```

The Compose service supplies `JWT_SECRET` and `STUB_MODE` so the container boots with no extra setup. That secret is a **local placeholder**: production takes it from SSM `/jpv/prod/*` in C17 and must never reuse it. `jbg-ai` joins `jpv-network` and opens no database connection.

### Postgres image (pgvector) — volume recreate

Compose Postgres uses `pgvector/pgvector:pg15` instead of `postgres:15`. After pulling the new image, if the existing `postgres_data` volume was created with the old image, recreate it:

```bash
cd backend
docker compose down -v
docker compose up -d postgres
```

`-v` deletes local volume data. Acceptable in O0 when there is no real catalog. Bringing Compose up does **not** create schema `ai` or run `CREATE EXTENSION vector` — that is the one-off provisioning below.

## Database and migrations

Schema `ai` belongs to `jbg-ai`; schema `public` belongs to the .NET API. **Python never writes to `public` and never reads it by SQL** — it reads the business side over HTTP through the paginated feeds. That boundary is enforced by database grants, not by convention: the `jbg_ai` role gets `permission denied` on `public`.

### 1. Provision once, with administrator privileges

`migrations/bootstrap.sql` installs the extension, creates schema `ai`, creates the dedicated role and grants it the minimum it needs. It is **not** an Alembic migration, and deliberately so: roles are cluster-level objects, so creating one from a migration would demand role-creation privilege from whoever migrates and would make a clean revert impossible.

```bash
cd ai-service
docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv \
  -v ai_password=local-dev-ai-password < migrations/bootstrap.sql
```

Pass the password **raw, without quoting it yourself**: psql's `:'var'` already renders it as a quoted literal, so pre-quoting creates a password that literally contains apostrophes and then fails to authenticate.

Re-running it is safe: the extension and schema are `IF NOT EXISTS`, and an existing role keeps its password — so the script can never silently rotate a production credential. Change one deliberately with `ALTER ROLE jbg_ai PASSWORD '...'`.

In production this step belongs to **C17**, run by the RDS master user. Because the migration also declares the extension idempotently, the same `DATABASE_URL` works in both worlds — locally the extension gets installed, on RDS the migration finds it already there. No second admin connection string is needed.

### 2. Migrate

```bash
cd ai-service
export DATABASE_URL="postgresql+psycopg://jbg_ai:local-dev-ai-password@localhost:5433/joiabagur_pv"
uv run alembic upgrade head
```

```powershell
cd ai-service
$env:DATABASE_URL = "postgresql+psycopg://jbg_ai:local-dev-ai-password@localhost:5433/joiabagur_pv"
uv run alembic upgrade head
```

`alembic downgrade base` reverts it. The revert drops the six tables and **keeps** schema `ai` and the extension: the extension is shared database-wide, and the schema holds Alembic's own version table.

Two details worth knowing before editing anything here:

- **The version table lives in `ai`**, not in `public`. Alembic's default would break the ownership boundary in the project's first Python migration, silently.
- **The schema is provisioned in `env.py`, not in the first revision.** Alembic materialises its version table *before* running any revision, so a `CREATE SCHEMA` inside `upgrade()` would arrive after the failure it was meant to prevent.

### One driver, two callers

`postgresql+psycopg://` is psycopg 3, which speaks sync for Alembic and async for FastAPI, so a single connection string serves both. Choosing `asyncpg` would have meant two URL forms and someone remembering to translate between them in every environment.

> **Windows caveat.** psycopg's async mode does not work with `ProactorEventLoop`, Python's default event loop on Windows; it needs `WindowsSelectorEventLoopPolicy`. This does not affect production (Linux container) or the test suite (Alembic is sync), only running the app with uvicorn directly on a Windows host once a route actually touches the database.

## Synchronising the POS availability projection

`ai.pos_projection` is what scopes retrieval to the assortment of one point of sale. It is
filled by a command, not by a route and not by a background task:

```bash
uv run --system-certs python -m jbg_ai.indexing sync-pos          # incremental
uv run --system-certs python -m jbg_ai.indexing sync-pos --full   # ignore the cursor
```

Like `sync`, it loads `backend/.env` through `run_module` and needs
`JPV_INDEX_FEED_BASE_URL` and `JPV_INDEX_FEED_API_KEY`. It needs **no** embedding key: it
embeds nothing. It prints one line of counters — `upserted`, `soft_deleted`, `pages`,
`failed_pages`, `computed_as_of` — and **exits non-zero when any page failed**, because a
partially synchronised projection that reports success is exactly the shape of lie the
freshness guard exists to prevent one layer up.

Its cursor lives in `ai.sync_checkpoint` under `feed = 'pos-availability'`, independent of
the `catalog` row. A page that fails is recorded in `ai.sync_failure` and the drain carries
on with the remaining pages; the bookmark stays before the page that failed, so a retry
starts in front of it rather than past it.

**There is no route and no scheduler**, on purpose. `ai-service-api-contracts` enumerates
the `/v1` surface in a MUST, and an in-process scheduler would add a background task to a
container capped at 512 MiB competing for a pool of five connections. Honesty about
staleness comes from `projection_age_seconds` on the retrieval response, not from a hidden
cron: if nobody has synchronised, the response says so and the guard acts on it.

Cron recipe, every ten minutes, logging what it did:

```cron
*/10 * * * * cd /srv/jbg-ai && /usr/local/bin/uv run python -m jbg_ai.indexing sync-pos >> /var/log/jbg-ai/sync-pos.log 2>&1
```

Run `--full` once after first deploying, and again whenever `IndexFeed:SalesAsOf` changes.
An incremental run recomputes nothing: the feed re-emits only pairs whose inventory row
moved, so a clock changed afterwards leaves every unchanged pair on the old one. The stored
`computed_as_of` is what makes such a mixture visible instead of silent.


## The knowledge corpus and its index (C23)

The second index. `ai.knowledge_document` and `ai.knowledge_chunk` had existed since C05
with their final shape and **nothing had ever written to them**; the content lives in
[`../data/knowledge/`](../data/knowledge/), versioned in git, and
[its README](../data/knowledge/README.md) carries the seven authoring rules.

Three commands need neither a database nor a provider:

```bash
uv run --system-certs python -m jbg_ai.knowledge validate   # the seven rules + coverage
uv run --system-certs python -m jbg_ai.knowledge stats      # doc_type and claim_scope counts
uv run --system-certs python -m jbg_ai.knowledge measure --compare
```

Indexing does need both, and it lives beside the other two drains:

```bash
uv run --system-certs python -m jbg_ai.indexing sync-knowledge          # idempotent
uv run --system-certs python -m jbg_ai.indexing sync-knowledge --full   # re-embed everything
```

Like `sync` and `sync-pos` it loads `backend/.env` through `run_module`. It needs
`JPV_EMBEDDING_API_KEY` and `DATABASE_URL`; it needs **no** index feed, because the corpus
in git is the whole truth. **There is no cursor**, so `--full` does not mean "ignore a
checkpoint" — it means **re-embed every chunk**, which is what a change of embedding model
calls for. The corpus is validated *before* anything is written: an invalid document fails
the command rather than landing half-indexed. It prints one line of counters —
`documents`, `chunks`, `embedded`, `skipped`, `deleted_chunks`, `deleted_documents`,
`version`.

**There is no route**, and that is a decision rather than an omission:
`ai-service-api-contracts` freezes the `/v1` surface in a MUST that enumerates ten routes,
and the only consumer of knowledge search is C30, **in this same Python process**. Adding a
route would mean regenerating the committed `openapi.json` and agreeing it with the .NET
side in order to connect two modules of one process. `search_knowledge()` is a callable,
shaped as a tool so C30 can hand it to the sales agent as `consultar_conocimiento`.

### What this corpus is, and what it is not

Stated here because a citation that is well formed and wrong is worse than no citation:

- **It is synthetic.** An assistant wrote it against the eight versioned block prompts in
  [`prompts/knowledge/v1/`](prompts/knowledge/v1/), reviewed block by block; the commercial
  texts the design listed as *«to ask the business for»* never arrived, exactly as the
  photographs never did. `_corpus.meta.json` seals the model, the prompt version and the
  instant.
- **Citation verification is structural, not semantic.** It confirms that the cited source
  existed and was retrieved, **not that it tells the truth**. An invented corpus can pass
  the check at 100 % while citing something false *with a verified stamp*.
- **The `establecimiento` sections are a minority of the corpus**: commitments of the house
  that are **today illustrative**. `_corpus.meta.json` seals the exact counts and
  `python -m jbg_ai.knowledge stats` reprints them, so no figure is copied by hand into
  prose that nothing re-measures. The whole service block is one, which is what demonstrates
  the marking mechanism from the first document. That mark travels with every retrieved
  fragment and C30 is obliged to propagate it: a commitment read aloud as if it were a fact
  of the world is the failure the mechanism exists to prevent.
- **The ring size table is a convention of the house.** Its arithmetic —
  `circunferencia = talla + 40`, and the diameter derived from it — is ordinary Spanish
  practice and is scoped `general`; that `M` is sizes 13-15 is a decision and is scoped
  `establecimiento`. Confirming those ranges with the business is a pending, non-blocking
  verification: if they differ, it changes **one section of one document**, and its mark
  already flags it.
## The evaluation harness and the golden set (C24)

The retriever was complete before anything measured whether it was any good. Expansion, fused
retrieval and the point-of-sale prefilter were all decided against a rubric that counts a hit as
«right piece type and right material» — which is the lexical branch's own objective function,
since `doc_text` carries canonical `Tipo:` and `Materiales:` lines and the expansion aims at
them. C24 builds the impartial judge those four changes each promised would re-measure them.

**48 judged queries and 56 written**, in [`evals/golden/`](evals/golden/), versioned in git with
graded relevance 0-2 and the annotation criterion written **before** any label. The composition
is validated by code and **the load fails** when the set stops being able to arbitrate what it
exists for — twelve queries whose best document the lexical branch cannot reach even after
synonym expansion, five that resolve only to a sparsely tagged field, four naming four different
stones, six covering the three classes of dictionary entry, five plausible in-domain questions
the catalogue cannot answer, four that are a literal code or name, and no category answered
entirely by synthetic products.

```bash
cd ai-service
uv run evals validate                                  # the set alone: no database, no provider
uv run evals freeze-vectors                            # once, against the real provider
uv run evals run --all --repeat 3 [--persist]          # the ablation table
uv run evals run --config v2-hibrido                   # one row
uv run evals sweep                                     # the directional sweep and its verdict
uv run evals cag [--dry-run]                           # the context-only measurement, dated
uv run evals provider-latency                          # the provider round trip, cold and warm
```

`--persist` is the only thing that writes `ai.eval_run` / `ai.eval_case` / `ai.eval_result`; the
report and the per-query detail land in [`evals/results/`](evals/results/) either way. The
component that produces the results does not import the one that persists them.

**The harness introduces no setting of its own.** What it needs is already in the table above,
and the reason it is listed here is that it needs all three at once and fails naming the missing
one rather than measuring something else:

| what | why the harness needs it |
|---|---|
| `DATABASE_URL` | The pool cannot be built from a file: knowing what each configuration returns means running it against the real index. Read from the process environment, not from `backend/.env`, which carries credentials only |
| `JPV_EMBEDDING_API_KEY` | Only for `freeze-vectors` and `provider-latency`. A **run** never calls the provider: the query vectors are frozen once and served from `golden/query_vectors.jsonl`, and a missing vector raises instead of embedding on the fly, because a run that silently embeds is a run nobody can repeat |
| `JPV_RAG_LLM_API_KEY` | Only for `evals cag`. A different key from the embedding one, on purpose |
| `SSL_CERT_FILE` | On this machine TLS is intercepted and LiteLLM verifies against `certifi` rather than the operating system store — see the two Windows traps above. Set `REQUESTS_CA_BUNDLE` to the same file for `evals cag`, whose token counter downloads its encoding through `requests` |

The event loop policy is handled by the CLI itself: `psycopg` cannot run in async mode on the
proactor loop Windows installs by default, and the failure names neither psycopg nor the policy.

The measured answer to the question the project rests on, over graded relevance
([full report](evals/results/c24-baselines-2026-09-07.md), [implementation
report](../Documentos/Proyecto%20Final%20AIEng/informes/c24-implementation-measurements.md)):

| configuration | what it is | nDCG@5 | cost/query |
|---|---|---:|---:|
| `v0-nombre` | the product search the shop already had | 0,082 | $0 |
| `v0-fts` | the degraded Spanish full-text searcher | 0,454 | $0 |
| `v0-cag` | the whole catalogue in the context, no retrieval | — | $0,00267 |
| `v1-vectorial` | the vector branch alone | 0,548 | $0,0000002 |
| `v2-hibrido` | what ships today | **0,603** | $0,0000002 |

Read in two steps: tokenising Spanish buys **+0,372** and is free; semantic retrieval on top of
that buys **+0,149**. And the verdict of the earlier rubric is **reversed** — it gave the vector
branch 67 of 120 against the lexical 107, and against a judge that is not one of the parties the
vector branch beats the full-text baseline. On the twelve queries with no lexical anchor the
full-text baseline scores 0,035 and the vector branch 0,431.

**RAG against CAG, measured rather than argued.** The compacted catalogue is 17.583 tokens and
$0,00267 a query — four orders of magnitude more than embedding a query — and on the subset that
most favours it, it recalls 0,133 against the vector branch's 0,483, answering literally
`NINGUNO` on ten of twelve. Retrieval also has no catalogue ceiling: the same context stops
fitting a 100.000-token budget at **6.643 products** — a figure the harness computes and prints
under the scale curve, rather than leaving it as a division for the reader.

Latency is reported as **two figures**, always. `p95` of retrieval, which excludes the provider
round trip, is **128,6 ms** against the 500 ms the design fixes; end to end with a cold provider
would be ~900 ms, and applying the criterion to that column would report a red that belongs to
the provider. Measured separately, the provider costs p50 223 ms / p95 832 ms cold and **0 ms**
warm — the process-wide client does not reduce the round trip on a repeated query, it removes it.

**Four limitations, declared rather than mitigated:**

1. **There is no inter-annotator agreement.** The design promised double labelling with
   reconciliation between two people; the project is developed by one, so that mitigation **was
   not applied**. What replaces it is the criterion written before labelling, grouping the
   sessions by category and a deferred re-read of the doubtful ones. The absolute values carry
   the bias of a single judgement; **what is comparable between configurations remains valid,
   because the bias is the same in every row.**
2. **The annotator wrote part of the corpus** — the 764 synthetic products came from C06b. This
   is irreducible, and it is why every metric is broken down by data origin.
3. **The set is small.** With 41 queries in the real portion the confidence interval of the
   acceptance criterion is ±0,13: it does not tell 0,80 from 0,88.
4. **What the point-of-sale prefilter costs in recall is not measured.** The golden set is
   labelled unscoped, a decision taken in C22 so that retrieval quality and assortment coverage
   are not compressed into one number, and the scoped row was cut by declared decision.

## Tests

```bash
cd ai-service
uv run --system-certs pytest
```

Tests inject required env / settings in-process, sign their own tokens, and never call LLM providers, embedding APIs, or production RDS. The stub tests additionally block socket connections to prove it.

The suite mirrors the `src/jbg_ai/` package — `tests/api/`, `tests/config/`, `tests/data/`, `tests/migrations/`, and a
`tests/support/` for shared helpers (including `fake_llm.py`). [`tests/README.md`](tests/README.md) explains where a new test
goes and which folder each upcoming change lands in.

### Migration tests need Docker

`tests/migrations/` runs against a **throwaway pgvector container**, with a fresh database per test so the reversibility test cannot leak schema state into its neighbours. They are marked `db`:

```bash
uv run --system-certs pytest -m db        # only the database tests
uv run --system-certs pytest -m "not db"  # everything else
```

**Without a reachable Docker they are skipped, not failed.** There is no CI running the Python suite yet, so permanent red on a laptop would teach everyone to ignore red — which costs more than these four tests are worth. The flip side is real and worth saying out loud: a green run does not by itself prove the migration was exercised. Check that the `db` tests ran, not just that nothing failed.

These four tests exist to catch failures that produce **no error at all**: an HNSW index built with the wrong operator class is silently never used, Alembic's version table lands in `public` without complaint, and an orphaned type survives a revert to break the *next* upgrade weeks later.

## Explicit non-goals

- No real retrieval or agent loops — stubs are replaced route by route in later changes. Enrichment is real when `STUB_MODE=false` (C09). Catalog index sync is real when `STUB_MODE=false` (C13). Product retrieval is real when `STUB_MODE=false` (C14) and **hybrid since C21**: three ranked lists fused by weighted RRF, distance threshold 0.65 (a floor, not a discriminator), no `query_log`, `indexing/embeddings.py` and `openapi.json` unchanged. Substitutes stay stub/501 (C26)
- No `POST /v1/retrieval/complementary` — later OpenAPI negotiation. `POST /v1/families/suggest` **exists since C18a**, which is the change that first called it; `POST /v1/families/audit` since C18b, for the same reason
- `ai.product_document` is written by C13 from the catalog feed; `ai.pos_projection` is **written by C22** from the POS availability feed; `ai.knowledge_document` and `ai.knowledge_chunk` are **written by C23**, by `python -m jbg_ai.indexing sync-knowledge`, from the corpus in `data/knowledge/`
- No `ai.query_log` (unassigned; the pipeline logs `stage=expand|embed|search|lexical|filters|fuse` with `trace_id` instead). The `ai.eval_*` tables **exist since C24** and are written only with `--persist`
- No reranking. C24 measured the number that would make it decidable — **one query of forty-eight** has a maximum-grade document inside the window a reranker would reorder but outside the five that are shown — and a cross-encoder at ~250 ms would spend 10-15 % of C16's budget for a ceiling of 2 % of the queries. Adding one is a `configs/v2-rerank.yaml` plus a run, which is the protocol being executable rather than rhetorical
- No recalibration of `JPV_RETRIEVAL_DISTANCE_THRESHOLD`: it is C25's scope. C24 published the input it needs and the answer is negative — over 3.926 judgements the relevant documents reach a distance of 0,8008 and the irrelevant ones start at 0,3268, so **the two populations overlap and no single value separates them**. A per-query quantile is required, which is a redesign rather than a sweep
- No SQL access to schema `public`, ever
- No production deploy, SSM or `CREATE EXTENSION` on RDS. C17 delivered the **enriched health** — `GET /health` reports database reachability, indexed document count, whether the embedding provider credential is configured, and a contrast between the configured embedding model and the one recorded on the index rows, all without ever calling the provider — and deployed it to an **isolated demo account**, not to the shop's production account. The return annotation stays an open mapping, so `openapi.json` is unchanged
- No production tuning: `halfvec`, `hnsw.iterative_scan`, `CREATE INDEX CONCURRENTLY` and the `VACUUM`/`REINDEX` cycle are deliberate omissions at ~1,500 vectors, not oversights
- No edits to `indexing/embeddings.py`, frozen since C11. The POS feed **is** drained since C22, by `python -m jbg_ai.indexing sync-pos` — a command with a documented cron, not a route and not an in-process scheduler
- **The rotation figures describe the world at its horizon, not "today".** The synthetic world of C10 ends on **2026-08-23**, and since C22 the sales windows are counted against a declared reference instant (`IndexFeed:SalesAsOf`) rather than the wall clock. Two consequences worth stating plainly. It is what makes the aggregates **reproducible** — the same configuration and seed give the same figures on different days, which a ranking that reads `now()` never could, dataset horizon or not. And it means `sales_30d` describes the thirty days before that instant: peak summer for a world whose seasonality is extreme, so **23,54 %** of assigned pairs are non-zero rather than the 16,28 % a wall-clock reading gave on 2026-09-05. Neither figure is "the truth about today"; the declared one is the one that can be cited twice and mean the same thing. Removing the setting restores wall-clock behaviour, and with it the drift to zero that made the setting necessary

## Layout

```
ai-service/
  src/jbg_ai/
    api/
      main.py       # app factory, /health, router mounting
      auth.py       # HS256 decode + ServicePrincipal
      deps.py       # auth dependency, settings access, 501 guard
      middleware.py # trace_id correlation
      routers/      # retrieval, assist, inventory, enrich, index, evals
      schemas/      # frozen request/response contracts
    config/         # pydantic-settings + canonical OpenAPI profile
    db/             # lazy async engine, bounded pool
    stubs/          # deterministic fixtures
    data/           # C06b generate/ingest + C10 world/; not imported by api.main
    enrichment/     # C09 extractor: vocabs, size regex, LiteLLM port, auditor
    families/       # C18a grouping + C18b audit over persisted families; offline, writes nothing
    indexing/       # C11 source-text/embeddings (frozen) + C13 feed client, repo, orchestrator, sku_provenance.json
    retrieval/      # C14 vector retriever (embed max_attempts=1, <=> HNSW, body filters)
                    # + C20 query expansion: synonyms.py, query_synonyms.yaml, measure.py CLI
    knowledge/      # C23 second index: corpus.py (seven authoring rules), chunking.py (pure),
                    # indexer.py (uuid5 identity, idempotent), search.py (callable, no route),
                    # sizing.py (D16 ring table), offline.py + measure.py (fixture, no provider)
    evals/          # C24 harness: golden.py (load + the composition validation that fails the
                    # load), pooling.py (adaptive depth), metrics.py (graded and binary),
                    # configs.py + baselines.py (the two v0 replicas), cag.py (context-only),
                    # sweep.py (the directional sweep and its written rule), runner.py,
                    # report.py, repository.py (opt-in sink, imported by nobody upstream),
                    # cli.py (`uv run evals`)
  prompts/          # versioned prompts: catalog-synth/v3 (C06b generate) + enrichment/v1 and v2 (extract; v2 in force since FIX1)
                    # + knowledge/v1: eight block prompts, one per generation block of the corpus
  evals/            # the yardstick, versioned: golden/ (queries, judgements, frozen query vectors,
                    # criterion.md, pricing.yaml), configs/ (the five baseline configurations) and
                    # results/ (C20 reach report, C21 arm comparison, C24 baselines + runs/<run_id>.jsonl)
  migrations/
    bootstrap.sql   # one-off: extension, schema, dedicated role, grants
    env.py          # version table in `ai`; provisions before revisions run
    versions/       # hand-written revisions (no autogenerate)
  tests/            # mirrors src/jbg_ai — see tests/README.md
    api/            # contract, auth, stubs, OpenAPI snapshot
    config/         # settings and fail-fast validation
    data/           # C06b catalog CLI + C10 world/ (no provider sockets)
    families/       # C18a grouping and C18b audit (fakes; no provider sockets)
    indexing/       # C11 embeddings, C13 catalog drain, C22 POS drain (marked `db` where SQL)
    knowledge/      # C23 corpus rules, chunking, sizing, indexer, search, measurement
    migrations/     # schema, indexes, reversibility (marked `db`)
    retrieval/      # C14 vector retriever + C20 expansion (fakes; no provider sockets)
    support/        # shared helpers and injectable fakes
  alembic.ini       # no connection string: read from DATABASE_URL
  openapi.json      # versioned contract snapshot
  Dockerfile
  pyproject.toml
```
