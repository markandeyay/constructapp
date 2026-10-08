"""The section 6.6 remediation engine.

The payoff feature: when a cassette does not fit, the engine must name a
specific element substitution with real numbers, not say "too long". These
tests assert the numbers.
"""

from __future__ import annotations

import pytest

from packages.core.part_registry import get_part
from packages.core.schemas.aav import AAVRequest, CassetteElementRole
from packages.core.schemas.capability import Severity
from packages.generation.aav import AAVDesigner
from packages.validation.aav import AAVThresholds, AAVValidator, build_remediation
from packages.validation.aav.remediation import remediation_entries, render_remediation_message

from tests.aav.support import build_design, cds_of_length, check_of

# Overhead of the oversized fixture: 145 + 145 ITR, 1,639 CAG, 225 bGH.
CAG_OVERHEAD = 145 + 145 + 1_639 + 225


def oversized_design(total: int = 5_049, **kwargs):
    """A cassette over the 4,700 bp target, built from real registry parts."""
    cds_bp = total - CAG_OVERHEAD
    assert cds_bp % 3 == 0
    return build_design(
        cds=cds_of_length(cds_bp),
        promoter="promoter.cag",
        polya="polya.bgh",
        target_tissue="ubiquitous",
        **kwargs,
    )


class TestRealPartLengths:
    """The engine's numbers come from the registry, so pin the registry lengths."""

    @pytest.mark.parametrize(
        "part_id,length_bp",
        [
            ("itr.aav2_itr_left", 145),
            ("itr.aav2_itr_right", 145),
            ("promoter.cag", 1_639),
            ("promoter.cmv", 663),
            ("promoter.cbh", 799),
            ("promoter.ef1a", 1_184),
            ("promoter.efs", 212),
            ("polya.bgh", 225),
            ("polya.sv40", 135),
            ("enhancer.wpre", 589),
            ("intron.chimeric", 141),
        ],
    )
    def test_registry_length(self, part_id, length_bp):
        assert get_part(part_id).length_bp == length_bp

    def test_there_is_no_synthetic_short_polya(self):
        """Appendix B lists one; WP-02 could not source a real sequence and omitted it."""
        from packages.core.part_registry import PartCategory, list_parts

        ids = {part.id for part in list_parts(PartCategory.POLYA)}
        assert ids == {"polya.bgh", "polya.sv40"}


class TestOversizedCassette:
    def test_the_overage_is_measured_against_the_target(self):
        report = build_remediation(oversized_design())
        assert report.total_bp == 5_049
        assert report.target_bp == 4_700
        assert report.soft_limit_bp == 4_900
        assert report.hard_limit_bp == 5_200
        assert report.overage_bp == 349

    def test_the_best_plan_is_a_single_concrete_substitution_with_numbers(self):
        report = build_remediation(oversized_design())
        assert report.solved
        best = report.plans[0]
        assert best.change_count == 1
        change = best.changes[0]
        assert change.kind == "substitute"
        assert CassetteElementRole(change.role) is CassetteElementRole.PROMOTER
        assert change.from_part_id == "promoter.cag"
        assert change.from_bp == 1_639
        assert change.to_part_id == "promoter.efs"
        assert change.to_bp == 212
        assert change.saved_bp == 1_427
        assert best.resulting_bp == 3_622
        assert best.resulting_headroom_bp == 1_078

    def test_every_plan_actually_closes_the_gap(self):
        report = build_remediation(oversized_design())
        for plan in report.plans:
            assert plan.saved_bp >= report.overage_bp
            assert plan.resulting_bp <= report.target_bp

    def test_plans_are_ranked_fewest_changes_first(self):
        report = build_remediation(oversized_design())
        counts = [plan.change_count for plan in report.plans]
        assert counts == sorted(counts)

    def test_the_tradeoff_names_the_biology_not_just_the_bp(self):
        report = build_remediation(oversized_design())
        tradeoff = report.plans[0].changes[0].tradeoff
        assert "ubiquitous" in tradeoff
        assert "tissue specificity is preserved" in tradeoff
        assert "Weaker than CAG" in tradeoff

    def test_build_metadata_is_kept_out_of_the_tradeoff_text(self):
        report = build_remediation(oversized_design())
        for plan in report.plans:
            for change in plan.changes:
                assert "sense strand contains" not in change.tradeoff.lower()

    def test_the_longest_transgene_that_would_fit_is_reported(self):
        report = build_remediation(oversized_design())
        # 145 + 212 (EFS) + 135 (SV40) + 145 = 637 of fixed overhead after every saving.
        assert report.max_available_saving_bp == 1_427 + 90
        assert report.max_transgene_bp == 4_700 - 637

    def test_a_cassette_inside_the_target_has_no_overage_and_no_plans(self):
        report = build_remediation(build_design())
        assert report.overage_bp == 0
        assert report.plans == []
        assert report.remaining_deficit_bp == 0


