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
