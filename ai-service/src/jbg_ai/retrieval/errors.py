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
