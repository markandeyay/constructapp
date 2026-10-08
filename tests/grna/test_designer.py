"""The section 8.7 output surface: ranked table, reasoning, oligos, exports.

Also the section 3.3 constraint 3 determinism requirement at whole-pipeline
level, and the section 16 wording requirements on everything the pipeline
emits.
"""

from __future__ import annotations

import pytest

from packages.core.schemas.capability import CapabilityKind, Severity
from packages.core.schemas.grna import OffTargetSpace
from packages.generation.grna import (
    GuideRNAGenerator,
    cloning_plan,
    render_guide_table,
    render_oligo_table,
)
from packages.validation.grna import CLONING_VECTORS, IVT_TEMPLATES

from .conftest import FIXED_TIME, make_request


def generator() -> GuideRNAGenerator:
    return GuideRNAGenerator(evaluated_at=FIXED_TIME)


class TestEndToEnd:
    def test_a_request_produces_a_ranked_table(self) -> None:
        result = generator().compose(make_request())
        assert result.capability == CapabilityKind.GUIDE_RNA
        assert result.guides_enumerated > 0
        assert 0 < len(result.guides_returned) <= 5
        assert [row.rank for row in result.guides_returned] == list(
            range(1, len(result.guides_returned) + 1)
        )

    def test_every_row_carries_its_own_report_and_reasoning(self) -> None:
        result = generator().compose(make_request())
        for row in result.guides_returned:
            assert len(row.report.checks) == 10
            assert row.report.capability == CapabilityKind.GUIDE_RNA
            assert len(row.reasoning) >= 4
            assert row.cloning is not None
            assert row.cloning.oligos

    def test_both_strands_appear_in_the_enumeration_notes(self) -> None:
        result = generator().compose(make_request())
        note = next(note for note in result.notes if "Both strands" in note)
        assert "forward-strand" in note and "reverse-strand" in note

    def test_no_returned_guide_has_a_failing_report(self) -> None:
        result = generator().compose(make_request())
        for row in result.guides_returned:
            assert Severity(row.report.overall) != Severity.FAIL

    def test_a_target_with_no_pam_returns_nothing_and_says_why(self) -> None:
        result = generator().compose(
            make_request(target_sequence="ATATATATATATATATATATATATATATATAT")
        )
        assert result.guides_returned == []
        assert any("No guide passed validation" in note for note in result.notes) or (
            result.guides_enumerated == 0
        )

    def test_design_result_satisfies_the_section_5_1_contract(self) -> None:
        _result, design_result = generator().design_result(make_request())
        assert design_result.capability == CapabilityKind.GUIDE_RNA
        assert design_result.parameters_used, "section 5.4 rule 3"
        assert design_result.provenance, "section 5.4 rule 5"
        assert set(design_result.artifacts) == {
            "guide_table.tsv",
            "oligo_order_table.tsv",
            "off_target_space.txt",
        }

    def test_provenance_attributes_every_source(self) -> None:
        _result, design_result = generator().design_result(
            make_request(
                delivery_construct_name="pTEST",
                delivery_construct_sequence="ACGT" * 50,
            )
        )
        joined = " ".join(design_result.provenance)
        assert "user_input:target_sequence:TEST_TARGET" in joined
        assert "user_input:delivery_construct_sequence:pTEST" in joined
        assert "cloning_vector:px330" in joined
        assert "on_target_model:" in joined
        assert "off_target_model:" in joined
        assert "on_target_fallback:" in joined


class TestDeterminism:
    def test_two_runs_agree_exactly(self) -> None:
        request = make_request()
        first = generator().compose(request)
        second = generator().compose(request)
        assert first.model_dump() == second.model_dump()

    def test_the_design_id_is_derived_from_the_input(self) -> None:
        request = make_request()
        assert generator().compose(request).design_id == generator().compose(request).design_id
        other = make_request(nuclease="SaCas9")
        assert generator().compose(other).design_id != generator().compose(request).design_id

    def test_ranking_has_no_ties(self) -> None:
        result = generator().compose(make_request(max_guides_returned=10))
        ids = [row.guide_id for row in result.guides_returned]
        assert len(ids) == len(set(ids))


class TestRankingPolicy:
    def test_a_heuristic_ranked_guide_never_outranks_a_published_scored_one(self) -> None:
        result = generator().compose(make_request(max_guides_returned=20))
        seen_withheld = False
        for row in result.guides_returned:
            if row.on_target.score is None:
                seen_withheld = True
            elif seen_withheld:
                pytest.fail(
                    "a guide with a published score was ranked below one without a score"
                )

    def test_out_of_domain_requests_rank_by_the_labeled_heuristic_and_say_so(self) -> None:
        result = generator().compose(make_request(nuclease="SaCas9"))
        assert result.guides_returned
        for row in result.guides_returned:
            assert row.on_target.score is None
            assert row.on_target.status == "out_of_domain"
        assert any("labeled heuristic" in note for note in result.notes)

    def test_alternative_pam_guides_sort_after_primary_ones(self) -> None:
        result = generator().compose(make_request(max_guides_returned=50))
        flags = [row.pam_is_alternative for row in result.guides_returned]
        assert flags == sorted(flags), "primary PAM guides come first"


