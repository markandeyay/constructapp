"""Section 6.8 outputs: the linear map, the length budget, GenBank and FASTA.

Section 6.8 and section 10.2 both say an AAV cassette is linear and that the
circular renderer must not be reused, so "nothing here is circular" is a test.
"""

from __future__ import annotations

import json
from io import StringIO

import pytest
from Bio import SeqIO

from packages.core.schemas.aav import AAVRequest, CassetteElementRole
from packages.generation.aav import (
    ARTIFACT_FASTA,
    ARTIFACT_GENBANK,
    ARTIFACT_LENGTH_BUDGET,
    ARTIFACT_LINEAR_MAP,
    AAVDesigner,
    length_budget,
    linear_map_payload,
    to_fasta,
    to_genbank,
)

from tests.aav.support import build_design, cds_of_length


@pytest.fixture
def design():
    return build_design(wpre="enhancer.wpre")


class TestLinearMap:
    def test_topology_is_always_linear(self, design):
        assert linear_map_payload(design)["topology"] == "linear"

    def test_every_element_has_both_coordinate_conventions(self, design):
        payload = linear_map_payload(design)
        for element in payload["elements"]:
            assert element["start_1based"] == element["start"] + 1
            assert element["end_1based"] == element["end"]
            assert element["length_bp"] == element["end"] - element["start"]

    def test_elements_tile_the_cassette_without_gaps_or_overlap(self, design):
        elements = linear_map_payload(design)["elements"]
        assert elements[0]["start"] == 0
        assert elements[-1]["end"] == design.total_bp
        for previous, current in zip(elements, elements[1:]):
            assert previous["end"] == current["start"]

    def test_the_band_is_reported_alongside_the_map(self, design):
        payload = linear_map_payload(design)
        assert payload["target_bp"] == 4_700
        assert payload["soft_limit_bp"] == 4_900
        assert payload["hard_limit_bp"] == 5_200

    def test_the_self_complementary_band_is_used_for_an_sc_design(self):
        sc = build_design(self_complementary=True)
        assert linear_map_payload(sc)["target_bp"] == 2_400

    def test_fractions_let_the_ui_draw_elements_to_scale(self, design):
        elements = linear_map_payload(design)["elements"]
        assert sum(element["fraction_of_cassette"] for element in elements) == pytest.approx(1.0, abs=1e-5)

    def test_the_json_form_is_byte_stable(self, design):
        from packages.generation.aav import linear_map_json

        assert linear_map_json(design) == linear_map_json(design)
        assert json.loads(linear_map_json(design))["topology"] == "linear"

    def test_no_part_id_is_lost(self, design):
        payload = linear_map_payload(design)
        assert [element["part_id"] for element in payload["elements"]] == [
            element.part_id for element in design.elements
        ]


class TestLengthBudget:
    def test_one_row_per_element(self, design):
        budget = length_budget(design)
        assert len(budget.rows) == len(design.elements)

    def test_the_running_total_accumulates(self, design):
        budget = length_budget(design)
        running = 0
        for row in budget.rows:
            running += row.length_bp
            assert row.running_total_bp == running
        assert running == budget.total_bp == design.total_bp

    def test_headroom_is_the_target_minus_the_running_total(self, design):
        budget = length_budget(design)
        for row in budget.rows:
            assert row.headroom_bp == budget.target_bp - row.running_total_bp

    def test_headroom_goes_negative_when_the_cassette_is_over(self):
        over = build_design(cds=cds_of_length(4_500), promoter="promoter.cag", target_tissue="ubiquitous")
        budget = length_budget(over)
        assert budget.headroom_bp < 0
        assert budget.rows[-1].headroom_bp == budget.headroom_bp

    def test_the_text_table_has_a_row_per_element_a_total_and_the_band(self, design):
        text = length_budget(design).to_text()
        lines = text.splitlines()
        assert "element" in lines[0] and "running" in lines[0] and "headroom" in lines[0]
        assert any("TOTAL" in line for line in lines)
        assert "target 4,700 bp, soft limit 4,900 bp, hard limit 5,200 bp" in text
        for element in design.elements:
            if element.part_id:
                assert element.part_id in text

    def test_the_basis_explains_which_band_applied(self, design):
        assert "Single stranded design" in length_budget(design).limit_basis
        sc = build_design(self_complementary=True)
        assert "halved self complementary band applies" in length_budget(sc).limit_basis

    def test_an_override_is_reported_in_the_basis(self):
        design = build_design(packaging_limit_bp=5_000)
        basis = length_budget(design).limit_basis
        assert "packaging_limit_bp was overridden to 5,000 bp" in basis
        assert "keeping the default band widths" in basis

    def test_the_table_is_byte_stable(self, design):
        assert length_budget(design).to_text() == length_budget(design).to_text()


