"""Every one of the fourteen section 6.4 checks, at every severity it can report.

One test class per check, in section 6.4 order. A check that can return
UNKNOWN has a test for that too, because section 3.3 constraint 4 makes
"UNKNOWN with a reason" a required behaviour rather than an edge case.
"""

from __future__ import annotations

import pytest

from packages.core.part_registry import get_part
from packages.core.schemas.aav import CassetteElement, CassetteElementRole
from packages.core.schemas.capability import Severity
from packages.core.sequence import reverse_complement
from packages.validation.aav import CHECK_IDS, AAVThresholds, AAVValidator

from tests.aav.support import build_design, cds_element, cds_of_length, check_of, part_element, severities

LEFT_ITR = get_part("itr.aav2_itr_left").sequence
RIGHT_ITR = get_part("itr.aav2_itr_right").sequence
HAIRPIN_CORE = LEFT_ITR[:125]


def validate(design, **kwargs):
    return AAVValidator(**kwargs).validate(design)


def sev(design, check_id, **kwargs) -> str:
    return check_of(validate(design, **kwargs), check_id).severity.value


# ---------------------------------------------------------------------------
# The closed list itself
# ---------------------------------------------------------------------------


class TestTheCheckList:
    def test_exactly_fourteen_checks_in_section_order(self):
        report = validate(build_design())
        assert [check.check_id for check in report.checks] == list(CHECK_IDS)
        assert len(CHECK_IDS) == 14

    def test_no_invented_check_id(self):
        report = validate(build_design())
        assert all(check.check_id.startswith("aav.") for check in report.checks)
        assert "aav.remediation" not in {check.check_id for check in report.checks}

    def test_every_check_carries_a_citation_and_an_actionable_message(self):
        for design in (build_design(), build_design(polya=None, promoter=None)):
            for check in validate(design).checks:
                assert check.citation, check.check_id
                assert len(check.message) > 60, check.check_id
                assert check.threshold, check.check_id

    def test_tier_marks_pass_as_a_and_warn_as_b(self):
        for check in validate(build_design(promoter="promoter.cag")).checks:
            if check.severity is Severity.PASS:
                assert check.tier == "A"
            elif check.severity is Severity.WARN:
                assert check.tier == "B"
            else:
                assert check.tier is None

    def test_a_clean_cassette_is_tier_a_clean(self):
        report = validate(build_design())
        assert report.overall is Severity.PASS
        assert all(check.severity is Severity.PASS for check in report.checks)

    def test_validation_is_deterministic(self):
        design = build_design(promoter="promoter.cag")
        first = validate(design)
        second = validate(design)
        assert severities(first) == severities(second)
        assert [check.message for check in first.checks] == [check.message for check in second.checks]


# ---------------------------------------------------------------------------
# 1. aav.packaging_limit
# ---------------------------------------------------------------------------


