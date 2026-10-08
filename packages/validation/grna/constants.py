"""Every configurable threshold the guide RNA capability applies.

Source policy, from section 3.3 constraint 1 and section 0.3: every number in
this file is in exactly one of three classes, and the class is stated next to
the number.

* **Appendix C**: the value is printed in Appendix C of the engine capability
  system design. Those are the spacer GC window, the maximum homopolymer run,
  the U6 terminator motif, and the seed region.
* **Literature**: the value is read from a named publication or from the source
  code of a named, published tool, with the citation and the retrieval date
  recorded here. Nothing in this class was recalled; Appendix E forbids that.
* **Construct convention**: no published value exists for the quantity, so the
  default is a stated engineering choice with its reasoning written out. These
  are flagged `convention` so a reviewer can find all of them in one grep, and
  they are never described in output as published.

Section 3.3 constraint 2 requires every threshold to be configurable. Nothing
here is read from a module global at validation time: `GuideRNAThresholds` is a
frozen dataclass, `DEFAULT_THRESHOLDS` is one instance of it, and a caller that
wants different numbers passes a different instance. The constants below exist
so the defaults have one place with one docstring each.

Section 5.4 rule 4 is enforced by `THRESHOLD_FINGERPRINTS`: a test calls
`assert_version_matches_thresholds`, so editing any default without bumping
`VALIDATOR_VERSION` fails.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .nuclease import NUCLEASES

VALIDATOR_VERSION = "grna-1.0.0"
"""Bumped whenever any default in this file or any nuclease geometry changes
(section 5.4 rule 4)."""

APPENDIX_C = "Appendix C of the engine capability system design (configurable feature windows)"
APPENDIX_D = "Appendix D of the engine capability system design (Type IIS enzyme reference)"
SECTION_8_5 = "Section 8.5 of the engine capability system design (sequence feature checks)"
SECTION_8_6 = "Section 8.6 of the engine capability system design (off-target search, scoped honestly)"

CRISPOR_CITATION = (
    "CRISPOR guide RNA selection tool, Genome Biol 2016;17(1):148, "
    "doi:10.1186/s13059-016-1012-2, PMID 27380939; value read from the tool's source, "
    "retrieved 2026-10-07 from https://github.com/maximilianh/crisporWebsite"
)

# ---------------------------------------------------------------------------
# Appendix C: sequence feature windows
# ---------------------------------------------------------------------------

SPACER_GC_MIN = 0.40
"""Appendix C: spacer GC fraction window, lower bound. Below it, the spacer
binds weakly and activity falls off."""

SPACER_GC_MAX = 0.70
"""Appendix C: spacer GC fraction window, upper bound. Above it, off-target
tolerance rises and the guide can bind too stably."""

MAX_HOMOPOLYMER_RUN = 4
"""Appendix C: maximum homopolymer run in the spacer. A run longer than this is
flagged (section 8.5 check 5, WARN)."""

U6_TERMINATOR_MOTIF = "TTTT"
"""Appendix C: the U6 terminator motif to reject. Section 8.5 check 4: its
presence prematurely terminates U6 transcription, so it is FAIL when the guide
is U6 driven and WARN otherwise."""

SEED_REGION_NT = 12
"""Appendix C gives the PAM-proximal seed region for off-target weighting as
8 to 12 nt and makes it configurable. The default is the top of that range, 12,
which is also the window the CRISPOR tool reports mismatches in: its
`last12MmCount` counts mismatches at guide positions 9 to 20 of a 20 nt spacer.
Source for the range: Appendix C. Corroboration for choosing 12: the CRISPOR
citation in `CRISPOR_CITATION` above."""

SEED_REGION_NT_MIN = 8
"""Appendix C: the lower end of the permitted seed region range. Values outside
8 to 12 are rejected rather than silently accepted."""

SEED_REGION_NT_MAX = 12
"""Appendix C: the upper end of the permitted seed region range."""

# ---------------------------------------------------------------------------
# Off-target search, section 8.6
# ---------------------------------------------------------------------------

OFF_TARGET_MAX_MISMATCHES = 4
"""Literature: the CRISPOR tool searches its genome index allowing up to 4
mismatches (`maxMMs=4` in its source). Sites with more mismatches than this are
not enumerated, and the report says so rather than implying they were cleared.
Source: the CRISPOR citation in `CRISPOR_CITATION` above."""

OFF_TARGET_FAIL_MAX_MISMATCHES = 2
"""Section 8.6: FAIL on any off-target with very few mismatches concentrated
outside the seed. This is the ceiling on "very few". Construct convention for
the exact integer, because section 8.6 words the rule qualitatively; 2 is
chosen so that a 1 or 2 mismatch site with a perfectly matched seed fails,
which is the case that a bench user would not tolerate."""

OFF_TARGET_FAIL_MAX_SEED_MISMATCHES = 0
"""Section 8.6: "concentrated outside the seed" means the seed itself is
matched. A site whose seed carries any mismatch is not a FAIL under this rule,
because a PAM-proximal mismatch is the disruptive kind. Construct convention
for the integer, with the principle taken from section 8.6 and Appendix C."""

OFF_TARGET_WARN_MAX_MISMATCHES = 4
"""Section 8.6: WARN on moderate hits. Any enumerated site that is not a FAIL
is a moderate hit, so this equals the search depth by default. Construct
convention for the integer."""

OFF_TARGET_MAX_SEARCH_BP = 5_000_000
"""Construct convention: a cap on the total size of the searched space.