class TestGenBankExport:
    def test_the_record_parses_and_is_linear(self, design):
        record = SeqIO.read(StringIO(to_genbank(design)), "genbank")
        assert record.annotations["topology"] == "linear"
        assert "circular" not in to_genbank(design).splitlines()[0].lower()

    def test_the_sequence_round_trips(self, design):
        record = SeqIO.read(StringIO(to_genbank(design)), "genbank")
        assert str(record.seq).upper() == design.cassette_sequence

    def test_every_element_is_a_feature_with_its_part_id(self, design):
        record = SeqIO.read(StringIO(to_genbank(design)), "genbank")
        element_features = [
            feature for feature in record.features if "construct_role" in feature.qualifiers
        ]
        assert len(element_features) == len(design.elements)
        for feature, element in zip(element_features, design.elements):
            assert feature.qualifiers["construct_role"][0] == CassetteElementRole(element.role).value
            assert feature.qualifiers["construct_part_id"][0] == (element.part_id or "none")

    def test_feature_coordinates_match_the_layout(self, design):
        record = SeqIO.read(StringIO(to_genbank(design)), "genbank")
        element_features = [
            feature for feature in record.features if "construct_role" in feature.qualifiers
        ]
        for feature, item in zip(element_features, design.layout()):
            assert int(feature.location.start) == item.start
            assert int(feature.location.end) == item.end

    def test_the_itrs_are_repeat_regions_and_the_polya_is_a_regulatory_feature(self, design):
        record = SeqIO.read(StringIO(to_genbank(design)), "genbank")
        by_role = {
            feature.qualifiers["construct_role"][0]: feature
            for feature in record.features
            if "construct_role" in feature.qualifiers
        }
        assert by_role["itr_5"].type == "repeat_region"
        assert by_role["itr_3"].type == "repeat_region"
        assert by_role["promoter"].type == "regulatory"
        assert by_role["promoter"].qualifiers["regulatory_class"] == ["promoter"]
        assert by_role["polya"].qualifiers["regulatory_class"] == ["polyA_signal_sequence"]
        assert by_role["cds"].type == "CDS"

    def test_the_cds_feature_carries_the_translation_table(self, design):
        record = SeqIO.read(StringIO(to_genbank(design)), "genbank")
        cds = next(
            feature
            for feature in record.features
            if feature.qualifiers.get("construct_role") == ["cds"]
        )
        assert cds.qualifiers["transl_table"] == ["1"]
        assert cds.qualifiers["codon_start"] == ["1"]

    def test_provenance_is_in_the_record_comment(self, design):
        text = to_genbank(design)
        for entry in design.provenance:
            assert entry in text

    def test_a_user_supplied_element_records_its_source(self, design):
        record = SeqIO.read(StringIO(to_genbank(design)), "genbank")
        cds = next(
            feature
            for feature in record.features
            if feature.qualifiers.get("construct_role") == ["cds"]
        )
        assert cds.qualifiers["construct_source"] == ["user_input:transgene_sequence"]

    def test_the_export_is_byte_stable(self, design):
        assert to_genbank(design) == to_genbank(design)

    def test_the_kozak_feature_carries_its_class_source_and_citation(self):
        from packages.generation.aav import AAVComposer

        composed = AAVComposer().compose(
            AAVRequest(transgene_name="t", transgene_sequence=cds_of_length(1_200), target_tissue="ubiquitous")
        )
        text = to_genbank(composed)
        record = SeqIO.read(StringIO(text), "genbank")
        kozak = next(
            feature
            for feature in record.features
            if feature.qualifiers.get("construct_role") == ["kozak"]
        )
        assert kozak.type == "regulatory"
        assert kozak.qualifiers["regulatory_class"] == ["ribosome_binding_site"]
        assert kozak.qualifiers["construct_source"] == ["published_rule:kozak_1987"]
        assert kozak.qualifiers["construct_part_id"] == ["none"]
        assert len(kozak.qualifiers["note"]) == 2
        assert "doi:10.1093/nar/15.20.8125" in kozak.qualifiers["note"][1]
        assert str(kozak.extract(record.seq)) == "GCCACC"
        # Only the Kozak feature gets a second note.
        for feature in record.features:
            if feature.qualifiers.get("construct_role") not in (None, ["kozak"]):
                assert len(feature.qualifiers["note"]) == 1


class TestLengthBudgetSourceColumn:
    def test_a_row_without_a_part_shows_its_source_not_user_supplied(self):
        from packages.generation.aav import AAVComposer

        composed = AAVComposer().compose(
            AAVRequest(transgene_name="t", transgene_sequence=cds_of_length(1_200), target_tissue="ubiquitous")
        )
        budget = length_budget(composed)
        text = budget.to_text()
        assert "published_rule:kozak_1987" in text
        assert "user_input:transgene_sequence" in text
        assert "user supplied" not in text
        header, *_ = text.splitlines()
        assert f"{'part':<30} " in header
        kozak = next(row for row in budget.rows if row.role is CassetteElementRole.KOZAK)
        assert kozak.source == "published_rule:kozak_1987" and kozak.part_id is None
        assert kozak.length_bp == 6


class TestFastaExport:
    def test_the_sequence_round_trips(self, design):
        record = SeqIO.read(StringIO(to_fasta(design)), "fasta")
        assert str(record.seq).upper() == design.cassette_sequence

    def test_the_header_names_the_element_layout_and_says_linear(self, design):
        header = to_fasta(design).splitlines()[0]
        assert design.design_id in header
        assert "linear" in header
        assert f"{design.total_bp} bp" in header
        assert "itr_5:1-145" in header

    def test_the_export_is_byte_stable(self, design):
        assert to_fasta(design) == to_fasta(design)


class TestDesignResultArtifacts:
    def test_all_four_artifacts_are_present_and_non_empty(self):
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="artifact test",
                transgene_sequence=cds_of_length(1_200),
                target_tissue="ubiquitous",
            )
        )
        artifacts = bundle.result.artifacts
        assert set(artifacts) == {
            ARTIFACT_GENBANK,
            ARTIFACT_FASTA,
            ARTIFACT_LENGTH_BUDGET,
            ARTIFACT_LINEAR_MAP,
        }
        for key, payload in artifacts.items():
            assert payload.strip(), key

    def test_the_validation_report_travels_with_the_artifacts(self):
        bundle = AAVDesigner().design(
            AAVRequest(
                transgene_name="artifact test",
                transgene_sequence=cds_of_length(1_200),
                target_tissue="ubiquitous",
            )
        )
        assert bundle.result.report is bundle.report
        assert len(bundle.result.report.checks) == 14
