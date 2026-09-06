"""Errors of the knowledge corpus. Delivered by C23.

Every one of them **names the file, and where it applies, the section**. A validation
message that says only "invalid claim scope" over 32 documents and 161 sections costs
the author a bisection; the file and the heading are the whole value of the error.
"""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base of everything this package raises."""


class KnowledgeCorpusError(KnowledgeError):
    """A document breaks one of the seven authoring rules.

    Carries `path` and, when the fault is inside a section, `section`. The string
    representation always leads with them, so the message a CLI prints is already the
    locator the author needs.
    """

    def __init__(self, message: str, *, path: str, section: str | None = None) -> None:
        self.path = path
        self.section = section
        where = f"{path}#{section}" if section else path
        super().__init__(f"{where}: {message}")


class KnowledgeCoverageError(KnowledgeError):
    """The corpus does not cover the closed vocabulary it is derived from.

    Separate from `KnowledgeCorpusError` because it is not a property of any one file:
    a missing material sheet is a fault of the corpus as a whole, and no path can be
    named for a document that does not exist.
    """


class KnowledgeIndexError(KnowledgeError):
    """Persistence or embedding failed while indexing the corpus."""


class KnowledgeSearchError(KnowledgeError):
    """A knowledge search could not be answered by its dependencies."""
