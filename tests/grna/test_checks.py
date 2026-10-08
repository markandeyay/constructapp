"""Each of the nine section 8.5 checks, plus the section 8.6 off-target check.

For every check there is a case where it passes and at least one case where it
fires at the severity the section 8.5 table gives it. Where a check can be
unevaluable there is a case for that too, and it asserts UNKNOWN rather than
PASS (section 3.3 constraint 4).

Every message is asserted to name the next action, which is section 5.4 rule 2.
"""

from __future__ import annotations

import pytest

from packages.core.schemas.capability import Severity
from packages.core.schemas.grna import GuideRNADesign, GuideSpec, OffTargetSpace
from packages.core.sequence import reverse_complement
from packages.validation.grna import GuideRNAValidator
from packages.validation.grna.checks import SECTION_8_5_CHECK_IDS

from .conftest import FIXED_TIME, make_design, make_request, message_of, severity_of

#: A 20 nt spacer that passes every section 8.5 check: GC 0.55, no TTTT, no run
#: over 4, no stem of 7 bp, no BbsI site.
CLEAN_SPACER = "GCATCAGCTAGGACTGACTG"
LEFT = "CCAACCAACCA"
RIGHT = "ACCAACCAACCAACCAACCAACCAACCAACC"
#: Length of the SpCas9 target built by `spcas9_target`: 11 + 20 + 3 + 31.
CLEAN_TARGET_LENGTH = 65
#: The blunt cut for the clean guide: 3 nt 5' of the PAM at position 31.
CLEAN_CUT_SITE = 28


def spcas9_target(spacer: str, pam: str = "AGG", left: str = LEFT, right: str = RIGHT) -> str:
    return left + spacer + pam + right


def validate(design: GuideRNADesign):
    return GuideRNAValidator(evaluated_at=FIXED_TIME).validate(design)


def clean_design(**overrides: object) -> GuideRNADesign:
    overrides.setdefault("target_sequence", spcas9_target(CLEAN_SPACER))
    overrides.setdefault("cds_region", (0, CLEAN_TARGET_LENGTH))
    return make_design(CLEAN_SPACER, "AGG", **overrides)


class TestEveryCheckIsAlwaysReported:
    def test_all_nine_section_8_5_checks_plus_the_off_target_check(self) -> None:
        report = validate(clean_design())
        reported = [check.check_id for check in report.checks]
        assert reported[:9] == list(SECTION_8_5_CHECK_IDS)
        assert reported[9] == "grna.off_target_hits"
        assert len(reported) == 10

    def test_a_clean_guide_passes_everything(self) -> None:
        report = validate(
            clean_design(
                delivery_construct_name="pTEST",
                delivery_construct_sequence="CCAACCAA" + CLEAN_SPACER + "GTTTTAGAGCTAGAAA",
            )
        )
        assert report.overall == Severity.PASS, [
            (check.check_id, check.severity, check.message)
            for check in report.checks
            if check.severity != Severity.PASS
        ]

    def test_every_message_is_non_trivial(self) -> None:
        report = validate(clean_design())
        for check in report.checks:
            assert len(check.message) > 40, check.check_id
            assert check.threshold, check.check_id


