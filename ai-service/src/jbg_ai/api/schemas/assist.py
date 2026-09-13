"""Sale assistance contracts: family-grouped results, rule warnings and citations.

The `pitch` never contains a resolved price or stock figure — it carries the
`{{price}}` and `{{stock}}` placeholders for the .NET API to substitute. **And the
prohibition holds over the whole response, not only over the pitch**: no model here carries
a price, a stock quantity or the availability bucket the index keeps for ranking.

**This block moved once, in C30a, and the window was the reason.** The frozen shape could
not serve its consumer — `family_id` required against a catalogue where ~58 % of products
have no family, and `query` required against a consumer anchored to a piece — and at that
moment the route had **zero** consumers: `IAiGatewayClient` had no assist method and C34 did
not exist. Regenerating the snapshot is a contract negotiation and not a chore, as the
service README says; C18a and C18b set the precedent of doing it in the same change that
moves the boundary, and doing it later would have cost what doing it then did not.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from jbg_ai.api.schemas.common import ScopedResponse, Usage
from jbg_ai.assist.constants import ASSIST_WARNING_CODES


class AssistContext(BaseModel):
    """Optional hints the operator can pass along with the query."""

    occasion: str | None = None
    recipient: str | None = None
    preferred_materials: list[str] = Field(default_factory=list)
    notes: str | None = None


class AssistRequest(BaseModel):
    """One of the two anchors is required, and **at least** one rather than exactly one.

    "Exactly one" would exclude the mode that carries the most value for the least cost —
    a piece on the screen plus the question the customer just asked — which is the mode
    that finally gives the ten counter-conversation documents of the corpus a route to an
    operator's screen. `IndexSyncRequest` with `full` against `since` is the same shape.
    """

    product_id: str | None = Field(
        default=None,
        min_length=1,
        description="Anchor the assistance to one indexed piece. Null means a free query",
    )
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="What the operator asked. Null means the piece itself is the request",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Families wanted after hydration")
    context: AssistContext | None = None
    locale: str = Field(default="es-ES")
    pos_id: str | None = Field(
        default=None,
        description="Accepted for client compatibility and ignored; scope comes from the token",
    )

    @model_validator(mode="after")
    def _requires_an_anchor(self) -> AssistRequest:
        """Name **both** fields: a caller that sent neither needs to be told the alternatives."""
        if self.product_id is None and self.query is None:
            raise ValueError(
                "at least one of product_id and query is required: "
                "product_id anchors the assistance to a piece, query asks a question, "
                "and a request carrying neither anchors nothing"
            )
        return self


class AssistGroupMember(BaseModel):
    product_id: str
    sku: str
    variant_label: str | None = Field(default=None, description="Null when the variant is unknown")
    materials: list[str] = Field(default_factory=list)
    score: float = Field(..., ge=0.0, le=1.0)
    match_reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Why the retrieval produced this candidate, in its own vocabulary. Reused rather "
            "than restated: these codes carry real provenance since C21 and the panel already "
            "maps them to badges"
        ),
    )


class AssistGroup(BaseModel):
    """One product family; members are the variants the operator can disambiguate.

    `family_id` is **nullable**, and the invariant that comes with it is *null implies exactly
    one member*. A synthetic identifier would have been a lie on the wire: .NET and the
    frontend would have to recognise a prefix no schema declares, and nothing in the type
    would stop the variants warning from firing on a group of one.
    """

    family_id: str | None = Field(
        default=None,
        description="Null when the product belongs to no family; such a group holds one member",
    )
    family_label: str | None = None
    members: list[AssistGroupMember]


class Citation(BaseModel):
    """A fragment of the knowledge corpus, carrying everything needed to present it honestly.

    **Citations are corpus fragments and nothing else.** Citing the catalogue would verify
    nothing — the product's metadata already travels in the response — so the anchoring of a
    candidate in the catalogue is expressed with `match_reasons` instead.

    `citation_id` is `<documento>#<sección>`: with the corpus in git it *resolves, locates and
    opens* a file and a heading. `claim_scope` is not decoration either — it separates a fact
    of the world from a commitment of the establishment, which is the failure the whole
    marking mechanism of C23 exists to prevent, and 25 of the corpus's 161 fragments carry it.
    """

    citation_id: str = Field(
        ..., description="`<document>#<section>`; resolves to a file and a heading in git"
    )
    document_title: str
    section_title: str
    doc_type: str = Field(..., description="Corpus document type: material, faq, politica, talla")
    claim_scope: str = Field(
        ...,
        description=(
            "`general` for a fact of the world, `establecimiento` for a commitment of the "
            "house, which is never read to a customer without confirming it in store"
        ),
    )
    score: float = Field(..., ge=0.0, le=1.0)
    snippet: str
    product_id: str | None = Field(
        default=None, description="The piece this claim supports, when the request anchored one"
    )


class AssistResponse(ScopedResponse):
    intent: str = Field(
        ...,
        description=(
            "Derived from the request shape and never from the wording: `product_pitch` for a "
            "piece with no question, `unclassified` otherwise. Classifying a query is C31"
        ),
    )
    groups: list[AssistGroup]
    pitch: str = Field(
        ...,
        description="Generated prose with unresolved {{price}} / {{stock}} placeholders",
    )
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Rule-derived codes, from the closed vocabulary of the assistance capability: "
            + ", ".join(ASSIST_WARNING_CODES)
            + ". Never a sentence: the Spanish a human reads belongs to the frontend"
        ),
    )
    clarification_question: str | None = None
    usage: Usage
    abstained: bool = Field(
        ...,
        description=(
            "The retrieval's abstention rule decided the catalogue cannot answer this query, "
            "so no group is returned. Emitted in every mode — constantly false for a piece "
            "with no question, where there is no retrieval to abstain from — and deliberately "
            "**not** `low_confidence`, whose measured meaning is cross-branch consensus and "
            "fires on answerable queries far more often than on out-of-domain ones"
        ),
    )
    prompt_version: str | None = Field(
        default=None,
        description="Version of the prompt that wrote the pitch. Null while there is no pitch",
    )
