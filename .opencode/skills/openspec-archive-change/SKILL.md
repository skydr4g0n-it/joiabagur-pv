---
name: openspec-archive-change
description: Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a change after implementation is complete.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show only active changes (not already archived).
   Include the schema used for each change if available.

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Check artifact completion status**

   Run `openspec status --change "<name>" --json` to check artifact completion.

   Parse the JSON to understand:
   - `schemaName`: The workflow being used
   - `artifacts`: List of artifacts with their status (`done` or other)

   **If any artifacts are not `done`:**
   - Display warning listing incomplete artifacts
   - Use **AskUserQuestion tool** to confirm user wants to proceed
   - Proceed if user confirms

3. **Check task completion status**

   Read the tasks file (typically `tasks.md`) to check for incomplete tasks.

   Count tasks marked with `- [ ]` (incomplete) vs `- [x]` (complete).

   **If incomplete tasks found:**
   - Display warning showing count of incomplete tasks
   - Use **AskUserQuestion tool** to confirm user wants to proceed
   - Proceed if user confirms

   **If no tasks file exists:** Proceed without task-related warning.

4. **Assess delta spec sync state**

   Check for delta specs at `openspec/changes/<name>/specs/`. If none exist, proceed without sync prompt.

   **If delta specs exist:**
   - Compare each delta spec with its corresponding main spec at `openspec/specs/<capability>/spec.md`
   - Determine what changes would be applied (adds, modifications, removals, renames)
   - Show a combined summary before prompting

   **Prompt options:**
   - If changes needed: "Sync now (recommended)", "Archive without syncing"
   - If already synced: "Archive now", "Sync anyway", "Cancel"

   If user chooses sync, use Task tool (subagent_type: "general-purpose", prompt: "Use Skill tool to invoke openspec-sync-specs for change '<name>'. Delta spec analysis: <include the analyzed delta spec summary>"). Proceed to archive regardless of choice.

5. **Perform the archive**

   Create the archive directory if it doesn't exist:
   ```bash
   mkdir -p openspec/changes/archive
   ```

   Generate target name using current date: `YYYY-MM-DD-<change-name>`

   **Check if target already exists:**
   - If yes: Fail with error, suggest renaming existing archive or using different date
   - If no: Move the change directory to archive

   ```bash
   mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>
   ```

6. **Repair the links the move just broke**

   Moving the change directory breaks every relative link that pointed at it — from
   `Documentos/Historias/AI-Eng/HU-*.md`, from `Documentos/epicas.md`, from reports.
   Nothing surfaces this, so it accumulates silently: on 2026-09-12 a full audit found
   **61 broken links**, most of them tickets of changes archived weeks earlier.

   Run the checker from the repository root:

   ```bash
   pwsh <skill-dir>/scripts/check-doc-links.ps1          # report only, exit 1 if any break
   pwsh <skill-dir>/scripts/check-doc-links.ps1 -Fix     # apply the repairs
   ```

   `<skill-dir>` is the folder holding this SKILL.md; the skill is replicated across the
   repo's harnesses (`.agent/`, `.claude/`, `.codex/`, `.cursor/`, `.github/` and
   `.opencode/skills/openspec-archive-change/`), so use your environment's copy.

   It only rewrites a link whose corrected target **exists on disk** — an archived change
   resolved through `openspec/changes/archive/`, or a relative depth that resolves at
   exactly one level. Anything ambiguous is reported and left alone, because guessing a
   target hides the breakage instead of fixing it.

   **Report what it could not resolve** in the summary rather than silently accepting it.
   `Documentos/prompts.md` and `openspec/changes/archive/**` are excluded by design: they
   are dated records, and repointing their links would rewrite history rather than repair it.

7. **Display summary**

   Show archive completion summary including:
   - Change name
   - Schema that was used
   - Archive location
   - Whether specs were synced (if applicable)
   - How many documentation links were repaired, and any the checker could not resolve
   - Note about any warnings (incomplete artifacts/tasks)

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<name>/
**Specs:** ✓ Synced to main specs (or "No delta specs" or "Sync skipped")
**Links:** ✓ N repaired, 0 unresolved (or "No broken links")

All artifacts complete. All tasks complete.
```

**Guardrails**
- Always prompt for change selection if not provided
- Use artifact graph (openspec status --json) for completion checking
- Don't block archive on warnings - just inform and confirm
- Preserve .openspec.yaml when moving to archive (it moves with the directory)
- Show clear summary of what happened
- If sync is requested, use openspec-sync-specs approach (agent-driven)
- If delta specs exist, always run the sync assessment and show the combined summary before prompting
- Always run the link checker after the move — the archive is what breaks those links, so
  leaving them for someone else is how 61 of them accumulated unnoticed
- Never hand-edit a link the checker declined to resolve without confirming the target first