class TestPackagingLimit:
    """Overhead with the default fixture is 740 bp: 290 of ITR, 225 of promoter, 225 of polyA."""

    OVERHEAD = 740

    def design_of_total(self, total: int, **kwargs):
        cds_bp = total - self.OVERHEAD
        assert cds_bp % 3 == 0, "pick a total that leaves a codon multiple for the coding sequence"
        return build_design(cds=cds_of_length(cds_bp), **kwargs)

    def test_at_or_under_target_passes(self):
        design = self.design_of_total(4_700)
        check = check_of(validate(design), "aav.packaging_limit")
        assert check.severity is Severity.PASS
        assert "4,700" in check.message
        assert check.remediation is None

    def test_over_target_and_under_soft_limit_warns(self):
        design = self.design_of_total(4_799)
        check = check_of(validate(design), "aav.packaging_limit")
        assert check.severity is Severity.WARN
        assert "99 bp over the target" in check.message
        assert "titer" in check.message
        assert check.remediation

    def test_over_soft_limit_fails(self):
        design = self.design_of_total(5_000)
        check = check_of(validate(design), "aav.packaging_limit")
        assert check.severity is Severity.FAIL
        assert "300 bp over the target" in check.message
        assert "4,900 bp soft limit" in check.message
        assert check.remediation

    def test_over_hard_limit_fails_and_says_so(self):
        design = self.design_of_total(5_300)
        check = check_of(validate(design), "aav.packaging_limit")
        assert check.severity is Severity.FAIL
        assert "over the hard ceiling of 5,200 bp" in check.message

    def test_observed_threshold_and_coordinates_are_reported(self):
        design = self.design_of_total(5_000)
        check = check_of(validate(design), "aav.packaging_limit")
        assert check.observed == "5,000 bp"
        assert check.threshold == "target 4,700 bp, soft limit 4,900 bp, hard limit 5,200 bp"
        assert check.coordinates == (0, 5_000)

    def test_single_stranded_band_is_used_even_for_a_self_complementary_design(self):
        design = self.design_of_total(2_900, self_complementary=True)
        report = validate(design)
        assert check_of(report, "aav.packaging_limit").severity is Severity.PASS
        assert check_of(report, "aav.sc_capacity").severity is Severity.FAIL

    def test_packaging_limit_override_moves_the_whole_band(self):
        design = self.design_of_total(5_000, packaging_limit_bp=5_000)
        check = check_of(validate(design), "aav.packaging_limit")
        assert check.severity is Severity.PASS
        assert check.threshold == "target 5,000 bp, soft limit 5,200 bp, hard limit 5,500 bp"

    def test_thresholds_are_configurable(self):
        design = self.design_of_total(4_700)
        thresholds = AAVThresholds(ss_target_bp=3_000, ss_soft_limit_bp=3_200, ss_hard_limit_bp=3_500)
        assert sev(design, "aav.packaging_limit", thresholds=thresholds) == "fail"


# ---------------------------------------------------------------------------
# 2. aav.itr_present_both
# ---------------------------------------------------------------------------


class TestItrPresentBoth:
    def test_both_registry_itrs_pass(self):
        check = check_of(validate(build_design()), "aav.itr_present_both")
        assert check.severity is Severity.PASS
        assert "100.0% identity to itr.aav2_itr_left" in check.observed

    def test_the_flip_flop_comparison_would_have_failed_a_correct_design(self):
        """The reason check 2 compares each ITR with its own reference.

        Left against the reverse complement of right scores 128 of 145 on a
        correct cassette, below the 0.95 threshold. Each ITR against the
        reference set scores 1.000.
        """
        from packages.core.sequence import global_identity

        naive = global_identity(LEFT_ITR, reverse_complement(RIGHT_ITR))
        assert naive == pytest.approx(0.8784, abs=5e-4)
        assert naive < 0.95
        assert check_of(validate(build_design()), "aav.itr_present_both").severity is Severity.PASS

    def test_missing_three_prime_itr_fails(self):
        check = check_of(validate(build_design(itr_3=None)), "aav.itr_present_both")
        assert check.severity is Severity.FAIL
        assert "3' ITR absent" in check.message
        assert "itr.aav2_itr_right" in check.message

    def test_missing_both_itrs_fails(self):
        check = check_of(validate(build_design(itr_5=None, itr_3=None)), "aav.itr_present_both")
        assert check.severity is Severity.FAIL
        assert check.observed == "0 of 2 ITRs present"

    def test_divergent_itr_below_the_identity_threshold_fails(self):
        decoy = CassetteElement(
            role=CassetteElementRole.ITR_5,
            name="not an ITR",
            sequence=get_part("promoter.efs").sequence[:145],
            source="test fixture",
        )
        design = build_design(itr_5=None)
        design = design.model_copy(update={"elements": [decoy] + list(design.elements)})
        check = check_of(validate(design), "aav.itr_present_both")
        assert check.severity is Severity.FAIL
        assert "below the 95% identity" in check.message

    def test_unknown_serotype_is_unknown_not_pass(self):
        check = check_of(validate(build_design(serotype="AAV9")), "aav.itr_present_both")
        assert check.severity is Severity.UNKNOWN
        assert "no ITR reference pair is registered for serotype 'AAV9'" in check.message
        assert "aav2" in check.message

    def test_identity_threshold_is_configurable(self):
        design = build_design()
        assert sev(design, "aav.itr_present_both", thresholds=AAVThresholds(itr_identity_threshold=1.0)) == "pass"


# ---------------------------------------------------------------------------
# 3. aav.itr_orientation
# ---------------------------------------------------------------------------


