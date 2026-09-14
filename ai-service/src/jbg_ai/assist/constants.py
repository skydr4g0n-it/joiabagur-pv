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
)

#: A piece is anchored and no question is asked: the request itself says what it wants.
INTENT_PRODUCT_PITCH = "product_pitch"

#: Anything with a question in it. **The only honest value this capability can emit**: routing
#: a query between catalogue, knowledge, both and out-of-domain is C31, and reporting anything
#: else here would claim a classification that was never made.
INTENT_UNCLASSIFIED = "unclassified"

ASSIST_INTENTS: tuple[str, ...] = (INTENT_PRODUCT_PITCH, INTENT_UNCLASSIFIED)

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
PROMPT_VERSION = "assist/v1"

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
