## 1. Baselines before touching anything

- [ ] 1.1 Record the Python baseline: `uv run pytest` from `ai-service/`, keeping the failing **test names**, not the count
- [ ] 1.2 Record the frontend baseline: `npm run test` in `frontend/`, keeping the failing **test names** — the suite is red before this change and `vitest` exits 0 when piped, so read the summary line
- [ ] 1.3 Confirm the local corpus is the one the report measured: 1.168 rows in `ai.product_document`, 11 with `piece_type IS NULL`, 85 with `broche`, and 1.200 profiles all on `enrichment/v1`
- [ ] 1.4 Pre-flight the cohort: confirm no profile of the 22 SKUs of `design.md` D1 carries `ReviewedByUserId` or `ReviewedAt` — re-enrichment clears them and logs `enrich_profile_review_reset`

## 2. Vocabulary (D3)

- [ ] 2.1 Append `diadema`, `gemelos`, `cinturon` and `llavero` to `piece_type.terms` in `ai-service/src/jbg_ai/enrichment/vocabularies.yaml`, in that order and at the end of the list
- [ ] 2.2 Add no extraction synonym for them in the enrichment YAML — query-side variants belong to the C20 overlay
- [ ] 2.3 Test `test_new_piece_types_are_canonical_and_normalised`: the four terms resolve to themselves, fold correctly, and `Cinturón` resolves to the unaccented canonical

## 3. Prompt `enrichment/v2` and its version derivation (D4)

- [ ] 3.1 Create `ai-service/prompts/enrichment/v2.md` from `v1.md`, heading `# enrichment/v2`, with the twelve-term `piece_type` list in the «Vocabularios» section
- [ ] 3.2 Add to the brief the line stating the catalogue may contain services, consumables and gift articles, for which `piece_type` is `null` — the `null` output already existed in C09; what was missing is the instruction
- [ ] 3.3 Verify `ai-service/prompts/enrichment/v1.md` has **no diff**
- [ ] 3.4 Set `PROMPT_VERSION = "enrichment/v2"` in `enrichment/constants.py`
- [ ] 3.5 Derive the path in `enrichment/pipeline.py`: `_PROMPT_RELATIVE = Path("prompts") / f"{PROMPT_VERSION}.md"`, keeping the three existing search candidates and updating the `FileNotFoundError` message so it no longer names `v1`
- [ ] 3.6 Test `test_prompt_version_matches_the_loaded_prompt_file`: the first line of `load_prompt()` is `# ` + `PROMPT_VERSION`
- [ ] 3.7 Test that the `piece_type` list written in the loaded prompt matches `piece_type.terms` of the YAML, so a future drift between the two fails red instead of silently

## 4. Pipeline tests that describe what they actually test (D8)

- [ ] 4.1 Rename `test_service_and_consumable_rows_get_null_piece_type` to name what it verifies with a fake `EnrichLlm` — the pipeline's handling of a null, not the prompt's wording
- [ ] 4.2 Test `test_untypeable_jewel_stays_null`: a product with no evidence of any canonical type keeps `piece_type` null and that is not treated as a rejected extraction
- [ ] 4.3 Test `test_proper_name_containing_a_piece_type_does_not_beat_the_head_noun`, fixture `Broche Cinturón de Orión` → `broche`, in the idiom of the `piel` exclusion
- [ ] 4.4 Confirm the whole `ai-service/tests/enrichment/` tree still opens no socket to a provider

## 5. Query overlay of C20 (D6)

- [ ] 5.1 Remove `llavero`, `diadema`, `gemelos` and `cinturon` from the `exclusions` of `retrieval/query_synonyms.yaml` — deleted, not rewritten as "closed"
- [ ] 5.2 Rewrite the `why` of `filigrana` so it no longer defers to this change, keeping its measurement (66 documents, a `style_tags` gap and a real Menorcan trade term)
- [ ] 5.3 Add class `piece_type / gemelos` with surface form `gemelo` and its measured reason: plural reduction runs singular←plural, so the singular cannot reach a plural canonical
- [ ] 5.4 Add no `tiara` entry — it reaches 0 documents and the overlay's rule is that an entry without a number behind it does not go in
- [ ] 5.5 Confirm `retrieval/synonyms.py` needs **no change**: `_base_layer()` derives the four new classes from the YAML on its own

## 6. The four pinned tests that must fire (D7)

