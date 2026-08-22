from __future__ import annotations

import hashlib
import re

from catalog_pipeline.constants import DESCRIPTION_MAX_LEN
from catalog_pipeline.grouping import normalize_name, strip_accents
from catalog_pipeline.models import SourceRow, TextQualityTier

_PIECE_TYPES = (
    ("pendientes", "pendientes"),
    ("criollas", "criollas"),
    ("anillo", "anillo"),
    ("colgante", "colgante"),
    ("pulsera", "pulsera"),
    ("brazalete", "brazalete"),
    ("tobillera", "tobillera"),
    ("collar", "collar"),
    ("macrame", "macramé"),
    ("broche", "broche"),
    ("cadena", "cadena"),
)

_PIECE_ARTICLE = {
    "pendientes": "Los pendientes",
    "criollas": "Las criollas",
    "anillo": "El anillo",
    "colgante": "El colgante",
    "pulsera": "La pulsera",
    "brazalete": "El brazalete",
    "tobillera": "La tobillera",
    "collar": "El collar",
    "macramé": "El macramé",
    "broche": "El broche",
    "cadena": "La cadena",
}

_MATERIAL_PHRASES = (
    ("plata de ley y oro", "plata de ley y oro"),
    ("hilo encerado y oro", "hilo encerado y oro 18k"),
    ("hilo encerado", "hilo encerado"),
    ("bano de oro", "baño de oro"),
    ("cadena de plata", "cadena de plata"),
    ("plata de ley", "plata de ley"),
    ("18 kl", "oro de 18k"),
    ("18kl", "oro de 18k"),
    ("18k", "oro de 18k"),
    ("oro", "oro"),
    ("plata", "plata"),
    ("perlas de rio", "perlas de río"),
    ("perlas", "perlas"),
)

_SIZE_LABELS = (
    ("extramini", "en tamaño extramini"),
    ("mini", "en tamaño mini"),
    ("xxs", "en talla XXS"),
    ("xs", "en talla XS"),
    ("xxl", "en talla XXL"),
    ("xl", "en talla XL"),
    ("largos", "en versión larga"),
    ("largo", "en versión larga"),
    ("pequeno", "en tamaño pequeño"),
    ("pequena", "en tamaño pequeño"),
    ("mediano", "en tamaño mediano"),
    ("grande", "en tamaño grande"),
    ("grandes", "en tamaño grande"),
)

_META_PHRASES = (
    "fotografia",
    "fotografias",
    "foto",
    "fotos",
    "imagen",
    "imagenes",
    "ficha de origen",
    "ficha original",
    "el export",
    "no consta",
    "no se certifican",
    "no se cuentan piedras",
    "el catalogo no incluye",
    "registro de entrada",
    "registro de gama",
    "si tuvieras la foto",
    "imaginar",
    "imaginarse",
)

_FORBIDDEN_UNEVIDENCED = (
    "diamante",
    "diamantes",
    "zafiro",
    "zafiros",
    "esmeralda",
    "esmeraldas",
    "rubi",
    "rubies",
    "circonita",
    "circonitas",
    "perla cultivada",
    "estuche",
    "certificado gemologico",
)

_CONDITIONAL_ACCESSORIES = (
    "perla",
    "perlas",
    "cadena",
    "cadenas",
    "cierre",
    "cierres",
)


def price_band(price) -> str:
    value = float(price)
    if value < 80:
        return "entrada"
    if value <= 250:
        return "media"
    return "alta"


def _contains(normalized: str, needle: str) -> bool:
    return f" {needle} " in f" {normalized} "


def infer_piece_type(normalized_name: str) -> str | None:
    for token, label in _PIECE_TYPES:
        if _contains(normalized_name, token) or normalized_name.startswith(token):
            return label
    return None


def infer_material(name: str, description: str) -> str | None:
    blob = normalize_name(f"{name} {description}")
    for token, label in _MATERIAL_PHRASES:
        if _contains(blob, token) or blob.endswith(token) or blob.startswith(token):
            return label
    return None


def infer_scale(normalized_name: str) -> str | None:
    tokens = set(normalized_name.split())
    for token, label in _SIZE_LABELS:
        if token in tokens:
            return label
    leftover = normalized_name.split()
    for token in leftover:
        if token in {"s", "m", "l"}:
            return f"en talla {token.upper()}"
    return None


