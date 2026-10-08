"""ITR reference resolution, identity matching and orientation determination.

This module exists because the two AAV2 ITR records in the part registry are
not reverse complements of each other, and a naive implementation of section
6.4 checks 2 and 3 therefore rejects every correct design.

The measured facts, from data/parts and reproduced by tests/aav:

* itr.aav2_itr_left and itr.aav2_itr_right are both 145 bp plus strand slices
  of NC_001401.2, at 1..145 and 4535..4679.
* The two records decompose exactly. Writing `core` for the 125 bp A, B, B',
  C, C', A' hairpin region and `D` for the 20 bp D sequence:
  `left = core + D` and `right = reverse complement of D + core`, with the
  identical 125 bases of `core` in both. The relation `right == rc(D) + core`
  holds character for character.
* The hairpin core is very nearly its own reverse complement, which is what
  lets it fold into the T shaped hairpin, but not exactly: `rc(core)` matches
  `core` at 85.9 percent. The two arrangements of the B and C arms are the
  flip and the flop configurations, and the reference annotates a flip
  oriented feature inside the left ITR and a flop oriented one at the
  corresponding position of the right ITR.
* Consequence. The naive comparison, left ITR against the reverse complement
  of the right ITR, is `(core + D)` against `(rc(core) + D)`. It differs at
  exactly the 17 positions where `core` and `rc(core)` differ, so it scores
  128 of 145, 88.3 percent, on a perfectly correct cassette. A check that
  demands 95 percent identity from that comparison rejects every valid design.
* Second consequence, for check 9: because `core` is shared verbatim, the two
  ITRs of any correct cassette are an exact 125 bp direct repeat of each other
  on the plus strand. See `check_internal_repeats` for how that is handled.

The two consequences, implemented below:

1. `aav.itr_present_both` compares **each ITR against the serotype reference
   set**, in both orientations, and takes the best match. Which reference record
   a copy derives from, and which arm arrangement it carries, is not a design
   error.
2. `aav.itr_orientation` decides inverted versus tandem from the **D element**,
   which is byte identical between the two records and unaffected by the arm
   arrangement. The D sequence sits at only one end of each ITR, the end facing
   the transgene, so its position decides the arrangement exactly, with no
   identity threshold doing real work. Only when the D element cannot be
   located does the code fall back to an identity margin comparison, and if
   that is also inconclusive the check returns UNKNOWN with a reason rather
   than guessing (section 3.3 constraint 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from packages.core.part_registry import PartCategory, PartRecord, list_parts
from packages.core.sequence import global_identity, reverse_complement

from .constants import AAVThresholds, DEFAULT_THRESHOLDS


class UnknownSerotype(LookupError):
    """No ITR reference pair is registered for the requested serotype.

    Raised rather than guessed at. The caller turns this into an UNKNOWN check
    result with this message as the reason, never into a pass.
    """

    def __init__(self, serotype: str, available: list[str]) -> None:
        self.serotype = serotype
        self.available = available
        listed = ", ".join(available) if available else "none"
        super().__init__(
            f"no ITR reference pair is registered for serotype {serotype!r}; "
            f"the part registry carries ITR references for: {listed}. "
            "Add the serotype's ITR records to data/parts/itr/ or request a registered serotype."
        )


def _serotype_key(serotype: str) -> str:
    """Normalise a serotype label to the registry naming, for example AAV2 to aav2."""
    return "".join(character for character in serotype.lower() if character.isalnum())


def registered_serotypes(parts: list[PartRecord] | None = None) -> list[str]:
    """Serotype keys that have both a left and a right ITR record in the registry."""
    records = parts if parts is not None else list_parts(PartCategory.ITR)
    left = {record.id.split(".", 1)[1].removesuffix("_itr_left") for record in records if record.id.endswith("_itr_left")}
    right = {record.id.split(".", 1)[1].removesuffix("_itr_right") for record in records if record.id.endswith("_itr_right")}
    return sorted(left & right)


@dataclass(frozen=True)
class ItrReference:
    """The ITR reference pair for one serotype, plus the derived D element anchor."""

    serotype: str
    left: PartRecord
    right: PartRecord
    d_element: str | None
    """The D sequence as it reads at the 3' end of the left reference ITR.

    None when the anchor could not be verified for this serotype, in which case
    `orientation_of_pair` falls back to the identity margin method. The anchor
    is accepted only if the reverse complement of the left reference's last
    `itr_d_element_bp` bases equals the right reference's first
    `itr_d_element_bp` bases exactly, which is a self check: it confirms the two
    records really are the two ends of one inverted terminal repeat pair before
    anything is inferred from them.
    """

    @property
    def references(self) -> tuple[tuple[str, str], ...]:
        """(part id, sequence) for every reference ITR of this serotype."""
        return ((self.left.id, self.left.sequence), (self.right.id, self.right.sequence))

    @property
    def citation(self) -> str:
        return f"{self.left.provenance.accession} {self.left.citation}"


def serotype_itr_references(
    serotype: str,
    thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
    parts: list[PartRecord] | None = None,
) -> ItrReference:
    """Load the ITR reference pair for `serotype`, or raise `UnknownSerotype`."""
    records = parts if parts is not None else list_parts(PartCategory.ITR)
    by_id = {record.id: record for record in records}
    key = _serotype_key(serotype)
    left = by_id.get(f"itr.{key}_itr_left")
    right = by_id.get(f"itr.{key}_itr_right")
    if left is None or right is None:
        raise UnknownSerotype(serotype, registered_serotypes(records))
    width = thresholds.itr_d_element_bp
    d_element: str | None = None
    if width > 0 and len(left.sequence) >= width and len(right.sequence) >= width:
        candidate = left.sequence[-width:]
        if reverse_complement(candidate) == right.sequence[:width]:
            d_element = candidate
    return ItrReference(serotype=serotype, left=left, right=right, d_element=d_element)


@dataclass(frozen=True)
class ItrMatch:
    """The best match of one ITR in a design against the serotype reference set."""

    reference_id: str
    orientation: int  # 1 if the design element reads like the reference, -1 if reverse complemented
    identity: float

    @property
    def orientation_label(self) -> str:
        return "as written" if self.orientation == 1 else "reverse complemented"

    def describe(self) -> str:
        return f"{self.identity:.1%} identity to {self.reference_id} ({self.orientation_label})"


def best_itr_match(sequence: str, reference: ItrReference) -> ItrMatch:
    """Best identity of `sequence` against every reference ITR, both orientations.

    Deterministic: ties break on the reference id then on forward orientation
    before reverse, so the same input always yields the same match.
    """
    candidates: list[ItrMatch] = []
    for reference_id, reference_sequence in reference.references:
        candidates.append(ItrMatch(reference_id, 1, global_identity(sequence, reference_sequence)))
        candidates.append(
            ItrMatch(reference_id, -1, global_identity(sequence, reverse_complement(reference_sequence)))
        )
    return min(candidates, key=lambda match: (-match.identity, match.reference_id, -match.orientation))


DEnd = Literal["3_prime", "5_prime"]


def locate_d_element(
    sequence: str,
    reference: ItrReference,
    thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
) -> tuple[DEnd | None, float]:
    """Which end of `sequence` carries the D element, and at what identity.

    Returns ("3_prime", identity) when the D sequence reads at the 3' end of
    the element (the canonical arrangement for a 5' ITR, whose D faces the
    transgene downstream of it), ("5_prime", identity) when the reverse
    complement of the D sequence reads at the 5' end (the canonical
    arrangement for a 3' ITR), and (None, best identity seen) when neither
    reaches `itr_identity_threshold`.
    """
    if reference.d_element is None:
        return None, 0.0
    width = len(reference.d_element)
    if len(sequence) < width:
        return None, 0.0
    threshold = thresholds.itr_identity_threshold
    at_three = global_identity(sequence[-width:], reference.d_element)
    at_five = global_identity(sequence[:width], reverse_complement(reference.d_element))
    if at_three >= threshold and at_three >= at_five:
        return "3_prime", at_three
    if at_five >= threshold:
        return "5_prime", at_five
    return None, max(at_three, at_five)


Arrangement = Literal["inverted", "tandem", "undetermined"]


@dataclass(frozen=True)
class OrientationVerdict:
    """The result of deciding whether two ITRs are inverted or tandem."""

    arrangement: Arrangement
    method: Literal["d_element", "identity_margin"]
    detail: str
    inverted_identity: float | None = None
    tandem_identity: float | None = None
    canonical: bool = True
    """False when the pair is inverted but both ITRs are flipped relative to the
    reference, which happens when the whole cassette is written on the other
    strand. Still a valid inverted arrangement, so not a failure, but worth
    saying out loud."""


def orientation_of_pair(
    itr_5: str,
    itr_3: str,
    reference: ItrReference,
    thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
) -> OrientationVerdict:
    """Decide whether the two ITRs of a cassette are inverted or in tandem.

    Primary method, the D element anchor, which is exact and immune to the
    flip and flop difference: the D sequence occurs at one end of each ITR
    only, and in an inverted pair both D sequences face inward, toward the
    transgene. So the 5' ITR carries D at its 3' end and the 3' ITR carries the
    reverse complement of D at its 5' end. A tandem pair has both D sequences
    at the same end.

    Fallback, the identity margin method, used only when the D element cannot
    be located in both ITRs: the inverted arrangement is called when the 5' ITR
    is more similar to the reverse complement of the 3' ITR than to the 3' ITR
    as written, by at least `itr_orientation_margin`. If neither comparison
    wins by the margin, the arrangement is `undetermined` and the caller
    reports UNKNOWN with this detail as the reason.
    """
    d_5, identity_5 = locate_d_element(itr_5, reference, thresholds)
    d_3, identity_3 = locate_d_element(itr_3, reference, thresholds)
    if d_5 is not None and d_3 is not None:
        if d_5 == "3_prime" and d_3 == "5_prime":
            return OrientationVerdict(
                arrangement="inverted",
                method="d_element",
                detail=(
                    f"the {len(reference.d_element or '')} bp D element faces inward in both ITRs: it reads at the "
                    f"3' end of the 5' ITR ({identity_5:.1%} identity) and its reverse complement reads at the "
                    f"5' end of the 3' ITR ({identity_3:.1%} identity)"
                ),
            )
        if d_5 == "5_prime" and d_3 == "3_prime":
            return OrientationVerdict(
                arrangement="inverted",
                method="d_element",
                detail=(
                    "the two ITRs are inverted relative to each other, but both are reverse complemented "
                    f"relative to the {reference.serotype} reference records, so the D element faces the "
                    "cassette ends rather than the transgene. The arrangement is inverted rather than "
                    "tandem, which is what this check tests, but the outward facing D sequence is unusual "
                    "and worth confirming"
                ),
                canonical=False,
            )
        where = "3' end" if d_5 == "3_prime" else "5' end"
        return OrientationVerdict(
            arrangement="tandem",
            method="d_element",
            detail=(
                f"the D element reads at the {where} of both ITRs, so the 3' ITR is a direct copy of the 5' ITR "
                "rather than its inverse. A tandem pair cannot be resolved and will not package"
            ),
        )

    inverted_identity = global_identity(itr_5, reverse_complement(itr_3))
    tandem_identity = global_identity(itr_5, itr_3)
    margin = thresholds.itr_orientation_margin
    if reference.d_element is None:
        preamble = (
            f"the D element anchor is not available for serotype {reference.serotype} (the reference pair in the "
            "part registry does not meet the exact reverse complement self check), so the identity margin "
            "method was used"
        )
    else:
        if d_5 is None and d_3 is None:
            missing, best = "both ITRs", min(identity_5, identity_3)
        elif d_5 is None:
            missing, best = "the 5' ITR", identity_5
        else:
            missing, best = "the 3' ITR", identity_3
        preamble = (
            f"the D element could not be located in {missing} (best window identity {best:.1%}, threshold "
            f"{thresholds.itr_identity_threshold:.0%}), so the identity margin method was used"
        )
    if inverted_identity - tandem_identity >= margin:
        arrangement: Arrangement = "inverted"
        detail = (
            f"{preamble}: the 5' ITR matches the reverse complement of the 3' ITR at {inverted_identity:.1%} "
            f"against {tandem_identity:.1%} for the tandem arrangement, a separation of "
            f"{inverted_identity - tandem_identity:.1%} above the {margin:.0%} margin"
        )
    elif tandem_identity - inverted_identity >= margin:
        arrangement = "tandem"
        detail = (
            f"{preamble}: the 5' ITR matches the 3' ITR as written at {tandem_identity:.1%} against "
            f"{inverted_identity:.1%} for the inverted arrangement, so the two ITRs are a direct repeat"
        )
    else:
        arrangement = "undetermined"
        detail = (
            f"{preamble}: inverted scores {inverted_identity:.1%} and tandem scores {tandem_identity:.1%}, "
            f"a separation of {abs(inverted_identity - tandem_identity):.1%} which is below the "
            f"{margin:.0%} margin, so the arrangement cannot be called"
        )
    return OrientationVerdict(
        arrangement=arrangement,
        method="identity_margin",
        detail=detail,
        inverted_identity=inverted_identity,
        tandem_identity=tandem_identity,
    )


def itr_motifs(reference: ItrReference, width: int) -> list[str]:
    """Every distinct `width` bp window of the serotype reference ITRs, sorted.

    The motif set for `aav.itr_internal_sites`. Derived from the registry
    records, so no ITR sequence is written into the validator.
    """
    if width <= 0:
        raise ValueError("width must be positive")
    motifs: set[str] = set()
    for _, sequence in reference.references:
        for start in range(len(sequence) - width + 1):
            motifs.add(sequence[start : start + width])
    return sorted(motifs)


def internal_itr_motif_hits(interior: str, reference: ItrReference, width: int) -> list[tuple[str, int, int]]:
    """ITR motifs that also occur in `interior`, on either strand.

    Returns (motif, offset in interior, strand) triples, sorted by offset then
    motif, so the output is deterministic. Implemented as a set intersection
    over windows rather than a search per motif, which keeps it linear in the
    length of the interior.
    """
    if width <= 0 or len(interior) < width:
        return []
    windows: dict[str, int] = {}
    for start in range(len(interior) - width + 1):
        windows.setdefault(interior[start : start + width], start)
    hits: list[tuple[str, int, int]] = []
    for motif in itr_motifs(reference, width):
        if motif in windows:
            hits.append((motif, windows[motif], 1))
            continue
        complementary = reverse_complement(motif)
        if complementary in windows:
            hits.append((motif, windows[complementary], -1))
    return sorted(hits, key=lambda hit: (hit[1], hit[0]))
