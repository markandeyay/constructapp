"""Appendix C geometry: PAM side, spacer length, both strands, cut sites.

Appendix C: "The Cas12a 5' PAM position is the single most likely integration
bug in Capability C." The tests here are written so that a 3' offset applied to
Cas12a fails them, and so that dropping reverse-strand enumeration fails them.
Each one builds its expectation independently of the implementation rather than
by calling the same helper the code under test calls.
"""

from __future__ import annotations

import pytest

from packages.core.sequence import reverse_complement
from packages.validation.grna import enumerate_guides, get_nuclease, seed_positions
from packages.validation.grna.nuclease import (
    ASCAS12A,
    LBCAS12A,
    SACAS9,
    SPCAS9,
    pam_interval,
    spacer_interval,
)


class TestAppendixCTable:
    """The four rows of the Appendix C table, verbatim."""

    @pytest.mark.parametrize(
        ("name", "pam_motif", "pam_side", "spacer_length"),
        [
            ("SpCas9", "NGG", "three_prime", 20),
            ("SaCas9", "NNGRRT", "three_prime", 21),
            ("LbCas12a", "TTTV", "five_prime", 23),
            ("AsCas12a", "TTTV", "five_prime", 23),
        ],
    )
    def test_row(self, name: str, pam_motif: str, pam_side: str, spacer_length: int) -> None:
        spec = get_nuclease(name)
        assert spec.pam_motif == pam_motif
        assert spec.pam_side == pam_side
        assert spec.spacer_length == spacer_length

    def test_spcas9_alternative_pam_is_nag_only(self) -> None:
        assert [item.motif for item in SPCAS9.alternative_pams] == ["NAG"]

    def test_other_nucleases_declare_no_alternative_pam(self) -> None:
        for spec in (SACAS9, LBCAS12A, ASCAS12A):
            assert spec.alternative_pams == ()


