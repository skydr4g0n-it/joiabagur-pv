"""Candidate grouping, material fusion and guards. Delivered by C18a.

Deterministic and offline. Given catalogue rows it produces family proposals and
the groups a guard refused, and it never decides membership from an absolute
similarity: the embedding veto lives in `veto` and runs on what this module
forms.

Order of operations, and why each step is where it is:

1. **Exclude** products that already belong to a family, so repeating the run
   converges instead of re-proposing what was just approved.
2. **Gate** on piece type. A null piece type groups with nobody: the null is a
   value of the gate, not a wildcard.
3. **Group** by normalised root (`naming.parse_name`).
4. **Fuse** groups whose roots differ by exactly one material token. Material is
   never stripped from the root — doing so collapses `Anillo plata S/M/L/XL`
   onto the bare piece type.
5. **Guard** against degenerate roots, reporting the rejection rather than
   dropping it: three of the six it catches on the real catalogue turn out not
   to be jewellery at all (`Encargos`, `Arreglos`, `Presión`).
6. **Label** each member with what actually distinguishes it, and order members
   by the canonical size rank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from jbg_ai.families.naming import ParsedName, parse_name
from jbg_ai.families.vocabulary import FamilyVocabulary

__all__ = [
    "CandidateProduct",
    "ExcludedProduct",
    "FamilyProposal",
    "GroupingOutcome",
    "ProposedMember",
    "RejectedGroup",
    "MIN_ROOT_TOKENS",
    "build_candidate_groups",
]

#: A root shorter than this is refused: it no longer names a piece.
MIN_ROOT_TOKENS = 2


@dataclass(frozen=True)
class CandidateProduct:
    """One catalogue row as the grouper needs it.

    No vector: grouping is pure text, and the veto that does use the vectors compares
    them inside PostgreSQL rather than in Python, so carrying 1536 floats per product
    through this layer would buy nothing.
    """

    product_id: UUID
    sku: str
    name: str
    piece_type: str | None
    family_id: UUID | None = None


@dataclass(frozen=True)
class ProposedMember:
    """A product inside a proposal, with the label that tells it from its siblings."""

    product_id: UUID
    sku: str
    name: str
    variant_label: str | None
    position: int
    flagged_for_review: bool = False
    review_reason: str | None = None
    distance: float | None = None


@dataclass(frozen=True)
class FamilyProposal:
    """A candidate family: one piece type, one root, two or more members."""

    root: str
    piece_type: str
    members: tuple[ProposedMember, ...]

    @property
    def suggested_name(self) -> str:
        """Human-facing name for the family, derived from the root."""
        return self.root[:1].upper() + self.root[1:] if self.root else self.root


@dataclass(frozen=True)
class RejectedGroup:
    """A group a guard refused, reported so a person can look at it."""

    root: str
    piece_type: str | None
    reason: str
    product_names: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExcludedProduct:
    """A product the gate removed before grouping, named so the gate is not silent."""

    product_id: UUID
    sku: str
    name: str
    reason: str


@dataclass(frozen=True)
class GroupingOutcome:
    """Everything one grouping run produced, including what it left out.

    `excluded` names products the piece-type gate removed one by one, because
    that exclusion is the surprising one: a product without a piece type also
    disappears from the review queue, not only from families, and nothing else
    would ever mention it. Products skipped for already belonging to a family
    are counted rather than listed — after the first batch they are hundreds,
    and their exclusion is the convergence rule working, not a finding.
    """

    proposals: tuple[FamilyProposal, ...]
    rejected: tuple[RejectedGroup, ...]
    excluded: tuple[ExcludedProduct, ...]
    already_in_family_count: int


@dataclass(frozen=True)
class _Parsed:
    product: CandidateProduct
    parsed: ParsedName


def build_candidate_groups(
    products: list[CandidateProduct],
    vocabulary: FamilyVocabulary,
) -> GroupingOutcome:
    """Form family proposals, and report what the guards and the gate left out."""
    eligible: list[_Parsed] = []
    excluded: list[ExcludedProduct] = []
    already_in_family = 0

    for product in products:
        if product.family_id is not None:
            already_in_family += 1
            continue
        if product.piece_type is None:
            excluded.append(
                ExcludedProduct(
                    product_id=product.product_id,
                    sku=product.sku,
                    name=product.name,
                    reason="no_piece_type",
                )
            )
            continue
        eligible.append(_Parsed(product, parse_name(product.name, vocabulary)))

    by_key: dict[tuple[str, str], list[_Parsed]] = {}
    for entry in eligible:
        assert entry.product.piece_type is not None  # filtered above
        by_key.setdefault((entry.product.piece_type, entry.parsed.root), []).append(entry)

    fused, refused_fusions = _fuse_on_material(by_key, vocabulary)

    proposals: list[FamilyProposal] = []
    rejected: list[RejectedGroup] = list(refused_fusions)
    for (piece_type, root), entries in sorted(fused.items()):
        if len(entries) < 2:
            continue
        reason = _guard_reason(root, vocabulary)
        if reason is not None:
            rejected.append(
                RejectedGroup(
                    root=root,
                    piece_type=piece_type,
                    reason=reason,
                    product_names=tuple(sorted(e.product.name for e in entries)),
                )
            )
            continue
        proposal = _build_proposal(root, piece_type, entries, vocabulary)
        labels = [member.variant_label for member in proposal.members]
        if len(set(labels)) != len(labels):
            # Two members the algorithm cannot tell apart on any axis it knows.
            # Emitting this would produce a proposal the family service refuses on
            # its uniqueness index — a constraint error instead of something a
            # person can act on. Two indistinguishable products are a catalogue
            # question ("are these really two products?"), so they go to review.
            rejected.append(
                RejectedGroup(
                    root=root,
                    piece_type=piece_type,
                    reason="duplicate_variant_labels",
                    product_names=tuple(sorted(e.product.name for e in entries)),
                )
            )
            continue
        proposals.append(proposal)

    return GroupingOutcome(
        proposals=tuple(proposals),
        rejected=tuple(sorted(rejected, key=lambda group: (group.piece_type or "", group.root))),
        excluded=tuple(sorted(excluded, key=lambda product: product.sku)),
        already_in_family_count=already_in_family,
    )


def _fuse_on_material(
    by_key: dict[tuple[str, str], list[_Parsed]],
    vocabulary: FamilyVocabulary,
) -> tuple[dict[tuple[str, str], list[_Parsed]], list[RejectedGroup]]:
    """Merge groups of one piece type whose roots differ by exactly one material.

    The surviving key is the **shorter** root, so `anillo lapislazuli oro` folds
    into `anillo lapislazuli` and not the other way round.

    A fusion whose survivor would be degenerate is **refused and reported**, never
    dropped in silence. That path is the one that finds `Encargos plata` /
    `Encargos Oro` and `Arreglos plata` / `Arreglos oro`: without it their two
    singleton groups simply fall below the minimum size and nobody ever learns the
    catalogue is carrying workshop services among the jewellery.
    """
    buckets: dict[tuple[str, str], list[tuple[str, list[_Parsed]]]] = {}
    for (piece_type, root), entries in by_key.items():
        reduced = _without_materials(root, vocabulary)
        buckets.setdefault((piece_type, reduced), []).append((root, entries))

    merged: dict[tuple[str, str], list[_Parsed]] = {}
    refused: list[RejectedGroup] = []

    for (piece_type, reduced), members in sorted(buckets.items()):
        if len(members) == 1:
            # Nothing to fuse. The group keeps its own root, and the reduced form
            # is NOT judged: `Anillo plata S/M/L/XL` reduces to the bare piece type
            # yet is a perfectly good family under its own root `anillo plata`.
            root, entries = members[0]
            merged.setdefault((piece_type, root), []).extend(entries)
            continue

        reason = _guard_reason(reduced, vocabulary)
        if reason is not None:
            refused.append(
                RejectedGroup(
                    root=reduced,
                    piece_type=piece_type,
                    reason=reason,
                    product_names=tuple(
                        sorted(e.product.name for _, entries in members for e in entries)
                    ),
                )
            )
            continue

        survivor = min(root for root, _ in members)
        for _, entries in members:
            merged.setdefault((piece_type, survivor), []).extend(entries)

    return merged, refused


def _without_materials(root: str, vocabulary: FamilyVocabulary) -> str:
    """The root with every material removed. Used only as a fusion key.

    Materials are matched as phrases for the same reason `naming.parse_name` does it:
    a token-at-a-time scan turns `baño de oro` into the residue `bano de`, which is a
    different fusion key from the `oro` variant's and would keep two groups that
    differ by exactly one material from ever meeting.
    """
    tokens = root.split()
    kept: list[str] = []
    index = 0
    while index < len(tokens):
        found = vocabulary.material_at(tokens, index)
        if found is None:
            kept.append(tokens[index])
            index += 1
        else:
            index += found[0]
    return " ".join(kept)


def _guard_reason(root: str, vocabulary: FamilyVocabulary) -> str | None:
    """Why this root cannot name a family, or None when it can."""
    if not root:
        return "empty_root"
    if vocabulary.is_piece_type(root):
        return "root_is_bare_piece_type"
    if len(root.split()) < MIN_ROOT_TOKENS:
        return "root_too_short"
    return None


def _build_proposal(
    root: str,
    piece_type: str,
    entries: list[_Parsed],
    vocabulary: FamilyVocabulary,
) -> FamilyProposal:
    """Order members by canonical size and label them by what distinguishes them."""
    ordered = sorted(
        entries,
        key=lambda e: (
            vocabulary.size_rank(e.parsed.canonical_size),
            e.product.name.casefold(),
        ),
    )
    labels = _distinguishing_labels(ordered)
    members = tuple(
        ProposedMember(
            product_id=entry.product.product_id,
            sku=entry.product.sku,
            name=entry.product.name,
            variant_label=label,
            position=position,
        )
        for position, (entry, label) in enumerate(zip(ordered, labels, strict=True))
    )
    return FamilyProposal(root=root, piece_type=piece_type, members=members)


def _distinguishing_labels(ordered: list[_Parsed]) -> list[str | None]:
    """Label each member with only what tells it from its siblings.

    A size that every member shares is not a variant, and neither is a material
    every member carries: including them would produce labels that repeat, which
    the family's uniqueness index rejects. What survives is the composite the
    two-axis families need — `mini oro` — and nothing more.

    The two halves are not treated alike, and the asymmetry is deliberate. The size
    is the fragment the catalogue wrote, kept verbatim down to its accent, because
    `mini` and `XS` are different sizes and translating one into the other would
    record something the shop never said. The material is its **canonical** term,
    because `Oro` and `18k` are one material spelled twice: keeping both verbatim
    would make one product look like two variants and would walk past the duplicate
    label guard, which compares labels and not meanings.
    """
    sizes = {entry.parsed.size_label for entry in ordered}
    size_distinguishes = len(sizes) > 1

    material_sets = [set(entry.parsed.canonical_materials) for entry in ordered]
    shared_materials = set.intersection(*material_sets) if material_sets else set()

    labels: list[str | None] = []
    for entry, materials in zip(ordered, material_sets, strict=True):
        parts: list[str] = []
        if size_distinguishes and entry.parsed.size_label is not None:
            parts.append(entry.parsed.size_label)
        parts.extend(
            token
            for token in entry.parsed.canonical_materials
            if token in materials - shared_materials
        )
        labels.append(" ".join(parts) if parts else None)
    return labels
