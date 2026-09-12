# jbg-ai test layout

The test tree **mirrors the `src/jbg_ai/` package**. One rule decides where a test
goes: *which module owns the behaviour under test?* That answer never changes when
a change is archived, so the layout survives C01 → C39 without renaming anything.

Tests are deliberately **not** organised by OpenSpec change. A change is a unit of
work, not a unit of behaviour: `test_openapi_snapshot_is_stable` was written in C02
but guards every change after it, and C22 edits code first shipped by C14. Change
traceability lives in the module docstring (`Delivered by C02.`), where it costs
nothing and cannot rot into a wrong folder name.

## Layout

```text
tests/
├── README.md
├── conftest.py       # global fixtures only — never import from it (see Support)
├── support/          # importable helpers and injectable fakes
├── fixtures/         # test data: payloads, golden set, corpus samples
├── api/              # HTTP surface: routing, auth, contracts, stubs, OpenAPI snapshot
├── config/           # settings loading and fail-fast validation
├── db/               # engine, connection pool, lazy construction
├── migrations/       # Alembic upgrade/downgrade, schema `ai`, index definitions
├── data/             # catalog corpus and synthetic world generators
├── enrichment/       # LLM extraction, closed vocabularies, per-field confidence
├── families/         # name-root grouping, material fusion, guards, relative embedding veto
├── indexing/         # source text, hashing, embeddings, upsert, drift
├── retrieval/        # vector/lexical search, RRF, filters, ranking, substitutes
├── assist/           # generation, guardrails, agent loops, inventory proposals
└── evals/            # harness, metrics, baselines, scenario replays
```

Folders are created **on demand**, not up front. `api/`, `config/`, `support/`, `db/`, `migrations/`, `data/`, `enrichment/`, `families/`, `indexing/`, `retrieval/`, `knowledge/` and `evals/` are populated; the rest are reserved names so nobody invents a
parallel taxonomy later.

## Which folder for which change

