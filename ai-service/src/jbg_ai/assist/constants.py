"""The closed vocabularies and the declared bounds of the assistance layer. C30a and C30b.

**Imports nothing at all**, which is what lets everything else read from it without a cycle:
the contract schemas take the warning vocabulary from here, and since C30b `config/settings.py`
takes the default of the generation timeout from here too. The direction is always *towards*
this module, never out of it — so the value and the measurement that set it live in one place
and a default duplicated in two files cannot drift.
"""

from __future__ import annotations

#: The family this piece belongs to holds other members the operator can offer. Computed from
#: the family's **roster** as the index holds it, never from how many candidates the retrieval
#: happened to return — a family of four whose search returned two still has four.
WARNING_FAMILY_HAS_VARIANTS = "family_has_variants"

#: The piece declares no size label. Read off the indexed document, not inferred.
WARNING_SIZE_LABEL_MISSING = "size_label_missing"

#: The router refused the query because it is not about this business at all. C31.
#:
#: **A different code from the one below, and the distinction is the point of D1.** What an
#: operator says to a customer differs between a trade the shop does not practise and a piece
#: the shop does not carry, and a single `refused` code would make the two rates this change
#: exists to publish separately indistinguishable on the wire.
WARNING_QUERY_OUT_OF_DOMAIN = "query_out_of_domain"

#: The router refused the query because it asks for an object this catalogue does not stock —
#: jewellery-adjacent and plausible, but none of the twelve closed `piece_type` terms. C31.
WARNING_QUERY_NOT_IN_CATALOGUE = "query_not_in_catalogue"

#: An anchored question the corpus does not cover: **zero citations after the distance
#: threshold**. C31, and it costs no provider call at all — the result is already computed.
#:
#: C23 fixed `jpv_knowledge_distance_threshold = 0,51` on a clean gap of eight thousandths, so
#: an empty citation list after it already *means* the corpus cannot answer. What was missing
#: was a consumer able to tell that apart from there being nothing worth citing, and that is
#: the whole of this code: the information existed and nobody could read it.
WARNING_KNOWLEDGE_NOT_COVERED = "knowledge_not_covered"

#: **Closed, and closed is the point.** The model never sees this tuple and cannot add to it,
#: which is what makes "warnings are rule-derived" a property a test can witness instead of a
#: promise a reader has to take on trust. The Spanish a human reads is the frontend's: codes
#: on the wire and copy in the presentation layer is the rule the assisted-search panel's live
#: spec already states for the retriever's match reasons.
#:
#: `stock_critical` and `family_members_out_of_stock` are **deliberately absent**. They need
#: real stock, which this service does not have: it holds an availability *bucket* for ranking
#: that may be minutes stale, and "critical stock" announced with twelve units in the drawer is
#: the assistant's credibility at the counter. They belong to C34, after hydration.
ASSIST_WARNING_CODES: tuple[str, ...] = (
    WARNING_FAMILY_HAS_VARIANTS,
    WARNING_SIZE_LABEL_MISSING,
    WARNING_QUERY_OUT_OF_DOMAIN,
    WARNING_QUERY_NOT_IN_CATALOGUE,
    WARNING_KNOWLEDGE_NOT_COVERED,
)

#: The two codes that state a **refusal by the router**, as opposed to a fact about a piece.
#: Kept as a subset of the vocabulary above rather than as a second vocabulary: a consumer
#: reads one list of codes, and this tuple is what lets a test say "exactly one of these is
#: present on a refused response" without restating the pair.
ASSIST_REFUSAL_CODES: tuple[str, ...] = (
    WARNING_QUERY_OUT_OF_DOMAIN,
    WARNING_QUERY_NOT_IN_CATALOGUE,
)

#: A piece is anchored and no question is asked: the request itself says what it wants.
INTENT_PRODUCT_PITCH = "product_pitch"

#: The router admitted the query: it is about this business and there is something to search.
#: C31. It says nothing about **which** index was consulted — that decision does not travel on
#: the wire, because it governs what runs rather than what the caller has to know.
INTENT_IN_DOMAIN = "in_domain"

#: The router refused: the query is not about this business at all. C31.
INTENT_OUT_OF_DOMAIN = "out_of_domain"

#: The router refused: jewellery-adjacent, and this catalogue does not stock the object. C31.
INTENT_NOT_IN_CATALOGUE = "not_in_catalogue"

