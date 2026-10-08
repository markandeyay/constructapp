"""Section 6.7 composition, step by step.

Section 4.2's point is that nothing is invented: every base in a composed
cassette comes from a registry part or from the user's own transgene. These
tests assert that, and they assert the selection rules the composer documents.
"""

from __future__ import annotations

import pytest

from packages.core.part_registry import get_part
from packages.core.schemas.aav import AAVRequest, CassetteElementRole
from packages.generation.aav import AAVComposer, TransgeneUnavailable

from tests.aav.support import cds_of_length


def request_for(**kwargs) -> AAVRequest:
    payload = {
        "transgene_name": "test transgene",
        "transgene_sequence": cds_of_length(1_200),
        "target_tissue": "ubiquitous",
    }
    payload.update(kwargs)
    return AAVRequest.model_validate(payload)


def roles(design) -> list[str]:
    return [CassetteElementRole(element.role).value for element in design.elements]


class TestStepOneTransgene:
    def test_a_supplied_sequence_is_used_verbatim(self):
        sequence = cds_of_length(1_200)
        design = AAVComposer().compose(request_for(transgene_sequence=sequence))
        cds = design.first_with_role(CassetteElementRole.CDS)
        assert cds is not None
        assert cds.sequence == sequence
        assert cds.source == "user_input:transgene_sequence"

    def test_no_sequence_and_no_resolver_refuses_rather_than_inventing_one(self):
        with pytest.raises(TransgeneUnavailable) as info:
            AAVComposer().compose(request_for(transgene_sequence=None))
        assert "no transgene resolver is configured" in str(info.value)
        assert "A placeholder sequence is not an option" in str(info.value)

    def test_a_configured_resolver_is_used_and_its_provenance_recorded(self):
        sequence = cds_of_length(900)
        composer = AAVComposer(transgene_resolver=lambda name: (sequence, f"test_corpus:{name}"))
        design = composer.compose(request_for(transgene_sequence=None, transgene_name="EGFP"))
        assert design.first_with_role(CassetteElementRole.CDS).sequence == sequence
        assert "test_corpus:EGFP" in design.provenance

    def test_lower_case_and_whitespace_in_the_request_are_normalised(self):
        sequence = cds_of_length(900)
        spaced = " ".join(sequence[index : index + 10] for index in range(0, len(sequence), 10)).lower()
        design = AAVComposer().compose(request_for(transgene_sequence=spaced))
        assert design.first_with_role(CassetteElementRole.CDS).sequence == sequence


class TestStepTwoPromoter:
    def test_the_most_compact_compatible_promoter_is_chosen(self):
        design = AAVComposer().compose(request_for(target_tissue="ubiquitous"))
        assert design.first_with_role(CassetteElementRole.PROMOTER).part_id == "promoter.efs"

    def test_an_exact_tissue_match_outranks_a_ubiquitous_part(self):
        design = AAVComposer().compose(request_for(target_tissue="cns_astrocyte"))
        promoter = design.first_with_role(CassetteElementRole.PROMOTER)
        assert promoter.part_id == "promoter.gfap"
        assert get_part(promoter.part_id).tissue_specificity == "cns_astrocyte"

    def test_the_shorter_of_two_exact_matches_wins(self):
        """cns_neuron has two annotated promoters: mecp2_mini at 225 bp and hsyn1 at 472 bp."""
        design = AAVComposer().compose(request_for(target_tissue="cns_neuron"))
        assert design.first_with_role(CassetteElementRole.PROMOTER).part_id == "promoter.mecp2_mini"

    def test_a_tissue_with_no_specific_promoter_falls_back_to_ubiquitous(self):
        for tissue in ("liver", "muscle", "cardiac", "retina"):
            design = AAVComposer().compose(request_for(target_tissue=tissue))
            promoter = design.first_with_role(CassetteElementRole.PROMOTER)
            assert get_part(promoter.part_id).tissue_specificity == "ubiquitous", tissue

    def test_the_longer_alternatives_are_recorded_in_the_notes(self):
        design = AAVComposer().compose(request_for(target_tissue="ubiquitous"))
        note = " ".join(design.notes)
        assert "auto-selected as the most compact part compatible with ubiquitous" in note
        assert "promoter.cag (1,639 bp)" in note
        assert "Set promoter_preference to choose one" in note

    def test_an_explicit_preference_is_honoured(self):
        design = AAVComposer().compose(request_for(promoter_preference="promoter.cag"))
        assert design.first_with_role(CassetteElementRole.PROMOTER).part_id == "promoter.cag"
        assert design.promoter_preference == "promoter.cag"

    def test_an_incompatible_preference_is_kept_and_explained(self):
        design = AAVComposer().compose(
            request_for(target_tissue="liver", promoter_preference="promoter.hsyn1")
        )
        assert design.first_with_role(CassetteElementRole.PROMOTER).part_id == "promoter.hsyn1"
        note = " ".join(design.notes)
        assert "kept rather than silently substituted" in note
        assert "aav.promoter_tissue_match reports it" in note

    def test_an_unknown_preference_raises_and_lists_the_registry(self):
        with pytest.raises(KeyError) as info:
            AAVComposer().compose(request_for(promoter_preference="promoter.nonexistent"))
        assert "promoter.efs" in str(info.value)

    def test_a_preference_from_the_wrong_category_raises(self):
        with pytest.raises(KeyError, match="is a polya part"):
            AAVComposer().compose(request_for(promoter_preference="polya.bgh"))