class TestCheck1PamValid:
    """FAIL. The PAM must match the motif AND sit at the correct offset."""

    def test_pass(self) -> None:
        report = validate(clean_design())
        assert severity_of(report, "grna.pam_valid") == "pass"

    def test_no_valid_pam_fails(self) -> None:
        target = spcas9_target(CLEAN_SPACER, pam="TTA")
        design = make_design(CLEAN_SPACER, "TTA", target_sequence=target)
        report = validate(design)
        assert severity_of(report, "grna.pam_valid") == "fail"
        message = message_of(report, "grna.pam_valid")
        assert "not a SpCas9 PAM" in message
        assert "NGG" in message

    def test_alternative_nag_pam_warns_rather_than_passes(self) -> None:
        target = spcas9_target(CLEAN_SPACER, pam="AAG")
        design = make_design(CLEAN_SPACER, "AAG", target_sequence=target)
        report = validate(design)
        assert severity_of(report, "grna.pam_valid") == "warn"
        assert "alternative PAM" in message_of(report, "grna.pam_valid")

    def test_cas9_offset_applied_to_cas12a_fails_with_the_offset_named(self) -> None:
        """The section 9.4 known-bad case: a Cas12a guide scored with a 3' PAM.

        The target carries a real TTTA PAM 5' of the spacer and a decoy TTTC 3'
        of it. A caller that took the PAM from the 3' side supplies TTTC, which
        satisfies the TTTV motif but is in the wrong place, and this check says
        so and names the right PAM.
        """
        spacer = "GCACGTCAGTCAGGATCCAGTCC"
        target = "CCAGGCACCAGGCACC" + "TTTA" + spacer + "TTTC" + "AGGCACCAGGCACC"
        design = GuideRNADesign(
            request=make_request(
                target_sequence=target,
                nuclease="LbCas12a",
                cloning_vector="pu6_lb_crrna",
            ),
            guide=GuideSpec(spacer=spacer, pam="TTTC", strand=1),
        )
        report = validate(design)
        assert severity_of(report, "grna.pam_valid") == "fail"
        message = message_of(report, "grna.pam_valid")
        assert "TTTA" in message, "the correct PAM is named"
        assert "5' of the spacer" in message
        assert "offset error" in message

    def test_cas12a_with_the_correct_five_prime_pam_passes(self) -> None:
        spacer = "GCACGTCAGTCAGGATCCAGTCC"
        target = "CCAGGCACCAGGCACC" + "TTTA" + spacer + "TTTC" + "AGGCACCAGGCACC"
        design = GuideRNADesign(
            request=make_request(
                target_sequence=target,
                nuclease="LbCas12a",
                cloning_vector="pu6_lb_crrna",
            ),
            guide=GuideSpec(spacer=spacer, pam="TTTA", strand=1),
        )
        report = validate(design)
        assert severity_of(report, "grna.pam_valid") == "pass"

    def test_an_unlocatable_guide_is_unknown_not_pass(self) -> None:
        design = make_design(CLEAN_SPACER, "AGG", target_sequence="ACGT" * 30)
        report = validate(design)
        assert severity_of(report, "grna.pam_valid") == "unknown"
        assert "does not occur" in message_of(report, "grna.pam_valid")

    def test_a_strand_mistake_is_hinted(self) -> None:
        target = spcas9_target(reverse_complement(CLEAN_SPACER))
        design = make_design(CLEAN_SPACER, "AGG", target_sequence=target, strand=1)
        report = validate(design)
        assert severity_of(report, "grna.pam_valid") == "unknown"
        assert "strand" in message_of(report, "grna.pam_valid")


class TestCheck2SpacerLength:
    """FAIL."""

    def test_pass(self) -> None:
        assert severity_of(validate(clean_design()), "grna.spacer_length") == "pass"

    @pytest.mark.parametrize(
        ("nuclease", "spacer", "expected_length"),
        [
            ("SpCas9", "GCATCAGCTAGGACTGACT", 20),
            ("SaCas9", "GCATCAGCTAGGACTGACTG", 21),
            ("LbCas12a", "GCATCAGCTAGGACTGACTG", 23),
        ],
    )
    def test_wrong_length_fails_and_names_the_requirement(
        self, nuclease: str, spacer: str, expected_length: int
    ) -> None:
        design = make_design(
            spacer,
            "AGG" if nuclease != "LbCas12a" else "TTTA",
            target_sequence=spcas9_target(spacer),
            nuclease=nuclease,
        )
        report = validate(design)
        assert severity_of(report, "grna.spacer_length") == "fail"
        message = message_of(report, "grna.spacer_length")
        assert f"{expected_length} nt" in message
        assert str(len(spacer)) in message


class TestCheck3GcContent:
    """WARN."""

    def test_pass(self) -> None:
        assert severity_of(validate(clean_design()), "grna.gc_content") == "pass"

    def test_too_low_warns_and_says_why(self) -> None:
        spacer = "ATATATCAGATATATCAGAT"  # GC 0.20
        design = make_design(spacer, "AGG", target_sequence=spcas9_target(spacer))
        report = validate(design)
        assert severity_of(report, "grna.gc_content") == "warn"
        message = message_of(report, "grna.gc_content")
        assert "0.20" in message
        assert "0.40 to 0.70" in message
        assert "binds weakly" in message

    def test_too_high_warns_and_says_why(self) -> None:
        spacer = "GCGCGCGACGCGCGCGACGC"  # GC 0.85
        design = make_design(spacer, "AGG", target_sequence=spcas9_target(spacer))
        report = validate(design)
        assert severity_of(report, "grna.gc_content") == "warn"
        assert "off-target" in message_of(report, "grna.gc_content")

    def test_the_window_is_configurable(self) -> None:
        from packages.validation.grna import GuideRNAThresholds

        spacer = "ATATATCAGATATATCAGAT"
        design = make_design(spacer, "AGG", target_sequence=spcas9_target(spacer))
        widened = GuideRNAValidator(
            thresholds=GuideRNAThresholds(spacer_gc_min=0.20, spacer_gc_max=0.90),
            evaluated_at=FIXED_TIME,
        ).validate(design)
        assert severity_of(widened, "grna.gc_content") == "pass"