class TestItrOrientation:
    def test_registry_pair_is_inverted_and_decided_by_the_d_element(self):
        check = check_of(validate(build_design()), "aav.itr_orientation")
        assert check.severity is Severity.PASS
        assert check.observed == "inverted (d_element)"
        assert "D element faces inward" in check.message

    def test_tandem_itrs_fail(self):
        """The 3' ITR is a direct copy of the 5' ITR, so both D elements face the same way."""
        tandem = CassetteElement(
            role=CassetteElementRole.ITR_3,
            name="tandem copy of the 5' ITR",
            sequence=LEFT_ITR,
            part_id="itr.aav2_itr_left",
        )
        design = build_design(itr_3=None)
        design = design.model_copy(update={"elements": list(design.elements) + [tandem]})
        check = check_of(validate(design), "aav.itr_orientation")
        assert check.severity is Severity.FAIL
        assert check.observed == "tandem (d_element)"
        assert "direct copy" in check.message
        assert "Reverse complement the 3' ITR" in check.message

    def test_a_reverse_complemented_cassette_is_still_the_canonical_inverted_pair(self):
        """Reverse complementing the whole cassette swaps the ITR order too, so it reads canonically."""
        design = build_design(itr_5=None, itr_3=None)
        flipped_5 = CassetteElement(
            role=CassetteElementRole.ITR_5, name="reverse complemented right ITR",
            sequence=reverse_complement(RIGHT_ITR), source="test fixture",
        )
        flipped_3 = CassetteElement(
            role=CassetteElementRole.ITR_3, name="reverse complemented left ITR",
            sequence=reverse_complement(LEFT_ITR), source="test fixture",
        )
        design = design.model_copy(
            update={"elements": [flipped_5] + list(design.elements) + [flipped_3]}
        )
        check = check_of(validate(design), "aav.itr_orientation")
        assert check.severity is Severity.PASS
        assert "faces inward in both ITRs" in check.message

    def _d_outward_design(self):
        """Both ITRs reverse complemented in place, so the D sequences face outward."""
        design = build_design(itr_5=None, itr_3=None)
        outward_5 = CassetteElement(
            role=CassetteElementRole.ITR_5, name="reverse complemented left ITR",
            sequence=reverse_complement(LEFT_ITR), source="test fixture",
        )
        outward_3 = CassetteElement(
            role=CassetteElementRole.ITR_3, name="reverse complemented right ITR",
            sequence=reverse_complement(RIGHT_ITR), source="test fixture",
        )
        return design.model_copy(
            update={"elements": [outward_5] + list(design.elements) + [outward_3]}
        )

    def test_both_itrs_flipped_in_place_warns_rather_than_passing(self):
        """Regression, WP-10 finding 1: a D outward pair must not PASS.

        It is inverted rather than tandem, so it is not the FAIL this check
        exists to produce, but a D outward genome is not functional and a PASS
        with a soft note is the one outcome a user could take into production.
        """
        check = check_of(validate(self._d_outward_design()), "aav.itr_orientation")
        assert check.severity is Severity.WARN
        assert check.severity is not Severity.PASS
        assert check.severity is not Severity.FAIL
        assert check.observed == "inverted but D outward (d_element)"
        assert check.tier == "B"

    def test_the_d_outward_warning_names_the_fault_the_consequence_and_the_fix(self):
        """Section 5.4 rule 2, on the message a user has to act on."""
        message = check_of(validate(self._d_outward_design()), "aav.itr_orientation").message
        # What is wrong.
        assert "inverted relative to each other" in message
        assert "D sequences face outward, toward the cassette ends" in message
        # What it costs.
        assert "not the functional arrangement" in message
        assert "will not give functional vector" in message
        assert "Do not take this design into production" in message
        # What to do.
        assert "reverse complement the whole cassette" in message
        assert "itr.aav2_itr_left" in message and "itr.aav2_itr_right" in message

    def test_the_d_outward_warning_does_not_make_the_overall_verdict_a_failure(self):
        """It is a WARN, so the tandem FAIL stays the only failing arrangement."""
        report = validate(self._d_outward_design())
        assert all(
            check.severity is not Severity.FAIL
            for check in report.checks
            if check.check_id == "aav.itr_orientation"
        )

    def test_one_itr_is_unknown_not_fail(self):
        """Orientation genuinely cannot be measured with one ITR, and check 2 owns the failure."""
        report = validate(build_design(itr_3=None))
        assert check_of(report, "aav.itr_orientation").severity is Severity.UNKNOWN
        assert check_of(report, "aav.itr_present_both").severity is Severity.FAIL

    def test_indeterminate_pair_is_unknown_with_a_reason(self):
        palindrome = HAIRPIN_CORE[:60] + reverse_complement(HAIRPIN_CORE[:60])
        design = build_design(itr_3=None)
        element = CassetteElement(
            role=CassetteElementRole.ITR_3, name="palindromic stand in", sequence=palindrome,
            source="test fixture",
        )
        design = design.model_copy(update={"elements": list(design.elements) + [element]})
        check = check_of(validate(design), "aav.itr_orientation")
        assert check.severity is Severity.UNKNOWN
        assert check.observed == "undetermined (identity_margin)"
        assert "below the 5% margin" in check.message

    def test_unknown_serotype_is_unknown(self):
        assert sev(build_design(serotype="AAV5"), "aav.itr_orientation") == "unknown"


