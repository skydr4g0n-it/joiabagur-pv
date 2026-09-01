# Tasks — add-synonym-dictionary (C20)

Order is dependency order. Group 1 is archivable on its own if the change overruns (cut line in the ticket): dictionary, expansion, flag and tests. Groups 5 and 6 are the observability and the evidence.

## 1. Dictionary loader and overlay

- [x] 1.1 Create `ai-service/src/jbg_ai/retrieval/query_synonyms.yaml` with the three families of entries — stemmer artefacts (`collares`, `aros`, `bano de oro`, `banado en oro`, `pequeño`/`pequeno`), commercial synonyms the base lacks (`arete`, `aretes`, `criolla`, `zarcillos`, `aro de dedo`, `choker`, `dije`, `medalla`, `prendedor`, `alfiler`, `cordon`, `cuerda`, `bronce`, `acrilico`, `acero inoxidable`) and the `dorado` → {`dorado`, `baño de oro`, `oro`} bridge — each with its reason in the file. Record the exclusions (`piel`, `llavero`, `diadema`, `gemelos`, `cinturon`, `filigrana`) with theirs. Validate: the file parses with `yaml.safe_load` and holds ~18 entries, no more.
- [x] 1.2 Create `ai-service/src/jbg_ai/retrieval/synonyms.py` with the dictionary loader: read the closed vocabularies through `jbg_ai.enrichment.vocab.load_vocabularies()` as base classes, merge the overlay, cache with `lru_cache` like `load_vocabularies` does. Validate: a loader test asserts a base-only class (`gargantilla` → `collar`) is reachable without the overlay restating it.
- [x] 1.3 Implement the precedence rule: the overlay may add forms and create classes but MUST NOT reassign a term the base already maps. Raise a load error naming the conflicting term. Validate: `test_overlay_never_overrides_a_base_canonical`.
- [x] 1.4 Implement plural reduction on both dictionary keys and query tokens, applied only when the reduced form exists in the dictionary. Validate: `test_plural_is_resolved_without_a_dedicated_entry` covers `sortijas`, `gargantillas`, `brazaletes`, `esclavas`, `dorados`.
- [x] 1.5 Build the emission index from **surface forms with diacritics** — canonical terms from `ClosedVocab.canonical` plus overlay forms — and never from `ClosedVocab.phrases_for()`, which returns folded phrases. Validate: `test_unaccented_query_reaches_accented_surface_form` asserts `bano de oro` yields `baño de oro`.

## 2. The expansion function

- [x] 2.1 Implement `expand_query(text, *, enabled)` returning `original`, `groups` and `matched`, matching on folded text via `fold()` / `ClosedVocab.resolve()`. Validate: `test_query_with_synonym_matches_canonical_term` and `test_expansion_returns_groups_not_a_rewritten_string`.
- [x] 2.2 Implement longest-phrase-first matching so `aro de dedo` → `anillo` beats `aro` → `pendientes`. Validate: `test_longest_phrase_wins_over_shorter_token`.
- [x] 2.3 Emit unknown tokens as single-element groups in the typed form, never dropped and never guessed. Validate: `test_unknown_term_passes_through_unchanged` with `anillo Ses Salines`.
- [x] 2.4 Honour `enabled=False`: single-element groups with the original forms and an empty `matched`. Validate: `test_disabled_flag_returns_original_query`.
- [x] 2.5 Keep the function pure — no session, no provider, no socket. Validate: `test_expansion_makes_no_database_or_provider_call`, reusing the `forbid_network` fixture pattern from `tests/conftest.py`.

## 3. Settings and wiring

- [x] 3.1 Add `jpv_query_expansion_enabled` to `Settings` with default `true`, a blank-string validator matching the other optional settings, and a docstring explaining why the default lives here and the value travels by parameter. Validate: `tests/config/` asserts the default and the blank-string case.
- [x] 3.2 Pin the flag in `canonical_openapi_settings`. Validate: `test_canonical_openapi_settings_pin_query_expansion_flag`, and `test_openapi_snapshot_is_stable` stays green with no regeneration.
- [x] 3.3 Add the flag as a keyword parameter of `retrieve_products` in `retrieval/orchestrator.py`, alongside `settings`, `embed` and `search`, and call `expand_query` before the embed step. Validate: a test calls the orchestrator twice in one process with the flag on and off and both succeed.
- [x] 3.4 Pass the settings default from `api/routers/retrieval.py` without touching `RetrievalRequest`. Validate: the retrieval request schema has no expansion field and the OpenAPI snapshot is unchanged.
- [x] 3.5 Confirm the embed call still receives the **original** query text, not an expanded form. Validate: `test_vector_branch_embeds_the_original_text` asserts exactly one embedding of the untouched query.

## 4. Guard rails against the frozen boundaries

- [x] 4.1 Add a fixation test that `enrichment/vocabularies.yaml` is unchanged by this capability, so the coupling to a file owned by `enrichment/` cannot drift into an edit. Validate: `test_base_vocabulary_file_is_not_modified`.
- [x] 4.2 Add `test_excluded_false_friend_is_absent`, asserting no leather class contains `piel`, and that no class introduces a piece type absent from the enrichment vocabulary. Validate: the test names the vocabulary-gap change in its failure message.
- [x] 4.3 Verify no document is re-indexed: `doc_text`, `tsv` and `source_hash` unchanged, no Alembic revision, no EF Core migration, no PostgreSQL extension installed, no text-search configuration created. Validate: `git diff` over `indexing/` and `migrations/` is empty and `test_expansion_does_not_modify_indexed_documents` passes.