class TestPromoterPreference:
    def test_a_plan_that_keeps_the_preference_is_ranked_first(self):
        """With WPRE in the cassette, dropping it closes the gap without touching CAG."""
        design = build_design(
            cds=cds_of_length(2_385),
            promoter="promoter.cag",
            polya="polya.bgh",
            wpre="enhancer.wpre",
            target_tissue="ubiquitous",
            promoter_preference="promoter.cag",
        )
        assert design.total_bp == 5_128
        report = build_remediation(design)
        assert report.overage_bp == 428
        best = report.plans[0]
        assert best.preserves_promoter_preference
        assert best.change_count == 1
        assert best.changes[0].kind == "remove"
        assert best.changes[0].from_part_id == "enhancer.wpre"
        assert best.changes[0].saved_bp == 589
        assert "optional in the section 6.2 cassette order" in best.changes[0].tradeoff

    def test_when_the_preference_cannot_be_kept_the_message_says_so(self):
        design = oversized_design(promoter_preference="promoter.cag")
        report = build_remediation(design)
        assert not any(plan.preserves_promoter_preference for plan in report.plans)
        assert report.preference_preserving_saving_bp == 90
        message = render_remediation_message(report, "single stranded")
        assert "No option keeps the stated promoter preference promoter.cag" in message
        assert "total 90 bp against a 349 bp overage" in message

    def test_a_substitution_back_to_the_preference_still_counts_as_preserving(self):
        design = oversized_design(promoter_preference="promoter.efs")
        report = build_remediation(design)
        best = report.plans[0]
        assert best.changes[0].to_part_id == "promoter.efs"
        assert best.preserves_promoter_preference


class TestTissueAndHostCompatibility:
    def test_a_substitution_never_breaks_tissue_targeting(self):
        """A neuron target must not be offered an astrocyte promoter."""
        design = build_design(
            cds=cds_of_length(4_500),
            promoter="promoter.hsyn1",
            polya="polya.bgh",
            target_tissue="cns_neuron",
        )
        report = build_remediation(design)
        offered = {
            change.to_part_id
            for plan in report.plans
            for change in plan.changes
            if change.to_part_id
        }
        assert "promoter.gfap" not in offered
        for part_id in offered:
            part = get_part(part_id)
            if part.tissue_specificity is not None:
                assert part.tissue_specificity in ("cns_neuron", "ubiquitous")

    def test_the_itrs_and_the_transgene_are_never_proposed_for_change(self):
        report = build_remediation(oversized_design())
        roles = {
            CassetteElementRole(change.role)
            for plan in report.plans
            for change in plan.changes
        }
        assert CassetteElementRole.ITR_5 not in roles
        assert CassetteElementRole.ITR_3 not in roles
        assert CassetteElementRole.CDS not in roles


class TestNoSolution:
    """Section 6.6 step 5: say so explicitly, report the deficit, suggest the alternatives."""

    def hopeless(self):
        return build_design(
            cds=cds_of_length(6_000), promoter="promoter.efs", polya="polya.sv40", target_tissue="ubiquitous"
        )

    def test_no_plan_is_reported_and_the_deficit_is_quantified(self):
        report = build_remediation(self.hopeless())
        assert not report.solved
        assert report.plans == []
        assert report.total_bp == 6_637
        assert report.overage_bp == 1_937
        assert report.max_available_saving_bp == 0
        assert report.remaining_deficit_bp == 1_937

    def test_the_message_suggests_a_shorter_variant_or_a_dual_vector(self):
        report = build_remediation(self.hopeless())
        message = render_remediation_message(report, "single stranded")
        assert "No combination of part registry substitutions closes the gap" in message
        assert "1,937 bp over the target" in message
        assert "shorter variant" in message
        assert "dual vector" in message
        assert f"{report.max_transgene_bp:,} bp of coding sequence" in message

    def test_the_structured_entries_record_the_no_solution_case(self):
        entries = remediation_entries(build_remediation(self.hopeless()))
        assert any(entry.startswith("plan=none") for entry in entries)
        assert any("remaining_deficit_bp=1937" in entry for entry in entries)
        assert any("dual vector approach" in entry for entry in entries)

    def test_the_check_result_carries_the_no_solution_remediation(self):
        check = check_of(AAVValidator().validate(self.hopeless()), "aav.packaging_limit")
        assert check.severity is Severity.FAIL
        assert check.remediation
        assert any("plan=none" in entry for entry in check.remediation)


