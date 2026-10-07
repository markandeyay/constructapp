from __future__ import annotations

import pytest

from packages.core.sequence import (
    BACTERIAL_CODE,
    STANDARD_CODE,
    UNIT_COST_SCORING,
    AlignmentScoring,
    Hit,
    Repeat,
    Run,
    clean_sequence,
    complement,
    direct_repeats,
    edit_distance,
    find_both_strands,
    find_exact,
    find_iupac,
    find_orfs,
    find_with_mismatches,
    gc_content,
    gc_count,
    global_align,
    global_identity,
    hamming_distance,
    homopolymer_runs,
    local_align,
    matches_iupac,
    reverse_complement,
    translate,
)


# ---- dna ----------------------------------------------------------------------------------


def test_reverse_complement_known_values() -> None:
    assert reverse_complement("ATGC") == "GCAT"
    assert reverse_complement("AAACCCGGGTTT") == "AAACCCGGGTTT"  # reverse-palindromic
    assert reverse_complement("atgc") == "GCAT"
    assert reverse_complement("GAATTC") == "GAATTC"  # EcoRI site is its own reverse complement


def test_reverse_complement_is_an_involution() -> None:
    sequence = "ACGTTGCAAGGCTTAACC"
    assert reverse_complement(reverse_complement(sequence)) == sequence


def test_reverse_complement_handles_iupac_codes() -> None:
    assert reverse_complement("RYKM") == "KMRY"
    assert reverse_complement("NNGG") == "CCNN"
    assert complement("ACGT") == "TGCA"


def test_clean_sequence_fails_loudly() -> None:
    assert clean_sequence(" ac gt\n") == "ACGT"
    for bad in ("", "   ", "ACGU", "AC GN"):
        with pytest.raises(ValueError):
            clean_sequence(bad)
    assert clean_sequence("ACGN", allow_ambiguous=True) == "ACGN"
    with pytest.raises(TypeError):
        clean_sequence(None)  # type: ignore[arg-type]


def test_gc_content() -> None:
    assert gc_content("GGCC") == 1.0
    assert gc_content("AATT") == 0.0
    assert gc_content("ATGC") == 0.5
    assert gc_count("ATGCGG") == 4
    assert gc_content("gcat") == 0.5
    with pytest.raises(ValueError):
        gc_content("ATGN")


# ---- codon and ORF ------------------------------------------------------------------------


def test_standard_code_has_64_codons_and_three_stops() -> None:
    assert len(STANDARD_CODE.codon_to_amino_acid) == 64
    assert STANDARD_CODE.stop_codons == {"TAA", "TAG", "TGA"}
    assert STANDARD_CODE.start_codons == {"TTG", "CTG", "ATG"}
    assert BACTERIAL_CODE.codon_to_amino_acid == STANDARD_CODE.codon_to_amino_acid
    assert "GTG" in BACTERIAL_CODE.start_codons


@pytest.mark.parametrize(
    ("codon", "amino_acid"),
    [("ATG", "M"), ("TGG", "W"), ("TTT", "F"), ("GCC", "A"), ("AAA", "K"), ("CGA", "R"), ("AGA", "R"), ("TAA", "*"), ("TGA", "*"), ("TAG", "*")],
)
def test_translate_codon_known_values(codon: str, amino_acid: str) -> None:
    assert STANDARD_CODE.translate_codon(codon) == amino_acid


def test_translate_sequences() -> None:
    assert translate("ATGAAATAA") == "MK*"
    assert translate("ATGAAATAAGGG", to_stop=True) == "MK"
    with pytest.raises(ValueError, match="multiple of 3"):
        translate("ATGAA")


def test_synonymous_codons() -> None:
    assert STANDARD_CODE.synonymous_codons("ATG") == ("ATG",)
    assert STANDARD_CODE.synonymous_codons("CTG") == ("CTA", "CTC", "CTG", "CTT", "TTA", "TTG")
    assert len(STANDARD_CODE.synonymous_codons("TGA")) == 3


def test_find_orfs_forward_strand() -> None:
    orfs = find_orfs("CCCATGAAATAAGG", min_length_nt=9, both_strands=False)
    assert [(orf.start, orf.end, orf.strand, orf.has_stop) for orf in orfs] == [(3, 12, 1, True)]
    assert orfs[0].length == 9