class TestStepThreePolya:
    def test_the_most_compact_functional_signal_is_chosen(self):
        design = AAVComposer().compose(request_for())
        assert design.first_with_role(CassetteElementRole.POLYA).part_id == "polya.sv40"

    def test_an_explicit_preference_is_honoured(self):
        design = AAVComposer().compose(request_for(polya_preference="polya.bgh"))
        assert design.first_with_role(CassetteElementRole.POLYA).part_id == "polya.bgh"

    def test_the_alternative_is_recorded(self):
        design = AAVComposer().compose(request_for())
        assert "polya.bgh (225 bp)" in " ".join(design.notes)


class TestStepFourWpre:
    def test_wpre_is_included_when_requested_and_it_fits(self):
        design = AAVComposer().compose(request_for(include_wpre=True))
        assert design.first_with_role(CassetteElementRole.WPRE).part_id == "enhancer.wpre"

    def test_wpre_is_omitted_when_not_requested(self):
        design = AAVComposer().compose(request_for(include_wpre=False))
        assert design.first_with_role(CassetteElementRole.WPRE) is None
        assert not any("WPRE" in note for note in design.notes)

    def test_wpre_is_omitted_when_it_does_not_fit_and_the_design_says_why(self):
        design = AAVComposer().compose(
            request_for(
                transgene_sequence=cds_of_length(4_200),
                promoter_preference="promoter.efs",
                polya_preference="polya.sv40",
                include_wpre=True,
            )
        )
        assert design.first_with_role(CassetteElementRole.WPRE) is None
        note = " ".join(design.notes)
        assert "include_wpre was requested but WPRE (enhancer.wpre, 589 bp) was omitted" in note
        assert "against the 4,700 bp target" in note

    def test_a_dropped_wpre_is_not_claimed_in_provenance(self):
        design = AAVComposer().compose(
            request_for(
                transgene_sequence=cds_of_length(4_200),
                promoter_preference="promoter.efs",
                include_wpre=True,
            )
        )
        assert "part:enhancer.wpre" not in design.provenance

    def test_the_self_complementary_band_is_what_wpre_is_tested_against(self):
        design = AAVComposer().compose(
            request_for(transgene_sequence=cds_of_length(1_200), self_complementary=True)
        )
        assert design.first_with_role(CassetteElementRole.WPRE) is None
        assert "2,400 bp target" in " ".join(design.notes)


