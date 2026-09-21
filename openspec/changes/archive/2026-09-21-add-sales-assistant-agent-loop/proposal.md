## Why

The sale assistant has six read-only tools and a registry that verifies them, and **nothing that
decides**: C32a delivered the instrument and deliberately left the decision layer out. Of the four
things the final project evaluates in an agentic layer — the loop, the hard budget, the read-only
invariant and `partial: true` — only the third is delivered, so the capability currently cannot be
demonstrated at all.

It is needed **now** because the ablation the design asks for in §11.4 — *pipeline against agent,
same golden set, same tools* — is the row that justifies paying for autonomy, and it only exists if
the loop **coexists with** the deterministic pipeline rather than replacing it. The window is also
the cheapest one left: `POST /v1/assist/sale` still has **zero .NET consumers**, so adding a route
costs nothing today and costs a client redeploy once C34 writes one.

## What Changes

- **A new agent provider port** whose return type carries tool calls and cost and has **no field for
  free text**, so "the loop's prose is discarded" is a property of the type rather than a discipline.
  Its adapter pins temperature zero, declares no output schema, and is injectable so no test opens a
  socket.
- **A manual function-calling loop**: decide, execute the turn's tool calls **in parallel**, observe,
  decide again — until the model stops asking for tools, asks for clarification, or a budget is
  exhausted.
- **Six hard budgets** instead of the four the plan recorded: iterations, tool calls, chat-provider
  calls, tokens, accumulated context in characters, and a **wall-clock deadline**. Exhausting any of
  them serves what was gathered and declares it with `partial: true` and an explicit stop reason.
- **`POST /v1/assist/agent`**, a route of its own, carrying the **multi-turn transcript in the
  request** with the service storing nothing between calls. Every turn travels delimited as data, and
  turns attributed to the assistant are treated as client-supplied data under the same caps.
- **The intent classifier changes role on this route**: one classification per request, over the turn
  being answered. A refusal short-circuits on any turn; the clarification verdict is ignored because
  the loop owns clarification through its own tool; the index verdict is dropped because the agent
  chooses its own tool.
- **Two versioned prompts**: one for the loop and one adding an agent-evidence task section to the
  argument prompt, with the previous argument version left intact on disk.
- **A response model that extends the existing assistance response** with the partial flag, the stop
  reason, the counters, a bounded trace and a usage object that publishes the call count.
- **A real-provider measurement pass with two model arms**, which fixes the token, context and
  wall-clock budgets by measurement and answers the two questions C32a left open: whether the
  granularity of six tools is right, and whether the qualitative availability label is too coarse to
  decide the pivot to substitutes.
- **A fifth tool-failure cause** for tool calls the model requests beyond the remaining budget.
- **Not breaking.** `POST /v1/assist/sale` is untouched field for field and ceiling for ceiling; the
  OpenAPI snapshot moves by **pure addition** — no field is retired and none changes type.

## Capabilities

### New Capabilities

- `sales-assistant-agent`: the decision layer — the loop and its stop conditions, the six budgets and
  the partial declaration, the stateless multi-turn transcript and its data-delimiting rules, the
  classifier acting as an entry guardrail rather than a router, the evidence accumulator that feeds
  the generation layer, the two-form trace, the new route and its contract, and the measurement pass
  that fixes the budgets that cannot be fixed by judgement.

### Modified Capabilities

- `sales-assistant-tools`: the closed vocabulary of tool failure causes gains a fifth value for a
  call refused because the request's tool budget is spent. The requirement that a failure travels as
  an observation with a closed-vocabulary cause is unchanged in shape; what changes is the set it
  draws from, which is a spec-level fact because the vocabulary is declared closed and asserted
  exhaustively by test.

## Impact

**Affected code** — `ai-service/` only:

- `src/jbg_ai/assist/` — new modules for the port, the loop and the transcript; `constants.py`
  extended with the budgets, the two prompt versions and the fifth cause.
- `src/jbg_ai/api/` — two new contract models and the new route, plus the credential resolution for
  the agent client.
- `src/jbg_ai/evals/` — a new two-arm sweep runner following the existing assist sweep's shape.
- `prompts/` — the loop prompt (new) and the argument prompt's next version; the current argument
  version stays byte-identical on disk.
- `evals/agent/` — a synthetic load set and a hand-written calibration set, both declared as
  instruments of this change and **not** as evaluation sets.
- `tests/` — loop, transcript and route suites, all offline against injected fakes.

**Affected contract** — `ai-service/openapi.json` is regenerated for the first time since C30a.
Pure addition, verified leaf by leaf rather than assumed, with the existing assistance response
shape pinned as a set.

**Affected configuration** — a dedicated credential and model variable for the agent, resolved
through a fallback chain whose winner is logged once per process, plus the timeouts and budgets the
pass fixes. All optional at boot and all pinned in the canonical OpenAPI settings so an exported
value cannot leak into the committed snapshot. With no credential at all the route degrades rather
than failing, which is the rollback and the ablation at once.

**Not affected** — `backend/`, `frontend/`, `terraform/`, `.github/workflows/`, database migrations.
No EF Core migration. The golden set of the evaluation harness is deliberately untouched, so it
remains a clean instrument for the ablation a later change will run.

**Dependencies** — C32a (archived), and through it C30b and C31. This change blocks the two that
close the project: the evaluation change and the documentation change.