class TestStructuredEntries:
    def test_the_header_entry_carries_every_number(self):
        entries = remediation_entries(build_remediation(oversized_design()))
        header = entries[0]
        for fragment in (
            "overage_bp=349",
            "total_bp=5049",
            "target_bp=4700",
            "soft_limit_bp=4900",
            "hard_limit_bp=5200",
            "max_available_saving_bp=1517",
            "max_transgene_bp=4063",
        ):
            assert fragment in header

    def test_each_plan_entry_is_machine_parseable(self):
        entries = remediation_entries(build_remediation(oversized_design()))
        plan_one = next(entry for entry in entries if entry.startswith("plan=1"))
        assert "changes=1" in plan_one
        assert "saves_bp=1427" in plan_one
        assert "result_bp=3622" in plan_one
        assert "substitute promoter.cag -> promoter.efs (saves 1427 bp)" in plan_one

    def test_entries_are_capped_by_the_configurable_plan_limit(self):
        design = oversized_design()
        report = build_remediation(design, AAVThresholds(remediation_max_plans=2))
        assert len(report.plans) == 2
        assert len(remediation_entries(report)) == 3  # one header plus two plans

    def test_the_change_limit_is_configurable(self):
        design = oversized_design()
        report = build_remediation(design, AAVThresholds(remediation_max_changes=1))
        assert all(plan.change_count == 1 for plan in report.plans)


class TestRemediationIsDeterministic:
    def test_repeated_runs_are_byte_identical(self):
        design = oversized_design()
        first = remediation_entries(build_remediation(design))
        second = remediation_entries(build_remediation(design))
        assert first == second


class TestEndToEndThroughTheDesigner:
    """The section 15.3 demo beat: it fails with a named fix, then the fix makes it pass."""

    def transgene(self):
        return cds_of_length(5_049 - CAG_OVERHEAD)

    def test_the_oversized_request_fails_and_names_the_substitution(self):
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="large therapeutic transgene",
                transgene_sequence=self.transgene(),
                target_tissue="ubiquitous",
                promoter_preference="promoter.cag",
                polya_preference="polya.bgh",
            )
        )
        assert bundle.design.total_bp == 5_055  # was 5_049: plus the 6 bp Kozak element
        assert bundle.report.overall is Severity.FAIL
        check = check_of(bundle.report, "aav.packaging_limit")
        assert check.severity is Severity.FAIL
        assert "355 bp over the target" in check.message
        assert "replace CAG (promoter.cag, 1,639 bp) with EFS (promoter.efs, 212 bp)" in check.message
        assert "saves 1,427 bp" in check.message
        assert "bringing the cassette to 3,628 bp" in check.message

    def test_applying_the_named_substitution_makes_it_pass(self):
        """Exactly the substitution the message named, nothing else changed."""
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="large therapeutic transgene",
                transgene_sequence=self.transgene(),
                target_tissue="ubiquitous",
                promoter_preference="promoter.efs",
                polya_preference="polya.bgh",
                include_wpre=False,
            )
        )
        assert bundle.design.total_bp == 3_628  # (was 3_622, plus 6 bp Kozak) the resulting_bp the plan predicted
        assert check_of(bundle.report, "aav.packaging_limit").severity is Severity.PASS
        assert bundle.report.overall is not Severity.FAIL

    def test_the_freed_capacity_lets_wpre_back_in(self):
        """With the default include_wpre, the 589 bp WPRE now fits again, and it still passes."""
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="large therapeutic transgene",
                transgene_sequence=self.transgene(),
                target_tissue="ubiquitous",
                promoter_preference="promoter.efs",
                polya_preference="polya.bgh",
            )
        )
        assert bundle.design.total_bp == 3_628 + 589
        assert check_of(bundle.report, "aav.packaging_limit").severity is Severity.PASS

    def test_the_self_complementary_failure_also_carries_remediation(self):
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="sc transgene",
                transgene_sequence=cds_of_length(600),
                target_tissue="ubiquitous",
                self_complementary=True,
                promoter_preference="promoter.cag",
                polya_preference="polya.bgh",
            )
        )
        assert bundle.design.total_bp == 2_760  # was 2_754: plus the 6 bp Kozak element
        # The single stranded band is not what fails here; the halved band is.
        assert check_of(bundle.report, "aav.packaging_limit").severity is Severity.PASS
        check = check_of(bundle.report, "aav.sc_capacity")
        assert check.severity is Severity.FAIL
        assert check.remediation
        assert "self complementary packaging target is 2,400 bp" in check.message
        assert "360 bp over the target" in check.message
        assert "promoter.efs" in " ".join(check.remediation)

    def test_the_wpre_removal_lever_appears_on_a_supplied_cassette(self):
        """Section 6.6's "dropping WPRE saves a further 600 bp" alternative, with real numbers."""
        design = build_design(
            cds=cds_of_length(2_385),
            promoter="promoter.cag",
            polya="polya.bgh",
            wpre="enhancer.wpre",
            target_tissue="ubiquitous",
        )
        check = check_of(AAVDesigner().evaluate(design).report, "aav.packaging_limit")
        assert check.severity is Severity.FAIL
        joined = " ".join(check.remediation)
        assert "remove enhancer.wpre (saves 589 bp)" in joined
