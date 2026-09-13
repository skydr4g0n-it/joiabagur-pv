"""Scoping the knowledge corpus to one piece, and only as far as it is safe to. C30a.

**The filter is asymmetric on purpose, and the asymmetry is the whole decision.**

    EXCLUDE       material-<slug> of each of the NINE canonical sheets the piece does NOT
                  declare — about eight decoys
    PASS ALWAYS   faq · politica · talla · piedras-* · material-piezas-mixtas ·
                  material-marcajes-y-punzones — and everything else

Excluding *inside* the nine is safe because they are **mutually exclusive by construction** —
C23's 1:1 invariant against the nine terms of `materials.terms` — and **confusable by
construction**: the corpus calls them "structurally identical — same skeleton, same register,
same vocabulary", and warns that cosine collapses by homogeneity, which is the reason C23 had
to add a lexical branch at all. Measured over the 72 golden queries on 2026-09-13, the filter
removes a mean of **36,4 foreign-sheet citations** per anchored material.

Excluding *outside* them would be a different thing entirely. A general "restrict to the
declared materials" filter would cut **23 of the 32 documents** and with them nearly every
real counter question — the pool, the repair, the size, the gift with no size — which is mass
false abstention. C25 already settled that asymmetry with a measurement: silencing a query the
shop CAN answer is a visible failure at the counter, while failing to abstain on an impossible
one shows five pieces that do not fit and the operator sees that. Here the cost is measured
too: the filter moves abstentions only from **41 to 44,3** of 72.

And two documents share the `material-` prefix and the `material` doc type without being the
sheet of a canonical material — `material-piezas-mixtas` and `material-marcajes-y-punzones`.
They pass, and that is correct rather than an oversight: *«¿qué significa el 925?»* is
answerable about a steel piece. The set is therefore built by **enumerating the nine sheets to
exclude**, never by enumerating what is allowed through — an allow-list here would silently
grow teeth every time the corpus gained a document.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from jbg_ai.enrichment.vocab import Vocabularies, load_vocabularies
from jbg_ai.knowledge.corpus import material_sheet_slug
from jbg_ai.knowledge.indexer import document_id


def canonical_material_sheets(vocabularies: Vocabularies | None = None) -> tuple[str, ...]:
    """The slug of the sheet of every canonical material, in vocabulary order.

    Read from `enrichment/vocabularies.yaml` **without modifying it**: touching that file
    forces a prompt version bump and a re-enrichment of every affected row. The list is
    derived rather than restated, so a tenth material added there is excluded correctly the
    day its sheet exists, and `missing_material_sheets` is what fails if it does not.
    """
    vocabs = vocabularies or load_vocabularies()
    return tuple(material_sheet_slug(term) for term in vocabs.materials.canonical)


def piece_scoped_exclusions(
    materials: Iterable[str], *, vocabularies: Vocabularies | None = None
) -> tuple[UUID, ...]:
    """Document identities to exclude when a question is scoped to one piece.

    `materials` is what the piece declares. The indexed values are canonical already, but
    each one is put through `resolve` anyway: that is the vocabulary's own folding — `plata
    de ley`, `925` and `sterling` all reach `plata`, and `bano de oro` reaches `baño de oro`
    across the `ñ` the Spanish stemmer does not fold. A term the vocabulary cannot resolve is
    **ignored rather than guessed**, which errs towards excluding less.

    A piece that declares **no** material excludes nothing: with nothing to scope to, the
    honest behaviour is the unfiltered corpus and not a guess.
    """
    vocabs = vocabularies or load_vocabularies()
    declared = {
        resolved
        for term in materials
        if (resolved := vocabs.materials.resolve(term)) is not None
    }
    if not declared:
        # Read literally, "exclude what the piece does not declare" would exclude all nine
        # here and take the whole material corpus with them. That is the opposite of the
        # intent: with nothing to scope to there is nothing to protect the question from,
        # and the unfiltered corpus is the honest answer.
        return ()
    return tuple(
        document_id(material_sheet_slug(term))
        for term in vocabs.materials.canonical
        if term not in declared
    )
