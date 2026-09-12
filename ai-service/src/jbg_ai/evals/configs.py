"""The configurations under evaluation, declared as files rather than written as code. C24.

Five rows of one ablation table, and only two of them are the live pipeline with different
knob values. The other three exist because the question the project has to answer is not
"which fusion weight is best" but **"does semantic search beat what the jeweller already had"**,
and that question has no answer unless what she had is in the table.

* `v0-nombre` — the product search that existed before any of this: substring match over the
  name plus an exact code, alphabetical. It is the baseline of decision 12.
* `v0-fts` — the degraded Spanish full-text searcher, which this project's own earlier work
  built. It is NOT "what she had", and calling the two by one name would hide the most useful
  reading of the table: how much of the gain is tokenising Spanish, which is free, and how much
  is semantic retrieval, which is not.
* `v0-cag` — the whole catalogue in the model's context, no retrieval. Bounded and dated.
* `v1-vectorial` / `v2b-fusion` / `v3-senales` — the live orchestrator, parameterised. Not a
  copy of it: a harness that re-implemented the pipeline would measure the copy, which is the
  subtle form of the mistake the offline stand-in embedder made in an earlier change. That rule
  is also why `v2-hibrido` is not kept runnable here now that its composition is gone:
  restating a retired pipeline inside the harness to preserve a row would measure the
  restatement. The row survives as an archived artefact instead.

A configuration is a file so that adding one — a reranker, say — is a YAML plus a run rather
than a patch, which is what makes the reranking protocol executable instead of rhetorical.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from jbg_ai.data.paths import AI_SERVICE_ROOT
from jbg_ai.evals.errors import ConfigurationError

CONFIG_DIR = AI_SERVICE_ROOT / "evals" / "configs"

KIND_NAME_SUBSTRING = "name-substring"
KIND_FULL_TEXT = "full-text"
KIND_PIPELINE = "pipeline"
KIND_CONTEXT_ONLY = "context-only"

KINDS = (KIND_NAME_SUBSTRING, KIND_FULL_TEXT, KIND_PIPELINE, KIND_CONTEXT_ONLY)

#: The order the ablation table is read in, from what existed before to what ships today.
#:
#: `v2-hibrido` left this tuple with C25bis. It was the published baseline row, and it was
#: measured under a composition that no longer exists, so it is no longer a row that can be
#: run: it is a CITATION. Its figures, its provenance and the configuration it was measured
#: under are versioned — the report and the per-query JSONL in `evals/results/`, the YAML in
#: `evals/configs/retired/` — and every citation of it says historical and not re-executable.
ABLATION_ORDER = (
    "v0-nombre",
    "v0-fts",
    "v0-cag",
    "v1-vectorial",
    "v2b-fusion",
    "v3-senales",
)

#: Configurations that produce a ranked list over the index, and therefore contribute to the
#: judgement pool. `v0-cag` does not: it answers in prose over a context window, so there is no
#: list of its own to pool, and pooling from it would put documents in the set that no
#: retriever ever ranked.
#:
#: This tuple says who ENTERS the next pooling run, which is not the same question as who
#: entered the last one. `judgements.jsonl` keeps naming `v2-hibrido` in the `pooled_in` of
#: every document it contributed, and that is correct and must not be edited: the tuple is a
#: knob, the judgement is a record.
POOLED = (
    "v0-nombre",
    "v0-fts",
    "v1-vectorial",
    "v2b-fusion",
    "v3-senales",
)


@dataclass(frozen=True)
class EvalConfig:
    """One row of the ablation table."""

    id: str
    kind: str
    label: str
    rationale: str
    #: True when the configuration sends anything to a paid provider. It decides whether cost
    #: is a measured figure or a recorded zero — and zero is a value, never a blank.
    uses_provider: bool
    mode: str | None = None
    expand_synonyms: bool | None = None
    rrf_k: int | None = None
    #: C25bis retired `fusion`, `weight_typed`, `weight_expanded` and `weight_vector`. There is
    #: one composition and no per-list weights, so a configuration naming any of them now fails
    #: the unknown-key check below rather than quietly producing a row that measured something
    #: else. `evals/configs/retired/v2-hibrido.yaml` is exactly such a file, kept as the record
    #: of what the published baseline was measured under — and it no longer loads, by design.
    branch_weight_lexical: float | None = None
    branch_weight_vector: float | None = None
    #: C25 coverage rule: `continuous` (adopted) or `none` (the control arm, and the rollback).
    #: Neither is a strength parameter - the scaling IS the proportion.
    coverage_rule: str | None = None
    #: C25 reading scope: the point of sale whose availability and rotation are READ, without
    #: restricting the candidate set. Distinct from `pos_prefilter`, which restricts it. The
    #: two are separate keys because they answer separate questions, and a single flag doing
    #: both is exactly why the demotion C22 shipped never fired in the published run.
    signal_pos_id: str | None = None
    business_weight_availability: float | None = None
    #: C25 abstention. `None` follows the live default (on); the baseline row pins it OFF, the
    #: same way it pins the flat fusion, because it exists to reproduce the configuration that
    #: was published BEFORE this change and the rule did not exist then.
    abstain: bool | None = None
    branch_depth: int | None = None
    pos_prefilter: bool = False
    max_results: int = 60
    context_budget_tokens: int | None = None
    context_model: str | None = None
    subset_category: str | None = None

    @property
    def pooled(self) -> bool:
        return self.id in POOLED

    @classmethod
    def from_mapping(cls, payload: dict[str, Any], *, where: str) -> "EvalConfig":
        missing = {"id", "kind", "label", "rationale", "uses_provider"} - set(payload)
        if missing:
            raise ConfigurationError(f"{where}: missing {sorted(missing)}")
        kind = str(payload["kind"])
        if kind not in KINDS:
            raise ConfigurationError(f"{where}: unknown kind {kind!r}, expected one of {KINDS}")
        known = {field for field in cls.__dataclass_fields__}
        unknown = set(payload) - known
        if unknown:
            raise ConfigurationError(
                f"{where}: unknown keys {sorted(unknown)}. A misspelt knob that is silently "
                "ignored produces a row of the table measuring something else"
            )
        return cls(**{key: payload[key] for key in payload})


def load_config(config_id: str, *, directory: Path | None = None) -> EvalConfig:
    base = directory or CONFIG_DIR
    path = base / f"{config_id}.yaml"
    if not path.is_file():
        available = ", ".join(sorted(item.stem for item in base.glob("*.yaml"))) or "none"
        raise ConfigurationError(f"{path} does not exist. Available: {available}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConfigurationError(f"{path}: the file must be a mapping")
    config = EvalConfig.from_mapping(payload, where=str(path))
    if config.id != config_id:
        raise ConfigurationError(
            f"{path}: declares id {config.id!r} but is filed as {config_id!r}. The file name is "
            "how a run is asked for, so the two must agree"
        )
    return config


def load_all(directory: Path | None = None) -> tuple[EvalConfig, ...]:
    """Every configuration, in ablation order, with anything unlisted appended after."""
    base = directory or CONFIG_DIR
    found = {path.stem: load_config(path.stem, directory=base) for path in base.glob("*.yaml")}
    ordered = [found.pop(name) for name in ABLATION_ORDER if name in found]
    ordered.extend(found[name] for name in sorted(found))
    return tuple(ordered)


def iter_pooled(configs: tuple[EvalConfig, ...]) -> Iterator[EvalConfig]:
    return (config for config in configs if config.pooled)
