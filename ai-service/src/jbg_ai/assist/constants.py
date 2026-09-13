"""The closed vocabularies and the declared bounds of the assistance layer. C30a.

Imports nothing from `jbg_ai.api`, so the contract schemas can read the warning vocabulary
without a cycle: the direction is schemas → here, never the other way.
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
