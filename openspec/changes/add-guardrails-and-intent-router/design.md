## Context

C30b left `POST /v1/assist/sale` writing prose in the two piece-anchored modes, with three deterministic checks over what the model produced. What it did not leave is a decision about the *query*: the abstention rule of C25 runs after retrieval and reads the shape of the distance profile, which the live spec itself calls a net rather than a classifier.

Three measured facts constrain every decision below.

**One — the two meanings of «out of domain».** The card motivating this change quotes *«what's the weather tomorrow»* and supports it with *«18 of 20 out-of-domain queries arrive with candidates»*. Those two halves describe different sets. The twenty are `un salero de plata`, `un lingote de oro`, `una correa de reloj marron`, `un joyero de viaje para los anillos` — silverware, watchmaking, stationery, numismatics — and `criterion.md` states it outright: *«they are plausible **within jewellery** and the catalogue cannot satisfy them»*. A classifier asking *«is this a jewellery question?»* answers **yes** to all twenty. The distinguishable-without-retrieval set has **five** members and lives in `data/knowledge/_eval/out-of-domain.yaml`.

**Two — the latency budget is already tight.** `AssistTimeoutMs` is **5.000 ms**; the retrieval costs **129 ms**; one generation call measured **p50 2.216 / p95 2.863 ms** over 175 real calls, and **55 %** of requests spend the repair. A repaired request is therefore already around **4.400 ms**. The headroom for anything placed in series ahead of it is hundreds of milliseconds, not a second.

**Three — a deterministic out-of-domain detector for questions already runs.** C23 fixed `jpv_knowledge_distance_threshold = 0,51` on a **clean gap of eight thousandths**: the 32 questions the corpus answers fall below, the 5 outsiders above — 100 % and 0 %. Today the anchored question mode generates identically when zero citations come back, and no consumer can tell.

## Goals / Non-Goals

**Goals:**

- Classify a free-text query and refuse it politely **before any retrieval runs**, covering both the domain gate and the catalogue-coverage gate.
- Emit a clarification question when the query does not carry enough to search, deterministically.
- Detect, at zero cost, that the corpus does not cover an anchored question.
- Generate prose in the free-query mode, which C30b deferred here.
- Publish the router's refusal rate and the retriever's abstention rate **as two separate figures**, and the false-positive rate over answerable queries as a third.
- Degrade to today's exact behaviour when the classifier is unavailable.

**Non-Goals:**

- Systematic adversarial and injection cases — those are C38's 20-25 cases. The structural mitigation is already delivered by C30b and is **not rebuilt**.
- Semantic fidelity of citations (RAGAS `faithfulness`) — C38, and still declared as a limitation.
- The agent loop, its tools and its hard budget — C32. Its `pedir_aclaracion` tool is a different thing from this `clarification_question`.
- Any .NET route or screen for the free-query mode — noted on C34's and C36's cards, not built here.
- Moving the shape of the frozen contract, or the published v0→v3 ablation table.
- Any database change, entity, index or EF Core migration.

## Decisions

### D1 · Two gates with two names, and two published figures

The router classifies both *domain* (not a jewellery question) and *catalogue coverage* (jewellery this shop does not stock). The retriever's abstention rate stays where it is and is reported unchanged; the router's refusal rate is a new figure beside it, and the report states they are **not summable**.

*Alternatives considered.* **Domain only** — cheap and safe, but leaves the figure the card uses to justify itself untouched and would require amending that justification. **Coverage only** — one mechanism, one figure, but loses the distinction between *«not our trade»* and *«our trade, not our stock»*, which are two different things to say to a customer standing at the counter.

*Why the coverage gate is tractable at all:* the distinction is a question about the requested **object** against the twelve closed `piece_type` terms of `enrichment/vocabularies.yaml`, not a question about intent. A lexical rule dies here on purpose — `pulsera` and `anillos` appear literally inside two of the twenty — and so does its mirror image, since the twelve `descripcion-sin-anclaje` queries name no piece type at all.

### D2 · The classifier costs one provider call, and only in the free-query mode

