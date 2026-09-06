"""The second index: general commercial knowledge, chunked, cited and searchable.

Delivered by C23. `ai.product_document` answers "show me silver rings"; this package
answers "can this ring get wet?", which lives in no product.

Four modules, and the split is the one the change owns end to end — ingestion *and*
query — which is why it is a package of its own rather than a file inside `indexing/`:

- `corpus`   — discovery, parsing and the seven authoring rules
- `chunking` — one `##` section, one chunk, one citation. A pure function
- `indexer`  — deterministic identity and idempotent persistence into the C05 tables
- `search`   — vector plus lexical, fused by rank, with an abstention of its own

Nothing here creates, alters or drops a schema object, and nothing here opens an HTTP route.
"""

from jbg_ai.knowledge.chunking import KnowledgeChunk, chunk_corpus, chunk_document, citation_id
from jbg_ai.knowledge.corpus import (
    KnowledgeCorpus,
    KnowledgeDocument,
    Section,
    load_corpus,
    parse_document,
    validate_corpus,
)
from jbg_ai.knowledge.errors import (
    KnowledgeCorpusError,
    KnowledgeCoverageError,
    KnowledgeError,
    KnowledgeIndexError,
    KnowledgeSearchError,
)

__all__ = [
    "KnowledgeChunk",
    "KnowledgeCorpus",
    "KnowledgeCorpusError",
    "KnowledgeCoverageError",
    "KnowledgeDocument",
    "KnowledgeError",
    "KnowledgeIndexError",
    "KnowledgeSearchError",
    "Section",
    "chunk_corpus",
    "chunk_document",
    "citation_id",
    "load_corpus",
    "parse_document",
    "validate_corpus",
]