def test_find_orfs_reverse_strand_reports_forward_coordinates() -> None:
    forward = "CCCATGAAATAAGG"
    orfs = find_orfs(reverse_complement(forward), min_length_nt=9)
    assert [(orf.strand, orf.start, orf.end, orf.forward_start, orf.forward_end) for orf in orfs] == [(-1, 3, 12, 2, 11)]


def test_find_orfs_uses_outermost_start_and_respects_minimum_and_stop_rules() -> None:
    sequence = "ATGATGAAATAA"
    assert [(o.start, o.end) for o in find_orfs(sequence, min_length_nt=3, both_strands=False)] == [(0, 12)]
    assert find_orfs(sequence, min_length_nt=13, both_strands=False) == []
    open_frame = "ATGAAACCC"
    assert find_orfs(open_frame, min_length_nt=3, both_strands=False) == []
    kept = find_orfs(open_frame, min_length_nt=3, both_strands=False, require_stop=False)
    assert [(o.start, o.end, o.has_stop) for o in kept] == [(0, 9, False)]
    with pytest.raises(ValueError):
        find_orfs("ATG", min_length_nt=0)


def test_find_orfs_start_codon_override() -> None:
    sequence = "GTGAAATAA"
    assert find_orfs(sequence, min_length_nt=3, both_strands=False) == []
    assert len(find_orfs(sequence, min_length_nt=3, both_strands=False, code=BACTERIAL_CODE)) == 1
    assert len(find_orfs(sequence, min_length_nt=3, both_strands=False, start_codons=frozenset({"GTG"}))) == 1


# ---- search -------------------------------------------------------------------------------


def test_find_exact_reports_overlapping_hits() -> None:
    assert find_exact("AAAA", "AA") == [0, 1, 2]
    assert find_exact("ACGT", "TT") == []


def test_find_exact_circular_spans_the_origin() -> None:
    assert find_exact("CGTA", "TAC", circular=True) == [2]
    assert find_exact("CGTA", "TAC") == []
    assert find_exact("ACGT", "ACGT", circular=True) == [0]
    with pytest.raises(ValueError):
        find_exact("AC", "ACG", circular=True)


def test_find_both_strands() -> None:
    hits = find_both_strands("GGTCTCAAAAGAGACC", "GGTCTC")
    assert hits == [Hit(0, 6, 1), Hit(10, 16, -1)]
    palindrome = find_both_strands("AAGAATTCAA", "GAATTC")
    assert palindrome == [Hit(2, 8, 1), Hit(2, 8, -1)]


def test_hamming_distance() -> None:
    assert hamming_distance("ACGT", "ACGA") == 1
    assert hamming_distance("ACGT", "ACGT") == 0
    with pytest.raises(ValueError):
        hamming_distance("ACG", "ACGT")


def test_find_with_mismatches() -> None:
    sequence = "TTACGTACTT"
    hits = find_with_mismatches(sequence, "ACGAAC", max_mismatches=1, both_strands=False)
    assert hits == [Hit(2, 8, 1, 1)]
    assert find_with_mismatches(sequence, "ACGAAC", max_mismatches=0, both_strands=False) == []
    reverse_hits = find_with_mismatches(sequence, "GTACGT", max_mismatches=0)
    assert reverse_hits == [Hit(2, 8, -1, 0)]
    with pytest.raises(ValueError):
        find_with_mismatches(sequence, "ACG", max_mismatches=-1)


def test_matches_iupac() -> None:
    assert matches_iupac("AGG", "NGG")
    assert not matches_iupac("AGA", "NGG")
    assert matches_iupac("TTTA", "TTTV")
    assert not matches_iupac("TTTT", "TTTV")
    assert matches_iupac("AAGGAT", "NNGRRT")
    assert not matches_iupac("AAGCAT", "NNGRRT")
    with pytest.raises(ValueError):
        matches_iupac("AAA", "AAZ")


def test_find_iupac_pam_on_both_strands() -> None:
    sequence = "CCATAGG"
    forward = find_iupac(sequence, "NGG", both_strands=False)
    assert forward == [Hit(4, 7, 1)]
    both = find_iupac(sequence, "NGG")
    assert Hit(0, 3, -1) in both and Hit(4, 7, 1) in both
    assert len(both) == 2