class TestCheck4U6Terminator:
    """FAIL when U6-driven, WARN otherwise."""

    SPACER = "GCATCTTTTAGGACTGACTG"

    def test_pass(self) -> None:
        assert severity_of(validate(clean_design()), "grna.u6_terminator") == "pass"

    def test_u6_driven_fails(self) -> None:
        design = make_design(
            self.SPACER,
            "AGG",
            target_sequence=spcas9_target(self.SPACER),
            expression_system="u6_plasmid",
        )
        report = validate(design)
        assert severity_of(report, "grna.u6_terminator") == "fail"
        message = message_of(report, "grna.u6_terminator")
        assert "TTTT" in message
        assert "U6 driven" in message
        assert "different guide" in message

    @pytest.mark.parametrize("system", ["t7_in_vitro", "other"])
    def test_not_u6_driven_warns(self, system: str) -> None:
        design = make_design(
            self.SPACER,
            "AGG",
            target_sequence=spcas9_target(self.SPACER),
            expression_system=system,
        )
        report = validate(design)
        assert severity_of(report, "grna.u6_terminator") == "warn"

    def test_the_motif_is_configurable(self) -> None:
        from packages.validation.grna import GuideRNAThresholds

        design = clean_design()
        report = GuideRNAValidator(
            thresholds=GuideRNAThresholds(u6_terminator_motif="GCAT"),
            evaluated_at=FIXED_TIME,
        ).validate(design)
        assert severity_of(report, "grna.u6_terminator") == "fail"


class TestCheck5Homopolymer:
    """WARN."""

    SPACER = "GGGGGCATCAGCTATTACAA"  # five G in a row, GC 0.50

    def test_pass(self) -> None:
        assert severity_of(validate(clean_design()), "grna.homopolymer") == "pass"

    def test_a_run_over_the_maximum_warns(self) -> None:
        design = make_design(
            self.SPACER, "AGG", target_sequence=spcas9_target(self.SPACER)
        )
        report = validate(design)
        assert severity_of(report, "grna.homopolymer") == "warn"
        message = message_of(report, "grna.homopolymer")
        assert "5 x G" in message
        assert "maximum of 4" in message
        assert "Shift the guide" in message

    def test_the_maximum_is_configurable(self) -> None:
        from packages.validation.grna import GuideRNAThresholds

        design = make_design(
            self.SPACER, "AGG", target_sequence=spcas9_target(self.SPACER)
        )
        report = GuideRNAValidator(
            thresholds=GuideRNAThresholds(max_homopolymer_run=6), evaluated_at=FIXED_TIME
        ).validate(design)
        assert severity_of(report, "grna.homopolymer") == "pass"


class TestCheck6SelfComplementarity:
    """WARN."""

    #: A 7 bp stem (GCATCAG pairing with CTGATGC) closing a 3 nt loop.
    SPACER = "GCATCAGTTACTGATGCGCA"

    def test_pass(self) -> None:
        assert severity_of(validate(clean_design()), "grna.self_complementarity") == "pass"

    def test_a_long_stem_warns_and_reports_the_stem(self) -> None:
        design = make_design(
            self.SPACER, "AGG", target_sequence=spcas9_target(self.SPACER)
        )
        report = validate(design)
        assert severity_of(report, "grna.self_complementarity") == "warn"
        message = message_of(report, "grna.self_complementarity")
        assert "GCATCAG" in message
        assert "7 bp" in message
        assert "not a free energy calculation" in message

    def test_the_reporting_length_is_configurable(self) -> None:
        from packages.validation.grna import GuideRNAThresholds

        design = make_design(
            self.SPACER, "AGG", target_sequence=spcas9_target(self.SPACER)
        )
        report = GuideRNAValidator(
            thresholds=GuideRNAThresholds(max_self_complement_stem_nt=9),
            evaluated_at=FIXED_TIME,
        ).validate(design)
        assert severity_of(report, "grna.self_complementarity") == "pass"


