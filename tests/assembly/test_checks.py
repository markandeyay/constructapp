"""Every one of the nineteen section 7.5 checks, proved to fire.

Source: the section 7.5 table and section 9.3 of the engine capability system
design. WP-06 writes the formal gold sets later; these tests prove each check
works now, and each follows the section 9.3 discipline: the named check must
report the expected severity, and no unexpected FAIL may appear.

Two harnesses are used. `one_fragment_design` builds a single-fragment
`pcr_cloning` design with exact pinned primers, which isolates the ten primer
checks and the amplicon check: with no junctions there is nothing for checks 11
to 18 to examine, so they are omitted and cannot interfere. `pinned_design` from
`fixtures` pins junctions as well, for the junction and overhang checks.

The binding region of every pinned primer is embedded in its fragment, so
`primer.specificity_in_template` passes and does not add noise to a test aimed
at another check. `test_specificity_*` breaks that deliberately.
"""

from __future__ import annotations

import pytest

from packages.core.schemas.assembly import AssemblyRequest, AssemblyThresholds, Fragment, Junction
from packages.core.sequence import reverse_complement
from packages.validation.assembly.checks import ALL_CHECK_IDS, APPLICABLE_CHECKS
from packages.validation.assembly.validator import AssemblyValidator
from tests.assembly import fixtures
from tests.assembly.fixtures import (
    FRAGMENT_A,
    FRAGMENT_B,
    clean_golden_gate_request,
    clean_request,
    design_from,
    pinned_design,
    primer,
    severity_of,
    unexpected_failures,
)

VALIDATOR = AssemblyValidator()

# Real flanking sequence for the synthetic fragments, from the fixture slices.
LEFT_FLANK = FRAGMENT_B[:40]
MIDDLE = FRAGMENT_A[40:100]
RIGHT_FLANK = FRAGMENT_B[120:170]


def one_fragment_design(
    forward_binding: str,
    reverse_binding: str,
    **request_kwargs: object,
):
    """A single-fragment pcr_cloning design with these two primers pinned.

    The fragment is built so each binding region occurs exactly once: real
    flanking sequence, the forward binding region, real middle sequence, the
    reverse complement of the reverse binding region, more real sequence. No
    junctions exist, so checks 11 to 18 are omitted and the primer checks are
    isolated.
    """
    sequence = LEFT_FLANK + forward_binding + MIDDLE + reverse_complement(reverse_binding) + RIGHT_FLANK
    fragment = Fragment(name="frag", sequence=sequence, source="synthetic from the fixture slices")
    base: dict[str, object] = {"strategy": "pcr_cloning", "fragments": [fragment]}
    base.update(request_kwargs)
    request = AssemblyRequest(**base)  # type: ignore[arg-type]
    forward_start = len(LEFT_FLANK)
    reverse_start = len(sequence) - len(RIGHT_FLANK) - len(reverse_binding)
    return pinned_design(
        request,
        [
            primer("frag_F", "frag", "forward", forward_binding, start=forward_start),
            primer("frag_R", "frag", "reverse", reverse_binding, start=reverse_start),
        ],
    )


# ---------------------------------------------------------------------------
# The catalogue itself
# ---------------------------------------------------------------------------


def test_all_nineteen_check_ids_are_the_section_7_5_table() -> None:
    """Nineteen checks, the exact ids, nothing added (section 7.5, section 6.4's rule)."""
    assert len(ALL_CHECK_IDS) == 19
    assert len(set(ALL_CHECK_IDS)) == 19
    assert set(ALL_CHECK_IDS) == {
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
    }


def test_every_check_is_applicable_to_some_strategy() -> None:
    """No check is dead code: each of the nineteen runs for at least one strategy."""
    reachable = {check_id for check_ids in APPLICABLE_CHECKS.values() for check_id in check_ids}
    assert reachable == set(ALL_CHECK_IDS)
    for strategy, check_ids in APPLICABLE_CHECKS.items():
        assert set(check_ids) <= set(ALL_CHECK_IDS), strategy


@pytest.mark.parametrize("strategy", sorted(APPLICABLE_CHECKS))
def test_no_check_outside_the_strategys_applicable_set(strategy: str) -> None:
    """A report never contains a check the strategy does not run."""
    if strategy == "golden_gate":
        request = clean_golden_gate_request()
    else:
        request = clean_request(strategy=strategy)
    report = VALIDATOR.validate(design_from(request))
    assert {check.check_id for check in report.checks} <= set(APPLICABLE_CHECKS[strategy])


# ---------------------------------------------------------------------------
# Tier A: the clean cases
# ---------------------------------------------------------------------------


