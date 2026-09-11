"""Evaluation harness: golden set, pooling, metrics, baselines, runner. Delivered by C24.

The package produces a `Report` and writes it to `ai-service/evals/results/`. Persistence to
`ai.eval_run` / `eval_case` / `eval_result` is a separate sink that the runner does not import:
the artefact in git is the normative copy and the database is the optional one.
"""