class TestCheck7PositionInCds:
    """WARN."""

    def test_pass_early_in_the_coding_sequence(self) -> None:
        report = validate(clean_design(cds_region=(0, CLEAN_TARGET_LENGTH)))
        assert severity_of(report, "grna.position_in_cds") == "pass"

    def test_no_cds_annotation_is_unknown_not_pass(self) -> None:
        report = validate(clean_design(cds_region=None))
        assert severity_of(report, "grna.position_in_cds") == "unknown"
        assert "no cds_region was supplied" in message_of(report, "grna.position_in_cds")

    def test_late_in_the_coding_sequence_warns(self) -> None:
        report = validate(clean_design(cds_region=(0, 30)))
        message = message_of(report, "grna.position_in_cds")
        assert severity_of(report, "grna.position_in_cds") == "warn"
        assert "past the configured limit of 60%" in message

    def test_the_final_exon_warns_and_explains(self) -> None:
        report = validate(clean_design(cds_region=(0, CLEAN_TARGET_LENGTH), final_exon_region=(25, CLEAN_TARGET_LENGTH)))
        assert severity_of(report, "grna.position_in_cds") == "warn"
        message = message_of(report, "grna.position_in_cds")
        assert "final exon" in message
        assert "truncated protein" in message

    def test_outside_the_coding_sequence_warns(self) -> None:
        report = validate(clean_design(cds_region=(40, CLEAN_TARGET_LENGTH)))
        assert severity_of(report, "grna.position_in_cds") == "warn"
        assert "outside the coding sequence" in message_of(report, "grna.position_in_cds")

    def test_a_non_constitutive_cut_warns(self) -> None:
        report = validate(
            clean_design(cds_region=(0, CLEAN_TARGET_LENGTH), constitutive_regions=((35, CLEAN_TARGET_LENGTH),))
        )
        assert severity_of(report, "grna.position_in_cds") == "warn"
        assert "constitutive region" in message_of(report, "grna.position_in_cds")

    @pytest.mark.parametrize("intent", ["knockin", "activation", "interference"])
    def test_other_intents_pass_with_the_reason_stated(self, intent: str) -> None:
        report = validate(clean_design(edit_intent=intent, cds_region=None))
        assert severity_of(report, "grna.position_in_cds") == "pass"
        message = message_of(report, "grna.position_in_cds")
        assert intent in message
        assert "does not constrain" in message

    def test_the_fraction_is_configurable(self) -> None:
        from packages.validation.grna import GuideRNAThresholds

        design = clean_design(cds_region=(0, 30))
        report = GuideRNAValidator(
            thresholds=GuideRNAThresholds(knockout_cds_max_fraction=0.95),
            evaluated_at=FIXED_TIME,
        ).validate(design)
        assert severity_of(report, "grna.position_in_cds") == "pass"


class TestCheck8SelfTargeting:
    """FAIL."""

    def test_no_construct_supplied_is_unknown_not_pass(self) -> None:
        report = validate(clean_design())
        assert severity_of(report, "grna.self_targeting") == "unknown"
        assert "No delivery construct sequence was supplied" in message_of(
            report, "grna.self_targeting"
        )

    def test_a_construct_carrying_the_spacer_next_to_a_pam_fails(self) -> None:
        construct = "CCAACCAACCAA" + CLEAN_SPACER + "AGGCCAACCAACCAA"
        report = validate(
            clean_design(
                delivery_construct_name="pBAD",
                delivery_construct_sequence=construct,
            )
        )
        assert severity_of(report, "grna.self_targeting") == "fail"
        message = message_of(report, "grna.self_targeting")
        assert "pBAD" in message
        assert "cut the vector" in message
        assert "ribonucleoprotein" in message

    def test_a_construct_carrying_the_spacer_followed_by_the_scaffold_passes(self) -> None:
        """The normal case. A guide cassette always contains its own spacer.

        In pX330 and its derivatives the spacer is followed by the scaffold,
        which starts GTTTTAGAG, so the three bases after the spacer are GTT and
        there is no PAM. A check that only looked for the spacer would flag
        every design.
        """
        construct = "GGAAAGGACGAAACACCG" + CLEAN_SPACER + "GTTTTAGAGCTAGAAATAGCAAG"
        report = validate(
            clean_design(
                delivery_construct_name="pX330-TEST",
                delivery_construct_sequence=construct,
            )
        )
        assert severity_of(report, "grna.self_targeting") == "pass"
        assert "will not cut its own" in message_of(report, "grna.self_targeting")

    def test_a_near_match_with_a_clean_seed_warns(self) -> None:
        # One mismatch at spacer position 1, which is PAM-distal and so outside
        # the 12 nt seed.
        mutated = "T" + CLEAN_SPACER[1:]
        construct = "CCAACCAACCAA" + mutated + "AGGCCAACCAACC"
        report = validate(
            clean_design(
                delivery_construct_name="pNEAR",
                delivery_construct_sequence=construct,
            )
        )
        assert severity_of(report, "grna.self_targeting") == "warn"
        assert "near match" in message_of(report, "grna.self_targeting")

    def test_the_construct_is_searched_even_when_the_scope_is_none(self) -> None:
        """Section 8.6: construct searching is always available."""
        construct = "CCAACCAACCAA" + CLEAN_SPACER + "AGGCCAACCAACCAA"
        report = validate(
            clean_design(
                off_target_space=OffTargetSpace(scope="none"),
                delivery_construct_name="pBAD",
                delivery_construct_sequence=construct,
            )
        )
        assert severity_of(report, "grna.self_targeting") == "fail"
        assert severity_of(report, "grna.off_target_hits") == "unknown"


