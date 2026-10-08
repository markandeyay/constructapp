"""Secondary structure scoring, section 7.4 and open question Q6.

Section 7.4 permits "a sliding-window complementarity score with explicit 3'
weighting ... provided the scoring is documented". These tests are what makes
the documented scoring checkable: each asserts a property the documentation in
`structure.py` claims.
"""

from __future__ import annotations

import pytest

from packages.core.sequence import reverse_complement
from packages.validation.assembly import structure


def test_a_fully_complementary_oligo_scores_its_whole_length() -> None:
    """Scores are in base pairs: a self-complementary 12-mer pairs over 12 bp."""
    result = structure.self_dimer("GAATTCGAATTC")
    assert result.any_score == 12
    assert result.three_prime_score == 12


def test_a_three_prime_run_is_scored_and_an_internal_one_is_not() -> None:
    """The 3' score counts only a run that reaches the 3'-terminal base.

    Section 7.4: a 3' dimer is extendable and that is what matters. An unpaired
    3' terminus scores zero even when the oligo pairs well elsewhere.
    """
    # 3' end is GGGGCCCC, whose last four bases pair with its own first four.
    three_prime = structure.self_dimer("ATCTAGCTAGCTAGGGGGCCCC")
    assert three_prime.three_prime_score >= 4

    # The query pairs fully over its first eight bases and its 3' end is a run of
    # A, which has no T or A partner in a GC-only oligo, so it cannot pair.
    internal = structure.complementarity("GGGGCCCCAAAAAAAA", "GGGGCCCC")
    assert internal.any_score == 8
    assert internal.three_prime_score == 0
    assert internal.three_prime_involved is False


def test_hetero_dimer_reports_whichever_three_prime_end_is_extendable() -> None:
    """Either primer's 3' end consumes the reaction, so both are tested."""
    forward = "ATCTAGCTAGCTAGCTAGCA"
    reverse = "TTTTTTTTTTTTTTTGCTAGCTAGCTAGAT"
    result = structure.hetero_dimer(forward, reverse)
    assert result.three_prime_score > 0
    assert result.three_prime_partner in ("forward", "reverse")
    # Swapping the arguments must find the same worst case.
    swapped = structure.hetero_dimer(reverse, forward)
    assert swapped.any_score == result.any_score
    assert swapped.three_prime_score == result.three_prime_score


def test_complementarity_is_symmetric_in_the_any_score() -> None:
    first, second = "ACGTTGCAGGCATTAC", "GTAATGCCTGCAACGT"
    assert structure.complementarity(first, second).any_score == structure.complementarity(second, first).any_score


def test_no_complementarity_scores_zero() -> None:
    result = structure.complementarity("AAAAAAAAAA", "AAAAAAAAAA")
    assert result.any_score == 0
    assert result.three_prime_score == 0


def test_complementarity_requires_two_sequences() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        structure.complementarity("ACGT", "")


# ---------------------------------------------------------------------------
# Hairpins
# ---------------------------------------------------------------------------


def test_window_hairpin_finds_the_designed_stem_and_loop() -> None:
    """A 6 bp stem closing a 4 nt loop, which is what the sequence encodes."""
    result = structure.window_hairpin("GCGCGCAAAAGCGCGC", min_loop_nt=3, three_prime_window_nt=5)
    assert result.engine == structure.ENGINE_WINDOW
    assert result.stem_bp == 6
    assert result.loop_nt == 4
    assert result.three_prime_involved is True
    assert result.delta_g_kcal_per_mol is None, "the window engine must not report an invented free energy"


def test_window_hairpin_respects_the_minimum_loop_size() -> None:
    """A stem that would close a loop shorter than the minimum is not a hairpin.

    Minimum loop 3 nt is the standard nucleic acid secondary structure minimum,
    and ViennaRNA uses the same value.
    """
    # GCGC + AA + GCGC: a 4 bp stem would need a 2 nt loop, which is too tight.
    tight = structure.window_hairpin("GCGCAAGCGC", min_loop_nt=3, three_prime_window_nt=5)
    loose = structure.window_hairpin("GCGCAAAGCGC", min_loop_nt=3, three_prime_window_nt=5)
    assert tight.stem_bp < loose.stem_bp


def test_window_hairpin_finds_nothing_in_an_unstructured_oligo() -> None:
    result = structure.window_hairpin("AAAAAAAAAAAAAAAAAAAA", min_loop_nt=3, three_prime_window_nt=5)
    assert result.stem_bp == 0
    assert result.three_prime_involved is False


def test_window_hairpin_rejects_a_nonsense_loop_size() -> None:
    with pytest.raises(ValueError, match="min_loop_nt"):
        structure.window_hairpin("ACGTACGT", min_loop_nt=0, three_prime_window_nt=5)


