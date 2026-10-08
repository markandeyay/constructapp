"""Nearest-neighbor melting temperature for DNA oligonucleotides.

Source: section 7.3 and Appendix A of the engine capability system design.
Section 13.4 assigns this implementation to WP-04 (the primer and assembly
package) but requires it to live in a shared location from the start, because
WP-05 (guide RNA) may need it. It is therefore here, beside the other shared
sequence primitives, and has no dependency on anything under
`packages/validation/assembly` or `packages/generation/assembly`.

What this module does, stated exactly as section 16 of the spec permits:
nearest-neighbor thermodynamics with salt correction, verified against
reference oligos within 1 degree C. No claim beyond that is made anywhere.

The method, per section 7.3:

    dH_total = sum(dH of nearest-neighbor pairs) + dH(initiation terms)
    dS_total = sum(dS of nearest-neighbor pairs) + dS(initiation terms)
    Tm (K)   = (dH_total * 1000) / (dS_total + R * ln(k))
    Tm (C)   = Tm(K) - 273.15

where k is C_T / 4 for a non-self-complementary duplex and C_T for a
self-complementary one, C_T being the total strand concentration in mol/L. The
self-complementary case also takes the Appendix A symmetry correction. One
initiation term is applied per duplex end, chosen by that end's base pair.

Monovalent salt correction, Appendix A:

    dS(salt) = dS(1M) + 0.368 * (N - 1) * ln([Na+])

N is the oligo length in nucleotides, [Na+] in mol/L.

Nothing here is approximate by design: the Wallace rule and every
GC-percentage estimate are deliberately absent, because section 7.3 forbids
them and they are wrong by several degrees on real primers.

Verification (Appendix A.1, section 14.2, tolerance 1.0 degree C). Reference
values are computed by Biopython 1.87's `Bio.SeqUtils.MeltingTemp.Tm_NN` with
`nn_table=DNA_NN3` and `saltcorr=5`. That configuration corresponds to
Appendix A exactly: DNA_NN3 carries the same ten nearest-neighbor pairs, the
same terminal A/T (2.3, 4.1) and terminal G/C (0.1, -2.8) initiation terms and
the same symmetry correction (0.0, -1.4), and salt correction method 5 is
`0.368 * (N - 1) * ln([Na+])` applied to the entropy. The comparison is in
`tests/assembly/test_tm_reference.py` and the recorded table is in
`progress/WP-04.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .dna import clean_sequence, complement, gc_content, reverse_complement

# Universal gas constant, in cal/(mol K).
# Source: Appendix A of the engine capability system design, which fixes
# R = 1.987 cal/(mol K) so the implementation never has to recall it.
GAS_CONSTANT_R: float = 1.987

# Kelvin offset for degrees Celsius, as written in section 7.3.
KELVIN_OFFSET: float = 273.15

# Unified nearest-neighbor parameters for Watson-Crick pairs in 1 M NaCl.
# Source: Appendix A of the engine capability system design, reproducing
# SantaLucia 1998 (Proc Natl Acad Sci USA 95:1460-1465), the unified
# nearest-neighbor parameter set. Each key is the 5'-to-3' dinucleotide over
# its complement, exactly as Appendix A writes it. Values are
# (dH in kcal/mol, dS in cal/(mol K)).
NEAREST_NEIGHBOR_PARAMETERS: dict[str, tuple[float, float]] = {
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

# Initiation with a terminal G/C base pair, (dH kcal/mol, dS cal/(mol K)).
# Source: Appendix A initiation terms table.
INITIATION_TERMINAL_GC: tuple[float, float] = (0.1, -2.8)

# Initiation with a terminal A/T base pair, (dH kcal/mol, dS cal/(mol K)).
# Source: Appendix A initiation terms table.
INITIATION_TERMINAL_AT: tuple[float, float] = (2.3, 4.1)

# Symmetry correction, applied only to a self-complementary duplex,
# (dH kcal/mol, dS cal/(mol K)).
# Source: Appendix A initiation terms table.
SYMMETRY_CORRECTION: tuple[float, float] = (0.0, -1.4)

# Coefficient of the monovalent salt correction on entropy.
# Source: Appendix A salt correction formula,
# dS(salt) = dS(1M) + 0.368 * (N - 1) * ln([Na+]), which is SantaLucia 1998.
SALT_CORRECTION_COEFFICIENT: float = 0.368

# Coefficient converting a free divalent magnesium concentration into a
# monovalent sodium equivalent, in the formula
# [Na_eq] = [Na+] + 120 * sqrt([Mg2+] - [dNTP]).
# Source: von Ahsen N, Wittwer CT, Schutz E. "Oligonucleotide melting
# temperatures under PCR conditions: nearest-neighbor corrections for Mg2+,
# deoxynucleotide triphosphate, and dimethyl sulfoxide concentrations with
# comparison to alternative empirical formulas." Clin Chem 2001;47(11):1956-1961.
# Appendix E of the spec points at the Owczarzy treatments for divalent and
# mixed-ion conditions; the von Ahsen monovalent equivalent is the documented
# conversion used here because it is the conversion the reference tool applies
# (Biopython's `salt_correction` builds the same sodium equivalent and names
# the same paper) and because Primer3 uses it for the same purpose in
# `divalent_to_monovalent`. Using the same conversion as the reference tool is
# what makes the Appendix A.1 comparison a comparison of like with like.
DIVALENT_TO_MONOVALENT_COEFFICIENT: float = 120.0


@dataclass(frozen=True)
class ThermodynamicResult:
    """Everything the Tm calculation produced, so a caller can show its work.

    `delta_h_kcal_per_mol` and `delta_s_cal_per_mol_k` are the 1 M NaCl totals
    including initiation and, when applicable, the symmetry correction.
    `delta_s_salt_corrected_cal_per_mol_k` is the entropy after the Appendix A
    monovalent correction. `sodium_equivalent_mm` is the monovalent
    concentration actually used, which equals the supplied monovalent
    concentration unless a divalent conversion was applied.
    """

    sequence: str
    tm_celsius: float
    delta_h_kcal_per_mol: float
    delta_s_cal_per_mol_k: float
    delta_s_salt_corrected_cal_per_mol_k: float
    self_complementary: bool
    strand_concentration_term_molar: float
    sodium_equivalent_mm: float
    divalent_conversion_applied: bool
    gc_fraction: float

    @property
    def length(self) -> int:
        return len(self.sequence)


def is_self_complementary(sequence: str) -> bool:
    """True when the oligo is its own reverse complement.

    Section 7.3 requires the self-complementary duplex to use C_T rather than
    C_T / 4 and to take the Appendix A symmetry correction, so this test
    selects between the two cases. Detection is exact, not approximate: a
    sequence that merely contains a palindrome is not self-complementary.
    """
    cleaned = clean_sequence(sequence)
    return len(cleaned) > 0 and cleaned == reverse_complement(cleaned)


def nearest_neighbor_stack(sequence: str) -> tuple[float, float]:
    """Summed nearest-neighbor dH (kcal/mol) and dS (cal/(mol K)) for the stacks.

    Initiation, symmetry and salt are not included: this is the stacking sum
    alone.

    Appendix A writes each entry as "the 5'-to-3' dinucleotide over its
    complement", so the key for a top-strand dinucleotide XY is
    `XY/complement(XY)` with the bottom strand written 3' to 5' underneath,
    for example `GT/CA`. A stack absent from the table is looked up under its
    reading from the other strand, whose top-strand dinucleotide is
    `reverse_complement(XY)`. The two readings describe one physical stack,
    which is why Appendix A lists ten entries and not sixteen.
    """
    cleaned = clean_sequence(sequence)
    if len(cleaned) < 2:
        raise ValueError("a nearest-neighbor calculation needs at least 2 nucleotides")
    delta_h = 0.0
    delta_s = 0.0
    for index in range(len(cleaned) - 1):
        top = cleaned[index : index + 2]
        parameters = NEAREST_NEIGHBOR_PARAMETERS.get(f"{top}/{complement(top)}")
        if parameters is None:
            # The same stack read from the complementary strand, 5' to 3'.
            flipped = reverse_complement(top)
            parameters = NEAREST_NEIGHBOR_PARAMETERS.get(f"{flipped}/{complement(flipped)}")
        if parameters is None:  # pragma: no cover - the ten keys cover all 16 dinucleotides
            raise ValueError(f"no Appendix A nearest-neighbor parameter for stack {top!r}")
        delta_h += parameters[0]
        delta_s += parameters[1]
    return delta_h, delta_s


def initiation_terms(sequence: str) -> tuple[float, float]:
    """Initiation dH and dS: one term per duplex end, chosen by that end's base pair.

    Source: Appendix A, "Apply one initiation term per duplex end chosen by
    that end's base pair." The two ends of the duplex are the base pair formed
    by the first nucleotide and the base pair formed by the last, so a G or C
    at an end takes the terminal G/C term and an A or T takes the terminal A/T
    term. Both ends are counted even when they are the same.
    """
    cleaned = clean_sequence(sequence)
    if not cleaned:
        raise ValueError("initiation terms need a non-empty sequence")
    delta_h = 0.0
    delta_s = 0.0
    for base in (cleaned[0], cleaned[-1]):
        term = INITIATION_TERMINAL_GC if base in "GC" else INITIATION_TERMINAL_AT
        delta_h += term[0]
        delta_s += term[1]
    return delta_h, delta_s


def sodium_equivalent_mm(
    monovalent_salt_mm: float,
    divalent_salt_mm: float = 0.0,
    dntp_mm: float = 0.0,
    *,
    apply_divalent_conversion: bool = True,
) -> tuple[float, bool]:
    """Monovalent sodium equivalent in mM, and whether a divalent term was added.

    Section 7.3: "If magnesium and dNTPs are specified, convert to a monovalent
    equivalent before applying this; record which conversion was used in the
    docstring with its source."

    The conversion used is von Ahsen et al. 2001 (Clin Chem 47:1956-1961):

        [Na_eq] = [Na+] + 120 * sqrt([Mg2+] - [dNTP])      when [dNTP] < [Mg2+]
        [Na_eq] = [Na+]                                    otherwise

    all concentrations in mM. dNTPs chelate Mg2+, so when dNTPs are at or above
    the magnesium concentration there is no free magnesium left to contribute
    and the divalent term is dropped rather than extrapolated. This is the same
    conversion the Appendix A.1 reference tool applies (Biopython's
    `Bio.SeqUtils.MeltingTemp.salt_correction` builds the identical sodium
    equivalent and cites the same paper) and the same one Primer3 applies in
    `divalent_to_monovalent`, which is what keeps the A.1 comparison a
    comparison of like with like.

    Passing `apply_divalent_conversion=False` ignores the divalent inputs
    entirely. A caller that does so must say so in `parameters_used`, because
    section 3.3 constraint 4 forbids a silent degradation.
    """
    if monovalent_salt_mm < 0 or divalent_salt_mm < 0 or dntp_mm < 0:
        raise ValueError("salt and dNTP concentrations must not be negative")
    if not apply_divalent_conversion or divalent_salt_mm <= 0 or dntp_mm >= divalent_salt_mm:
        return monovalent_salt_mm, False
    free_divalent = divalent_salt_mm - dntp_mm
    equivalent = monovalent_salt_mm + DIVALENT_TO_MONOVALENT_COEFFICIENT * math.sqrt(free_divalent)
    return equivalent, True


def melting_temperature_detail(
    sequence: str,
    *,
    primer_conc_nm: float,
    monovalent_salt_mm: float,
    divalent_salt_mm: float = 0.0,
    dntp_mm: float = 0.0,
    apply_divalent_conversion: bool = True,
) -> ThermodynamicResult:
    """Nearest-neighbor Tm with salt correction, with the intermediate terms kept.

    `primer_conc_nm` is C_T, the total strand concentration, in nM, matching
    the `primer_conc_nm` field of the section 7.2 request schema.
    `monovalent_salt_mm`, `divalent_salt_mm` and `dntp_mm` are in mM, matching
    the same schema. Salt and dNTP handling is `sodium_equivalent_mm`, above.

    The strand concentration term is C_T / 4 for a non-self-complementary
    duplex and C_T for a self-complementary one, per section 7.3. The symmetry
    correction from Appendix A is applied only in the self-complementary case.
    """
    cleaned = clean_sequence(sequence)
    if len(cleaned) < 2:
        raise ValueError("a melting temperature needs at least 2 nucleotides")
    if primer_conc_nm <= 0:
        raise ValueError("primer_conc_nm must be positive: Tm depends on ln(strand concentration)")

    equivalent_mm, divalent_applied = sodium_equivalent_mm(
        monovalent_salt_mm,
        divalent_salt_mm,
        dntp_mm,
        apply_divalent_conversion=apply_divalent_conversion,
    )
    if equivalent_mm <= 0:
        raise ValueError(
            "the monovalent sodium equivalent is zero, so the Appendix A salt correction "
            "ln([Na+]) is undefined; supply a non-zero monovalent_salt_mm"
        )

    stack_h, stack_s = nearest_neighbor_stack(cleaned)
    init_h, init_s = initiation_terms(cleaned)
    delta_h = stack_h + init_h
    delta_s = stack_s + init_s

    self_complementary = is_self_complementary(cleaned)
    total_strand_molar = primer_conc_nm * 1e-9
    if self_complementary:
        delta_h += SYMMETRY_CORRECTION[0]
        delta_s += SYMMETRY_CORRECTION[1]
        concentration_term = total_strand_molar
    else:
        concentration_term = total_strand_molar / 4.0

    sodium_molar = equivalent_mm * 1e-3
    delta_s_salt = delta_s + SALT_CORRECTION_COEFFICIENT * (len(cleaned) - 1) * math.log(sodium_molar)

    denominator = delta_s_salt + GAS_CONSTANT_R * math.log(concentration_term)
    if denominator == 0:  # pragma: no cover - requires a pathological parameter set
        raise ValueError("the Tm denominator is zero for these parameters; Tm is undefined")
    tm_kelvin = (delta_h * 1000.0) / denominator
    return ThermodynamicResult(
        sequence=cleaned,
        tm_celsius=tm_kelvin - KELVIN_OFFSET,
        delta_h_kcal_per_mol=delta_h,
        delta_s_cal_per_mol_k=delta_s,
        delta_s_salt_corrected_cal_per_mol_k=delta_s_salt,
        self_complementary=self_complementary,
        strand_concentration_term_molar=concentration_term,
        sodium_equivalent_mm=equivalent_mm,
        divalent_conversion_applied=divalent_applied,
        gc_fraction=gc_content(cleaned),
    )


def melting_temperature(
    sequence: str,
    *,
    primer_conc_nm: float,
    monovalent_salt_mm: float,
    divalent_salt_mm: float = 0.0,
    dntp_mm: float = 0.0,
    apply_divalent_conversion: bool = True,
) -> float:
    """Nearest-neighbor Tm in degrees C. See `melting_temperature_detail`."""
    return melting_temperature_detail(
        sequence,
        primer_conc_nm=primer_conc_nm,
        monovalent_salt_mm=monovalent_salt_mm,
        divalent_salt_mm=divalent_salt_mm,
        dntp_mm=dntp_mm,
        apply_divalent_conversion=apply_divalent_conversion,
    ).tm_celsius
