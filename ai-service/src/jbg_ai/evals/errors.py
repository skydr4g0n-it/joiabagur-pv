"""Errors of the evaluation harness. Delivered by C24.

Every one of them **names what is missing and why the harness refuses to continue**.
A golden set that fails its composition check has to say which requirement it failed
and how far short it fell, because the alternative — a measurement that runs anyway —
is the failure mode the whole change exists to prevent.
"""

from __future__ import annotations


class EvalError(Exception):
    """Base of everything this package raises."""


class GoldenSetError(EvalError):
    """The golden set is malformed, or does not satisfy the composition it needs.

    Carries `requirement` when the fault is one of the traceability minimums, so a
    caller can report which dispute the set stopped being able to arbitrate rather
    than only that "validation failed".
    """

    def __init__(self, message: str, *, requirement: str | None = None) -> None:
        self.requirement = requirement
        super().__init__(f"[{requirement}] {message}" if requirement else message)


class ConfigurationError(EvalError):
    """A configuration file is absent, malformed, or names an unknown kind."""


class EvaluationUnavailable(EvalError):
    """A dependency the run needs is not reachable. A skip, never a silent zero."""
