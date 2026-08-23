"""Constants for the C09 enrichment pipeline."""

from __future__ import annotations

PROMPT_VERSION = "enrichment/v1"
DEFAULT_RAG_LLM_MODEL = "openai/gpt-4o"
DEFAULT_RAG_LLM_CONCURRENCY = 8

CONFIDENCE_RULE = 1.0
CONFIDENCE_SPAN = 0.85
CONFIDENCE_NO_SPAN = 0.45
CONFIDENCE_ABSENT = 0.20

RESIDUAL_STONE = "piedra"
