"""The nineteen section 7.5 validation checks, with their exact check_ids.

Source: the section 7.5 table of the engine capability system design. The
check_ids, the thing each check verifies and the severity on violation are
taken from that table and nothing is added to it: section 6.4's instruction
"These are the checks. Implement all of them. Do not add an invented one."
applies to section 7.5 in the same way.

Every check returns at most one `CheckResult`, aggregating across the primers,
junctions or amplicons it inspects. That is required rather than stylistic: the
shared contract rejects a report containing two results with the same
`check_id`, and one row per check is what section 10.3's shared validation
report component renders. The severity of the row is the worst found, and the
message names every item that contributed, with its number, so the row is
actionable per section 5.4 rule 2.

APPLICABILITY. Nine checks are strategy-specific: checks 11 to 13 apply to
Gibson, checks 14 to 17 to Golden Gate, and check 18 only where the junction
topology exists to be examined. A check that does not apply to the requested
strategy is omitted from the report rather than reported as a PASS or an
UNKNOWN. Reporting it PASS would assert something that was never tested, and
section 3.3 constraint 4 forbids that; reporting it UNKNOWN would put a
permanent unevaluated row in every report, which section 5.4 rule 1 reserves
for checks that genuinely could not be evaluated. `applicable_checks` lists
which checks a strategy runs and it goes into `parameters_used`, so a reader
can always see what was and was not examined.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.core.schemas.assembly import AssemblyDesign, AssemblyRequest, Junction, Primer
from packages.core.schemas.capability import CheckResult, Severity
from packages.core.sequence import clean_sequence, find_both_strands, gc_content, homopolymer_runs, reverse_complement
from packages.core.sequence.tm import melting_temperature

from . import structure
from .constants import CITATIONS, GIBSON_INCUBATION_C, PCR_EXTENSION_S_PER_KB
from .enzymes import TypeIISEnzyme, find_recognition_sites, get_enzyme
from .settings import Settings

# Which of the nineteen section 7.5 checks each strategy runs. See the
# APPLICABILITY note in the module docstring.
_UNIVERSAL: tuple[str, ...] = (
    "primer.tm_in_range",
    "primer.pair_tm_delta",
    "primer.gc_content",
    "primer.length",
    "primer.three_prime_stability",
    "primer.hairpin",
    "primer.self_dimer",
    "primer.hetero_dimer",
    "primer.specificity_in_template",
    "primer.homopolymer",
    "assembly.amplicon_size",
)
APPLICABLE_CHECKS: dict[str, tuple[str, ...]] = {
    "gibson": _UNIVERSAL
    + (
        "gibson.overlap_length",
        "gibson.overlap_tm",
        "gibson.overlap_uniqueness",
        "assembly.fragment_order_defined",
    ),
    "golden_gate": _UNIVERSAL
    + (
        "gg.enzyme_site_internal",
        "gg.overhang_uniqueness",
        "gg.overhang_not_palindromic",
        "gg.overhang_composition",
        "assembly.fragment_order_defined",
    ),
    "pcr_cloning": _UNIVERSAL + ("assembly.fragment_order_defined",),
}

# Every check_id in the section 7.5 table, in table order. Used by the tests to
# assert that nothing was dropped and nothing was invented.
ALL_CHECK_IDS: tuple[str, ...] = (
    "primer.tm_in_range",
    "primer.pair_tm_delta",
    "primer.gc_content",
    "primer.length",
    "primer.three_prime_stability",
    "primer.hairpin",
    "primer.self_dimer",
    "primer.hetero_dimer",
    "primer.specificity_in_template",
    "primer.homopolymer",
    "gibson.overlap_length",
    "gibson.overlap_tm",
    "gibson.overlap_uniqueness",
    "gg.enzyme_site_internal",
    "gg.overhang_uniqueness",
    "gg.overhang_not_palindromic",
    "gg.overhang_composition",
    "assembly.fragment_order_defined",
    "assembly.amplicon_size",
)

_LABELS: dict[str, str] = {
    "primer.tm_in_range": "Primer melting temperature in range",
    "primer.pair_tm_delta": "Primer pair melting temperature difference",
    "primer.gc_content": "Primer GC content",
    "primer.length": "Primer length",
    "primer.three_prime_stability": "Primer 3' end composition",
    "primer.hairpin": "Primer hairpin",
    "primer.self_dimer": "Primer self-dimer",
    "primer.hetero_dimer": "Primer pair hetero-dimer",
    "primer.specificity_in_template": "Primer specificity in the template set",
    "primer.homopolymer": "Primer homopolymer run",
    "gibson.overlap_length": "Gibson terminal homology length",
    "gibson.overlap_tm": "Gibson overlap melting temperature",
    "gibson.overlap_uniqueness": "Gibson junction homology uniqueness",
    "gg.enzyme_site_internal": "Type IIS site inside a fragment",
    "gg.overhang_uniqueness": "Fusion overhangs distinct",
    "gg.overhang_not_palindromic": "Fusion overhang not palindromic",
    "gg.overhang_composition": "Fusion overhang composition",
    "assembly.fragment_order_defined": "Assembly order unambiguous",
    "assembly.amplicon_size": "Expected amplicon size",
}


@dataclass
class Context:
    """Everything the checks read, resolved once so they cannot disagree."""

    design: AssemblyDesign
    settings: Settings

    @property
    def request(self) -> AssemblyRequest:
        return self.design.request

    def tm(self, sequence: str) -> float:
        """Nearest-neighbor Tm at the request's salt and strand concentration."""
        return melting_temperature(
            sequence,
            primer_conc_nm=self.request.primer_conc_nm,
            monovalent_salt_mm=self.request.monovalent_salt_mm,
            divalent_salt_mm=self.request.divalent_salt_mm,
            dntp_mm=self.request.dntp_mm,
        )

    @property
    def enzyme(self) -> TypeIISEnzyme | None:
        return get_enzyme(self.request.enzyme) if self.request.enzyme else None


def _result(
    check_id: str,
    severity: Severity,
    message: str,
    *,
    observed: str | None = None,
    threshold: str | None = None,
    coordinates: tuple[int, int] | None = None,
    tier: str | None = None,
    remediation: list[str] | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        label=_LABELS[check_id],
        severity=severity,
        message=message,
        observed=observed,
        threshold=threshold,
        coordinates=coordinates,
        citation=CITATIONS[check_id],
        tier=tier,  # type: ignore[arg-type]
        remediation=remediation,
    )


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def _subject(count: int, noun: str, verb_singular: str, verb_plural: str) -> str:
    """"1 primer melts" or "3 primers melt", so a message reads correctly at any count."""
    return f"{count} {_plural(count, noun)} {verb_singular if count == 1 else verb_plural}"


