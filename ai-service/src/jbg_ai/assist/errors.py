"""Errors of the assistance layer. Delivered by C30a."""

from __future__ import annotations


class AssistError(Exception):
    """Base class, so a caller can catch the layer without catching the world."""


class PitchProviderError(AssistError, RuntimeError):
    """The generative provider failed, timed out, or returned something that did not parse.

    **It never reaches the router.** C30b's rule is that a provider fault degrades to the
    structured response with 200: the structured half is already computed and correct, and
    discarding it because the prose failed turns a partial loss into a total one. The class
    exists so the degradation has one thing to catch and one `cause` to log, rather than a
    bare `except Exception` whose reason nobody can read afterwards.
    """

    def __init__(self, message: str, *, cause: str) -> None:
        self.cause = cause
        super().__init__(message)


class NoAnchorError(AssistError, ValueError):
    """The request carried neither a piece nor a question.

    In the HTTP path this never reaches the layer: the request model rejects it first, with
    a 422 that names both fields. It exists because the layer is also a **callable** — C32's
    agent loop and the evaluation harness will drive it directly — and a library that
    depended on its caller having run a validator would be one refactor from serving a mode
    it cannot resolve.
    """

    def __init__(self) -> None:
        super().__init__(
            "at least one of product_id and query is required: "
            "product_id anchors the assistance to a piece, query asks a question"
        )


class UnusableAnchorProductError(AssistError, ValueError):
    """The anchored `product_id` cannot anchor anything. Three causes, three sentences.

    Reuses the shape C26 set for `UnusableSourceProductError`, and for the same reason: the
    index reports absence, inactivity and a missing embedding as **values**, and which
    sentence a caller writes is not a decision the SQL layer gets to make.

    **It is deliberately not an abstention.** Answering 200 with `abstained: true` would
    assert that the catalogue cannot answer, when what happened is that the piece the
    request named cannot be used — a statement about the request, not about the catalogue,
    and one the system has not established.

    The router translates it to 422, the status the two sibling paths already use for a body
    naming something this service cannot process.
    """

    def __init__(self, product_id: str, cause: str) -> None:
        self.product_id = product_id
        self.cause = cause
        super().__init__(f"cannot assist on product_id {product_id}: {cause}")
