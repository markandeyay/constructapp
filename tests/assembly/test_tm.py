"""Unit tests for the shared nearest-neighbor Tm implementation.

Source: section 7.3 and Appendix A of the engine capability system design. The
Appendix A.1 gate is in `test_tm_reference.py`; these tests cover the pieces that
gate does not reach: the Appendix A table itself, the symmetry branch, the
divalent conversion, the shared location section 13.4 requires, and the
failure modes that must raise rather than return a number.
"""

from __future__ import annotations

import math

import pytest

from packages.core.sequence.tm import (
    DIVALENT_TO_MONOVALENT_COEFFICIENT,
    GAS_CONSTANT_R,
    INITIATION_TERMINAL_AT,
    INITIATION_TERMINAL_GC,
    NEAREST_NEIGHBOR_PARAMETERS,
    SALT_CORRECTION_COEFFICIENT,
    SYMMETRY_CORRECTION,
    initiation_terms,
    is_self_complementary,
    melting_temperature,
    melting_temperature_detail,
    nearest_neighbor_stack,
    sodium_equivalent_mm,
)


def test_appendix_a_constants_are_the_appendix_a_values() -> None:
    """Appendix A fixes these so no agent has to recall them (section 0.3)."""
    assert GAS_CONSTANT_R == 1.987
    assert SALT_CORRECTION_COEFFICIENT == 0.368
    assert INITIATION_TERMINAL_GC == (0.1, -2.8)
    assert INITIATION_TERMINAL_AT == (2.3, 4.1)
    assert SYMMETRY_CORRECTION == (0.0, -1.4)
    assert NEAREST_NEIGHBOR_PARAMETERS == {
        "AA/TT": (-7.9, -22.2),
        "AT/TA": (-7.2, -20.4),
        "TA/AT": (-7.2, -21.3),
        "CA/GT": (-8.5, -22.7),
        "GT/CA": (-8.4, -22.4),
        "CT/GA": (-7.8, -21.0),
        "GA/CT": (-8.2, -22.2),
        "CG/GC": (-10.6, -27.2),
        "GC/CG": (-9.8, -24.4),
        "GG/CC": (-8.0, -19.9),
    }


def test_the_tm_implementation_lives_in_the_shared_package() -> None:
    """Section 13.4: WP-04 owns the Tm but places it in a shared location from the start.

    WP-05 imports it from here, so this is a contract test, not a style test.
    """
    from packages.core.sequence import melting_temperature as exported

    assert exported is melting_temperature
    module = melting_temperature.__module__
    assert module == "packages.core.sequence.tm", module


def test_all_sixteen_dinucleotides_resolve_against_the_ten_appendix_a_entries() -> None:
    """Appendix A lists ten pairs; the other six read as the same stack from the other strand."""
    for first in "ACGT":
        for second in "ACGT":
            delta_h, delta_s = nearest_neighbor_stack(first + second)
            assert delta_h < 0 and delta_s < 0, first + second


def test_a_stack_and_its_reverse_complement_give_the_same_values() -> None:
    """One physical stack, two readings, one set of parameters."""
    assert nearest_neighbor_stack("GT") == nearest_neighbor_stack("AC")
    assert nearest_neighbor_stack("CA") == nearest_neighbor_stack("TG")
    assert nearest_neighbor_stack("AA") == nearest_neighbor_stack("TT")


def test_initiation_applies_one_term_per_duplex_end() -> None:
    """Appendix A: one initiation term per duplex end, chosen by that end's base pair."""
    # Both ends G or C: two terminal G/C terms.
    assert initiation_terms("GAAAC") == pytest.approx(
        (2 * INITIATION_TERMINAL_GC[0], 2 * INITIATION_TERMINAL_GC[1])
    )
    # Both ends A or T: two terminal A/T terms.
    assert initiation_terms("ACCCT") == pytest.approx(
        (2 * INITIATION_TERMINAL_AT[0], 2 * INITIATION_TERMINAL_AT[1])
    )
    # One of each.
    assert initiation_terms("GCCCT") == pytest.approx(
        (
            INITIATION_TERMINAL_GC[0] + INITIATION_TERMINAL_AT[0],
            INITIATION_TERMINAL_GC[1] + INITIATION_TERMINAL_AT[1],
        )
    )


