# Design — add-synonym-dictionary (C20)

## Context

C05 created `ai.product_document.tsv` as a generated `to_tsvector('spanish', doc_text)` column with a GIN index. It is populated on all 1.168 live rows and **no code reads it**. C14 built the vector branch; `mode=hybrid` and `mode=lexical` both run it and say so in `debug.notes`. C21 will build the lexical branch that finally consumes `tsv`.

Decision 4 of the review removed `SearchAliases` — AI-generated text persisted per product, with drift. Design §7.4 replaced it with a hand-curated domain dictionary applied **at query time, never at indexing time**.

Everything below was measured on 2026-09-01 against the local PostgreSQL (1.168 live documents) and, for the vector figures, against the real embedding provider with `text-embedding-3-small`. The full record is the §0 entry of `Documentos/Proyecto Final AIEng/proyecto-final-plan-changes-openspec.md`.

Four measurements govern the design:

| # | Measurement | Consequence |
|---|---|---|
| 1 | `doc_text` carries canonical `Tipo:` (1.157/1.168) and `Materiales:` (1.042/1.168) lines. Lexical hits on a canonical term equal the `piece_type` count exactly — `anillo` 268 = 268, `pendientes` 275 = 275, `pulsera` 207 = 207, `collar` 140 = 140 | Expanding *operator word → canonical* has a guaranteed target. That is the direction `vocabularies.yaml` already encodes |
| 2 | Without expansion the lexical branch returns **0** for `gargantilla dorada` and `collares de plata`, **1** for `criollas de oro`, **3** for `sortija de plata` | The dictionary is not an improvement; it is the difference between a lexical branch that answers and one that does not |
| 3 | The Spanish stemmer splits domain nouns: `collar`→`'coll'` ≠ `collares`→`'collar'` (**140 vs 1** documents); `baño`→`'bañ'` ≠ `bano`→`'ban'` (**38 vs 0**); `pequeño`→`'pequeñ'` ≠ `pequeno`→`'pequen'` (134 vs 71, both legitimate). Acute accents *are* folded (`ámbar`=`ambar`, `ónix`=`onix`); `ñ` is not | Stemmer artefacts are dictionary content, not a footnote. A till operator typing without `ñ` gets nothing |
| 4 | A single widened `tsquery` `(sortij\|anill) & plat` ranks **0 of the 3** literal «Sortija» products in the top 10. RRF (k=60) over the original and widened lists puts them back at **1, 2, 3** while keeping all 144 candidates | The expansion must hand C21 several lists, not one rewritten query. C20 cannot destroy the signal C21 fuses on |

And one that decides what C20 does *not* do:

| Query | correct in top-10, variant | correct in top-10, canonical | top-10 overlap |
|---|---|---|---|
| `criollas de oro` | **1/10** | 8/10 | 1/10 |
| `sortija de plata` | **4/10** | 10/10 | 2/10 |
| `gargantilla dorada` | **6/10** | 10/10 | **0/10** |
| `aros de plata` | 9/10 | 10/10 | 0/10 |
| `collares de plata` | 10/10 | 10/10 | 8/10 |

The vector branch is no substitute for the dictionary, and it fails **without abstaining**: it returns ten candidates under the 0,65 threshold regardless, so «Pulsera Río de Plata» is the first result for `sortija de plata`. The plural case it crosses unaided, which confirms the stemmer problem is strictly lexical.

## Goals / Non-Goals

**Goals:**

- One definition per domain term, with no second copy that can drift.
- Query expansion whose output preserves everything C21 needs: the operator's own words, the canonical class, and the vocabulary field each term resolved to.
- Stemmer artefacts and the missing `ñ` handled without a migration.
- An enable flag that C24 can sweep in-process.
- Evidence C20 produces itself, because the harness that was supposed to judge it (C24) sits downstream of C21, which sits downstream of C20.
- Zero change to the observable behaviour of `POST /v1/retrieval/products`.

**Non-Goals:**

