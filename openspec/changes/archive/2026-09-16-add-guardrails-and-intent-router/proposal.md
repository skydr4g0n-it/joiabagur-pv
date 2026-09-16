## Why

The service can generate prose but cannot decide whether it should: C30b's abstention cut is a net that reads the *shape* of a candidate profile after retrieving, not a classifier, and measured it fires on only **2 of the 20** out-of-domain queries — so **18 of 20** reach the generation layer with candidates. Worse, the card that motivates this change conflates two different failures under one name: *«this is not a jewellery question»* (5 cases exist, in the knowledge fixture) and *«this is jewellery and **this** catalogue does not stock it»* (the golden set's largest category, 20 of 72, all of them silverware, watchmaking, stationery and numismatics). A pure intent classifier answers **yes** to all twenty and moves neither figure, so this change delivers **two gates** and publishes **two figures that are never summed**.

## What Changes

- **Intent router on the free-query mode**, deciding on three axes before any retrieval runs: whether the request is served (`in_domain` / `out_of_domain` / `not_in_catalogue`), which index answers it (`catalog` / `knowledge` / `both`), and whether the query carries enough to search at all. **One provider call, no repair.**
- **Polite refusal as safe-completion**, not a blank success: a closed-vocabulary reason code on the wire, Spanish copy in the presentation layer — the rule `assisted-search-panel` already states for match reasons.
- **`clarification_question` stops being permanently null**, resolved from a **closed catalogue of Spanish templates selected in code** from the axis the query left out. Its evaluation set already exists: the four `ambigua` golden queries declared unjudged because *«the correct answer is a follow-up question»*.
- **Free deterministic guardrail on the piece-anchored question mode**: zero citations after the knowledge distance threshold already means the corpus does not cover the question, and today nothing reads it as such. **No extra provider call.**
- **The free-query mode generates prose**, which C30b deferred here — with a payload shape that does not exist today and its own numeric-whitelist policy.
- **Prompt version `assist/v2`** adding per-route task sections; `assist/v1` is preserved so C30b's 120 measured generations stay interpretable. **Amended by the implementation:** the measurement of the free-query gate refuted one of v2's task sections — the `catalog` route hands the model an empty corpus list and the section said nothing about citations, so the model declared invented ones — and the served version is **`assist/v3`**. **Both earlier versions are preserved**, for the same reason v1 is: v2 is the version whose measurement produced v3.
- **Fail-open is a declared behaviour, not an accident**: with no classifier the reported intent returns to the unclassified value and the system behaves exactly as it does today.
- **A literal ceiling of three provider calls per request** (one router, at most two pitch), observable the way C30b's ceiling of two is.
- **Three new optional settings** for the classifier's model, credential and timeout, with the credential falling back through the chain C30b opened.
- **Routing evaluation** over the manifest in `ai-service/evals/routing/cases.yaml`: 109 pre-existing cases referenced rather than copied, plus 10 newly written compound cases.
- **BREAKING (behaviour, not shape)**: a free-text query the router refuses returns **no groups** where today it returns up to five. The response schema does not move — `intent` is a plain string and `clarification_question` already exists — so `openapi.json` changes only in **descriptions**. The route has **zero consumers** today, which is why this change lands before the .NET endpoints.

## Capabilities

### New Capabilities

None. The router adds requirements to the capability C30a created and C30b extended, for the same reason C30b gave: the behaviour belongs to the same served route and the same response contract.

### Modified Capabilities

- `assist-generation`: the intent value stops being derived solely from the request shape and becomes a routing verdict on the free-query mode; the prohibition on calling a provider in that mode is **removed**; the clarification question stops being required absent and gains its resolution rule; new requirements cover the two refusal classes, the deterministic corpus-coverage guardrail on the anchored question mode, fail-open, the three-call ceiling, and the separation between the router's refusal and the retrieval abstention flag.

## Impact

- **`ai-service/src/jbg_ai/assist/`** — new modules for the classifier client, its closed-vocabulary output schema, the clarification templates and the free-query payload; wiring in `orchestrator.py`; new constants.
- **`ai-service/prompts/assist/`** — `v2.md` added, `v1.md` untouched.
- **`ai-service/src/jbg_ai/api/schemas/assist.py`** — field **descriptions** only.
- **`ai-service/src/jbg_ai/config/settings.py`** — three optional settings, defaults supplied from the constants module.
- **`ai-service/openapi.json`** — regenerated; verified leaf by leaf that no field is added, removed or retyped.
- **`ai-service/evals/routing/`** — manifest loading and the confusion-matrix runner; artefacts under `evals/results/`.
- **`openspec/DEFERRED_TASKS.md`** — the deployment steps for the new settings, following the pattern C30b established.
- **Not touched on purpose**: `backend/`, `frontend/`, `terraform/`, `.github/workflows/`, `ai-service/migrations/`, `retrieval/` and `enrichment/`. `knowledge/` is read, never modified.
- **No database change and no migration**: neither the routing verdict nor the clarification question is persisted.
- **Downstream**: unblocks C32 (agent loop); C34 gains a noted .NET route for the free-query mode and C36 two rows in its copy table, both recorded in their plan cards rather than implemented here.