def test_self_complementary_detection_is_exact() -> None:
    assert is_self_complementary("GAATTC")
    assert is_self_complementary("AATTAATTAATTAATTAATT")
    assert is_self_complementary("GCGGCCGCGGCCGCGGCCGC")
    # Contains a palindrome but is not itself one.
    assert not is_self_complementary("AAAGAATTCAAA")
    assert not is_self_complementary("GTAAAACGACGGCCAGTGAA")


def test_the_symmetry_correction_and_the_concentration_term_apply_together() -> None:
    """Section 7.3: a self-complementary duplex uses C_T, not C_T / 4, plus the symmetry term."""
    detail = melting_temperature_detail("GAATTCGAATTC", primer_conc_nm=500.0, monovalent_salt_mm=50.0)
    assert detail.self_complementary is True
    assert detail.strand_concentration_term_molar == pytest.approx(500e-9)
    # The symmetry correction is in the reported entropy.
    stack_s = nearest_neighbor_stack("GAATTCGAATTC")[1]
    init_s = initiation_terms("GAATTCGAATTC")[1]
    assert detail.delta_s_cal_per_mol_k == pytest.approx(stack_s + init_s + SYMMETRY_CORRECTION[1])

    other = melting_temperature_detail("GTAAAACGACGGCCAGTGAA", primer_conc_nm=500.0, monovalent_salt_mm=50.0)
    assert other.self_complementary is False
    assert other.strand_concentration_term_molar == pytest.approx(500e-9 / 4)


def test_the_salt_correction_is_the_appendix_a_formula() -> None:
    sequence = "GTAAAACGACGGCCAGTGAA"
    detail = melting_temperature_detail(sequence, primer_conc_nm=500.0, monovalent_salt_mm=50.0)
    expected = detail.delta_s_cal_per_mol_k + SALT_CORRECTION_COEFFICIENT * (len(sequence) - 1) * math.log(0.050)
    assert detail.delta_s_salt_corrected_cal_per_mol_k == pytest.approx(expected)


def test_lower_salt_lowers_the_tm() -> None:
    """A real property of the formula, and a guard against a sign error in it."""
    high = melting_temperature("GTAAAACGACGGCCAGTGAA", primer_conc_nm=500.0, monovalent_salt_mm=200.0)
    low = melting_temperature("GTAAAACGACGGCCAGTGAA", primer_conc_nm=500.0, monovalent_salt_mm=10.0)
    assert low < high


def test_higher_primer_concentration_raises_the_tm() -> None:
    dilute = melting_temperature("GTAAAACGACGGCCAGTGAA", primer_conc_nm=50.0, monovalent_salt_mm=50.0)
    concentrated = melting_temperature("GTAAAACGACGGCCAGTGAA", primer_conc_nm=5000.0, monovalent_salt_mm=50.0)
    assert concentrated > dilute


def test_no_gc_percentage_approximation_is_used() -> None:
    """Section 7.3 forbids the Wallace rule and every GC-percentage estimate.

    Two 20-mers with identical GC content and different sequence must give
    different melting temperatures. Any GC-percentage formula, Wallace included,
    would give them the same answer.
    """
    first = "ATATATATATGCGCGCGCGC"
    second = "ATGCATGCATGCATGCATGC"
    assert first.count("G") + first.count("C") == second.count("G") + second.count("C")
    a = melting_temperature(first, primer_conc_nm=500.0, monovalent_salt_mm=50.0)
    b = melting_temperature(second, primer_conc_nm=500.0, monovalent_salt_mm=50.0)
    assert abs(a - b) > 1.0, "a sequence-dependent model must separate these two"


# ---------------------------------------------------------------------------
# The divalent conversion, section 7.3 and Appendix E
# ---------------------------------------------------------------------------


def test_divalent_conversion_is_the_von_ahsen_formula() -> None:
    """Section 7.3: convert magnesium and dNTPs to a monovalent equivalent."""
    equivalent, applied = sodium_equivalent_mm(50.0, 1.5, 0.2)
    assert applied is True
    assert equivalent == pytest.approx(50.0 + DIVALENT_TO_MONOVALENT_COEFFICIENT * math.sqrt(1.5 - 0.2))


