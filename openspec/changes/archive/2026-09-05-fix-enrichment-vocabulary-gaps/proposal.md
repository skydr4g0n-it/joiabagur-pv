# fix-enrichment-vocabulary-gaps (FIX1)

## Why

`piece_type` is a **closed** vocabulary of eight hypernyms, fixed by C09 and replicated in four other places. The catalogue holds pieces those eight terms cannot name, and the extractor does exactly what it was told: it leaves `piece_type` null, or it picks the most plausible hypernym. C18a saw half of that — eleven products with no type — and booked it as a change of its own.

**The exploration of 2026-09-05 measured the other half, and it is the worse one.** Of the 22 products whose name carries one of the four missing terms, **eleven have no type and nine are wrongly typed**. A null is honest: it matches no facet and nobody is misled. A wrong label lies, and the category filter is **hard** (`AND d.piece_type = :category`), so a tiara labelled `broche` shows up when the operator filters for brooches. Today **six of the 85 `broche` documents are three tiaras, two cufflinks and a keyring**, `collar` carries two tiaras of its 140, and `colgante` one of its 161.

Re-enriching only the eleven nulls — what the ficha asks for — would ship a "Diadema" facet returning **5 of 11**. It does not say zero; it says five. No error, no trace, results on screen. That is the C17 signature in its worst form, and it is why the cohort is the full twenty-two.

Two secondary reasons point the same way. The change alters the **normative content of two live specs**, and `openspec validate --all --strict` would stay green over both while they lie, because it validates structure and not truth. And it **moves the corpus**: re-enrichment rewrites `ProductAiProfile`, `doc_text`, `source_hash` and the embeddings of those rows — a data migration even without a schema change — which must land **before C24 labels its baseline**, since `source-text/v1` would not betray it.

## What Changes

- **Four canonical terms are added to `piece_type.terms`**: `diadema`, `gemelos`, `cinturon`, `llavero`. `gemelos` is plural, like `pendientes`; `cinturon` is unaccented, following the `pequeno` precedent, because the panel value is compared by exact equality and only the label carries the accent.
- **A new prompt `enrichment/v2`** carries the widened list plus the line that was actually missing. C09's prompt already offered *«un hiperónimo de la lista cerrada, **o null**»* — the option existed; **the brief did not**. It opens with *«Eres un extractor de atributos de joyería»* and never contemplates that the catalogue might hold something else, so faced with `Arreglos oro` it guesses `collar`, which is precisely what it was asked to do. `v1.md` is **neither edited nor deleted**: 1.178 profiles will keep claiming to come from it and that claim must stay verifiable.
- **`load_prompt()` derives its path from `PROMPT_VERSION`.** The two are declared separately today (`constants.py` and `pipeline.py`), so bumping one without the other would stamp profiles `enrichment/v2` while sending `v1` — dismantling, in silence, the exact property that makes mixing prompt versions safe: that a profile says which prompt produced it. A two-line test asserts the loaded file's heading matches the constant.
- **A cohort of 22 enumerated SKUs is re-enriched** with `force: true` and `reviewMode: AutoBulk`, in a single batch, followed by **one** incremental index sync. Nineteen gain or correct a type; `Joya del Zodiaco` (SKU845, empty description) stays null and that is the correct outcome; and **`Broche Cinturón de Orión` (SKU822) and `Anillo Cinturón de Orión` (SKU882) are the control group that must not move** — "Cinturón de Orión" is the constellation, a measured false friend of the same family as the `piel → cuero` exclusion.
- **BREAKING relative to the ficha: the population is 22, not 11.** Its "out of scope" excludes re-enriching all 1.200 because that *«podría reclasificar productos existentes de forma difusa»*. The reason holds and the 1.200 stay out — but it does not apply to nine rows that each carry the new term in their own name and each sit in a category demonstrably not theirs. That reclassification is enumerated, nominal and auditable line by line.
- **BREAKING relative to the ficha: its end-to-end criterion already passes today.** *«Buscar "diadema" pasa de cero a resultados»* — measured, `diadema` already reaches **11 documents** through C21's lexical branch, because the name lives in `doc_text`. A verifier running it would sign green for the wrong reason. The acceptance criteria are rewritten as structural: nulls 11 → 1, `piece_type = 'diadema'` 0 → 11, impostors in `broche` 6 → 0.
- **The frontend mirror grows to twelve options.** Measured against the assortment, every new term clears the bar the repository already accepts: `diadema` and `gemelos` are carried in 11 of 11 points of sale, `cinturon` in 10, `llavero` in 6 — against `cadena`, which has shipped in that dropdown since C16 with 7 products in 6 of 11.
- **The C20 query overlay enters scope**, against the ficha's exclusion list. Its four `exclusions` say literally *«pertenece a `fix-enrichment-vocabulary-gaps`»*; leaving them would be well-formed, false documentation — the very sin that justifies this being a change. They are removed, `filigrana`'s reason is rewritten so it no longer defers to this change, and a surface form `gemelo` is added because plural reduction runs singular←plural and cannot reach a plural canonical.
- **Four pinned tests fail on purpose, not two.** Beyond the two the ficha names, `test_vocabulary_gaps_are_recorded_as_exclusions_not_smuggled_in` requires the four terms in `exclusions`, and `test_overlay_anchor_absent_from_the_base_is_a_vocabulary_gap` **uses `diadema` as its example of an unknown canonical** — it will fail with `DID NOT RAISE`, in the opposite direction to the expected one. Its example becomes `filigrana`, the gap that is still open; **the test is not deleted**, because it is the guard that keeps vocabulary gaps from being smuggled in as synonyms.
- **No migration**, of either kind. **No new HTTP route.** **`ai-service/openapi.json` is not regenerated** — no route, field or schema moves. `source-text/v1`, `embedding_version` and `indexing/embeddings.py` are untouched: the document template does not change, only the content of twenty-two rows. Mixing `embedding_version` would be comparing two geometric spaces — S11's silent corruption; mixing `PromptVersion` is two comparable populations of attributes, and the field exists to make that difference visible.