def test_find_iupac_cas12a_style_five_prime_pam() -> None:
    hits = find_iupac("GTTTAGCC", "TTTV", both_strands=False)
    assert hits == [Hit(1, 5, 1)]


def test_homopolymer_runs() -> None:
    assert homopolymer_runs("ACGGGGTAAAAAC", min_length=4) == [Run(2, 6, "G"), Run(7, 12, "A")]
    assert homopolymer_runs("ACGGGGTAAAAAC", min_length=6) == []
    assert homopolymer_runs("TTTT", min_length=4) == [Run(0, 4, "T")]
    assert Run(2, 6, "G").length == 4
    with pytest.raises(ValueError):
        homopolymer_runs("AAAA", min_length=1)


def test_direct_repeats_reports_a_repeat_once_at_maximal_extent() -> None:
    sequence = "ACGTTGCAAC" + "GGGG" + "ACGTTGCAAC"
    assert direct_repeats(sequence, min_length=6) == [Repeat(0, 14, 10)]
    assert direct_repeats(sequence, min_length=11) == []


def test_direct_repeats_ignores_overlapping_copies() -> None:
    assert direct_repeats("AAAAAAAA", min_length=5) == []
    assert direct_repeats("ACGTACGT", min_length=4) == [Repeat(0, 4, 4)]


def test_direct_repeats_validates_input() -> None:
    with pytest.raises(ValueError):
        direct_repeats("ACGT", min_length=0)
    assert direct_repeats("ACGT", min_length=5) == []


# ---- alignment ----------------------------------------------------------------------------


def test_edit_distance_classic_values() -> None:
    assert edit_distance("GATTACA", "GATTACA") == 0
    assert edit_distance("ACGT", "AGT") == 1
    assert edit_distance("AAAA", "TTTT") == 4
    assert edit_distance("GATTACA", "GCATGC") == edit_distance("GCATGC", "GATTACA")


def test_global_align_identical_and_single_substitution() -> None:
    identical = global_align("ACGTACGT", "ACGTACGT", UNIT_COST_SCORING)
    assert identical.score == 8 and identical.identity == 1.0 and identical.gaps == 0
    one = global_align("ACGTACGT", "ACGTTCGT", UNIT_COST_SCORING)
    assert one.mismatches == 1 and one.matches == 7
    assert one.identity == pytest.approx(7 / 8)


def test_global_align_places_a_gap() -> None:
    result = global_align("ACGTACGT", "ACGACGT", UNIT_COST_SCORING)
    assert result.length == 8
    assert result.gaps == 1
    assert result.aligned_a.replace("-", "") == "ACGTACGT"
    assert result.aligned_b.replace("-", "") == "ACGACGT"


def test_global_align_respects_the_scoring_it_is_given() -> None:
    custom = AlignmentScoring(match=2, mismatch=-3, gap=-5)
    assert global_align("ACGT", "ACCT", custom).score == 3
    assert global_align("ACGTACGT", "ACGACGT", UNIT_COST_SCORING).score == 6
    assert global_align("ACGTACGT", "ACGACGT", AlignmentScoring(match=1, mismatch=-1, gap=-10)).score == -3


def test_global_align_is_deterministic() -> None:
    first = global_align("ACACACAC", "ACAC", UNIT_COST_SCORING)
    second = global_align("ACACACAC", "ACAC", UNIT_COST_SCORING)
    assert first == second


def test_global_identity_of_reverse_complement_pair_is_low_until_flipped() -> None:
    sequence = "GGATCCAAGGTTCCAAGGATCC"
    assert global_identity(sequence, sequence) == 1.0
    assert global_identity(sequence, reverse_complement(sequence)) < 1.0
    assert global_identity(sequence, reverse_complement(reverse_complement(sequence))) == 1.0


def test_local_align_finds_the_shared_region() -> None:
    result = local_align("TTTTGATTACATTTT", "CCCCGATTACACCCC", UNIT_COST_SCORING)
    assert result.score == 7
    assert result.aligned_a == "GATTACA"
    assert (result.start_a, result.end_a, result.start_b, result.end_b) == (4, 11, 4, 11)


def test_local_align_with_nothing_in_common_is_empty() -> None:
    result = local_align("AAAA", "TTTT", UNIT_COST_SCORING)
    assert result.score == 0 and result.length == 0 and result.identity == 0.0
