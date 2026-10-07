"""Genetic codes, translation and ORF finding.

Source of the genetic codes: the NCBI genetic code tables
(https://www.ncbi.nlm.nih.gov/Taxonomy/Utils/wprintgc.cgi). Table 1 is the
standard code. Table 11 is the bacterial, archaeal and plant plastid code, which
has the same amino acid assignments as table 1 and a larger set of start
codons. The 64 codon strings below are the NCBI `gc.prt` layout (amino acids in
TCAG order over the three codon positions), and the start and stop sets are
those listed on the NCBI page for each table.

These are genetic codes, not codon usage tables. Host codon usage frequencies
(for choosing synonymous codons, section 7.6) are a separate dataset that each
caller must source and cite; none is bundled here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dna import clean_sequence, reverse_complement

_BASES = "TCAG"
_NCBI_TABLE_1_AMINO_ACIDS = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"

_CODONS: tuple[str, ...] = tuple(a + b + c for a in _BASES for b in _BASES for c in _BASES)


@dataclass(frozen=True)
class GeneticCode:
    """A genetic code: codon to amino acid map plus the start and stop codon sets."""

    table_id: int
    name: str
    codon_to_amino_acid: dict[str, str]
    start_codons: frozenset[str]
    stop_codons: frozenset[str]

    def translate_codon(self, codon: str) -> str:
        """Amino acid (one letter) for a codon, `*` for a stop. Raises KeyError for a non-codon."""
        return self.codon_to_amino_acid[codon.upper()]

    def synonymous_codons(self, codon: str) -> tuple[str, ...]:
        """All codons that encode the same amino acid as `codon`, including itself, sorted."""
        amino_acid = self.translate_codon(codon)
        return tuple(sorted(c for c, aa in self.codon_to_amino_acid.items() if aa == amino_acid))


_STANDARD_MAP = dict(zip(_CODONS, _NCBI_TABLE_1_AMINO_ACIDS))
_STOPS = frozenset(codon for codon, amino_acid in _STANDARD_MAP.items() if amino_acid == "*")

STANDARD_CODE = GeneticCode(
    table_id=1,
    name="Standard",
    codon_to_amino_acid=_STANDARD_MAP,
    start_codons=frozenset({"TTG", "CTG", "ATG"}),
    stop_codons=_STOPS,
)

BACTERIAL_CODE = GeneticCode(
    table_id=11,
    name="Bacterial, Archaeal and Plant Plastid",
    codon_to_amino_acid=_STANDARD_MAP,
    start_codons=frozenset({"TTG", "CTG", "ATT", "ATC", "ATA", "ATG", "GTG"}),
    stop_codons=_STOPS,
)

GENETIC_CODES: dict[int, GeneticCode] = {STANDARD_CODE.table_id: STANDARD_CODE, BACTERIAL_CODE.table_id: BACTERIAL_CODE}


def translate(sequence: str, code: GeneticCode = STANDARD_CODE, *, to_stop: bool = False) -> str:
    """Translate in frame from the first base.

    The length must be a multiple of three; a trailing partial codon raises
    ValueError rather than being dropped silently. With `to_stop` translation
    ends at the first stop codon, which is not included.
    """
    cleaned = clean_sequence(sequence)
    if len(cleaned) % 3:
        raise ValueError(f"sequence length {len(cleaned)} is not a multiple of 3")
    protein: list[str] = []
    for index in range(0, len(cleaned), 3):
        amino_acid = code.codon_to_amino_acid[cleaned[index : index + 3]]
        if amino_acid == "*" and to_stop:
            break
        protein.append(amino_acid)
    return "".join(protein)


@dataclass(frozen=True)
class Orf:
    """An open reading frame on `strand` (+1 or -1).

    `start` and `end` are zero-based, end exclusive, on the strand that was
    scanned. For a reverse strand ORF they are coordinates in the reverse
    complement; `forward_start` and `forward_end` give the same interval on the
    original sequence.
    """

    start: int
    end: int
    strand: int
    frame: int
    has_stop: bool
    forward_start: int
    forward_end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def find_orfs(
    sequence: str,
    *,
    min_length_nt: int,
    code: GeneticCode = STANDARD_CODE,
    start_codons: frozenset[str] | None = None,
    both_strands: bool = True,
    require_stop: bool = True,
) -> list[Orf]:
    """Find open reading frames, one per stop codon, starting at the outermost start codon.

    `min_length_nt` has no default because a minimum ORF length is a design
    choice of the caller, not a biological constant. It counts nucleotides and
    includes the start codon and the stop codon when one is present.

    Scanning runs over the three forward frames and, with `both_strands`, the
    three frames of the reverse complement. For each stop codon the ORF begins at
    the first (outermost) start codon after the previous stop in that frame.
    With `require_stop=False`, an open frame that reaches the end of the
    sequence without a stop is also reported, with `has_stop` False.

    `start_codons` defaults to the start set of `code`. Results are sorted by
    forward start, then strand, then length.
    """
    if min_length_nt < 1:
        raise ValueError("min_length_nt must be at least 1")
    cleaned = clean_sequence(sequence)
    starts = start_codons if start_codons is not None else code.start_codons
    total = len(cleaned)
    found: list[Orf] = []
    strands: list[tuple[int, str]] = [(1, cleaned)]
    if both_strands:
        strands.append((-1, reverse_complement(cleaned)))
    for strand, scanned in strands:
        for frame in range(3):
            open_start: int | None = None
            position = frame
            while position + 3 <= total:
                codon = scanned[position : position + 3]
                if open_start is None and codon in starts:
                    open_start = position
                if codon in code.stop_codons:
                    if open_start is not None:
                        found.append(_make_orf(open_start, position + 3, strand, frame, True, total))
                    open_start = None
                position += 3
            if open_start is not None and not require_stop:
                found.append(_make_orf(open_start, position, strand, frame, False, total))
    return sorted(
        (orf for orf in found if orf.length >= min_length_nt),
        key=lambda orf: (orf.forward_start, -orf.strand, -orf.length),
    )


def _make_orf(start: int, end: int, strand: int, frame: int, has_stop: bool, total: int) -> Orf:
    if strand == 1:
        forward_start, forward_end = start, end
    else:
        forward_start, forward_end = total - end, total - start
    return Orf(start, end, strand, frame, has_stop, forward_start, forward_end)
