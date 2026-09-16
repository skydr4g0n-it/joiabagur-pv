"""What the model returns, and why it does not live in `api/schemas/`. Delivered by C30b.

**This shape never reaches the wire.** It is the `response_format` of one provider call and
the input of three deterministic checks; the response keeps `pitch: str` and `citations[]`
with the ten fields C30a froze, so the whole verification costs **zero** contract movement.
Putting it in `api/schemas/` would put it in `openapi.json`, and `supported_claim` is an
internal artefact of verification rather than something a consumer asked for.

**Why the span exists at all.** `{pitch, citation_ids[]}` — the obvious shape — verifies that
an identifier resolves and nothing more. A model that echoes back the five identifiers it was
handed passes that check perfectly and trivially, having used none of them, so the claim
*«these are the citations the argument used»* stays the model's word. Declaring five citations
here obliges the model to point at five spans of the text it just wrote, and an invented span
is a substring of nothing. Deterministic, no judge, no extra call, ~30 tokens of output.

What it still does **not** guarantee is that the cited fragment *says* what the sentence
asserts. That is the alucinación con coartada, declared in the capability and measured with
RAGAS in C38; no model judge runs in the serving path.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """What the classifier returns for one free-text query. C31. **Internal, never on the wire.**

    Three axes and no prose. `served` is the verdict, `index` is which of the two indexes gets
    consulted, and `missing_axis` says the query does not carry enough to search with.

    **The closed vocabularies are `Literal`s, and that is the enforcement.** A label outside the
    set fails Pydantic's parse, which the client turns into a `RouterProviderError` with cause
    `parse`, which the orchestrator turns into a fail-open. So an invented label can never
    reach the response and can never be acted on — the classification may be made by a model,
    the enforcement may not. That distinction is what makes this a guardrail rather than an
    instruction the model is free to disregard.

    All three fields are **required**, `index` and `missing_axis` nullable. Requiring them
    obliges the model to commit to each axis instead of omitting the ones it is unsure about,
    and a null is a decision the code can read.
    """

    served: Literal["in_domain", "out_of_domain", "not_in_catalogue"] = Field(
        ...,
        description=(
            "`in_domain` si la consulta es de esta joyería; `not_in_catalogue` si es joyería u "
            "oficio vecino pero el objeto pedido no es ninguno de los doce tipos de pieza; "
            "`out_of_domain` si no es del negocio en absoluto. Ante la duda, `in_domain`"
        ),
    )
    index: Literal["catalog", "knowledge", "both"] | None = Field(
        ...,
        description=(
            "A qué índice se pregunta: `catalog` si se piden piezas, `knowledge` si se pregunta "
            "algo del oficio, `both` si se hacen las dos cosas. Null cuando no se atiende"
        ),
    )
    missing_axis: Literal["piece_type", "material", "occasion", "price"] | None = Field(
        ...,
        description=(
            "El eje que la consulta deja sin determinar, cuando no determina nada que buscar. "
            "Null cuando la consulta basta, y null siempre que no se atienda"
        ),
    )

    @property
    def is_served(self) -> bool:
        return self.served == "in_domain"

    @property
    def is_sufficient(self) -> bool:
        return self.missing_axis is None


class UsedCitation(BaseModel):
    """One citation the argument used, with the span of the argument it supports."""

    citation_id: str = Field(
        ...,
        description=(
            "Identificador de una de las citas entregadas, copiado tal cual. No inventes "
            "ninguno ni compongas uno nuevo"
        ),
    )
    supported_claim: str = Field(
        ...,
        description=(
            "Fragmento copiado literalmente del argumentario que acabas de escribir, "
            "carácter por carácter, que esta cita sostiene. No lo parafrasees ni lo tomes "
            "del documento citado"
        ),
    )


class AssistPitch(BaseModel):
    """The generated argument and the citations it declares having used.

    Flat rather than claim-by-claim (`{claims: [{text, ids}]}`) because the contract carries a
    single `pitch: str`: the code would end up assembling prose out of fragments the model
    wrote separately, and an argument read at a counter needs continuity. RAGAS does not need
    the decomposition either — *faithfulness* takes (question, answer, contexts) and breaks the
    answer into claims on its own.
    """

    pitch: str = Field(
        ...,
        description=(
            "Prosa corrida, un solo párrafo, entre tres y cinco frases, con {{price}} y "
            "{{stock}} como marcadores allí donde se hable de precio o disponibilidad"
        ),
    )
    used: list[UsedCitation] = Field(
        default_factory=list,
        description=(
            "Las citas en que te has apoyado y sólo ésas. Puede estar vacía: los datos de la "
            "propia pieza no son citables"
        ),
    )
