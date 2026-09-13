"""Structured sale assistance for POST /v1/assist/sale. Delivered by C30a.

Library only: `jbg_ai.api.main` must not import this package; the assist router imports
submodules. The same rule `retrieval/` and `families/` already follow.

**This package generates no prose and calls no provider.** It consumes what C21/C25 and C23
already built — retrieved candidates with their real match reasons, and citable fragments
with their claim scope — and turns them into a *shape*: candidates grouped by family,
warnings derived from rules, and citations that resolve to a file and a heading in git. The
argument in prose, its versioned prompt and the numeric gate that guards it are C30b, and the
split exists so that C30b's value can be measured **against** this layer rather than asserted.

Three modes, selected by which anchors the request carries and by nothing else:

    M1  query, no piece   → candidates from `retrieve_products`, knowledge unfiltered
    M2  piece, no query   → one group, citations addressed by primary key, no search at all
    M3  piece and query   → one group, knowledge filtered by the piece's own materials

`intent` is derived from that table and never from the wording of the query: classifying a
query is C31 entire, and a keyword router built here would be work C31 deletes.
"""