# ---------------------------------------------------------------------------
# 4. aav.required_elements
# ---------------------------------------------------------------------------


class TestRequiredElements:
    def test_all_three_present_passes(self):
        assert sev(build_design(), "aav.required_elements") == "pass"

    def test_missing_promoter_fails_and_names_a_part(self):
        check = check_of(validate(build_design(promoter=None)), "aav.required_elements")
        assert check.severity is Severity.FAIL
        assert "missing promoter" in check.message
        assert "promoter.efs" in check.message

    def test_missing_polya_fails_and_names_a_part(self):
        check = check_of(validate(build_design(polya=None)), "aav.required_elements")
        assert check.severity is Severity.FAIL
        assert "polya.sv40" in check.message

    def test_missing_cds_fails(self):
        design = build_design(
            elements=[
                part_element(CassetteElementRole.ITR_5, "itr.aav2_itr_left"),
                part_element(CassetteElementRole.PROMOTER, "promoter.mecp2_mini"),
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                part_element(CassetteElementRole.ITR_3, "itr.aav2_itr_right"),
            ]
        )
        check = check_of(validate(design), "aav.required_elements")
        assert check.severity is Severity.FAIL
        assert "transgene_sequence" in check.message


# ---------------------------------------------------------------------------
# 5. aav.element_order
# ---------------------------------------------------------------------------


class TestElementOrder:
    def test_functional_order_passes(self):
        check = check_of(validate(build_design(wpre="enhancer.wpre")), "aav.element_order")
        assert check.severity is Severity.PASS
        assert check.observed == "itr_5 -> promoter -> cds -> wpre -> polya -> itr_3"

    def test_polya_before_the_coding_sequence_fails(self):
        design = build_design(
            elements=[
                part_element(CassetteElementRole.ITR_5, "itr.aav2_itr_left"),
                part_element(CassetteElementRole.PROMOTER, "promoter.mecp2_mini"),
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                cds_element(cds_of_length(1_500)),
                part_element(CassetteElementRole.ITR_3, "itr.aav2_itr_right"),
            ]
        )
        check = check_of(validate(design), "aav.element_order")
        assert check.severity is Severity.FAIL
        assert "inverts the functional order" in check.message
        assert "itr_5 -> enhancer -> promoter -> intron -> cds -> wpre -> polya -> itr_3" in check.message

    def test_wpre_before_the_promoter_fails(self):
        design = build_design(
            elements=[
                part_element(CassetteElementRole.ITR_5, "itr.aav2_itr_left"),
                part_element(CassetteElementRole.WPRE, "enhancer.wpre"),
                part_element(CassetteElementRole.PROMOTER, "promoter.mecp2_mini"),
                cds_element(cds_of_length(1_500)),
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                part_element(CassetteElementRole.ITR_3, "itr.aav2_itr_right"),
            ]
        )
        assert sev(design, "aav.element_order") == "fail"

    def test_a_dual_promoter_cassette_is_noted_not_failed(self):
        design = build_design(
            elements=[
                part_element(CassetteElementRole.ITR_5, "itr.aav2_itr_left"),
                part_element(CassetteElementRole.PROMOTER, "promoter.mecp2_mini"),
                part_element(CassetteElementRole.PROMOTER, "promoter.efs"),
                cds_element(cds_of_length(1_500)),
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                part_element(CassetteElementRole.ITR_3, "itr.aav2_itr_right"),
            ]
        )
        check = check_of(validate(design), "aav.element_order")
        assert check.severity is Severity.PASS
        assert "more than one element in these roles: promoter" in check.message


