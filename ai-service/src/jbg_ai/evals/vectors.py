"""Frozen query embeddings, and the client that serves them. C24.

The alternative — calling the provider on every run — is not reproducible and multiplies the
bill by configurations times repetitions. The alternative to THAT, an offline stand-in
embedder, is ruled out by what it did in the previous change: a stand-in that scores lexical
overlap **is** the lexical branch, so it cannot arbitrate a dispute between the lexical branch
and the vector one, and when the real provider was finally used the verdict reversed and the
threshold that stand-in had calibrated turned out to cite four of five out-of-domain questions.

So the vectors are the REAL provider's, obtained once and versioned. Six decimals: about
700 KB for 48 queries, small enough to read and diff, and the rounding is orders of magnitude
below the distances being separated, which run from 0.366 to 0.700 on this corpus.

Keyed by `model_version_key`, because a vector from another model is not a stale vector — it is
a vector in a different space, and serving it would produce distances that mean nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from jbg_ai.evals.errors import EvaluationUnavailable
from jbg_ai.evals.golden import GOLDEN_DIR, VECTORS_FILE
from jbg_ai.indexing.embeddings import EmbedResult, document_version_key, model_version_key

#: Six decimals, fixed here so the writer and any later reader cannot disagree about precision.
DECIMALS = 6


@dataclass(frozen=True)
class FrozenVector:
    query_id: str
    text: str
    model_version_key: str
    vector: tuple[float, ...]


def vectors_path(root: Path | None = None) -> Path:
    return (root or GOLDEN_DIR) / VECTORS_FILE


def load_vectors(root: Path | None = None) -> tuple[FrozenVector, ...]:
    path = vectors_path(root)
    if not path.is_file():
        return ()
    out: list[FrozenVector] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            out.append(
                FrozenVector(
                    query_id=str(payload["query_id"]),
                    text=str(payload["text"]),
                    model_version_key=str(payload["model_version_key"]),
                    vector=tuple(float(value) for value in payload["vector"]),
                )
            )
    return tuple(out)


def write_vectors(vectors: list[FrozenVector], root: Path | None = None) -> Path:
    path = vectors_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in sorted(vectors, key=lambda value: value.query_id):
            handle.write(
                json.dumps(
                    {
                        "query_id": item.query_id,
                        "text": item.text,
                        "model_version_key": item.model_version_key,
                        "vector": [round(value, DECIMALS) for value in item.vector],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


@dataclass
class FrozenEmbeddingClient:
    """Serves the frozen vectors, and refuses rather than improvises when one is missing.

    It satisfies the same port the live client does, so the orchestrator cannot tell the
    difference — which is the point: the harness measures the pipeline, not a copy of it.

    A missing vector raises. Falling back to the provider would make a run's result depend on
    whether the file happened to be complete, and two runs of "the same configuration" would
    then differ for a reason nothing records.
    """

    model: str
    by_text: dict[str, tuple[float, ...]] = field(default_factory=dict)
    calls: int = 0

    def __post_init__(self) -> None:
        self.model_id = self.model
        self.document_version_key = document_version_key(self.model)
        self.model_version_key = model_version_key(self.model)

    @classmethod
    def from_file(cls, model: str, root: Path | None = None) -> "FrozenEmbeddingClient":
        key = model_version_key(model)
        frozen = [item for item in load_vectors(root) if item.model_version_key == key]
        if not frozen:
            raise EvaluationUnavailable(
                f"no frozen query vectors for {key}. Freeze them once against the real provider "
                "with `uv run evals freeze-vectors`; the harness will not call the provider "
                "behind your back, because a run that silently embeds is a run nobody can repeat"
            )
        return cls(model=model, by_text={item.text: item.vector for item in frozen})

    async def embed(self, texts: list[str]) -> EmbedResult:
        vectors: list[list[float]] = []
        for text in texts:
            frozen = self.by_text.get(text)
            if frozen is None:
                raise EvaluationUnavailable(
                    f"no frozen vector for {text!r} under {self.model_version_key}. Re-freeze "
                    "after changing a query: an evaluation must not embed on the fly"
                )
            vectors.append(list(frozen))
        self.calls += len(texts)
        return EmbedResult(
            vectors=vectors,
            embedding_model=self.model_id,
            embedding_version=self.document_version_key,
            cache_hits=len(texts),
        )