def _motif(name: str, piece: str | None) -> str | None:
    skip = {
        "mini",
        "extramini",
        "s",
        "m",
        "l",
        "xl",
        "xs",
        "xxl",
        "xxs",
        "oro",
        "plata",
        "dorado",
        "largos",
        "largo",
        "abierto",
        "cerrado",
        "pequeno",
        "pequena",
        "mediano",
        "grande",
        "grandes",
    }
    if piece:
        skip.add(normalize_name(piece).replace("é", "e"))
    kept: list[str] = []
    for word in name.split():
        token = normalize_name(word)
        if not token or token in skip or token.isdigit():
            continue
        kept.append(word)
    if not kept:
        return None
    return " ".join(kept[:8])


def _style_index(sku: str) -> int:
    return int(hashlib.sha256(sku.encode("utf-8")).hexdigest()[:8], 16)


def _wear_sentence(piece: str | None, style: int) -> str | None:
    options = {
        "pendientes": (
            "Se apoyan en el lóbulo y el motivo se lee de frente.",
            "Cuelgan con un peso ligero; al girar la cabeza el dibujo queda a la vista.",
            "El motivo ocupa el centro de la oreja y se lee de frente.",
        ),
        "criollas": (
            "Cierran el óvalo de la oreja y dejan el motivo al exterior.",
            "Rodean el lóbulo con un trazo continuo y el dibujo se lee de lado.",
        ),
        "anillo": (
            "El volumen se nota al cerrar la mano; el motivo queda arriba.",
            "Abraza el dedo y el relieve se lee de frente al apoyar la mano.",
            "Sienta bajo, con el dibujo centrado sobre el nudillo.",
        ),
        "colgante": (
            "Cae centrado sobre el pecho y el relieve se lee de cerca.",
            "El motivo queda al frente, con un caído corto y estable.",
            "Descansa sobre la clavícula y el dibujo se ve de frente.",
        ),
        "pulsera": (
            "Rodea la muñeca y el motivo queda al exterior.",
            "Ciñe la muñeca sin rígido; el dibujo se lee al apoyar la mano.",
        ),
        "brazalete": (
            "Abraza el antebrazo y deja el dibujo a la vista.",
            "El arco se abre al pasar la muñeca y el motivo queda al frente.",
        ),
        "tobillera": (
            "Sigue el tobillo con un trazo ligero.",
            "Rodea el tobillo y el metal se lee al caminar.",
        ),
        "collar": (
            "Cae sobre el cuello y el motivo queda centrado al frente.",
            "Rodea el cuello con un caído suave; el dibujo se lee de cerca.",
        ),
        "macramé": (
            "El nudo se adapta a la muñeca y el motivo queda al centro.",
            "El hilo ciñe sin rígido; la pieza de metal se lee al exterior.",
        ),
        "broche": (
            "Se sujeta al tejido y el motivo queda de frente.",
            "El relieve se lee al pinzarlo sobre la tela.",
        ),
        "cadena": (
            "El eslabón corre ligero sobre la piel y el brillo se reparte al moverse.",
            "Cae con un trazo continuo, sin nudos a la vista.",
        ),
    }
    if piece is None or piece not in options:
        return None
    choices = options[piece]
    return choices[style % len(choices)]