# ---------------------------------------------------------------------------
# 1. primer.tm_in_range
# ---------------------------------------------------------------------------


def check_tm_in_range(context: Context) -> CheckResult:
    """Section 7.5 check 1: WARN outside the window, FAIL far outside.

    Measured on the template-binding region, not the whole oligo: a Gibson
    homology arm or a Type IIS tail does not anneal to the template in the
    first cycle, so including it would report a melting temperature the
    reaction never sees.
    """
    settings = context.settings
    target = context.request.target_tm_c
    warn: list[str] = []
    fail: list[str] = []
    values: list[str] = []
    for primer in context.design.primers:
        value = context.tm(primer.binding)
        values.append(f"{primer.name} {value:.1f} C")
        delta = abs(value - target)
        if delta > settings.primer_tm_fail_tolerance_c:
            fail.append(f"{primer.name} at {value:.1f} C, {delta:.1f} C from target")
        elif delta > settings.primer_tm_warn_tolerance_c:
            warn.append(f"{primer.name} at {value:.1f} C, {delta:.1f} C from target")
    window = (
        f"{target - settings.primer_tm_warn_tolerance_c:.1f} to "
        f"{target + settings.primer_tm_warn_tolerance_c:.1f} C"
    )
    observed = "; ".join(values)
    threshold = f"target {target:.1f} C, warn outside {window}, fail beyond {settings.primer_tm_fail_tolerance_c:.1f} C"
    if fail:
        return _result(
            "primer.tm_in_range",
            Severity.FAIL,
            f"{_subject(len(fail), 'primer', 'melts', 'melt')} more than "
            f"{settings.primer_tm_fail_tolerance_c:.1f} C from the {target:.1f} C target: "
            f"{'; '.join(fail)}. No single annealing temperature will serve these alongside the "
            "rest of the set. Redesign each by moving its binding region or changing its length "
            f"until its Tm is inside {window}, or split the reaction into separate PCRs.",
            observed=observed,
            threshold=threshold,
        )
    if warn:
        return _result(
            "primer.tm_in_range",
            Severity.WARN,
            f"{_subject(len(warn), 'primer', 'falls', 'fall')} outside the {window} window: "
            f"{'; '.join(warn)}. Lengthen the binding region of a primer that melts low and "
            "shorten one that melts high, by one or two nucleotides at a time, or accept the "
            "spread and set the annealing temperature from the lowest Tm in the set.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.tm_in_range",
        Severity.PASS,
        f"Every primer melts within {settings.primer_tm_warn_tolerance_c:.1f} C of the "
        f"{target:.1f} C target ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 2. primer.pair_tm_delta
# ---------------------------------------------------------------------------


def check_pair_tm_delta(context: Context) -> CheckResult | None:
    """Section 7.5 check 2: WARN when a pair's Tm difference exceeds the threshold."""
    pairs = context.design.primer_pairs()
    if not pairs:
        return None
    limit = context.settings.primer_pair_max_tm_delta_c
    offenders: list[str] = []
    values: list[str] = []
    for forward, reverse in pairs:
        forward_tm = context.tm(forward.binding)
        reverse_tm = context.tm(reverse.binding)
        delta = abs(forward_tm - reverse_tm)
        values.append(f"{forward.name}/{reverse.name} {delta:.1f} C")
        if delta > limit:
            cooler, warmer = (forward, reverse) if forward_tm < reverse_tm else (reverse, forward)
            offenders.append(
                f"{forward.name} {forward_tm:.1f} C against {reverse.name} {reverse_tm:.1f} C, "
                f"a {delta:.1f} C difference; lengthen the binding region of {cooler.name} or "
                f"shorten the binding region of {warmer.name} until they are within {limit:.1f} C"
            )
    observed = "; ".join(values)
    threshold = f"at most {limit:.1f} C within a pair"
    if offenders:
        return _result(
            "primer.pair_tm_delta",
            Severity.WARN,
            f"{_subject(len(offenders), 'primer pair', 'differs', 'differ')} by more than "
            f"{limit:.1f} C: {'; '.join(offenders)}. A pair that far apart cannot both anneal "
            "well at one temperature: the cooler primer binds inefficiently at the temperature "
            "the warmer one needs, and lowering the temperature to suit it costs specificity.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.pair_tm_delta",
        Severity.PASS,
        f"Every pair is within {limit:.1f} C ({observed}), so one annealing temperature serves "
        "the whole set. No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 3. primer.gc_content
# ---------------------------------------------------------------------------


def check_gc_content(context: Context) -> CheckResult:
    """Section 7.5 check 3: WARN when the binding region's GC fraction is outside the window."""
    settings = context.settings
    low, high = settings.primer_gc_min_fraction, settings.primer_gc_max_fraction
    offenders: list[str] = []
    values: list[str] = []
    for primer in context.design.primers:
        fraction = gc_content(primer.binding)
        values.append(f"{primer.name} {fraction * 100:.0f}%")
        if fraction < low:
            offenders.append(
                f"{primer.name} at {fraction * 100:.0f}%, below {low * 100:.0f}%; shift its "
                "binding region towards a GC-richer part of the template"
            )
        elif fraction > high:
            offenders.append(
                f"{primer.name} at {fraction * 100:.0f}%, above {high * 100:.0f}%; shift its "
                "binding region towards an AT-richer part of the template"
            )
    observed = "; ".join(values)
    threshold = f"{low * 100:.0f}% to {high * 100:.0f}% GC"
    if offenders:
        return _result(
            "primer.gc_content",
            Severity.WARN,
            f"{_subject(len(offenders), 'primer', 'sits', 'sit')} outside the "
            f"{threshold} window: {'; '.join(offenders)}. A GC-poor primer binds weakly and a "
            "GC-rich one mispriments and forms secondary structure, so moving the binding region "
            "a few nucleotides is usually enough to fix it.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.gc_content",
        Severity.PASS,
        f"Every primer's binding region is within {threshold} ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 4. primer.length
# ---------------------------------------------------------------------------


def check_length(context: Context) -> CheckResult:
    """Section 7.5 check 4: WARN when a length is outside the window.

    Two lengths are measured, for the reason given in `constants.py`: the
    binding region against the primer length window, and the whole oligo
    including any tail against the ordering limit.
    """
    settings = context.settings
    offenders: list[str] = []
    values: list[str] = []
    for primer in context.design.primers:
        values.append(f"{primer.name} {len(primer.binding)} nt binding, {primer.length_nt} nt total")
        if len(primer.binding) < settings.primer_min_length_nt:
            offenders.append(
                f"{primer.name} binds over only {len(primer.binding)} nt, under the "
                f"{settings.primer_min_length_nt} nt minimum; extend it into the template"
            )
        elif len(primer.binding) > settings.primer_max_length_nt:
            offenders.append(
                f"{primer.name} binds over {len(primer.binding)} nt, over the "
                f"{settings.primer_max_length_nt} nt maximum; trim it from the 5' end of the "
                "binding region, which does not change where it anneals from"
            )
        if primer.length_nt > settings.primer_max_total_length_nt:
            offenders.append(
                f"{primer.name} is {primer.length_nt} nt in total, over the "
                f"{settings.primer_max_total_length_nt} nt ordering limit; shorten the "
                f"{len(primer.tail)} nt tail or the binding region, or order it as an "
                "extended-length oligo"
            )
    observed = "; ".join(values)
    threshold = (
        f"binding {settings.primer_min_length_nt} to {settings.primer_max_length_nt} nt, "
        f"total at most {settings.primer_max_total_length_nt} nt"
    )
    if offenders:
        return _result(
            "primer.length",
            Severity.WARN,
            f"{len(offenders)} length {_plural(len(offenders), 'problem')}: {'; '.join(offenders)}.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.length",
        Severity.PASS,
        f"Every primer is within {threshold} ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 5. primer.three_prime_stability
# ---------------------------------------------------------------------------


def check_three_prime_stability(context: Context) -> CheckResult:
    """Section 7.5 check 5, verbatim: the last five bases are not excessively
    GC-rich, and the 3' base is not T.

    The 3' end is where the polymerase starts, so its composition decides
    whether a mispriming event gets extended. A GC-rich 3' end anchors a primer
    that is otherwise mismatched; a 3' T is the base that mispairs most readily.
    """
    settings = context.settings
    window = settings.primer_three_prime_window_nt
    limit = settings.primer_three_prime_max_gc_in_window
    offenders: list[str] = []
    values: list[str] = []
    for primer in context.design.primers:
        sequence = primer.sequence
        tail_bases = sequence[-window:]
        gc = sum(1 for base in tail_bases if base in "GC")
        values.append(f"{primer.name} 3'-{tail_bases}, {gc} GC, ends {sequence[-1]}")
        if gc > limit:
            offenders.append(
                f"{primer.name} ends 3'-{tail_bases} with {gc} of {len(tail_bases)} bases G or C, "
                f"over the limit of {limit}; move the 3' end one or two nucleotides so it lands on "
                "an A or T"
            )
        if sequence.endswith("T"):
            offenders.append(
                f"{primer.name} ends in T, which mispairs more readily than the other three bases; "
                "shift the 3' end by one nucleotide so it ends in A, G or C"
            )
    observed = "; ".join(values)
    threshold = f"at most {limit} G or C in the last {window} bases, 3' base not T"
    if offenders:
        return _result(
            "primer.three_prime_stability",
            Severity.WARN,
            f"{len(offenders)} 3' end {_plural(len(offenders), 'problem')}: {'; '.join(offenders)}.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.three_prime_stability",
        Severity.PASS,
        f"Every 3' end satisfies {threshold} ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 6. primer.hairpin
# ---------------------------------------------------------------------------


def _hairpin_detail(primer: Primer, fold: structure.HairpinResult, stem_text: str) -> str:
    """One primer's hairpin finding, with the oligo segment each arm lies in.

    A stem length on its own is not actionable: the reader cannot tell whether
    the self-complementary stretch is in the fixed 5' tail, where a Gibson
    homology arm or a Type IIS site plus overhang is set by the assembly
    standard, or in the template-binding region, which can be walked along the
    template. The arm positions and their segments say which.
    """
    where = structure.arm_segments(fold, tail_nt=len(primer.tail))
    return f"{stem_text} ({where})" if where else stem_text


def _hairpin_segment_advice(offenders: list[tuple[Primer, structure.HairpinResult]]) -> str:
    """The remedy that follows from where the reported stems actually sit.

    This is the only remedy the message offers, deliberately. A generic "shorten
    the primer from the 5' end" alongside it would contradict the segment advice
    whenever the 5' end is a fixed tail, and a reader given two conflicting
    remedies acts on neither.
    """
    if not offenders or any(
        fold.five_prime_arm is None or fold.three_prime_arm is None for _, fold in offenders
    ):
        # No arm coordinates, so nothing can be said about segments. Fall back to
        # the remedy that holds regardless of where the stem sits.
        return (
            " Move the binding region so the self-complementary stretch is broken up, or shorten "
            "the primer from the 5' end if the stem starts there."
        )
    if all(structure.arms_are_movable(fold, tail_nt=len(primer.tail)) for primer, fold in offenders):
        return (
            " Both arms of every stem reported lie in the template-binding region, so walking the "
            "primer a few bases along the template breaks the self-complementary stretch without "
            "touching the junction."
        )
    return (
        " At least one arm lies in the fixed 5' tail, whose sequence the assembly standard sets, "
        "so the tail cannot be moved and only the template-binding arm can be redesigned: walk "
        "the binding region until it no longer pairs with the tail."
    )


def check_hairpin(context: Context) -> CheckResult:
    """Section 7.5 check 6: WARN at or past the threshold, FAIL when a 3' stem
    is past the hard threshold.

    The metric depends on the engine, which is recorded in the message and in
    `parameters_used` rather than left for the reader to guess. With a free
    energy engine the threshold is in kcal/mol; with the documented
    sliding-window fallback it is a stem length in base pairs. A request that
    demands the free energy engine and does not get it returns UNKNOWN with the
    reason, never a pass (section 3.3 constraint 4).
    """
    settings = context.settings
    requested = context.request.hairpin_engine
    if requested == "viennarna" and not structure.hairpin_engine_available():
        return _result(
            "primer.hairpin",
            Severity.UNKNOWN,
            "A hairpin free energy was requested but ViennaRNA is not importable in this "
            "environment, so no free energy could be computed and no hairpin verdict is given. "
            "Install ViennaRNA, or set hairpin_engine to 'window' to use the documented "
            "sliding-window stem score instead, which reports a stem length in base pairs.",
            threshold=f"{settings.hairpin_dg_warn_kcal_per_mol:.1f} kcal/mol",
        )
    folds: list[tuple[Primer, structure.HairpinResult]] = [
        (
            primer,
            structure.hairpin(
                primer.sequence,
                min_loop_nt=settings.hairpin_min_loop_nt,
                three_prime_window_nt=settings.three_prime_involvement_window_nt,
                engine=requested,
            ),
        )
        for primer in context.design.primers
    ]
    engine = folds[0][1].engine if folds else structure.ENGINE_WINDOW
    free_energy = engine == structure.ENGINE_VIENNARNA

    fail: list[str] = []
    warn: list[str] = []
    values: list[str] = []
    offenders: list[tuple[Primer, structure.HairpinResult]] = []
    for primer, fold in folds:
        if free_energy:
            value = fold.delta_g_kcal_per_mol or 0.0
            values.append(f"{primer.name} {value:.1f} kcal/mol")
            detail = _hairpin_detail(
                primer,
                fold,
                f"{primer.name} folds to {value:.1f} kcal/mol over a {fold.stem_bp} bp stem "
                f"({fold.structure})",
            )
            if fold.three_prime_involved and value <= settings.hairpin_three_prime_dg_fail_kcal_per_mol:
                fail.append(detail)
                offenders.append((primer, fold))
            elif value <= settings.hairpin_dg_warn_kcal_per_mol:
                warn.append(detail)
                offenders.append((primer, fold))
        else:
            # The 3' threshold is read against the longest 3'-involved stem, not
            # against the longest stem overall. Reading it against the longest
            # stem lets a longer internal stem mask a shorter 3'-anchored one and
            # silently drops a FAIL that section 7.5 check 6 requires, because a
            # stem sequestering the 3' end is what stops the primer extending.
            anchored = fold.worst_three_prime
            if anchored is not None and anchored.stem_bp != fold.stem_bp:
                values.append(
                    f"{primer.name} {fold.stem_bp} bp stem, {anchored.stem_bp} bp with the 3' end in it"
                )
            else:
                values.append(f"{primer.name} {fold.stem_bp} bp stem")
            if anchored is not None and anchored.stem_bp >= settings.hairpin_window_stem_three_prime_fail_bp:
                fail.append(
                    _hairpin_detail(
                        primer, anchored, f"{primer.name} folds over a {anchored.stem_bp} bp stem"
                    )
                )
                offenders.append((primer, anchored))
            elif fold.stem_bp >= settings.hairpin_window_stem_warn_bp:
                warn.append(
                    _hairpin_detail(primer, fold, f"{primer.name} folds over a {fold.stem_bp} bp stem")
                )
                offenders.append((primer, fold))
    segment_advice = _hairpin_segment_advice(offenders)

    metric = (
        f"minimum free energy in kcal/mol, ViennaRNA {structure.viennarna_version()} with DNA "
        "parameters (dna_mathews2004)"
        if free_energy
        else "longest contiguous stem in base pairs, documented sliding-window score"
    )
    threshold = (
        f"warn at {settings.hairpin_dg_warn_kcal_per_mol:.1f} kcal/mol, fail at "
        f"{settings.hairpin_three_prime_dg_fail_kcal_per_mol:.1f} kcal/mol with the 3' end in the stem"
        if free_energy
        else (
            f"warn at {settings.hairpin_window_stem_warn_bp} bp stem, fail at "
            f"{settings.hairpin_window_stem_three_prime_fail_bp} bp with the 3' end in the stem"
        )
    )
    observed = "; ".join(values)
    if fail:
        return _result(
            "primer.hairpin",
            Severity.FAIL,
            f"{_subject(len(fail), 'primer', 'folds', 'fold')} strongly with the 3' end inside the "
            f"stem: {'; '.join(fail)}. A hairpin that sequesters the 3' end stops the polymerase "
            f"extending the primer, so this will not amplify.{segment_advice} Measured as {metric}.",
            observed=observed,
            threshold=threshold,
        )
    if warn:
        return _result(
            "primer.hairpin",
            Severity.WARN,
            f"{_subject(len(warn), 'primer', 'folds', 'fold')}: {'; '.join(warn)}. The 3' end is "
            "not in the stem, so the primer can still be extended once it anneals, but the fold "
            f"competes with annealing and may cost yield.{segment_advice} Measured as {metric}. "
            "Raising the annealing temperature also helps.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.hairpin",
        Severity.PASS,
        f"No primer folds past the threshold ({observed}). Measured as {metric}. No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 7. primer.self_dimer
# ---------------------------------------------------------------------------


def check_self_dimer(context: Context) -> CheckResult:
    """Section 7.5 check 7: WARN on extendable 3' self-complementarity.

    Scoring is documented in `structure.py`. Both numbers are reported, but the
    3' one is the one that matters: section 7.4 says a 3' dimer is extendable
    and produces artifact that consumes the reaction.
    """
    settings = context.settings
    offenders: list[str] = []
    values: list[str] = []
    for primer in context.design.primers:
        score = structure.self_dimer(primer.sequence)
        values.append(f"{primer.name} any {score.any_score} bp, 3' {score.three_prime_score} bp")
        if score.three_prime_score > settings.max_self_complementarity_end_bp:
            offenders.append(
                f"{primer.name} pairs with itself over {score.three_prime_score} bp ending at its "
                f"own 3' terminus, over the limit of {settings.max_self_complementarity_end_bp:.0f} bp; "
                "this dimer is extendable, so redesign the 3' end"
            )
        elif score.any_score > settings.max_self_complementarity_any_bp:
            offenders.append(
                f"{primer.name} pairs with itself over {score.any_score} bp internally, over the "
                f"limit of {settings.max_self_complementarity_any_bp:.0f} bp; the 3' end is free, so "
                "it will still extend, but the dimer competes for primer"
            )
    observed = "; ".join(values)
    threshold = (
        f"at most {settings.max_self_complementarity_any_bp:.0f} bp internally and "
        f"{settings.max_self_complementarity_end_bp:.0f} bp at the 3' end"
    )
    if offenders:
        return _result(
            "primer.self_dimer",
            Severity.WARN,
            f"{len(offenders)} self-dimer {_plural(len(offenders), 'problem')}: "
            f"{'; '.join(offenders)}. Shifting the binding region by two or three nucleotides "
            "usually breaks a self-dimer without changing the amplicon.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.self_dimer",
        Severity.PASS,
        f"No primer self-dimerises past {threshold} ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 8. primer.hetero_dimer
# ---------------------------------------------------------------------------


def check_hetero_dimer(context: Context) -> CheckResult | None:
    """Section 7.5 check 8: WARN on extendable 3' complementarity between a pair."""
    pairs = context.design.primer_pairs()
    if not pairs:
        return None
    settings = context.settings
    offenders: list[str] = []
    values: list[str] = []
    for forward, reverse in pairs:
        score = structure.hetero_dimer(forward.sequence, reverse.sequence)
        label = f"{forward.name}/{reverse.name}"
        values.append(f"{label} any {score.any_score} bp, 3' {score.three_prime_score} bp")
        extendable = forward.name if score.three_prime_partner == "forward" else reverse.name
        if score.three_prime_score > settings.max_pair_complementarity_end_bp:
            offenders.append(
                f"{label} pair over {score.three_prime_score} bp ending at the 3' terminus of "
                f"{extendable}, over the limit of {settings.max_pair_complementarity_end_bp:.0f} bp; "
                f"the polymerase will extend {extendable} on the other primer and make primer dimer "
                "instead of product, so redesign that 3' end"
            )
        elif score.any_score > settings.max_pair_complementarity_any_bp:
            offenders.append(
                f"{label} pair over {score.any_score} bp internally, over the limit of "
                f"{settings.max_pair_complementarity_any_bp:.0f} bp; neither 3' end is involved, so "
                "the duplex is not extendable, but it sequesters primer"
            )
    observed = "; ".join(values)
    threshold = (
        f"at most {settings.max_pair_complementarity_any_bp:.0f} bp internally and "
        f"{settings.max_pair_complementarity_end_bp:.0f} bp at either 3' end"
    )
    if offenders:
        return _result(
            "primer.hetero_dimer",
            Severity.WARN,
            f"{len(offenders)} hetero-dimer {_plural(len(offenders), 'problem')}: "
            f"{'; '.join(offenders)}. Move whichever binding region is easier to move; a shift of "
            "two or three nucleotides usually removes the complementarity.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.hetero_dimer",
        Severity.PASS,
        f"No pair dimerises past {threshold} ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 9. primer.specificity_in_template
# ---------------------------------------------------------------------------


def check_specificity(context: Context) -> CheckResult:
    """Section 7.5 check 9: FAIL on multiple binding sites, FAIL on zero.

    Both strands of every supplied template are searched, because a primer
    binding region occurs on the strand opposite the one it anneals to and a
    forward-only search would report every reverse primer as absent.
    """
    templates = context.request.template_set
    zero: list[str] = []
    many: list[str] = []
    values: list[str] = []
    for primer in context.design.primers:
        locations: list[str] = []
        for name, sequence in templates.items():
            for hit in find_both_strands(sequence, primer.binding):
                locations.append(f"{name}:{hit.start}..{hit.end}({hit.strand:+d})")
        values.append(f"{primer.name} {len(locations)}")
        if not locations:
            zero.append(
                f"{primer.name} binding region {primer.binding} occurs nowhere in the supplied "
                "templates; check that the right template was supplied and that the coordinates "
                "match the sequence given"
            )
        elif len(locations) > 1:
            many.append(
                f"{primer.name} binding region {primer.binding} occurs {len(locations)} times "
                f"({', '.join(locations)}); move it into a unique part of the template or lengthen "
                "it until it is unique"
            )
    observed = "; ".join(values)
    threshold = "exactly one occurrence per primer across the supplied template set"
    if zero or many:
        problems = zero + many
        return _result(
            "primer.specificity_in_template",
            Severity.FAIL,
            f"{len(problems)} specificity {_plural(len(problems), 'problem')}: "
            f"{'; '.join(problems)}. A primer with no site does not amplify and a primer with two "
            "gives a mixture of products, so neither can be ordered as it stands.",
            observed=observed,
            threshold=threshold,
        )
    return _result(
        "primer.specificity_in_template",
        Severity.PASS,
        f"Every primer binds exactly once across the {len(templates)} supplied "
        f"{_plural(len(templates), 'template')} ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 10. primer.homopolymer
# ---------------------------------------------------------------------------


def check_homopolymer(context: Context) -> CheckResult:
    """Section 7.5 check 10: WARN on a run above the configured length."""
    limit = context.settings.primer_max_homopolymer_run_nt
    offenders: list[str] = []
    longest: list[str] = []
    for primer in context.design.primers:
        runs = homopolymer_runs(primer.sequence, min_length=limit + 1)
        longest.append(f"{primer.name} {max((run.length for run in runs), default=0)}")
        for run in runs:
            offenders.append(
                f"{primer.name} has {run.length} consecutive {run.base} at {run.start}..{run.end}, "
                f"over the limit of {limit}; shift the binding region past the run, or trim the "
                "primer so the run falls outside it"
            )
    observed = "longest run per primer: " + "; ".join(longest)
    threshold = f"at most {limit} identical consecutive nucleotides"
    if offenders:
        return _result(
            "primer.homopolymer",
            Severity.WARN,
            f"{len(offenders)} homopolymer {_plural(len(offenders), 'run')} over the limit: "
            f"{'; '.join(offenders)}. A long run slips during synthesis and during polymerase "
            "extension, which shows up as a ladder of products rather than one band.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "primer.homopolymer",
        Severity.PASS,
        f"No primer carries a run over {limit} nucleotides ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 11. gibson.overlap_length
# ---------------------------------------------------------------------------


def _gibson_junctions(context: Context) -> list[Junction]:
    return [junction for junction in context.design.junctions if junction.kind == "gibson_homology"]


def check_gibson_overlap_length(context: Context) -> CheckResult | None:
    """Section 7.5 check 11: FAIL when terminal homology is outside the window."""
    junctions = _gibson_junctions(context)
    if not junctions:
        return None
    settings = context.settings
    low, high = settings.gibson_overlap_min_bp, settings.gibson_overlap_max_bp
    offenders: list[str] = []
    values: list[str] = []
    for junction in junctions:
        length = junction.length_bp
        label = f"{junction.left_fragment} to {junction.right_fragment}"
        values.append(f"{label} {length} bp")
        if length < low:
            offenders.append(
                f"{label} shares only {length} bp, under the {low} bp minimum; extend the 5' tail "
                f"of the {junction.right_fragment} forward primer by {low - length} bp so it "
                f"reaches further into {junction.left_fragment}"
            )
        elif length > high:
            offenders.append(
                f"{label} shares {length} bp, over the {high} bp maximum; trim the 5' tail of the "
                f"{junction.right_fragment} forward primer by {length - high} bp, which shortens "
                "the oligo without changing the join"
            )
    observed = "; ".join(values)
    threshold = f"{low} to {high} bp terminal homology"
    if offenders:
        return _result(
            "gibson.overlap_length",
            Severity.FAIL,
            f"{_subject(len(offenders), 'Gibson junction', 'is', 'are')} outside the "
            f"{threshold} window: {'; '.join(offenders)}. An overlap under the minimum does not "
            "survive the exonuclease chew-back and the fragments will not join.",
            observed=observed,
            threshold=threshold,
        )
    return _result(
        "gibson.overlap_length",
        Severity.PASS,
        f"All {len(junctions)} {_plural(len(junctions), 'junction')} share {threshold} ({observed}). "
        "No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 12. gibson.overlap_tm
# ---------------------------------------------------------------------------


def check_gibson_overlap_tm(context: Context) -> CheckResult | None:
    """Section 7.5 check 12: WARN when an overlap Tm is below the floor."""
    junctions = _gibson_junctions(context)
    if not junctions:
        return None
    floor = context.settings.gibson_overlap_min_tm_c
    offenders: list[str] = []
    values: list[str] = []
    for junction in junctions:
        value = context.tm(junction.sequence)
        label = f"{junction.left_fragment} to {junction.right_fragment}"
        values.append(f"{label} {value:.1f} C")
        if value < floor:
            offenders.append(
                f"{label} melts at {value:.1f} C, {floor - value:.1f} C under the {floor:.1f} C "
                f"floor; extend that homology arm, or move the junction into a GC-richer part of "
                f"{junction.left_fragment}"
            )
    observed = "; ".join(values)
    threshold = f"at least {floor:.1f} C per overlap"
    if offenders:
        return _result(
            "gibson.overlap_tm",
            Severity.WARN,
            f"{_subject(len(offenders), 'Gibson overlap', 'melts', 'melt')} below "
            f"{floor:.1f} C: {'; '.join(offenders)}. The assembly incubation is at "
            f"{GIBSON_INCUBATION_C:.0f} C, so an overlap melting below that anneals poorly and the "
            "junction forms inefficiently.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "gibson.overlap_tm",
        Severity.PASS,
        f"Every overlap melts at or above {floor:.1f} C ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 13. gibson.overlap_uniqueness
# ---------------------------------------------------------------------------


def check_gibson_overlap_uniqueness(context: Context) -> CheckResult | None:
    """Section 7.5 check 13: FAIL when two junctions share enough homology to mis-assemble."""
    junctions = _gibson_junctions(context)
    if len(junctions) < 2:
        return None
    limit = context.settings.gibson_junction_max_shared_homology_bp
    offenders: list[str] = []
    worst = 0
    for index, first in enumerate(junctions):
        for second in junctions[index + 1 :]:
            shared = max(
                structure.longest_shared_complementarity(first.sequence, second.sequence),
                _longest_common_substring(first.sequence, second.sequence),
            )
            worst = max(worst, shared)
            if shared >= limit:
                offenders.append(
                    f"the {first.left_fragment} to {first.right_fragment} junction and the "
                    f"{second.left_fragment} to {second.right_fragment} junction share {shared} bp "
                    f"of homology, at or over the {limit} bp limit; move one junction to a "
                    "different position in its fragment so the two arms no longer resemble each other"
                )
    observed = f"longest homology shared between two junctions: {worst} bp"
    threshold = f"under {limit} bp shared between any two junctions"
    if offenders:
        return _result(
            "gibson.overlap_uniqueness",
            Severity.FAIL,
            f"{_subject(len(offenders), 'junction pair', 'shares', 'share')} homology: "
            f"{'; '.join(offenders)}. Two junctions that resemble each other let fragments join in "
            "the wrong order, which gives a mixture of plasmids rather than the intended one.",
            observed=observed,
            threshold=threshold,
        )
    return _result(
        "gibson.overlap_uniqueness",
        Severity.PASS,
        f"No two junctions share {limit} bp or more ({observed}), so only the intended order can "
        "assemble. No change needed.",
        observed=observed,
        threshold=threshold,
    )


def _longest_common_substring(first: str, second: str) -> int:
    """Longest identical stretch shared by two sequences, in base pairs.

    Two junctions can mis-assemble two ways: one arm complementary to the
    other (which `structure.longest_shared_complementarity` measures) or the
    two arms being the same sequence, so a fragment can join at either. This
    measures the second.
    """
    top, other = clean_sequence(first), clean_sequence(second)
    previous = [0] * (len(other) + 1)
    best = 0
    for i in range(1, len(top) + 1):
        current = [0] * (len(other) + 1)
        for j in range(1, len(other) + 1):
            if top[i - 1] == other[j - 1]:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best


# ---------------------------------------------------------------------------
# 14. gg.enzyme_site_internal
# ---------------------------------------------------------------------------


def check_enzyme_site_internal(context: Context) -> CheckResult | None:
    """Section 7.5 check 14: FAIL with a domestication report.

    Both strands are searched, per Appendix D. The structured report goes in
    `CheckResult.remediation` and the readable form in `message`, so the check
    is actionable per section 5.4 rule 2 and assertable by the gold harness.
    """
    enzyme = context.enzyme
    if enzyme is None:
        return None
    offenders: list[str] = []
    total = 0
    for fragment in context.request.fragments:
        hits = find_recognition_sites(fragment.sequence, enzyme, circular=fragment.is_circular)
        total += len(hits)
        for hit in hits:
            offenders.append(
                f"{fragment.name} carries {enzyme.recognition} at {hit.start}..{hit.end} on the "
                f"{'forward' if hit.strand > 0 else 'reverse'} strand"
            )
    observed = f"{total} internal {enzyme.recognition} {_plural(total, 'site')}"
    threshold = f"no {enzyme.recognition} site inside any fragment"
    if not offenders:
        return _result(
            "gg.enzyme_site_internal",
            Severity.PASS,
            f"No fragment carries an internal {enzyme.name} ({enzyme.recognition}) site on either "
            "strand, so the one-pot digestion cuts only at the designed junctions. No "
            "domestication needed.",
            observed=observed,
            threshold=threshold,
        )
    report = context.design.domestication
    remediation: list[str] = []
    plan = ""
    if report is not None:
        remediation = [edit.summary for edit in report.edits]
        remediation.extend(
            f"{site.fragment} {site.site_start}..{site.site_end}: {site.reason}"
            for site in report.unresolved
        )
        if report.edits:
            plan = (
                " Domestication plan, "
                f"{len(report.edits)} {_plural(len(report.edits), 'edit')}: "
                + "; ".join(edit.summary for edit in report.edits)
                + "."
            )
        if report.unresolved:
            plan += (
                f" {len(report.unresolved)} {_plural(len(report.unresolved), 'site')} could not be "
                "domesticated: " + "; ".join(site.reason for site in report.unresolved)
            )
        if report.host_codon_usage_status == "unknown":
            plan += (
                " Host codon frequencies are reported as UNKNOWN because no host codon usage table "
                "is bundled with this build; each edit was chosen as the minimal silent change that "
                "destroys the site."
            )
    return _result(
        "gg.enzyme_site_internal",
        Severity.FAIL,
        f"{total} internal {enzyme.name} ({enzyme.recognition}) {_plural(total, 'site')} would be "
        f"cut during the one-pot reaction, destroying the fragment: {'; '.join(offenders)}. "
        f"Domesticate the fragments before ordering, or switch to a Type IIS enzyme whose site is "
        f"absent from all fragments.{plan}",
        observed=observed,
        threshold=threshold,
        remediation=remediation or None,
    )


# ---------------------------------------------------------------------------
# 15, 16, 17: the overhang checks
# ---------------------------------------------------------------------------


def _overhangs(context: Context) -> list[Junction]:
    return [junction for junction in context.design.junctions if junction.kind == "golden_gate_overhang"]


def check_overhang_uniqueness(context: Context) -> CheckResult | None:
    """Section 7.5 check 15: FAIL unless all fusion overhangs are distinct.

    Appendix D: "all overhangs in one assembly distinct". Two overhangs are
    treated as not distinct when they are the same sequence, and also when one
    is the reverse complement of the other, because that lets the downstream
    fragment ligate into the other junction in the opposite orientation. The
    second reading is a deliberate extension of the literal rule and is called
    out here so a reviewer can see it.
    """
    junctions = _overhangs(context)
    if len(junctions) < 2:
        return None
    offenders: list[str] = []
    for index, first in enumerate(junctions):
        for second in junctions[index + 1 :]:
            first_label = f"{first.left_fragment} to {first.right_fragment}"
            second_label = f"{second.left_fragment} to {second.right_fragment}"
            if first.sequence == second.sequence:
                offenders.append(
                    f"the {first_label} and {second_label} junctions both use the overhang "
                    f"{first.sequence}; either junction can accept either fragment, so change one "
                    "of them by moving its junction a base or two along the fragment"
                )
            elif first.sequence == reverse_complement(second.sequence):
                offenders.append(
                    f"the {first_label} overhang {first.sequence} is the reverse complement of the "
                    f"{second_label} overhang {second.sequence}, which lets a fragment ligate into "
                    "the wrong junction backwards; move one junction so the two no longer match"
                )
    observed = "overhangs: " + ", ".join(junction.sequence for junction in junctions)
    threshold = "every fusion overhang distinct, and distinct from every other's reverse complement"
    if offenders:
        return _result(
            "gg.overhang_uniqueness",
            Severity.FAIL,
            f"{len(offenders)} overhang {_plural(len(offenders), 'collision')}: "
            f"{'; '.join(offenders)}. A one-pot assembly with a repeated overhang produces a "
            "mixture of orders and orientations rather than the intended construct.",
            observed=observed,
            threshold=threshold,
        )
    return _result(
        "gg.overhang_uniqueness",
        Severity.PASS,
        f"All {len(junctions)} fusion overhangs are distinct ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


def check_overhang_not_palindromic(context: Context) -> CheckResult | None:
    """Section 7.5 check 16: FAIL when an overhang is its own reverse complement."""
    junctions = _overhangs(context)
    if not junctions:
        return None
    offenders: list[str] = []
    for junction in junctions:
        if junction.sequence == reverse_complement(junction.sequence):
            offenders.append(
                f"the {junction.left_fragment} to {junction.right_fragment} overhang "
                f"{junction.sequence} is its own reverse complement, so the fragment can ligate "
                "in either orientation; move that junction by one base, which changes the overhang "
                "to a non-palindromic one"
            )
    observed = "overhangs: " + ", ".join(junction.sequence for junction in junctions)
    threshold = "no overhang equal to its own reverse complement"
    if offenders:
        return _result(
            "gg.overhang_not_palindromic",
            Severity.FAIL,
            f"{len(offenders)} palindromic {_plural(len(offenders), 'overhang')}: "
            f"{'; '.join(offenders)}. Half the ligation events will insert the fragment backwards, "
            "so the correct construct is at best a minority of the colonies.",
            observed=observed,
            threshold=threshold,
        )
    return _result(
        "gg.overhang_not_palindromic",
        Severity.PASS,
        f"No fusion overhang is palindromic ({observed}), so every fragment can only go in one "
        "way round. No change needed.",
        observed=observed,
        threshold=threshold,
    )


def check_overhang_composition(context: Context) -> CheckResult | None:
    """Section 7.5 check 17: WARN on an all-GC or an all-AT overhang."""
    junctions = _overhangs(context)
    if not junctions:
        return None
    offenders: list[str] = []
    for junction in junctions:
        label = f"the {junction.left_fragment} to {junction.right_fragment} overhang {junction.sequence}"
        fraction = gc_content(junction.sequence)
        if fraction == 1.0:
            offenders.append(
                f"{label} is all G and C, which ligates inefficiently because the overhang anneals "
                "too stably to exchange during cycling; move the junction so at least one A or T "
                "falls inside it"
            )
        elif fraction == 0.0:
            offenders.append(
                f"{label} is all A and T, which anneals too weakly to hold the two fragments "
                "together for the ligase; move the junction so at least one G or C falls inside it"
            )
    observed = "; ".join(
        f"{junction.sequence} {gc_content(junction.sequence) * 100:.0f}% GC" for junction in junctions
    )
    threshold = "no overhang all-GC or all-AT"
    if offenders:
        return _result(
            "gg.overhang_composition",
            Severity.WARN,
            f"{_subject(len(offenders), 'overhang', 'has', 'have')} an extreme composition: "
            f"{'; '.join(offenders)}. The assembly can still work, with reduced efficiency, so "
            "this is worth fixing rather than blocking.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "gg.overhang_composition",
        Severity.PASS,
        f"Every fusion overhang mixes GC and AT ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 18. assembly.fragment_order_defined
# ---------------------------------------------------------------------------


def check_fragment_order_defined(context: Context) -> CheckResult | None:
    """Section 7.5 check 18: FAIL when the junction topology admits more than one order.

    Each junction is identified by its joining sequence: a fusion overhang for
    Golden Gate, a terminal homology arm for Gibson, a restriction site for
    simple PCR cloning. An assembly has exactly one order when every junction
    sequence appears once, because then each fragment end can anneal to only
    one partner. A sequence appearing twice means two ends compete for the same
    partner and the product is a mixture.

    The remedy is branched on strategy, because the three strategies do not
    share one. Gibson and Golden Gate both let the designer choose the joining
    sequence, so moving the junction or adopting a published overhang set fixes
    the degeneracy at the design stage. Single-enzyme PCR cloning does not: the
    joining sequence is a restriction site, both ends carry the same one by
    construction, and no choice of position makes them distinct. There the real
    options are to use two different enzymes so the ends are no longer
    interchangeable, or to accept the mixture and screen colonies for
    orientation. Offering the Gibson remedy there would send the reader after a
    change that cannot be made.
    """
    junctions = context.design.junctions
    if len(junctions) < 2:
        return None
    seen: dict[str, list[str]] = {}
    for junction in junctions:
        seen.setdefault(junction.sequence, []).append(
            f"{junction.left_fragment} to {junction.right_fragment}"
        )
    ambiguous = {sequence: labels for sequence, labels in seen.items() if len(labels) > 1}
    observed = f"{len(junctions)} junctions, {len(seen)} distinct joining sequences"
    threshold = "one distinct joining sequence per junction"
    if ambiguous:
        detail = "; ".join(
            f"{sequence} joins {' and '.join(labels)}" for sequence, labels in sorted(ambiguous.items())
        )
        if context.request.strategy == "pcr_cloning":
            remedy = (
                "With a single restriction enzyme both fragment ends carry the same site, so no "
                "junction position makes them distinct. Either cut with two different enzymes so "
                "the two ends are no longer interchangeable, or run the ligation as it stands and "
                "screen colonies for the orientation you want, which is the standard way this is "
                "handled when a second enzyme is not available."
            )
        else:
            remedy = (
                "Give each junction its own joining sequence by moving the junction position, or "
                "by supplying a published overhang standard whose set is distinct by construction."
            )
        return _result(
            "assembly.fragment_order_defined",
            Severity.FAIL,
            f"The junction topology admits more than one assembly order: {detail}. {remedy} Until "
            "then the reaction cannot be relied on to produce the intended order.",
            observed=observed,
            threshold=threshold,
        )
    return _result(
        "assembly.fragment_order_defined",
        Severity.PASS,
        f"Each of the {len(junctions)} junctions has its own joining sequence, so the fragments can "
        f"assemble in exactly one order: {' to '.join(context.design.fragment_order)}. No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# 19. assembly.amplicon_size
# ---------------------------------------------------------------------------


def check_amplicon_size(context: Context) -> CheckResult | None:
    """Section 7.5 check 19: WARN when an expected amplicon is outside the window."""
    amplicons = context.design.amplicons
    if not amplicons:
        return None
    settings = context.settings
    low, high = settings.amplicon_min_bp, settings.amplicon_max_bp
    offenders: list[str] = []
    values: list[str] = []
    for amplicon in amplicons:
        values.append(f"{amplicon.name} {amplicon.length_bp} bp")
        if amplicon.length_bp < low:
            offenders.append(
                f"{amplicon.name} is {amplicon.length_bp} bp, under the {low} bp floor; a product "
                "this short is hard to tell from primer dimer on a gel, so plan to check it by "
                "sequencing rather than by size"
            )
        elif amplicon.length_bp > high:
            offenders.append(
                f"{amplicon.name} is {amplicon.length_bp} bp, over the {high} bp ceiling; extend "
                f"the extension step to {PCR_EXTENSION_S_PER_KB} seconds per kilobase and expect "
                "reduced yield, or split the fragment and assemble it in two pieces"
            )
    observed = "; ".join(values)
    threshold = f"{low} to {high} bp per amplicon"
    if offenders:
        return _result(
            "assembly.amplicon_size",
            Severity.WARN,
            f"{_subject(len(offenders), 'amplicon', 'is', 'are')} outside the {threshold} "
            f"window: {'; '.join(offenders)}.",
            observed=observed,
            threshold=threshold,
            tier="B",
        )
    return _result(
        "assembly.amplicon_size",
        Severity.PASS,
        f"Every expected amplicon is within {threshold} ({observed}). No change needed.",
        observed=observed,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

# In section 7.5 table order.
CHECKS = (
    check_tm_in_range,
    check_pair_tm_delta,
    check_gc_content,
    check_length,
    check_three_prime_stability,
    check_hairpin,
    check_self_dimer,
    check_hetero_dimer,
    check_specificity,
    check_homopolymer,
    check_gibson_overlap_length,
    check_gibson_overlap_tm,
    check_gibson_overlap_uniqueness,
    check_enzyme_site_internal,
    check_overhang_uniqueness,
    check_overhang_not_palindromic,
    check_overhang_composition,
    check_fragment_order_defined,
    check_amplicon_size,
)


def run_all(design: AssemblyDesign, settings: Settings) -> list[CheckResult]:
    """Every applicable section 7.5 check, in table order.

    A check that returns None did not apply to this design and is omitted, per
    the APPLICABILITY note in the module docstring.
    """
    context = Context(design=design, settings=settings)
    results: list[CheckResult] = []
    for check in CHECKS:
        outcome = check(context)
        if outcome is not None:
            results.append(outcome)
    return results