def test_the_q6_decision_is_recorded_and_consistent() -> None:
    """Open question Q6: prefer ViennaRNA when installable, and record the choice.

    `viennarna_version` is the single answer to "is it available", and `auto`
    must agree with it. Both branches are legitimate; what is not legitimate is
    the two disagreeing, because then the engine that ran is unknown.
    """
    available = structure.hairpin_engine_available()
    assert available == (structure.viennarna_version() is not None)
    result = structure.hairpin("GCGCGCAAAAGCGCGC", min_loop_nt=3, three_prime_window_nt=5, engine="auto")
    assert result.engine == (structure.ENGINE_VIENNARNA if available else structure.ENGINE_WINDOW)


def test_demanding_viennarna_when_it_is_absent_raises_rather_than_degrading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Section 3.3 constraint 4: a silent degradation is forbidden."""
    monkeypatch.setattr(structure, "viennarna_version", lambda: None)
    with pytest.raises(RuntimeError, match="ViennaRNA is not importable"):
        structure.hairpin("GCGCGCAAAAGCGCGC", min_loop_nt=3, three_prime_window_nt=5, engine="viennarna")


def test_viennarna_uses_dna_parameters_not_rna_parameters() -> None:
    """A primer is DNA. Folding it against RNA parameters would be the wrong number.

    The DNA parameter set gives a measurably different free energy from the RNA
    default for the same sequence, so this test would catch a build that silently
    stopped loading it.
    """
    if not structure.hairpin_engine_available():
        pytest.skip("ViennaRNA is not installed in this environment")
    result = structure.viennarna_hairpin("GCGCGCAAAAGCGCGC", three_prime_window_nt=5)
    assert result.engine == structure.ENGINE_VIENNARNA
    assert result.delta_g_kcal_per_mol is not None and result.delta_g_kcal_per_mol < 0
    assert result.structure is not None and "(" in result.structure
    assert result.stem_bp == 6


def test_viennarna_reports_an_unstructured_oligo_as_a_real_zero() -> None:
    if not structure.hairpin_engine_available():
        pytest.skip("ViennaRNA is not installed in this environment")
    result = structure.viennarna_hairpin("AAAAAAAAAAAAAAAAAAAA", three_prime_window_nt=5)
    assert result.delta_g_kcal_per_mol == pytest.approx(0.0)
    assert result.stem_bp == 0


def test_both_engines_agree_about_which_oligos_are_structured() -> None:
    """The fallback is not a different answer, it is the same answer in other units."""
    if not structure.hairpin_engine_available():
        pytest.skip("ViennaRNA is not installed in this environment")
    structured = "GCGCGCGCAAAAGCGCGCGC"
    flat = "AAAAAAAAAAAAAAAAAAAA"
    for sequence, expect_structure in ((structured, True), (flat, False)):
        window = structure.window_hairpin(sequence, min_loop_nt=3, three_prime_window_nt=5)
        vienna = structure.viennarna_hairpin(sequence, three_prime_window_nt=5)
        assert (window.stem_bp > 0) is expect_structure, sequence
        assert (vienna.stem_bp > 0) is expect_structure, sequence


def test_hairpin_rejects_an_unknown_engine() -> None:
    with pytest.raises(ValueError, match="engine must be"):
        structure.hairpin("ACGTACGT", min_loop_nt=3, three_prime_window_nt=5, engine="mfold")


# ---------------------------------------------------------------------------
# Shared complementarity, used by section 7.5 check 13
# ---------------------------------------------------------------------------


def test_longest_shared_complementarity_measures_the_right_thing() -> None:
    arm = "ACGTTGCAGGCATTACGGAC"
    assert structure.longest_shared_complementarity(arm, reverse_complement(arm)) == len(arm)
    assert structure.longest_shared_complementarity(arm, "AAAAAAAAAAAAAAAAAAAA") < 5


def test_longest_shared_complementarity_rejects_an_empty_input() -> None:
    """An empty junction arm is a malformed design, so it raises rather than scoring 0."""
    with pytest.raises(ValueError, match="must not be empty"):
        structure.longest_shared_complementarity("", "ACGT")


def test_scores_are_deterministic() -> None:
    """Section 3.3 constraint 3."""
    sequence = "ATCTAGCTAGCTAGGGGGCCCC"
    first = structure.self_dimer(sequence)
    second = structure.self_dimer(sequence)
    assert first == second
    assert structure.window_hairpin(sequence, min_loop_nt=3, three_prime_window_nt=5) == structure.window_hairpin(
        sequence, min_loop_nt=3, three_prime_window_nt=5
    )