- The lexical branch, `ts_rank`, RRF fusion, SKU boosting and rule-based filter extraction from query text — all C21.
- Any effect on the vector branch. The embedding is computed on the original text.
- Editing `enrichment/vocabularies.yaml`, jumping to `enrichment/v2`, or filling the `piece_type` / `style_tags` gaps (`llavero`, `diadema`, `gemelos`, `cinturon`, `filigrana`) — all `fix-enrichment-vocabulary-gaps`.
- Installing `unaccent` or `pg_trgm`, or creating a custom text-search configuration.
- Typo tolerance, LLM query rewriting, `ai.query_log`, persisting anything.
- The per-request embedding client singleton and the 2500 → 800 ms budget revert (C21/C22, recorded in `openspec/DEFERRED_TASKS.md`).
- Regenerating `openapi.json`, any Alembic revision, any EF Core migration, `backend/`, `frontend/`.

## Decisions

### D1 — Two layers: enrichment base plus a query-only overlay

`enrichment/vocabularies.yaml` is loaded as the base equivalence classes and **is never modified**. `retrieval/query_synonyms.yaml` adds what must not enter the extraction contract.

The base already carries `sortija→anillo`, `alianza→anillo`, `gargantilla→collar`, `brazalete→pulsera`, `aro`/`aros`/`criollas→pendientes`, `plata de ley`/`925`/`sterling`→`plata`, `18k`/`gold`→`oro` — with the right direction and, crucially, the **right accents**. `ClosedVocab.resolve()` matches on folded text, so `resolve("bano de oro")` already returns `"baño de oro"` today. Reuse is free; duplication is not.

| Option | Drift | Cost of a new base term | Cost of `collares` (a tokenizer artefact) |
|---|---|---|---|
| **Base + overlay (chosen)** | impossible — one definition | arrives free from C09 | overlay, extraction contract untouched |
| Standalone new file | **two definitions of `sortija→anillo` that diverge silently** | must remember to replicate | free |
| Extend `vocabularies.yaml` | impossible | free | **forces `enrichment/v2` and re-enrichment** |

The standalone file is what the original ficha said. It is rejected for the reason that killed C19: a second copy of a definition whose two versions can disagree. The cost of the chosen option is a coupling from `retrieval/` to a file owned by `enrichment/`, mitigated by a fixation test that fails if the base loses a class the expander relies on.

**Precedence rule:** the overlay may *add* surface forms to a base class and *create* new classes. It may **not** reassign a base canonical. A test pins this — otherwise the overlay becomes a silent fork of the extraction vocabulary, which is exactly what layering was meant to prevent.

### D2 — Output is equivalence groups plus resolved terms, never a rewritten string

```
ExpandedQuery(
    original = "gargantilla dorada",
    groups   = [["gargantilla", "collar"],
                ["dorado", "baño de oro", "oro"]],
    matched  = [("gargantilla", "piece_type", "collar"),
                ("dorado",      "color_tags", "dorado")],
)
```

Measurement 4 rules out the single widened query: `ts_rank` cannot tell a document matching the operator's own word from one matching a synonym, so the exact term is diluted to invisibility. Handing C21 the groups **and** the original lets it run two rankings and fuse them, which is measured to restore the exact matches to positions 1–3 without losing any recall.

`matched` is not decoration. C21 must extract structural filters by rule (`test_never_invents_filter_absent_from_query`), and the mapping *typed term → vocabulary field → canonical* is exactly that lookup. Omitting it makes C21 build a second lookup table over the same data — C19's mistake at smaller scale.

**Alternatives rejected:** a list of rewritten query strings (`["sortija plata", "anillo plata"]`) is closer to S10's multi-query shape and reads well, but explodes combinatorially with two or more expandable tokens and forces C21 to re-tokenise to recover filters; a single canonicalised string (`gargantilla dorada` → `collar dorado`) is simplest but measured worse on both counts — 22 documents against 64, and canonicalising `pequeño`→`pequeno` throws away the 134 documents that use the accented form in prose.

### D3 — The whole class is emitted, not just the canonical

`pequeño` reaches 134 documents and `pequeno` reaches 71, and they are different sets: the accented form lives in descriptions, the unaccented one in the canonical `Talla:` line. Emitting only the canonical would lose the larger set. The class is the union, ordered with the operator's own form first so C21 can weight it if it chooses to.

### D4 — Matching on folded text, emission on surface forms

Matching reuses `fold()` and `ClosedVocab.resolve()`, which is what makes the `ñ` problem disappear on the input side.

Emission cannot reuse `ClosedVocab.phrases_for()`. That function returns the class **folded** — `fold()` strips accents and turns `ñ` into `n` — and `to_tsvector('spanish','bano')` yields `'ban'`, which does not match `'bañ'`. Accented surface forms come from `ClosedVocab.canonical` and from the overlay. This is the easiest trap in the change and the one most likely to pass tests written against folded fixtures.

