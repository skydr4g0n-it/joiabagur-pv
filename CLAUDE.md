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

## ai-service (jbg-ai)

- `uv sync` and `uv run` need `--system-certs` on this machine, otherwise PyPI fails with
  `invalid peer certificate: UnknownIssuer`.
- `ai-service/openapi.json` is a frozen contract with the .NET side. If
  `test_openapi_snapshot_is_stable` fails, the boundary moved — agree the change with
  whoever owns the .NET client before regenerating it with the README one-liner.