The search is a direct two-strand Hamming scan over the supplied sequences,
which is linear in their total length. A space larger than this cap makes the
request UNKNOWN with the reason and the real size, rather than being silently
truncated. Raise it and accept the runtime, or supply a smaller set. Section
3.2 lists genome-wide off-target search as an explicit non-goal, so there is no
index to fall back on."""

# ---------------------------------------------------------------------------
# Scaffold fold and cloning, sections 8.5 and 8.7
# ---------------------------------------------------------------------------

MAX_SELF_COMPLEMENT_STEM_NT = 7
"""Construct convention: the shortest internal self-complementary stem inside
the spacer that is reported by section 8.5 check 6.

No published threshold exists for "self-complementarity that would disrupt the
scaffold fold". Section 7.4 of the same design document blesses a documented
sliding-window complementarity score in place of a full free-energy
minimisation, and that is what `selfcomp.py` implements. The default of 7 bp is
an engineering choice: shorter stems are common by chance in a 20 nt window and
would flag almost every guide, while a stem of 7 bp or more competes
meaningfully with the scaffold fold. Configurable, and labelled a convention in
every message that reports it."""

MIN_HAIRPIN_LOOP_NT = 3
"""Construct convention: the smallest loop a reported hairpin may close.

A nucleic acid hairpin cannot close a loop of fewer than about 3 unpaired
nucleotides for steric reasons, so a shorter apparent loop is a scoring
artefact rather than a structure. Configurable."""

CLONING_ENZYME_SITES: Mapping[str, str] = {
    "BsaI": "GGTCTC",
    "BsmBI": "CGTCTC",
    "BbsI": "GAAGAC",
    "SapI": "GCTCTTC",
    "AarI": "CACCTGC",
}
"""Appendix D: Type IIS recognition sequences, verbatim. Appendix D also
requires both strands to be checked, because these sequences are not
palindromic; `checks.py` uses the shared `find_both_strands` utility for exactly
that reason. BsmBI is also called Esp3I, BbsI is also called BpiI, SapI is also
called LguI (Appendix D)."""

# ---------------------------------------------------------------------------
# Knockout positioning, section 8.5 check 7
# ---------------------------------------------------------------------------

KNOCKOUT_CDS_MAX_FRACTION = 0.60
"""Construct convention: for a knockout, the cut site should fall within the
first 60 percent of the coding sequence.

