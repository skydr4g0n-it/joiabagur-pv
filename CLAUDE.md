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

## ai-service (jbg-ai)

- `uv sync` and `uv run` need `--system-certs` on this machine, otherwise PyPI fails with
  `invalid peer certificate: UnknownIssuer`.
- `ai-service/openapi.json` is a frozen contract with the .NET side. If
  `test_openapi_snapshot_is_stable` fails, the boundary moved — agree the change with
  whoever owns the .NET client before regenerating it with the README one-liner.