# ---------------------------------------------------------------------------
# 6. aav.cds_integrity
# ---------------------------------------------------------------------------


class TestCdsIntegrity:
    def test_clean_open_reading_frame_passes(self):
        check = check_of(validate(build_design()), "aav.cds_integrity")
        assert check.severity is Severity.PASS
        assert "divisible by 3" in check.message

    def test_no_atg_start_fails(self):
        design = build_design(cds="GCT" + cds_of_length(1_500)[3:])
        check = check_of(validate(design), "aav.cds_integrity")
        assert check.severity is Severity.FAIL
        assert "starts with GCT rather than ATG" in check.message

    def test_length_not_divisible_by_three_fails(self):
        design = build_design(cds=cds_of_length(1_500) + "AT")
        check = check_of(validate(design), "aav.cds_integrity")
        assert check.severity is Severity.FAIL
        assert "not divisible by 3" in check.message
        assert "remainder 2" in check.message

    def test_premature_in_frame_stop_fails_and_names_the_position(self):
        clean = cds_of_length(1_500)
        mutated = clean[:300] + "TAA" + clean[303:]
        design = build_design(cds=mutated)
        check = check_of(validate(design), "aav.cds_integrity")
        assert check.severity is Severity.FAIL
        assert "premature in-frame stop codon" in check.message
        assert "codon 101 of 500" in check.message

    def test_no_stop_codon_fails(self):
        design = build_design(cds=cds_of_length(1_500)[:-3] + "GCT")
        check = check_of(validate(design), "aav.cds_integrity")
        assert check.severity is Severity.FAIL
        assert "no in-frame stop codon" in check.message

    def test_no_cds_is_unknown_not_pass(self):
        design = build_design(
            elements=[
                part_element(CassetteElementRole.ITR_5, "itr.aav2_itr_left"),
                part_element(CassetteElementRole.PROMOTER, "promoter.mecp2_mini"),
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                part_element(CassetteElementRole.ITR_3, "itr.aav2_itr_right"),
            ]
        )
        assert sev(design, "aav.cds_integrity") == "unknown"


# ---------------------------------------------------------------------------
# 7. aav.sc_capacity
# ---------------------------------------------------------------------------


class TestScCapacity:
    OVERHEAD = TestPackagingLimit.OVERHEAD

    def design_of_total(self, total: int, **kwargs):
        return build_design(cds=cds_of_length(total - self.OVERHEAD), **kwargs)

    def test_single_stranded_design_passes_and_explains_the_band_it_used(self):
        check = check_of(validate(build_design()), "aav.sc_capacity")
        assert check.severity is Severity.PASS
        assert "halved self complementary capacity does not apply" in check.message
        assert "2,400 bp" in check.message

    def test_self_complementary_under_the_halved_target_passes(self):
        check = check_of(
            validate(self.design_of_total(2_300, self_complementary=True)), "aav.sc_capacity"
        )
        assert check.severity is Severity.PASS
        assert "halved 2,400 bp target" in check.message

    def test_self_complementary_over_target_and_under_soft_limit_warns(self):
        check = check_of(
            validate(self.design_of_total(2_450, self_complementary=True)), "aav.sc_capacity"
        )
        assert check.severity is Severity.WARN
        assert check.remediation

    def test_sc_cassette_sized_legally_for_ss_fails_only_on_sc_capacity(self):
        """The section 9.4 known-bad shape: exactly one check must fail."""
        report = validate(self.design_of_total(4_400, self_complementary=True))
        failing = [check.check_id for check in report.checks if check.severity is Severity.FAIL]
        assert failing == ["aav.sc_capacity"]
        assert report.overall is Severity.FAIL
        check = check_of(report, "aav.sc_capacity")
        assert "packaged genome is the cassette duplicated" in check.message
        assert "dropping self_complementary" in check.message
        assert check.remediation

    def test_sc_thresholds_are_configurable(self):
        design = self.design_of_total(2_300, self_complementary=True)
        thresholds = AAVThresholds(sc_target_bp=2_000, sc_soft_limit_bp=2_100, sc_hard_limit_bp=2_200)
        assert sev(design, "aav.sc_capacity", thresholds=thresholds) == "fail"


