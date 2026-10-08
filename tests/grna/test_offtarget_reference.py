"""The off-target model, the seed principle, the searched space and its statement.

The expected scores below were produced on 2026-10-07 by running the reference
implementation, `crispor.py` functions `calcHitScore` and `calcMitGuideScore`
with the weight vector `hitScoreM`, fetched from
https://raw.githubusercontent.com/maximilianh/crisporWebsite/master/crispor.py
The model is Nat Biotechnol 2013;31(9):827-832, doi:10.1038/nbt.2647,
PMID 23873081, and the tool is Genome Biol 2016;17(1):148,
doi:10.1186/s13059-016-1012-2, PMID 27380939.

The class `TestSeedRegionDominates` is the one section 8.6 cares about most: it
asserts that a PAM-proximal mismatch costs far more score than a PAM-distal
one, so an implementation that weighted positions equally fails.
"""

from __future__ import annotations

import pytest

from packages.core.schemas.grna import OffTargetSpace
from packages.validation.grna import (
    MIT_MODEL_NAME,
    mit_guide_specificity,
    mit_hit_score,
    search_off_targets,
)
from packages.validation.grna.offtarget import (
    MIT_POSITION_WEIGHTS,
    collect_sources,
    format_size,
    parse_fasta,
    space_statement,
)

from .conftest import TARGET, make_request

REFERENCE_HITS = [
    ("GTAAAACGACGGCCAGTGAA", "GTAAAACGACGGCCAGTGAA", 100.0),
    ("GTAAAACGACGGCCAGTGAA", "ATAAAACGACGGCCAGTGAA", 100.0),
    ("GTAAAACGACGGCCAGTGAA", "GTAAAACGACGGCCAGTGAT", 41.7),
    ("GTAAAACGACGGCCAGTGAA", "ATAAAACGACGGCCAGTGAT", 10.425),
    ("GTAAAACGACGGCCAGTGAA", "GTAAAACGACGGCCAGTTTT", 0.05972723076923077),
    ("GTAAAACGACGGCCAGTGAA", "AAAAAACGACGGCCAGTGAA", 5.219780219780221),
    ("GCCTACGATCGATCGGGTTA", "GCCTACGATCGATCGGGTTA", 100.0),
    ("GCCTACGATCGATCGGGTTA", "TCCTACGATCGATCGGGTTA", 100.0),
    ("GCCTACGATCGATCGGGTTA", "GCCTACGATCGATCGGGTTT", 41.7),
]

REFERENCE_SPECIFICITY = [
    ([], 100.0),
    ([41.7], 71.0),
    ([100.0, 10.0], 48.0),
    ([0.059727], 100.0),
]


class TestMitScoreMatchesTheReferenceImplementation:
    @pytest.mark.parametrize(("spacer", "protospacer", "expected"), REFERENCE_HITS)
    def test_hit_score(self, spacer: str, protospacer: str, expected: float) -> None:
        assert mit_hit_score(spacer, protospacer) == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize(("hit_scores", "expected"), REFERENCE_SPECIFICITY)
    def test_guide_specificity(self, hit_scores: list[float], expected: float) -> None:
        assert mit_guide_specificity(hit_scores) == pytest.approx(expected)

    def test_weight_vector_is_the_published_length(self) -> None:
        assert len(MIT_POSITION_WEIGHTS) == 20
        assert all(0.0 <= weight <= 1.0 for weight in MIT_POSITION_WEIGHTS)

    def test_wrong_length_is_refused_rather_than_fudged(self) -> None:
        with pytest.raises(ValueError, match="20 nt protospacers"):
            mit_hit_score("ACGT", "ACGT")


class TestSeedRegionDominates:
    """Section 8.6: "mismatches in the PAM-proximal seed region are far more
    disruptive to binding than distal mismatches. A model that weights all
    positions equally is wrong."
    """

    SPACER = "GTAAAACGACGGCCAGTGAA"

    def _one_mismatch(self, position: int) -> str:
        """Mutate the 1-based position of the spacer to a different base."""
        index = position - 1
        replacement = "A" if self.SPACER[index] != "A" else "C"
        return self.SPACER[:index] + replacement + self.SPACER[index + 1 :]

    def test_a_pam_proximal_mismatch_costs_far_more_than_a_pam_distal_one(self) -> None:
        distal = mit_hit_score(self.SPACER, self._one_mismatch(1))
        proximal = mit_hit_score(self.SPACER, self._one_mismatch(20))
        assert distal == pytest.approx(100.0), "position 1 carries no weight"
        assert proximal < 50.0
        assert proximal < distal / 2

    def test_weights_rise_toward_the_pam(self) -> None:
        """The PAM-proximal half of the vector outweighs the PAM-distal half."""
        distal_half = sum(MIT_POSITION_WEIGHTS[:10])
        proximal_half = sum(MIT_POSITION_WEIGHTS[10:])
        assert proximal_half > 3 * distal_half

    def test_scores_are_monotonic_in_the_right_direction_across_positions(self) -> None:
        """Mismatching a later (more PAM-proximal) position never scores higher."""
        scores = [mit_hit_score(self.SPACER, self._one_mismatch(p)) for p in range(1, 21)]
        assert scores[0] == pytest.approx(100.0)
        assert min(scores[13:]) < max(scores[:5])

    def test_equal_weighting_would_fail_this_file(self) -> None:
        """Guard: if every weight were equal, the asymmetry assertions above are vacuous."""
        assert len(set(MIT_POSITION_WEIGHTS)) > 1


