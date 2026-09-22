# CLAUDE.md

Guidance for Claude Code in this repository. Full project context lives in
[openspec/project.md](openspec/project.md); functional and architectural docs in
[Documentos/](Documentos/).

## OpenSpec validation

`openspec validate` needs a target. Three forms, and only one of them is the project gate:

| Command | Scope |
|---|---|
| `openspec validate --all --strict` | **The project gate.** Every spec and every active change. Must report `0 failed` |
| `openspec validate <change-name> --strict` | One change, while it is in progress |
| `openspec validate` / `openspec validate --strict` | **Validates nothing.** Prints the alternatives and exits 1 — never read this as a pass |

Run `--all --strict` before archiving a change, not just the single-change form: a
change can be green while the live specs it syncs into are broken. That is exactly how
three malformed specs survived unnoticed until 2026-08-06.

### El validador lee sólo la PRIMERA LÍNEA FÍSICA de la descripción de un requisito

Esto cuesta una sesión la primera vez. En una delta, la descripción que sigue a
`### Requirement: …` se valida **leyendo únicamente su primera línea física**. Si editas una
spec y el `SHALL` cae en la segunda línea por un ajuste de ancho, falla con
*«must contain SHALL or MUST»* **aunque lo contenga**, y el mensaje no da ninguna pista de que
el problema es tipográfico.

Las deltas se escriben con la descripción en **una sola línea larga**, sin ajustar a 90
columnas, exactamente como están las archivadas. Los párrafos siguientes sí pueden ajustarse:
la regla sólo afecta al primero.

## Live specs vs delta specs

Delta syntax belongs **only** to a change, never to a live spec:

- `openspec/changes/<name>/specs/<capability>/spec.md` — uses `## ADDED Requirements`,
  `## MODIFIED Requirements`, `## REMOVED Requirements`, `## RENAMED Requirements`
- `openspec/specs/<capability>/spec.md` — must start with `# <capability> Specification`,
  then `## Purpose`, then `## Requirements`, then the `### Requirement:` blocks

A live spec containing `## ADDED Requirements` is a broken sync, not a style choice: it
means delta files were copied verbatim into `openspec/specs/` instead of being merged.
`--all --strict` catches it via the missing `## Purpose` section.

## Backend test suite: a red count is not a regression signal

`dotnet test` on this repository comes back with **dozens of failures that were already
there**. They are not yours. Never conclude you broke something from the count alone, and
never spend a session "fixing" them without being asked — but never wave them away either:

| Step | Command |
|---|---|
| Measure the baseline first | `git stash push -u`, run the suite, `git stash pop` |
| Compare | your change is clean if the failing **test names** are the same set, not if the number matches |

The number alone is unreliable: a handful of these failures are genuinely order-dependent, so
two runs of identical code disagree. Compare names.

Two of those failures are traps you will fall into yourself the first time you write a test
here, because they look like application bugs and are not:

- **"Expected 401 but found 200/403/201".** The shared `HttpClient` a test class uses to log in
  keeps the cookies of every login it performed, so it is not anonymous. Ask the factory for a
  fresh client to assert an unauthenticated call.
- **`22001: value too long for type character varying(20)`.** The object mothers generate data
  with Bogus, and a generated phone number does not always fit `PointOfSale.Phone`. Pin the
  field explicitly (`.WithPhone("600123456")`) instead of leaving it to chance.

The full inventory — root causes, and why a tree of 270 tests went unrun for weeks — is under
*Estado de la suite: fallos conocidos* in [Documentos/testing-backend.md](Documentos/testing-backend.md).

## Frontend test suite: same story, and it catches people out harder

`npm run test` in `frontend/` **also comes back red before you touch anything**: measured on
2026-09-13, **113 failures of 595 tests, across 14 of the 48 files** (it was 118 of 482 on
2026-08-29 — the suite grew and the red did not). The method is identical to the backend's —
baseline first, then compare the failing **test names**, never the count.

Unlike the backend's, **this set of names is stable between runs**: C28 measured an identical
113 names at baseline and at close. Compare by name here because the *count* moves whenever
somebody adds tests, not because the set rotates.

It catches people out harder than the backend one for two reasons. Nobody expects a frontend
suite to be red, and `vitest` exits **0** when you pipe it (`npm run test | tail` reports the
exit code of `tail`), so a green shell prompt says nothing at all. Read the summary line.

Three traps, all of which look like your bug and are not:

- **`useCart must be used within a CartProvider`** (and `useAuth` / `AuthProvider`). Rendering a
  page component drags in whatever context it consumes. This alone accounts for roughly a third
  of the red: `pages/sales/__tests__/new.test.tsx` fails **11 of 11** and
  `pages/products/edit.test.tsx` **27 of 27**, for nothing but this. Wrap in the provider, or
  mock the hook — `pages/sales/__tests__/cart.test.tsx` is the file to copy.
- **MSW does not fail an unhandled request.** `src/test/setup.ts` starts the server with
  `onUnhandledRequest: 'warn'`, so a call with no handler prints a warning and returns nothing.
  A test can pass having asserted nothing at all. Declare handlers explicitly, or mock the
  service module with `vi.mock` — which is what the service tests here already do.
- **`tsc --noEmit` is not a gate.** It reports dozens of pre-existing errors in the Metronic
  template files (`lucide-react` missing exports, absent modules, `chart.tsx`). Filter its output
  to your own files. The real gate is `npm run build`.

The full inventory — the five root causes and which files each one accounts for — is under
*Estado de la suite: fallos conocidos* in [Documentos/testing-frontend.md](Documentos/testing-frontend.md).

## ai-service (jbg-ai)

- `uv sync` and `uv run` need `--system-certs` on this machine, otherwise PyPI fails with
  `invalid peer certificate: UnknownIssuer`.
- **`--system-certs` arregla a `uv`, no al proceso Python.** En tiempo de ejecución `litellm`
  sale por `aiohttp`/`httpx`, que usan el bundle de `certifi` y **no** el almacén de Windows, y
  esta máquina tiene un MITM de **Norton Web/Mail Shield** cuya raíz vive sólo en ese almacén.
  Cualquier llamada real al proveedor —un spike, una pasada de `evals`, un `sync` de índice—
  muere con `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. La salida:
  exportar el almacén a un PEM y apuntar `SSL_CERT_FILE` (y `REQUESTS_CA_BUNDLE`) a él.
  `ssl.enum_certificates('ROOT'|'CA')` concatenado al `certifi.where()` basta. **Filtrar por la
  bandera de confianza no basta**: la raíz de Norton no la lleva y el bundle sale incompleto.
  **No afecta a ningún test** — ninguno llama al proveedor. **Tampoco afecta a los contenedores**:
  desde Docker el TLS del proveedor y de PyPI se verifica con el bundle del sistema y lo firma la CA
  real (comprobado en C34, §2.8 de su informe), así que medir con `jbg-ai` en Compose no necesita PEM.
- **Windows: `psycopg` rechaza el `ProactorEventLoop`**, que es el que Python instala por
  defecto. Cualquier script suelto que abra el motor asíncrono necesita
  `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`. En los tests eso ya
  lo resuelve `support/async_db.run_db`, que además dispone el motor a ambos lados: el motor es
  de proceso y sus conexiones pertenecen al bucle que las abrió, así que **dos `asyncio.run` en
  un mismo test fallan con `InterfaceError`**. Un escenario, un bucle.
- `ai-service/openapi.json` is a frozen contract with the .NET side. If
  `test_openapi_snapshot_is_stable` fails, the boundary moved — agree the change with
  whoever owns the .NET client before regenerating it with the README one-liner.