class TestOffTargetStatementEverywhere:
    """Section 8.6: the statement is shown verbatim in the UI and in every export."""

    @pytest.mark.parametrize("scope", ["construct_only", "none"])
    def test_statement_is_identical_at_the_top_level_and_on_every_row(self, scope: str) -> None:
        request = make_request(off_target_space=OffTargetSpace(scope=scope))
        result = generator().compose(request)
        assert result.off_target_space_statement.endswith("This is not a genome-wide search.")
        for row in result.guides_returned:
            assert row.off_target.space_statement == result.off_target_space_statement

    @pytest.mark.parametrize("scope", ["construct_only", "supplied_fasta", "none"])
    def test_both_exports_begin_with_the_statement(self, scope: str, tmp_path) -> None:
        if scope == "supplied_fasta":
            fasta = tmp_path / "x.fa"
            fasta.write_text(">chrX\n" + "ACGT" * 100 + "\n")
            space = OffTargetSpace(scope=scope, fasta_path=str(fasta))
        else:
            space = OffTargetSpace(scope=scope)
        result = generator().compose(make_request(off_target_space=space))
        statement = result.off_target_space_statement
        assert render_guide_table(result).startswith(statement)
        assert render_oligo_table(result).startswith(statement)

    def test_scope_none_states_it_prominently_in_the_exports(self) -> None:
        result = generator().compose(
            make_request(off_target_space=OffTargetSpace(scope="none"))
        )
        for export in (render_guide_table(result), render_oligo_table(result)):
            assert export.startswith("No off-target search was performed.")

    @pytest.mark.parametrize("banned", ["genome-wide search of", "comprehensive", "exhaustive"])
    def test_section_16_banned_wordings_do_not_appear(self, banned: str) -> None:
        result = generator().compose(make_request())
        blob = " ".join(
            [result.off_target_space_statement]
            + result.notes
            + [line for row in result.guides_returned for line in row.reasoning]
            + [check.message for row in result.guides_returned for check in row.report.checks]
        ).lower()
        assert banned not in blob

    @pytest.mark.parametrize("banned", ["validated", "measured", "guaranteed"])
    def test_scores_are_never_called_validated_or_measured(self, banned: str) -> None:
        result = generator().compose(make_request())
        for row in result.guides_returned:
            for field in (
                row.on_target.model_name,
                row.on_target.disclaimer,
                row.off_target.specificity_model_name,
                row.off_target.disclaimer,
            ):
                assert banned not in field.lower()


class TestReasoningIsTheDifferentiator:
    """Section 8.7: "which features drove the score up or down"."""

    def test_the_reasoning_names_the_model_and_its_drivers(self) -> None:
        result = generator().compose(make_request(max_guides_returned=10))
        scored = [row for row in result.guides_returned if row.on_target.score is not None]
        assert scored, "at least one guide should be in the model's domain"
        row = scored[0]
        text = " ".join(row.reasoning)
        assert row.on_target.model_name in text
        assert "drove the published score" in text
        assert "Ranked by:" in text
        assert row.off_target.space_statement in text

    def test_contributions_carry_a_direction_and_a_weight(self) -> None:
        result = generator().compose(make_request(max_guides_returned=10))
        scored = [row for row in result.guides_returned if row.on_target.score is not None]
        for item in scored[0].on_target.reasoning:
            assert item.direction in {"up", "down", "neutral"}
            assert item.detail

    def test_a_warned_guide_explains_the_warning_in_its_reasoning(self) -> None:
        result = generator().compose(
            make_request(max_guides_returned=20, cds_region=(0, 40))
        )
        warned = [
            row
            for row in result.guides_returned
            if Severity(row.report.overall) == Severity.WARN
        ]
        assert warned
        text = " ".join(warned[0].reasoning)
        assert "WARN " in text


