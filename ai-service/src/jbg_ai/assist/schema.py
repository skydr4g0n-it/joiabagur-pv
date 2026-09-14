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

from pydantic import BaseModel, Field


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
