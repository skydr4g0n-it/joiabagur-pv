"""Typed failures of family suggestion. Delivered by C18a."""

from __future__ import annotations

__all__ = ["FamilyDependencyError", "InvalidPieceTypeError"]


class FamilyDependencyError(RuntimeError):
    """A dependency the suggestion needs was unreachable — database, index, config.

    Kept distinct from a bad request so the router can answer 503 rather than 400:
    suggestion has no degraded mode. Unlike search, which drops to the lexical
    index, there is no honest partial answer here — proposing groupings without
    the index would mean inventing catalogue structure.
    """


class InvalidPieceTypeError(ValueError):
    """`piece_type` was present in the body and is not a term of the closed vocabulary."""

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f"piece_type is not a known term: {value}")