#: No classification was made. **The value gained a second meaning in C31 and both are true.**
#: Before the router it said "queries are not classified at all"; now it says "this particular
#: request was not classified" — because no classifier ran (a piece with a question is routed
#: structurally) or because one ran and could not be used (no credential, a fault, a timeout,
#: an unparseable reply). A consumer needs no new field to tell them apart: the log records
#: which, and the response is identical in both cases by design — that is the fail-open.
INTENT_UNCLASSIFIED = "unclassified"

ASSIST_INTENTS: tuple[str, ...] = (
    INTENT_PRODUCT_PITCH,
    INTENT_IN_DOMAIN,
    INTENT_OUT_OF_DOMAIN,
    INTENT_NOT_IN_CATALOGUE,
    INTENT_UNCLASSIFIED,
)

#: Sections addressed by primary key in M2. An **allow-list**, never "every section of the
#: sheet": measured, these two are present and `claim_scope: general` in **all nine** canonical
#: sheets, while `material-bano-de-oro` carries a seventh section, «Nuestra garantía sobre el
#: baño», of `establecimiento` scope whose last paragraph says the conditions are confirmed in
#: store before being passed to a customer. "All the sections" would put a workshop guarantee
#: into an argument nobody asked for, and only for plated pieces. The risk does not grow
#: linearly with the number of sections: it is a step, and it is in named sections.
#:
#: Travels **by parameter** and not inlined, so C30b can sweep 1/2/3 sections in one process
#: and publish the effect — the pattern C20, C23 and C25 established.
DEFAULT_PITCH_SECTIONS: tuple[str, ...] = (
    "cuidados-y-limpieza-en-casa",
    "piel-sensible-y-alergias",
)

#: The mixed-piece sheet, added when the piece declares two or more materials. It is the
#: section the corpus already wrote for the one risk no filter can remove: both sheets of a
#: silver-with-plating piece are correct, and «la plata tolera bien el agua» belongs to one
#: part and not the other.
MIXED_PIECE_DOCUMENT = "material-piezas-mixtas"
MIXED_PIECE_SECTION = "limpiar-una-pieza-mixta-sin-estropear-nada"

#: How many declared materials enter the M2 context, in the order the piece declares them.
#: Two, because the cost of more is decided by attention and not by tokens: the corpus calls
#: the nine sheets "structurally identical" and warns that cosine collapses by homogeneity, so
#: the risk is not that a fragment is ignored but that a fact about one material is attributed
#: to another. By parameter, like the section list.
DEFAULT_MATERIAL_CAP = 2

#: Hard ceiling on one family roster read. Measured 2026-09-13 over the live index: 156
#: families, 491 members, **maximum 8**, mean 3,15, p95 4, and nothing above 8. Twenty-four is
#: three times the observed maximum — the cap exists to bound the worst case of a read, not to
#: trim real families, and a family that reached it would be a sign that C18b's grouping broke
#: rather than an answer worth serving whole.
FAMILY_ROSTER_CAP = 24


# --- C30b · the generation layer -----------------------------------------------------------

#: The prompt that writes the argument, and the value `prompt_version` reports. The path is
#: **derived** from it in `assist/prompt.py` and never named beside it, so a version that moved
#: while the file did not cannot stamp a response with a prompt that never reached the model —
#: the failure `enrichment/` already paid for once. `test_prompt_version_matches_the_loaded_
#: prompt_file` pins the other half.
#:
#: **Moved to v2 by C31, and `prompts/assist/v1.md` stays on disk untouched.** Adding the
#: free-query task sections to v1 would have silently changed what «v1» means for the 120
#: generations C30b measured against it, and those figures have to stay interpretable. The
#: invariant system rules are byte-identical between the two files; what v2 adds are task
#: sections — one per route the router can decide, plus the degraded one for an anchored
#: question the corpus does not cover. `test_the_previous_prompt_version_is_present_and_intact`
#: is what keeps v1 from being edited by accident later.
PROMPT_VERSION = "assist/v3"

#: The prompt of the **classifier**, versioned separately because it is a different call with a
#: different output and a different model setting. A router prompt that shared the argument's
#: version would make either figure unreadable the first time one of the two moved.
ROUTER_PROMPT_VERSION = "router/v3"