- [ ] 6.1 `test_base_vocabulary_terms_are_pinned`: extend the `piece_type` tuple to twelve terms and update the docstring, which today announces this very change
- [ ] 6.2 `test_vocabulary_gaps_are_recorded_as_exclusions_not_smuggled_in`: reduce the required set to the exclusions still alive, `piel` and `filigrana`
- [ ] 6.3 `test_overlay_anchor_absent_from_the_base_is_a_vocabulary_gap`: **swap `diadema` for `filigrana`** as the unknown canonical. **Do not delete the test** — it fails with `DID NOT RAISE`, the opposite direction to the expected, and it is the guard that keeps gaps from entering as synonyms
- [ ] 6.4 `frontend/src/lib/materials-vocabulary.test.ts`: extend the pinned array and its description from "the eight canonical piece types" to twelve

## 7. Frontend mirror (D5)

- [ ] 7.1 Add to `PIECE_TYPE_OPTIONS` in `frontend/src/lib/materials-vocabulary.ts`: `diadema`/«Diadema», `gemelos`/«Gemelos», `cinturon`/«Cinturón», `llavero`/«Llavero»
- [ ] 7.2 Verify the `value` is byte-for-byte the YAML canonical — it travels to `AND d.piece_type = :category`, compared by exact equality — and that the accent lives only in the `label`
- [ ] 7.3 Confirm no change is needed in `pages/sales/assisted.tsx`: the `<Select>` maps over the constant
- [ ] 7.4 `npm run build` clean — the real gate; `tsc --noEmit` carries pre-existing Metronic template errors and is not the gate

## 8. Spec deltas

- [ ] 8.1 `specs/catalog-enrichment-pipeline/spec.md`: two `MODIFIED` requirements restated in full with all their scenarios, plus the `ADDED` requirement on rows that are not finished jewellery
- [ ] 8.2 `specs/query-expansion/spec.md`: the `MODIFIED` requirement on entries and exclusions justified against the corpus
- [ ] 8.3 `openspec validate fix-enrichment-vocabulary-gaps --strict` in green

## 9. The re-enrichment run (D8)

- [ ] 9.1 Recreate the `jbg-ai` container with `STUB_MODE=false` and `JPV_RAG_LLM_API_KEY`, per the C12 runbook — with the stub, the report would describe a fiction
- [ ] 9.2 Capture the "before" state of the 22 SKUs: full profile, not only `piece_type`
- [ ] 9.3 Run `POST /api/ai/catalog/enrich-batch` with the 22 `productId`, `force: true` and `reviewMode: "AutoBulk"`, in a single batch
- [ ] 9.4 Verify the 22 profiles are on `enrichment/v2` and the other 1.178 remain on `enrichment/v1`
- [ ] 9.5 Verify the control group: SKU822 is still `broche` and SKU882 still `anillo`. If either moved, stop and fix the brief before continuing
- [ ] 9.6 Verify SKU845 `Joya del Zodiaco` is still null, and that it is the only null left in the index
- [ ] 9.7 Review the **full diff** of the 22 rows — materials, stone, size and the three tag lists, not just the type — and record anything that moved unexpectedly
- [ ] 9.8 Run one incremental index sync and verify the number of re-embedded rows equals the number of profiles whose `doc_text` changed
- [ ] 9.9 Confirm `embedding_version` and the `source-text` version did not move on any row

## 10. End-to-end verification (D2)

- [ ] 10.1 Count in `ai.product_document`: `diadema` 11, `gemelos` 4, `llavero` 3, `cinturon` 1, `piece_type IS NULL` 1
- [ ] 10.2 Count `broche` 79 and confirm none of its rows is a tiara, cufflinks or a keyring; `collar` and `colgante` down by 2 and 1
- [ ] 10.3 Through the UI, with a real operator session: filter by «Diadema» and by «Broche» and check the **counts**, not just that something comes back
- [ ] 10.4 Do **not** use "searching `diadema` returns results" as evidence — it passed before the change too

## 11. Closing

- [ ] 11.1 Write `Documentos/Proyecto Final AIEng/informes/fix1-vocabulary-gaps-measurements.md` with the 22-row before/after table, the full diff and the control-group verdict
- [ ] 11.2 Declare in the `ai-service` README that the catalogue now holds two enrichment prompt versions, and that any aggregate metric over extracted attributes must be reported per `PromptVersion`
- [ ] 11.3 Update `Documentos/epicas.md` (EP12): mark FIX1 done and link the implementation report
- [ ] 11.4 Compare both suites against the baselines of section 1 **by failing test name**, never by count
- [ ] 11.5 Confirm no migration was created, `ai-service/openapi.json` has no diff, and `test_openapi_snapshot_is_stable` is green
- [ ] 11.6 `openspec validate --all --strict` reporting `0 failed` before archiving
