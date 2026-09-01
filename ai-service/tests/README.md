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

Folders are created **on demand**, not up front. `api/`, `config/`, `support/`, `db/`, `migrations/`, `data/`, `enrichment/`, `families/`, `indexing/` and `retrieval/` are populated; the rest are reserved names so nobody invents a
parallel taxonomy later.

## Which folder for which change

| Folder | Changes that will land here |
|---|---|
| `api/` | C01 (health), C02 (contracts, service auth, stubs, snapshot), C08 (enrichment provenance, catalog-scoped auth), C13 (landed: `/v1/index/*` real), C14 (landed: `/v1/retrieval/products` real), C17 (landed: enriched `/health` — database, index, provider credential, model contrast), C18b (landed: `POST /v1/families/audit` — tenth route, service token, judged pairs travelling in the request) |
| `config/` | C01, C02 (settings, canonical OpenAPI profile), C13 (feed settings) |
| `db/` | C05 (engine, bounded pool, boot without a database) |
| `migrations/` | C05, C13 (landed: `text_provenance`, `sync_checkpoint`), C18b (landed: Alembic logging isolation — `fileConfig` must not disable the service loggers, which is destructive in-process and invisible under the CLI) |
| `data/` | C06b (landed: generate/ingest CLI), C10 (landed: `world/`), C23 |
| `enrichment/` | C09 |
| `families/` | C18a (landed: root grouping, material fusion, guards, relative veto, `POST /v1/families/suggest`), C18b (landed: audit over persisted families, orphan nomination by relative margin, source guards that the audit writes nothing and calls no provider) |
| `indexing/` | C11 (landed: source-text/v1 + embeddings), C13 (landed: catalog drain + `sku_provenance.json`), C22, C23 |
| `retrieval/` | C14, C20 (landed: two-layer synonym dictionary, equivalence-group expansion, directional bridges, the enable flag swept in-process, and the measurement CLI's safe `tsquery` composition), C21, C22, C25, C26, C27 |
| `assist/` | C30, C31, C32, C33, C35 |
| `evals/` | C24, C38 |

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
- **Local fixtures** go in a `conftest.py` inside the folder that needs them (a
  database fixture belongs to `migrations/conftest.py`, not to the global one).
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

Populated after C14: `api/`, `config/`, `db/`, `migrations/`, `data/` (C06b/C10), `enrichment/` (C09), `indexing/` (C11 + C13), `families/` (C18a + C18b), `retrieval/` (C14 + C20) and `support/`. Remaining folders are reserved names. Two settings in
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