#: The model that writes the argument. A **module constant and not a setting**, for the reason
#: the timeout below is one: `JPV_RAG_LLM_MODEL` is C09's enrichment model — `gpt-4o` on this
#: deployment — and inheriting it would silently move the model of a counter-side call whose
#: cost, latency and measured rejection rate were all taken on this one. The credential is
#: shared (`JPV_RAG_LLM_API_KEY`, which exists since C09); the model is not.
DEFAULT_ASSIST_MODEL = "openai/gpt-4o-mini"

#: Seconds **one provider call** may take — per call, never per request: a repaired request
#: makes two, and measuring its total against a one-call limit is how a five per cent cut reads
#: as seventy.
#:
#: Opened at three seconds as a product judgement with no latency measurement behind it. The
#: C30b sweep took one — 175 real calls, `evals/results/c30b-assist-sweep-5a6e1b4b8621.json` —
#: and it moved the value: **p50 2.216 s, p95 2.863 s**, with **8 of 175 calls (4,6 %) over
#: three seconds** and **1 of 175 (0,6 %) over four**. Three seconds sat at 1,05 × p95, which
#: is a cut that fires on jitter rather than on generations that are genuinely too slow.
#:
#: Raising it to four costs nothing for the ~95 % of calls that finish early — a timeout does
#: not slow a fast call down — and only changes the tail: at three seconds those requests are
#: served with no argument at all, at four they are served with one. The typical wait is
#: unchanged at ~2,2 s, which is what the "no sirve en un mostrador" argument is about.
#:
#: It is now **also adjustable**, which is what the design said to do if the sweep measured a
#: cut: `JPV_ASSIST_PITCH_TIMEOUT_SECONDS` supplies the default and the value travels by
#: parameter, so a deployment can set it against its own measured distribution rather than
#: against one taken on a developer machine in Spain through a TLS interceptor.
PITCH_TIMEOUT_SECONDS = 4.0

#: Provider calls one request may make: the generation and, at most, **one** repair. The ceiling
#: is literal — there is no transient-retry loop underneath it — and that is a deliberate
#: departure from C09's seam, recorded in the implementation report: `ENRICH_BACKOFF_BASE_
#: SECONDS` is two seconds, so a single backoff sleep would consume two thirds of the budget
#: above before the retried call even started. Degrading is the cheaper answer at a counter.
MAX_PITCH_PROVIDER_CALLS = 2

# --- C31 · the intent router ---------------------------------------------------------------

#: The model that classifies the query. A **setting with its own variable**, and it never
#: inherits `JPV_ASSIST_LLM_MODEL` nor `JPV_RAG_LLM_MODEL` — the same measured argument C30b
#: used against inheriting C09's. These are calls of very different shape: ~30 output tokens
#: against a paragraph, so sharing a variable would make any cost comparison between them false.
#:
#: **Opened at `gpt-4o-mini` and moved to `gpt-4o` by the measurement, which is the whole reason
#: the variable is separate.** Over the 119 cases of `evals/routing/cases.yaml`, same prompt
#: (`router/v3`), temperature zero, full coverage on both arms:
#:
#:     modelo            catalog   falso positivo   silenciadas   veto
#:     gpt-4o-mini        81,3 %        6,25 %           3        NO PASA
#:     gpt-4o            100,0 %        0,00 %           0        PASA
#:
#: The veto of D12 is not a preference: a single silenced answerable query rejects the
#: configuration, and `gpt-4o-mini` silenced three — `el calzado tipico que se lleva en las
#: fiestas de la isla`, `una brujula para no perder el rumbo`, `una bicicleta antigua` — all
#: three of them queries that describe **the motif a piece depicts** rather than an article.
#: Three prompt revisions took that from fifteen to three and could not take it to zero; the
#: model took it to zero with no prompt change at all. **What decides this gate is the model.**
#:
#: The argument's model stays `gpt-4o-mini` and is untouched: that is what D9's separate
#: variable bought, and moving one without the other is the thing a shared variable would have
#: made impossible. Cost: ~700 input and ~30 output tokens per classification, so this arm is
#: of the order of 0,002 USD per request against the 0,00077 the argument measures — published
#: as its own figure in the C31 report and never folded into the argument's.
DEFAULT_ROUTER_MODEL = "openai/gpt-4o"