class TestCheck9RestrictionInSpacer:
    """WARN."""

    SPACER = "GCATGAAGACTAGGCATCAG"  # contains the BbsI site GAAGAC

    def test_pass(self) -> None:
        assert severity_of(validate(clean_design()), "grna.restriction_in_spacer") == "pass"

    def test_the_cloning_enzyme_site_warns_and_names_the_vector(self) -> None:
        design = make_design(
            self.SPACER,
            "AGG",
            target_sequence=spcas9_target(self.SPACER),
            cloning_vector="px330",
        )
        report = validate(design)
        assert severity_of(report, "grna.restriction_in_spacer") == "warn"
        message = message_of(report, "grna.restriction_in_spacer")
        assert "BbsI" in message
        assert "GAAGAC" in message
        assert "Addgene 42230" in message
        assert "both strands" in message

    def test_both_strands_are_checked(self) -> None:
        """Appendix D: the recognition site is not palindromic, so check both."""
        reverse_site_spacer = "GCATGTCTTCTAGGCATCAG"  # GTCTTC is GAAGAC reversed
        design = make_design(
            reverse_site_spacer,
            "AGG",
            target_sequence=spcas9_target(reverse_site_spacer),
            cloning_vector="px330",
        )
        report = validate(design)
        assert severity_of(report, "grna.restriction_in_spacer") == "warn"
        assert "reverse strand" in message_of(report, "grna.restriction_in_spacer")

    def test_a_vector_without_a_declared_enzyme_is_unknown_not_pass(self) -> None:
        spacer = "GCACGTCAGTCAGGATCCAGTCC"
        target = "CCAGGCACC" + "TTTA" + spacer + "AGGCACCAGG"
        design = GuideRNADesign(
            request=make_request(
                target_sequence=target,
                nuclease="LbCas12a",
                cloning_vector="pu6_lb_crrna",
            ),
            guide=GuideSpec(spacer=spacer, pam="TTTA", strand=1),
        )
        report = validate(design)
        assert severity_of(report, "grna.restriction_in_spacer") == "unknown"
        assert "does not declare a Type IIS digest enzyme" in message_of(
            report, "grna.restriction_in_spacer"
        )

    def test_a_different_vector_enzyme_changes_the_verdict(self) -> None:
        design = make_design(
            self.SPACER,
            "AGG",
            target_sequence=spcas9_target(self.SPACER),
            cloning_vector="lenticrispr_v2",  # BsmBI, CGTCTC
        )
        report = validate(design)
        assert severity_of(report, "grna.restriction_in_spacer") == "pass"