def _material_sentence(material: str | None, style: int) -> str | None:
    if not material:
        return None
    options = {
        "plata de ley": (
            "Es de plata de ley, con un brillo claro y frío.",
            "La plata de ley deja un destello limpio sobre el motivo.",
            "En plata de ley, el metal se ve satinado o pulido según la luz.",
        ),
        "oro de 18k": (
            "Es de oro de 18k, con un tono cálido y compacto.",
            "El oro de 18k cubre el motivo con un brillo denso.",
            "En oro de 18k, el color se mantiene uniforme al girar la pieza.",
        ),
        "oro": (
            "El oro da un tono cálido al motivo.",
            "En oro, el brillo se concentra en los relieves.",
        ),
        "plata": (
            "La plata deja un brillo claro sobre el dibujo.",
            "En plata, el motivo se lee nítido contra el metal.",
        ),
        "baño de oro": (
            "El baño de oro cubre la superficie con un destello uniforme.",
            "Lleva baño de oro; el tono cálido recorre todo el motivo.",
        ),
        "plata de ley y oro": (
            "Combina plata de ley y oro; los dos metales se leen en el mismo motivo.",
            "Plata de ley y oro conviven en la pieza, con el contraste a la vista.",
        ),
        "hilo encerado": (
            "El hilo encerado ciñe con un tacto mate; el metal del motivo contrasta.",
            "Va montada en hilo encerado, flexible sobre la muñeca.",
        ),
        "hilo encerado y oro 18k": (
            "El hilo encerado sujeta un motivo de oro de 18k.",
            "Hilo encerado y oro de 18k: el nudo es mate y el metal, cálido.",
        ),
        "cadena de plata": (
            "Cuelga de una cadena de plata, fina y continua.",
            "La cadena de plata deja el motivo centrado al caer.",
        ),
        "perlas de río": (
            "Las perlas de río se leen una a una, con un brillo suave.",
            "Monta perlas de río; el tono es irregular y vivo.",
        ),
        "perlas": (
            "Las perlas se suceden con un brillo suave.",
            "El collar de perlas tiene un caído regular y un tacto fresco.",
        ),
    }
    choices = options.get(material)
    if not choices:
        return f"El material es {material}."
    return choices[style % len(choices)]


def _presence_sentence(band: str, piece: str | None, style: int) -> str:
    if band == "alta":
        choices = (
            "El metal pesa en la mano y el brillo se concentra en los relieves.",
            "Tiene presencia: el volumen se nota al acercarla y el destello es denso.",
            "Pieza de peso contenido, con un brillo que se sostiene a la luz del día.",
        )
    elif band == "media":
        choices = (
            "El volumen se nota sin recargar; queda bien de día y de tarde.",
            "Presencia clara, de uso frecuente, con el motivo bien definido.",
            "Se ve entera de un vistazo: silueta nítida y metal a la vista.",
        )
    else:
        choices = (
            "Pieza ligera, de uso diario, que no disputa la atención.",
            "Discreta de cerca y legible de frente; cabe en el día a día.",
            "Un gesto pequeño: el motivo se lee y el peso casi no se nota.",
        )
    extra = ""
    if piece == "pendientes" and style % 2:
        extra = ", y en la oreja el dibujo queda estable"
    return choices[style % len(choices)].rstrip(".") + extra + "."


def _collection_sentence(collection_name: str, style: int) -> str | None:
    text = collection_name.strip()
    if not text:
        return None
    if style % 2 == 0:
        return f"Pertenece a {text}."
    return f"De {text}."


def _motif_sentence(motif: str | None, piece: str | None, style: int) -> str | None:
    if not motif:
        return None
    if piece == "pendientes":
        options = (
            f"El motivo de {motif} se recorta nítido sobre el lóbulo.",
            f"Se ve {motif}, compacto, con el relieve a la luz.",
            f"El dibujo de {motif} ocupa el frente de la pieza.",
        )
    elif piece == "anillo":
        options = (
            f"El motivo de {motif} queda arriba, con el relieve al cerrar el puño.",
            f"El motivo de {motif} se lee de frente sobre el aro.",
        )
    elif piece == "colgante":
        options = (
            f"El motivo de {motif} queda centrado al caer y el relieve se sigue con el dedo.",
            f"Se lee {motif} de cerca, con el contorno bien marcado.",
        )
    else:
        options = (
            f"El motivo de {motif} se lee de frente, con el relieve a la vista.",
            f"Se ve {motif} nítido; el contorno no se pierde al girar la pieza.",
            f"El dibujo de {motif} es el centro de la silueta.",
        )
    return options[style % len(options)]


def _lead(
    row: SourceRow,
    piece: str | None,
    material: str | None,
    scale: str | None,
    motif: str | None,
    style: int,
) -> str:
    display_name = " ".join(row.name.split())
    material_bit = f", en {material}" if material else ""
    scale_bit = f", {scale}" if scale else ""
    article = _PIECE_ARTICLE.get(piece or "", "")
    if style % 4 == 0 and article and motif:
        return f"{article} con {motif}{scale_bit}{material_bit}."
    if style % 4 == 1:
        return f"{display_name}{material_bit}."
    if style % 4 == 2 and article:
        motif_bit = f" con {motif}" if motif else ""
        return f"{article}{motif_bit}{scale_bit}{material_bit}."
    return f"{display_name}{scale_bit}{material_bit}."