class TestStepFiveItrs:
    def test_the_serotype_pair_is_loaded_at_both_ends(self):
        design = AAVComposer().compose(request_for())
        assert design.elements[0].part_id == "itr.aav2_itr_left"
        assert design.elements[-1].part_id == "itr.aav2_itr_right"

    def test_an_unregistered_serotype_refuses_with_a_usable_message(self):
        with pytest.raises(LookupError) as info:
            AAVComposer().compose(request_for(serotype="AAV9"))
        assert "no ITR reference pair is registered for serotype 'AAV9'" in str(info.value)


class TestStepsSixAndSevenAssemblyAndProvenance:
    def test_elements_are_in_the_section_six_two_functional_order(self):
        design = AAVComposer().compose(request_for(include_wpre=True))
        assert roles(design) == ["itr_5", "promoter", "cds", "wpre", "polya", "itr_3"]

    def test_the_cassette_sequence_is_the_elements_laid_end_to_end(self):
        design = AAVComposer().compose(request_for())
        assert design.cassette_sequence == "".join(element.sequence for element in design.elements)
        assert design.total_bp == len(design.cassette_sequence)

    def test_coordinates_are_contiguous_and_cover_the_cassette(self):
        design = AAVComposer().compose(request_for(include_wpre=True))
        layout = design.layout()
        assert layout[0].start == 0
        assert layout[-1].end == design.total_bp
        for previous, current in zip(layout, layout[1:]):
            assert previous.end == current.start

    def test_every_base_is_attributable(self):
        """Section 11.1: a design containing unattributable sequence is not acceptable."""
        design = AAVComposer().compose(request_for(include_wpre=True))
        for element in design.elements:
            assert element.part_id or element.source
            assert "unattributed" not in element.attribution

    def test_provenance_names_every_part_and_the_serotype_record(self):
        design = AAVComposer().compose(request_for(include_wpre=True))
        assert design.provenance == [
            "user_input:transgene_sequence",
            "part:itr.aav2_itr_left",
            "part:promoter.efs",
            "part:enhancer.wpre",
            "part:polya.sv40",
            "part:itr.aav2_itr_right",
            "serotype_reference:NC_001401.2",
        ]

    def test_the_request_settings_the_validator_needs_are_carried_over(self):
        design = AAVComposer().compose(
            request_for(
                target_tissue="cns_neuron",
                self_complementary=True,
                promoter_preference="promoter.hsyn1",
                polya_preference="polya.bgh",
                packaging_limit_bp=3_000,
                serotype="AAV2",
            )
        )
        assert design.target_tissue == "cns_neuron"
        assert design.self_complementary is True
        assert design.promoter_preference == "promoter.hsyn1"
        assert design.polya_preference == "polya.bgh"
        assert design.packaging_limit_bp == 3_000
        assert design.serotype == "AAV2"


class TestDeterminism:
    def test_the_same_request_gives_the_same_cassette_and_the_same_id(self):
        first = AAVComposer().compose(request_for())
        second = AAVComposer().compose(request_for())
        assert first.design_id == second.design_id
        assert first.cassette_sequence == second.cassette_sequence
        assert first.notes == second.notes

    def test_a_different_cassette_gets_a_different_id(self):
        first = AAVComposer().compose(request_for())
        second = AAVComposer().compose(request_for(promoter_preference="promoter.cag"))
        assert first.design_id != second.design_id

    def test_the_id_is_derived_from_the_cassette(self):
        import hashlib

        design = AAVComposer().compose(request_for())
        digest = hashlib.sha256(design.cassette_sequence.encode("ascii")).hexdigest()
        assert design.design_id == f"aav-{digest[:12]}"


class TestNoInventedSequence:
    def test_every_registry_element_is_byte_identical_to_its_part_record(self):
        design = AAVComposer().compose(request_for(include_wpre=True))
        for element in design.elements:
            if element.part_id:
                assert element.sequence == get_part(element.part_id).sequence, element.part_id

    def test_the_cassette_contains_no_base_outside_its_sources(self):
        sequence = cds_of_length(1_200)
        design = AAVComposer().compose(request_for(transgene_sequence=sequence, include_wpre=True))
        accounted = sum(
            len(get_part(element.part_id).sequence) if element.part_id else len(sequence)
            for element in design.elements
        )
        assert accounted == design.total_bp