def test_clean_gibson_design_is_tier_a() -> None:
    """A Tier A case: no FAIL, no WARN, no UNKNOWN (section 3.4, section 9.2)."""
    report = VALIDATOR.validate(design_from(clean_request()))
    offenders = [(check.check_id, check.severity.value) for check in report.checks if check.severity.value != "pass"]
    assert offenders == [], offenders
    assert report.overall.value == "pass"


def test_clean_golden_gate_design_is_tier_a() -> None:
    report = VALIDATOR.validate(design_from(clean_golden_gate_request()))
    offenders = [(check.check_id, check.severity.value) for check in report.checks if check.severity.value != "pass"]
    assert offenders == [], offenders
    assert report.overall.value == "pass"


def test_clean_pcr_cloning_design_is_tier_a() -> None:
    report = VALIDATOR.validate(design_from(clean_request(strategy="pcr_cloning")))
    offenders = [(check.check_id, check.severity.value) for check in report.checks if check.severity.value != "pass"]
    assert offenders == [], offenders


# ---------------------------------------------------------------------------
# 1. primer.tm_in_range
# ---------------------------------------------------------------------------


def test_tm_in_range_warns_outside_the_window() -> None:
    """Section 7.5 check 1: WARN outside the window.

    This primer melts at 54.1 C, which is 5.9 C from the 60 C target: outside the
    3.0 C warn tolerance and inside the 10.0 C fail tolerance.
    """
    design = one_fragment_design("ATCATGATTAATCAAGCGATATCAGG", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.tm_in_range") == "warn"
    assert unexpected_failures(report, set()) == []


def test_tm_in_range_fails_far_outside_the_window() -> None:
    """Section 7.5 check 1: FAIL far outside the window."""
    design = one_fragment_design("ATTAATTAATTAATTAATAA", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.tm_in_range") == "fail"
    assert unexpected_failures(report, {"primer.tm_in_range"}) == []


def test_tm_in_range_message_names_the_primer_and_the_window() -> None:
    """Section 5.4 rule 2: the message says what to do, not just what is wrong."""
    report = VALIDATOR.validate(one_fragment_design("ATTAATTAATTAATTAATAA", FRAGMENT_A[100:120]))
    check = next(item for item in report.checks if item.check_id == "primer.tm_in_range")
    assert "frag_F" in check.message
    assert "60.0 C target" in check.message
    assert check.threshold is not None and "target" in check.threshold
    assert check.citation is not None and "Primer3" in check.citation


# ---------------------------------------------------------------------------
# 2. primer.pair_tm_delta
# ---------------------------------------------------------------------------


def test_pair_tm_delta_warns_on_a_large_difference() -> None:
    """Section 7.5 check 2: WARN when a pair is further apart than the threshold."""
    design = one_fragment_design("ATATTAATTAATTAAGCGATAT", FRAGMENT_A[0:26])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.pair_tm_delta") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.pair_tm_delta")
    assert "lengthen" in check.message and "shorten" in check.message


# ---------------------------------------------------------------------------
# 3. primer.gc_content
# ---------------------------------------------------------------------------


def test_gc_content_warns_below_the_window() -> None:
    design = one_fragment_design("ATATTAATTAATTAAGCGATATCGA", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.gc_content") == "warn"


def test_gc_content_warns_above_the_window() -> None:
    design = one_fragment_design("GCGCGGCGGCGGCGGACGGCG", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.gc_content") == "warn"


# ---------------------------------------------------------------------------
# 4. primer.length
# ---------------------------------------------------------------------------


def test_length_warns_when_the_binding_region_is_too_short() -> None:
    design = one_fragment_design(FRAGMENT_A[0:12], FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.length") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.length")
    assert "18 nt minimum" in check.message


def test_length_warns_when_the_whole_oligo_is_over_the_ordering_limit() -> None:
    """The tail counts towards the ordering limit even though it does not anneal."""
    base = one_fragment_design(FRAGMENT_A[0:20], FRAGMENT_A[100:120])
    tailed = base.primers[0].model_copy(update={"tail": FRAGMENT_B[0:45]})
    design = base.model_copy(update={"primers": [tailed, base.primers[1]]})
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.length") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.length")
    assert "ordering limit" in check.message


# ---------------------------------------------------------------------------
# 5. primer.three_prime_stability
# ---------------------------------------------------------------------------


def test_three_prime_stability_warns_on_a_terminal_t() -> None:
    """Section 7.5 check 5: the 3' base is not T."""
    design = one_fragment_design(FRAGMENT_B[40:62] + "ACGT", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.three_prime_stability") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.three_prime_stability")
    assert "ends in T" in check.message


def test_three_prime_stability_warns_on_a_gc_rich_3_prime_window() -> None:
    """Section 7.5 check 5: the last five bases are not excessively GC-rich."""
    design = one_fragment_design(FRAGMENT_B[40:60] + "GCCGC", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.three_prime_stability") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.three_prime_stability")
    assert "G or C" in check.message


# ---------------------------------------------------------------------------
# 6. primer.hairpin
# ---------------------------------------------------------------------------


def test_hairpin_fails_on_a_three_prime_stem_with_the_window_engine() -> None:
    """Section 7.5 check 6: FAIL when a 3' stem is past the hard threshold.

    The engine is pinned to `window` so the test is deterministic whether or not
    ViennaRNA is installed in the environment running it.
    """
    stem = "GCGCGCGC" + "AAAA" + "GCGCGCGC"
    design = one_fragment_design(stem, FRAGMENT_A[100:120], hairpin_engine="window")
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hairpin") == "fail"
    check = next(item for item in report.checks if item.check_id == "primer.hairpin")
    assert "sliding-window" in check.message
    assert "bp stem" in (check.threshold or "")


def test_hairpin_warns_on_an_internal_stem_with_the_window_engine() -> None:
    design = one_fragment_design(
        "GCGCGC" + "AAAA" + "GCGCGC" + FRAGMENT_B[40:52], FRAGMENT_A[100:120], hairpin_engine="window"
    )
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hairpin") == "warn"


def test_hairpin_is_unknown_when_viennarna_is_demanded_and_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Section 3.3 constraint 4: a check that cannot be evaluated is UNKNOWN with a reason."""
    from packages.validation.assembly import structure

    monkeypatch.setattr(structure, "hairpin_engine_available", lambda: False)
    design = one_fragment_design(FRAGMENT_A[0:20], FRAGMENT_A[100:120], hairpin_engine="viennarna")
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hairpin") == "unknown"
    check = next(item for item in report.checks if item.check_id == "primer.hairpin")
    assert "ViennaRNA is not importable" in check.message
    # An UNKNOWN never improves the verdict and never reads as a pass.
    assert check not in [item for item in report.checks if item.severity.value == "pass"]


def test_hairpin_uses_free_energy_when_viennarna_is_available() -> None:
    """Open question Q6: ViennaRNA is preferred for hairpin free energy when installed."""
    from packages.validation.assembly import structure

    if not structure.hairpin_engine_available():
        pytest.skip("ViennaRNA is not installed in this environment")
    stem = "GCGCGCGC" + "AAAA" + "GCGCGCGC"
    design = one_fragment_design(stem, FRAGMENT_A[100:120], hairpin_engine="viennarna")
    report = VALIDATOR.validate(design)
    check = next(item for item in report.checks if item.check_id == "primer.hairpin")
    assert check.severity.value == "fail"
    assert "kcal/mol" in check.message
    assert "ViennaRNA" in check.message


def test_auto_engine_prefers_viennarna_when_it_is_available() -> None:
    from packages.validation.assembly import structure

    if not structure.hairpin_engine_available():
        pytest.skip("ViennaRNA is not installed in this environment")
    design = one_fragment_design("GCGCGCGCAAAAGCGCGCGC", FRAGMENT_A[100:120], hairpin_engine="auto")
    report = VALIDATOR.validate(design)
    check = next(item for item in report.checks if item.check_id == "primer.hairpin")
    assert "kcal/mol" in check.message


# The masking oligo from tests/assembly/test_structure.py, used here as a
# primer. A 10 bp internal stem sits upstream and a 7 bp stem pairs the first
# seven bases against the last seven, so the FAIL condition section 7.5 check 6
# specifies is present but hides behind the longer internal stem.
MASKING_PRIMER = "ACTTGCAGGTCAATGCTATATAGCATTGACCAAATTTAAATTTTTGCAAGT"


def masking_design(tail_nt: int, **request_kwargs: object):
    """A pcr_cloning design whose forward primer is `MASKING_PRIMER`.

    `tail_nt` splits the oligo into a fixed 5' tail and a template-binding
    region, so the segment labelling is exercised on a real report rather than
    only at the structure level.
    """
    tail, binding = MASKING_PRIMER[:tail_nt], MASKING_PRIMER[tail_nt:]
    reverse_binding = FRAGMENT_A[100:120]
    sequence = LEFT_FLANK + binding + MIDDLE + reverse_complement(reverse_binding) + RIGHT_FLANK
    fragment = Fragment(name="frag", sequence=sequence, source="synthetic from the fixture slices")
    base: dict[str, object] = {"strategy": "pcr_cloning", "fragments": [fragment]}
    base.update(request_kwargs)
    request = AssemblyRequest(**base)  # type: ignore[arg-type]
    reverse_start = len(sequence) - len(RIGHT_FLANK) - len(reverse_binding)
    return pinned_design(
        request,
        [
            primer("frag_F", "frag", "forward", binding, tail=tail, start=len(LEFT_FLANK)),
            primer("frag_R", "frag", "reverse", reverse_binding, start=reverse_start),
        ],
    )


def test_hairpin_fails_on_a_three_prime_stem_masked_by_a_longer_internal_stem() -> None:
    """Regression: a longer internal stem must not swallow a 3'-anchored FAIL.

    Before the fix the single reported stem was chosen by length, so this primer
    reported a 10 bp internal stem with `three_prime_involved` False and the
    check returned WARN. The 7 bp stem that sequesters the 3' end, which section
    7.5 check 6 makes a FAIL, was never looked at. The severity-maximising
    result is the 3'-involved one whenever it reaches the FAIL threshold.
    """
    design = masking_design(tail_nt=20, hairpin_engine="window")
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hairpin") == "fail"
    check = next(item for item in report.checks if item.check_id == "primer.hairpin")
    assert "7 bp stem" in check.message, "the FAIL must be reported on the 3'-anchored stem"
    # `observed` carries both numbers, so the reader can see why a 10 bp stem
    # produced a FAIL quoted at 7 bp rather than being left to wonder.
    assert "10 bp stem, 7 bp with the 3' end in it" in (check.observed or "")


def test_a_masked_three_prime_stem_below_the_threshold_still_only_warns() -> None:
    """The fix raises severity only when the 3' stem really reaches the FAIL level.

    With the FAIL stem configured above the 3'-anchored stem's 7 bp, the same
    primer must fall back to the internal stem's WARN. Otherwise the fix would
    have turned the false negative into a false positive.
    """
    design = masking_design(
        tail_nt=20,
        hairpin_engine="window",
        thresholds=AssemblyThresholds(hairpin_window_stem_three_prime_fail_bp=9),
    )
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hairpin") == "warn"


def test_the_hairpin_message_says_which_oligo_segment_each_arm_lies_in() -> None:
    """A stem length alone cannot be acted on; the segment says what is movable."""
    design = masking_design(tail_nt=20, hairpin_engine="window")
    report = VALIDATOR.validate(design)
    check = next(item for item in report.checks if item.check_id == "primer.hairpin")
    assert "5' arm at 1 to 7 in the fixed 5' tail" in check.message
    assert "3' arm at 45 to 51 in the template-binding region" in check.message
    # One arm is in the tail, so the message must not suggest moving the tail.
    assert "the tail cannot be moved" in check.message


def test_the_hairpin_message_offers_the_walkable_remedy_when_both_arms_are_movable() -> None:
    """With no tail, both arms are in the binding region and can be walked."""
    design = one_fragment_design(
        "GCGCGCGC" + "AAAA" + "GCGCGCGC", FRAGMENT_A[100:120], hairpin_engine="window"
    )
    report = VALIDATOR.validate(design)
    check = next(item for item in report.checks if item.check_id == "primer.hairpin")
    assert "Both arms of every stem reported lie in the template-binding region" in check.message


# ---------------------------------------------------------------------------
# The recalibrated window stem thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stem_bp", [4, 5])
def test_a_short_stem_no_longer_fires_the_window_hairpin_check(stem_bp: int) -> None:
    """Regression: 4 bp and 5 bp stems are below the recalibrated WARN of 6 bp.

    A 4 bp stem occurs in 0.90 of random 47 nt oligos, so flagging it reported
    nine correct designs in ten. The DNA energy model puts the stems this scan
    reports at 4 bp near -0.4 kcal/mol and at 5 bp near -2.1, against a WARN
    level of -2.0 that the primary engine concurs with in only about half of
    5 bp cases. Neither is a structure worth reporting.
    """
    arm = ("GCTAGC" * 2)[:stem_bp]
    stem = arm + "AAAA" + reverse_complement(arm)
    # Pad to a realistic primer length with sequence that adds no further stem.
    binding = stem + "AAATTTAAATTTAAATTT"[: 24 - len(stem)]
    design = one_fragment_design(binding, FRAGMENT_A[100:120], hairpin_engine="window")
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hairpin") == "pass"


def test_a_six_base_pair_stem_still_warns() -> None:
    """6 bp is the recalibrated WARN level, so it must fire at exactly 6."""
    arm = "GCTAGC"
    binding = arm + "AAAA" + reverse_complement(arm) + "AAATTTAAA"
    design = one_fragment_design(binding, FRAGMENT_A[100:120], hairpin_engine="window")
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hairpin") == "warn"


def test_the_window_thresholds_match_the_free_energy_levels_they_stand_in_for() -> None:
    """The two thresholds are a pair, and the 3' one is the harder of the two.

    The relation is what keeps the fallback from contradicting the engine it
    replaces: the 3' FAIL stem must sit above the WARN stem, exactly as
    HAIRPIN_THREE_PRIME_DG_FAIL_KCAL_PER_MOL sits below
    HAIRPIN_DG_WARN_KCAL_PER_MOL.
    """
    from packages.validation.assembly import constants

    assert constants.HAIRPIN_WINDOW_STEM_WARN_BP == 6
    assert constants.HAIRPIN_WINDOW_STEM_THREE_PRIME_FAIL_BP == 7
    assert (
        constants.HAIRPIN_WINDOW_STEM_THREE_PRIME_FAIL_BP > constants.HAIRPIN_WINDOW_STEM_WARN_BP
    )
    assert (
        constants.HAIRPIN_THREE_PRIME_DG_FAIL_KCAL_PER_MOL < constants.HAIRPIN_DG_WARN_KCAL_PER_MOL
    )


# ---------------------------------------------------------------------------
# 7. primer.self_dimer
# ---------------------------------------------------------------------------


def test_self_dimer_warns_on_an_extendable_three_prime_self_complementarity() -> None:
    """Section 7.5 check 7, with the section 7.4 point: the 3' case is the one that matters."""
    design = one_fragment_design(FRAGMENT_B[40:58] + "GGGGCCCC", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.self_dimer") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.self_dimer")
    assert "extendable" in check.message or "3' terminus" in check.message


# ---------------------------------------------------------------------------
# 8. primer.hetero_dimer
# ---------------------------------------------------------------------------


def test_hetero_dimer_warns_on_an_extendable_three_prime_pair_complementarity() -> None:
    """Section 7.5 check 8. A 3' hetero-dimer consumes the reaction (section 7.4)."""
    forward = FRAGMENT_B[40:58] + "GGGGGCCCCC"
    reverse = FRAGMENT_A[100:118] + "GGGGGCCCCC"
    design = one_fragment_design(forward, reverse)
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.hetero_dimer") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.hetero_dimer")
    assert "primer dimer" in check.message or "sequesters" in check.message


# ---------------------------------------------------------------------------
# 9. primer.specificity_in_template
# ---------------------------------------------------------------------------


def test_specificity_fails_when_the_binding_region_is_absent() -> None:
    """Section 7.5 check 9: FAIL on zero occurrences."""
    design = one_fragment_design(FRAGMENT_A[0:20], FRAGMENT_A[100:120])
    absent = design.primers[0].model_copy(update={"binding": "ACGTACGTAAGGTTCCAAGG"})
    broken = design.model_copy(update={"primers": [absent, design.primers[1]]})
    report = VALIDATOR.validate(broken)
    assert severity_of(report, "primer.specificity_in_template") == "fail"
    check = next(item for item in report.checks if item.check_id == "primer.specificity_in_template")
    assert "occurs nowhere" in check.message


def test_specificity_fails_when_the_binding_region_occurs_twice() -> None:
    """Section 7.5 check 9: FAIL on multiple occurrences."""
    repeated = FRAGMENT_A[0:24]
    sequence = FRAGMENT_B[:40] + repeated + MIDDLE + repeated + FRAGMENT_B[120:170]
    fragment = Fragment(name="frag", sequence=sequence, source="synthetic, repeated binding region")
    request = AssemblyRequest(strategy="pcr_cloning", fragments=[fragment])
    design = pinned_design(
        request,
        [
            primer("frag_F", "frag", "forward", repeated, start=40),
            primer("frag_R", "frag", "reverse", reverse_complement(FRAGMENT_B[140:164]), start=140),
        ],
    )
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.specificity_in_template") == "fail"
    check = next(item for item in report.checks if item.check_id == "primer.specificity_in_template")
    assert "occurs 2 times" in check.message


# ---------------------------------------------------------------------------
# 10. primer.homopolymer
# ---------------------------------------------------------------------------


def test_homopolymer_warns_on_a_long_run() -> None:
    design = one_fragment_design(FRAGMENT_B[40:58] + "AAAAAAAA", FRAGMENT_A[100:120])
    report = VALIDATOR.validate(design)
    assert severity_of(report, "primer.homopolymer") == "warn"
    check = next(item for item in report.checks if item.check_id == "primer.homopolymer")
    assert "consecutive A" in check.message


# ---------------------------------------------------------------------------
# 11, 12, 13: the Gibson junction checks
# ---------------------------------------------------------------------------


def gibson_design(junction_sequences: list[str]):
    """A Gibson design with the junction homology arms pinned to these sequences."""
    from packages.generation.assembly.designer import compose

    composed = compose(clean_request())
    junctions = [
        Junction(
            index=index,
            left_fragment=composed.junctions[index].left_fragment,
            right_fragment=composed.junctions[index].right_fragment,
            kind="gibson_homology",
            sequence=sequence,
        )
        for index, sequence in enumerate(junction_sequences)
    ]
    return composed.model_copy(update={"junctions": junctions})


def test_gibson_overlap_length_fails_when_too_short() -> None:
    """Section 7.5 check 11: FAIL outside the window."""
    report = VALIDATOR.validate(gibson_design([FRAGMENT_A[0:6], FRAGMENT_B[0:20]]))
    assert severity_of(report, "gibson.overlap_length") == "fail"
    check = next(item for item in report.checks if item.check_id == "gibson.overlap_length")
    assert "under the 15 bp minimum" in check.message
    assert unexpected_failures(report, {"gibson.overlap_length"}) == []


def test_gibson_overlap_length_fails_when_too_long() -> None:
    report = VALIDATOR.validate(gibson_design([FRAGMENT_A[0:45], FRAGMENT_B[0:20]]))
    assert severity_of(report, "gibson.overlap_length") == "fail"
    check = next(item for item in report.checks if item.check_id == "gibson.overlap_length")
    assert "over the 40 bp maximum" in check.message


def test_gibson_overlap_tm_warns_below_the_floor() -> None:
    """Section 7.5 check 12: WARN when an overlap melts below the floor."""
    report = VALIDATOR.validate(gibson_design(["ATTAATTAATTAATTAAT", FRAGMENT_B[0:20]]))
    assert severity_of(report, "gibson.overlap_tm") == "warn"
    check = next(item for item in report.checks if item.check_id == "gibson.overlap_tm")
    assert "48.0 C" in check.message
    assert unexpected_failures(report, set()) == []


def test_gibson_overlap_uniqueness_fails_on_shared_homology() -> None:
    """Section 7.5 check 13: FAIL when two junctions share homology.

    Two identical arms also make the assembly order ambiguous, so check 18 fails
    too. It is listed as an allowed extra failure (section 9.3's
    `allowed_extra_fail`) rather than ignored.
    """
    arm = FRAGMENT_A[0:20]
    report = VALIDATOR.validate(gibson_design([arm, arm]))
    assert severity_of(report, "gibson.overlap_uniqueness") == "fail"
    assert unexpected_failures(report, {"gibson.overlap_uniqueness", "assembly.fragment_order_defined"}) == []


def test_gibson_overlap_uniqueness_fails_on_complementary_arms() -> None:
    """One arm complementary to another is the same mis-assembly hazard."""
    arm = FRAGMENT_A[0:20]
    report = VALIDATOR.validate(gibson_design([arm, reverse_complement(arm)]))
    assert severity_of(report, "gibson.overlap_uniqueness") == "fail"


# ---------------------------------------------------------------------------
# 14. gg.enzyme_site_internal
# ---------------------------------------------------------------------------


def test_enzyme_site_internal_fails_with_a_domestication_report() -> None:
    """Section 7.5 check 14: FAIL, with a domestication report (section 7.6)."""
    contaminated = FRAGMENT_A[:60] + "GGTCTC" + FRAGMENT_A[66:]
    request = clean_golden_gate_request(
        fragments=[
            Fragment(name="frag_a", sequence=contaminated, source="fixture with a BsaI site inserted"),
            Fragment(name="frag_b", sequence=fixtures.GOLDEN_GATE_B, source=fixtures.GOLDEN_GATE_B_SOURCE),
        ]
    )
    report = VALIDATOR.validate(design_from(request))
    assert severity_of(report, "gg.enzyme_site_internal") == "fail"
    check = next(item for item in report.checks if item.check_id == "gg.enzyme_site_internal")
    assert "GGTCTC" in check.message
    assert "Domestication plan" in check.message
    assert check.remediation, "section 9.3 must_also_report: the structured remediation list"


def test_enzyme_site_internal_finds_a_site_on_the_reverse_strand() -> None:
    """Appendix D: both strands must be checked, the sites are not palindromic."""
    contaminated = FRAGMENT_A[:60] + reverse_complement("GGTCTC") + FRAGMENT_A[66:]
    request = clean_golden_gate_request(
        fragments=[
            Fragment(name="frag_a", sequence=contaminated, source="fixture with a reverse-strand BsaI site"),
            Fragment(name="frag_b", sequence=fixtures.GOLDEN_GATE_B, source=fixtures.GOLDEN_GATE_B_SOURCE),
        ]
    )
    report = VALIDATOR.validate(design_from(request))
    assert severity_of(report, "gg.enzyme_site_internal") == "fail"
    check = next(item for item in report.checks if item.check_id == "gg.enzyme_site_internal")
    assert "reverse strand" in check.message


def test_enzyme_site_internal_passes_when_no_fragment_carries_the_site() -> None:
    report = VALIDATOR.validate(design_from(clean_golden_gate_request()))
    assert severity_of(report, "gg.enzyme_site_internal") == "pass"


# ---------------------------------------------------------------------------
# 15, 16, 17: the overhang checks
# ---------------------------------------------------------------------------


def golden_gate_design(overhangs: list[str]):
    """A Golden Gate design with the fusion overhangs pinned to these sequences."""
    from packages.generation.assembly.designer import compose

    composed = compose(clean_golden_gate_request())
    junctions = [
        composed.junctions[index].model_copy(update={"sequence": sequence})
        for index, sequence in enumerate(overhangs)
    ]
    return composed.model_copy(update={"junctions": junctions})


def test_overhang_uniqueness_fails_on_a_repeated_overhang() -> None:
    """Section 7.5 check 15 and Appendix D: all overhangs in one assembly distinct."""
    report = VALIDATOR.validate(golden_gate_design(["ATGC", "ATGC"]))
    assert severity_of(report, "gg.overhang_uniqueness") == "fail"
    assert unexpected_failures(report, {"gg.overhang_uniqueness", "assembly.fragment_order_defined"}) == []


def test_overhang_uniqueness_fails_when_one_overhang_is_another_s_reverse_complement() -> None:
    """A reverse-complement collision lets a fragment ligate in backwards."""
    report = VALIDATOR.validate(golden_gate_design(["ATGC", reverse_complement("ATGC")]))
    assert severity_of(report, "gg.overhang_uniqueness") == "fail"
    check = next(item for item in report.checks if item.check_id == "gg.overhang_uniqueness")
    assert "backwards" in check.message


def test_overhang_not_palindromic_fails_on_a_palindrome() -> None:
    """Section 7.5 check 16 and Appendix D: no overhang equal to its own reverse complement."""
    report = VALIDATOR.validate(golden_gate_design(["AATT", "ACGG"]))
    assert severity_of(report, "gg.overhang_not_palindromic") == "fail"
    check = next(item for item in report.checks if item.check_id == "gg.overhang_not_palindromic")
    assert "either orientation" in check.message
    assert unexpected_failures(report, {"gg.overhang_not_palindromic"}) == []


def test_overhang_composition_warns_on_all_gc() -> None:
    """Section 7.5 check 17 and Appendix D: avoid all-GC and all-AT compositions."""
    report = VALIDATOR.validate(golden_gate_design(["GCGG", "ACTG"]))
    assert severity_of(report, "gg.overhang_composition") == "warn"
    check = next(item for item in report.checks if item.check_id == "gg.overhang_composition")
    assert "all G and C" in check.message
    assert unexpected_failures(report, set()) == []


def test_overhang_composition_warns_on_all_at() -> None:
    report = VALIDATOR.validate(golden_gate_design(["ATTA", "ACTG"]))
    assert severity_of(report, "gg.overhang_composition") == "warn"
    check = next(item for item in report.checks if item.check_id == "gg.overhang_composition")
    assert "all A and T" in check.message


# ---------------------------------------------------------------------------
# 18. assembly.fragment_order_defined
# ---------------------------------------------------------------------------


def test_fragment_order_defined_fails_when_the_topology_is_ambiguous() -> None:
    """Section 7.5 check 18: FAIL if ambiguous."""
    report = VALIDATOR.validate(golden_gate_design(["ATGC", "ATGC"]))
    assert severity_of(report, "assembly.fragment_order_defined") == "fail"
    check = next(item for item in report.checks if item.check_id == "assembly.fragment_order_defined")
    assert "more than one assembly order" in check.message


def test_fragment_order_defined_passes_for_distinct_junctions() -> None:
    report = VALIDATOR.validate(design_from(clean_golden_gate_request()))
    assert severity_of(report, "assembly.fragment_order_defined") == "pass"


def test_pcr_cloning_with_the_same_site_at_both_ends_is_ambiguous() -> None:
    """Simple PCR cloning with one enzyme gives an insert that can go in either way."""
    report = VALIDATOR.validate(design_from(clean_request(strategy="pcr_cloning", enzyme="BsaI")))
    assert severity_of(report, "assembly.fragment_order_defined") == "fail"


def test_fragment_order_remedy_is_branched_on_strategy() -> None:
    """The three strategies do not share a remedy, so the message must not either.

    Gibson and Golden Gate let the designer choose the joining sequence, so
    moving the junction or adopting a published overhang set is a real fix.
    Single-enzyme PCR cloning cannot do either: both ends carry the same site by
    construction. Offering the Gibson remedy there sends the reader after a
    change that cannot be made.
    """
    pcr = VALIDATOR.validate(design_from(clean_request(strategy="pcr_cloning", enzyme="BsaI")))
    pcr_check = next(item for item in pcr.checks if item.check_id == "assembly.fragment_order_defined")
    assert pcr_check.severity.value == "fail"
    assert "two different enzymes" in pcr_check.message
    assert "screen colonies" in pcr_check.message
    assert "moving the junction position" not in pcr_check.message
    assert "overhang standard" not in pcr_check.message

    gg = VALIDATOR.validate(golden_gate_design(["ATGC", "ATGC"]))
    gg_check = next(item for item in gg.checks if item.check_id == "assembly.fragment_order_defined")
    assert gg_check.severity.value == "fail"
    assert "moving the junction position" in gg_check.message
    assert "overhang standard" in gg_check.message
    assert "screen colonies" not in gg_check.message


# ---------------------------------------------------------------------------
# 19. assembly.amplicon_size
# ---------------------------------------------------------------------------


def test_amplicon_size_warns_when_too_short() -> None:
    """Section 7.5 check 19: WARN outside the window."""
    short = FRAGMENT_A[:60]
    request = AssemblyRequest(
        strategy="pcr_cloning",
        fragments=[Fragment(name="frag", sequence=short, source="fixture slice, 60 bp")],
    )
    report = VALIDATOR.validate(design_from(request))
    assert severity_of(report, "assembly.amplicon_size") == "warn"
    check = next(item for item in report.checks if item.check_id == "assembly.amplicon_size")
    assert "under the 100 bp floor" in check.message


def test_amplicon_size_warns_when_too_long() -> None:
    """The ceiling side of check 19, exercised through the threshold override.

    A real amplicon over 10 kb would need a 10 kb fixture, and the fixtures here
    are real GenBank slices rather than invented filler. Lowering the configured
    ceiling instead tests the same branch and tests that section 3.3 constraint
    2's configurability actually reaches the check.
    """
    request = clean_request(thresholds=AssemblyThresholds(amplicon_max_bp=150))
    report = VALIDATOR.validate(design_from(request))
    assert severity_of(report, "assembly.amplicon_size") == "warn"
    check = next(item for item in report.checks if item.check_id == "assembly.amplicon_size")
    assert "over the 150 bp ceiling" in check.message
    assert unexpected_failures(report, set()) == []


# ---------------------------------------------------------------------------
# Contract obligations that apply to every check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", sorted(APPLICABLE_CHECKS))
def test_every_check_carries_a_label_message_threshold_and_citation(strategy: str) -> None:
    """Section 5.1 and 5.4: every row the UI renders must be complete."""
    request = clean_golden_gate_request() if strategy == "golden_gate" else clean_request(strategy=strategy)
    report = VALIDATOR.validate(design_from(request))
    for check in report.checks:
        assert check.label and check.label != check.check_id, check.check_id
        assert len(check.message) > 40, f"{check.check_id} message is too terse to be actionable"
        assert check.citation, check.check_id
        if check.severity.value != "unknown":
            assert check.threshold, check.check_id
            assert check.observed, check.check_id


def test_overall_is_the_worst_non_unknown_severity() -> None:
    """Section 5.4 rule 1, enforced by the shared contract rather than by this package."""
    report = VALIDATOR.validate(gibson_design([FRAGMENT_A[0:6], FRAGMENT_B[0:20]]))
    assert report.overall.value == "fail"
    report = VALIDATOR.validate(gibson_design(["ATTAATTAATTAATTAAT", FRAGMENT_B[0:20]]))
    assert report.overall.value == "warn"


def test_a_warning_row_is_tagged_tier_b() -> None:
    """Section 3.4: a Tier B warning is surfaced and explained, not treated as a failure."""
    report = VALIDATOR.validate(gibson_design(["ATTAATTAATTAATTAAT", FRAGMENT_B[0:20]]))
    for check in report.checks:
        if check.severity.value == "warn":
            assert check.tier == "B", check.check_id


def test_validation_is_deterministic() -> None:
    """Section 3.3 constraint 3: same input, same output, every time."""
    request = clean_golden_gate_request()
    first = VALIDATOR.validate(design_from(request))
    second = VALIDATOR.validate(design_from(request))
    assert [(c.check_id, c.severity, c.message) for c in first.checks] == [
        (c.check_id, c.severity, c.message) for c in second.checks
    ]