The anchored-piece mode has no query to classify. The anchored-question mode is `both` **by construction** — the piece is the catalogue side and the question the corpus side — and the router could not refuse there without refusing a legitimate piece.

*Alternatives considered.* **Classify in all three modes** — uniform, and blows the budget of fact two above for the one mode that has a .NET consumer. **Run the classifier concurrently with retrieval** (`asyncio.gather`) — costs `max(router, retrieval)` instead of the sum, but breaks the card's *«refuse before calling the retriever»*, and 129 ms does not buy breaking a property whose value is that the guardrail is visibly prior.

### D3 · The anchored-question guardrail is the existing threshold, not a new call

Zero citations after `0,51` means the corpus does not cover the question. This becomes a warning code and a degraded task section.

*Alternative considered.* **A router call in that mode too** — same information, one more round trip inside the mode that is already closest to the 5 s ceiling. It also yields a free by-product: the router and the threshold give **two independent opinions** on the same question, and their disagreement measures the eight-thousandth margin whose own report called it narrow *«and by construction»*.

### D4 · The verdict travels in `intent`; the reason as a code in `warnings[]`; the question in `clarification_question`

All three fields already exist with the right types, so `openapi.json` moves only in **descriptions** — the same single-description move C30b made. `product_pitch` survives untouched, exactly as `assist/modes.py` promised: *«that router will replace `unclassified`, never `product_pitch`»*.

*Alternative considered.* **A dedicated `refusal_reason` field** — more explicit, at the cost of regenerating the contract for a *shape* rather than a description. Rejected while the cheaper option carries the same information; the route has zero consumers today, so the option stays open if a consumer later needs it.

### D5 · `abstained` is never reused for the router's refusal

They are two mechanisms: one reads the distance profile *after* retrieving, the other classifies *before*. Collapsing them would make the published 0,10 indistinguishable from the new figure and destroy the very distinction D1 exists to deliver.

### D6 · `unclassified` gains a second, honest meaning, and the router fails open

With no credential, a provider fault, a timeout or an unparseable reply, the reported intent returns to `unclassified` and the request proceeds exactly as it does today, with the degradation logged. The value stops meaning *«we do not classify yet»* and starts meaning *«we could not classify this time»* — true in both eras.

*Alternative considered.* **Fail closed** — defensible for a safety gate in the abstract, and here it would turn a provider blip into a universal polite refusal, i.e. a total outage of the useful path. Failing open degrades to a shipped, tested, declared behaviour. It is logged rather than silent.

### D7 · The clarification question is chosen by code from a closed catalogue of templates

The contract types the field as **prose**, so the presentation layer cannot resolve a code. The classifier returns the missing axis; Python selects the Spanish sentence.

*Alternatives considered.* **The field carries a code** — contradicts its type and its name. **The model writes the sentence** — model prose reaching the operator outside every gate, and a question like *«something under 50 €?»* carries a figure nobody checked. The chosen option also makes the four `ambigua` queries judgeable deterministically: not *«is the sentence good?»* but *«did it pick the missing axis?»*.

### D8 · One router call, no repair; the system ceiling becomes a literal three

There is nothing to repair in a label: an unparseable reply is a fail-open, not a violation. Combined with C30b's ceiling of two, one request makes **at most three** provider calls, observable by introspection.

*Consequence, and it settles the card's conflict:* C30b's measured decision **not** to retry on a parse failure stands, and the card's `..._triggers_single_retry_then_safe_error` is amended. A backoff or a third call would consume the budget of fact two before the retried call started.

### D9 · The classifier gets its own model setting, and the credential falls back

`JPV_ROUTER_LLM_MODEL` defaults to `openai/gpt-4o-mini` from a module constant and **never inherits** `JPV_ASSIST_LLM_MODEL` or `JPV_RAG_LLM_MODEL` — the same measured argument C30b used against inheriting C09's: these are calls of very different shape (~30 output tokens against a paragraph), and sharing a variable would make any cost comparison false. `JPV_ROUTER_LLM_API_KEY` falls back to the assist key and then to the RAG one, and which is in force is logged once per process.

### D10 · The prompt becomes `assist/v2`, and `v1` is preserved

