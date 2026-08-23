"""Injectable LLM port and OpenAI adapter. Delivered by C06b."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from jbg_ai.data.constants import DEFAULT_LLM_MODEL
from jbg_ai.data.errors import GenerateError
from jbg_ai.data.paths import PROMPT_MARKDOWN
from jbg_ai.data.quality import TextQualityTier


class PieceDraft(BaseModel):
    name: str
    description: str
    price: str


class PieceBatch(BaseModel):
    pieces: list[PieceDraft] = Field(default_factory=list)


@dataclass(frozen=True)
class DraftRequest:
    collection_name: str
    audience: str
    count: int
    theme: str = ""
    text_quality_tier: TextQualityTier = "rich"


class CatalogLlm(Protocol):
    model_id: str

    def draft_pieces(self, request: DraftRequest, prompt: str) -> list[PieceDraft]: ...


def load_prompt() -> str:
    return PROMPT_MARKDOWN.read_text(encoding="utf-8")


class OpenAICatalogLlm:
    """Thin wrapper around the official SDK. Imported only when generating."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_LLM_MODEL,
        base_url: str | None = None,
        temperature: float = 0.8,
    ) -> None:
        if not api_key.strip():
            raise GenerateError("OpenAI API key is required for generate.")
        from openai import OpenAI

        kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model
        self._temperature = temperature
        self.model_id = f"openai:{model}"

    def draft_pieces(self, request: DraftRequest, prompt: str) -> list[PieceDraft]:
        if request.collection_name.strip():
            collection_line = f"Colección (nombre de diseño, único): {request.collection_name}"
        else:
            collection_line = "Colección: ninguna. Estas piezas NO pertenecen a una línea."
        theme_line = request.theme.strip() or "(libre, coherente con el nombre de colección si lo hay)"
        user = (
            f"{collection_line}\n"
            f"Tema de línea: {theme_line}\n"
            f"Público / POS pensado (NO es el nombre de la colección): {request.audience}\n"
            f"text_quality_tier de ESTE lote (obedécelo en cada descripción): "
            f"{request.text_quality_tier}\n"
            f"Genera exactamente {request.count} piezas BASE de joyería vendible "
            "(nombre sin talla S/M/L/XL).\n"
            "Devuelve solo el JSON del schema."
        )
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user},
            ],
            response_format=PieceBatch,
            temperature=self._temperature,
            max_completion_tokens=8192,
        )
        message = completion.choices[0].message
        if message.parsed is None:
            raise GenerateError(f"OpenAI refused or returned no parse for {request.collection_name!r}.")
        pieces = list(message.parsed.pieces)
        if len(pieces) != request.count:
            raise GenerateError(
                f"OpenAI returned {len(pieces)} pieces for {request.collection_name!r}, "
                f"expected {request.count}."
            )
        return pieces
