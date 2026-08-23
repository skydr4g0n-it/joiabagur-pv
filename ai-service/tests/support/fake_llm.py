"""Injectable catalog LLM that never opens a socket. Delivered by C06b."""

from __future__ import annotations

from jbg_ai.data.llm import DraftRequest, PieceDraft


class FakeCatalogLlm:
    model_id = "fake:c06b"

    def __init__(
        self,
        *,
        overlong_on: tuple[str, int] | None = None,
        expensive_on: tuple[str, int] | None = None,
        empty_on: tuple[str, int] | None = None,
    ) -> None:
        self.overlong_on = overlong_on
        self.expensive_on = expensive_on
        self.empty_on = empty_on
        self.calls: list[DraftRequest] = []

    def draft_pieces(self, request: DraftRequest, prompt: str) -> list[PieceDraft]:
        _ = prompt
        self.calls.append(request)
        pieces: list[PieceDraft] = []
        for index in range(request.count):
            label = request.collection_name or "suelta"
            description = _description_for(request.text_quality_tier, label, request.audience)
            if request.collection_name == (self.overlong_on or (None, None))[0] and index == (
                self.overlong_on or (None, None)
            )[1]:
                description = "x" * 1001
            if request.collection_name == (self.expensive_on or (None, None))[0] and index == (
                self.expensive_on or (None, None)
            )[1]:
                price = "50000.00"
            else:
                price = f"{80 + index}.50"
            name = f"Colgante {label} pieza{index}"
            if self.empty_on and request.collection_name == self.empty_on[0] and index == self.empty_on[1]:
                description = ""
            pieces.append(PieceDraft(name=name, description=description, price=price))
        return pieces


def _description_for(tier: str, label: str, audience: str) -> str:
    if tier == "short":
        return "Plata."
    if tier == "sparse":
        return f"Pieza de {label} en plata, de peso contenido."
    return (
        f"{label} en plata de ley y ónix, con un gesto de joyero claro. "
        f"Está pensada para un {audience} que busca presencia en vitrina. "
        f"El metal y la piedra se trabajan a mano, sin prisa. "
        f"Queda con cuerpo en escaparate y se lee de lejos."
    )