#: Seconds the **single** classifier call may take.
#:
#: **Declared NOT calibrated.** Two seconds is a product judgement with no latency measurement
#: behind it, in exactly the position C30b's three seconds occupied before its sweep moved the
#: value to four. The difference is that this cut is harder, because the classifier runs *in
#: front of everything*: a request that spends it has spent it before the retrieval starts.
#: It is also the reason `JPV_ROUTER_TIMEOUT_SECONDS` is deliberately left out of the deployment
#: steps until the deployment measures its own distribution — the default was taken on a
#: developer machine in Spain through a TLS interceptor and is an upper bound, not a budget.
#:
#: Exceeding it is a **fail-open**: the request proceeds unclassified, which is today's
#: behaviour, so the worst case of a badly chosen value is the behaviour this change replaces.
ROUTER_TIMEOUT_SECONDS = 2.0

#: Provider calls the classifier may make for one request. **One, and the one is literal**:
#: there is no retry and no repair underneath it. An unparseable label is a degradation and not
#: a violation to fix — there is nothing in a label to repair — and spending a second call on
#: it would buy a second opinion from the same model at temperature zero, which is the same
#: opinion. It also keeps C30b's measured decision not to retry on a parse failure intact.
MAX_ROUTER_PROVIDER_CALLS = 1

#: **The ceiling of the whole system, and it is literal: three.** One classifier call plus the
#: two of the argument. Derived from the two constants rather than written as a digit, so a
#: change to either cannot leave a stale three behind, and observable by introspection over the
#: accumulated `usage.calls` — the same property C30b delivered for two.
MAX_PROVIDER_CALLS = MAX_ROUTER_PROVIDER_CALLS + MAX_PITCH_PROVIDER_CALLS

#: Markers of money. **es-ES, closed and short**, which is exactly what licenses a blacklist
#: here: there is no legitimate use of `€` in an argument whose price travels as a placeholder.
#: The corresponding argument against blacklists — made in C30's D-H and still correct — is
#: about *numbers*, not about currency marks: "numbers in jewellery" is open and ambiguous,
#: this set is neither.
CURRENCY_MARKERS: tuple[str, ...] = ("€", "EUR", "euro", "euros")

#: Markers of stock, same rule and same reason. `{{stock}}` is what carries availability.
STOCK_MARKERS: tuple[str, ...] = (
    "unidades",
    "quedan",
    "en stock",
    "disponible",
    "disponibles",
)

#: Why a figure was refused. The rejection rate is only readable **partitioned by cause**: a
#: single aggregate number cannot tell a gate that works from a gate that gets in the way.
CAUSE_FIGURE_NOT_IN_CONTEXT = "figure_not_in_context"
CAUSE_CURRENCY_ADJACENT = "currency_adjacent_figure"
CAUSE_STOCK_ADJACENT = "stock_adjacent_figure"
#: A figure absent from the context that is the numeral of a numbered list. Still a violation —
#: the gate forgives nothing — but it is the cause the *prompt* exists to remove, and telling it
#: apart is what says whether "continuous prose" is working.
CAUSE_ENUMERATION_FORMAT = "enumeration_format"
#: A figure absent from the context whose digits, with every separator stripped, do match one
#: that is present: `1.500` against `1500`. A violation too, and the cause that would say a
#: separator rule needs a measurement rather than an opinion.
CAUSE_DECIMAL_FORM = "decimal_form"

#: The two causes that are not about figures.
CAUSE_DANGLING_CITATION = "dangling_citation"
CAUSE_CLAIM_NOT_IN_PITCH = "claim_not_in_pitch"

#: Closed vocabulary of violation causes, so a sweep can partition by it exhaustively.
PITCH_VIOLATION_CAUSES: tuple[str, ...] = (
    CAUSE_DANGLING_CITATION,
    CAUSE_CLAIM_NOT_IN_PITCH,
    CAUSE_FIGURE_NOT_IN_CONTEXT,
    CAUSE_CURRENCY_ADJACENT,
    CAUSE_STOCK_ADJACENT,
    CAUSE_ENUMERATION_FORMAT,
    CAUSE_DECIMAL_FORM,
)

