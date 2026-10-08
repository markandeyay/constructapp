"""Nuclease geometry: PAM motif, PAM side, spacer length, cut offsets.

Source: Appendix C of the engine capability system design, reproduced below
without alteration:

    | Nuclease | PAM motif | PAM position   | Spacer length |
    | SpCas9   | NGG       | 3' of spacer   | 20 nt |
    | SaCas9   | NNGRRT    | 3' of spacer   | 21 nt |
    | LbCas12a | TTTV      | 5' of spacer   | 23 nt |
    | AsCas12a | TTTV      | 5' of spacer   | 23 nt |

Appendix C also states, and this module exists to make it structurally
impossible to get wrong:

    The Cas12a 5' PAM position is the single most likely integration bug in
    Capability C.

Nothing in this package computes a PAM offset by hand. Every placement goes
through `spacer_interval` and `pam_interval`, which branch on
`NucleaseSpec.pam_side` and on nothing else. A nuclease whose `pam_side` is
`five_prime` therefore cannot be given a 3' offset without editing this one
function, and the tests in `tests/grna/test_nuclease_geometry.py` assert the
Cas12a geometry against an independently written expectation.

Appendix C on the SpCas9 alternative PAM:

    NAG is tolerated at substantially reduced efficiency; treat as a WARN-level
    alternative PAM, not a primary one.

Every number in this module is either an Appendix C value or a documented,
configurable parameter whose source is named in the field docstring. A caller
that wants different geometry builds a different `NucleaseSpec`; nothing here
is read from a global.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

from packages.core.sequence import clean_sequence, matches_iupac, reverse_complement

PamSide = Literal["three_prime", "five_prime"]

#: Appendix C of the engine capability system design, section 8.6 and section 13.4
#: reference the CRISPOR guide selection tool for the cleavage geometry below.
CRISPOR_CITATION = (
    "CRISPOR guide RNA selection tool, Genome Biol 2016;17(1):148, "
    "doi:10.1186/s13059-016-1012-2, PMID 27380939; geometry read from the tool's "
    "source file crispor.py, retrieved 2026-10-07 from "
    "https://raw.githubusercontent.com/maximilianh/crisporWebsite/master/crispor.py"
)

#: Cell 2015;163(3):759-771, doi:10.1016/j.cell.2015.09.038, PMID 26422227.
#: The Cas12a (Cpf1) staggered cut, as summarised in the CRISPOR source: cleavage
#: occurs usually after the 18th base on the strand carrying the TTTV PAM and
#: after the 23rd base on the targeted strand, leaving a 5 nt 5' overhang.
CAS12A_CUT_CITATION = (
    "Cell 2015;163(3):759-771, doi:10.1016/j.cell.2015.09.038, PMID 26422227, "
    f"as summarised in {CRISPOR_CITATION}"
)

#: Nature 2015;520(7546):186-191, doi:10.1038/nature14299, PMID 25830891.
#: SaCas9 cleaves with the same pattern as SpCas9, so the blunt cut 3 nt 5' of
#: the PAM applies to both.
SACAS9_CUT_CITATION = (
    "Nature 2015;520(7546):186-191, doi:10.1038/nature14299, PMID 25830891 "
    f"(SaCas9 cleavage pattern reported as identical to SpCas9), with the offset read from {CRISPOR_CITATION}"
)

APPENDIX_C = "Appendix C of the engine capability system design (nuclease and PAM reference)"


@dataclass(frozen=True)
class AlternativePam:
    """A PAM that works at reduced efficiency, surfaced as WARN rather than PASS.

    Source: Appendix C. For SpCas9 the only entry is `NAG`, described there as
    tolerated at substantially reduced efficiency. Treating it as a primary PAM
    would overstate the design space, and discarding it would hide real guides,
    so it is enumerated and flagged.
    """

    motif: str
    note: str
    citation: str = APPENDIX_C


@dataclass(frozen=True)
class NucleaseSpec:
    """Everything the enumerator and the validator need about one nuclease.

    Fields and their sources:

    * `pam_motif`, `pam_side`, `spacer_length`: Appendix C, verbatim.
    * `alternative_pams`: Appendix C.
    * `blunt_cut_offset_from_pam`: for a 3' PAM nuclease, how many nucleotides
      5' of the PAM the blunt double-strand break falls. Default 3, from the
      CRISPOR tool, which states the expected cleavage position is 3 bp 5' of
      the PAM site. Configurable, because it is a measured property of the
      protein and not a universal constant.
    * `staggered_cut_offsets`: for a 5' PAM nuclease, the two cut positions
      counted in nucleotides along the spacer from its 5' end, the first on the
      PAM-carrying strand and the second on the targeted strand. Default
      (18, 23) from the Cas12a citation above. `None` for blunt cutters.
    * `supports_published_on_target_model`: whether the Rule Set 1 on-target
      model in `ontarget.py` is inside its validity domain for this nuclease.
      Only SpCas9 is, because that model was trained on SpCas9 data.
    * `supports_published_off_target_model`: whether the MIT specificity score
      in `offtarget.py` is inside its validity domain. Only SpCas9 is. The
      CRISPOR tool states plainly that the MIT specificity score and the related
      CFD model were developed
      for SpCas9 and that there is not enough data to support their usefulness
      for Cas12a, and it uses a separate SaCas9 model, so applying the MIT
      score to SaCas9 or Cas12a here would be a silent extrapolation of the
      kind section 8.4 forbids.
    """

    name: str
    pam_motif: str
    pam_side: PamSide
    spacer_length: int
    alternative_pams: tuple[AlternativePam, ...] = ()
    blunt_cut_offset_from_pam: int | None = 3
    staggered_cut_offsets: tuple[int, int] | None = None
    supports_published_on_target_model: bool = False
    supports_published_off_target_model: bool = False
    notes: str = ""
    citation: str = APPENDIX_C
    cut_citation: str = CRISPOR_CITATION

    @property
    def pam_length(self) -> int:
        return len(self.pam_motif)

    def pam_motifs(self) -> tuple[tuple[str, bool], ...]:
        """Every PAM motif to enumerate, each flagged as alternative or not.

        The primary motif comes first so enumeration order is deterministic.
        """
        motifs: list[tuple[str, bool]] = [(self.pam_motif, False)]
        motifs.extend((alternative.motif, True) for alternative in self.alternative_pams)
        return tuple(motifs)

    def alternative_note(self, motif: str) -> str | None:
        for alternative in self.alternative_pams:
            if alternative.motif == motif:
                return alternative.note
        return None


SPCAS9 = NucleaseSpec(
    name="SpCas9",
    pam_motif="NGG",
    pam_side="three_prime",
    spacer_length=20,
    alternative_pams=(
        AlternativePam(
            motif="NAG",
            note=(
                "NAG is tolerated at substantially reduced efficiency (Appendix C). "
                "Prefer an NGG guide when one is available."
            ),
        ),
    ),
    blunt_cut_offset_from_pam=3,
    supports_published_on_target_model=True,
    supports_published_off_target_model=True,
    notes="The standard. Blunt cut 3 nt 5' of the PAM.",
    cut_citation=CRISPOR_CITATION,
)

SACAS9 = NucleaseSpec(
    name="SaCas9",
    pam_motif="NNGRRT",
    pam_side="three_prime",
    spacer_length=21,
    blunt_cut_offset_from_pam=3,
    supports_published_on_target_model=False,
    supports_published_off_target_model=False,
    notes="Smaller protein, fits AAV more comfortably. R is A or G (Appendix C).",
    cut_citation=SACAS9_CUT_CITATION,
)

LBCAS12A = NucleaseSpec(
    name="LbCas12a",
    pam_motif="TTTV",
    pam_side="five_prime",
    spacer_length=23,
    blunt_cut_offset_from_pam=None,
    staggered_cut_offsets=(18, 23),
    supports_published_on_target_model=False,
    supports_published_off_target_model=False,
    notes="PAM is 5' of the spacer. V is A, C or G. Staggered cut, not blunt (Appendix C).",
    cut_citation=CAS12A_CUT_CITATION,
)

ASCAS12A = NucleaseSpec(
    name="AsCas12a",
    pam_motif="TTTV",
    pam_side="five_prime",
    spacer_length=23,
    blunt_cut_offset_from_pam=None,
    staggered_cut_offsets=(18, 23),
    supports_published_on_target_model=False,
    supports_published_off_target_model=False,
    notes="PAM is 5' of the spacer. V is A, C or G. Staggered cut, not blunt (Appendix C).",
    cut_citation=CAS12A_CUT_CITATION,
)

NUCLEASES: Mapping[str, NucleaseSpec] = {
    spec.name: spec for spec in (SPCAS9, SACAS9, LBCAS12A, ASCAS12A)
}


def get_nuclease(name: str) -> NucleaseSpec:
    """Look up a nuclease by its section 8.2 name, failing loudly on an unknown one."""
    try:
        return NUCLEASES[name]
    except KeyError:
        known = ", ".join(sorted(NUCLEASES))
        raise KeyError(f"unsupported nuclease {name!r} (supported: {known})") from None


def spacer_interval(spec: NucleaseSpec, pam_start: int, pam_end: int) -> tuple[int, int]:
    """Where the spacer sits, given where the PAM sits, in guide-strand coordinates.

    This is the single place the 3' versus 5' PAM decision is made. Both
    intervals are zero-based, start inclusive, end exclusive, on the strand the
    guide targets (so a reverse-strand guide is handled by viewing the reverse
    complement of the target, not by a second offset rule).

    * `three_prime` (Cas9): the PAM follows the spacer, so the spacer ends where
      the PAM begins.
    * `five_prime` (Cas12a): the PAM precedes the spacer, so the spacer begins
      where the PAM ends.

    The returned interval may be out of range for the sequence. The caller
    discards such a position: it means the PAM is too close to an end for a
    full spacer to exist.
    """
    if spec.pam_side == "three_prime":
        return pam_start - spec.spacer_length, pam_start
    if spec.pam_side == "five_prime":
        return pam_end, pam_end + spec.spacer_length
    raise ValueError(f"unsupported pam_side {spec.pam_side!r}")


def pam_interval(spec: NucleaseSpec, spacer_start: int, spacer_end: int) -> tuple[int, int]:
    """Where the PAM must sit, given where the spacer sits, in guide-strand coordinates.

    The exact inverse of `spacer_interval`, and the function the PAM validity
    check uses to decide which bases of the target to compare against the PAM
    motif. Deriving both directions from `pam_side` is what makes a wrong
    Cas12a offset a test failure rather than a silently wrong guide.
    """
    if spec.pam_side == "three_prime":
        return spacer_end, spacer_end + spec.pam_length
    if spec.pam_side == "five_prime":
        return spacer_start - spec.pam_length, spacer_start
    raise ValueError(f"unsupported pam_side {spec.pam_side!r}")


def cut_sites(spec: NucleaseSpec, spacer_start: int, spacer_end: int) -> tuple[int, int | None]:
    """Cut position or positions in guide-strand coordinates.

    The returned coordinate is the index of the base immediately 3' of the cut
    on the guide strand, so a cut reported at index `i` lies between `i - 1` and
    `i`.

    * Blunt cutter: `blunt_cut_offset_from_pam` nucleotides 5' of the PAM. For
      SpCas9 with the default offset of 3 that is between spacer positions 17
      and 18 counted from the spacer 5' end.
    * Staggered cutter: the two `staggered_cut_offsets` counted along the spacer
      from its 5' end.
    """
    if spec.pam_side == "three_prime":
        if spec.blunt_cut_offset_from_pam is None:
            raise ValueError(f"{spec.name} has no blunt cut offset configured")
        return spacer_end - spec.blunt_cut_offset_from_pam, None
    if spec.staggered_cut_offsets is None:
        raise ValueError(f"{spec.name} has no staggered cut offsets configured")
    first, second = spec.staggered_cut_offsets
    return spacer_start + first, spacer_start + second


def strand_view(target: str, strand: int) -> str:
    """The target as the guide strand reads it.

    Scanning both strands (section 8.3) is done by scanning this view for
    `strand` +1 and -1, which keeps one offset rule rather than two.
    """
    sequence = clean_sequence(target)
    if strand == 1:
        return sequence
    if strand == -1:
        return reverse_complement(sequence)
    raise ValueError(f"strand must be 1 or -1, not {strand!r}")


def to_forward(length: int, strand: int, start: int, end: int) -> tuple[int, int]:
    """Map a guide-strand interval back to forward target coordinates.

    `length` is the length of the target. For the reverse strand, guide-strand
    position `p` is forward position `length - 1 - p`, so the interval flips.
    """
    if strand == 1:
        return start, end
    if strand == -1:
        return length - end, length - start
    raise ValueError(f"strand must be 1 or -1, not {strand!r}")


def to_forward_position(length: int, strand: int, position: int) -> int:
    """Map a single guide-strand coordinate back to a forward target coordinate.

    A cut reported between guide-strand bases `position - 1` and `position`
    falls, on the forward sequence, between forward bases `length - position - 1`
    and `length - position` when the guide is on the reverse strand.
    """
    if strand == 1:
        return position
    if strand == -1:
        return length - position
    raise ValueError(f"strand must be 1 or -1, not {strand!r}")


def pam_matches(spec: NucleaseSpec, pam: str) -> tuple[bool, bool]:
    """Does `pam` satisfy one of this nuclease's motifs, and is that motif alternative.

    Returns `(matches, is_alternative)`. IUPAC expansion comes from the shared
    `matches_iupac` utility, so `N`, `R` and `V` are handled in one place
    (Appendix C: N any base, R purine, V A or C or G).
    """
    candidate = clean_sequence(pam)
    for motif, is_alternative in spec.pam_motifs():
        if len(candidate) == len(motif) and matches_iupac(candidate, motif):
            return True, is_alternative
    return False, False


@dataclass(frozen=True)
class GeometryFacts:
    """The Appendix C row for one nuclease, for `parameters_used` and the UI."""

    nuclease: str
    pam_motif: str
    pam_position: str
    spacer_length_nt: int
    alternative_pams: tuple[str, ...] = field(default_factory=tuple)
    cut_description: str = ""
    citation: str = APPENDIX_C


def geometry_facts(spec: NucleaseSpec) -> GeometryFacts:
    """Human readable Appendix C row, so a report can show what it measured against."""
    if spec.pam_side == "three_prime":
        position = "3' of spacer"
        cut = (
            f"blunt cut {spec.blunt_cut_offset_from_pam} nt 5' of the PAM "
            f"({spec.cut_citation})"
        )
    else:
        position = "5' of spacer"
        first, second = spec.staggered_cut_offsets or (0, 0)
        cut = (
            f"staggered cut after spacer position {first} on the PAM-carrying strand and "
            f"after spacer position {second} on the targeted strand ({spec.cut_citation})"
        )
    return GeometryFacts(
        nuclease=spec.name,
        pam_motif=spec.pam_motif,
        pam_position=position,
        spacer_length_nt=spec.spacer_length,
        alternative_pams=tuple(alternative.motif for alternative in spec.alternative_pams),
        cut_description=cut,
    )
