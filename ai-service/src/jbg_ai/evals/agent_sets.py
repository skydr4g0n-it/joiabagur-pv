"""The generator of the agent's **load set**. C32b.

**It measures accumulation, not quality**, and that distinction is the whole reason there are
two instruments instead of one. This one answers *what does a loop cost* — tokens, wall clock,
the growth of the accumulated context per turn, and the cost of each model arm. Nothing here
carries a judgement about whether an answer was good, and nothing here is ground truth.

**Why it is generated rather than written by hand, and why the other one is the opposite.** At
temperature zero and over a deterministic registry, repeating a transcript returns very nearly
the same thing, so repetitions buy no resolution on a high percentile: a p95 needs **variety of
transcripts**. Ground truth needs the opposite — few transcripts, carefully annotated — which
is what `evals/agent/calibration.yaml` is and why it is hand-written and small.

**Seeded from the catalogue's own vocabulary and from nothing else.** The terms come from
`enrichment/vocabularies.yaml`, which is the closed vocabulary the index is enriched with, so
the transcripts describe things this shop could actually be asked about. It is deliberately
**not** built with the synthetic world simulator, which would drag its own model of the world
into an instrument that only measures accumulation — the answer Q-3 already gave.

**It touches no evaluation set.** No query of `evals/golden/` is read, copied or referenced
here: the comparison the agent exists to enable is run over that set by a later change, and an
instrument seeded from it would make its own verdict meaningless. A test walks both directions.

    uv run python -m jbg_ai.evals.agent_sets            # rewrites evals/agent/load-set.yaml
    uv run python -m jbg_ai.evals.agent_sets --check    # fails if the file is stale
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

import yaml

from jbg_ai.assist.constants import (
    MAX_TRANSCRIPT_CHARS,
    MAX_TRANSCRIPT_TURNS,
    MAX_TURN_CHARS,
    TURN_ROLE_ASSISTANT,
    TURN_ROLE_OPERATOR,
)
from jbg_ai.data.paths import AI_SERVICE_ROOT

LOAD_SET = AI_SERVICE_ROOT / "evals" / "agent" / "load-set.yaml"
VOCABULARIES = AI_SERVICE_ROOT / "src" / "jbg_ai" / "enrichment" / "vocabularies.yaml"

#: Fixed, and fixed is the point: the set is an artefact in git and two people regenerating it
#: must get the same file, byte for byte. A run that wanted a different sample would change
#: this constant deliberately and the diff would say so.
SEED = "c32b-load/v1"

#: The identifier of the set, recorded in the provenance of every run that uses it.
SET_ID = "c32b-agent-load/v1"

#: How many transcripts, and the distribution of their lengths. **The lengths are the design.**
#: The curve this set exists to publish is the growth of the accumulated context per turn, and
#: a set of uniform length would produce one point on it. The weighting leans short because a
#: real counter conversation does, and the long ones are what populate the tail the p95 reads.
TURN_COUNT_WEIGHTS: dict[int, int] = {1: 22, 2: 22, 3: 18, 4: 12, 5: 8}

TARGET_SIZE = sum(TURN_COUNT_WEIGHTS.values())

#: Every piece type of the closed vocabulary, with the Spanish a person would actually say:
#: the indefinite singular and the bare plural. **The terms are still the vocabulary's** — this
#: adds grammar and nothing else, and a thirteenth piece type breaks
#: `test_every_piece_type_of_the_vocabulary_has_its_spanish` rather than producing
#: «busco un cadena», which is the same shape C32a gave the bucket-to-label map.
#:
#: It is not cosmetic for a measurement: a transcript in broken Spanish is a transcript that
#: invites a clarification the model would not otherwise ask for, and a clarification is a
#: turn. That would put grammar into the token and latency distributions this set exists to
#: publish, which is a confound with nothing to attribute it to afterwards.
PIECE_SPANISH: dict[str, tuple[str, str]] = {
    "anillo": ("un anillo", "anillos"),
    "pendientes": ("unos pendientes", "pendientes"),
    "collar": ("un collar", "collares"),
    "pulsera": ("una pulsera", "pulseras"),
    "colgante": ("un colgante", "colgantes"),
    "tobillera": ("una tobillera", "tobilleras"),
    "broche": ("un broche", "broches"),
    "cadena": ("una cadena", "cadenas"),
    "diadema": ("una diadema", "diademas"),
    "gemelos": ("unos gemelos", "gemelos"),
    "cinturon": ("un cinturón", "cinturones"),
    "llavero": ("un llavero", "llaveros"),
}

#: What the operator opens with. `{piece_one}` is the indefinite singular, `{piece_many}` the
#: bare plural, and the rest are filled from the closed vocabulary.
OPENINGS: tuple[str, ...] = (
    "busco {piece_one} de {material}",
    "quiero enseñarle {piece_many} de {material} para {occasion}",
    "me piden algo de {material} para {occasion}",
    "tengo un cliente que busca {piece_many} en tono {colour}",
    "querría ver {piece_many} de estilo {style}",
    "busco {piece_one} con {stone}",
    "algo de {material} para {occasion}, estilo {style}",
    "enséñame {piece_many} en {colour} que no sean caros",
    "necesito {piece_one} de {material} para regalar",
    "qué {piece_many} de {material} me recomiendas para {occasion}",
)

#: What the operator says next. These are the shapes that make a conversation a conversation:
#: the elliptical pivot, the objection, the constraint added late, and the question of trade
#: that the catalogue cannot answer on its own.
FOLLOW_UPS: tuple[str, ...] = (
    "¿y en {colour}?",
    "¿lo tienes en {material}?",
    "no le convence, ¿qué más hay?",
    "¿hay otra talla?",
    "¿eso se puede mojar?",
    "¿y algo más de estilo {style}?",
    "prefiere con {stone}",
    "¿le va bien a alguien con la piel sensible?",
    "¿tienes algo parecido pero para {occasion}?",
    "¿y si lo quiere para un regalo?",
    "enséñame otra cosa, esa no",
    "¿cómo se cuida eso?",
)

#: What the client *claims* the assistant said. **Attributed and never trusted**: it is the
#: client that composes the whole request, so these turns are load like any other and their
#: only job here is to occupy context, which is exactly what this set measures.
ASSISTANT_TURNS: tuple[str, ...] = (
    "te enseño lo que tenemos",
    "estas son las que encajan",
    "hay varias opciones, mira",
    "tengo dos que le pueden servir",
    "esta es la que más se acerca",
)


def _vocabulary() -> dict[str, list[str]]:
    """The closed vocabulary the index is enriched with. Read, never modified.

    `enrichment/vocabularies.yaml` is frozen against edits from outside enrichment — touching
    it forces a prompt bump and a re-enrichment — so this only reads it, which is the same
    relationship `retrieval/synonyms.py` already has with the file.
    """
    data = yaml.safe_load(VOCABULARIES.read_text(encoding="utf-8"))
    return {
        "piece_type": list(data["piece_type"]["terms"]),
        "material": list(data["materials"]["terms"]),
        "stone": list(data["stone_type"]["terms"]),
        "colour": list(data["color_tags"]["terms"]),
        "style": list(data["style_tags"]["terms"]),
        "occasion": list(data["occasion_tags"]["terms"]),
    }


def _fill(template: str, rng: random.Random, vocabulary: dict[str, list[str]]) -> str:
    """One filled line. The piece is drawn once and rendered in whichever form the slot needs,
    so a template naming both forms cannot name two different pieces."""
    values = {key: rng.choice(items) for key, items in vocabulary.items()}
    one, many = PIECE_SPANISH[values["piece_type"]]
    return template.format(piece_one=one, piece_many=many, **values)


def _turn_counts(rng: random.Random) -> list[int]:
    counts = [length for length, many in TURN_COUNT_WEIGHTS.items() for _ in range(many)]
    rng.shuffle(counts)
    return counts


def build(seed: str = SEED) -> dict[str, Any]:
    """The whole set, deterministically. **No provider, no database, no network.**

    An operator turn, then an attributed assistant turn, then another operator turn, and so on:
    a transcript of `n` operator turns carries `n - 1` assistant turns between them, which is
    the shape a stateless multi-turn contract actually receives.
    """
    rng = random.Random(seed)
    vocabulary = _vocabulary()
    transcripts: list[dict[str, Any]] = []

    for index, operator_turns in enumerate(_turn_counts(rng), start=1):
        turns: list[dict[str, str]] = [
            {
                "role": TURN_ROLE_OPERATOR,
                "text": _fill(rng.choice(OPENINGS), rng, vocabulary),
            }
        ]
        for _ in range(operator_turns - 1):
            turns.append(
                {"role": TURN_ROLE_ASSISTANT, "text": rng.choice(ASSISTANT_TURNS)}
            )
            turns.append(
                {
                    "role": TURN_ROLE_OPERATOR,
                    "text": _fill(rng.choice(FOLLOW_UPS), rng, vocabulary),
                }
            )
        transcripts.append(
            {
                "id": f"L{index:03d}",
                "operator_turns": operator_turns,
                "turns": turns,
            }
        )

    return {
        "id": SET_ID,
        "seed": seed,
        "generated_by": "python -m jbg_ai.evals.agent_sets",
        "measures": "load",
        "carries_ground_truth": False,
        "size": len(transcripts),
        "by_operator_turns": {
            str(length): sum(1 for item in transcripts if item["operator_turns"] == length)
            for length in sorted(TURN_COUNT_WEIGHTS)
        },
        "transcripts": transcripts,
    }


HEADER = f"""\
# Conjunto de CARGA del bucle agéntico — C32b. **GENERADO, no escrito a mano.**
#
# `uv run python -m jbg_ai.evals.agent_sets` lo reescribe; `--check` falla si está atrasado.
# No se edita a mano: lo que se edita es el guion, y el diff del fichero dice qué cambió.
#
# ── Qué mide, y qué NO mide ────────────────────────────────────────────────────────────────
#
# Mide **acumulación**: tokens, reloj de pared, la curva de crecimiento del contexto por vuelta
# y el coste de cada brazo de modelo. **No mide calidad y no trae verdad de terreno.** Ninguna
# de estas transcripciones lleva anotada la herramienta que debería elegirse, y ninguna se puede
# usar para decir si una respuesta fue buena. Para eso está `calibration.yaml`, que es pequeño,
# está escrito a mano y está declarado `calibration-only`.
#
# ── Por qué generado, y por qué el otro es lo contrario ────────────────────────────────────
#
# A temperatura cero y sobre un registro determinista, repetir una transcripción devuelve casi
# lo mismo: las repeticiones **no compran resolución de p95**. Un percentil alto necesita
# VARIEDAD de transcripciones; la verdad de terreno necesita lo contrario, pocas y anotadas.
# Son dos preguntas distintas y por eso son dos instrumentos de tamaños muy distintos.
#
# ── De dónde sale el vocabulario ───────────────────────────────────────────────────────────
#
# De `src/jbg_ai/enrichment/vocabularies.yaml` y de nada más: es el vocabulario cerrado con el
# que se enriquece el índice, así que estas conversaciones hablan de cosas por las que a esta
# tienda se le puede preguntar de verdad. **No** se usa el simulador de mundo sintético, que
# arrastraría su modelo del mundo a un instrumento que sólo mide acumulación.
#
# ── El muro de contaminación ───────────────────────────────────────────────────────────────
#
# **Ninguna consulta de `evals/golden/` se lee, se copia ni se referencia aquí.** La comparación
# entre el pipeline determinista y el agente se corre sobre ese conjunto en un change posterior,
# y un instrumento sembrado de él inhabilitaría su propio veredicto.
# `test_no_transcript_of_either_agent_set_reuses_a_golden_query` recorre las dos direcciones.
#
# ── La forma, que es deliberada ────────────────────────────────────────────────────────────
#
# Las longitudes están repartidas a propósito: la curva que este conjunto existe para publicar
# es el crecimiento del contexto **por vuelta**, y un conjunto de longitud uniforme daría un
# solo punto de esa curva. Los turnos atribuidos al asistente son carga como cualquier otra —
# los compone el cliente, igual que los del operario.
#
# Topes del contrato que todas cumplen: ≤ {MAX_TRANSCRIPT_TURNS} turnos,
# ≤ {MAX_TURN_CHARS} caracteres por turno, ≤ {MAX_TRANSCRIPT_CHARS} en total.
"""


def render(document: dict[str, Any]) -> str:
    return HEADER + yaml.safe_dump(
        document, allow_unicode=True, sort_keys=False, width=100
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m jbg_ai.evals.agent_sets",
        description="Generate the agent load set from the catalogue's closed vocabulary",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write: fail if the committed file is not what the generator produces",
    )
    args = parser.parse_args(argv)

    rendered = render(build())
    if args.check:
        current = LOAD_SET.read_text(encoding="utf-8") if LOAD_SET.is_file() else ""
        if current != rendered:
            print(
                "evals/agent/load-set.yaml is stale; regenerate it with "
                "`uv run python -m jbg_ai.evals.agent_sets`",
                file=sys.stderr,
            )
            return 1
        print(f"{LOAD_SET.name} is up to date ({build()['size']} transcripts)")
        return 0

    LOAD_SET.parent.mkdir(parents=True, exist_ok=True)
    LOAD_SET.write_text(rendered, encoding="utf-8")
    print(f"wrote {LOAD_SET} ({build()['size']} transcripts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