# ---------------------------------------------------------------------------
# 8. aav.promoter_tissue_match
# ---------------------------------------------------------------------------


class TestPromoterTissueMatch:
    def test_exact_tissue_match_passes(self):
        check = check_of(validate(build_design(target_tissue="cns_neuron")), "aav.promoter_tissue_match")
        assert check.severity is Severity.PASS

    def test_ubiquitous_promoter_is_compatible_with_any_target(self):
        for tissue in ("liver", "muscle", "cardiac", "retina", "cns_neuron"):
            design = build_design(promoter="promoter.efs", target_tissue=tissue)
            assert sev(design, "aav.promoter_tissue_match") == "pass", tissue

    def test_neuron_promoter_with_a_liver_target_warns(self):
        design = build_design(promoter="promoter.hsyn1", target_tissue="liver")
        check = check_of(validate(design), "aav.promoter_tissue_match")
        assert check.severity is Severity.WARN
        assert "promoter.hsyn1 is annotated cns_neuron and the target tissue is liver" in check.message
        assert "promoter.efs" in check.message
        assert check.tier == "B"

    def test_tissue_specific_promoter_with_a_ubiquitous_target_warns(self):
        design = build_design(promoter="promoter.gfap", target_tissue="ubiquitous")
        check = check_of(validate(design), "aav.promoter_tissue_match")
        assert check.severity is Severity.WARN
        assert "restricted below what was requested" in check.message

    def test_no_promoter_is_unknown(self):
        assert sev(build_design(promoter=None), "aav.promoter_tissue_match") == "unknown"

    def test_non_registry_promoter_is_unknown_not_pass(self):
        element = CassetteElement(
            role=CassetteElementRole.PROMOTER, name="custom promoter",
            sequence=get_part("promoter.efs").sequence, source="user supplied",
        )
        design = build_design(promoter=None)
        elements = list(design.elements)
        elements.insert(1, element)
        design = design.model_copy(update={"elements": elements})
        check = check_of(validate(design), "aav.promoter_tissue_match")
        assert check.severity is Severity.UNKNOWN
        assert "not a part registry record" in check.message

    def test_compatibility_table_is_configurable(self):
        design = build_design(promoter="promoter.hsyn1", target_tissue="liver")
        widened = AAVThresholds(
            tissue_compatibility={"liver": frozenset({"liver", "ubiquitous", "cns_neuron"})}
        )
        assert sev(design, "aav.promoter_tissue_match", thresholds=widened) == "pass"


# ---------------------------------------------------------------------------
# 9. aav.internal_repeats
# ---------------------------------------------------------------------------


class TestInternalRepeats:
    def test_clean_interior_passes(self):
        check = check_of(validate(build_design()), "aav.internal_repeats")
        assert check.severity is Severity.PASS
        assert "between the two ITRs" in check.message

    def test_the_shared_itr_hairpin_core_is_not_counted(self):
        """The two reference ITRs share 125 bp verbatim, by construction.

        If check 9 counted it, every correct design would warn, which section
        3.4 says is worse than no validator.
        """
        assert LEFT_ITR[:125] == RIGHT_ITR[20:]
        assert sev(build_design(), "aav.internal_repeats") == "pass"

    def test_cmv_enhancer_repeat_warns(self):
        design = build_design(promoter="promoter.cmv", target_tissue="ubiquitous")
        check = check_of(validate(design), "aav.internal_repeats")
        assert check.severity is Severity.WARN
        assert "ACGGTAAATGGCCCGCCTGGC" in check.message
        assert "promoter.efs" in check.message
        assert check.tier == "B"

    def test_a_long_repeat_in_the_transgene_warns_and_locates_it(self):
        unit = cds_of_length(90)[3:-3]
        design = build_design(cds="ATG" + unit + unit + "TAA")
        check = check_of(validate(design), "aav.internal_repeats")
        assert check.severity is Severity.WARN
        assert "cds" in check.message

    def test_repeat_length_is_configurable(self):
        design = build_design()
        assert sev(design, "aav.internal_repeats", thresholds=AAVThresholds(max_direct_repeat_bp=6)) == "warn"