def test_divalent_conversion_is_dropped_when_dntps_chelate_all_the_magnesium() -> None:
    """dNTPs at or above the magnesium concentration leave no free magnesium.

    Extrapolating past that point would be inventing a number, which section 3.3
    constraint 1 forbids, so the divalent term is dropped instead.
    """
    equivalent, applied = sodium_equivalent_mm(50.0, 1.5, 1.5)
    assert applied is False
    assert equivalent == 50.0
    equivalent, applied = sodium_equivalent_mm(50.0, 1.5, 5.0)
    assert applied is False
    assert equivalent == 50.0


def test_divalent_conversion_can_be_switched_off_explicitly() -> None:
    equivalent, applied = sodium_equivalent_mm(50.0, 1.5, 0.2, apply_divalent_conversion=False)
    assert applied is False
    assert equivalent == 50.0


def test_divalent_conversion_matches_the_reference_tool() -> None:
    """The conversion used is the one the Appendix A.1 reference tool applies.

    Biopython's `salt_correction` builds the same von Ahsen sodium equivalent and
    cites the same paper, so this is a check that the two agree rather than a
    check that the formula was typed in correctly.
    """
    Bio = pytest.importorskip("Bio")
    assert Bio is not None
    from Bio.SeqUtils import MeltingTemp as mt

    sequence = "GTAAAACGACGGCCAGTGAA"
    ours = melting_temperature(
        sequence, primer_conc_nm=500.0, monovalent_salt_mm=50.0, divalent_salt_mm=1.5, dntp_mm=0.2
    )
    reference = mt.Tm_NN(
        sequence,
        nn_table=mt.DNA_NN3,
        saltcorr=5,
        Na=50,
        Mg=1.5,
        dNTPs=0.2,
        dnac1=250,
        dnac2=250,
        selfcomp=False,
    )
    assert abs(ours - reference) <= 1.0, (ours, reference)


def test_magnesium_raises_the_tm() -> None:
    without = melting_temperature("GTAAAACGACGGCCAGTGAA", primer_conc_nm=500.0, monovalent_salt_mm=50.0)
    with_magnesium = melting_temperature(
        "GTAAAACGACGGCCAGTGAA", primer_conc_nm=500.0, monovalent_salt_mm=50.0, divalent_salt_mm=1.5, dntp_mm=0.2
    )
    assert with_magnesium > without


# ---------------------------------------------------------------------------
# Failure modes: raise rather than return a meaningless number
# ---------------------------------------------------------------------------


def test_a_one_base_oligo_raises() -> None:
    with pytest.raises(ValueError, match="at least 2 nucleotides"):
        melting_temperature("A", primer_conc_nm=500.0, monovalent_salt_mm=50.0)


def test_zero_primer_concentration_raises() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        melting_temperature("ACGTACGTACGT", primer_conc_nm=0.0, monovalent_salt_mm=50.0)


def test_zero_monovalent_salt_raises() -> None:
    """ln([Na+]) is undefined at zero, so the formula must refuse rather than guess."""
    with pytest.raises(ValueError, match="sodium equivalent is zero"):
        melting_temperature("ACGTACGTACGT", primer_conc_nm=500.0, monovalent_salt_mm=0.0)


def test_negative_salt_raises() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        sodium_equivalent_mm(-1.0)


def test_an_ambiguity_code_raises() -> None:
    """An N has no nearest-neighbor parameter, so a Tm for it would be invented."""
    with pytest.raises(ValueError):
        melting_temperature("ACGTNACGTACGT", primer_conc_nm=500.0, monovalent_salt_mm=50.0)


def test_detail_reports_everything_needed_to_reproduce_the_number() -> None:
    detail = melting_temperature_detail(
        "GTAAAACGACGGCCAGTGAA", primer_conc_nm=500.0, monovalent_salt_mm=50.0, divalent_salt_mm=1.5, dntp_mm=0.2
    )
    assert detail.length == 20
    assert detail.gc_fraction == pytest.approx(0.5)
    assert detail.divalent_conversion_applied is True
    assert detail.sodium_equivalent_mm > 50.0
    assert detail.tm_celsius == pytest.approx(
        (detail.delta_h_kcal_per_mol * 1000.0)
        / (
            detail.delta_s_salt_corrected_cal_per_mol_k
            + GAS_CONSTANT_R * math.log(detail.strand_concentration_term_molar)
        )
        - 273.15
    )