def _original_missing_from_text(original: str, material: str | None, assembled: str) -> str | None:
    text = original.strip()
    if not text:
        return None
    assembled_norm = normalize_name(assembled)
    original_norm = normalize_name(text)
    if original_norm and (original_norm in assembled_norm or _contains(assembled_norm, original_norm)):
        return None
    if material:
        material_norm = normalize_name(material)
        if original_norm == material_norm or original_norm in material_norm:
            return None
        if original_norm in {"18kl", "18 kl", "18k", "18 k"} and "18k" in material_norm:
            return None
        if original_norm in {"plata de ley", "plata"} and "plata" in material_norm:
            return None
    return text


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" .", ".").replace(" ,", ",")
    text = re.sub(r",,", ",", text)
    text = re.sub(r"\.\.+", ".", text)
    return text.strip()


def _trim_to_limit(text: str) -> str:
    if len(text) <= DESCRIPTION_MAX_LEN:
        return text
    trimmed = text[: DESCRIPTION_MAX_LEN - 1].rsplit(" ", 1)[0]
    if not trimmed.endswith("."):
        trimmed = trimmed.rstrip(".,;:") + "."
    return trimmed


def draft_description(row: SourceRow, tier: TextQualityTier) -> str:
    if tier == "original":
        return row.description

    normalized = normalize_name(row.name)
    piece = infer_piece_type(normalized)
    material = infer_material(row.name, row.description)
    motif = _motif(row.name, piece)
    scale = infer_scale(normalized)
    band = price_band(row.price)
    style = _style_index(row.sku)
    original = row.description.strip()

    lead = _tidy(_lead(row, piece, material, scale, motif, style))
    wear = _wear_sentence(piece, style)
    material_s = _material_sentence(material, style)
    motif_s = _motif_sentence(motif, piece, style)
    presence = _presence_sentence(band, piece, style)
    collection_s = _collection_sentence(row.collection_name, style)

    if tier == "sparse":
        sentences = [lead]
        material_already = bool(material and normalize_name(material) in normalize_name(lead))
        second = wear if material_already else (material_s or wear or motif_s)
        if not second or second in lead:
            second = motif_s or wear
        if second and second not in lead:
            sentences.append(second)
        text = _tidy(" ".join(sentences))
        leftover = _original_missing_from_text(original, material, text)
        if leftover:
            text = _tidy(f"{text} {leftover}.".replace("..", "."))
        text = _trim_to_limit(text)
        assert_no_meta_copy(text, row.sku)
        assert_no_unevidenced_claims(text, row)
        return text

    sentences = [lead]
    for candidate in (motif_s, material_s, wear, presence, collection_s):
        if candidate and candidate not in sentences and candidate.rstrip(".") not in lead:
            sentences.append(candidate)
        if len(sentences) >= 5:
            break
    while len(sentences) < 3:
        filler = wear or presence or collection_s
        if filler and filler not in sentences:
            sentences.append(filler)
        else:
            break
    text = _tidy(" ".join(sentences[:5]))
    leftover = _original_missing_from_text(original, material, text)
    if leftover:
        text = _tidy(f"{text} {leftover}.".replace("..", "."))
    text = _trim_to_limit(text)
    assert_no_meta_copy(text, row.sku)
    assert_no_unevidenced_claims(text, row)
    return text


def assert_no_unevidenced_claims(text: str, row: SourceRow) -> None:
    blob = normalize_name(f"{row.name} {row.description}")
    drafted = normalize_name(text)
    for token in _FORBIDDEN_UNEVIDENCED:
        needle = strip_accents(token)
        if _contains(drafted, needle) and not _contains(blob, needle):
            raise ValueError(f"Assisted text invented {token!r} for {row.sku}")
    for token in _CONDITIONAL_ACCESSORIES:
        needle = strip_accents(token)
        if _contains(drafted, needle) and not _contains(blob, needle):
            raise ValueError(f"Assisted text invented accessory {token!r} for {row.sku}")


def assert_no_meta_copy(text: str, sku: str) -> None:
    drafted = normalize_name(text)
    for phrase in _META_PHRASES:
        if phrase in drafted:
            raise ValueError(f"{sku}: assisted text mentions {phrase!r}")
