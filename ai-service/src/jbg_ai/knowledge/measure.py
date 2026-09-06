"""Mini-measurement of knowledge retrieval. Delivered by C23.

One question per document — the `eval_question` each one declares, which is authoring rule
7 — plus a group of **out-of-domain** questions whose correct result is no citation at all.
Reports recall at three, mean reciprocal rank and the abstention rate, and compares the
vector-only configuration against the fused one.

**It does not touch `ai.eval_run`, `ai.eval_case` or `ai.eval_result`.** Those tables belong
to C24, and using them would make C24 a prerequisite of this change, which would cost C23
exactly the property that makes it a good candidate now: it blocks nobody.

**And it runs offline**, over `offline.InMemoryKnowledgeIndex` and
`offline.LocalEmbeddingClient` — see that module for what the stand-in buys and what it
costs. The fusion, the threshold and the abstention it exercises are the real ones.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from jbg_ai.knowledge.chunking import chunk_corpus
from jbg_ai.knowledge.constants import OUT_OF_DOMAIN_PATH
from jbg_ai.knowledge.corpus import KnowledgeCorpus, load_corpus
from jbg_ai.knowledge.errors import KnowledgeCorpusError
from jbg_ai.knowledge.offline import InMemoryKnowledgeIndex, LocalEmbeddingClient
from jbg_ai.knowledge.search import KnowledgeCitation, search_knowledge

RECALL_AT = 3


@dataclass(frozen=True)
class Case:
    """One question and the document that must answer it, or `None` for out of domain."""

    question: str
    expected_document: str | None

    @property
    def out_of_domain(self) -> bool:
        return self.expected_document is None


@dataclass(frozen=True)
class CaseOutcome:
    case: Case
    citations: tuple[KnowledgeCitation, ...]

    @property
    def rank(self) -> int | None:
        """One-based position of the first citation from the expected document."""
        if self.case.expected_document is None:
            return None
        for position, citation in enumerate(self.citations, start=1):
            if citation.document_slug == self.case.expected_document:
                return position
        return None

    @property
    def passed(self) -> bool:
        if self.case.out_of_domain:
            return not self.citations
        rank = self.rank
        return rank is not None and rank <= RECALL_AT


@dataclass
class Report:
    label: str
    threshold: float
    hybrid_enabled: bool
    outcomes: list[CaseOutcome] = field(default_factory=list)

    @property
    def in_domain(self) -> list[CaseOutcome]:
        return [item for item in self.outcomes if not item.case.out_of_domain]

    @property
    def out_of_domain(self) -> list[CaseOutcome]:
        return [item for item in self.outcomes if item.case.out_of_domain]

    @property
    def recall_at_3(self) -> float:
        cases = self.in_domain
        if not cases:
            return 0.0
        hits = sum(1 for item in cases if item.rank is not None and item.rank <= RECALL_AT)
        return hits / len(cases)

    @property
    def mrr(self) -> float:
        cases = self.in_domain
        if not cases:
            return 0.0
        return sum(1.0 / item.rank if item.rank else 0.0 for item in cases) / len(cases)

    @property
    def abstention_rate(self) -> float:
        cases = self.out_of_domain
        if not cases:
            return 0.0
        return sum(1 for item in cases if not item.citations) / len(cases)

    @property
    def false_citations(self) -> list[CaseOutcome]:
        """Out-of-domain questions that came back with a citation. Each one is a failure."""
        return [item for item in self.out_of_domain if item.citations]

    @property
    def misses(self) -> list[CaseOutcome]:
        return [
            item
            for item in self.in_domain
            if item.rank is None or item.rank > RECALL_AT
        ]

    def format(self) -> str:
        lines = [
            f"{self.label}: threshold={self.threshold:.2f} hybrid={self.hybrid_enabled}",
            f"  Recall@{RECALL_AT}    {self.recall_at_3 * 100:5.1f} %  "
            f"({len(self.in_domain) - len(self.misses)}/{len(self.in_domain)})",
            f"  MRR           {self.mrr:5.3f}",
            f"  Abstención    {self.abstention_rate * 100:5.1f} %  "
            f"({len(self.out_of_domain) - len(self.false_citations)}/{len(self.out_of_domain)})",
        ]
        for outcome in self.misses:
            first = outcome.citations[0].citation_id if outcome.citations else "—"
            lines.append(
                f"    falla  {outcome.case.expected_document}: «{outcome.case.question}» "
                f"-> {first}"
            )
        for outcome in self.false_citations:
            lines.append(
                f"    cita fuera de dominio «{outcome.case.question}» -> "
                f"{outcome.citations[0].citation_id}"
            )
        return "\n".join(lines)


def load_out_of_domain(path: Path | None = None) -> tuple[Case, ...]:
    """Read the versioned out-of-domain questions."""
    target = path or OUT_OF_DOMAIN_PATH
    if not target.is_file():
        raise KnowledgeCorpusError("falta el fichero de preguntas fuera de dominio", path=str(target))
    payload = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    questions = payload.get("questions") or ()
    return tuple(
        Case(question=str(item["text"]).strip(), expected_document=None) for item in questions
    )


def build_fixture(corpus: KnowledgeCorpus, out_of_domain: Path | None = None) -> tuple[Case, ...]:
    """One case per document plus the out-of-domain group.

    The in-domain questions are **not** kept in a file of their own: each document declares
    its own, so a document and its question cannot drift apart.
    """
    in_domain = tuple(
        Case(question=document.eval_question, expected_document=document.slug)
        for document in corpus.documents
    )
    return in_domain + load_out_of_domain(out_of_domain)


async def run_report(
    cases: Sequence[Case],
    index: InMemoryKnowledgeIndex,
    embed: LocalEmbeddingClient,
    *,
    label: str,
    threshold: float,
    hybrid_enabled: bool,
    top_k: int = RECALL_AT,
) -> Report:
    report = Report(label=label, threshold=threshold, hybrid_enabled=hybrid_enabled)
    for case in cases:
        citations = await search_knowledge(
            case.question,
            embed=embed,
            index=index,
            top_k=top_k,
            distance_threshold=threshold,
            hybrid_enabled=hybrid_enabled,
        )
        report.outcomes.append(CaseOutcome(case=case, citations=citations))
    return report


def measure(
    *,
    threshold: float,
    hybrid_enabled: bool,
    label: str = "knowledge",
    corpus: KnowledgeCorpus | None = None,
) -> Report:
    """Synchronous entry point. Loads the corpus, builds the index, runs the fixture."""
    resolved = corpus or load_corpus()
    chunks = chunk_corpus(resolved)
    index = InMemoryKnowledgeIndex(chunks=chunks)
    embed = LocalEmbeddingClient()
    cases = build_fixture(resolved)
    return asyncio.run(
        run_report(
            cases,
            index,
            embed,
            label=label,
            threshold=threshold,
            hybrid_enabled=hybrid_enabled,
        )
    )


def sweep(
    thresholds: Sequence[float],
    *,
    hybrid_enabled: bool = True,
    corpus: KnowledgeCorpus | None = None,
) -> list[Report]:
    """One report per threshold, for the calibration rule of D8.

    The rule is **the strictest value that keeps the out-of-domain questions at zero without
    losing any of the questions that do have an answer** — a rule, not a number chosen by
    eye, which is why this returns the whole curve instead of a single verdict.
    """
    resolved = corpus or load_corpus()
    chunks = chunk_corpus(resolved)
    index = InMemoryKnowledgeIndex(chunks=chunks)
    embed = LocalEmbeddingClient()
    cases = build_fixture(resolved)

    async def _all() -> list[Report]:
        return [
            await run_report(
                cases,
                index,
                embed,
                label=f"threshold={value:.2f}",
                threshold=value,
                hybrid_enabled=hybrid_enabled,
            )
            for value in thresholds
        ]

    return asyncio.run(_all())


def calibrated_threshold(reports: Sequence[Report]) -> Report | None:
    """Apply the calibration rule of D8 to a sweep.

    D8 states it as *the strictest value that keeps the out-of-domain questions at zero
    without losing any of the ones that do have an answer*. Measured, **no value satisfies
    both halves**: against the offline stand-in, recall tops out at 78 % long before the
    abstention breaks, so a rule written as a conjunction would return nothing and calibrate
    nothing. The rule is therefore applied as what it means rather than as what it says:

    1. **Zero out-of-domain citations is inviolable.** A citation that is well formed and
       wrong is worse than no citation, and it is the failure the whole change guards
       against — so it is a constraint, never a term to trade against recall.
    2. Inside that band, **maximise Recall@3**: "without losing any that have an answer" is
       an objective once it cannot be an absolute.
    3. Ties go to the **stricter** value, which is the word D8 actually uses.

    Step 2 is not the same as "take the loosest safe threshold", and the sweep shows why:
    Recall@3 is **not monotonic** in the threshold. A looser cut admits distractor chunks
    that displace the right one out of the top three, so being generous "to be safe" costs
    recall as well as abstention.
    """
    safe = [report for report in reports if not report.false_citations]
    if not safe:
        return None
    best_recall = max(report.recall_at_3 for report in safe)
    return min(
        (report for report in safe if report.recall_at_3 >= best_recall),
        key=lambda report: report.threshold,
    )
