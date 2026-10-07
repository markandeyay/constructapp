"""Basic DNA operations shared by every capability.

Source: section 13.4 of the engine capability system design (reverse
complement, GC content). The IUPAC ambiguity table is the standard IUPAC
nucleotide code (Nucleic Acids Research 13:3021, 1985, doi:10.1093/nar/13.9.3021, the
nomenclature adopted by NCBI GenBank). Nothing here is a fitted constant.
"""

from __future__ import annotations

STRICT_ALPHABET = frozenset("ACGT")

# IUPAC nucleotide ambiguity codes: code -> the bases it stands for.
IUPAC_CODES: dict[str, frozenset[str]] = {
    "A": frozenset("A"),
    "C": frozenset("C"),
    "G": frozenset("G"),
    "T": frozenset("T"),
    "R": frozenset("AG"),
    "Y": frozenset("CT"),
    "S": frozenset("CG"),
    "W": frozenset("AT"),
    "K": frozenset("GT"),
    "M": frozenset("AC"),
    "B": frozenset("CGT"),
    "D": frozenset("AGT"),
    "H": frozenset("ACT"),
    "V": frozenset("ACG"),
    "N": frozenset("ACGT"),
}

_COMPLEMENT_TABLE = str.maketrans(
    "ACGTRYSWKMBDHVN",
    "TGCAYRSWMKVHDBN",
)


def clean_sequence(sequence: str, *, allow_ambiguous: bool = False) -> str:
    """Upper-case a sequence, strip whitespace, and reject anything that is not DNA.

    By default only A, C, G and T are accepted. With `allow_ambiguous` the IUPAC
    ambiguity codes are accepted as well. Raises ValueError on an empty
    sequence or an unexpected character, so a malformed input fails loudly
    instead of being silently scored.
    """
    if not isinstance(sequence, str):
        raise TypeError("DNA sequence must be a string")
    cleaned = "".join(sequence.upper().split())
    if not cleaned:
        raise ValueError("DNA sequence must not be empty")
    allowed = IUPAC_CODES.keys() if allow_ambiguous else STRICT_ALPHABET
    invalid = sorted(set(cleaned) - set(allowed))
    if invalid:
        raise ValueError(f"DNA sequence contains unsupported characters: {''.join(invalid)}")
    return cleaned


def complement(sequence: str) -> str:
    """Complement a sequence without reversing it. IUPAC codes are complemented too."""
    return clean_sequence(sequence, allow_ambiguous=True).translate(_COMPLEMENT_TABLE)


def reverse_complement(sequence: str) -> str:
    """Reverse complement of a DNA sequence (IUPAC codes accepted)."""
    return complement(sequence)[::-1]


def gc_count(sequence: str) -> int:
    """Number of G and C bases in an unambiguous sequence."""
    return sum(1 for base in clean_sequence(sequence) if base in "GC")


def gc_content(sequence: str) -> float:
    """Fraction of bases that are G or C, in the range 0.0 to 1.0.

    Ambiguity codes are rejected rather than guessed, because a fraction over a
    partly unknown sequence would be misleading. Windows and thresholds belong to
    the calling capability; this function only measures.
    """
    cleaned = clean_sequence(sequence)
    return sum(1 for base in cleaned if base in "GC") / len(cleaned)
