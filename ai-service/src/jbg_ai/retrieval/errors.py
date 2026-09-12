"""Errors raised by the retrieval pipeline. Delivered by C14."""

from __future__ import annotations


class RetrievalDependencyError(Exception):
    """A platform dependency is missing or the compatible index is empty.

    The router translates this to HTTP 503. It is not abstention.
    """


class InvalidFamilyIdError(ValueError):
    """`filters.family_id` was present and did not parse as a UUID."""

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f"filters.family_id is not a valid UUID: {value}")


class InvalidPosIdError(ValueError):
    """The token’s `pos_id` claim did not parse as a UUID.

    The router translates this to HTTP 422. It is deliberately **not** treated as an absent
    scope: a token whose point of sale cannot be read is a mis-issued token, and answering it
    with an unscoped search over the whole catalogue would turn a broken claim into every
    other shop’s assortment on someone’s screen.
    """


class UnusableSourceProductError(ValueError):
    """The `product_id` of a substitutes request cannot anchor a search. Delivered by C26.

    Three causes reach it — absent from the index, present but inactive, indexed but without
    an embedding — and the message names which one, because the three are three different
    things for whoever has to fix them.

    The router translates this to HTTP 422, the status the frozen contract already documents
    for this route and the one its two sibling errors already use: the body named something
    this service cannot process. It is deliberately **not** a 200 with an empty candidate
    list. An empty success is indistinguishable from a catalogue that holds no substitute at
    all, and the panel paints the same "nothing found" screen over both.
    """

    def __init__(self, product_id: str, cause: str) -> None:
        self.product_id = product_id
        self.cause = cause
        super().__init__(
            f"no substitutes can be retrieved for product_id {product_id}: {cause}"
        )
