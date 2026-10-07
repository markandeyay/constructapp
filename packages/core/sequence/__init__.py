"""Shared sequence utilities (section 13.4 of the engine capability system design).

Reverse complement, GC content, genetic codes and ORF finding, sequence search
primitives and pairwise alignment, used by the primer, guide RNA and AAV
capabilities. The nearest-neighbor Tm implementation is not here: section 13.4
assigns it to the primer and assembly package.
"""

from .align import (
    UNIT_COST_SCORING,
    Alignment,
    AlignmentScoring,
    edit_distance,
    global_align,
    global_identity,
    local_align,
)
from .codon import BACTERIAL_CODE, GENETIC_CODES, STANDARD_CODE, GeneticCode, Orf, find_orfs, translate
from .dna import (
    IUPAC_CODES,
    STRICT_ALPHABET,
    clean_sequence,
    complement,
    gc_content,
    gc_count,
    reverse_complement,
)
from .search import (
    Hit,
    Repeat,
    Run,
    direct_repeats,
    find_both_strands,
    find_exact,
    find_iupac,
    find_with_mismatches,
    hamming_distance,
    homopolymer_runs,
    matches_iupac,
)

__all__ = [
    "Alignment",
    "AlignmentScoring",
    "BACTERIAL_CODE",
    "GENETIC_CODES",
    "GeneticCode",
    "Hit",
    "IUPAC_CODES",
    "Orf",
    "Repeat",
    "Run",
    "STANDARD_CODE",
    "STRICT_ALPHABET",
    "UNIT_COST_SCORING",
    "clean_sequence",
    "complement",
    "direct_repeats",
    "edit_distance",
    "find_both_strands",
    "find_exact",
    "find_iupac",
    "find_orfs",
    "find_with_mismatches",
    "gc_content",
    "gc_count",
    "global_align",
    "global_identity",
    "hamming_distance",
    "homopolymer_runs",
    "local_align",
    "matches_iupac",
    "reverse_complement",
    "translate",
]
