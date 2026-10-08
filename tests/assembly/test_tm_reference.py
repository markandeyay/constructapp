"""The Appendix A.1 verification gate for the nearest-neighbor Tm.

Source: Appendix A.1 and section 14.2 of the engine capability system design.
Section 14.2: "WP-04's Tm implementation is checked against the Appendix A test
oligos. Tolerance: 1.0 degree C. This is a unit test and it is a hard gate. A Tm
implementation that is silently wrong is worse than no Tm implementation,
because people will order primers from it."

Appendix A.1 deliberately does not state expected values, "because a number
copied from memory is exactly the failure mode section 0.3 forbids". The
reference values are therefore computed here, in this test, by an established
tool at the stated conditions, and the recorded table is in `progress/WP-04.md`.

THE REFERENCE TOOL AND ITS CONFIGURATION.

Tool: Biopython 1.87, `Bio.SeqUtils.MeltingTemp.Tm_NN`.

Configuration, and why it corresponds to Appendix A rather than merely
resembling it:

* `nn_table=DNA_NN3`. Of the four DNA tables Biopython ships, DNA_NN3 is the one
  whose values are Appendix A's. Its ten nearest-neighbor pairs are Appendix A's
  ten, value for value; its `init_A/T` is (2.3, 4.1) and its `init_G/C` is
  (0.1, -2.8), which are Appendix A's two initiation terms; its `sym` is
  (0.0, -1.4), Appendix A's symmetry correction; and its general `init` term is
  (0, 0), so no extra initiation is added. `test_reference_table_matches_appendix_a`
  asserts all of that rather than taking it on trust, so a Biopython release that
  changed a value would fail this test instead of silently shifting the
  reference.
* `saltcorr=5`. Biopython's method 5 is documented as
  "Correction for deltaS: 0.368 x (N-1) x ln[Na+] (SantaLucia (1998))", which is
  the Appendix A salt correction formula character for character.
* `dnac1`/`dnac2`/`selfcomp` chosen so Biopython's strand concentration term `k`
  equals the one section 7.3 specifies. Biopython uses
  `k = dnac1 - dnac2 / 2` normally and `k = dnac1` when `selfcomp` is set.
  Section 7.3 uses `C_T / 4` for a non-self-complementary duplex and `C_T` for a
  self-complementary one. So a total strand concentration of C_T is passed as
  `dnac1 = dnac2 = C_T / 2` in the first case, giving
  `k = C_T/2 - C_T/4 = C_T/4`, and as `dnac1 = C_T, selfcomp=True` in the
  second, giving `k = C_T`. Both describe the same 500 nM of total strand, which
  is the condition Appendix A.1 states.
* `Na=50`, `Mg=0`, `dNTPs=0`: the Appendix A.1 condition of 50 mM monovalent
  salt, with no divalent term so the comparison isolates the monovalent
  correction. The divalent conversion is tested separately in
  `test_tm.py::test_divalent_conversion_matches_the_reference_tool`.

Two of the four Appendix A.1 oligos are self-complementary, which is checked
explicitly below: the GC-rich 20-mer and the AT-rich 20-mer are both their own
reverse complement. That makes the symmetry case a real part of this gate rather
than an untested branch.
"""

from __future__ import annotations

import pytest

from packages.core.sequence.tm import (
    INITIATION_TERMINAL_AT,
    INITIATION_TERMINAL_GC,
    NEAREST_NEIGHBOR_PARAMETERS,
    SYMMETRY_CORRECTION,
    is_self_complementary,
    melting_temperature,
)

Bio = pytest.importorskip("Bio", reason="Biopython is the Appendix A.1 reference tool")
from Bio.SeqUtils import MeltingTemp as mt  # noqa: E402  (after importorskip, by design)

# Appendix A.1, verbatim.
APPENDIX_A1_OLIGOS: tuple[tuple[str, str], ...] = (
    ("GC-balanced, 20 nt", "GTAAAACGACGGCCAGTGAA"),
    ("GC-rich, 20 nt", "GCGGCCGCGGCCGCGGCCGC"),
    ("AT-rich, 20 nt", "AATTAATTAATTAATTAATT"),
    ("Short, 18 nt", "ACGTACGTACGTACGTAC"),
)

# Appendix A.1 conditions: 500 nM primer and 50 mM monovalent salt.
PRIMER_CONC_NM = 500.0
MONOVALENT_SALT_MM = 50.0

# Section 14.2. Not negotiable, and never widened to accommodate a discrepancy.
TOLERANCE_C = 1.0


def reference_tm(sequence: str) -> float:
    """The reference value for one oligo. Configuration justified in the module docstring."""
    if is_self_complementary(sequence):
        return mt.Tm_NN(
            sequence,
            nn_table=mt.DNA_NN3,
            saltcorr=5,
            Na=MONOVALENT_SALT_MM,
            Mg=0,
            dNTPs=0,
            dnac1=PRIMER_CONC_NM,
            dnac2=0,
            selfcomp=True,
        )
    return mt.Tm_NN(
        sequence,
        nn_table=mt.DNA_NN3,
        saltcorr=5,
        Na=MONOVALENT_SALT_MM,
        Mg=0,
        dNTPs=0,
        dnac1=PRIMER_CONC_NM / 2,
        dnac2=PRIMER_CONC_NM / 2,
        selfcomp=False,
    )