Adding task sections to `v1.md` would silently change what «v1» means for C30b's 120 measured generations. A new version keeps those figures interpretable and delivers, as a by-product, the **v1→v2 prompt progression** that C39 asks for in writing and that nothing else in the graph was going to produce.

### D11 · The classifier's prompt is written from the vocabulary, never from the evaluation sets

`enrichment/vocabularies.yaml` and the corpus README — **not** the golden set's `note` fields, which literally spell out the classification rule (*«what keeps jewellery, not a jewel»*), and not the routing fixture's `why` fields. This is declared in the implementation report, because it is the structural risk `criterion.md` declared of itself, here in sharper form.

### D12 · The veto criterion is the false positive over answerable queries

A single silenced `descripcion-sin-anclaje` query vetoes a configuration, even if it catches all twenty. The asymmetry is the one already measured and argued in `retrieval/abstention.py`: silencing a query the shop **can** answer is a visible failure at the counter; failing to refuse an impossible one shows five pieces that do not fit, and the operator sees that.

## Risks / Trade-offs

- **False positives over the answerable class, especially the twelve queries with no lexical anchor** → The veto criterion of D12, declared before measuring; the confusion matrix reports that rate as a figure of its own; and D6 means the worst case of a bad classifier is switching it off and returning to today.
- **Circular measurement, because the golden set's `note` fields contain the classification rule** → D11, written as a task and a declaration rather than a convention.
- **Precision over the twenty is an upper bound**, since they were *chosen* to be unsatisfiable → declared alongside the figure, never presented as counter traffic.
- **The free-query numeric whitelist widens with every candidate**, against a gate that measured **0 violations in 120 generations** with a single-piece payload → internal identifiers and retrieval scores excluded explicitly, and the free-query rejection rate published **separately** from the anchored one, because they are not the same gate.
- **C34's 5 s budget** → not worsened here by D2, but inherited unresolved; recorded in C34's card together with the measured numbers.
- **The eight-thousandth margin of the knowledge threshold is narrow**, as its own report warned → the router is a second opinion, not a replacement; disagreements are published as a finding.
- **The free-query pitch could consume the session** → it is the **declared cut line**: the router and the refusal are non-negotiable per the plan's *«never cut»* list, the pitch is not. If cut, the mode keeps returning an empty pitch — today's behaviour, with a test — and the cut is declared.
- **`both` has no independent evaluation set**; its ten cases are constructed from the corpus's own eval questions → declared as constructed, and carrying eight controlled pairs against already-judged queries, which is more evidence than a free set of the same size.

## Migration Plan

No database migration: nothing new is persisted.

**Deploy.** Three optional settings. With none of them the classifier is not constructed, the route behaves exactly as C30b's, and that is both the ablation and the rollback. The deployment steps for the demo environment follow C30b's pattern and are recorded in `openspec/DEFERRED_TASKS.md`; `JPV_ROUTER_TIMEOUT_SECONDS` is deliberately left out of them until the deployment measures its own distribution, because the default was taken on a developer machine through a TLS interceptor and is an upper bound.

**Verification without opening a console or reading a key:** `stage=router_client … credential=router|assist_fallback|rag_fallback` in the container log, and `intent` carrying a routing verdict instead of `unclassified` in the response.

**Rollback.** Remove the credential. The router stops being constructed, `intent` returns to `unclassified`, and the abstention rule remains as the net it is today.

## Open Questions

All five of the ticket's open questions are resolved here by taking their declared default:

1. **Refusal reason** → in `warnings[]` as a closed-vocabulary code (D4), not a new field.
2. **The `both` class** → measured with the ten constructed cases, **declaring that they are constructed**.
3. **Free-query pitch** → in scope, and the declared cut line if the session overruns.
4. **Classifier model** → same `gpt-4o-mini` as a starting point, with its **own** setting (D9).
5. **Persisting the routing verdict** → no, log only; the evaluation harness remains the declared exception.

Nothing is left open. What is deliberately *not* decided here is semantic fidelity, which stays declared as a limitation of the capability and measured in C38.