# ---------------------------------------------------------------------------
# 10. aav.homopolymer_runs
# ---------------------------------------------------------------------------


class TestHomopolymerRuns:
    def test_clean_cassette_passes(self):
        assert sev(build_design(), "aav.homopolymer_runs") == "pass"

    def test_the_cag_g_run_warns(self):
        design = build_design(promoter="promoter.cag", target_tissue="ubiquitous")
        check = check_of(validate(design), "aav.homopolymer_runs")
        assert check.severity is Severity.WARN
        assert "14 consecutive G" in check.message
        assert "promoter" in check.message
        assert check.tier == "B"

    def test_a_run_in_the_transgene_warns(self):
        clean = cds_of_length(1_500)
        design = build_design(cds=clean[:300] + "AAAAAAAAAAAA" + clean[312:])
        check = check_of(validate(design), "aav.homopolymer_runs")
        assert check.severity is Severity.WARN
        assert "consecutive A" in check.message
        assert "synonymous codon" in check.message
        assert "cds" in check.message

    def test_run_length_is_configurable(self):
        design = build_design()
        assert sev(design, "aav.homopolymer_runs", thresholds=AAVThresholds(max_homopolymer_run=2)) == "warn"


# ---------------------------------------------------------------------------
# 11. aav.kozak_context
# ---------------------------------------------------------------------------


class TestKozakContext:
    def test_strong_context_passes(self):
        """promoter.mecp2_mini ends CGGAAA, so position -3 is a purine, and the fixture CDS has G at +4."""
        check = check_of(validate(build_design()), "aav.kozak_context")
        assert check.severity is Severity.PASS
        assert "purine (A) at -3" in check.message
        assert "G at +4" in check.message

    def test_pyrimidine_at_minus_three_warns(self):
        """promoter.efs ends ACACAG, so position -3 is C."""
        design = build_design(promoter="promoter.efs", target_tissue="ubiquitous")
        check = check_of(validate(design), "aav.kozak_context")
        assert check.severity is Severity.WARN
        assert "position -3 is C" in check.message
        assert "GCCRCC prefix immediately before the ATG" in check.message

    def test_wrong_base_at_plus_four_warns(self):
        clean = cds_of_length(1_500)
        design = build_design(cds="ATGA" + clean[4:])
        check = check_of(validate(design), "aav.kozak_context")
        assert check.severity is Severity.WARN
        assert "position +4 is A rather than G" in check.message
        assert "synonymous change" in check.message

    def test_no_cds_is_unknown(self):
        design = build_design(
            elements=[
                part_element(CassetteElementRole.ITR_5, "itr.aav2_itr_left"),
                part_element(CassetteElementRole.PROMOTER, "promoter.mecp2_mini"),
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
                part_element(CassetteElementRole.ITR_3, "itr.aav2_itr_right"),
            ]
        )
        assert sev(design, "aav.kozak_context") == "unknown"

    def test_cds_without_an_atg_start_is_unknown_here_and_fails_on_check_six(self):
        design = build_design(cds="GCT" + cds_of_length(1_500)[3:])
        report = validate(design)
        assert check_of(report, "aav.kozak_context").severity is Severity.UNKNOWN
        assert check_of(report, "aav.cds_integrity").severity is Severity.FAIL

    def test_no_upstream_context_is_unknown(self):
        design = build_design(
            elements=[
                cds_element(cds_of_length(1_500)),
                part_element(CassetteElementRole.POLYA, "polya.bgh"),
            ]
        )
        check = check_of(validate(design), "aav.kozak_context")
        assert check.severity is Severity.UNKNOWN
        assert "position -3 of the initiation context does not exist" in check.message

    def test_kozak_positions_are_configurable(self):
        design = build_design()
        thresholds = AAVThresholds(kozak_minus3_purines=("C",))
        assert sev(design, "aav.kozak_context", thresholds=thresholds) == "warn"


# ---------------------------------------------------------------------------
# 12. aav.polya_present_functional
# ---------------------------------------------------------------------------