## Capabilities

### New Capabilities

None. This change adds no capability: it corrects the normative content of two that already exist.

### Modified Capabilities

- `catalog-enrichment-pipeline`: the canonical `piece_type` list goes from eight hypernyms to twelve, the scenario that fixes `prompt_version` moves to `enrichment/v2`, and a new requirement states that rows which are not finished jewellery get a null piece type rather than the most plausible hypernym.
- `query-expansion`: the scenario requiring the four terms to be recorded as belonging to the vocabulary-gap change becomes false once that change closes them, and is rewritten around the exclusions that remain open.

## Impact

| Area | Impact |
|---|---|
| `ai-service/src/jbg_ai/enrichment/` | `vocabularies.yaml` (+4 terms), `constants.py` (`PROMPT_VERSION`), `pipeline.py` (`load_prompt` derives its path) |
| `ai-service/prompts/enrichment/` | `v2.md` **new**; `v1.md` **unchanged** |
| `ai-service/src/jbg_ai/retrieval/` | `query_synonyms.yaml`: four exclusions closed, `filigrana`'s reason rewritten, `gemelo` surface form added. `synonyms.py` is untouched — it derives the new classes on its own through `_base_layer()` |
| `ai-service/tests/` | Three pinned tests updated in `retrieval/test_synonyms.py`; four new tests in `enrichment/` |
| `frontend/src/lib/` | `materials-vocabulary.ts` (+4 options) and its pinned test |
| `openspec/changes/.../specs/` | Two `MODIFIED` requirements plus one `ADDED` in `catalog-enrichment-pipeline`; one `MODIFIED` in `query-expansion` |
| `Documentos/` | `epicas.md` (EP12), report `fix1-vocabulary-gaps-measurements.md`, README limitation |
| Data | 22 `ProductAiProfiles` rewritten; ~19 `ai.product_document` rows re-rendered and re-embedded by one incremental sync |
| `backend/src/` | **No code change.** `POST /api/ai/catalog/enrich-batch` is executed with `force: true`; `Force`, `MaxBatchSize = 50` and `AutoBulk → Approved` all already exist |
| `ai-service/openapi.json` · `terraform/` · `.github/workflows/` | **None** |