class TestSpaceStatement:
    """Section 8.6: the statement is generated from what was really searched."""

    def test_construct_only_with_a_delivery_construct(self) -> None:
        request = make_request(
            delivery_construct_name="pTEST",
            delivery_construct_sequence="ACGT" * 100,
        )
        sources = collect_sources(request)
        statement = space_statement(
            request.off_target_space, sources, has_delivery_construct=True
        )
        assert statement == (
            "Off-target search covered the delivery construct and the target sequence, "
            "598 bp in total across 2 sequences. This is not a genome-wide search."
        )

    def test_construct_only_without_a_delivery_construct_says_so(self) -> None:
        request = make_request()
        sources = collect_sources(request)
        statement = space_statement(
            request.off_target_space, sources, has_delivery_construct=False
        )
        assert statement == (
            "Off-target search covered the target sequence only, 198 bp in total across "
            "1 sequence. No delivery construct sequence was supplied, so self-targeting of the "
            "delivery construct was not searched. This is not a genome-wide search."
        )

    def test_supplied_fasta(self, tmp_path) -> None:
        fasta = tmp_path / "extra.fa"
        fasta.write_text(">chrA\n" + "ACGT" * 250 + "\n>chrB\n" + "ACGT" * 250 + "\n")
        request = make_request(
            off_target_space=OffTargetSpace(
                scope="supplied_fasta", fasta_path=str(fasta)
            ),
            delivery_construct_name="pTEST",
            delivery_construct_sequence="ACGT" * 100,
        )
        sources = collect_sources(request)
        statement = space_statement(
            request.off_target_space, sources, has_delivery_construct=True
        )
        assert statement == (
            "Off-target search covered the delivery construct, the target sequence and the "
            "supplied 2.0 kb sequence set, 2.6 kb in total across 4 sequences. "
            "This is not a genome-wide search."
        )

    def test_scope_none_says_so_prominently(self) -> None:
        request = make_request(off_target_space=OffTargetSpace(scope="none"))
        statement = space_statement(
            request.off_target_space, [], has_delivery_construct=False
        )
        assert statement == (
            "No off-target search was performed. The off-target risk of this guide is unknown. "
            "This is not a genome-wide search."
        )

    def test_over_the_configured_limit_says_nothing_was_searched(self) -> None:
        request = make_request()
        sources = collect_sources(request)
        statement = space_statement(
            request.off_target_space,
            sources,
            has_delivery_construct=False,
            over_limit_bp=100,
        )
        assert statement.startswith("No off-target search was performed:")
        assert "above the configured limit of 100 bp" in statement
        assert statement.endswith("This is not a genome-wide search.")

    @pytest.mark.parametrize("scope", ["construct_only", "supplied_fasta", "none"])
    def test_every_scope_ends_with_the_not_genome_wide_sentence(self, scope: str, tmp_path) -> None:
        if scope == "supplied_fasta":
            fasta = tmp_path / "x.fa"
            fasta.write_text(">a\nACGTACGT\n")
            space = OffTargetSpace(scope=scope, fasta_path=str(fasta))
        else:
            space = OffTargetSpace(scope=scope)
        request = make_request(off_target_space=space)
        statement = space_statement(
            space, collect_sources(request), has_delivery_construct=False
        )
        assert statement.endswith("This is not a genome-wide search.")

    @pytest.mark.parametrize("banned", ["genome-wide search of", "comprehensive", "exhaustive"])
    def test_banned_words_never_describe_the_search(self, banned: str, tmp_path) -> None:
        """Section 16 bans genome-wide, comprehensive and exhaustive as descriptions."""
        fasta = tmp_path / "x.fa"
        fasta.write_text(">a\nACGTACGT\n")
        for space in (
            OffTargetSpace(scope="construct_only"),
            OffTargetSpace(scope="supplied_fasta", fasta_path=str(fasta)),
            OffTargetSpace(scope="none"),
        ):
            request = make_request(off_target_space=space)
            statement = space_statement(
                space, collect_sources(request), has_delivery_construct=False
            )
            assert banned not in statement.lower()

    def test_a_request_supplied_label_is_never_the_statement(self) -> None:
        """A user cannot inject an overstated label into the shown text."""
        space = OffTargetSpace(
            scope="construct_only", label="Genome-wide search of the human genome"
        )
        request = make_request(off_target_space=space)
        summary = search_off_targets(request, "ACGTACGTACGTACGTACGT", None)
        assert summary.space_statement != space.label
        assert "genome-wide search of" not in summary.space_statement.lower()


