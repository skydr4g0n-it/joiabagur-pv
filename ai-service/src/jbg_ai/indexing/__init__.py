"""Canonical source text and embedding client. Delivered by C11.

Library only: `jbg_ai.api.main` must not import this package. C13 writes the
index; C14/C23 reuse `embeddings.py` and must not edit it.
"""

from jbg_ai.indexing.constants import SOURCE_TEXT_VERSION
from jbg_ai.indexing.source_text import ProductSourceText, build_source_text, hash_source_text

__all__ = [
    "SOURCE_TEXT_VERSION",
    "ProductSourceText",
    "build_source_text",
    "hash_source_text",
]