## 5. Observability

- [x] 5.1 Emit `stage=expand` from the orchestrator beside `stage=embed` and `stage=search`, carrying `trace_id`, `enabled`, `tokens`, `matched_terms` and `latency_ms`. Log the operator query only at Debug and never the full expanded classes at Information. Validate: `test_expand_stage_log_carries_trace_id` via `caplog`.
- [x] 5.2 Assert the retrieval response is byte-identical with the flag on and off while no consumer exists. Validate: `test_response_is_unchanged_while_expansion_has_no_consumer`.

## 6. Measurement and evidence

- [x] 6.1 Create the measurement entry point under `jbg_ai.retrieval` (its own `__main__`, not a subcommand of the indexing CLI), loading credentials through `jbg_ai.data.envload.load_local_env()`. It must read only — never write to the database — and skip cleanly with a clear message when no database is reachable. Validate: run it with `DATABASE_URL` absent and confirm exit without error.
- [x] 6.2 Implement the measurement: per curated query, documents matched with and without expansion; per overlay entry, documents gained. Write the versioned report to `ai-service/evals/results/`, creating the tree. Validate: the report file exists and is committed.
- [x] 6.3 Run it against the local index and confirm it reproduces the design figures — `gargantilla dorada` 0 → 64 and `collares de plata` 0 → 66. Record the run in `qa.md`. Validate: the numbers match or the discrepancy is explained in `qa.md`.

## 7. Documentation and closure

- [x] 7.1 Add the `JPV_QUERY_EXPANSION_ENABLED` row to the environment table of `ai-service/README.md`, and state there that the dictionary is curated against the corpus and not against observed demand, beside the existing limitations. Validate: the table renders and the setting name matches `Settings`.
- [x] 7.2 Link HU-AIENG-020 from `Documentos/epicas.md` under EP14, following the pattern of the neighbouring stories. Validate: the relative link resolves.
- [x] 7.3 Run the full suite and the gate: `uv run pytest` green with no provider, LLM or RDS call, and `openspec validate --all --strict` reporting `0 failed`. Validate: both commands are clean and the counts are recorded in `qa.md`.
- [x] 7.4 Confirm the cut line held: `vocabularies.yaml`, `openapi.json`, `indexing/embeddings.py`, `indexing/source_text.py`, `backend/` and `frontend/` have no diff, and nothing of C21 was brought forward. Validate: `git diff --stat` reviewed against the ticket's "explicitly untouched" list.

---

## Notas del apply (2026-09-01)

Tres cosas que la implementación descubrió y que cambiaron artefactos, registradas aquí
porque el `qa.md` las cita:

1. **La base cubría más de lo que la ficha suponía, y menos en dos puntos que nadie había
   nombrado.** Medido antes de curar el overlay: `sortija`, `alianza`, `gargantilla`,
   `brazalete`, `esclava`, `criollas`, `bano de oro`, `chapado en oro` y todos los plurales
   regulares ya casaban con la base más la singularización. En cambio **`pendiente` en
   singular no casaba** —la base sólo tiene el plural canónico, 275 documentos— y **`dorada`
   en femenino tampoco**, que es la mitad de `gargantilla dorada`. Las dos entraron al overlay.

2. **El puente entre vocabularios pasó a ser direccional.** La primera medición dio
   `bano de oro` 0 → **436**, que no era una cifra del diseño. La causa: el puente simétrico
   hacía que una consulta por el baño —420 € de media— arrastrase las **282 piezas de oro
   macizo de 587 € de media**. Y los 64 de `gargantilla dorada` vienen enteros de incluir
   `oro` (22 sin él, 64 con él), así que la dirección *color → oro* sí hace falta y la inversa
   no. Con el puente direccional `bano de oro` queda en 154 y las cinco cifras del diseño se
   conservan exactas. La spec ganó el requisito *Bridges between vocabularies are directional*.

3. **Dos correcciones de spec que el código obligó.** El requisito de artefactos del stemmer
   exigía declararlos *en el overlay*, y `collares` no lo necesita: la singularización más la
   emisión de la forma tecleada ya produce el grupo correcto. Se reescribió para exigir el
   resultado y no el mecanismo. Y *«el overlay MAY create new classes»* pasó a lo contrario:
   un canónico que la base no conoce es un hueco de vocabulario, y el cargador lo rechaza al
   arrancar nombrando `fix-enrichment-vocabulary-gaps`, lo que hace estructural la regla que
   antes era sólo un test.

**Un fallo propio que conviene no perder**, porque es exactamente el que el diseño anticipaba:
la primera versión del deduplicador plegaba con `fold()`, y así la forma tecleada `bano de oro`
**suprimía** la acentuada `baño de oro` — dejando el grupo sin la única forma que alcanza los 38
documentos. Se deduplica por mayúsculas y nunca por plegado, con el motivo escrito en el código.