class TestFormatSize:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(0, "0 bp"), (999, "999 bp"), (1000, "1.0 kb"), (2_400_000, "2.4 Mb")],
    )
    def test_sizes(self, value: int, expected: str) -> None:
        assert format_size(value) == expected


class TestFastaReading:
    def test_records_are_read_in_order(self, tmp_path) -> None:
        path = tmp_path / "x.fa"
        path.write_text(">one description here\nACGT\nACGT\n>two\nTTTT\n")
        assert parse_fasta(path) == [("one", "ACGTACGT"), ("two", "TTTT")]


class TestTheSearch:
    """A hit is reported only when a usable PAM sits beside it."""

    SPACER = "GCACGTCAGTCAGGATCCAG"

    def test_a_planted_perfect_off_target_with_a_pam_is_found(self) -> None:
        construct = "CCAACCAACCAA" + self.SPACER + "TGGCCAACCAACCAA"
        request = make_request(
            target_sequence="ACGT" * 20 + self.SPACER + "AGG" + "ACGT" * 20,
            delivery_construct_name="pTEST",
            delivery_construct_sequence=construct,
        )
        summary = search_off_targets(request, self.SPACER, None)
        construct_hits = [
            hit for hit in summary.hits if hit.source_id == "delivery_construct"
        ]
        assert len(construct_hits) == 1
        assert construct_hits[0].mismatches == 0
        assert construct_hits[0].pam == "TGG"
        assert construct_hits[0].hit_score == pytest.approx(100.0)

    def test_a_protospacer_without_a_pam_is_not_reported(self) -> None:
        construct = "CCAACCAACCAA" + self.SPACER + "TTTCCAACCAACCAA"
        request = make_request(
            target_sequence="ACGT" * 20 + self.SPACER + "AGG" + "ACGT" * 20,
            delivery_construct_name="pTEST",
            delivery_construct_sequence=construct,
        )
        summary = search_off_targets(request, self.SPACER, None)
        assert not [hit for hit in summary.hits if hit.source_id == "delivery_construct"]

    def test_mismatch_positions_are_reported_along_the_spacer(self) -> None:
        mutated = "T" + self.SPACER[1:-1] + "T"  # positions 1 and 20
        construct = "CCAACCAACCAA" + mutated + "TGGCCAACCAA"
        request = make_request(
            target_sequence="ACGT" * 20,
            delivery_construct_name="pTEST",
            delivery_construct_sequence=construct,
        )
        summary = search_off_targets(request, self.SPACER, None)
        hits = [hit for hit in summary.hits if hit.source_id == "delivery_construct"]
        assert len(hits) == 1
        assert hits[0].mismatch_positions == (1, 20)
        # Seed is the PAM-proximal 12 nt, so position 20 is in it and 1 is not.
        assert hits[0].seed_mismatches == 1

    def test_scope_none_performs_no_search(self) -> None:
        request = make_request(off_target_space=OffTargetSpace(scope="none"))
        summary = search_off_targets(request, self.SPACER, None)
        assert summary.searched is False
        assert summary.hits == []
        assert summary.specificity_score is None
        assert summary.searched_bases == 0
        assert "No off-target search was performed." in summary.space_statement

    def test_over_the_limit_refuses_rather_than_truncating(self) -> None:
        from packages.validation.grna import GuideRNAThresholds

        request = make_request()
        thresholds = GuideRNAThresholds(off_target_max_search_bp=10)
        summary = search_off_targets(request, self.SPACER, None, thresholds=thresholds)
        assert summary.searched is False
        assert "above the configured limit" in summary.space_statement
        assert any("not truncated silently" in note for note in summary.notes)

    @pytest.mark.parametrize("nuclease", ["SaCas9", "LbCas12a", "AsCas12a"])
    def test_the_published_score_is_withheld_outside_its_domain(self, nuclease: str) -> None:
        request = make_request(nuclease=nuclease)
        spacer = TARGET[:21] if nuclease == "SaCas9" else TARGET[:23]
        summary = search_off_targets(request, spacer, None)
        assert summary.specificity_status == "out_of_domain"
        assert summary.specificity_score is None
        assert summary.specificity_model_name == MIT_MODEL_NAME
        assert any(nuclease in note for note in summary.notes)
        assert summary.searched is True, "the search still runs, only the score is withheld"

    def test_determinism(self) -> None:
        request = make_request(
            delivery_construct_name="pTEST",
            delivery_construct_sequence="CCAACCAA" + self.SPACER + "TGGCCAA",
        )
        first = search_off_targets(request, self.SPACER, None)
        second = search_off_targets(request, self.SPACER, None)
        assert first.model_dump() == second.model_dump()