class TestCas12aFivePrimePam:
    """The Cas12a 5' PAM, proved against an independently computed expectation.

    The target below is built so the correct answer is known by construction:
    a TTTA PAM, then exactly 23 nucleotides of spacer, with distinct flanks on
    either side. Under a 3' offset the extracted spacer would be the 23
    nucleotides BEFORE the PAM, which is a different string, so each assertion
    here fails if the offset is wrong.
    """

    PAM = "TTTA"
    SPACER = "GCACGTCAGTCAGGATCCAGTCC"  # 23 nt, contains no TTT
    LEFT_FLANK = "CCAGGCACCAGGCACCAGGCAC"  # no TTT, no TTTV PAM
    RIGHT_FLANK = "GCCAGGCACCAGGCACCAGGCA"

    def target(self) -> str:
        assert len(self.SPACER) == 23
        return self.LEFT_FLANK + self.PAM + self.SPACER + self.RIGHT_FLANK

    @pytest.mark.parametrize("nuclease", ["LbCas12a", "AsCas12a"])
    def test_spacer_is_taken_from_the_three_prime_side_of_the_pam(self, nuclease: str) -> None:
        target = self.target()
        pam_start = len(self.LEFT_FLANK)
        expected_spacer_start = pam_start + len(self.PAM)

        guides = [
            guide
            for guide in enumerate_guides(target, nuclease)
            if guide.placement.strand == 1 and guide.pam == self.PAM
        ]
        assert len(guides) == 1, "exactly one forward TTTV PAM was planted"
        guide = guides[0]

        assert guide.spacer == self.SPACER
        assert guide.placement.spacer_start == expected_spacer_start
        assert guide.placement.spacer_end == expected_spacer_start + 23
        assert guide.placement.pam_start == pam_start
        assert guide.placement.pam_end == pam_start + 4
        assert guide.placement.pam_side == "five_prime"
        # The decisive assertion: the spacer must NOT be the 23 nt before the PAM.
        wrong_spacer = target[pam_start - 23 : pam_start]
        assert guide.spacer != wrong_spacer
        assert guide.placement.spacer_start != pam_start - 23

    @pytest.mark.parametrize("nuclease", ["LbCas12a", "AsCas12a"])
    def test_pam_interval_is_before_the_spacer(self, nuclease: str) -> None:
        spec = get_nuclease(nuclease)
        start, end = pam_interval(spec, 100, 123)
        assert (start, end) == (96, 100), "a 5' PAM sits immediately before the spacer"
        spacer_start, spacer_end = spacer_interval(spec, 96, 100)
        assert (spacer_start, spacer_end) == (100, 123)

    def test_spcas9_pam_interval_is_after_the_spacer(self) -> None:
        start, end = pam_interval(SPCAS9, 100, 120)
        assert (start, end) == (120, 123), "a 3' PAM sits immediately after the spacer"
        assert spacer_interval(SPCAS9, 120, 123) == (100, 120)

    def test_the_two_pam_sides_disagree_so_the_distinction_is_load_bearing(self) -> None:
        """If both nucleases produced the same interval the test above would be empty."""
        assert pam_interval(SPCAS9, 100, 120) != pam_interval(LBCAS12A, 100, 123)

    @pytest.mark.parametrize("nuclease", ["LbCas12a", "AsCas12a"])
    def test_reverse_strand_cas12a_spacer_is_also_three_prime_of_its_pam(
        self, nuclease: str
    ) -> None:
        """The same geometry on the reverse strand, checked on forward coordinates.

        The reverse-complement target carries the same planted site, so the
        guide must come back with the identical spacer and with forward
        coordinates mirrored.
        """
        forward = self.target()
        reverse = reverse_complement(forward)
        guides = [
            guide
            for guide in enumerate_guides(reverse, nuclease)
            if guide.placement.strand == -1 and guide.spacer == self.SPACER
        ]
        assert len(guides) == 1
        guide = guides[0]
        length = len(forward)
        pam_start_forward = len(self.LEFT_FLANK)
        spacer_start_forward = pam_start_forward + len(self.PAM)
        # On the reverse-complemented sequence, the forward interval of the
        # spacer is the mirror image of its interval on the original.
        assert guide.placement.spacer_start == length - (spacer_start_forward + 23)
        assert guide.placement.spacer_end == length - spacer_start_forward
        # And the PAM sits at HIGHER forward coordinates than the spacer, because
        # 5' on the reverse strand is the high-coordinate end of the forward one.
        assert guide.placement.pam_start == guide.placement.spacer_end
        assert guide.placement.pam_end == guide.placement.spacer_end + 4

    @pytest.mark.parametrize("nuclease", ["LbCas12a", "AsCas12a"])
    def test_staggered_cut_sites_come_from_the_spacer_five_prime_end(
        self, nuclease: str
    ) -> None:
        """Cell 2015;163(3):759-771: cleavage after spacer position 18 and 23."""
        guides = [
            guide
            for guide in enumerate_guides(self.target(), nuclease)
            if guide.placement.strand == 1 and guide.pam == self.PAM
        ]
        guide = guides[0]
        assert guide.placement.cut_site == guide.placement.spacer_start + 18
        assert guide.placement.cut_site_staggered == guide.placement.spacer_start + 23
        assert guide.placement.cut_site_staggered - guide.placement.cut_site == 5


class TestSpCas9CutSite:
    """A blunt cut 3 nt 5' of the PAM, on both strands."""

    def test_forward_strand(self) -> None:
        target = "CCAGGCACCAGG" + "ACGTCAGTCAGGATCCAGTCC" + "AGGCACCAGGCACCAGGCACC"
        guides = [
            guide
            for guide in enumerate_guides(target, "SpCas9")
            if guide.placement.strand == 1 and not guide.pam_is_alternative
        ]
        assert guides
        for guide in guides:
            assert guide.placement.cut_site == guide.placement.pam_start - 3
            assert guide.placement.cut_site_staggered is None

    def test_reverse_strand_cut_is_three_nucleotides_from_the_pam(self) -> None:
        target = "CCAGGCACCAGG" + "ACGTCAGTCAGGATCCAGTCC" + "AGGCACCAGGCACCAGGCACC"
        guides = [
            guide
            for guide in enumerate_guides(target, "SpCas9")
            if guide.placement.strand == -1 and not guide.pam_is_alternative
        ]
        assert guides
        for guide in guides:
            # On the reverse strand the PAM is at lower forward coordinates, so
            # the cut is 3 nt above the PAM end rather than below the PAM start.
            assert guide.placement.cut_site == guide.placement.pam_end + 3


