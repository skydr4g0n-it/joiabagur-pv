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


class RouterProviderError(AssistError, RuntimeError):
    """The classifier failed, timed out, or returned something that is not a valid label. C31.

    **It never reaches the router either, and for a stronger reason than its sibling above.**
    A classifier fault is a *fail-open*: the request proceeds unclassified and is served exactly
    as it was before this capability routed anything, with the cause recorded. Failing closed
    would turn a provider blip into a universal polite refusal — a total outage of the useful
    path dressed up as a safety measure.

    The class exists so that the fail-open is **a branch with one thing to catch and one
    `cause` to log**, rather than a bare `except Exception` whose reason nobody can read
    afterwards. A label outside the closed vocabulary raises it with `cause="parse"`: an
    unknown value is treated as an unparseable reply and never propagated.
    """

    def __init__(self, message: str, *, cause: str) -> None:
        self.cause = cause
        super().__init__(message)


class AgentProviderError(AssistError, RuntimeError):
    """The loop's provider failed, timed out, or returned something unusable. C32b.

    **It never reaches the router either, and it costs the loop a turn rather than the
    request.** A fault on the first turn leaves a request with no evidence, which is served as
    a partial response with the cause recorded; a fault on a later turn leaves the evidence the
    earlier turns gathered, which is served the same way. Failing the request instead would
    throw away work already paid for, which is the argument its two siblings above already make
    and this one inherits without change.

    Third class and not a shared one, for the reason the third client is not a subclass of the
    second: `cause` is partitioned per stage in the log and in the report, and one class for
    three stages would make «which stage degraded» a string somebody has to parse.
    """

    def __init__(self, message: str, *, cause: str) -> None:
        self.cause = cause
        super().__init__(message)


class TranscriptError(AssistError, ValueError):
    """The transcript breaks one of its three declared caps. C32b.

    Raised **before any provider call is made**, which is the requirement and not an
    optimisation: the caps exist because carrying the conversation in the request hands the
    client the factor that dominates the cost of a loop, and a cap enforced after the first
    call has already let the request buy what it was meant to prevent.

    In the HTTP path the request model rejects most of this first. It exists because the layer
    is also a callable — the evaluation harness drives it directly, as it drives every other
    part of this service — and a library that trusted its caller to have run a validator would
    be one refactor away from serving what it declares it refuses.
    """


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
