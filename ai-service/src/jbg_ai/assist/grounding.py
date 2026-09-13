"""Citable fragments for a piece nobody asked a question about. Delivered by C30a.

**No search runs here.** The addresses are built from what the piece declares and resolved
by primary key, so the mode that cites *without being asked* cannot return a fragment about
another material — the one failure a similarity search over nine near-identical sheets can
always have, and the one a key never can.

Two invariants govern which fragments are eligible, and both are measurements rather than
caution.

**Only `claim_scope: general`.** `material-bano-de-oro` carries a seventh section,
«Nuestra garantía sobre el baño», scoped `establecimiento`, whose last paragraph says in so
many words that the conditions are confirmed in store before being passed to a customer. A
rule of the form "include the sheet's sections" would put a workshop guarantee into an
argument nobody requested, and **only for plated pieces**. The risk does not grow linearly
with the number of sections: it is a step, and it sits in named sections.

**At most two materials.** Cost decides nothing here — at ~200 tokens a section the
difference between two sections and six is fractions of a cent. What decides is attention
and citation fatigue: the corpus calls the nine sheets "structurally identical" and warns
that cosine collapses by homogeneity, so the danger is not that a fragment is ignored but
that a fact about one material is attributed to another.

**The risk that survives, declared rather than solved.** A silver piece with gold plating
carries two sheets and **both are correct**, yet «la plata tolera bien el agua» belongs to
one part and not the other. The mitigation is the cap, the mixed-piece section below, and
labelling each fragment with its material in the context — the consumer reads which sheet a
claim came from instead of inferring it.
"""

from __future__ import annotations

from collections.abc import Sequence

from jbg_ai.assist.constants import (
    DEFAULT_MATERIAL_CAP,
    DEFAULT_PITCH_SECTIONS,
    MIXED_PIECE_DOCUMENT,
    MIXED_PIECE_SECTION,
)
from jbg_ai.enrichment.vocab import Vocabularies, load_vocabularies
from jbg_ai.knowledge.constants import CLAIM_SCOPE_GENERAL
from jbg_ai.knowledge.corpus import material_sheet_slug
from jbg_ai.knowledge.search import KnowledgeCitation, KnowledgeSearchIndex, address_fragments


def pitch_addresses(
    materials: Sequence[str],
    *,
    sections: Sequence[str] = DEFAULT_PITCH_SECTIONS,
    material_cap: int = DEFAULT_MATERIAL_CAP,
    vocabularies: Vocabularies | None = None,
) -> tuple[tuple[str, str], ...]:
    """`(document_slug, section_slug)` pairs for a piece, in the order it declares them.

    `sections` and `material_cap` are **parameters and not constants inlined here**, for the
    reason C20, C23 and C25 all established: C30b has to compare one, two and three sections
    in a single process and publish the effect on the rejection rate of its numeric gate, and
    a constant would mean restarting between arms.

    A material the vocabulary cannot resolve contributes no address rather than an address
    to a sheet that does not exist — the same erring-towards-less as the exclusion set.
    """
    if material_cap < 0:
        raise ValueError("material_cap must be >= 0")
    vocabs = vocabularies or load_vocabularies()

    resolved: list[str] = []
    for term in materials:
        canonical = vocabs.materials.resolve(term)
        if canonical is not None and canonical not in resolved:
            resolved.append(canonical)

    chosen = resolved[:material_cap]
    addresses = [
        (material_sheet_slug(canonical), section)
        for canonical in chosen
        for section in sections
    ]

    # The mixed-piece guidance enters on what the piece DECLARES, not on what the cap let
    # through: a piece of three materials is more exposed to cross-attribution, not less,
    # and capping it at two is precisely why it needs the section that says which part
    # governs.
    if len(resolved) >= 2:
        addresses.append((MIXED_PIECE_DOCUMENT, MIXED_PIECE_SECTION))
    return tuple(addresses)


async def ground_piece(
    materials: Sequence[str],
    *,
    index: KnowledgeSearchIndex,
    sections: Sequence[str] = DEFAULT_PITCH_SECTIONS,
    material_cap: int = DEFAULT_MATERIAL_CAP,
    vocabularies: Vocabularies | None = None,
) -> tuple[KnowledgeCitation, ...]:
    """The citable fragments of a piece with no question. No provider is called.

    Anything not scoped `general` is dropped **after** the read rather than assumed absent
    from the allow-list: the allow-list is authored and the corpus is authored, and the day
    those two disagree the invariant has to hold anyway. A test asserts the list's sections
    are general in all nine sheets; this filter is what makes the guarantee independent of
    that test still being true.
    """
    addresses = pitch_addresses(
        materials,
        sections=sections,
        material_cap=material_cap,
        vocabularies=vocabularies,
    )
    fragments = await address_fragments(addresses, index=index)
    return tuple(
        fragment for fragment in fragments if fragment.claim_scope == CLAIM_SCOPE_GENERAL
    )