class TestOffTargetCheck:
    """Section 8.6 severity: FAIL, WARN, PASS, UNKNOWN."""

    SPACER = "GCACGTCAGTCAGGATCCAG"

    def _design(self, fasta_path: str | None = None, **overrides: object) -> GuideRNADesign:
        space = (
            OffTargetSpace(scope="supplied_fasta", fasta_path=fasta_path)
            if fasta_path
            else OffTargetSpace(scope="construct_only")
        )
        overrides.setdefault("off_target_space", space)
        overrides.setdefault("target_sequence", spcas9_target(self.SPACER))
        overrides.setdefault("cds_region", (0, CLEAN_TARGET_LENGTH))
        return make_design(self.SPACER, "AGG", **overrides)

    def test_a_clean_space_passes_and_states_the_space(self) -> None:
        report = validate(self._design())
        assert severity_of(report, "grna.off_target_hits") == "pass"
        message = message_of(report, "grna.off_target_hits")
        assert "This is not a genome-wide search." in message
        assert "Sites outside it were not examined." in message

    def test_scope_none_is_unknown_not_pass(self) -> None:
        report = validate(self._design(off_target_space=OffTargetSpace(scope="none")))
        assert severity_of(report, "grna.off_target_hits") == "unknown"
        message = message_of(report, "grna.off_target_hits")
        assert "No off-target search was performed." in message
        assert "No off-target verdict can be given" in message

    def test_a_near_site_with_a_clean_seed_fails(self, tmp_path) -> None:
        """One mismatch at a PAM-distal position: the seed is intact, so FAIL."""
        decoy = "T" + self.SPACER[1:]
        fasta = tmp_path / "decoy.fa"
        fasta.write_text(">decoy_contig\nCCAACCAACC" + decoy + "TGGCCAACCAACC\n")
        report = validate(self._design(fasta_path=str(fasta)))
        assert severity_of(report, "grna.off_target_hits") == "fail"
        message = message_of(report, "grna.off_target_hits")
        assert "decoy_contig" in message
        assert "seed" in message
        assert "This is not a genome-wide search." in message
        assert "different guide" in message

    def test_a_site_with_seed_mismatches_only_warns(self, tmp_path) -> None:
        """Three mismatches all inside the PAM-proximal seed: WARN, not FAIL."""
        decoy = self.SPACER[:17] + "".join(
            "A" if base != "A" else "C" for base in self.SPACER[17:]
        )
        fasta = tmp_path / "decoy.fa"
        fasta.write_text(">decoy_contig\nCCAACCAACC" + decoy + "TGGCCAACCAACC\n")
        report = validate(self._design(fasta_path=str(fasta)))
        assert severity_of(report, "grna.off_target_hits") == "warn"
        message = message_of(report, "grna.off_target_hits")
        assert "moderate rather than disqualifying" in message
        assert "This is not a genome-wide search." in message

    def test_a_decoy_without_a_pam_is_not_reported(self, tmp_path) -> None:
        decoy = "T" + self.SPACER[1:]
        fasta = tmp_path / "decoy.fa"
        fasta.write_text(">decoy_contig\nCCAACCAACC" + decoy + "TTTCCAACCAACC\n")
        report = validate(self._design(fasta_path=str(fasta)))
        assert severity_of(report, "grna.off_target_hits") == "pass"

    def test_the_fail_threshold_is_configurable(self, tmp_path) -> None:
        from packages.validation.grna import GuideRNAThresholds

        decoy = "T" + self.SPACER[1:]
        fasta = tmp_path / "decoy.fa"
        fasta.write_text(">decoy_contig\nCCAACCAACC" + decoy + "TGGCCAACCAACC\n")
        design = self._design(fasta_path=str(fasta))
        report = GuideRNAValidator(
            thresholds=GuideRNAThresholds(off_target_fail_max_mismatches=0),
            evaluated_at=FIXED_TIME,
        ).validate(design)
        assert severity_of(report, "grna.off_target_hits") == "warn"


class TestUnknownNeverImprovesTheVerdict:
    """Section 5.4 rule 1 and section 3.3 constraint 4."""

    def test_a_report_with_unknown_checks_is_not_a_pass_by_default(self) -> None:
        report = validate(clean_design())
        unknown = {check.check_id for check in report.unknown_checks}
        assert "grna.self_targeting" in unknown
        # The overall verdict is still derived from the evaluable checks only,
        # and the unknown ones are listed separately for the UI.
        assert report.overall == Severity.PASS
        assert unknown

    def test_a_failing_check_beats_an_unknown_one(self) -> None:
        target = spcas9_target(CLEAN_SPACER, pam="TTA")
        design = make_design(CLEAN_SPACER, "TTA", target_sequence=target, cds_region=(0, CLEAN_TARGET_LENGTH))
        report = validate(design)
        assert report.overall == Severity.FAIL
