"""ITR reference resolution, identity matching and orientation determination.

The flip and flop finding from WP-02 is the reason this module exists, so it is
pinned here as a test: if the registry records ever change in a way that breaks
the D element anchor, these fail loudly rather than the capability quietly
mis-calling orientation.
"""

from __future__ import annotations

import pytest

from packages.core.part_registry import get_part
from packages.core.sequence import global_identity, reverse_complement
from packages.validation.aav import AAVThresholds
from packages.validation.aav.itr import (
    UnknownSerotype,
    best_itr_match,
    internal_itr_motif_hits,
    itr_motifs,
    locate_d_element,
    orientation_of_pair,
    registered_serotypes,
    serotype_itr_references,
)

LEFT = get_part("itr.aav2_itr_left").sequence
RIGHT = get_part("itr.aav2_itr_right").sequence
CORE = LEFT[:125]
D_ELEMENT = LEFT[125:]


class TestReferenceResolution:
    def test_aav2_resolves(self):
        reference = serotype_itr_references("AAV2")
        assert reference.left.id == "itr.aav2_itr_left"
        assert reference.right.id == "itr.aav2_itr_right"

    def test_serotype_label_is_case_and_punctuation_insensitive(self):
        for label in ("AAV2", "aav2", "AAV-2", "aav_2"):
            assert serotype_itr_references(label).left.id == "itr.aav2_itr_left"

    def test_the_d_element_anchor_is_derived_and_self_checked(self):
        reference = serotype_itr_references("AAV2")
        assert reference.d_element == D_ELEMENT
        assert reverse_complement(reference.d_element) == RIGHT[:20]

    def test_an_unregistered_serotype_raises_with_the_registered_ones(self):
        with pytest.raises(UnknownSerotype) as info:
            serotype_itr_references("AAV9")
        assert "AAV9" in str(info.value)
        assert "aav2" in str(info.value)
        assert "data/parts/itr/" in str(info.value)

    def test_only_aav2_is_registered(self):
        """Section 17 Q5: AAV2 only, it is the standard for recombinant vector ITRs."""
        assert registered_serotypes() == ["aav2"]


class TestTheFlipFlopFinding:
    """The measured facts the implementation depends on."""

    def test_both_itrs_are_145_bp(self):
        assert len(LEFT) == len(RIGHT) == 145

    def test_the_right_itr_decomposes_exactly(self):
        assert RIGHT == reverse_complement(D_ELEMENT) + CORE

    def test_the_hairpin_core_is_nearly_but_not_exactly_self_reverse_complementary(self):
        assert reverse_complement(CORE) != CORE
        assert global_identity(CORE, reverse_complement(CORE)) == pytest.approx(0.859, abs=1e-3)

    def test_the_naive_comparison_scores_128_of_145(self):
        assert sum(1 for a, b in zip(LEFT, reverse_complement(RIGHT)) if a != b) == 17
        assert global_identity(LEFT, reverse_complement(RIGHT)) == pytest.approx(0.8784, abs=5e-4)

    def test_the_naive_comparison_is_below_the_identity_threshold(self):
        """Which is exactly why check 2 does not use it."""
        assert global_identity(LEFT, reverse_complement(RIGHT)) < AAVThresholds().itr_identity_threshold

    def test_the_separation_the_fallback_method_relies_on(self):
        inverted = global_identity(LEFT, reverse_complement(RIGHT))
        tandem = global_identity(LEFT, RIGHT)
        assert tandem == pytest.approx(0.7576, abs=5e-4)
        assert inverted - tandem == pytest.approx(0.121, abs=2e-3)
        assert inverted - tandem > AAVThresholds().itr_orientation_margin

    def test_the_identical_itr_layout_separates_far_more_widely(self):
        inverted = global_identity(LEFT, reverse_complement(reverse_complement(LEFT)))
        tandem = global_identity(LEFT, reverse_complement(LEFT))
        assert inverted == 1.0
        assert tandem == pytest.approx(0.6548, abs=5e-4)


class TestBestItrMatch:
    def test_each_registry_itr_matches_its_own_record_exactly(self):
        reference = serotype_itr_references("AAV2")
        left_match = best_itr_match(LEFT, reference)
        right_match = best_itr_match(RIGHT, reference)
        assert (left_match.reference_id, left_match.orientation, left_match.identity) == (
            "itr.aav2_itr_left",
            1,
            1.0,
        )
        assert (right_match.reference_id, right_match.orientation, right_match.identity) == (
            "itr.aav2_itr_right",
            1,
            1.0,
        )

    def test_a_reverse_complemented_itr_still_matches_at_full_identity(self):
        reference = serotype_itr_references("AAV2")
        match = best_itr_match(reverse_complement(LEFT), reference)
        assert match.identity == 1.0
        assert match.orientation == -1
        assert match.orientation_label == "reverse complemented"

    def test_a_non_itr_sequence_scores_low(self):
        reference = serotype_itr_references("AAV2")
        match = best_itr_match(get_part("promoter.efs").sequence[:145], reference)
        assert match.identity < AAVThresholds().itr_identity_threshold

    def test_matching_is_deterministic(self):
        reference = serotype_itr_references("AAV2")
        assert best_itr_match(LEFT, reference) == best_itr_match(LEFT, reference)