#: The causes whose survival costs the whole argument. Resolution and the numeric gate: a
#: dangling citation is never ignored, and an invented figure is the failure the layer exists
#: to prevent. Correspondence is **deliberately absent** — the fragment exists and was in the
#: context, and what failed is the model's own account of using it, so the proportionate answer
#: is withdrawing that citation and publishing the prose.
HARD_VIOLATION_CAUSES: tuple[str, ...] = (
    CAUSE_DANGLING_CITATION,
    CAUSE_FIGURE_NOT_IN_CONTEXT,
    CAUSE_CURRENCY_ADJACENT,
    CAUSE_STOCK_ADJACENT,
    CAUSE_ENUMERATION_FORMAT,
    CAUSE_DECIMAL_FORM,
)


# --- C32a · the sale assistant's tool registry ----------------------------------------------

#: The six tools of the sale assistant, **frozen**. A seventh is a deliberate act with a test
#: behind it and never whatever `build_registry` happened to assemble, which is the whole
#: reason this is a declared constant and not a derivation of the construction.
#:
#: `perfil_punto_venta` and `buscar_complementarios` are **absent and must stay absent**: the
#: first was served by a change that was cancelled, the second was cut when its signals
#: measured empty over the real catalogue. Naming them nowhere would make their return a
#: silent diff; `test_the_registry_holds_exactly_the_six_frozen_tools` names them so that it
#: cannot be.
TOOL_NAMES: tuple[str, ...] = (
    "buscar_catalogo",
    "buscar_sustitutos",
    "listar_familia",
    "consultar_conocimiento",
    "consultar_disponibilidad",
    "pedir_aclaracion",
)

#: Tools withdrawn before this registry existed. Held as a constant so the frozen-set test can
#: assert their absence by name rather than by a count that would also pass if one came back
#: and another left.
WITHDRAWN_TOOL_NAMES: tuple[str, ...] = (
    "perfil_punto_venta",
    "buscar_complementarios",
)

#: The availability vocabulary, **qualitative and with no digit in it**. The projection stores
#: availability as `QTY_BUCKETS = {"0", "1-2", "3+"}`, whose members are literally numerals, so
#: emitting a bucket verbatim would put a stock figure into the model's context — the thing the
#: service boundary forbids and the thing `SearchHit.qty_bucket` already declares when it says
#: that «a bucket on the wire would be the beginning of one».
#:
#: The authority over stock remains .NET's. This is a **band**, of the same kind the ranking
#: already consumes, and `test_no_availability_label_contains_a_digit` is what keeps it one.
AVAILABILITY_OUT_OF_STOCK = "sin_existencias"
AVAILABILITY_LAST_UNITS = "ultimas_unidades"
AVAILABILITY_IN_STOCK = "disponible"

#: **A fourth value, and the fourth is the point.** It states that nothing was read — the
#: principal carries no point of sale, or this point of sale has no projection row for the
#: piece — and it is NOT an absence of stock. The precedent is literal and it is the port's:
#: `qty_bucket = None` means «ran unscoped, which is not the same as a bucket of zero».
#:
#: Collapsing the two would fire the pivot to substitutes over a piece the shop can actually
#: sell, which is the failure the degrade-never-remove rule exists to prevent.
AVAILABILITY_NO_SCOPE = "sin_ambito"

AVAILABILITY_LABELS: tuple[str, ...] = (
    AVAILABILITY_OUT_OF_STOCK,
    AVAILABILITY_LAST_UNITS,
    AVAILABILITY_IN_STOCK,
    AVAILABILITY_NO_SCOPE,
)

#: Every bucket the index feed can store, mapped to its label.
#:
#: **The keys are written out here rather than imported from `indexing/feed.py`**, because this
#: module imports nothing at all and that property is what lets everything else read from it
#: without a cycle. The coupling is not lost, it is moved to where it can fail loudly:
#: `test_every_bucket_the_feed_can_store_has_a_label` compares these keys against `QTY_BUCKETS`
#: itself, so a tenth bucket added to the feed breaks a test rather than silently falling
#: through to «no scope».
#:
#: `AVAILABILITY_NO_SCOPE` is deliberately **not** a value of this map: it is never derived
#: from a bucket, only from the absence of one.
AVAILABILITY_LABEL_BY_BUCKET: dict[str, str] = {
    "0": AVAILABILITY_OUT_OF_STOCK,
    "1-2": AVAILABILITY_LAST_UNITS,
    "3+": AVAILABILITY_IN_STOCK,
}

