"""Which mode a request is in, and what intent that implies. Delivered by C30a.

**Structural, and that is the entire design.** The mode is read off which anchors the
request carries; the intent follows from the mode. Nothing here looks at the *words* of the
query, so nothing here can be wrong about them.

That matters beyond tidiness. Routing a query between catalogue, knowledge, both and
out-of-domain is C31 in its entirety, and a keyword mini-router built here would be work
C31 deletes — this repository already paid once for scaffolding it had to remove, with
C25bis. It also means the value reported for a piece with no question stays **correct after
C31**: that router will replace `unclassified`, never `product_pitch`.
"""

from __future__ import annotations

from enum import Enum

from jbg_ai.assist.constants import INTENT_PRODUCT_PITCH, INTENT_UNCLASSIFIED
from jbg_ai.assist.errors import NoAnchorError


class AssistMode(Enum):
    """The three modes, named after what the caller supplied rather than after M1/M2/M3.

    The change's documents call them M1, M2 and M3 and this enum deliberately does not: a
    reader of the code should not have to hold a table in their head to know what
    `PIECE_ONLY` means.
    """

    #: A free question with no piece. Candidates come from the product retrieval, and the
    #: abstention rule governs whether there are any.
    QUERY_ONLY = "query_only"

    #: A piece and no question. No search of any kind runs: the group is the piece's family
    #: and the citations are addressed by primary key.
    PIECE_ONLY = "piece_only"

    #: A piece and a question. The group is still the piece's, and the question is answered
    #: over the corpus with the sheets of the undeclared materials excluded.
    PIECE_AND_QUERY = "piece_and_query"

    @property
    def is_anchored(self) -> bool:
        """Does a concrete piece govern the groups?"""
        return self is not AssistMode.QUERY_ONLY

    @property
    def intent(self) -> str:
        """`product_pitch` for a piece with no question, `unclassified` for the rest.

        Two values and no third, because two is all this capability can honestly report.
        """
        return (
            INTENT_PRODUCT_PITCH
            if self is AssistMode.PIECE_ONLY
            else INTENT_UNCLASSIFIED
        )


def resolve_mode(*, product_id: str | None, query: str | None) -> AssistMode:
    """The mode of a request, from its anchors alone.

    A query that is only whitespace is **not** an anchor. Treating it as one would put a
    request into the mode with a question and then hand the knowledge search a blank string,
    which `search_knowledge` answers with nothing — an empty citation list that looks like
    an abstention and is really a caller mistake.
    """
    piece = (product_id or "").strip() or None
    asked = (query or "").strip() or None
    if piece is not None and asked is not None:
        return AssistMode.PIECE_AND_QUERY
    if piece is not None:
        return AssistMode.PIECE_ONLY
    if asked is not None:
        return AssistMode.QUERY_ONLY
    raise NoAnchorError()
