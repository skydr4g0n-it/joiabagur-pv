"""Assisted product-family grouping for POST /v1/families/suggest. Delivered by C18a.

Library only: `jbg_ai.api.main` must not import this package; the families router
imports submodules. Deterministic and offline — no LLM, no embedding provider call,
no SQL against schema `public`. Similarity comes from vectors already stored on
`ai.product_document`.

The grouping inverts what design §7.5 prescribes, and the inversion is measured:
a global cosine threshold cannot separate siblings from strangers on this corpus
(worst siblings span 0.847-0.948, nearest strangers reach 0.936-0.945), while the
nearest neighbour is a sibling for 96.2% of real and 99.7% of synthetic members.
So the **name root groups and the embedding vetoes**, and the veto is relative to the
*other proposed families* rather than to a constant — or to a group's own centre,
which was the first implementation and flags on ordinary spread, since every group
has a least typical member by construction.
"""