def test_reference_table_matches_appendix_a() -> None:
    """DNA_NN3 is Appendix A's parameter set, so the reference is the right reference.

    If a Biopython release ever changed one of these values, this test fails
    rather than the comparison below silently drifting.
    """
    for key, (delta_h, delta_s) in NEAREST_NEIGHBOR_PARAMETERS.items():
        assert key in mt.DNA_NN3, f"{key} is in Appendix A but not in Biopython's DNA_NN3"
        assert mt.DNA_NN3[key] == pytest.approx((delta_h, delta_s)), key
    assert len(NEAREST_NEIGHBOR_PARAMETERS) == 10, "Appendix A lists ten nearest-neighbor pairs"
    assert mt.DNA_NN3["init_A/T"] == pytest.approx(INITIATION_TERMINAL_AT)
    assert mt.DNA_NN3["init_G/C"] == pytest.approx(INITIATION_TERMINAL_GC)
    assert mt.DNA_NN3["sym"] == pytest.approx(SYMMETRY_CORRECTION)
    # No extra initiation term, so Appendix A's two terms are the whole story.
    assert mt.DNA_NN3["init"] == pytest.approx((0.0, 0.0))
    assert mt.DNA_NN3["init_oneG/C"] == pytest.approx((0.0, 0.0))
    assert mt.DNA_NN3["init_allA/T"] == pytest.approx((0.0, 0.0))
    assert mt.DNA_NN3["init_5T/A"] == pytest.approx((0.0, 0.0))


def test_appendix_a1_self_complementarity_is_detected() -> None:
    """Two of the four Appendix A.1 oligos are self-complementary.

    The GC-rich and the AT-rich 20-mers are each their own reverse complement, so
    section 7.3's `C_T` rather than `C_T / 4` and the Appendix A symmetry
    correction both apply to them. Asserted here so the gate below is known to
    exercise the symmetry branch.
    """
    results = {label: is_self_complementary(sequence) for label, sequence in APPENDIX_A1_OLIGOS}
    assert results == {
        "GC-balanced, 20 nt": False,
        "GC-rich, 20 nt": True,
        "AT-rich, 20 nt": True,
        "Short, 18 nt": False,
    }


@pytest.mark.parametrize(("label", "sequence"), APPENDIX_A1_OLIGOS, ids=[item[0] for item in APPENDIX_A1_OLIGOS])
def test_appendix_a1_gate(label: str, sequence: str) -> None:
    """THE SECTION 14.2 HARD GATE: within 1.0 degree C of the reference tool.

    If this fails, the implementation is wrong. The tolerance does not move.
    """
    ours = melting_temperature(
        sequence,
        primer_conc_nm=PRIMER_CONC_NM,
        monovalent_salt_mm=MONOVALENT_SALT_MM,
    )
    reference = reference_tm(sequence)
    assert abs(ours - reference) <= TOLERANCE_C, (
        f"{label} ({sequence}): this implementation gives {ours:.4f} C, Biopython "
        f"{Bio.__version__} Tm_NN with DNA_NN3 and saltcorr=5 gives {reference:.4f} C, a "
        f"difference of {abs(ours - reference):.4f} C against a {TOLERANCE_C} C tolerance. "
        "Fix the implementation, not the tolerance (section 14.2)."
    )


def test_appendix_a1_table_for_the_progress_record(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the side-by-side table that `progress/WP-04.md` records.

    Run with `-s` to see it. Having the table generated by the test rather than
    typed into the progress file is what keeps the recorded numbers honest.
    """
    lines = [
        f"Reference tool: Biopython {Bio.__version__}, Bio.SeqUtils.MeltingTemp.Tm_NN",
        "Parameters: nn_table=DNA_NN3, saltcorr=5, Na=50, Mg=0, dNTPs=0; "
        "dnac1=dnac2=250 nM (k = C_T/4) for a non-self-complementary oligo, "
        "dnac1=500 nM with selfcomp=True (k = C_T) for a self-complementary one",
        f"Conditions: {PRIMER_CONC_NM:.0f} nM total strand, {MONOVALENT_SALT_MM:.0f} mM monovalent salt",
        "",
        f"{'Oligo':24s} {'Sequence':22s} {'selfcomp':9s} {'ours (C)':>9s} {'ref (C)':>9s} {'delta':>9s}",
    ]
    for label, sequence in APPENDIX_A1_OLIGOS:
        ours = melting_temperature(
            sequence, primer_conc_nm=PRIMER_CONC_NM, monovalent_salt_mm=MONOVALENT_SALT_MM
        )
        reference = reference_tm(sequence)
        lines.append(
            f"{label:24s} {sequence:22s} {str(is_self_complementary(sequence)):9s} "
            f"{ours:9.4f} {reference:9.4f} {ours - reference:+9.4f}"
        )
    print("\n".join(lines))
    assert len(lines) == 9
