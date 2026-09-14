"""Sale assistance for POST /v1/assist/sale. Structure by C30a, prose by C30b.

Library only: `jbg_ai.api.main` must not import this package; the assist router imports
submodules. The same rule `retrieval/` and `families/` already follow.

**The split survives its own second half.** C30a consumes what C21/C25 and C23 already built
— retrieved candidates with their real match reasons, and citable fragments with their claim
scope — and turns them into a *shape*: candidates grouped by family, warnings derived from
rules, and citations that resolve to a file and a heading in git. C30b writes the argument
over that shape, and writes it through a client the layer is **handed**, so the structured
response is still exactly what comes out when there is no client, when the provider fails, or
when a check refuses the prose. That is what keeps the generation measurable as an ablation
rather than asserted: same route, same candidates, same citations, with prose and without it.

Three checks guard the prose and none of them is a prompt instruction: a declared citation
must resolve to one that was handed over, the span it declares must occur in the argument that
was written, and every figure must belong to the payload object — with adjacency to money or
to stock refused whether or not it does. One repair per request, two policies, and a text that
is never persisted and never logged.

Three modes, selected by which anchors the request carries and by nothing else:

    M1  query, no piece   → candidates from `retrieve_products`, knowledge unfiltered
    M2  piece, no query   → one group, citations addressed by primary key, no search at all
    M3  piece and query   → one group, knowledge filtered by the piece's own materials

`intent` is derived from that table and never from the wording of the query: classifying a
query is C31 entire, and a keyword router built here would be work C31 deletes.
"""
