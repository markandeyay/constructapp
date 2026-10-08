"""The guide RNA validation checks.

The nine checks of section 8.5, with the `check_id` values exactly as that
table spells them, plus one more that section 8.6 mandates:

    | # | check_id                   | severity on violation |
    | 1 | grna.pam_valid             | FAIL |
    | 2 | grna.spacer_length         | FAIL |
    | 3 | grna.gc_content            | WARN |
    | 4 | grna.u6_terminator         | FAIL when U6-driven, WARN otherwise |
    | 5 | grna.homopolymer           | WARN |
    | 6 | grna.self_complementarity  | WARN |
    | 7 | grna.position_in_cds       | WARN |
    | 8 | grna.self_targeting        | FAIL |
    | 9 | grna.restriction_in_spacer | WARN |
    |   | grna.off_target_hits       | FAIL, WARN or PASS per section 8.6 |

`grna.off_target_hits` is not in the section 8.5 table because that table is
titled "sequence feature checks" and an off-target hit is not a sequence
feature of the spacer. Section 8.6 nonetheless specifies a severity for it,
FAIL on a near-perfect site outside the seed, WARN on a moderate one, PASS on a
clean searched space, and `ValidationReport` is the only place a severity can
live. Reporting it there is what makes a dangerous off-target able to move the
overall verdict. This is recorded under spec challenges in `PROGRESS.md`.

Two rules shape every function here.

* Section 5.4 rule 2: the message says what to do. Each one names the observed
  value, the threshold, and the next action.
* Section 3.3 constraint 4: a check that cannot be evaluated returns UNKNOWN
  with the reason. There is no code path in this module that returns PASS
  because an input was missing.

Every threshold is read from the `GuideRNAThresholds` instance passed in, never
from a module global, so a caller can change any of them (section 3.3
constraint 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.core.schemas.capability import CheckResult, Severity
from packages.core.schemas.grna import (
    GuideRNADesign,
    GuideRNARequest,
    GuideSpec,
    OffTargetSummary,
    Placement,
)
from packages.core.sequence import (
    clean_sequence,
    find_both_strands,
    find_with_mismatches,
    gc_content,
    homopolymer_runs,
    reverse_complement,
)

from .constants import (
    APPENDIX_C,
    APPENDIX_D,
    CLONING_ENZYME_SITES,
    DEFAULT_THRESHOLDS,
    GuideRNAThresholds,
    SECTION_8_5,
    SECTION_8_6,
)
from .enumeration import ResolvedPlacement, pam_at, resolve_placement, seed_positions
from .nuclease import NucleaseSpec, get_nuclease, pam_matches
from .offtarget import seed_label
from .selfcomp import longest_self_complementary_stem
from .vectors import CloningVector, get_vector

CONVENTION = "Construct convention, not a published value; see the docstring in constants.py"


@dataclass(frozen=True)
class CheckContext:
    """Everything the checks read, resolved once so each check stays small."""

    request: GuideRNARequest
    guide: GuideSpec
    spacer: str
    spec: NucleaseSpec
    resolved: ResolvedPlacement
    vector: CloningVector
    off_target: OffTargetSummary
    thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS

    @property
    def placement(self) -> Placement | None:
        return self.resolved.placement

    @property
    def u6_driven(self) -> bool:
        return self.request.expression_system == "u6_plasmid"


def build_context(
    design: GuideRNADesign,
    off_target: OffTargetSummary,
    thresholds: GuideRNAThresholds = DEFAULT_THRESHOLDS,
) -> CheckContext:
    """Resolve the shared inputs of every check for one design."""
    return CheckContext(
        request=design.request,
        guide=design.guide,
        spacer=clean_sequence(design.guide.spacer),
        spec=get_nuclease(design.request.nuclease),
        resolved=resolve_placement(design.request, design.guide),
        vector=get_vector(design.request.cloning_vector, design.request.nuclease),
        off_target=off_target,
        thresholds=thresholds,
    )


# ---------------------------------------------------------------------------
# 1. grna.pam_valid
# ---------------------------------------------------------------------------


def check_pam_valid(context: CheckContext) -> CheckResult:
    """A valid PAM for the nuclease at the correct offset and orientation. FAIL.

    Three distinct failures, and the third is the one Appendix C calls the most
    likely integration bug in this capability:

    1. the reported PAM does not satisfy the nuclease's motif;
    2. the reported PAM satisfies the motif but the target does not carry it at
       the position the nuclease geometry requires, which is what a 3' offset
       applied to a 5' PAM nuclease produces;
    3. the PAM is the nuclease's tolerated alternative, which is a WARN and not
       a PASS (Appendix C).
    """
    spec = context.spec
    reported = clean_sequence(context.guide.pam)
    side = "5' of the spacer" if spec.pam_side == "five_prime" else "3' of the spacer"
    threshold = f"{spec.pam_motif} {side}, spacer {spec.spacer_length} nt"
    matches, is_alternative = pam_matches(spec, reported)

    if not matches:
        expected = ", ".join(motif for motif, _ in spec.pam_motifs())
        return CheckResult(
            check_id="grna.pam_valid",
            label="PAM valid for the nuclease",
            severity=Severity.FAIL,
            message=(
                f"The reported PAM {reported} is not a {spec.name} PAM. {spec.name} requires "
                f"{expected} located {side}. Choose a protospacer whose {side} neighbour matches "
                f"{spec.pam_motif}, or change the nuclease to one whose PAM this site satisfies."
            ),
            observed=reported,
            threshold=threshold,
            citation=APPENDIX_C,
        )

    placement = context.placement
    if placement is None:
        return CheckResult(
            check_id="grna.pam_valid",
            label="PAM valid for the nuclease",
            severity=Severity.UNKNOWN,
            message=(
                f"The reported PAM {reported} satisfies the {spec.name} motif, but its offset "
                f"could not be verified against the target. {context.resolved.reason} Until the "
                "guide can be located, the PAM offset is unverified and this check is not a pass."
            ),
            observed=reported,
            threshold=threshold,
            citation=APPENDIX_C,
        )

    if placement.pam_observed != reported:
        wrong_side = "3' of the spacer" if spec.pam_side == "five_prime" else "5' of the spacer"
        return CheckResult(
            check_id="grna.pam_valid",
            label="PAM valid for the nuclease",
            severity=Severity.FAIL,
            message=(
                f"The reported PAM {reported} is not what the target carries at the correct "
                f"offset. {spec.name} places its PAM {side}, and the target reads "
                f"{placement.pam_observed} there (target positions {placement.pam_start} to "
                f"{placement.pam_end}). A PAM taken from {wrong_side} instead is the classic "
                f"offset error for this nuclease. Re-extract the PAM {side} of the spacer, or "
                "re-enumerate the guides so the offset comes from the nuclease geometry."
            ),
            coordinates=(placement.pam_start, placement.pam_end),
            observed=f"{placement.pam_observed} at the correct offset, {reported} reported",
            threshold=threshold,
            citation=APPENDIX_C,
            remediation=[
                f"use PAM {placement.pam_observed} for this spacer",
                f"{spec.name} PAM side is {spec.pam_side}",
            ],
        )

    if is_alternative:
        note = next(
            (
                alternative.note
                for alternative in spec.alternative_pams
                if _motif_fits(reported, alternative.motif)
            ),
            "This PAM is tolerated at reduced efficiency (Appendix C).",
        )
        return CheckResult(
            check_id="grna.pam_valid",
            label="PAM valid for the nuclease",
            severity=Severity.WARN,
            message=(
                f"The PAM {reported} at target positions {placement.pam_start} to "
                f"{placement.pam_end} is an alternative PAM, not the primary {spec.pam_motif}. "
                f"{note} Prefer a guide with a {spec.pam_motif} PAM if one covers the same "
                "region, and expect lower cutting if you keep this one."
            ),
            coordinates=(placement.pam_start, placement.pam_end),
            observed=reported,
            threshold=threshold,
            citation=APPENDIX_C,
            tier="B",
        )

    return CheckResult(
        check_id="grna.pam_valid",
        label="PAM valid for the nuclease",
        severity=Severity.PASS,
        message=(
            f"The PAM {reported} sits {side} at target positions {placement.pam_start} to "
            f"{placement.pam_end} and satisfies the {spec.name} motif {spec.pam_motif}. "
            "No change needed."
        ),
        coordinates=(placement.pam_start, placement.pam_end),
        observed=reported,
        threshold=threshold,
        citation=APPENDIX_C,
    )


def _motif_fits(pam: str, motif: str) -> bool:
    from packages.core.sequence import matches_iupac

    return len(pam) == len(motif) and matches_iupac(pam, motif)


# ---------------------------------------------------------------------------
# 2. grna.spacer_length
# ---------------------------------------------------------------------------


def check_spacer_length(context: CheckContext) -> CheckResult:
    """Spacer length correct for the nuclease. FAIL."""
    spec = context.spec
    observed = len(context.spacer)
    expected = spec.spacer_length
    if observed == expected:
        return CheckResult(
            check_id="grna.spacer_length",
            label="Spacer length correct for the nuclease",
            severity=Severity.PASS,
            message=(
                f"The spacer is {observed} nt, which is the {spec.name} spacer length. "
                "No change needed."
            ),
            observed=f"{observed} nt",
            threshold=f"{expected} nt",
            citation=APPENDIX_C,
        )
    difference = observed - expected
    direction = "longer" if difference > 0 else "shorter"
    action = (
        f"trim {abs(difference)} nt from the PAM-distal end"
        if difference > 0
        else f"extend the spacer {abs(difference)} nt away from the PAM"
    )
    return CheckResult(
        check_id="grna.spacer_length",
        label="Spacer length correct for the nuclease",
        severity=Severity.FAIL,
        message=(
            f"The spacer is {observed} nt, which is {abs(difference)} nt {direction} than the "
            f"{expected} nt {spec.name} requires. Either {action}, or switch to the nuclease whose "
            f"spacer length is {observed} nt."
        ),
        observed=f"{observed} nt",
        threshold=f"{expected} nt",
        citation=APPENDIX_C,
        remediation=[f"{spec.name} spacer length is {expected} nt", action],
    )


# ---------------------------------------------------------------------------
# 3. grna.gc_content
# ---------------------------------------------------------------------------


def check_gc_content(context: CheckContext) -> CheckResult:
    """Spacer GC fraction within the configured window. WARN."""
    thresholds = context.thresholds
    fraction = gc_content(context.spacer)
    window = f"{thresholds.spacer_gc_min:.2f} to {thresholds.spacer_gc_max:.2f}"
    observed = f"{fraction:.2f}"
    if thresholds.spacer_gc_min <= fraction <= thresholds.spacer_gc_max:
        return CheckResult(
            check_id="grna.gc_content",
            label="Spacer GC fraction in window",
            severity=Severity.PASS,
            message=(
                f"Spacer GC fraction is {observed}, inside the configured window {window}. "
                "No change needed."
            ),
            observed=observed,
            threshold=window,
            citation=APPENDIX_C,
        )
    if fraction < thresholds.spacer_gc_min:
        consequence = (
            "A spacer this AT-rich binds weakly, so cutting is often low. Pick a guide shifted "
            "into a more GC-rich part of the target"
        )
    else:
        consequence = (
            "A spacer this GC-rich binds very stably, which raises tolerance of mismatched "
            "off-target sites. Pick a guide shifted into a less GC-rich part of the target"
        )
    return CheckResult(
        check_id="grna.gc_content",
        label="Spacer GC fraction in window",
        severity=Severity.WARN,
        message=(
            f"Spacer GC fraction is {observed}, outside the configured window {window}. "
            f"{consequence}, or keep this guide and validate it at the bench alongside a second "
            "guide with GC inside the window."
        ),
        observed=observed,
        threshold=window,
        citation=APPENDIX_C,
        tier="B",
    )


# ---------------------------------------------------------------------------
# 4. grna.u6_terminator
# ---------------------------------------------------------------------------


def check_u6_terminator(context: CheckContext) -> CheckResult:
    """No U6 terminator motif in the spacer. FAIL when U6-driven, WARN otherwise."""
    motif = context.thresholds.u6_terminator_motif
    spacer = context.spacer
    position = spacer.find(motif)
    if position < 0:
        return CheckResult(
            check_id="grna.u6_terminator",
            label="No U6 terminator motif in spacer",
            severity=Severity.PASS,
            message=(
                f"The spacer does not contain {motif}, so U6 transcription will not terminate "
                "inside the guide. No change needed."
            ),
            observed=f"{motif} absent",
            threshold=f"{motif} must not appear in the spacer",
            citation=APPENDIX_C,
        )
    severity = Severity.FAIL if context.u6_driven else Severity.WARN
    if context.u6_driven:
        consequence = (
            "The guide is U6 driven, so transcription terminates at this motif and the guide is "
            "truncated or not made at all. Choose a different guide whose spacer has no "
            f"{motif}; a guide shifted by even one nucleotide usually avoids it. If this exact "
            "site is required, express the guide from a promoter that does not terminate at "
            f"{motif}"
        )
    else:
        consequence = (
            f"The expression system is {context.request.expression_system}, so {motif} is not a "
            "termination signal here, but it will become one if this guide is later moved to a "
            "U6 cassette. Prefer a guide without the motif if one is available"
        )
    return CheckResult(
        check_id="grna.u6_terminator",
        label="No U6 terminator motif in spacer",
        severity=severity,
        message=(
            f"The spacer contains {motif} at spacer position {position + 1}. {consequence}."
        ),
        observed=f"{motif} at spacer position {position + 1}",
        threshold=f"{motif} must not appear in the spacer",
        citation=APPENDIX_C,
        tier=None if context.u6_driven else "B",
        remediation=[f"shift the guide so the spacer avoids {motif}"],
    )


# ---------------------------------------------------------------------------
# 5. grna.homopolymer
# ---------------------------------------------------------------------------


def check_homopolymer(context: CheckContext) -> CheckResult:
    """No homopolymer run above the configured length. WARN."""
    maximum = context.thresholds.max_homopolymer_run
    runs = homopolymer_runs(context.spacer, min_length=maximum + 1)
    threshold = f"at most {maximum} identical bases in a row"
    if not runs:
        return CheckResult(
            check_id="grna.homopolymer",
            label="No long homopolymer run in spacer",
            severity=Severity.PASS,
            message=(
                f"The longest homopolymer run in the spacer is within the configured maximum of "
                f"{maximum}. No change needed."
            ),
            observed=f"no run longer than {maximum}",
            threshold=threshold,
            citation=APPENDIX_C,
        )
    described = ", ".join(
        f"{run.length} x {run.base} at spacer positions {run.start + 1} to {run.end}"
        for run in runs
    )
    longest = max(run.length for run in runs)
    return CheckResult(
        check_id="grna.homopolymer",
        label="No long homopolymer run in spacer",
        severity=Severity.WARN,
        message=(
            f"The spacer contains {described}, above the configured maximum of {maximum}. Long "
            "runs make the oligo harder to synthesise accurately and can reduce guide activity. "
            "Shift the guide by one or two nucleotides to break the run, or choose another guide "
            "in the same region and compare the two at the bench."
        ),
        observed=f"longest run {longest}",
        threshold=threshold,
        citation=APPENDIX_C,
        tier="B",
    )


# ---------------------------------------------------------------------------
# 6. grna.self_complementarity
# ---------------------------------------------------------------------------


def check_self_complementarity(context: CheckContext) -> CheckResult:
    """No internal self-complementarity that would disrupt the scaffold fold. WARN."""
    thresholds = context.thresholds
    limit = thresholds.max_self_complement_stem_nt
    stem = longest_self_complementary_stem(context.spacer, min_loop_nt=thresholds.min_hairpin_loop_nt)
    longest = 0 if stem is None else stem.length
    threshold = (
        f"longest internal stem under {limit} bp, with a loop of at least "
        f"{thresholds.min_hairpin_loop_nt} nt ({CONVENTION})"
    )
    if stem is None or stem.length < limit:
        return CheckResult(
            check_id="grna.self_complementarity",
            label="No disruptive internal self-complementarity",
            severity=Severity.PASS,
            message=(
                f"The longest internal self-complementary stem in the spacer is {longest} bp, "
                f"under the configured reporting length of {limit} bp. No change needed."
            ),
            observed=f"{longest} bp stem",
            threshold=threshold,
            citation=SECTION_8_5,
        )
    return CheckResult(
        check_id="grna.self_complementarity",
        label="No disruptive internal self-complementarity",
        severity=Severity.WARN,
        message=(
            f"The spacer can fold on itself over {stem.length} bp ({stem.stem_sequence} at spacer "
            f"positions {stem.left_start + 1} to {stem.left_end} pairing with positions "
            f"{stem.right_start + 1} to {stem.right_end}, loop {stem.loop} nt), at or above the "
            f"configured reporting length of {limit} bp. A spacer hairpin competes with the "
            "scaffold fold and can lower activity. Choose another guide in the same region, or "
            "keep this one and test it against a guide with no internal stem. This is a stem "
            "length measurement, not a free energy calculation, so treat it as a flag rather than "
            "a prediction."
        ),
        coordinates=None,
        observed=f"{stem.length} bp stem, {stem.loop} nt loop",
        threshold=threshold,
        citation=SECTION_8_5,
        tier="B",
    )


# ---------------------------------------------------------------------------
# 7. grna.position_in_cds
# ---------------------------------------------------------------------------


def check_position_in_cds(context: CheckContext) -> CheckResult:
    """For knockout, the cut site is early and constitutive rather than in the final exon. WARN.

    Judgement calls recorded for review:

    * For an intent other than knockout the rule does not apply, so the result
      is PASS with the reason stated. It is not UNKNOWN, because nothing failed
      to evaluate: the constraint simply does not exist for that intent.
    * When `constitutive_regions` is not supplied, the final exon rule and the
      position rule still apply and the message says the constitutive status was
      not supplied. That keeps the useful part of the check available without
      implying the unsupplied part was cleared.
    """
    request = context.request
    thresholds = context.thresholds
    fraction_limit = thresholds.knockout_cds_max_fraction
    threshold = (
        f"cut site inside the coding sequence, within the first "
        f"{fraction_limit:.0%} of it, outside the final exon, in a constitutive region "
        f"(fraction is a {CONVENTION}; the final exon and constitutive rules are {SECTION_8_5})"
    )
    if request.edit_intent != "knockout":
        return CheckResult(
            check_id="grna.position_in_cds",
            label="Cut site positioned for a knockout",
            severity=Severity.PASS,
            message=(
                f"The edit intent is {request.edit_intent}, so the knockout positioning rule "
                "(cut early in the coding sequence and not in the final exon) does not constrain "
                "this guide. No change needed. If the real intent is a knockout, set edit_intent "
                "to knockout and supply cds_region so this check can run."
            ),
            observed=f"edit intent {request.edit_intent}",
            threshold=threshold,
            citation=SECTION_8_5,
        )
    placement = context.placement
    if placement is None:
        return CheckResult(
            check_id="grna.position_in_cds",
            label="Cut site positioned for a knockout",
            severity=Severity.UNKNOWN,
            message=(
                "The cut site could not be located on the target, so its position in the coding "
                f"sequence cannot be evaluated. {context.resolved.reason}"
            ),
            threshold=threshold,
            citation=SECTION_8_5,
        )
    if request.cds_region is None:
        return CheckResult(
            check_id="grna.position_in_cds",
            label="Cut site positioned for a knockout",
            severity=Severity.UNKNOWN,
            message=(
                f"The cut site is at target position {placement.cut_site}, but no cds_region was "
                "supplied, so whether it falls in an early constitutive region cannot be "
                "evaluated. Supply cds_region, and final_exon_region and constitutive_regions if "
                "known, to evaluate this check."
            ),
            coordinates=(placement.cut_site, placement.cut_site + 1),
            observed=f"cut site at target position {placement.cut_site}",
            threshold=threshold,
            citation=SECTION_8_5,
        )

    cut = placement.cut_site
    cds_start, cds_end = request.cds_region
    cds_length = cds_end - cds_start
    coordinates = (cut, cut + 1)
    problems: list[str] = []
    remediation: list[str] = []

    if not cds_start <= cut < cds_end:
        problems.append(
            f"the cut site at target position {cut} is outside the coding sequence "
            f"({cds_start} to {cds_end})"
        )
        remediation.append("move the guide into the coding sequence")
        fraction_text = "not applicable"
    else:
        fraction = (cut - cds_start) / cds_length
        fraction_text = f"{fraction:.0%} into the coding sequence"
        if fraction > fraction_limit:
            problems.append(
                f"the cut site is {fraction:.0%} into the coding sequence, past the configured "
                f"limit of {fraction_limit:.0%}"
            )
            remediation.append(
                f"choose a guide cutting before target position "
                f"{cds_start + int(cds_length * fraction_limit)}"
            )

    if request.final_exon_region is not None:
        final_start, final_end = request.final_exon_region
        if final_start <= cut < final_end:
            problems.append(
                f"the cut site is inside the final exon ({final_start} to {final_end}), where a "
                "frameshift often escapes transcript degradation and leaves a partly functional "
                "truncated protein"
            )
            remediation.append(f"choose a guide cutting before target position {final_start}")

    if request.constitutive_regions:
        inside = any(start <= cut < end for start, end in request.constitutive_regions)
        if not inside:
            spans = ", ".join(f"{start} to {end}" for start, end in request.constitutive_regions)
            problems.append(
                f"the cut site is not inside any supplied constitutive region ({spans}), so some "
                "transcript isoforms would not be disrupted"
            )
            remediation.append("choose a guide cutting inside a constitutive region")

    if problems:
        return CheckResult(
            check_id="grna.position_in_cds",
            label="Cut site positioned for a knockout",
            severity=Severity.WARN,
            message=(
                "For a knockout, " + "; ".join(problems) + ". "
                + (" ".join(f"Option: {item}." for item in remediation))
                + " A guide placed early in a constitutive coding region gives the most reliable "
                "null allele."
            ),
            coordinates=coordinates,
            observed=f"cut site at target position {cut}, {fraction_text}",
            threshold=threshold,
            citation=SECTION_8_5,
            tier="B",
            remediation=remediation,
        )

    note = (
        ""
        if request.constitutive_regions
        else (
            " Constitutive exon spans were not supplied, so isoform coverage was not evaluated; "
            "supply constitutive_regions to check it."
        )
    )
    return CheckResult(
        check_id="grna.position_in_cds",
        label="Cut site positioned for a knockout",
        severity=Severity.PASS,
        message=(
            f"The cut site at target position {cut} is {fraction_text}, within the configured "
            f"first {fraction_limit:.0%}, and not in the final exon. No change needed.{note}"
        ),
        coordinates=coordinates,
        observed=f"cut site at target position {cut}, {fraction_text}",
        threshold=threshold,
        citation=SECTION_8_5,
    )


# ---------------------------------------------------------------------------
# 8. grna.self_targeting
# ---------------------------------------------------------------------------


def check_self_targeting(context: CheckContext) -> CheckResult:
    """The guide does not target the delivery plasmid itself. FAIL.

    A delivery plasmid always contains the spacer, because the U6 cassette
    encodes it. What matters is whether a usable PAM sits next to that copy at
    the offset the nuclease needs: a spacer followed by the scaffold is not a
    target, a spacer followed by a PAM is. So this check searches the construct
    for the spacer and then applies the nuclease geometry, which keeps it from
    flagging every design.

    The search runs here independently of the declared off-target scope,
    because section 8.6 says construct searching is always available.
    """
    request = context.request
    spec = context.spec
    thresholds = context.thresholds
    construct = request.delivery_construct_sequence
    name = request.delivery_construct_name or "the delivery construct"
    threshold = (
        f"no {spec.pam_motif} PAM adjacent to a copy of the spacer in the delivery construct, "
        f"within {thresholds.off_target_max_mismatches} mismatches"
    )
    if not construct:
        return CheckResult(
            check_id="grna.self_targeting",
            label="Guide does not target the delivery construct",
            severity=Severity.UNKNOWN,
            message=(
                "No delivery construct sequence was supplied, so whether this guide cuts its own "
                "delivery vector cannot be evaluated. Supply delivery_construct_sequence (and "
                "delivery_construct_name) to evaluate this check. A guide that cuts its own "
                "vector destroys the vector in the transfected cell."
            ),
            threshold=threshold,
            citation=SECTION_8_5,
        )

    sequence = clean_sequence(construct)
    spacer = context.spacer
    exact: list[tuple[int, int]] = []
    near: list[tuple[int, int, int, int]] = []
    for hit in find_with_mismatches(
        sequence,
        spacer,
        max_mismatches=thresholds.off_target_max_mismatches,
        both_strands=True,
    ):
        pam_result = pam_at(sequence, spec, hit.strand, hit.start, len(spacer))
        if pam_result is None:
            continue
        _, matches, _ = pam_result
        if not matches:
            continue
        if hit.mismatches == 0:
            exact.append((hit.start, hit.strand))
        else:
            window = sequence[hit.start : hit.end]
            protospacer = window if hit.strand == 1 else reverse_complement(window)
            seed = seed_positions(spec, len(spacer), thresholds.seed_region_nt)
            seed_mismatches = sum(
                1
                for index, (a, b) in enumerate(zip(spacer, protospacer))
                if a != b and index + 1 in seed
            )
            near.append((hit.start, hit.strand, hit.mismatches, seed_mismatches))

    if exact:
        described = ", ".join(
            f"position {start} on the {'forward' if strand == 1 else 'reverse'} strand"
            for start, strand in exact
        )
        return CheckResult(
            check_id="grna.self_targeting",
            label="Guide does not target the delivery construct",
            severity=Severity.FAIL,
            message=(
                f"This guide targets its own delivery construct {name}: the spacer occurs there "
                f"with a valid {spec.pam_motif} PAM at the correct offset at {described}. The "
                "nuclease will cut the vector it was delivered on, which stops expression and can "
                "integrate vector fragments. Fix it by removing or silently mutating the PAM "
                "adjacent to the spacer copy in the construct, or by choosing a different guide, "
                "or by delivering the nuclease and the guide as ribonucleoprotein instead of from "
                "this plasmid."
            ),
            observed=f"{len(exact)} exact self-target site(s) with a valid PAM",
            threshold=threshold,
            citation=SECTION_8_5,
            remediation=[
                f"mutate the PAM next to the spacer copy at construct position {start}"
                for start, _ in exact
            ],
        )

    clean_seed = [item for item in near if item[3] == 0]
    if clean_seed:
        described = ", ".join(
            f"position {start} on the {'forward' if strand == 1 else 'reverse'} strand with "
            f"{mismatches} mismatch(es), none in the seed"
            for start, strand, mismatches, _ in clean_seed
        )
        return CheckResult(
            check_id="grna.self_targeting",
            label="Guide does not target the delivery construct",
            severity=Severity.WARN,
            message=(
                f"The delivery construct {name} carries a near match to this spacer with a valid "
                f"{spec.pam_motif} PAM at {described}. The seed region "
                f"{seed_label(spec, len(spacer), thresholds.seed_region_nt)} is fully matched, and "
                "the construct is present at high copy number after transfection, so some vector "
                "cutting is plausible. Prefer a guide with no construct match, or mutate the PAM "
                "at that construct position."
            ),
            observed=f"{len(clean_seed)} near self-target site(s) with a matched seed",
            threshold=threshold,
            citation=SECTION_8_5,
            tier="B",
        )

    return CheckResult(
        check_id="grna.self_targeting",
        label="Guide does not target the delivery construct",
        severity=Severity.PASS,
        message=(
            f"The delivery construct {name} ({len(sequence)} bp) carries no copy of this spacer "
            f"with a valid {spec.pam_motif} PAM at the correct offset, within "
            f"{thresholds.off_target_max_mismatches} mismatches. The guide will not cut its own "
            "vector. No change needed."
        ),
        observed=f"no self-target site in {len(sequence)} bp",
        threshold=threshold,
        citation=SECTION_8_5,
    )


# ---------------------------------------------------------------------------
# 9. grna.restriction_in_spacer
# ---------------------------------------------------------------------------


def check_restriction_in_spacer(context: CheckContext) -> CheckResult:
    """The spacer does not contain a site needed for the cloning strategy. WARN."""
    vector = context.vector
    enzyme = vector.digest_enzyme
    if enzyme is None:
        return CheckResult(
            check_id="grna.restriction_in_spacer",
            label="Spacer free of the cloning enzyme site",
            severity=Severity.UNKNOWN,
            message=(
                f"The chosen vector {vector.name} ({vector.accession}) does not declare a Type IIS "
                "digest enzyme in its record, so whether the spacer contains the site the cloning "
                "strategy needs cannot be evaluated. Name the enzyme used by that vector's "
                "protocol, or choose a vector whose record declares one, to evaluate this check."
            ),
            threshold="spacer must not contain the cloning enzyme recognition site",
            citation=APPENDIX_D,
        )
    site = CLONING_ENZYME_SITES.get(enzyme)
    if site is None:
        known = ", ".join(sorted(CLONING_ENZYME_SITES))
        return CheckResult(
            check_id="grna.restriction_in_spacer",
            label="Spacer free of the cloning enzyme site",
            severity=Severity.UNKNOWN,
            message=(
                f"The chosen vector {vector.name} is digested with {enzyme}, whose recognition "
                f"sequence is not in the Appendix D table (it holds {known}). Add {enzyme} to the "
                "enzyme table with its recognition sequence and a citation, or choose a vector "
                "that uses a listed enzyme, to evaluate this check."
            ),
            threshold="spacer must not contain the cloning enzyme recognition site",
            citation=APPENDIX_D,
        )
    threshold = f"{enzyme} site {site} must not appear in the spacer, on either strand"
    hits = find_both_strands(context.spacer, site)
    if not hits:
        return CheckResult(
            check_id="grna.restriction_in_spacer",
            label="Spacer free of the cloning enzyme site",
            severity=Severity.PASS,
            message=(
                f"The spacer contains no {enzyme} site ({site}) on either strand, so it survives "
                f"the digest used to clone into {vector.name} ({vector.accession}). "
                "No change needed."
            ),
            observed=f"{enzyme} site absent",
            threshold=threshold,
            citation=APPENDIX_D,
        )
    described = ", ".join(
        f"spacer positions {hit.start + 1} to {hit.end} on the "
        f"{'forward' if hit.strand == 1 else 'reverse'} strand"
        for hit in hits
    )
    alternatives = sorted(
        other.vector_id
        for other in _vectors_for(context.request.nuclease)
        if other.digest_enzyme
        and other.digest_enzyme != enzyme
        and not find_both_strands(context.spacer, CLONING_ENZYME_SITES.get(other.digest_enzyme, "A"))
    )
    suggestion = (
        f" A vector using a different enzyme would avoid it: {', '.join(alternatives)}."
        if alternatives
        else ""
    )
    return CheckResult(
        check_id="grna.restriction_in_spacer",
        label="Spacer free of the cloning enzyme site",
        severity=Severity.WARN,
        message=(
            f"The spacer contains the {enzyme} recognition site {site} at {described}. "
            f"{enzyme} is the enzyme that opens {vector.name} ({vector.accession}), so the "
            "annealed oligo duplex will be cut internally during the ligation and the clone will "
            f"fail or rearrange. Choose a different guide in the same region.{suggestion} "
            "Appendix D requires both strands to be checked because the site is not palindromic, "
            "and both were."
        ),
        observed=f"{enzyme} site at {described}",
        threshold=threshold,
        citation=APPENDIX_D,
        tier="B",
        remediation=[f"avoid the {enzyme} site {site} in the spacer"] + [
            f"alternative vector {vector_id}" for vector_id in alternatives
        ],
    )


def _vectors_for(nuclease: str) -> list[CloningVector]:
    from .vectors import CLONING_VECTORS

    return [
        vector
        for _, vector in sorted(CLONING_VECTORS.items())
        if nuclease in vector.nucleases
    ]


# ---------------------------------------------------------------------------
# Section 8.6: off-target hits in the declared space
# ---------------------------------------------------------------------------


def check_off_target_hits(context: CheckContext) -> CheckResult:
    """Off-target severity for the declared space (section 8.6).

    FAIL on a site with very few mismatches and none of them in the seed, WARN
    on any other enumerated site, PASS when the searched space is clean, and
    UNKNOWN when no search was performed. Every message states the searched
    space verbatim, so the verdict can never be read as broader than the search.
    """
    summary = context.off_target
    thresholds = context.thresholds
    spec = context.spec
    seed = seed_label(spec, len(context.spacer), thresholds.seed_region_nt)
    threshold = (
        f"no site within {thresholds.off_target_fail_max_mismatches} mismatches carrying at most "
        f"{thresholds.off_target_fail_max_seed_mismatches} seed mismatch(es); searched to "
        f"{thresholds.off_target_max_mismatches} mismatches; seed is {seed}"
    )
    if not summary.searched:
        return CheckResult(
            check_id="grna.off_target_hits",
            label="Off-target sites in the searched space",
            severity=Severity.UNKNOWN,
            message=(
                f"{summary.space_statement} No off-target verdict can be given for this guide. "
                + " ".join(summary.notes)
            ),
            observed="no search performed",
            threshold=threshold,
            citation=SECTION_8_6,
        )

    off_targets = [hit for hit in summary.hits if not hit.is_on_target]
    failing = [
        hit
        for hit in off_targets
        if hit.mismatches <= thresholds.off_target_fail_max_mismatches
        and hit.seed_mismatches <= thresholds.off_target_fail_max_seed_mismatches
    ]
    if failing:
        worst = min(failing, key=lambda hit: (hit.mismatches, hit.start))
        described = "; ".join(
            f"{hit.source_label} position {hit.start} on the "
            f"{'forward' if hit.strand == 1 else 'reverse'} strand, {hit.mismatches} mismatch(es) "
            f"at spacer position(s) {', '.join(str(p) for p in hit.mismatch_positions) or 'none'}, "
            f"{hit.seed_mismatches} of them in the seed, PAM {hit.pam}"
            for hit in failing[:5]
        )
        return CheckResult(
            check_id="grna.off_target_hits",
            label="Off-target sites in the searched space",
            severity=Severity.FAIL,
            message=(
                f"{summary.space_statement} It contains {len(failing)} site(s) within "
                f"{thresholds.off_target_fail_max_mismatches} mismatches whose seed region {seed} "
                f"is fully matched: {described}. Mismatches in the seed are what stop binding, so "
                "a site with a clean seed and this few mismatches is likely to be cut. Choose a "
                f"different guide (the closest site here has {worst.mismatches} mismatch(es)), or "
                "move the mismatches into the seed by shifting the guide, or validate this site "
                "directly by amplicon sequencing before relying on the guide."
            ),
            coordinates=(worst.start, worst.end),
            observed=f"{len(failing)} near site(s), closest at {worst.mismatches} mismatch(es)",
            threshold=threshold,
            citation=SECTION_8_6,
            remediation=[
                f"near off-target in {hit.source_label} at {hit.start}, {hit.mismatches} mismatches"
                for hit in failing[:5]
            ],
        )
    if off_targets:
        closest = min(off_targets, key=lambda hit: (hit.mismatches, hit.start))
        return CheckResult(
            check_id="grna.off_target_hits",
            label="Off-target sites in the searched space",
            severity=Severity.WARN,
            message=(
                f"{summary.space_statement} It contains {len(off_targets)} site(s) within "
                f"{thresholds.off_target_max_mismatches} mismatches, the closest in "
                f"{closest.source_label} at position {closest.start} with {closest.mismatches} "
                f"mismatch(es), {closest.seed_mismatches} of them inside the seed {seed}. Seed "
                "mismatches make cutting much less likely, so these are moderate rather than "
                "disqualifying. Keep the guide and check these sites by amplicon sequencing, or "
                "pick a guide with no site in the searched space."
            ),
            coordinates=(closest.start, closest.end),
            observed=f"{len(off_targets)} moderate site(s), closest at {closest.mismatches} mismatch(es)",
            threshold=threshold,
            citation=SECTION_8_6,
            tier="B",
        )
    return CheckResult(
        check_id="grna.off_target_hits",
        label="Off-target sites in the searched space",
        severity=Severity.PASS,
        message=(
            f"{summary.space_statement} No other site in it matches this spacer within "
            f"{thresholds.off_target_max_mismatches} mismatches next to a valid PAM. No change "
            "needed inside this space. Sites outside it were not examined."
        ),
        observed=f"0 off-target sites in {summary.searched_bases} bp",
        threshold=threshold,
        citation=SECTION_8_6,
    )


ALL_CHECKS = (
    check_pam_valid,
    check_spacer_length,
    check_gc_content,
    check_u6_terminator,
    check_homopolymer,
    check_self_complementarity,
    check_position_in_cds,
    check_self_targeting,
    check_restriction_in_spacer,
    check_off_target_hits,
)
"""Section 8.5's nine checks in table order, then the section 8.6 off-target
check. Report order is this order, which keeps output deterministic."""

SECTION_8_5_CHECK_IDS = (
    "grna.pam_valid",
    "grna.spacer_length",
    "grna.gc_content",
    "grna.u6_terminator",
    "grna.homopolymer",
    "grna.self_complementarity",
    "grna.position_in_cds",
    "grna.self_targeting",
    "grna.restriction_in_spacer",
)
"""The nine `check_id` values of the section 8.5 table, spelled as that table
spells them. A test asserts every run reports all nine."""

OFF_TARGET_CHECK_ID = "grna.off_target_hits"