#: Why a tool observation came back failed. **Codes, never prose**, the same rule the
#: rule-derived warnings above already follow — the Spanish belongs to whoever presents it, and
#: here the consumer is a loop that has to branch on the cause rather than read it.
#:
#: They are in Spanish because their siblings in this file are: the tool names, their
#: descriptions and the availability labels all are, and a consumer reading `sin_ambito` beside
#: `unknown_reference` would be reading two vocabularies that were never meant to be two.
#:
#: An exception is **not** one of the options. One escaping would kill the consuming loop
#: instead of costing it one turn, and a generic `error` would leave the model blind exactly
#: where an informative code lets it reformulate.

#: The arguments did not satisfy the tool's own schema. Raised **before any port is touched**.
TOOL_CAUSE_INVALID_ARGUMENT = "argumento_invalido"

#: The SKU does not exist in the index. A statement about the reference, not about the
#: catalogue: reformulating with another piece is the useful next step.
TOOL_CAUSE_UNKNOWN_REFERENCE = "referencia_desconocida"

#: The piece exists and cannot anchor this tool — discontinued, or indexed without an
#: embedding. Separate from the code above because the two are different sentences for whoever
#: has to act on them, exactly as the substitutes path already keeps them apart.
TOOL_CAUSE_UNUSABLE_REFERENCE = "referencia_no_utilizable"

#: A dependency the tool consults is unavailable. The loop's useful move is to stop asking this
#: tool, which is a different decision from reformulating, so it is a different code.
TOOL_CAUSE_DEPENDENCY_UNAVAILABLE = "dependencia_no_disponible"

TOOL_FAILURE_CAUSES: tuple[str, ...] = (
    TOOL_CAUSE_INVALID_ARGUMENT,
    TOOL_CAUSE_UNKNOWN_REFERENCE,
    TOOL_CAUSE_UNUSABLE_REFERENCE,
    TOOL_CAUSE_DEPENDENCY_UNAVAILABLE,
)

#: Candidates one catalogue search may return, as the tool's schema declares them. **A declared
#: minimum and maximum and not an open integer**: everything a tool returns is re-sent on every
#: subsequent turn of the consuming loop, so an uncapped `top_k` is the cheapest way for one
#: turn to drag fifty candidates through all the following ones.
TOOL_TOP_K_MIN = 1
TOOL_TOP_K_MAX = 10
TOOL_TOP_K_DEFAULT = 5

#: Fragments one knowledge question may return. Same argument as the bound above, and the same
#: reason it is small: a fragment is a paragraph, not a row.
TOOL_CITATION_TOP_K = 3

#: The method-name vocabulary that marks a write. Matched **token by token** against the
#: snake_case name of every method a tool's collaborators expose.
#:
#: **Token equality and not substring containment, and the difference is not cosmetic.** Read
#: literally as a substring, `sync` flags `ProductSearchPort.projection_synced_at()` and
#: `ProjectionFreshness.synced_at()`, which are reads of a checkpoint, and the invariant would
#: be unsatisfiable with the very ports this registry is required to inject. Token equality
#: catches every spelling built from one of these verbs — `save_profile`, `bulk_insert`,
#: `upsert_projection`, `delete_row`, `sync_now`, `apply_page` — and
#: `test_a_tool_capturing_a_writing_port_is_refused_however_it_describes_itself` is what holds
#: that claim up.
#:
#: **What it does not catch is a verb this list never had, and that is the real limit.** It is
#: not inflection: `SqlAlchemyPosProjection.put_checkpoint()` is an `INSERT … ON CONFLICT DO
#: UPDATE` that lives in this repository today and matches nothing here — and would match
#: nothing under substring reading either, so the comparison rule is not what loses it. The
#: same goes for the family it belongs to: `put_`, `store_`, `record_`, `commit`, `flush`. The
#: vocabulary is fixed by the change's design decision and widening it is a decision, not a
#: patch; what must not happen is reading this set as though it were exhaustive. The check is
#: a floor under the object graph, not a proof that no method writes.
WRITE_METHOD_VERBS: frozenset[str] = frozenset(
    {"insert", "update", "delete", "write", "save", "upsert", "persist", "sync", "apply"}
)

#: HTTP verbs that are not a read. A collaborator exposing one of these as a callable is a
#: client that **can** issue it, which is what the third axis of the read-only check refuses —
#: the question is what the object is able to do, never what it happens to do today.
WRITE_HTTP_VERBS: frozenset[str] = frozenset({"post", "put", "patch", "delete"})