Section 8.5 check 7 states the rule qualitatively ("an early constitutive
region rather than the final exon") and gives no number. Published guide design
tools disagree on the exact window, some preferring the earliest exons and some
the middle of the transcript, so no single published value is available to
copy. 0.60 is a stated engineering default: it keeps the cut far enough from
the 3' end that a frameshifted transcript is unlikely to yield a functional
truncated protein, while not rejecting most of a short coding sequence. The
final exon rule, which does come from section 8.5, is applied independently of
this fraction and does not depend on it."""


@dataclass(frozen=True)
class HeuristicWeights:
    """Weights of the labelled fallback on-target heuristic.

    These are NOT published coefficients. They are a Construct convention and
    the only thing that makes them defensible is that they are stated, that the
    features they combine are the section 8.5 features, and that every output
    carrying this score labels it a heuristic (section 8.4). Presenting these
    numbers as a published score is banned by section 16.

    `base` is the starting point on a 0 to 100 scale and every other field is a
    signed adjustment.
    """

    base: float = 50.0
    gc_in_window: float = 15.0
    gc_outside_window: float = -15.0
    gc_per_extra_step: float = -5.0
    gc_step: float = 0.05
    gc_penalty_floor: float = -30.0
    no_long_homopolymer: float = 10.0
    per_long_homopolymer: float = -10.0
    no_u6_terminator: float = 10.0
    u6_terminator_present: float = -25.0
    no_self_complement_stem: float = 10.0
    self_complement_stem_present: float = -10.0
    proximal_gc_adequate: float = 5.0
    proximal_gc_window_nt: int = 6
    proximal_gc_min_count: int = 4
    alternative_pam: float = -20.0

    def as_mapping(self) -> dict[str, Any]:
        return asdict(self)


#: Literature note attached to the one heuristic feature that has observational
#: support in the literature, so the heuristic's provenance is not uniformly
#: "convention". The CRISPOR tool surfaces this as its "Prox GC" column.
PROXIMAL_GC_CITATION = (
    "Observational heuristic surfaced by the CRISPOR tool as its proximal GC column: "
    "highest cleavage reported when the final 6 nt of the spacer contain at least 4 G or C, "
    "from a 39 guide experiment in one invertebrate species, so it is organism specific and "
    f"weak. Source: {CRISPOR_CITATION}"
)


@dataclass(frozen=True)
class GuideRNAThresholds:
    """One immutable set of thresholds. Pass a different instance to change any of them.

    Every field's default is one of the module constants above, so the source of
    each number is documented exactly once.
    """

    spacer_gc_min: float = SPACER_GC_MIN
    spacer_gc_max: float = SPACER_GC_MAX
    max_homopolymer_run: int = MAX_HOMOPOLYMER_RUN
    u6_terminator_motif: str = U6_TERMINATOR_MOTIF
    seed_region_nt: int = SEED_REGION_NT
    off_target_max_mismatches: int = OFF_TARGET_MAX_MISMATCHES
    off_target_fail_max_mismatches: int = OFF_TARGET_FAIL_MAX_MISMATCHES
    off_target_fail_max_seed_mismatches: int = OFF_TARGET_FAIL_MAX_SEED_MISMATCHES
    off_target_warn_max_mismatches: int = OFF_TARGET_WARN_MAX_MISMATCHES
    off_target_max_search_bp: int = OFF_TARGET_MAX_SEARCH_BP
    max_self_complement_stem_nt: int = MAX_SELF_COMPLEMENT_STEM_NT
    min_hairpin_loop_nt: int = MIN_HAIRPIN_LOOP_NT
    knockout_cds_max_fraction: float = KNOCKOUT_CDS_MAX_FRACTION
    heuristic: HeuristicWeights = field(default_factory=HeuristicWeights)

    def __post_init__(self) -> None:
        if not 0.0 <= self.spacer_gc_min < self.spacer_gc_max <= 1.0:
            raise ValueError("spacer GC window must satisfy 0 <= min < max <= 1")
        if self.max_homopolymer_run < 2:
            raise ValueError("max_homopolymer_run must be at least 2")
        if not SEED_REGION_NT_MIN <= self.seed_region_nt <= SEED_REGION_NT_MAX:
            raise ValueError(
                f"seed_region_nt must be within the Appendix C range "
                f"{SEED_REGION_NT_MIN} to {SEED_REGION_NT_MAX}, got {self.seed_region_nt}"
            )
        if self.off_target_max_mismatches < 0:
            raise ValueError("off_target_max_mismatches must not be negative")
        if not 0.0 < self.knockout_cds_max_fraction <= 1.0:
            raise ValueError("knockout_cds_max_fraction must satisfy 0 < value <= 1")

    def as_mapping(self) -> dict[str, Any]:
        """Flat mapping for `DesignResult.parameters_used` (section 5.4 rule 3)."""
        values: dict[str, Any] = {
            key: value for key, value in asdict(self).items() if key != "heuristic"
        }
        values["heuristic_weights"] = self.heuristic.as_mapping()
        return values


DEFAULT_THRESHOLDS = GuideRNAThresholds()
"""The defaults every entry point uses unless a caller supplies its own."""


def nuclease_geometry_mapping() -> dict[str, Any]:
    """Appendix C geometry as plain data, for the fingerprint and for `parameters_used`."""
    return {
        name: {
            "pam_motif": spec.pam_motif,
            "pam_side": spec.pam_side,
            "spacer_length": spec.spacer_length,
            "alternative_pams": [alternative.motif for alternative in spec.alternative_pams],
            "blunt_cut_offset_from_pam": spec.blunt_cut_offset_from_pam,
            "staggered_cut_offsets": list(spec.staggered_cut_offsets)
            if spec.staggered_cut_offsets
            else None,
        }
        for name, spec in sorted(NUCLEASES.items())
    }


def fingerprint_payload(thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS) -> dict[str, Any]:
    """Everything a stored verdict was measured against (section 5.4 rule 4).

    Nuclease geometry is included because a wrong PAM side or spacer length
    would change every verdict just as much as a wrong GC window would.
    """
    payload = dict(thresholds.as_mapping())
    payload["nuclease_geometry"] = nuclease_geometry_mapping()
    payload["cloning_enzyme_sites"] = dict(sorted(CLONING_ENZYME_SITES.items()))
    return payload


THRESHOLD_FINGERPRINTS: Mapping[str, str] = {
    "grna-1.0.0": "a9efc4e926aec6203c0f53486de1fe7eb95e594965a0fa90b121f536deae69b1",
}
"""`validator_version` to threshold fingerprint, per section 5.4 rule 4.

A test calls `assert_version_matches_thresholds(VALIDATOR_VERSION,
fingerprint_payload(), THRESHOLD_FINGERPRINTS)`. Editing a default above
without bumping `VALIDATOR_VERSION` and adding a new entry here fails that
test, and the failure message prints the fingerprint to pin.
"""