Phrase matching is **longest first**, so `aro de dedo` → `anillo` beats `aro` → `pendientes`. Verified: all 15 sampled `aro`/`aros` documents are `piece_type = pendientes`, and the 6 that match `aro de dedo` are all rings, so both mappings are safe as long as the longer phrase wins.

### D5 — Singularisation on both sides at load time

Applied to dictionary keys and to query tokens, and **only** when the reduced form exists in the dictionary — it never invents a canonical. This alone resolves `sortijas`, `gargantillas`, `brazaletes`, `esclavas` and `dorados`, removing roughly ten entries that would otherwise be one-per-inflection noise in a file whose whole value is being readable.

It does **not** subsume D4: the stemmer's failures (`collares`, `aros`, `bano`) are not inflection rules and stay explicit in the overlay.

### D6 — The flag's default lives in `Settings`; its value travels through the orchestrator signature

`JPV_QUERY_EXPANSION_ENABLED`, boolean, **default `true`**, optional at boot, pinned in `canonical_openapi_settings`.

C24 will sweep `v0-lexico`, `v0-cag` and `v2-hibrido` in one process. An environment-only switch forces a restart per configuration; moving it to `RetrievalRequest` would move the frozen `openapi.json`. So `Settings` supplies the default and the orchestrator takes a parameter — the same seam `settings`, `embed` and `search` already use in `retrieve_products`.

Default `true` because with the lexical branch still off it changes nothing today, and the day C21 switches on, answering zero to `gargantilla dorada` is not a defensible default. C24's ablation can turn it off; measurement 2 is not in doubt.

### D7 — Observe-only, because the contract is frozen and the harness is downstream

C20 cannot expose an endpoint: `ai-service/openapi.json` is frozen with the .NET side and `test_openapi_snapshot_is_stable` guards it. And it cannot be judged by C24, which sits two changes downstream (`C20 → C21 → C24`) — the original ficha asked C20 to be measured by a harness its own change unblocks.

So the expansion is computed on every real retrieval, logged as `stage=expand`, and **not consumed** until C21. That is stated plainly in the spec and the README rather than dressed up. Against it: for one change there is code on the hot path whose result nothing reads. In its favour: the alternative is a library that never executes once — the signature this project has chased since C17 — and the log gives C24 a free record of how often real queries hit the dictionary.

### D8 — Three exclusions, each with its measurement

| Excluded | Why |
|---|---|
| `piel` → `cuero` | **False friend.** All 7 matching documents say «sobre la piel», «acaricia la piel» — human skin in marketing prose. `cuero` has **one** product in the whole catalogue, so the mapping would inject seven errors into every leather query |
| `llavero`, `diadema`, `gemelos`, `cinturon` | Not synonyms — `piece_type` gaps. They belong to `fix-enrichment-vocabulary-gaps`, whose own ficha claims them |
| `filigrana` | Needs no expansion: it matches **66** documents on its own, spread across every piece type. It is a `style_tags` gap and a real Menorcan domain term — one of the 12 recorded searches is literally *«anillo de filigrana tradicional menorquina»* |

`piel` is the argument for why this dictionary is curated and measured rather than generated. Any entry added later must come with its document count or it does not go in.

### D9 — `dorado` bridges two vocabularies deliberately

`dorado` is canonical in `color_tags` **and** a synonym of `baño de oro` in `materials`, and the §0 entry of 2026-08-31 already recorded that its absence from `materials` leaves families ungrouped. The class is the union `{dorado, baño de oro, oro}`, measured at **64** documents against **22** for simple canonicalisation. It is a content decision recorded in the overlay with that number beside it, not a mechanism.

### D10 — No `unaccent`, no custom text-search configuration

`unaccent` is available and not installed. Adopting it would mean a custom `ts` configuration, and `tsv` is a **generated** column: the migration would rewrite it on every row and rebuild the GIN index, making C20 a 🗄️ change. `unaccent(text)` is also `STABLE`, not `IMMUTABLE`, so a generated column needs an immutable wrapper — a known PostgreSQL trap. Three overlay entries buy the same outcome for the terms that actually matter.

## Flow