class TestBothStrandsAreEnumerated:
    """Section 8.3: "Scan both strands."

    The proof is a target with a PAM that exists on one strand only, so a
    forward-only implementation returns nothing for it.
    """

    def test_a_reverse_only_site_is_found(self) -> None:
        # CCT on the forward strand is AGG on the reverse strand, so this target
        # has a reverse-strand NGG PAM and no forward-strand NGG or NAG PAM.
        target = "CCT" + "ACATCATCATCATCATCATC"
        assert "GG" not in target and "AG" not in target
        guides = enumerate_guides(target, "SpCas9")
        assert len(guides) == 1
        guide = guides[0]
        assert guide.placement.strand == -1
        assert guide.pam == "AGG"
        assert guide.spacer == reverse_complement(target[3:23])

    def test_a_forward_only_site_is_found(self) -> None:
        target = "ACATCATCATCATCATCATC" + "AGG"
        guides = enumerate_guides(target, "SpCas9")
        assert len(guides) == 1
        assert guides[0].placement.strand == 1
        assert guides[0].pam == "AGG"

    @pytest.mark.parametrize("nuclease", ["SpCas9", "SaCas9", "LbCas12a", "AsCas12a"])
    def test_every_nuclease_returns_guides_on_both_strands(self, nuclease: str) -> None:
        target = (
            "TTTAGCACGTCAGTCAGGATCCAGTCCATGGACGTTTCGGTACCAGGTTACGAACCGGTTAAGG"
            "CCTTAAGGCCGGTTAACCGGTAAACGTACGTAGCTGACTGACGATCGGATCCTTAGGCATCAGC"
            "TAGCTAGGACTGACTGGCATCAGCATCAGGTACGTACGTAAGGCCTTAAGGACGTCTGACTGAC"
        )
        guides = enumerate_guides(target, nuclease)
        strands = {guide.placement.strand for guide in guides}
        assert strands == {1, -1}, f"{nuclease} must enumerate both strands"

    def test_enumeration_of_the_reverse_complement_mirrors_the_forward_run(self) -> None:
        """Scanning a sequence and its reverse complement must find the same guides.

        Every spacer found on one must appear on the other, which cannot hold if
        only one strand is scanned.
        """
        target = (
            "TTTAGCACGTCAGTCAGGATCCAGTCCATGGACGTTTCGGTACCAGGTTACGAACCGGTTAAGG"
            "CCTTAAGGCCGGTTAACCGGTAAACGTACGTAGCTGACTGACGATCGGATCCTTAGGCATCAGC"
        )
        for nuclease in ("SpCas9", "SaCas9", "LbCas12a", "AsCas12a"):
            forward = {g.spacer for g in enumerate_guides(target, nuclease)}
            mirrored = {
                g.spacer for g in enumerate_guides(reverse_complement(target), nuclease)
            }
            assert forward == mirrored, nuclease


class TestSeedRegionFollowsThePamSide:
    """Appendix C: the seed is the PAM-proximal 8 to 12 nt, whichever end that is."""

    def test_cas9_seed_is_the_three_prime_end_of_the_spacer(self) -> None:
        positions = seed_positions(SPCAS9, 20, 12)
        assert positions == frozenset(range(9, 21))

    def test_cas12a_seed_is_the_five_prime_end_of_the_spacer(self) -> None:
        positions = seed_positions(LBCAS12A, 23, 12)
        assert positions == frozenset(range(1, 13))

    def test_the_two_seeds_are_different_sets(self) -> None:
        assert seed_positions(SPCAS9, 20, 12) != seed_positions(LBCAS12A, 20, 12)
