"""Every threshold the assembly validator applies, with the source of each.

Source: section 7 of the engine capability system design, with Appendix D for
the Type IIS enzymes and Appendix E for the literature each threshold derives
from. Section 3.3 constraint 1 forbids an inline magic number and constraint 2
requires every threshold to be configurable, so every value lives here, every
value carries its source in the comment above it, and every value is
overridable through `AssemblyThresholds` in `packages.core.schemas.assembly`.

Appendix E states the rule this module follows: "Where the implementation picks
a threshold, cite where it came from." Three kinds of provenance appear below
and each is labelled explicitly, because the difference matters to a reviewer:

* SPEC: the value or the rule is written in this build's specification
  (section 7.5, Appendix A, Appendix D). Not negotiable.
* TOOL DEFAULT: the value is the published default of an established primer
  design tool or the published recommendation in a vendor protocol. The tool
  and the parameter name are given so the number can be checked.
* CHOSEN DEFAULT: no published table fixes the value. The rationale is stated,
  the nearest published anchor is named, and the value is configurable. Section
  3.3 constraint 1 permits exactly this, provided the default and its source
  are recorded, which is what the comment does. These are the values WP-10
  should look at first.

Primer3 parameter names below refer to the Primer3 release documentation
(`primer3_manual`, the global input tag list). NEB protocol references are to
the product protocols published by New England Biolabs for the named master
mix, and the note under `PROTOCOL` applies: a protocol number is the vendor's
published default and must be confirmed against the lot insert before use.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Validator identity
# ---------------------------------------------------------------------------

# Bumped whenever any threshold in this module changes (section 5.4 rule 4).
# `THRESHOLD_FINGERPRINTS` pins the thresholds each released version shipped
# with, and `tests/assembly/test_constants.py` fails if a threshold moves
# without a bump.
VALIDATOR_VERSION: str = "assembly-1.1.0"


# ---------------------------------------------------------------------------
# Primer melting temperature, section 7.5 checks 1 and 2
# ---------------------------------------------------------------------------

# Degrees C either side of the request's `target_tm_c` within which a primer Tm
# is a PASS. Outside it the primer WARNs (section 7.5 check 1: "WARN outside").
# TOOL DEFAULT: Primer3 ships PRIMER_MIN_TM 57.0, PRIMER_OPT_TM 60.0 and
# PRIMER_MAX_TM 63.0, a band of plus or minus 3.0 C about the optimum. The spec
# request schema (section 7.2) defaults `target_tm_c` to the same 60.0 C, so
# this reproduces the Primer3 band exactly.
PRIMER_TM_WARN_TOLERANCE_C: float = 3.0

# Degrees C either side of `target_tm_c` beyond which a primer Tm is a FAIL
# (section 7.5 check 1: "FAIL far outside").
# CHOSEN DEFAULT: no published tool defines a second, harder band, because
# Primer3 rejects a candidate outside its single window rather than grading it.
# Section 7.5 requires two severities, so the FAIL boundary is set here at ten
# degrees, on the grounds that a primer whose Tm is more than 10 C from the
# target cannot share a thermocycling program with the rest of the assembly:
# the annealing temperature that works for one will not amplify the other.
# Configurable.
PRIMER_TM_FAIL_TOLERANCE_C: float = 10.0

# Maximum acceptable Tm difference, in C, between the two primers of a pair
# (section 7.5 check 2, WARN on violation).
# CHOSEN DEFAULT: Primer3 exposes the same control as PRIMER_PAIR_MAX_DIFF_TM
# but its release default is 100.0 C, which is effectively unconstrained, so
# the tool default is of no use here. Five degrees is the figure in standard
# primer design guidance (for example the NEB Tm Calculator usage notes and the
# IDT primer design guidelines, both of which advise keeping a pair within
# about 5 C) and it is what a single annealing temperature can serve.
# Configurable.
PRIMER_PAIR_MAX_TM_DELTA_C: float = 5.0


# ---------------------------------------------------------------------------
# Primer composition, section 7.5 checks 3, 4, 5 and 10
# ---------------------------------------------------------------------------

# GC fraction window for a primer's template-binding region (check 3, WARN).
# TOOL DEFAULT, narrowed deliberately: Primer3's PRIMER_MIN_GC and
# PRIMER_MAX_GC default to 20 and 80 percent, which is a synthesis-feasibility
# window rather than a design recommendation. The 40 to 60 percent window used
# here is the standard recommendation in primer design guidance (NEB and IDT
# primer design documentation both state it), and it is the window the Tm
# window above is consistent with. Configurable.
PRIMER_GC_MIN_FRACTION: float = 0.40
PRIMER_GC_MAX_FRACTION: float = 0.60

# Length window, in nucleotides, for a primer's template-binding region
# (check 4, WARN).
# TOOL DEFAULT: Primer3 ships PRIMER_MIN_SIZE 18, PRIMER_OPT_SIZE 20 and
# PRIMER_MAX_SIZE 27. These are those values.
PRIMER_MIN_LENGTH_NT: int = 18
PRIMER_MAX_LENGTH_NT: int = 27

# Maximum total length, in nucleotides, of a primer including any 5' tail
# (restriction site, Type IIS site plus overhang, or Gibson homology arm).
# The binding window above deliberately does not cover the tail, because a
# Gibson or Golden Gate primer is longer than any Primer3 candidate by
# construction and measuring the whole oligo against 27 nt would fire on every
# correct design.
# CHOSEN DEFAULT: an ordering practicality limit rather than a thermodynamic
# one. Standard desalted oligo synthesis is routinely offered to 60 nt, and a
# Gibson primer with the longest overlap this module will design (40 nt, below)
# plus the longest binding region (27 nt) reaches 67 nt, so a design above this
# limit is worth surfacing rather than silently ordering. Configurable.
PRIMER_MAX_TOTAL_LENGTH_NT: int = 60

# 3' end stability, check 5: "3' terminal base and the last five bases are not
# excessively GC-rich, and the 3' base is not T" (WARN).
# SPEC: the rule, the five-base window and the "not T" condition are stated in
# section 7.5 check 5. The maximum count within the window is the one number
# the spec leaves open.
# TOOL DEFAULT for the window: Primer3 measures 3' end stability over the last
# five bases (PRIMER_MAX_END_STABILITY) and exposes a 3' GC requirement as
# PRIMER_GC_CLAMP.
# CHOSEN DEFAULT for the count: at most 3 of the last 5 bases may be G or C.
# Rationale: 3 of 5 is 60 percent, the top of the primer GC window above, so a
# 3' end GC-richer than the primer's own permitted composition is what gets
# flagged. Configurable.
PRIMER_THREE_PRIME_WINDOW_NT: int = 5
PRIMER_THREE_PRIME_MAX_GC_IN_WINDOW: int = 3

# Maximum homopolymer run length, in nucleotides, inside a primer
# (check 10, WARN). A run longer than this is reported.
# TOOL DEFAULT: Primer3's PRIMER_MAX_POLY_X default is 5.
PRIMER_MAX_HOMOPOLYMER_RUN_NT: int = 5


# ---------------------------------------------------------------------------
# Secondary structure, section 7.4 and section 7.5 checks 6, 7 and 8
# ---------------------------------------------------------------------------

# Minimum hairpin loop size, in nucleotides. A stem cannot close a loop shorter
# than this.
# TOOL DEFAULT: the minimum hairpin loop size in the standard nucleic acid
# secondary structure models is 3 nt, and ViennaRNA ships the same minimum
# (`TURN`, also exposed as the `--minLoopSize`/`min_loop_size` option).
HAIRPIN_MIN_LOOP_NT: int = 3

# Hairpin free energy, in kcal/mol, at or below which a primer WARNs
# (check 6). Used when a free energy engine is available.
# CHOSEN DEFAULT: no published table fixes a primer-rejection free energy.
# Established tools express the same constraint in different units: Primer3's
# PRIMER_MAX_HAIRPIN_TH default rejects a primer whose hairpin melting
# temperature exceeds 47.0 C, while IDT's OligoAnalyzer documentation advises
# attention to hairpins with a free energy below about -2 kcal/mol. The latter
# is in the units this check reports, so it is the default here. Configurable,
# and the engine that produced the number is recorded in `parameters_used` so
# the threshold is never read against the wrong metric.
HAIRPIN_DG_WARN_KCAL_PER_MOL: float = -2.0

# Hairpin free energy, in kcal/mol, at or below which a primer FAILS when the
# fold involves the 3' end (check 6: "FAIL if 3' stem below hard threshold").
# CHOSEN DEFAULT: one and a half times the WARN threshold. Rationale: a 3' stem
# is qualitatively worse than an internal one because the 3' end is the end the
# polymerase extends, so a hairpin that sequesters it stops the primer working
# rather than merely competing with annealing. Section 7.4 states this
# asymmetry ("especially when the stem involves the 3' end") without giving a
# number. Configurable.
HAIRPIN_THREE_PRIME_DG_FAIL_KCAL_PER_MOL: float = -3.0

# Number of 3'-terminal nucleotides whose involvement in a fold or a dimer
# counts as 3' involvement.
# CHOSEN DEFAULT: the same five-base window as the 3' stability check above, so
# the module uses one definition of "the 3' end" throughout. Configurable.
THREE_PRIME_INVOLVEMENT_WINDOW_NT: int = 5

# Hairpin stem length, in base pairs, at or above which a primer WARNs when no
# free energy engine is available and the documented sliding-window
# complementarity score is used instead (section 7.4, open question Q6).
#
# CHOSEN DEFAULT: six base pairs, calibrated against the free energy threshold
# the primary engine applies to the same oligo. The whole job of this constant
# is to express `HAIRPIN_DG_WARN_KCAL_PER_MOL = -2.0` in base pairs, so that the
# fallback agrees in severity with the engine it stands in for instead of
# contradicting it.
#
# DERIVATION, measured rather than estimated. For random 47 nt oligos the stem
# this scan reports was rebuilt as a dot-bracket structure and handed to the
# same DNA energy model the primary engine uses
# (`RNA.eval_structure_simple` under `dna_mathews2004`), giving the free energy
# the primary engine assigns to the very stem the fallback found:
#
#   stem   mean dG37   fraction at or past -2.0   fraction at or past -3.0
#   4 bp      -0.4            0.17                       0.04
#   5 bp      -2.1            0.52                       0.30
#   6 bp      -3.7            0.88                       0.65
#   7 bp      -5.0            0.90                       0.86
#
# Two readings of that table are possible and they differ by one base pair. On
# a mean-energy reading the -2.0 crossing is at 5 bp and the -3.0 crossing at
# 6 bp. On a concurrence reading, which is the one adopted here, the question is
# the one that matters for a stand-in engine: when the fallback fires, would the
# primary engine agree? At 5 bp it agrees about half the time, which is a coin
# flip; at 6 bp it agrees in 0.88 of cases. Six base pairs is therefore the
# shortest stem at which this check firing is usually right rather than usually
# arbitrary, and the one base pair of conservatism relative to the mean-energy
# crossing is spent in the direction that keeps a WARN informative.
#
# WHY THE PREVIOUS VALUE OF 4 WAS A DEFECT, not merely a stricter preference.
# A bare base-pair count is not length normalized, and the old rationale was
# calibrated on a 20-mer and then applied unchanged to the 40 to 47 nt tailed
# primers this module designs. Measured on random oligos at 50 percent GC, a
# stem of 4 bp or more occurs in 0.16 of 20-mers but in 0.90 of 47-mers. A check
# that fires on nine structureless designs in ten carries no information and is
# the section 3.4 failure mode: it teaches the reader to ignore the validator,
# including the checks that matter. At 6 bp the same rate is 0.004 at 20 nt and
# 0.10 at 47 nt. Raising `HAIRPIN_MIN_LOOP_NT` is not the lever: only about 5
# percent of qualifying stems in a 47-mer close a 3 nt loop, so the excess comes
# from stem length, not from minimal loops.
#
# The units are base pairs, not kcal/mol, and the message and `parameters_used`
# say so. Configurable.
HAIRPIN_WINDOW_STEM_WARN_BP: int = 6

# Hairpin stem length, in base pairs, at or above which a primer FAILS when the
# stem involves the 3' end and the sliding-window score is in use.
#
# CHOSEN DEFAULT: seven base pairs, one base pair above the WARN stem. Both
# halves of that statement carry weight. The "one above the WARN stem" relation
# is the same 3' asymmetry given for
# HAIRPIN_THREE_PRIME_DG_FAIL_KCAL_PER_MOL and is unchanged. The absolute value
# comes from the same measured table in the WARN constant above: 7 bp is the
# stem length at which the primary engine's -3.0 kcal/mol FAIL level is reached
# in 0.86 of cases, against 0.65 at 6 bp and 0.30 at 5 bp. Since this threshold
# carries FAIL severity and so blocks a design outright, the concurrence
# reading is the only defensible one: a FAIL that the primary engine would
# contradict in a third of cases is not a FAIL.
#
# WHY THE PREVIOUS VALUE OF 5 WAS A DEFECT. A 5 bp stem touching the last 5
# bases occurs in roughly 0.12 of random 47 nt oligos, so about one correct
# tailed primer in eight was at risk of an outright hairpin FAIL, with no
# redesign available to the user because the oligo cannot be moved off its
# junction. That is worse than a noisy WARN: it is a FAIL on a design with
# nothing wrong with it. The previous value shares the WARN constant's root
# cause, being calibrated for a 20-mer and not length normalized.
#
# Configurable.
HAIRPIN_WINDOW_STEM_THREE_PRIME_FAIL_BP: int = 7

# Maximum self-complementarity score, in base pairs, anywhere in a primer
# (check 7, WARN). Score definition is in `structure.py`.
# TOOL DEFAULT: Primer3's PRIMER_MAX_SELF_ANY default is 8.00, in units where
# 1.00 is one matched base pair.
MAX_SELF_COMPLEMENTARITY_ANY_BP: float = 8.0

# Maximum self-complementarity score, in base pairs, involving the 3' end
# (check 7, WARN). This is the extendable case section 7.4 singles out.
# TOOL DEFAULT: Primer3's PRIMER_MAX_SELF_END default is 3.00, same units.
MAX_SELF_COMPLEMENTARITY_END_BP: float = 3.0

# Maximum complementarity score, in base pairs, anywhere between the two
# primers of a pair (check 8, WARN).
# TOOL DEFAULT: Primer3's PRIMER_PAIR_MAX_COMPL_ANY default is 8.00.
MAX_PAIR_COMPLEMENTARITY_ANY_BP: float = 8.0

# Maximum complementarity score, in base pairs, involving either primer's 3'
# end (check 8, WARN). A 3' hetero-dimer is extendable and consumes the
# reaction, which is the point section 7.4 makes.
# TOOL DEFAULT: Primer3's PRIMER_PAIR_MAX_COMPL_END default is 3.00.
MAX_PAIR_COMPLEMENTARITY_END_BP: float = 3.0


# ---------------------------------------------------------------------------
# Gibson assembly, section 7.5 checks 11, 12 and 13
# ---------------------------------------------------------------------------

# Terminal homology length window, in base pairs, for a Gibson junction
# (check 11, FAIL outside).
# TOOL DEFAULT: the NEBuilder HiFi DNA Assembly and Gibson Assembly protocols
# recommend overlaps of 15 to 20 bp for assemblies of a few fragments, and
# Gibson et al. 2009 (Nat Methods 6:343-345), the method's originating paper
# cited in Appendix E, used 40 bp overlaps. The window spans both.
GIBSON_OVERLAP_MIN_BP: int = 15
GIBSON_OVERLAP_MAX_BP: int = 40

# Overlap length, in base pairs, this module designs when it is free to choose
# (not a validation threshold).
# TOOL DEFAULT: the midpoint of the NEBuilder HiFi recommendation of 15 to
# 20 bp, rounded up, which is the length the NEBuilder Assembly Tool produces
# for a two or three fragment assembly.
GIBSON_OVERLAP_DESIGN_BP: int = 20

# Minimum Gibson overlap Tm, in degrees C (check 12, WARN below).
# TOOL DEFAULT: the NEBuilder Assembly Tool designs overlaps to a melting
# temperature of at least 48 C, and the NEBuilder HiFi protocol states the same
# floor. Measured with the same nearest-neighbor implementation as the primers,
# at the request's salt and strand concentration.
GIBSON_OVERLAP_MIN_TM_C: float = 48.0

# Longest shared complementary stretch, in base pairs, permitted between two
# different Gibson junction overlaps before mis-assembly is possible
# (check 13, FAIL at or above).
# CHOSEN DEFAULT: ten base pairs. Rationale: the failure mode is one junction's
# homology arm annealing to another junction's, which needs enough shared
# complementarity to survive the 50 C assembly incubation; ten base pairs of
# contiguous complementarity is around the shortest stretch that does, and it
# is half the designed overlap length above, so a junction pair sharing half
# its homology is reported. Configurable.
GIBSON_JUNCTION_MAX_SHARED_HOMOLOGY_BP: int = 10


# ---------------------------------------------------------------------------
# Golden Gate, section 7.5 checks 14 to 17 and Appendix D
# ---------------------------------------------------------------------------

# Number of spacer nucleotides placed between the 5' end of a Golden Gate
# primer and the Type IIS recognition site.
# TOOL DEFAULT: the NEB Golden Gate Assembly protocol and the NEB Golden Gate
# Assembly Tool add a short 5' spacer so the enzyme has duplex DNA to bind on
# both sides of its site; one nucleotide is the minimum they use.
GOLDEN_GATE_PRIMER_SPACER_NT: int = 1

# Overhang length, in nucleotides, expected of a standard Golden Gate assembly.
# SPEC: Appendix D gives a 4 nt overhang for BsaI, BsmBI, BbsI and AarI and a
# 3 nt overhang for SapI, so the length is read from the enzyme record in
# `enzymes.py` and this value is only the default the checks report against
# when an assembly mixes enzymes. Section 7.5 checks 15 to 17 speak of "4 bp
# fusion overhangs".
GOLDEN_GATE_DEFAULT_OVERHANG_NT: int = 4


# ---------------------------------------------------------------------------
# Amplicon size, section 7.5 check 19
# ---------------------------------------------------------------------------

# Amplicon length window, in base pairs, within which a PCR is routine
# (check 19, WARN outside).
# TOOL DEFAULT: the NEB Q5 High-Fidelity DNA Polymerase protocol specifies an
# extension time of 20 to 30 seconds per kilobase and is documented for
# amplicons up to about 10 kb under standard cycling; below about 100 bp an
# amplicon is hard to resolve from primer dimer on a gel. Configurable, and a
# long-amplicon protocol legitimately moves the upper bound.
AMPLICON_MIN_BP: int = 100
AMPLICON_MAX_BP: int = 10_000


# ---------------------------------------------------------------------------
# Protocol, section 7.7
# ---------------------------------------------------------------------------
#
# PROTOCOL NOTE. Every number in this block is the vendor's published default
# for the named master mix at the time of writing. It is reproduced so the
# protocol output is a real protocol rather than a placeholder, and it is
# configurable because a different polymerase or master mix has different
# numbers. The generated protocol states the product it is based on, and that
# the lab must confirm it against the lot insert.

# PROTOCOL. Annealing temperature offset, in degrees C, below the lower primer Tm.
# Section 7.7 requires the annealing temperature to be "derived from the
# computed Tm rather than assumed", which this is.
# CHOSEN DEFAULT: five degrees below the lower of the pair's two Tm values is
# the standard rule of thumb in PCR guidance. It is deliberately conservative:
# NEB recommends for Q5 an annealing temperature based on its own Tm
# calculator, typically at or just above the lower primer Tm, so a lab using Q5
# should raise this. Configurable, and the protocol output names the rule it
# applied.
ANNEALING_OFFSET_BELOW_MIN_TM_C: float = 5.0

# PROTOCOL. Floor and ceiling, in degrees C, for the derived annealing
# temperature, so a
# pathological Tm cannot produce an impossible thermocycler step.
# TOOL DEFAULT: the NEB Q5 protocol states an annealing range of 50 to 72 C.
ANNEALING_MIN_C: float = 50.0
ANNEALING_MAX_C: float = 72.0

# PROTOCOL, TOOL DEFAULT: PCR cycling, NEB Q5 High-Fidelity DNA Polymerase
# standard protocol.
PCR_INITIAL_DENATURATION_C: float = 98.0
PCR_INITIAL_DENATURATION_S: int = 30
PCR_DENATURATION_C: float = 98.0
PCR_DENATURATION_S: int = 10
PCR_ANNEALING_S: int = 20
PCR_EXTENSION_C: float = 72.0
PCR_EXTENSION_S_PER_KB: int = 30
PCR_FINAL_EXTENSION_S: int = 120
PCR_CYCLES: int = 30

# PROTOCOL, TOOL DEFAULT: Gibson assembly incubation, NEBuilder HiFi DNA
# Assembly protocol: 50 C for
# 15 minutes for two or three fragments, 60 minutes for four to six.
GIBSON_INCUBATION_C: float = 50.0
GIBSON_INCUBATION_MIN_FEW_FRAGMENTS: int = 15
GIBSON_INCUBATION_MIN_MANY_FRAGMENTS: int = 60
GIBSON_FEW_FRAGMENTS_MAX: int = 3

# PROTOCOL, TOOL DEFAULT: Golden Gate cycling, NEB Golden Gate Assembly
# protocol: cycles of 37 C
# digestion and 16 C ligation, followed by a 60 C final digestion.
GOLDEN_GATE_DIGEST_C: float = 37.0
GOLDEN_GATE_DIGEST_S: int = 300
GOLDEN_GATE_LIGATE_C: float = 16.0
GOLDEN_GATE_LIGATE_S: int = 300
GOLDEN_GATE_CYCLES: int = 30
GOLDEN_GATE_FINAL_DIGEST_C: float = 60.0
GOLDEN_GATE_FINAL_DIGEST_S: int = 300

# PROTOCOL, TOOL DEFAULT: restriction digest for simple PCR cloning, the
# standard condition for the
# great majority of NEB restriction enzymes.
PCR_CLONING_DIGEST_C: float = 37.0
PCR_CLONING_DIGEST_MIN: int = 60


def thresholds() -> dict[str, Any]:
    """Every biological threshold this validator applies, for `parameters_used`.

    Section 5.4 rule 3: "Every threshold used appears in `parameters_used`. A
    user must be able to see what the verdict was measured against." This is
    also the mapping fingerprinted for rule 4, so the protocol numbers above
    are deliberately absent: they are reaction conditions in the output, not
    thresholds a verdict was measured against, and the protocol reports them
    itself.
    """
    return {
        "primer_tm_warn_tolerance_c": PRIMER_TM_WARN_TOLERANCE_C,
        "primer_tm_fail_tolerance_c": PRIMER_TM_FAIL_TOLERANCE_C,
        "primer_pair_max_tm_delta_c": PRIMER_PAIR_MAX_TM_DELTA_C,
        "primer_gc_min_fraction": PRIMER_GC_MIN_FRACTION,
        "primer_gc_max_fraction": PRIMER_GC_MAX_FRACTION,
        "primer_min_length_nt": PRIMER_MIN_LENGTH_NT,
        "primer_max_length_nt": PRIMER_MAX_LENGTH_NT,
        "primer_max_total_length_nt": PRIMER_MAX_TOTAL_LENGTH_NT,
        "primer_three_prime_window_nt": PRIMER_THREE_PRIME_WINDOW_NT,
        "primer_three_prime_max_gc_in_window": PRIMER_THREE_PRIME_MAX_GC_IN_WINDOW,
        "primer_max_homopolymer_run_nt": PRIMER_MAX_HOMOPOLYMER_RUN_NT,
        "hairpin_min_loop_nt": HAIRPIN_MIN_LOOP_NT,
        "hairpin_dg_warn_kcal_per_mol": HAIRPIN_DG_WARN_KCAL_PER_MOL,
        "hairpin_three_prime_dg_fail_kcal_per_mol": HAIRPIN_THREE_PRIME_DG_FAIL_KCAL_PER_MOL,
        "hairpin_window_stem_warn_bp": HAIRPIN_WINDOW_STEM_WARN_BP,
        "hairpin_window_stem_three_prime_fail_bp": HAIRPIN_WINDOW_STEM_THREE_PRIME_FAIL_BP,
        "three_prime_involvement_window_nt": THREE_PRIME_INVOLVEMENT_WINDOW_NT,
        "max_self_complementarity_any_bp": MAX_SELF_COMPLEMENTARITY_ANY_BP,
        "max_self_complementarity_end_bp": MAX_SELF_COMPLEMENTARITY_END_BP,
        "max_pair_complementarity_any_bp": MAX_PAIR_COMPLEMENTARITY_ANY_BP,
        "max_pair_complementarity_end_bp": MAX_PAIR_COMPLEMENTARITY_END_BP,
        "gibson_overlap_min_bp": GIBSON_OVERLAP_MIN_BP,
        "gibson_overlap_max_bp": GIBSON_OVERLAP_MAX_BP,
        "gibson_overlap_design_bp": GIBSON_OVERLAP_DESIGN_BP,
        "gibson_overlap_min_tm_c": GIBSON_OVERLAP_MIN_TM_C,
        "gibson_junction_max_shared_homology_bp": GIBSON_JUNCTION_MAX_SHARED_HOMOLOGY_BP,
        "golden_gate_primer_spacer_nt": GOLDEN_GATE_PRIMER_SPACER_NT,
        "golden_gate_default_overhang_nt": GOLDEN_GATE_DEFAULT_OVERHANG_NT,
        "amplicon_min_bp": AMPLICON_MIN_BP,
        "amplicon_max_bp": AMPLICON_MAX_BP,
        "annealing_offset_below_min_tm_c": ANNEALING_OFFSET_BELOW_MIN_TM_C,
        "annealing_min_c": ANNEALING_MIN_C,
        "annealing_max_c": ANNEALING_MAX_C,
    }


# Threshold fingerprint per released `validator_version` (section 5.4 rule 4,
# enforced by `assert_version_matches_thresholds`). Editing any threshold above
# without adding a new version here fails `tests/assembly/test_constants.py`.
THRESHOLD_FINGERPRINTS: dict[str, str] = {
    "assembly-1.0.0": "c379f77561c72a33829a948e0c26097dc6c3af5229ea582330764332f4344db6",
    # assembly-1.1.0 recalibrated the two sliding-window hairpin stem thresholds
    # against the free energy levels the primary engine applies, raising
    # HAIRPIN_WINDOW_STEM_WARN_BP from 4 to 6 and
    # HAIRPIN_WINDOW_STEM_THREE_PRIME_FAIL_BP from 5 to 7. The derivation is in
    # the comment above each constant. A report stored under assembly-1.0.0
    # read its window hairpin verdict against the older, uncalibrated pair.
    "assembly-1.1.0": "3889464a48cf006b6e5c9b03ee90d5f4afeb1e9566598fc10982a6b3ee434a5e",
}

# Citations attached to the `CheckResult.citation` field, keyed by check_id
# (section 5.1: "citation: why this threshold exists"). The text names the
# source of the threshold the check applied, not a general reference.
CITATIONS: dict[str, str] = {
    "primer.tm_in_range": (
        "Nearest-neighbor thermodynamics, SantaLucia 1998 unified parameters "
        "(Appendix A). Window from the Primer3 defaults PRIMER_MIN_TM 57 / "
        "PRIMER_OPT_TM 60 / PRIMER_MAX_TM 63."
    ),
    "primer.pair_tm_delta": (
        "Standard primer design guidance (NEB Tm Calculator usage notes, IDT "
        "primer design guidelines) keeps a pair within about 5 C so one "
        "annealing temperature serves both. Primer3's PRIMER_PAIR_MAX_DIFF_TM "
        "exposes the same control but defaults to 100 C, unconstrained."
    ),
    "primer.gc_content": (
        "40 to 60 percent is the standard primer GC recommendation (NEB and "
        "IDT primer design documentation). Primer3's PRIMER_MIN_GC / "
        "PRIMER_MAX_GC default to the wider 20 to 80 percent synthesis window."
    ),
    "primer.length": "Primer3 defaults PRIMER_MIN_SIZE 18 / PRIMER_OPT_SIZE 20 / PRIMER_MAX_SIZE 27.",
    "primer.three_prime_stability": (
        "Rule stated in section 7.5 check 5. Five-base window follows Primer3's "
        "PRIMER_MAX_END_STABILITY, which is measured over the last five 3' bases."
    ),
    "primer.hairpin": (
        "Section 7.4. Free energy threshold is a configurable default in the "
        "units IDT OligoAnalyzer reports; Primer3 expresses the same constraint "
        "as PRIMER_MAX_HAIRPIN_TH, a hairpin Tm of 47 C. Minimum loop size 3 nt "
        "is the standard nucleic acid secondary structure minimum, as in "
        "ViennaRNA. The sliding-window fallback's stem thresholds of 6 bp and "
        "7 bp are calibrated so that the stem lengths they flag are the ones "
        "the free energy engine assigns past -2.0 and -3.0 kcal/mol under the "
        "same DNA parameters, which is what keeps the two engines from "
        "contradicting each other."
    ),
    "primer.self_dimer": "Primer3 defaults PRIMER_MAX_SELF_ANY 8.00 and PRIMER_MAX_SELF_END 3.00, in base pairs.",
    "primer.hetero_dimer": (
        "Primer3 defaults PRIMER_PAIR_MAX_COMPL_ANY 8.00 and "
        "PRIMER_PAIR_MAX_COMPL_END 3.00, in base pairs."
    ),
    "primer.specificity_in_template": (
        "Section 7.5 check 9: the binding region must occur exactly once in the "
        "supplied template set. Both strands are searched."
    ),
    "primer.homopolymer": (
        "Primer3 default PRIMER_MAX_POLY_X 5. A longer run slips during oligo synthesis and "
        "during polymerase extension."
    ),
    "gibson.overlap_length": (
        "Gibson et al. 2009, Nat Methods 6:343-345 used 40 bp overlaps; the "
        "NEBuilder HiFi DNA Assembly protocol recommends 15 to 20 bp for a few "
        "fragments. The window spans both."
    ),
    "gibson.overlap_tm": "The NEBuilder Assembly Tool designs overlaps to a melting temperature of at least 48 C.",
    "gibson.overlap_uniqueness": (
        "Section 7.5 check 13. The shared-homology limit is a configurable "
        "default: mis-assembly needs enough cross-complementarity between two "
        "junctions to survive the 50 C NEBuilder HiFi incubation."
    ),
    "gg.enzyme_site_internal": (
        "Appendix D Type IIS enzyme reference. Both strands are checked because "
        "these recognition sequences are not palindromic. Engler et al. "
        "introduced the one-pot Type IIS method (Appendix E)."
    ),
    "gg.overhang_uniqueness": "Appendix D overhang rules: all overhangs in one assembly must be distinct.",
    "gg.overhang_not_palindromic": (
        "Appendix D overhang rules: no overhang may equal its own reverse "
        "complement, which would let the fragment ligate in either orientation."
    ),
    "gg.overhang_composition": "Appendix D overhang rules: avoid all-GC and all-AT compositions, which assemble inefficiently.",
    "assembly.fragment_order_defined": (
        "Section 7.5 check 18. A one-pot assembly is only usable if the overhang "
        "topology admits exactly one order."
    ),
    "assembly.amplicon_size": (
        "NEB Q5 High-Fidelity DNA Polymerase protocol: 20 to 30 seconds per "
        "kilobase extension, documented to about 10 kb. The lower bound keeps "
        "the amplicon resolvable from primer dimer."
    ),
}