```
POST /v1/retrieval/products            internal JWT (with pos_id)
         │
         └─ STUB_MODE=false
                │
                ├──► expand_query(payload.query, enabled)      ← C20, pure, no I/O
                │         │
                │         ├─ groups   ──┐
                │         ├─ matched  ──┼──► C21: lexical branch, RRF, rule filters
                │         └─ original ──┘        (NOT in this change)
                │         │
                │         └─ log stage=expand (trace_id, enabled, tokens, matched_terms)
                │
                ├──► embed(payload.query)        ← ORIGINAL text; the vector is not expanded
                │
                ├──► SQL  embedding <=> q ≤ threshold          ← C14, unchanged
                │
                └──► 200 results / low_confidence              ← byte-identical to today

ai.product_document.tsv ── generated, GIN-indexed, populated, NO CONSUMER until C21
```

Load path, once per process (`lru_cache`, mirroring `load_vocabularies()`):

```
vocabularies.yaml ──┐
                    ├─► merge ─► singularise both sides ─► equivalence classes
query_synonyms.yaml ┘              (overlay adds, never reassigns)
```

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Recall rises and precision falls.** 3 → 144 candidates is a lot of noise if `ts_rank` cannot discriminate | The RRF simulation over this index already shows the exact matches surviving at 1–3. The real verdict is nDCG@5 in C24, which is why the flag exists. C20 does not claim a precision result it cannot measure |
| **Dead code on the hot path until C21** (D7) | Bounded to one change, guarded by the flag, and paid for by the `stage=expand` record. The spec states the expansion is not consumed, so nobody reads the log as evidence of a working lexical branch |
| **Emitting with `phrases_for()`** — folded output silently loses `ñ` and accents, and a fixture written folded would pass | Called out in D4, and covered by a test that asserts `bano de oro` expands to the accented `baño de oro` |
| **The overlay drifts into a fork of the extraction vocabulary** | Precedence rule in D1 plus a test that the overlay never reassigns a base canonical, and a fixation test that the base file has no diff |
| **A future editor "helpfully" adds an entry without measuring**, and reintroduces a `piel` | The file records the excluded entries and their reason next to the included ones, so the rule is visible where the temptation is |
| **Zone conflict with C21** — both live in `src/jbg_ai/retrieval/` | The surviving §1 rule: two changes touching the same files are not open at once, even for the same person. C20 adds files and touches the orchestrator at one point |
| **The measurement CLI needs a database that may not exist** | Skips cleanly rather than failing, as C05's pgvector tests do. It is not part of the unit suite, and no test requires 1.168 rows |
| **Curated against the corpus, not against demand** — 31 telemetry rows, 12 texts, all developer-written in canonical vocabulary | Declared as a limitation in the README beside the golden set's absence of inter-annotator agreement, and re-measured by C24 |

## Migration Plan

No migration. No Alembic revision, no EF Core migration, no PostgreSQL extension, no document reindexed — `doc_text`, `tsv` and `source_hash` are provably identical before and after, and a scenario asserts it.

Deployment is a code deploy plus one optional environment variable. **Rollback is setting `JPV_QUERY_EXPANSION_ENABLED=false`**, which returns single-element groups and restores byte-identical behaviour; since nothing consumes the groups until C21, even the flag is belt-and-braces.

## Open Questions

All five open questions from the ticket were resolved with their stated defaults on the user's instruction:

| # | Question | Resolution |
|---|---|---|
| 1 | New capability or delta of `vector-retrieval`? | **New capability `query-expansion`**, plus a delta of `ai-service-runtime` for the flag. `vector-retrieval` describes endpoint behaviour, which does not change; C21 inherits the new capability |
| 2 | Module name | **`retrieval/synonyms.py`**, matching `query_synonyms.yaml` and the change name |
| 3 | Report location | **`ai-service/evals/results/`**, creating the tree. C24 reuses it rather than duplicating a second home for the same artefact |
| 4 | CLI shape | **Own entrypoint under `jbg_ai.retrieval`**, so the indexing CLI — which writes to the database — does not grow a read-only reporting surface |
| 5 | Final overlay size | The **~18** inventoried entries, no speculative additions. Every future entry carries its document count or does not enter |

Default for any minor detail the apply uncovers: the narrowest option that does **not** edit `vocabularies.yaml`, regenerate `openapi.json`, touch the vector branch, open a migration, or bring any part of C21 forward.