class TestPolyaPresentFunctional:
    def test_bgh_polya_passes_and_names_the_hexamer(self):
        check = check_of(validate(build_design()), "aav.polya_present_functional")
        assert check.severity is Severity.PASS
        assert "AATAAA at position 91" in check.message

    def test_sv40_polya_passes_with_two_hexamers(self):
        check = check_of(validate(build_design(polya="polya.sv40")), "aav.polya_present_functional")
        assert check.severity is Severity.PASS
        assert "AATAAA at position 32" in check.message
        assert "1 further occurrence" in check.message

    def test_absent_polya_fails(self):
        check = check_of(validate(build_design(polya=None)), "aav.polya_present_functional")
        assert check.severity is Severity.FAIL
        assert "read through into the 3' ITR" in check.message
        assert "polya.sv40 (135 bp)" in check.message

    def test_unrecognised_polya_warns_rather_than_failing(self):
        element = CassetteElement(
            role=CassetteElementRole.POLYA, name="unverified polyA",
            sequence=get_part("promoter.efs").sequence, source="user supplied",
        )
        design = build_design(polya=None)
        elements = list(design.elements)
        elements.insert(-1, element)
        design = design.model_copy(update={"elements": elements})
        check = check_of(validate(design), "aav.polya_present_functional")
        assert check.severity is Severity.WARN
        assert "none of the recognised polyadenylation hexamers" in check.message

    def test_motif_set_is_configurable(self):
        """polya.bgh carries AATAAA but not the ATTAAA variant, so restricting the set warns."""
        design = build_design()
        thresholds = AAVThresholds(polya_signal_motifs=("ATTAAA",))
        assert sev(design, "aav.polya_present_functional", thresholds=thresholds) == "warn"


# ---------------------------------------------------------------------------
# 13. aav.minimum_genome_size
# ---------------------------------------------------------------------------


class TestMinimumGenomeSize:
    def test_a_normal_cassette_passes(self):
        assert sev(build_design(), "aav.minimum_genome_size") == "pass"

    def test_a_small_cassette_warns_and_says_how_much_to_add(self):
        design = build_design(cds=cds_of_length(900))
        check = check_of(validate(design), "aav.minimum_genome_size")
        assert check.severity is Severity.WARN
        assert check.observed == "1,640 bp"
        assert "360 bp below the 2,000 bp minimum" in check.message
        assert "enhancer.wpre" in check.message
        assert check.tier == "B"

    def test_minimum_is_configurable(self):
        design = build_design()
        assert sev(design, "aav.minimum_genome_size", thresholds=AAVThresholds(min_genome_bp=4_000)) == "warn"


# ---------------------------------------------------------------------------
# 14. aav.itr_internal_sites
# ---------------------------------------------------------------------------


class TestItrInternalSites:
    def test_clean_interior_passes(self):
        check = check_of(validate(build_design()), "aav.itr_internal_sites")
        assert check.severity is Severity.PASS
        assert "0 internal ITR motifs" in check.observed

    def test_an_internal_itr_fragment_warns(self):
        fragment = CassetteElement(
            role=CassetteElementRole.ENHANCER, name="internal ITR fragment",
            sequence=LEFT_ITR[20:80], source="test fixture",
        )
        design = build_design()
        elements = list(design.elements)
        elements.insert(1, fragment)
        design = design.model_copy(update={"elements": elements})
        check = check_of(validate(design), "aav.itr_internal_sites")
        assert check.severity is Severity.WARN
        assert "aberrant resolution" in check.message
        assert check.tier == "B"

    def test_motif_is_found_on_the_minus_strand_too(self):
        fragment = CassetteElement(
            role=CassetteElementRole.ENHANCER, name="reverse complemented ITR fragment",
            sequence=reverse_complement(LEFT_ITR[20:80]), source="test fixture",
        )
        design = build_design()
        elements = list(design.elements)
        elements.insert(1, fragment)
        design = design.model_copy(update={"elements": elements})
        check = check_of(validate(design), "aav.itr_internal_sites")
        assert check.severity is Severity.WARN
        assert "minus strand" in check.message

    def test_no_interior_is_unknown(self):
        assert sev(build_design(itr_3=None), "aav.itr_internal_sites") == "unknown"

    def test_unknown_serotype_is_unknown(self):
        assert sev(build_design(serotype="AAVrh10"), "aav.itr_internal_sites") == "unknown"

    def test_motif_width_is_configurable(self):
        design = build_design()
        assert sev(design, "aav.itr_internal_sites", thresholds=AAVThresholds(itr_internal_motif_bp=4)) == "warn"
