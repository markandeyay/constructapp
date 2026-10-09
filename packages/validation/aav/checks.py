"""The fourteen AAV checks of section 6.4.

Section 6.4 is a closed list: "These are the checks. Implement all of them. Do
not add an invented one." `CHECK_IDS` below is that list, in that order, with
those exact ids. There is no fifteenth check, and remediation is not one: it
rides on `aav.packaging_limit` and `aav.sc_capacity` in `message` and in
`remediation`, which is what sections 6.5 and 6.6 ask for.

Conventions every check in this module follows:

* A check that cannot be evaluated returns UNKNOWN with a reason in `message`
  (section 3.3 constraint 4). It never returns PASS by default, and it never
  returns FAIL for something another check already owns. For example, if the
  5' ITR is missing, `aav.itr_present_both` FAILs and `aav.itr_orientation`
  returns UNKNOWN, because orientation genuinely cannot be measured with one
  ITR and a second FAIL would only obscure the real fault.
* Severity on violation is exactly what the section 6.4 table specifies. The
  WARN checks stay WARN even when the finding is ugly, because section 3.4 is
  explicit that real constructs carry intentional architecture that a naive
  checker reads as an error.
* `tier` marks the section 3.4 tier a result belongs to: "A" on PASS
  (strict clean), "B" on WARN (accepted with caveats, surfaced and explained),
  and None on FAIL and UNKNOWN, which are neither.
* Every message states the measurement, the threshold, and what to do about it
  (section 5.4 rule 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.core.part_registry import PartCategory, PartRecord, list_parts
from packages.core.schemas.aav import (
    FUNCTIONAL_ORDER,
    REQUIRED_ROLES,
    AAVDesign,
    CassetteElementRole,
    LayoutElement,
    RemediationReport,
)
from packages.core.schemas.capability import CheckResult, Severity
from packages.core.sequence import (
    STANDARD_CODE,
    direct_repeats,
    find_exact,
    homopolymer_runs,
    matches_iupac,
    translate,
)

from .constants import CHECK_CITATIONS, AAVThresholds, DEFAULT_THRESHOLDS
from .itr import (
    ItrReference,
    UnknownSerotype,
    best_itr_match,
    internal_itr_motif_hits,
    orientation_of_pair,
    serotype_itr_references,
)
from .remediation import build_remediation, remediation_entries, render_remediation_message

# The closed section 6.4 list, in section 6.4 order.
CHECK_IDS: tuple[str, ...] = (
    "aav.packaging_limit",
    "aav.itr_present_both",
    "aav.itr_orientation",
    "aav.required_elements",
    "aav.element_order",
    "aav.cds_integrity",
    "aav.sc_capacity",
    "aav.promoter_tissue_match",
    "aav.internal_repeats",
    "aav.homopolymer_runs",
    "aav.kozak_context",
    "aav.polya_present_functional",
    "aav.minimum_genome_size",
    "aav.itr_internal_sites",
)

CHECK_LABELS: dict[str, str] = {
    "aav.packaging_limit": "Packaging limit",
    "aav.itr_present_both": "Both ITRs present and matched",
    "aav.itr_orientation": "ITR orientation",
    "aav.required_elements": "Required elements present",
    "aav.element_order": "Functional element order",
    "aav.cds_integrity": "Coding sequence integrity",
    "aav.sc_capacity": "Self complementary capacity",
    "aav.promoter_tissue_match": "Promoter and target tissue match",
    "aav.internal_repeats": "Internal direct repeats",
    "aav.homopolymer_runs": "Homopolymer runs",
    "aav.kozak_context": "Kozak initiation context",
    "aav.polya_present_functional": "Functional polyadenylation signal",
    "aav.minimum_genome_size": "Minimum genome size",
    "aav.itr_internal_sites": "Internal ITR motifs",
}


def _tier(severity: Severity) -> str | None:
    if severity is Severity.PASS:
        return "A"
    if severity is Severity.WARN:
        return "B"
    return None


def result(
    check_id: str,
    severity: Severity,
    message: str,
    *,
    observed: str | None = None,
    threshold: str | None = None,
    coordinates: tuple[int, int] | None = None,
    remediation: list[str] | None = None,
) -> CheckResult:
    """Build one `CheckResult`, filling the label, citation and tier."""
    return CheckResult(
        check_id=check_id,
        label=CHECK_LABELS[check_id],
        severity=severity,
        message=message,
        observed=observed,
        threshold=threshold,
        coordinates=coordinates,
        citation=CHECK_CITATIONS[check_id],
        tier=_tier(severity),
        remediation=remediation,
    )


@dataclass
class CheckContext:
    """Everything the fourteen checks share, computed once per validation run.

    Pure data over the design. No database, no network, no model (section 3.3
    constraint 3 and the environment note that validators are pure functions
    over sequences).
    """

    design: AAVDesign
    thresholds: AAVThresholds
    parts: dict[str, PartRecord] = field(default_factory=dict)
    cassette: str = ""
    layout: tuple[LayoutElement, ...] = ()
    itr_reference: ItrReference | None = None
    itr_error: str | None = None
    remediation_ss: RemediationReport | None = None
    remediation_sc: RemediationReport | None = None

    @classmethod
    def build(
        cls,
        design: AAVDesign,
        thresholds: AAVThresholds = DEFAULT_THRESHOLDS,
        parts: list[PartRecord] | None = None,
    ) -> CheckContext:
        records = list(parts if parts is not None else list_parts())
        registry = {record.id: record for record in records}
        reference: ItrReference | None = None
        error: str | None = None
        try:
            reference = serotype_itr_references(design.serotype, thresholds, [r for r in records if r.id.startswith("itr.")])
        except UnknownSerotype as exc:
            error = str(exc)
        return cls(
            design=design,
            thresholds=thresholds,
            parts=registry,
            cassette=design.cassette_sequence,
            layout=design.layout(),
            itr_reference=reference,
            itr_error=error,
            remediation_ss=build_remediation(design, thresholds, records, self_complementary=False),
            remediation_sc=build_remediation(design, thresholds, records, self_complementary=True),
        )

    def element_at(self, role: CassetteElementRole) -> LayoutElement | None:
        return next((item for item in self.layout if item.role == role), None)

    def count_role(self, role: CassetteElementRole) -> int:
        return sum(1 for item in self.layout if item.role == role)


# ---------------------------------------------------------------------------
# 1. aav.packaging_limit
# ---------------------------------------------------------------------------


def _band_severity(total: int, target: int, soft: int) -> Severity:
    """Section 6.5 banding: at or under target PASS, at or under soft WARN, else FAIL.

    The hard limit does not change the severity, it changes the message. The
    section 6.6 worked example is a 5,048 bp cassette against a 4,700 bp target
    and a 4,900 bp soft limit: it FAILs while still sitting 152 bp under the
    5,200 bp hard ceiling, which is exactly this banding.
    """
    if total <= target:
        return Severity.PASS
    if total <= soft:
        return Severity.WARN
    return Severity.FAIL


def check_packaging_limit(context: CheckContext) -> CheckResult:
    """Check 1: total length, 5' ITR start through 3' ITR end, against the band.

    Always measured against the single stranded band, which is the physical
    capsid ceiling for a conventional recombinant genome. The halved self
    complementary capacity is check 7's job, so that an scAAV cassette sized
    legally for ssAAV reports exactly one failure, on the check that names the
    reason.
    """
    design = context.design
    total = design.total_bp
    target, soft, hard = context.thresholds.band(False)
    severity = _band_severity(total, target, soft)
    report = context.remediation_ss
    assert report is not None  # built in CheckContext.build

    if severity is Severity.PASS:
        message = (
            f"Cassette is {total:,} bp, which is {target - total:,} bp inside the {target:,} bp single "
            f"stranded packaging target. No length change is needed. Headroom to the {soft:,} bp soft "
            f"limit is {soft - total:,} bp, so a transgene up to {report.max_transgene_bp:,} bp of coding "
            f"sequence would still fit with the current regulatory elements plus every available saving."
        )
        remediation = None
    elif severity is Severity.WARN:
        message = (
            render_remediation_message(report, "single stranded")
            + " The design is over the target but at or under the soft limit, so expect reduced titer and "
            "some truncated species rather than a packaging failure. Applying one of the changes below "
            "removes that risk."
        )
        remediation = remediation_entries(report)
    else:
        message = (
            render_remediation_message(report, "single stranded")
            + f" This is a failure rather than a warning because the cassette is above the {soft:,} bp "
            f"soft limit"
            + (f", and above the {hard:,} bp hard ceiling as well." if total > hard else ".")
        )
        remediation = remediation_entries(report)

    return result(
        "aav.packaging_limit",
        severity,
        message,
        observed=f"{total:,} bp",
        threshold=f"target {target:,} bp, soft limit {soft:,} bp, hard limit {hard:,} bp",
        coordinates=(0, total),
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# 2. aav.itr_present_both
# ---------------------------------------------------------------------------


def check_itr_present_both(context: CheckContext) -> CheckResult:
    """Check 2: both ITRs present and matched to the serotype reference.

    Each ITR is compared with the serotype's reference ITRs **in both
    orientations**, and the best match is taken. It is deliberately not
    compared with the reverse complement of the other ITR in the design: the
    AAV2 left ITR reads core plus D and the right reads reverse complement of D
    plus the same core, and the hairpin core is only 85.9 percent identical to
    its own reverse complement, so that comparison scores 88.3 percent on a
    perfectly correct cassette and would fail every design against the
    95 percent threshold. Orientation is check 3's job and is decided by the
    D element, not by this identity.
    """
    design = context.design
    threshold = context.thresholds.itr_identity_threshold
    left = design.first_with_role(CassetteElementRole.ITR_5)
    right = design.first_with_role(CassetteElementRole.ITR_3)
    missing = [
        label
        for label, element in (("5' ITR", left), ("3' ITR", right))
        if element is None
    ]
    if missing:
        return result(
            "aav.itr_present_both",
            Severity.FAIL,
            f"{' and '.join(missing)} absent from the cassette. The ITRs are the only viral sequence a "
            f"recombinant genome retains and they are required in cis for replication and packaging, so a "
            f"cassette without both will not package at all. Add the serotype ITR pair from the part "
            f"registry: for {design.serotype} that is itr.{design.serotype.lower()}_itr_left at the 5' end "
            f"and itr.{design.serotype.lower()}_itr_right at the 3' end.",
            observed=f"{2 - len(missing)} of 2 ITRs present",
            threshold="2 ITRs required",
        )
    if context.itr_reference is None:
        return result(
            "aav.itr_present_both",
            Severity.UNKNOWN,
            f"Both ITR elements are present but their identity could not be measured: {context.itr_error}",
            observed="2 of 2 ITRs present, identity not measured",
            threshold=f"{threshold:.0%} identity to the serotype reference",
        )

    reference = context.itr_reference
    assert left is not None and right is not None
    matches = {
        "5' ITR": (left, best_itr_match(left.sequence, reference)),
        "3' ITR": (right, best_itr_match(right.sequence, reference)),
    }
    failures = [name for name, (_, match) in matches.items() if match.identity < threshold]
    observed = "; ".join(f"{name} {match.describe()}" for name, (_, match) in matches.items())
    duplicate_note = ""
    for role, label in ((CassetteElementRole.ITR_5, "5' ITR"), (CassetteElementRole.ITR_3, "3' ITR")):
        count = context.count_role(role)
        if count > 1:
            duplicate_note += (
                f" The cassette carries {count} elements in the {label} role; the first was measured. "
                f"Remove the extra copies."
            )
    if failures:
        detail = "; ".join(
            f"{name} reaches only {matches[name][1].identity:.1%} (best reference "
            f"{matches[name][1].reference_id}, {matches[name][1].orientation_label})"
            for name in failures
        )
        return result(
            "aav.itr_present_both",
            Severity.FAIL,
            f"{detail}, below the {threshold:.0%} identity required against the {design.serotype} reference. "
            f"Replace the divergent ITR with the registry record ({reference.left.id} for the 5' end, "
            f"{reference.right.id} for the 3' end) rather than editing it; the terminal repeat is the "
            f"packaging signal and partial copies reduce or abolish vector yield.{duplicate_note}",
            observed=observed,
            threshold=f"{threshold:.0%} identity to the serotype reference",
        )
    return result(
        "aav.itr_present_both",
        Severity.PASS,
        f"Both ITRs are present and match the {design.serotype} reference above the {threshold:.0%} "
        f"threshold ({observed}). Each ITR was compared with the serotype reference records in both "
        f"orientations, not with the other ITR, because the left ITR reads core plus D and the right reads "
        f"reverse complement of D plus core, so that comparison scores only 88.3 percent even when both "
        f"ITRs are correct. Keep the registry records as they are."
        + duplicate_note,
        observed=observed,
        threshold=f"{threshold:.0%} identity to the serotype reference",
    )


# ---------------------------------------------------------------------------
# 3. aav.itr_orientation
# ---------------------------------------------------------------------------


def check_itr_orientation(context: CheckContext) -> CheckResult:
    """Check 3: the two ITRs are inverted relative to each other, not tandem.

    Decided from the D element, which is identical between the flip and flop
    configurations, so the flip and flop difference in the reference records
    cannot produce a false verdict. See `packages.validation.aav.itr` for the
    method and for the fallback.

    Four outcomes, all on this one check id, because section 6.4 fixes the check
    list at fourteen and this is the check whose subject ITR orientation is:

    * PASS, an inverted pair with the D sequences facing the transgene.
    * WARN, an inverted pair with the D sequences facing the cassette ends.
      Inverted, so not the tandem failure, but not a functional genome either,
      and it is the one arrangement a user could otherwise take into production
      on the strength of a pass.
    * FAIL, a tandem pair.
    * UNKNOWN, fewer than two ITRs, no serotype reference, or an arrangement the
      D element anchor and the identity margin fallback both leave undecided.
    """
    design = context.design
    left = design.first_with_role(CassetteElementRole.ITR_5)
    right = design.first_with_role(CassetteElementRole.ITR_3)
    if left is None or right is None:
        return result(
            "aav.itr_orientation",
            Severity.UNKNOWN,
            "Orientation cannot be evaluated because the cassette does not carry both ITRs. Add the "
            "missing ITR, which aav.itr_present_both reports, and this check will evaluate.",
            observed="fewer than 2 ITRs",
            threshold="inverted arrangement required",
        )
    if context.itr_reference is None:
        return result(
            "aav.itr_orientation",
            Severity.UNKNOWN,
            f"Orientation cannot be evaluated: {context.itr_error}",
            observed="serotype reference unavailable",
            threshold="inverted arrangement required",
        )
    verdict = orientation_of_pair(left.sequence, right.sequence, context.itr_reference, context.thresholds)
    observed = f"{verdict.arrangement} ({verdict.method})"
    if verdict.arrangement == "inverted" and not verdict.canonical:
        return result(
            "aav.itr_orientation",
            Severity.WARN,
            f"The two ITRs are inverted relative to each other, but they are oriented so that the D "
            f"sequences face outward, toward the cassette ends, instead of inward toward the transgene: "
            f"{verdict.detail}. This is not the functional arrangement. The D sequence has to face the "
            f"transgene for the terminal resolution site to be cut on the correct side of the hairpin, so a "
            f"D outward pair does not resolve correctly, and a cassette built this way will not give "
            f"functional vector even though its two ITRs are inverted rather than in tandem. Do not take "
            f"this design into production as it stands. To fix, either reverse complement the whole "
            f"cassette, which swaps the two ITRs as well as their sequences and so restores the inward "
            f"facing arrangement, or replace both ITRs with the registry records: "
            f"{context.itr_reference.left.id} at the 5' end and {context.itr_reference.right.id} at the "
            f"3' end, which are already in the correct orientation. This is a warning rather than a failure "
            f"because the pair is inverted and this check's failure condition is a tandem pair; treat it as "
            f"a defect to correct, not as a caveat to record.",
            observed=f"inverted but D outward ({verdict.method})",
            threshold="inverted arrangement required",
        )
    if verdict.arrangement == "inverted":
        return result(
            "aav.itr_orientation",
            Severity.PASS,
            f"The ITRs are inverted relative to each other, which is the required arrangement: "
            f"{verdict.detail}. No change is needed.",
            observed=observed,
            threshold="inverted arrangement required",
        )
    if verdict.arrangement == "tandem":
        return result(
            "aav.itr_orientation",
            Severity.FAIL,
            f"The two ITRs are in tandem rather than inverted: {verdict.detail}. Reverse complement the "
            f"3' ITR, or replace it with {context.itr_reference.right.id} from the part registry, which is "
            f"already in the correct orientation for the 3' end of a cassette.",
            observed=observed,
            threshold="inverted arrangement required",
        )
    return result(
        "aav.itr_orientation",
        Severity.UNKNOWN,
        f"The arrangement of the two ITRs could not be determined: {verdict.detail}. Replace both ITRs with "
        f"the registry records ({context.itr_reference.left.id} and {context.itr_reference.right.id}) so "
        f"the D element anchor can be located, then revalidate.",
        observed=observed,
        threshold="inverted arrangement required",
    )


# ---------------------------------------------------------------------------
# 4. aav.required_elements
# ---------------------------------------------------------------------------


def check_required_elements(context: CheckContext) -> CheckResult:
    """Check 4: promoter, transgene CDS and polyA all present."""
    design = context.design
    present = {CassetteElementRole(element.role) for element in design.elements}
    missing = [role for role in REQUIRED_ROLES if role not in present]
    observed = ", ".join(sorted(role.value for role in present))
    if missing:
        hints = {
            CassetteElementRole.PROMOTER: "add a promoter from data/parts/promoter (for example promoter.efs at 212 bp when capacity is tight)",
            CassetteElementRole.CDS: "add the transgene coding sequence; supply it as transgene_sequence on the request",
            CassetteElementRole.POLYA: "add a polyA from data/parts/polya (polya.sv40 at 135 bp is the smaller of the two)",
        }
        return result(
            "aav.required_elements",
            Severity.FAIL,
            f"The cassette is missing {', '.join(role.value for role in missing)}. Without all three of "
            f"promoter, coding sequence and polyA the transcript is not made, not translated or not "
            f"stabilised, so the vector cannot express. To fix: "
            + "; ".join(hints[role] for role in missing)
            + ".",
            observed=f"present: {observed}",
            threshold="promoter, cds and polya all required",
        )
    return result(
        "aav.required_elements",
        Severity.PASS,
        f"Promoter, coding sequence and polyA are all present ({observed}). No change is needed.",
        observed=f"present: {observed}",
        threshold="promoter, cds and polya all required",
    )


# ---------------------------------------------------------------------------
# 5. aav.element_order
# ---------------------------------------------------------------------------


def check_element_order(context: CheckContext) -> CheckResult:
    """Check 5: elements appear in the section 6.2 functional order.

    `5' ITR -> [enhancer] -> promoter -> [intron] -> transgene CDS -> [WPRE]
    -> polyA -> 3' ITR`. Two elements in the same role are not an ordering
    violation, so a dual promoter cassette is not failed here; it is reported
    in the message and left to the reader.
    """
    canonical = " -> ".join(role.value for role in sorted(FUNCTIONAL_ORDER, key=FUNCTIONAL_ORDER.__getitem__))
    ranks = [(item, FUNCTIONAL_ORDER[CassetteElementRole(item.role)]) for item in context.layout]
    observed = " -> ".join(CassetteElementRole(item.role).value for item in context.layout)
    for index in range(1, len(ranks)):
        previous, previous_rank = ranks[index - 1]
        current, current_rank = ranks[index]
        if current_rank < previous_rank:
            return result(
                "aav.element_order",
                Severity.FAIL,
                f"Element {index + 1} ({CassetteElementRole(current.role).value}, {current.name}) appears "
                f"after element {index} ({CassetteElementRole(previous.role).value}, {previous.name}), which "
                f"inverts the functional order. The order must be {canonical}. Observed order: {observed}. "
                f"Move the {CassetteElementRole(current.role).value} element before the "
                f"{CassetteElementRole(previous.role).value} element and revalidate.",
                observed=observed,
                threshold=canonical,
                coordinates=(current.start, current.end),
            )
    duplicates = sorted(
        {
            CassetteElementRole(item.role).value
            for item in context.layout
            if context.count_role(CassetteElementRole(item.role)) > 1
        }
    )
    note = (
        f" Note that the cassette carries more than one element in these roles: {', '.join(duplicates)}. "
        f"That is not an ordering error, but confirm it is intentional."
        if duplicates
        else ""
    )
    return result(
        "aav.element_order",
        Severity.PASS,
        f"Elements appear in the required functional order: {observed}. No change is needed.{note}",
        observed=observed,
        threshold=canonical,
    )


# ---------------------------------------------------------------------------
# 6. aav.cds_integrity
# ---------------------------------------------------------------------------


def check_cds_integrity(context: CheckContext) -> CheckResult:
    """Check 6: ATG start, in-frame stop, length divisible by 3, no premature stop."""
    cds_layout = context.element_at(CassetteElementRole.CDS)
    if cds_layout is None:
        return result(
            "aav.cds_integrity",
            Severity.UNKNOWN,
            "There is no coding sequence element to check. Supply the transgene coding sequence, which "
            "aav.required_elements reports as missing, and this check will evaluate.",
            observed="no cds element",
            threshold="ATG start, length divisible by 3, single in-frame stop at the 3' end",
        )
    sequence = context.design.elements[cds_layout.index].sequence
    length = len(sequence)
    problems: list[str] = []
    fixes: list[str] = []
    if not sequence.startswith("ATG"):
        problems.append(f"it starts with {sequence[:3]} rather than ATG")
        fixes.append("prepend the initiator ATG or trim the 5' bases that precede it")
    if length % 3 != 0:
        problems.append(f"its length {length:,} bp is not divisible by 3 (remainder {length % 3})")
        fixes.append(
            f"add {3 - length % 3} base(s) or remove {length % 3} base(s) so the reading frame closes"
        )
    in_frame = sequence[: length - length % 3]
    protein = translate(in_frame, STANDARD_CODE) if in_frame else ""
    stops = [index for index, residue in enumerate(protein) if residue == "*"]
    if not stops:
        problems.append("it has no in-frame stop codon")
        fixes.append("append an in-frame stop codon (TAA, TAG or TGA)")
    else:
        if stops[-1] != len(protein) - 1:
            problems.append(
                f"its last in-frame stop is at codon {stops[-1] + 1} of {len(protein)}, so coding sequence "
                f"continues past it"
            )
            fixes.append("trim the sequence to end at the stop codon")
        premature = [index for index in stops if index != len(protein) - 1]
        if premature:
            first = premature[0]
            problems.append(
                f"it carries {len(premature)} premature in-frame stop codon(s), the first at codon "
                f"{first + 1} of {len(protein)} (cassette position {cds_layout.start + first * 3 + 1:,})"
            )
            fixes.append(
                f"correct the codon at position {cds_layout.start + first * 3 + 1:,} of the cassette; a "
                f"premature stop truncates the protein and the vector will express a non-functional product"
            )
    observed = f"{length:,} bp, {len(protein)} codons, {len(stops)} in-frame stop(s)"
    threshold = "ATG start, length divisible by 3, single in-frame stop at the 3' end"
    if problems:
        return result(
            "aav.cds_integrity",
            Severity.FAIL,
            f"The coding sequence for {context.design.transgene_name} is not a clean open reading frame: "
            + "; ".join(problems)
            + ". To fix: "
            + "; ".join(fixes)
            + ".",
            observed=observed,
            threshold=threshold,
            coordinates=(cds_layout.start, cds_layout.end),
        )
    return result(
        "aav.cds_integrity",
        Severity.PASS,
        f"The coding sequence for {context.design.transgene_name} is a clean open reading frame: "
        f"{length:,} bp, divisible by 3, ATG start, a single in-frame stop at the 3' end, and "
        f"{len(protein) - 1} coding codons. No change is needed.",
        observed=observed,
        threshold=threshold,
        coordinates=(cds_layout.start, cds_layout.end),
    )


# ---------------------------------------------------------------------------
# 7. aav.sc_capacity
# ---------------------------------------------------------------------------


def check_sc_capacity(context: CheckContext) -> CheckResult:
    """Check 7: when `self_complementary` is set, the halved limit is applied.

    A self complementary genome is an inverted repeat that self anneals, so the
    packaged DNA is effectively the cassette twice over and usable capacity is
    halved. When the design is not self complementary this check reports PASS
    and says which band was applied instead, so the reader can see that the
    halved limit was considered and correctly not used.
    """
    design = context.design
    total = design.total_bp
    sc_target, sc_soft, sc_hard = context.thresholds.band(True)
    ss_target, _ss_soft, _ss_hard = context.thresholds.band(False)
    threshold = f"target {sc_target:,} bp, soft limit {sc_soft:,} bp, hard limit {sc_hard:,} bp"
    if not design.self_complementary:
        return result(
            "aav.sc_capacity",
            Severity.PASS,
            f"The design is single stranded, so the halved self complementary capacity does not apply and "
            f"the {ss_target:,} bp single stranded target was used by aav.packaging_limit instead. If you "
            f"switch to self complementary, the cassette would be measured against {sc_target:,} bp, and at "
            f"{total:,} bp it would be "
            + (
                f"{total - sc_target:,} bp over that target, so the cassette would have to shrink first."
                if total > sc_target
                else f"{sc_target - total:,} bp inside that target, so the switch would need no length change."
            )
            + " No change is needed for the current single stranded design.",
            observed=f"{total:,} bp, single stranded",
            threshold=threshold,
        )
    severity = _band_severity(total, sc_target, sc_soft)
    report = context.remediation_sc
    assert report is not None
    if severity is Severity.PASS:
        message = (
            f"Self complementary design: the cassette is {total:,} bp against the halved "
            f"{sc_target:,} bp target, {sc_target - total:,} bp inside it. The packaged genome is the "
            f"cassette duplicated, so this is the limit that matters here. No change is needed."
        )
        remediation = None
    elif severity is Severity.WARN:
        message = (
            "Self complementary design, so the halved capacity applies: the packaged genome is the "
            "cassette duplicated. "
            + render_remediation_message(report, "self complementary")
            + f" The design is over the target but at or under the soft limit, so expect reduced titer. "
            f"Dropping self_complementary would move the design to the {ss_target:,} bp single stranded "
            f"target, at the cost of slower onset and a higher dose."
        )
        remediation = remediation_entries(report)
    else:
        message = (
            f"Self complementary design, so the halved capacity applies: the packaged genome is the "
            f"cassette duplicated, which is why the target is {sc_target:,} bp rather than the "
            f"{ss_target:,} bp single stranded target. "
            + render_remediation_message(report, "self complementary")
            + f" If none of these changes is acceptable, dropping self_complementary moves the design to "
            f"the {ss_target:,} bp single stranded target, at the cost of slower onset and a higher dose."
        )
        remediation = remediation_entries(report)
    return result(
        "aav.sc_capacity",
        severity,
        message,
        observed=f"{total:,} bp, self complementary",
        threshold=threshold,
        coordinates=(0, total),
        remediation=remediation,
    )


# ---------------------------------------------------------------------------
# 8. aav.promoter_tissue_match
# ---------------------------------------------------------------------------


def check_promoter_tissue_match(context: CheckContext) -> CheckResult:
    """Check 8: promoter `tissue_specificity` is compatible with `target_tissue`.

    WARN on violation, never FAIL (section 6.4). A length check will never
    catch a neuron specific promoter in a liver targeted vector, which is why
    this check exists, but the user is the one who knows the intended cell
    type, so the verdict is surfaced and explained rather than imposed.
    """
    design = context.design
    target = design.target_tissue
    allowed = sorted(context.thresholds.tissue_compatibility.get(target, frozenset()))
    threshold = f"promoter tissue_specificity in {{{', '.join(allowed)}}} for target {target}"
    promoter_layout = context.element_at(CassetteElementRole.PROMOTER)
    if promoter_layout is None:
        return result(
            "aav.promoter_tissue_match",
            Severity.UNKNOWN,
            "There is no promoter element, so tissue compatibility cannot be evaluated. Add a promoter, "
            "which aav.required_elements reports as missing, and this check will evaluate.",
            observed="no promoter element",
            threshold=threshold,
        )
    part_id = promoter_layout.part_id
    part = context.parts.get(part_id) if part_id else None
    if part is None:
        return result(
            "aav.promoter_tissue_match",
            Severity.UNKNOWN,
            f"The promoter element ({promoter_layout.name}) is not a part registry record, so it carries no "
            f"tissue_specificity annotation and compatibility with the {target} target cannot be evaluated. "
            f"Use a registry promoter, or confirm the tissue specificity of this sequence yourself.",
            observed=f"promoter not in registry: {part_id or promoter_layout.name}",
            threshold=threshold,
        )
    specificity = part.tissue_specificity
    if specificity is None:
        return result(
            "aav.promoter_tissue_match",
            Severity.UNKNOWN,
            f"Registry part {part.id} carries no tissue_specificity annotation, so compatibility with the "
            f"{target} target cannot be evaluated. Annotate the part or choose one that is annotated.",
            observed=f"{part.id} tissue_specificity is null",
            threshold=threshold,
        )
    if specificity in context.thresholds.tissue_compatibility.get(target, frozenset()):
        return result(
            "aav.promoter_tissue_match",
            Severity.PASS,
            f"Promoter {part.id} is annotated {specificity}, which is compatible with the {target} target. "
            f"No change is needed.",
            observed=f"{part.id} is {specificity}, target is {target}",
            threshold=threshold,
            coordinates=(promoter_layout.start, promoter_layout.end),
        )
    compatible = context.thresholds.tissue_compatibility.get(target, frozenset())
    alternatives = sorted(
        (
            candidate
            for candidate in context.parts.values()
            if PartCategory(candidate.category) is PartCategory.PROMOTER
            and candidate.tissue_specificity in compatible
        ),
        key=lambda candidate: (candidate.length_bp, candidate.id),
    )
    suggestion = (
        "; ".join(
            f"{candidate.id} ({candidate.tissue_specificity}, {candidate.length_bp:,} bp)"
            for candidate in alternatives[:3]
        )
        or "no compatible promoter is in the registry, so supply one"
    )
    if target == "ubiquitous":
        reason = (
            f"the vector asks for ubiquitous expression but {part.id} is {specificity} specific, so "
            f"expression will be restricted below what was requested"
        )
    else:
        reason = (
            f"{part.id} is annotated {specificity} and the target tissue is {target}, so the transgene may "
            f"not be expressed in the intended cells at all. No length or structural check catches this"
        )
    return result(
        "aav.promoter_tissue_match",
        Severity.WARN,
        f"Promoter and target tissue do not match: {reason}. Compatible registry promoters, shortest "
        f"first: {suggestion}. If the mismatch is intentional, for example because the intended cell type "
        f"is covered by this promoter in a way the annotation does not capture, keep it and record why.",
        observed=f"{part.id} is {specificity}, target is {target}",
        threshold=threshold,
        coordinates=(promoter_layout.start, promoter_layout.end),
    )


# ---------------------------------------------------------------------------
# 9. aav.internal_repeats
# ---------------------------------------------------------------------------


def check_internal_repeats(context: CheckContext) -> CheckResult:
    """Check 9: no direct repeat above the configured length inside the cassette.

    Scope: the region strictly between the two ITRs, and the whole cassette
    when the ITR pair is not present to delimit an interior. The scope is
    stated in every message.

    Why the ITRs are excluded, which is a biological judgment call and is
    recorded as one. The two AAV2 reference ITRs share their 125 bp hairpin
    core exactly: in the records in data/parts, `itr.aav2_itr_left` reads
    `core + D` and `itr.aav2_itr_right` reads `reverse complement of D + core`,
    the same 125 bases of core in both. So the two ITRs of any correct cassette
    are an exact 125 bp direct repeat of each other on the plus strand, by
    construction. That is the defining feature of an AAV vector, not a design
    error, and the ITR relationship is already policed by `aav.itr_present_both`,
    `aav.itr_orientation` and `aav.itr_internal_sites`. Reporting it here would
    put a WARN on every single correct design, which is exactly the failure
    mode section 3.4 warns about: it trains the user to ignore the validator.
    A repeat between an ITR and the interior is still caught, by check 14.
    """
    limit = context.thresholds.max_direct_repeat_bp
    span = context.design.interior_span()
    if span is None:
        offset, region = 0, context.cassette
        scope = f"the whole {len(region):,} bp cassette (no ITR pair delimits an interior)"
    else:
        offset = span[0]
        region = context.cassette[span[0] : span[1]]
        scope = f"the {len(region):,} bp region between the two ITRs"
    threshold = f"no direct repeat longer than {limit:,} bp"
    repeats = direct_repeats(region, min_length=limit + 1) if len(region) > limit else []
    if not repeats:
        return result(
            "aav.internal_repeats",
            Severity.PASS,
            f"No direct repeat longer than {limit:,} bp occurs in {scope}, so there is no obvious "
            f"recombination substrate to remove. No change is needed.",
            observed=f"0 repeats longer than {limit:,} bp in {scope}",
            threshold=threshold,
        )
    longest = max(repeats, key=lambda repeat: (repeat.length, -repeat.first))
    first = offset + longest.first
    second = offset + longest.second

    def where(position: int) -> str:
        for item in context.layout:
            if item.start <= position < item.end:
                return f"{CassetteElementRole(item.role).value} ({item.name})"
        return "outside any annotated element"

    return result(
        "aav.internal_repeats",
        Severity.WARN,
        f"{len(repeats)} direct repeat(s) longer than {limit:,} bp occur in {scope}. The longest is "
        f"{longest.length:,} bp, present at cassette positions {first + 1:,} and {second + 1:,} (in "
        f"{where(first)} and {where(second)}). Direct repeats in the same orientation are recombination "
        f"substrates during vector production and yield deleted species, so this lowers the fraction of "
        f"full length genomes. Either accept it, which is normal for standard parts (the 21 bp sequence "
        f"ACGGTAAATGGCCCGCCTGGC occurs twice inside promoter.cmv, promoter.cag and promoter.cbh because all "
        f"three carry the repeated CMV enhancer motif), or substitute a part that does not carry the "
        f"repeat: promoter.efs, promoter.ef1a, promoter.gfap, promoter.hsyn1 and promoter.mecp2_mini carry "
        f"none. This is a Tier B warning, not a failure.",
        observed=f"{len(repeats)} repeat(s), longest {longest.length:,} bp",
        threshold=threshold,
        coordinates=(first, first + longest.length),
    )


# ---------------------------------------------------------------------------
# 10. aav.homopolymer_runs
# ---------------------------------------------------------------------------


def check_homopolymer_runs(context: CheckContext) -> CheckResult:
    """Check 10: no homopolymer run above the configured length."""
    limit = context.thresholds.max_homopolymer_run
    threshold = f"no single base run longer than {limit:,} bp"
    runs = homopolymer_runs(context.cassette, min_length=limit + 1)
    if not runs:
        return result(
            "aav.homopolymer_runs",
            Severity.PASS,
            f"No single base run longer than {limit:,} bp occurs inside the {len(context.cassette):,} bp "
            f"cassette, so synthesis and replication stability are not at risk from homopolymers. No "
            f"change is needed.",
            observed=f"longest run at or under {limit:,} bp",
            threshold=threshold,
        )
    longest = max(runs, key=lambda run: (run.length, -run.start))
    element = next(
        (item for item in context.layout if item.start <= longest.start < item.end),
        None,
    )
    located = (
        f" inside {CassetteElementRole(element.role).value} ({element.name})" if element is not None else ""
    )
    return result(
        "aav.homopolymer_runs",
        Severity.WARN,
        f"{len(runs)} homopolymer run(s) longer than {limit:,} bp occur inside the cassette. The longest is "
        f"{longest.length:,} consecutive {longest.base} at cassette position {longest.start + 1:,}"
        f"{located}. Long single base runs destabilise synthesis and replication and are a common cause of "
        f"indels in the ordered DNA. If the run sits in your own transgene, break it with synonymous codon "
        f"changes. If it sits in a registry part, it is expected and documented: promoter.cag carries a "
        f"14 bp G run and promoter.cbh a 16 bp G run in their GC rich cores. This is a Tier B warning, not "
        f"a failure.",
        observed=f"{len(runs)} run(s), longest {longest.length:,} bp of {longest.base}",
        threshold=threshold,
        coordinates=(longest.start, longest.end),
    )


# ---------------------------------------------------------------------------
# 11. aav.kozak_context
# ---------------------------------------------------------------------------


def _describe_upstream_source(context: CheckContext, position: int, cds_index: int) -> str:
    """Name the cassette element that supplies the base at `position`.

    The composer now places a Kozak initiation context element between the last
    upstream element and the ATG when the transgene begins with ATG, so for a
    composed cassette position -3 belongs to that element. This helper's job is
    to name the owner of the -3 base in the cases where it is still something
    else: a caller supplied cassette, and a transgene that brought its own
    context, where the base is whatever the last upstream element happens to end
    on. A user told only that "position -3 is C" cannot tell whose C it is, so
    every message that quotes the -3 base names its owner.
    Returns "" when no element covers the position, which happens only for an
    explicit cassette whose elements do not tile the sequence.
    """
    owner = next(
        (item for item in context.layout if item.start <= position < item.end and item.index != cds_index),
        None,
    )
    if owner is None:
        return ""
    from_end = owner.end - position
    identifier = f" ({owner.part_id})" if owner.part_id else ""
    where = (
        f"the last base of {owner.name}{identifier}"
        if from_end == 1
        else f"{from_end} bases from the 3' end of {owner.name}{identifier}"
    )
    if owner.role is CassetteElementRole.KOZAK:
        return (
            f" That base is {where}, which is the cassette's own initiation context element. The base comes "
            f"from that element's own sequence, which is not the cited consensus, so the element itself "
            f"should be corrected."
        )
    sentence = (
        f" That base is {where}, the element immediately 5' of the coding sequence: the cassette carries "
        f"no initiation context element between the two, so the last bases of that element become the "
        f"5' UTR and set this position."
    )
    if owner.role == CassetteElementRole.INTRON:
        sentence += (
            " Note that the intron, not the promoter, is the last element before the coding sequence "
            "whenever it is included, so it sets position -3 whichever promoter was chosen. Removing the "
            "intron hands the position back to the promoter."
        )
    elif owner.role == CassetteElementRole.PROMOTER:
        sentence += (
            " It is a promoter feature boundary rather than anything chosen for translation, so changing "
            "promoter changes this base by coincidence, not by design."
        )
    return sentence


def check_kozak_context(context: CheckContext) -> CheckResult:
    """Check 11: an ATG with a recognisable Kozak context precedes the CDS.

    Scored on the two positions the Kozak 1987 consensus makes decisive, a
    purine at -3 and a G at +4, with the full `GCCRCCATGG` consensus reported
    separately. UNKNOWN when there is no CDS, when the CDS does not start with
    ATG (which aav.cds_integrity already reports), or when fewer than three
    bases precede the start codon, because then position -3 does not exist.

    The bases immediately 5' of the ATG really are the transcript's 5' UTR: the
    transcription start site sits inside the promoter, so everything from there
    to the ATG is transcribed and `cassette[start - 3]` is the mRNA's -3
    position. For a composed cassette whose transgene begins with ATG the
    composer places a Kozak element there, so that base is the cited consensus.
    When no such element is present, a caller supplied cassette or a transgene
    that brought its own context, what that base *is* is an accident of where a
    curator drew the upstream part's feature boundary, because nothing places an
    initiation context element between the two. So the message names the element
    the base came from: see `_describe_upstream_source`. Without that, a user
    told "position -3 is C" has no way to find out whose C it is.
    """
    thresholds = context.thresholds
    purines = " or ".join(thresholds.kozak_minus3_purines)
    threshold = (
        f"purine ({' or '.join(thresholds.kozak_minus3_purines)}) at -3 and "
        f"{thresholds.kozak_plus4_base} at +4; full consensus {thresholds.kozak_consensus_motif}"
    )
    cds_layout = context.element_at(CassetteElementRole.CDS)
    if cds_layout is None:
        return result(
            "aav.kozak_context",
            Severity.UNKNOWN,
            "There is no coding sequence, so the initiation context cannot be evaluated. Add the transgene "
            "coding sequence and this check will evaluate.",
            observed="no cds element",
            threshold=threshold,
        )
    cassette = context.cassette
    start = cds_layout.start
    if cassette[start : start + 3] != "ATG":
        return result(
            "aav.kozak_context",
            Severity.UNKNOWN,
            f"The coding sequence does not begin with ATG (it begins with {cassette[start:start + 3]}), so "
            f"there is no initiator codon whose context can be scored. Fix the start codon, which "
            f"aav.cds_integrity reports, and this check will evaluate.",
            observed=f"cds begins with {cassette[start:start + 3]}",
            threshold=threshold,
        )
    if start < 3:
        return result(
            "aav.kozak_context",
            Severity.UNKNOWN,
            f"Only {start} base(s) precede the start codon, so position -3 of the initiation context does "
            f"not exist and the context cannot be scored. Place the coding sequence downstream of a "
            f"promoter, or supply at least 6 bases of 5' context.",
            observed=f"{start} bases of 5' context",
            threshold=threshold,
        )
    if start + 4 > len(cassette):
        return result(
            "aav.kozak_context",
            Severity.UNKNOWN,
            "The coding sequence is too short to read position +4 of the initiation context, so it cannot "
            "be scored. Supply the full coding sequence and this check will evaluate.",
            observed="fewer than 4 bases from the start codon",
            threshold=threshold,
        )
    minus3 = cassette[start - 3]
    plus4 = cassette[start + 3]
    window_start = max(0, start - 6)
    window = cassette[window_start : start + 4]
    full_consensus = len(window) == len(thresholds.kozak_consensus_motif) and matches_iupac(
        window, thresholds.kozak_consensus_motif
    )
    minus3_ok = minus3 in thresholds.kozak_minus3_purines
    plus4_ok = plus4 == thresholds.kozak_plus4_base
    observed = f"-3 is {minus3}, +4 is {plus4}, context {window}"
    coordinates = (window_start, start + 4)
    if minus3_ok and plus4_ok:
        extra = (
            " The context also matches the full consensus exactly."
            if full_consensus
            else f" The full {thresholds.kozak_consensus_motif} consensus is not matched at every position, "
            f"which is common and not a problem once -3 and +4 are right."
        )
        # The consensus is written R at -3, so A and G both satisfy this check and
        # the threshold is the same for either. The cited analysis nonetheless
        # finds A the commoner purine there, which is worth saying when the base
        # is G so that a designer starting from scratch knows which to choose.
        if minus3 == "G" and "A" in thresholds.kozak_minus3_purines:
            extra += (
                " One refinement, which does not change this verdict: the consensus is written with a "
                "purine at -3 and A and G both satisfy it, so this check accepts either and the threshold "
                "is the same for both, but A is the commoner of the two in the cited analysis. If the "
                "context is being designed rather than inherited, prefer A at -3."
            )
        return result(
            "aav.kozak_context",
            Severity.PASS,
            f"The initiator ATG sits in a strong Kozak context: a purine ({minus3}) at -3 and "
            f"{thresholds.kozak_plus4_base} at +4, reading {window}. No change is needed.{extra}",
            observed=observed,
            threshold=threshold,
            coordinates=coordinates,
        )
    weak: list[str] = []
    fixes: list[str] = []
    source = ""
    if not minus3_ok:
        weak.append(f"position -3 is {minus3}, where a purine ({purines}) is required")
        fixes.append(f"change the base 3 nt upstream of the ATG to {purines}")
        source = _describe_upstream_source(context, start - 3, cds_layout.index)
    if not plus4_ok:
        weak.append(
            f"position +4 is {plus4} rather than {thresholds.kozak_plus4_base}, which is the first base of "
            f"the second codon"
        )
        fixes.append(
            f"choose a second codon beginning with {thresholds.kozak_plus4_base}, which for most residues is "
            f"a synonymous change and does not alter the protein"
        )
    # Inserting the prefix only helps when -3 is what fails. When -3 is already a
    # purine and only +4 fails, there is nothing to insert and the second codon
    # is the only fix.
    prefix_advice = (
        f" The simplest change is to insert the {thresholds.kozak_consensus_motif[:6]} prefix "
        f"immediately before the ATG."
        if not minus3_ok
        else ""
    )
    strength = "an adequate but not optimal" if (minus3_ok or plus4_ok) else "a weak"
    return result(
        "aav.kozak_context",
        Severity.WARN,
        f"The initiator ATG sits in {strength} Kozak context ({window}): {' and '.join(weak)}.{source} A "
        f"weak context allows leaky scanning past the start codon and lowers the amount of protein made per "
        f"transcript. To fix: {'; '.join(fixes)}.{prefix_advice} If the context is "
        f"deliberately weak, for example to tune expression down, this is a Tier B warning to record rather "
        f"than a failure.",
        observed=observed,
        threshold=threshold,
        coordinates=coordinates,
    )


# ---------------------------------------------------------------------------
# 12. aav.polya_present_functional
# ---------------------------------------------------------------------------


def check_polya_present_functional(context: CheckContext) -> CheckResult:
    """Check 12: polyA is a recognised functional signal, not merely an annotation.

    FAIL when no polyA element is present, WARN when one is present but carries
    none of the configured hexamers.
    """
    motifs = context.thresholds.polya_signal_motifs
    threshold = f"one of {', '.join(motifs)} present in the polyA element"
    polya_layout = context.element_at(CassetteElementRole.POLYA)
    if polya_layout is None:
        shortest = sorted(
            (
                part
                for part in context.parts.values()
                if PartCategory(part.category) is PartCategory.POLYA
            ),
            key=lambda part: (part.length_bp, part.id),
        )
        options = (
            ", ".join(f"{part.id} ({part.length_bp:,} bp)" for part in shortest)
            or "no polyA part is in the registry"
        )
        return result(
            "aav.polya_present_functional",
            Severity.FAIL,
            f"The cassette carries no polyadenylation signal. Without one the transcript is not cleaved and "
            f"polyadenylated, so it is unstable, poorly exported and read through into the 3' ITR. Add a "
            f"polyA element from the part registry, shortest first: {options}.",
            observed="no polya element",
            threshold=threshold,
        )
    sequence = context.design.elements[polya_layout.index].sequence
    found: list[tuple[str, int]] = []
    for motif in motifs:
        for offset in find_exact(sequence, motif):
            found.append((motif, offset))
    found.sort(key=lambda hit: (hit[1], hit[0]))
    if not found:
        return result(
            "aav.polya_present_functional",
            Severity.WARN,
            f"An element is annotated as the polyA ({polya_layout.name}, {polya_layout.length_bp:,} bp) but "
            f"it contains none of the recognised polyadenylation hexamers ({', '.join(motifs)}), so it may "
            f"be an annotation rather than a functional signal. Verify the sequence, or replace it with a "
            f"registry part: polya.bgh (225 bp) carries AATAAA at position 91 and polya.sv40 (135 bp) "
            f"carries it at positions 32 and 61. This is a warning, not a failure, because a functional "
            f"signal with an unusual hexamer is possible.",
            observed="no recognised hexamer in the polyA element",
            threshold=threshold,
            coordinates=(polya_layout.start, polya_layout.end),
        )
    motif, offset = found[0]
    return result(
        "aav.polya_present_functional",
        Severity.PASS,
        f"The polyA element ({polya_layout.name}, {polya_layout.length_bp:,} bp) carries a recognised "
        f"polyadenylation hexamer: {motif} at position {offset + 1:,} of the element, cassette position "
        f"{polya_layout.start + offset + 1:,}"
        + (f", and {len(found) - 1} further occurrence(s)." if len(found) > 1 else ".")
        + " No change is needed.",
        observed=f"{motif} at element position {offset + 1:,} ({len(found)} occurrence(s))",
        threshold=threshold,
        coordinates=(polya_layout.start + offset, polya_layout.start + offset + len(motif)),
    )


# ---------------------------------------------------------------------------
# 13. aav.minimum_genome_size
# ---------------------------------------------------------------------------


def check_minimum_genome_size(context: CheckContext) -> CheckResult:
    """Check 13: the genome is not so small that packaging efficiency degrades."""
    minimum = context.thresholds.min_genome_bp
    total = context.design.total_bp
    threshold = f"at least {minimum:,} bp"
    if total >= minimum:
        return result(
            "aav.minimum_genome_size",
            Severity.PASS,
            f"The cassette is {total:,} bp, which is at or above the {minimum:,} bp minimum, so packaging "
            f"efficiency is not degraded by under-length genomes. No change is needed.",
            observed=f"{total:,} bp",
            threshold=threshold,
        )
    shortfall = minimum - total
    return result(
        "aav.minimum_genome_size",
        Severity.WARN,
        f"The cassette is {total:,} bp, {shortfall:,} bp below the {minimum:,} bp minimum. Genomes this "
        f"small package less efficiently and raise the empty capsid fraction, so the usable titer per "
        f"production run drops. Add about {shortfall:,} bp: a longer promoter (promoter.ef1a is 1,184 bp "
        f"against promoter.efs at 212 bp), the chimeric intron (intron.chimeric, 141 bp), WPRE "
        f"(enhancer.wpre, 589 bp), or a stuffer sequence. This is a warning, not a failure: the vector will "
        f"still package.",
        observed=f"{total:,} bp",
        threshold=threshold,
        coordinates=(0, total),
    )


# ---------------------------------------------------------------------------
# 14. aav.itr_internal_sites
# ---------------------------------------------------------------------------


def check_itr_internal_sites(context: CheckContext) -> CheckResult:
    """Check 14: no sequence inside the cassette duplicates an ITR motif.

    The motif set is every window of `itr_internal_motif_bp` bases taken from
    the serotype's reference ITR records, so nothing is written into the code.
    The search covers the region strictly between the two ITRs, on both
    strands, because an internal ITR copy is a substrate for aberrant terminal
    resolution and yields truncated genomes during production.
    """
    width = context.thresholds.itr_internal_motif_bp
    threshold = f"no {width:,} bp window of a {context.design.serotype} ITR present between the ITRs"
    if context.itr_reference is None:
        return result(
            "aav.itr_internal_sites",
            Severity.UNKNOWN,
            f"Internal ITR motifs cannot be searched for: {context.itr_error}",
            observed="serotype reference unavailable",
            threshold=threshold,
        )
    span = context.design.interior_span()
    if span is None:
        return result(
            "aav.itr_internal_sites",
            Severity.UNKNOWN,
            "There is no region between two ITRs to search, because the cassette does not carry both ITRs "
            "with content between them. Add the missing ITR, which aav.itr_present_both reports, and this "
            "check will evaluate.",
            observed="no interior region between two ITRs",
            threshold=threshold,
        )
    start, end = span
    interior = context.cassette[start:end]
    hits = internal_itr_motif_hits(interior, context.itr_reference, width)
    if not hits:
        return result(
            "aav.itr_internal_sites",
            Severity.PASS,
            f"No {width:,} bp window of a {context.design.serotype} ITR occurs in the {len(interior):,} bp "
            f"region between the two ITRs, on either strand. There is no internal terminal repeat copy to "
            f"remove. No change is needed.",
            observed=f"0 internal ITR motifs in {len(interior):,} bp",
            threshold=threshold,
        )
    motif, offset, strand = hits[0]
    position = start + offset
    element = next((item for item in context.layout if item.start <= position < item.end), None)
    located = (
        f" inside {CassetteElementRole(element.role).value} ({element.name})" if element is not None else ""
    )
    return result(
        "aav.itr_internal_sites",
        Severity.WARN,
        f"{len(hits)} ITR motif(s) of {width:,} bp also occur inside the cassette. The first is {motif} at "
        f"cassette position {position + 1:,}{located}, on the "
        + ("plus" if strand == 1 else "minus")
        + " strand. An internal copy of terminal repeat sequence is a substrate for aberrant resolution "
        "during production and yields truncated genomes, so it lowers the fraction of full length vector. "
        "Check whether the element carrying it can be substituted, or whether the match is incidental GC "
        "rich sequence. This is a Tier B warning, not a failure.",
        observed=f"{len(hits)} internal ITR motif(s), first {motif} at {position + 1:,}",
        threshold=threshold,
        coordinates=(position, position + width),
    )


# The section 6.4 table, in order. The validator runs exactly these, in this
# order, and nothing else.
CHECKS: tuple[tuple[str, object], ...] = (
    ("aav.packaging_limit", check_packaging_limit),
    ("aav.itr_present_both", check_itr_present_both),
    ("aav.itr_orientation", check_itr_orientation),
    ("aav.required_elements", check_required_elements),
    ("aav.element_order", check_element_order),
    ("aav.cds_integrity", check_cds_integrity),
    ("aav.sc_capacity", check_sc_capacity),
    ("aav.promoter_tissue_match", check_promoter_tissue_match),
    ("aav.internal_repeats", check_internal_repeats),
    ("aav.homopolymer_runs", check_homopolymer_runs),
    ("aav.kozak_context", check_kozak_context),
    ("aav.polya_present_functional", check_polya_present_functional),
    ("aav.minimum_genome_size", check_minimum_genome_size),
    ("aav.itr_internal_sites", check_itr_internal_sites),
)