| Folder | Changes that will land here |
|---|---|
| `api/` | C01 (health), C02 (contracts, service auth, stubs, snapshot), C08 (enrichment provenance, catalog-scoped auth), C13 (landed: `/v1/index/*` real), C14 (landed: `/v1/retrieval/products` real), C17 (landed: enriched `/health` — database, index, provider credential, model contrast), C18b (landed: `POST /v1/families/audit` — tenth route, service token, judged pairs travelling in the request) |
| `config/` | C01, C02 (settings, canonical OpenAPI profile), C13 (feed settings) |
| `db/` | C05 (engine, bounded pool, boot without a database) |
| `migrations/` | C05, C13 (landed: `text_provenance`, `sync_checkpoint`), C18b (landed: Alembic logging isolation — `fileConfig` must not disable the service loggers, which is destructive in-process and invisible under the CLI), C22 (landed: `pos_projection.computed_as_of` — one additive nullable column, and a test that the revision touches nothing else), C24 (landed: `ai.eval_run` / `ai.eval_case` / `ai.eval_result` — the provenance tuple a run is compared by, the CHECK that keeps a result unjudged exactly when it carries no grade, and a downgrade that leaves no trace) |
| `data/` | C06b (landed: generate/ingest CLI), C10 (landed: `world/`) |
| `enrichment/` | C09, FIX1 (landed: the four widened `piece_type` canonicals and their folding, the prompt whose heading must match `PROMPT_VERSION`, the prompt list pinned against the YAML, and the null that is an outcome and not a rejected extraction) |
| `families/` | C18a (landed: root grouping, material fusion, guards, relative veto, `POST /v1/families/suggest`), C18b (landed: audit over persisted families, orphan nomination by relative margin, source guards that the audit writes nothing and calls no provider) |
| `indexing/` | C11 (landed: source-text/v1 + embeddings), C13 (landed: catalog drain + `sku_provenance.json`), C22 (landed: typed POS feed items, the `ai.pos_projection` repository whose tombstone is a soft delete, and the POS drain with its own `pos-availability` checkpoint and per-page failures), C23 (landed: the `sync-knowledge` subcommand only — everything it drives is tested in `knowledge/`) |
| `retrieval/` | C14, C20 (landed: two-layer synonym dictionary, equivalence-group expansion, directional bridges, the enable flag swept in-process, and the measurement CLI's safe `tsquery` composition), C21 (landed: safe `tsquery` composition with coordination ordering, weighted RRF over three ranked lists, structural filters that demote and never exclude, and the bounded cache of the embedding singleton), C22 (landed: the point-of-sale scope as the only hard filter, availability as the last demotion block, freshness read from the checkpoint and never from the rows, and the 503-on-empty / degrade-on-stale pair), FIX1 (landed: the four closed gaps gone from the exclusions, the guard test re-aimed at `filigrana`, and the plural canonical reached from its singular), C24 (landed: the deterministic tiebreak both statements needed — the compiled `ORDER BY` asserted key by key so removing it from the SQL breaks the test, and truncation proved stable where distance ties and where `coordination` and `ts_rank` tie together), C25, C26, C27 |
| `knowledge/` | C23 (landed: the seven authoring rules and the coverage invariant derived from the enrichment vocabulary, pure section chunking, deterministic `uuid5` identity whose citations resolve to a file and a heading of `data/knowledge/`, idempotent indexing that re-embeds nothing unchanged, the callable search with its own abstention threshold, the D16 ring-size table, and the offline fixture measurement) |
| `assist/` | C30, C31, C32, C33, C35 |
| `evals/` | C24 (landed: the golden set validation that **fails the load** when the composition stops being able to arbitrate what the set exists for, adaptive-depth pooling with appendable judgements, nDCG against a hand-computed fixture with the binary reading beside it, the two `v0` baselines and the guard that breaks when the canonical renderer drifts, deterministic truncation of the context-only catalogue with the omitted count recorded, provenance-gated comparability over frozen query vectors, and the default-change rule exercised in all four of its outcomes), C38 |

Changes with no Python zone (C03, C04, C07, C08, C12, C15, C16, C19, C28, C29,
C34, C36, C37) are tested on the .NET or frontend side. C17 also ships a post-deploy smoke
check that belongs to the deployment pipeline rather than here — but it does have a
Python zone after all: the enriched `/health` is tested in `api/test_health_report.py`,
with its probe double in `support/fake_health_probe.py`.

Source: [`proyecto-final-plan-changes-openspec.md`](../../Documentos/Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md).

## Where does my test go?

Ask what would have to break for the test to fail:

- **A wire contract** — status code, payload shape, auth decision, mounted route →
  `api/`, even when the endpoint belongs to another domain. `test_assist_stub.py`
  lives in `api/` because it asserts the frozen contract, not sales reasoning.
- **A computation** — ranking order, similarity, extracted fields, metrics →
  the module that computes it. When C30 replaces the assist stub with real
  generation, the behavioural tests are born in `assist/`; the contract test stays
  in `api/`.
- **Both** — split it. A contract assertion buried in a ranking test makes the
  contract regression invisible.

## Support vs fixtures

- `support/` holds **code**: request builders, token helpers, and the injectable
  fakes that stand in for LLM and embedding clients. Importable from any test
  (`tests/` is on `pythonpath`).
- `fixtures/` holds **data**: request/response payloads, golden-set entries, corpus
  samples. The changes plan already fixes this path for evaluation fixtures.

`conftest.py` is pytest's fixture mechanism, **not** a module to import. Today four
test files do `from conftest import build_settings` / `from sample_requests import
V1_REQUESTS`; those imports only resolve because every test sits in one flat
directory and break the moment subfolders exist. They move to `support/`.

## Conventions

- **Naming**: `test_<unit>_<scenario>_<expected>` — the Python convention fixed in
  the changes plan, distinct from .NET (`Method_Scenario_ExpectedResult`) and the
  frontend (`should [behavior] when [condition]`).
- **Module docstring**: one line saying what the file guards, plus the delivering
  change. Example: `"""Frozen /v1 contract shapes. Delivered by C02."""`
- **Local fixtures** go in a `conftest.py` inside the folder that needs them — until a
  second folder needs the same one. The ephemeral-PostgreSQL fixtures (`postgres_container`,
  `database_url`, `alembic_config`, `migrated`) lived in `migrations/conftest.py` until C22,
  when the projection repository needed them from `indexing/`; they moved to the root
  `conftest.py` and `migrations/conftest.py` kept only what is its own (`database_name`,
  `run_bootstrap`).
- **Markers**: everything is a fast in-process unit test by default. Declare the
  exceptions — `@pytest.mark.db` for tests needing PostgreSQL with pgvector,
  `@pytest.mark.slow` for evaluation sweeps — so CI can select them.

## Hard rules

No test calls a real LLM provider, embedding API, or production RDS. Fakes are
injected from `support/`; the `forbid_network` fixture turns any socket connection
into a failure, and stub tests use it to prove they stay offline.

```bash
cd ai-service
uv run --system-certs pytest
```

## Current state

Populated after C24: `api/`, `config/`, `db/`, `migrations/` (C05 + C13 + C18b + C22 + C24), `data/` (C06b/C10), `enrichment/` (C09 + FIX1), `indexing/` (C11 + C13 + C22), `families/` (C18a + C18b), `retrieval/` (C14 + C20 + C21 + C22 + FIX1 + C24), `knowledge/` (C23), `evals/` (C24) and `support/`. Remaining folders are reserved names. Two settings in
`pyproject.toml` hold the layout together:

- `pythonpath = ["src", "tests"]` — makes `support/` importable from any subfolder.
- `addopts = "--import-mode=importlib"` — stops same-named test modules in
  different folders from colliding.

Never anchor a path with `Path(__file__).parents[N]` in a test file: the count is
wrong as soon as the file changes depth. Import from `support/paths.py` instead,
which is where `AI_SERVICE_ROOT`, `OPENAPI_SNAPSHOT`, `ALEMBIC_INI` and
`MIGRATIONS_DIR` are resolved once.

`build_settings()` in `support/settings.py` pins `database_url` to `None`. That is
not decoration: pydantic reads unset fields from the environment, so without the
pin a developer with `DATABASE_URL` exported would see tests build engines against
their own database — and the cases that assert "no database configured" would
quietly stop failing when they should.

## C25 — ranking, business signals and abstention

`tests/retrieval/test_abstention.py` is new and owns the rule that declines to answer: the shape
of the distance profile, what the rule must never do, and the observability. Its fixtures carry
**twenty** candidates rather than ten, because a profile cannot be flat against a rule that asks
for fifteen and a test that passed on that technicality would witness nothing.

The rest extends files that already existed:

| file | what C25 added |
|---|---|
| `test_fusion.py` | that `fuse` composes with itself without touching the formula, and that the flat mode is bit-identical to C21's single stage |
| `test_orchestrator.py` | the two-stage fusion, the coverage rule and its **gate** |
| `test_pos_scope.py` | the reading scope against the restricting one, and the business score |
| `test_filters.py` | the ordering key with a continuous tail |
| `test_sweep_phases.py` | capture and re-score, and that the second reaches no provider and no database |
| `test_provenance_and_report.py` | the fusion mode as the sixth element of the provenance, the dirty-tree marker, and that the published table carries no withdrawn claim |
| `test_golden_validation.py` | the out-of-domain category at its new floor of twenty |

**The gate is `test_full_coverage_leaves_the_lexical_weight_untouched`.** It covers five
categories measured at coverage 1,00, and each of its five queries is a **real** query of the
golden set chosen because the naive denominator breaks it. Verified by injecting that
denominator: all five fail. A gate that cannot fail is not a gate.

**C22's sales guard was retired and replaced.** It forbade `sales_30d`, `sales_90d` and
`last_sale_at` from reaching the pipeline at all. `sales_30d` now travels — the report publishes
its distribution and C26 needs it — so the guarantee moved to where it can still be structural:
**the protocol the ordering reads does not carry the field**, so `demote` cannot consume it even
by accident. The other two still never reach the pipeline, and no ordering module may reach for a
wall clock.