class TestCloningOligos:
    """Section 8.7: cloning-ready oligos including the required 5' overhangs."""

    def test_the_vector_overhangs_are_applied(self) -> None:
        request = make_request(cloning_vector="px330")
        plan = cloning_plan(request, "GCATCAGCTAGGACTGACTG", "g1")
        sense, antisense = plan.oligos
        assert sense.sequence == "CACC" + "GCATCAGCTAGGACTGACTG"
        assert antisense.sequence == "AAAC" + "CAGTCAGTCCTAGCTGATGC"
        assert plan.digest_enzyme == "BbsI"
        assert "Addgene 42230" in plan.vector_name

    def test_a_spacer_without_a_five_prime_g_gets_one_with_the_reason(self) -> None:
        request = make_request(cloning_vector="px330")
        plan = cloning_plan(request, "ACATCAGCTAGGACTGACTG", "g1")
        sense, antisense = plan.oligos
        assert sense.sequence == "CACC" + "G" + "ACATCAGCTAGGACTGACTG"
        assert antisense.sequence == "AAAC" + "CAGTCAGTCCTAGCTGATGT" + "C"
        assert any("U6 promoter" in note for note in sense.notes)

    def test_the_mlm3636_suffix_is_applied(self) -> None:
        request = make_request(cloning_vector="mlm3636")
        plan = cloning_plan(request, "GCATCAGCTAGGACTGACTG", "g1")
        assert plan.oligos[0].sequence == "ACACC" + "GCATCAGCTAGGACTGACTG" + "G"
        assert plan.oligos[1].sequence == "AAAAC" + "CAGTCAGTCCTAGCTGATGC" + "G"

    def test_cas12a_vectors_use_their_own_overhangs_and_need_no_five_prime_g(self) -> None:
        request = make_request(nuclease="LbCas12a", cloning_vector="pu6_lb_crrna")
        plan = cloning_plan(request, "ACACGTCAGTCAGGATCCAGTCC", "g1")
        assert plan.oligos[0].sequence == "AGAT" + "ACACGTCAGTCAGGATCCAGTCC"
        assert plan.oligos[1].sequence == "AAAA" + "GGACTGGATCCTGACTGACGTGT"
        assert plan.oligos[0].notes == []

    def test_in_vitro_transcription_uses_the_nuclease_scaffold(self) -> None:
        request = make_request(expression_system="t7_in_vitro")
        plan = cloning_plan(request, "GCATCAGCTAGGACTGACTG", "g1")
        template = IVT_TEMPLATES["SpCas9"]
        assert plan.oligos[0].sequence == (
            template.target_prefix + "GCATCAGCTAGGACTGACTG" + template.target_suffix
        )
        assert plan.oligos[1].sequence == template.constant_oligo

    def test_cas12a_in_vitro_transcription_refuses_rather_than_guessing(self) -> None:
        request = make_request(nuclease="LbCas12a", expression_system="t7_in_vitro")
        plan = cloning_plan(request, "ACACGTCAGTCAGGATCCAGTCC", "g1")
        assert plan.oligos == []
        assert any("applies only to SpCas9 and SaCas9" in note for note in plan.notes)

    def test_every_vector_declares_a_source_and_an_accession(self) -> None:
        for vector in CLONING_VECTORS.values():
            assert vector.accession.startswith("Addgene ")
            assert "CRISPOR" in vector.source
            assert vector.forward_overhang and vector.reverse_overhang

    def test_an_unknown_vector_fails_loudly(self) -> None:
        with pytest.raises(KeyError, match="unknown cloning vector"):
            cloning_plan(make_request(cloning_vector="nope"), "ACGTACGTACGTACGTACGT", "g1")

    def test_oligo_length_matches_the_sequence(self) -> None:
        result = generator().compose(make_request())
        for row in result.guides_returned:
            for oligo in row.cloning.oligos:  # type: ignore[union-attr]
                assert oligo.length_nt == len(oligo.sequence)


class TestExports:
    def test_the_guide_table_has_the_section_8_7_columns(self) -> None:
        result = generator().compose(make_request())
        header = render_guide_table(result).splitlines()[1].split("\t")
        assert header == [
            "rank",
            "spacer_5_to_3",
            "pam",
            "strand",
            "target_start",
            "target_end",
            "cut_site",
            "on_target_score",
            "on_target_model",
            "on_target_model_kind",
            "off_target_sites",
            "off_target_specificity",
            "flags",
        ]

    def test_the_oligo_table_lists_every_oligo(self) -> None:
        result = generator().compose(make_request())
        lines = render_oligo_table(result).strip().splitlines()
        expected = sum(len(row.cloning.oligos) for row in result.guides_returned)  # type: ignore[union-attr]
        assert len(lines) == expected + 2  # statement line plus header

    def test_a_withheld_score_is_printed_as_withheld_not_as_zero(self) -> None:
        result = generator().compose(make_request(nuclease="SaCas9"))
        table = render_guide_table(result)
        assert "withheld" in table
        assert "\t0.0\t" not in table


class TestSuppliedFastaScope:
    def test_a_planted_near_site_rejects_the_guide(self, tmp_path) -> None:
        """A one-mismatch PAM-distal decoy fails the guide out of the table."""
        baseline = generator().compose(make_request(max_guides_returned=1))
        spacer = baseline.guides_returned[0].spacer
        decoy = ("A" if spacer[0] != "A" else "C") + spacer[1:]
        fasta = tmp_path / "decoy.fa"
        fasta.write_text(">decoy\nCCAACCAACC" + decoy + "TGGCCAACCAACC\n")
        result = generator().compose(
            make_request(
                off_target_space=OffTargetSpace(
                    scope="supplied_fasta", fasta_path=str(fasta)
                ),
                max_guides_returned=50,
            )
        )
        returned = {row.spacer for row in result.guides_returned}
        assert spacer not in returned
        rejected = {entry["spacer"] for entry in result.rejected}
        assert spacer in rejected

    def test_the_statement_reports_the_real_supplied_size(self, tmp_path) -> None:
        fasta = tmp_path / "big.fa"
        fasta.write_text(">chrX\n" + "ACGT" * 2500 + "\n")
        result = generator().compose(
            make_request(
                off_target_space=OffTargetSpace(
                    scope="supplied_fasta", fasta_path=str(fasta)
                )
            )
        )
        assert "supplied 10.0 kb sequence set" in result.off_target_space_statement