class TestLocateDElement:
    def test_the_left_itr_carries_d_at_its_three_prime_end(self):
        reference = serotype_itr_references("AAV2")
        end, identity = locate_d_element(LEFT, reference)
        assert end == "3_prime"
        assert identity == 1.0

    def test_the_right_itr_carries_d_at_its_five_prime_end(self):
        reference = serotype_itr_references("AAV2")
        end, identity = locate_d_element(RIGHT, reference)
        assert end == "5_prime"
        assert identity == 1.0

    def test_a_truncated_itr_has_no_locatable_d_element(self):
        reference = serotype_itr_references("AAV2")
        end, _identity = locate_d_element(CORE, reference)
        assert end is None


class TestOrientation:
    def reference(self):
        return serotype_itr_references("AAV2")

    def test_the_registry_pair_is_inverted_by_the_d_element_method(self):
        verdict = orientation_of_pair(LEFT, RIGHT, self.reference())
        assert verdict.arrangement == "inverted"
        assert verdict.method == "d_element"
        assert verdict.canonical

    def test_a_direct_copy_is_tandem(self):
        verdict = orientation_of_pair(LEFT, LEFT, self.reference())
        assert verdict.arrangement == "tandem"
        assert verdict.method == "d_element"

    def test_both_itrs_flipped_in_place_is_inverted_but_not_canonical(self):
        """D outward. Still inverted, so the arrangement is not tandem, but flagged.

        `canonical` is what `aav.itr_orientation` turns into a WARN, so this is
        the layer that has to keep telling the two inverted arrangements apart.
        """
        verdict = orientation_of_pair(
            reverse_complement(LEFT), reverse_complement(RIGHT), self.reference()
        )
        assert verdict.arrangement == "inverted"
        assert verdict.method == "d_element"
        assert not verdict.canonical
        assert "face the cassette ends rather than the transgene" in verdict.detail

    def test_the_commoner_identical_itr_layout_is_inverted(self):
        """Both ITRs the same sequence, one reverse complemented: the usual plasmid layout."""
        verdict = orientation_of_pair(LEFT, reverse_complement(LEFT), self.reference())
        assert verdict.arrangement == "inverted"
        assert verdict.method == "d_element"

    def test_truncated_itrs_fall_back_to_the_identity_margin(self):
        verdict = orientation_of_pair(CORE, reverse_complement(CORE), self.reference())
        assert verdict.method == "identity_margin"
        assert verdict.arrangement == "inverted"
        assert verdict.inverted_identity == 1.0

    def test_a_palindromic_second_itr_is_undetermined_rather_than_guessed(self):
        palindrome = CORE[:60] + reverse_complement(CORE[:60])
        verdict = orientation_of_pair(LEFT, palindrome, self.reference())
        assert verdict.arrangement == "undetermined"
        assert verdict.method == "identity_margin"
        assert verdict.inverted_identity == verdict.tandem_identity

    def test_the_margin_is_configurable_and_widening_it_forces_undetermined(self):
        wide = AAVThresholds(itr_orientation_margin=0.99)
        verdict = orientation_of_pair(CORE, CORE, self.reference(), wide)
        assert verdict.arrangement == "undetermined"
        assert "below the 99% margin" in verdict.detail

    def test_orientation_is_deterministic(self):
        first = orientation_of_pair(LEFT, RIGHT, self.reference())
        second = orientation_of_pair(LEFT, RIGHT, self.reference())
        assert first == second


class TestItrMotifs:
    def test_motifs_come_from_the_reference_records(self):
        motifs = itr_motifs(serotype_itr_references("AAV2"), 20)
        assert LEFT[:20] in motifs
        assert RIGHT[:20] in motifs
        assert all(len(motif) == 20 for motif in motifs)

    def test_motifs_are_sorted_and_distinct(self):
        motifs = itr_motifs(serotype_itr_references("AAV2"), 20)
        assert motifs == sorted(set(motifs))

    def test_a_zero_width_window_is_rejected(self):
        with pytest.raises(ValueError, match="width must be positive"):
            itr_motifs(serotype_itr_references("AAV2"), 0)

    def test_an_interior_with_no_itr_sequence_has_no_hits(self):
        interior = get_part("promoter.efs").sequence + get_part("polya.sv40").sequence
        assert internal_itr_motif_hits(interior, serotype_itr_references("AAV2"), 20) == []

    def test_a_plus_strand_hit_is_found_and_located(self):
        interior = "A" * 50 + LEFT[30:70] + "C" * 50
        hits = internal_itr_motif_hits(interior, serotype_itr_references("AAV2"), 20)
        assert hits
        motif, offset, strand = hits[0]
        assert strand == 1
        assert interior[offset : offset + 20] == motif

    def test_a_minus_strand_hit_is_found(self):
        interior = "A" * 50 + reverse_complement(LEFT[30:70]) + "C" * 50
        hits = internal_itr_motif_hits(interior, serotype_itr_references("AAV2"), 20)
        assert hits
        assert all(strand == -1 for _motif, _offset, strand in hits)

    def test_an_interior_shorter_than_the_window_has_no_hits(self):
        assert internal_itr_motif_hits("ACGT", serotype_itr_references("AAV2"), 20) == []
